from google.cloud import ndb

import json
import logging as log
import random
import time

from util import enums_from_strlist, picks_by_coord, get_preset_from_paths, compose_multi_value, decompose_multi_value, normalize_pickup, split_owner, SEED_FORMAT
from enums import (MultiplayerGameType, ShareType, Variation, LogicPath, KeyMode, PathDifficulty, presets,
                   preset_path_diff, preset_variations)
from collections import OrderedDict
from threading import Lock
from cachetools import TTLCache
from seedbuilder.generator import SeedGenerator, MultiworldSlotOverflow

# Process-local inflated params, shared and READ-ONLY (mutate-and-put paths use key.get()).
# Correct only single-instance; puts bust it via the model hooks, the TTL covers deploy overlap.
_PARAMS_CACHE = TTLCache(maxsize=8, ttl=120)
_PARAMS_LOCK = Lock()

JSON_SHARE = lambda x: x.value if x != ShareType.EVENT else "World Events"

def normalize_pool(pool):
    return {normalize_pickup(k): v for k, v in (pool or {}).items()}


def pool_from_query(raw):
    """An item pool sent as JSON in the seedgen page's shape ({"HC|1": [12], "WP|*": [4, 8]});
    ValueError when it isn't one."""
    pool = json.loads(raw)
    def counts_ok(v):
        return isinstance(v, list) and len(v) in (1, 2) and all(type(n) is int and n >= 0 for n in v)
    if not isinstance(pool, dict) or not all(isinstance(k, str) and counts_ok(v) for k, v in pool.items()):
        raise ValueError("not an item pool")
    return normalize_pool(pool)


def spawn_weights(ws):
    """A blank weight arrives as null (NaN in JSON); it reads as 0."""
    return [float(w) if isinstance(w, (int, float)) else 0.0 for w in (ws or [])]


def player_cap_problem(params):
    from util import MAX_PLAYERS
    if int(getattr(params, "players", 1) or 1) > MAX_PLAYERS:
        return "Seeds can have at most %s players." % MAX_PLAYERS
    return None


def seed_mode_problem(params):
    """User-facing reason this seed request can't be built, or None. The Archipelago
    kill switch refuses creation too."""
    from util import ARCHIPELAGO
    cap = player_cap_problem(params)
    if cap:
        return cap
    players = int(getattr(params, "players", 1) or 1)
    for w in range(1, players + 1):
        view = world_view(params, w)
        if getattr(view, "start", None) in ("Horu", "Ginso") and Variation.CLOSED_DUNGEONS in (getattr(view, "variations", None) or []):
            return "Closed Dungeons can't start in %s." % view.start
        # the basic routes are all casual-core, so no seed can finish without it
        paths = getattr(view, "logic_paths", None)
        if paths is not None and LogicPath.CASUAL_CORE not in paths:
            return "%s needs the Casual Core logic path." % ("World %d" % w if players > 1 else "This seed")
    ap_mode = getattr(params, "ap_mode", False)
    if ap_mode:
        # ahead of the singleplayer early return: K=1 AP is still an AP seed
        if not ARCHIPELAGO:
            return "Archipelago support is switched off right now."
        # the bridge delivers through the netcode
        if not (params.sync.enabled and params.tracking):
            return "Archipelago seeds need tracking (the room talks to the game over netcode)."
    if not params.sync.enabled:
        return None
    if params.sync.mode == MultiplayerGameType.MULTIWORLD:
        if not params.tracking:
            return "Multiworld requires tracking (it's netcode all the way down)."
        # getattr: CLI params carry no placements
        for placement in getattr(params, "placements", None) or []:
            s = placement.stuff[0]
            for ref in (s.player, getattr(s, "owner", None)):
                try:
                    if ref and not (1 <= int(ref) <= params.players):
                        return "Preplacement references player %s, but this game only has %s players." % (ref, params.players)
                except ValueError:
                    return "Preplacement references invalid player %r." % ref
    if ap_mode:
        if params.sync.mode != MultiplayerGameType.MULTIWORLD:
            return "Archipelago seeds use Multiworld mode."
        from archipelago.convert import DEFAULT_EXPORT, share_export_clash
        exported = set(getattr(params, "ap_export", None) or []) or set(DEFAULT_EXPORT)
        clash = share_export_clash(params.sync.shared, exported)
        if clash:
            return "Archipelago export and shared categories overlap: %s." % ", ".join(clash)
    if (ShareType.EVENT in (getattr(params.sync, "shared", None) or [])
            and getattr(params, "world_settings", None)):
        modes = {params.world_params(w).key_mode for w in range(1, (params.players or 1) + 1)}
        if KeyMode.SHARDS in modes and len(modes) > 1:
            return ("Sharing World Events needs every world on the same dungeon keys: "
                    "Shards splits each event into five pieces, so a mixed lobby has "
                    "nothing to share.")
    if params.sync.mode == MultiplayerGameType.SPLITSHARDS:
        return "SplitShards was removed (2026-07). Consider Multiworld with Shards keymode."
    if params.sync.mode == MultiplayerGameType.SHARED and not params.sync.cloned:
        return "Seperate Seeds generation was removed (2026-07). Use Cloned Seeds or Multiworld."
    return None


def seed_failure_reason(params):
    """Why a failed roll likely failed, for known-bad combinations, else None. Read only
    after a real attempt; refuses nothing."""
    if (params.sync.enabled and params.sync.mode == MultiplayerGameType.MULTIWORLD
            and not getattr(params, "balanced", True)):
        return ("Classic fill often can't finish a multiworld seed. Switch the fill "
                "algorithm to Balanced under Advanced, or try again.")
    return None


def bingo_worlds(params):
    """The worlds whose own variations include Bingo."""
    return [w for w in range(1, int(getattr(params, "players", 1) or 1) + 1)
            if Variation.BINGO in world_view(params, w).variations]


def rolled_player_names(names, params):
    """Sanitized per-world names, trailing blanks dropped; none for a non-multiworld,
    non-AP bingo seed (its lobby names players)."""
    multiworld = getattr(getattr(params, "sync", None), "mode", None) == MultiplayerGameType.MULTIWORLD
    if (Variation.BINGO in (getattr(params, "variations", None) or [])
            and not multiworld and not getattr(params, "ap_mode", False)):
        return []
    from ap_models import sanitize_display_name, PLAYER_NAME_MAX
    out = [sanitize_display_name(str(n or ""), PLAYER_NAME_MAX)
           for n in (names or [])][:int(getattr(params, "players", 0) or 0)]
    while out and not out[-1]:
        out.pop()
    return out


FLAGLESS_VARS = [Variation.WARMTH_FRAGMENTS, Variation.WORLD_TOUR]
JSON_GAME_MODE = {MultiplayerGameType.SHARED: "Co-op", MultiplayerGameType.SIMUSOLO: "Race", MultiplayerGameType.MULTIWORLD: "Multiworld", MultiplayerGameType.SPLITSHARDS: "SplitShards"}
JSON_MODE_GAME = {v:k for k,v in JSON_GAME_MODE.items()}
PBC = picks_by_coord(extras=True)

class Stuff(ndb.Model):
    code = ndb.StringProperty()
    id = ndb.StringProperty()
    player = ndb.StringProperty()
    # whose item this is when not the holding world (player)
    owner = ndb.StringProperty()

class Placement(ndb.Model):
    location = ndb.StringProperty()
    zone = ndb.StringProperty()
    stuff = ndb.LocalStructuredProperty(Stuff, repeated=True)

# a box seed line (BX|...), per world, kept as written; the client reads it
class BoxLine(ndb.Model):
    player = ndb.StringProperty()
    line = ndb.StringProperty()
    # editor-only: a locked box is read-only in the plando builder
    locked = ndb.BooleanProperty(default=False)

class MultiplayerOptions(ndb.Model):
    str_mode = ndb.StringProperty(default="None")
    str_shared = ndb.StringProperty(repeated=True)

    def get_mode(self): return MultiplayerGameType.mk(self.str_mode) or MultiplayerGameType.SIMUSOLO

    def set_mode(self, mode):         self.str_mode = mode.value

    def get_shared(self): return enums_from_strlist(ShareType, self.str_shared)

    def set_shared(self, shared):    self.str_shared = [s.value for s in shared]

    mode = property(get_mode, set_mode)
    shared = property(get_shared, set_shared)
    enabled = ndb.BooleanProperty(default=False)
    cloned = ndb.BooleanProperty(default=True)
    hints = ndb.BooleanProperty()
    dedup = ndb.BooleanProperty(default=False)
    teams = ndb.JsonProperty()

    @staticmethod
    def from_url(qparams):
        opts = MultiplayerOptions()
        opts.enabled = int(qparams.get("players", 1)) > 1
        if opts.enabled:
            opts.mode = MultiplayerGameType(qparams.get("sync_mode", "None"))
            opts.cloned = qparams.get("sync_gen") != "disjoint"
            if opts.cloned:
                opts.dedup = bool(qparams.get("dedup_shared", False))
            opts.shared = enums_from_strlist(ShareType, qparams.getlist("sync_shared"))
            teamsRaw = qparams.get("teams")
            if teamsRaw and opts.mode == MultiplayerGameType.SHARED and opts.cloned:
                cnt = 1
                teams = {}
                for teamRaw in teamsRaw.split("|"):
                    teams[cnt] = [int(p) for p in teamRaw.split(",")]
                    cnt += 1
                opts.teams = teams
        return opts
    @staticmethod
    def from_json(json):
        opts = MultiplayerOptions()
        # a solo AP world still needs the netcode: the bridge delivers through it
        ap_mode = bool(json.get("apMode", False))
        opts.enabled = json.get("players", 1) > 1 or ap_mode
        opts.teams = json.get("teams", {})
        if opts.enabled:
            jsonMode = json.get("coopGameMode", "None")
            opts.mode = JSON_MODE_GAME[jsonMode] if jsonMode in JSON_MODE_GAME else MultiplayerGameType(jsonMode)
            if ap_mode:
                opts.mode = MultiplayerGameType.MULTIWORLD  # SyncMode 5: the client only reads slot bitfields there
            # cloned/teams are SHARED-only: multiworld teams would hand everyone world 1's seed
            opts.cloned = json.get("coopGenMode") != "disjoint" and opts.mode != MultiplayerGameType.MULTIWORLD
            if opts.cloned:
                opts.teams = {1: list(range(1, json.get("players", 1) + 1))}
                opts.dedup = bool(json.get("dedupShared", False))
            opts.shared = enums_from_strlist( ShareType, [a.replace(" ", "") for a in json.get("syncShared", json.get("shared", []))]) #shit fuck ass jank shit
        return opts

    def get_team_str(self):
        if self.teams:
            return "|".join(",".join(str(p) for p in team) for team in self.teams.values())
        return ""

# per-world override keys (page/preset json) -> (attribute, converter); omitted keys keep the seed's value
WORLD_FIELDS = {
    "paths":          ("logic_paths",     lambda v: enums_from_strlist(LogicPath, v)),
    "pathDiff":       ("path_diff",       PathDifficulty),
    "keyMode":        ("key_mode",        KeyMode),
    "variations":     ("variations",      lambda v: enums_from_strlist(Variation, v)),
    "expPool":        ("exp_pool",        int),
    "cellFreq":       ("cell_freq",       int),
    "fragCount":      ("frag_count",      int),
    "fragReq":        ("frag_req",        int),
    "relicCount":     ("relic_count",     int),
    "bingoLines":     ("bingo_lines",     int),
    "bingoDiff":      ("bingo_diff",      str),
    "bingoGoal":      ("bingo_goal",      str),
    "bingoSquares":   ("bingo_squares",   int),
    "bingoMeta":      ("bingo_meta",      bool),
    "bingoDisc":      ("bingo_disc",      int),
    "itemPool":       ("item_pool",       normalize_pool),
    "selectedPool":   ("pool_preset",     str),
    "spawn":          ("start",           str),
    "spawnECs":       ("starting_energy", int),
    "spawnHCs":       ("starting_health", int),
    "spawnSKs":       ("starting_skills", int),
    "spawnWeights":   ("spawn_weights",   spawn_weights),
    "senseData":      ("sense",           lambda v: v),
    "verboseSpoiler": ("verbose_spoiler", bool),
}


def all_fass(json):
    """The seed's forced assignments plus each world's own; a world's rows default to
    that world as both host and owner."""
    rows = list(json.get("fass") or [])
    for world, blob in enumerate(json.get("worldSettings") or [], 1):
        for row in (blob or {}).get("fass") or []:
            tagged = dict(row)
            tagged.setdefault("world", world)
            tagged.setdefault("owner", tagged["world"])
            rows.append(tagged)
    return rows


def spawn_view(base, world):
    """Where that world starts; older seeds fall back to the summary (maybe "Random")."""
    spawns = getattr(base, "spawns", None) or []
    return spawns[world - 1] if 0 < world <= len(spawns) else base.spawn


def world_view(base, p):
    """World p's settings; the base object itself when that world has no overrides."""
    settings = getattr(base, "world_settings", None) or []
    blob = settings[p - 1] if 0 < p <= len(settings) else None
    if not blob:
        return base
    over = {}
    for key, (attr, conv) in WORLD_FIELDS.items():
        if key in blob and blob[key] is not None:
            over[attr] = conv(blob[key])
    return WorldParams(base, over) if over else base


class WorldParams(object):
    """One world's view: its overrides, else read live off the base entity (writes go to the base)."""
    __slots__ = ("_base", "_over")

    def __init__(self, base, over):
        object.__setattr__(self, "_base", base)
        object.__setattr__(self, "_over", over)

    def __getattr__(self, name):
        over = object.__getattribute__(self, "_over")
        if name in over:
            return over[name]
        base = object.__getattribute__(self, "_base")
        # settings methods rebind to the view; anything ndb.Model defines stays on the entity
        own = type(base).__dict__.get(name)
        if isinstance(own, type(lambda: 0)) and not hasattr(ndb.Model, name):
            return own.__get__(self, type(self))
        return getattr(base, name)

    def __setattr__(self, name, value):
        setattr(object.__getattribute__(self, "_base"), name, value)


class SeedGenParams(ndb.Model):
    str_vars = ndb.StringProperty(repeated=True)
    str_paths = ndb.StringProperty(repeated=True)
    str_pathdiff = ndb.StringProperty(default=PathDifficulty.NORMAL.value)
    str_keymode = ndb.StringProperty(default=KeyMode.CLUES.value)

    def get_pathdiff(self): return PathDifficulty(self.str_pathdiff)

    def set_pathdiff(self, pathdiff): self.str_pathdiff = pathdiff.value

    def get_vars(self): return enums_from_strlist(Variation, self.str_vars)

    def set_vars(self, vars): self.str_vars = [v.value for v in vars]

    def get_paths(self): return enums_from_strlist(LogicPath, self.str_paths)

    def set_paths(self, paths): self.str_paths = [p.value for p in paths]

    def get_keymode(self): return KeyMode(self.str_keymode)

    def set_keymode(self, key_mode):     self.str_keymode = key_mode.value
    seed = ndb.StringProperty(required=True)
    variations = property(get_vars, set_vars)
    logic_paths = property(get_paths, set_paths)
    key_mode = property(get_keymode, set_keymode)
    path_diff = property(get_pathdiff, set_pathdiff)
    exp_pool = ndb.IntegerProperty(default=10000)
    balanced = ndb.BooleanProperty(default=True)
    tracking = ndb.BooleanProperty(default=True)
    players = ndb.IntegerProperty(default=1)
    created_on = ndb.DateTimeProperty(auto_now_add=True)
    sync = ndb.LocalStructuredProperty(MultiplayerOptions)
    frag_count = ndb.IntegerProperty(default=30)
    frag_req = ndb.IntegerProperty(default=20)
    relic_count = ndb.IntegerProperty(default=8)
    cell_freq = ndb.IntegerProperty(default=256)
    anti_bk_bias = ndb.FloatProperty(default=0.0)
    # the UI's fass list verbatim, for rerolls (placements can't carry world/owner)
    fass_json = ndb.JsonProperty()
    placements = ndb.LocalStructuredProperty(Placement, repeated=True, compressed=True)
    boxes = ndb.LocalStructuredProperty(BoxLine, repeated=True)
    spawn_placement = ndb.LocalStructuredProperty(Placement)
    preplaced_coords = ndb.IntegerProperty(repeated=True)
    spoilers = ndb.TextProperty(repeated=True, compressed=True)
    sense = ndb.StringProperty()
    is_plando = ndb.BooleanProperty(default=False)
    # set only when the plando has a spoiler (the text stays on the Seed)
    plando_spoiler_key = ndb.KeyProperty(kind="Seed")
    plando_flags = ndb.StringProperty(repeated=True)
    # {world: [[home, target], ...]}: the generator's keystone-door sighting order
    ks_door_order = ndb.JsonProperty()
    item_pool = ndb.JsonProperty()
    pool_preset = ndb.StringProperty()
    bingo_lines = ndb.IntegerProperty(default=3)
    # what a world's board looks like; bingo_disc 0 means discovery is off
    bingo_diff = ndb.StringProperty(default="normal")
    bingo_goal = ndb.StringProperty(default="bingos")
    bingo_squares = ndb.IntegerProperty(default=13)
    bingo_meta = ndb.BooleanProperty(default=False)
    bingo_disc = ndb.IntegerProperty(default=0)
    start = ndb.StringProperty(default="Glades")
    spawn = ndb.StringProperty(default="Glades")
    starting_health = ndb.IntegerProperty(default=3)
    starting_energy = ndb.IntegerProperty(default=1)
    starting_skills = ndb.IntegerProperty(default=0)
    spawn_weights = ndb.FloatProperty(repeated=True)
    verbose_spoiler = ndb.BooleanProperty(default=False)
    # ap_export: categories handed to the AP pool; empty means the default set
    ap_mode = ndb.BooleanProperty(default=False)
    ap_export = ndb.StringProperty(repeated=True)
    # index 0 = player 1; blanks fall back to "Player N" / "OriN"
    player_names = ndb.StringProperty(repeated=True)
    # deaths cross between this seed's worlds and the AP room, both ways
    ap_death_link = ndb.BooleanProperty(default=False)
    # index i overrides world i+1's settings; empty means every world plays the same seed
    world_settings = ndb.JsonProperty(repeated=True, compressed=True)
    # the spot each world actually starts at, once "Random" has been rolled
    spawns = ndb.StringProperty(repeated=True)
    do_loc_analysis = False
    areas_ori_path = ""

    def world_params(self, p):
        return world_view(self, p)

    def spawn_for(self, world):
        return spawn_view(self, world)

    @staticmethod
    def from_plando(plando, tracking=True):
        params = SeedGenParams(
            seed = plando.name,
            players = plando.players,
            tracking = tracking,
            is_plando=True, 
            plando_flags = plando.flags,
            placements = plando.placements,
            boxes = plando.boxes,
            # a description-less plando is a legal row; spoilers is a string list
            spoilers = [plando.description or ""],
            plando_spoiler_key = plando.key if plando.spoiler else None,
            )
        params.sync = MultiplayerOptions()
        params.sync.enabled = plando.players > 1
        mode = plando.mode()
        if mode is None and plando.players > 1:
            # older plandos lack mode=; SIMUSOLO would serve player 1's seed to everyone
            mode = MultiplayerGameType.SHARED
        if mode:
            params.sync.mode = mode
        params.sync.shared = plando.shared()
        for flag in plando.flags:
            if flag.capitalize() in presets:
                params.logic_paths = presets[flag.capitalize()]
                break
        params.set_vars(enums_from_strlist(Variation, plando.flags))
        params.put()
        return params

    @staticmethod
    def from_json(json):
        params = SeedGenParams()
        seed = json.get("seed")
        params.seed = "" if seed is None else str(seed)
        if not params.seed:
            log.error("No seed in %r! returning None" % json)
            return None
        params.variations = enums_from_strlist(Variation, json.get("variations", []))
        params.logic_paths = enums_from_strlist(LogicPath, json.get("paths", []))
        if not params.logic_paths:
            log.error("No logic paths in %r! returning None" % json)
            return None
        params.key_mode = KeyMode(json.get("keyMode", "Clues"))
        params.path_diff = PathDifficulty(json.get("pathDiff", "Normal"))
        params.exp_pool = json.get("expPool", 10000)
        params.balanced = json.get("fillAlg") != "Classic"
        params.players = json.get("players", 1)
        params.tracking = json.get("tracking") or bool(json.get("apMode", False))
        params.frag_count = json.get("fragCount", 30)
        params.frag_req = json.get("fragReq", 20)
        params.relic_count = json.get("relicCount", 8)
        params.cell_freq = json.get("cellFreq", 256)
        params.anti_bk_bias = min(1.0, max(0.0, float(json.get("antiBkBias", 0) or 0)))
        params.sync = MultiplayerOptions.from_json(json)
        params.sense = json.get("senseData")
        params.item_pool = normalize_pool(json.get("itemPool"))
        params.bingo_lines = json.get("bingoLines", 3)
        params.bingo_diff = json.get("bingoDiff", "normal")
        params.bingo_goal = json.get("bingoGoal", "bingos")
        params.bingo_squares = json.get("bingoSquares", 13)
        params.bingo_meta = bool(json.get("bingoMeta", False))
        params.bingo_disc = json.get("bingoDisc", 0)
        params.pool_preset = json.get("selectedPool", "Standard")
        params.placements = []
        params.preplaced_coords = []
        params.fass_json = json.get("fass", []) or None
        for fass in all_fass(json):
            if "item" in fass: # this is stupid af but it's a faster way to handle the json mismatch than the other fixes available
                pcode, _, pid = normalize_pickup(fass["item"]).partition("|")
            else:
                pcode, pid  = fass["code"], fass["id"]
            world = str(fass.get("world", 1) or 1)
            # spawn items are granted at that world's start, never cross-world
            owner = world if fass["loc"] == "2" else str(fass.get("owner", world) or world)
            params.placements.append(Placement(location=fass["loc"], zone="", stuff=[Stuff(code=pcode, id=pid, player=world, owner=owner)]))
            if fass["loc"] == "2" and world == "1":  # kept apart: seedgen adds its own items at loc 2
                params.spawn_placement = Placement(location=fass["loc"], zone="", stuff=[Stuff(code=pcode, id=pid, player=world)])
            elif fass["loc"] != "2":
                params.preplaced_coords.append(int(fass["loc"]))
        params.starting_energy = json.get("spawnECs", 1)
        params.starting_health = json.get("spawnHCs", 3)
        params.starting_skills = json.get("spawnSKs", 0)
        params.start = json.get("spawn", "Glades")
        params.spawn_weights = spawn_weights(json.get("spawnWeights"))
        params.verbose_spoiler = json.get("verboseSpoiler", False)
        from archipelago.convert import normalize_categories
        params.ap_export = normalize_categories(str(c) for c in json.get("apExport", []))
        params.ap_mode = bool(json.get("apMode")) or bool(params.ap_export)
        params.ap_death_link = params.ap_mode and bool(json.get("apDeathLink"))
        params.player_names = rolled_player_names(json.get("playerNames", []), params)
        params.world_settings = [w or {} for w in (json.get("worldSettings") or [])]
        if params.ap_mode:
            from archipelago.convert import EXPORTABLE_CATEGORIES
            bad = [c for c in params.ap_export if c not in EXPORTABLE_CATEGORIES]
            if bad:
                log.error("Unknown AP export categories %r! returning None", bad)
                return None
        return params.put()

    @staticmethod
    def from_url(qparams):
        params = SeedGenParams()
        # a caller with nothing to say about the seed gets the clock, not an error
        params.seed = qparams.get("seed") or str(int(time.time()))
        params.variations = enums_from_strlist(Variation, qparams.getlist("var"))
        params.logic_paths = enums_from_strlist(LogicPath, qparams.getlist("path"))
        # paths and vars add to the mode's; path_diff replaces, having nothing to add to
        group = qparams.get("logic_mode")
        if group:
            group = group.capitalize()
            if group not in presets:
                log.error("Unknown logic_mode %r; expected one of %s",
                          qparams.get("logic_mode"), ", ".join(sorted(presets)))
                return None
            params.logic_paths = sorted(set(params.logic_paths) | presets[group])
            params.variations = sorted(set(params.variations) | preset_variations.get(group, set()))
        if not params.logic_paths:
            log.error("No logic paths in %r! returning None" % qparams)
            return None
        params.key_mode = KeyMode(qparams.get("key_mode", "Clues"))
        default_diff = preset_path_diff.get(group, PathDifficulty.NORMAL)
        params.path_diff = PathDifficulty(qparams.get("path_diff", default_diff))
        params.exp_pool = int(qparams.get("exp_pool", 10000))
        params.balanced = qparams.get("gen_mode") != "Classic"
        params.players = int(qparams.get("players", 1))
        params.tracking = qparams.get("tracking") != "Disabled"
        params.frag_count = int(qparams.get("frags", 30))
        params.frag_req = int(qparams.get("frags_req", 20))
        params.relic_count = int(qparams.get("relics", 8))
        params.cell_freq = int(qparams.get("cell_freq", 256))
        params.anti_bk_bias = min(1.0, max(0.0, float(qparams.get("anti_bk_bias", 0) or 0)))
        params.sync = MultiplayerOptions.from_url(qparams)
        params.sense = qparams.get("sense")
        params.pool_preset = qparams.get("pool_preset", "Standard").title()
        params.item_pool = {}
        params.start = qparams.get("spawn", "Glades")
        params.starting_energy = int(qparams.get("spawnECs", 1))
        params.starting_health = int(qparams.get("spawnHCs", 3))
        params.starting_skills = int(qparams.get("spawnSKs", 0))
        params.verbose_spoiler = qparams.get("verboseSpoiler", "") == "true"
        raw_pool = qparams.get("item_pool")
        if raw_pool:
            params.item_pool = pool_from_query(raw_pool)
        else:
            # a pool named outright beats the BonusPickups variation's
            bonus = Variation.EXTRA_BONUS_PICKUPS in params.variations and not qparams.get("pool_preset")
            if bonus or params.pool_preset == "Extra Bonus":
                params.pool_preset = "Extra Bonus"
                params.item_pool = { 
                  "TP|Grove": [1], "TP|Swamp": [1], "TP|Grotto": [1], "TP|Valley": [1], "TP|Sorrow": [1], "TP|Ginso": [1],
                  "TP|Horu": [1], "TP|Forlorn": [1], "TP|Blackroot": [1], "HC|1": [12], "EC|1": [15], "AC|1": [33], "RP|RB/0": [3], "RP|RB/1": [3], 
                  "RB|6": [5], "RB|9": [1], "RB|10": [1], "RB|11": [1], "RB|12": [2], "RB|37": [2], "RB|13": [3], "RB|15": [3],
                  "RB|31": [1], "RB|32": [1], "RB|33": [2], "RG|RB/12/RB/33/RB/37": [3], "RB|36": [1],
                  "BS|*": [4], "ES|*": [0, 2], "WP|*": [4, 8],
                }
            elif params.pool_preset == "Bonus Lite":
                params.item_pool = {
                  "TP|Grove": [1], "TP|Swamp": [1], "TP|Grotto": [1], "TP|Valley": [1], "TP|Sorrow": [1], "TP|Ginso": [1],
                  "TP|Horu": [1], "TP|Forlorn": [1], "TP|Blackroot": [1], "HC|1": [12], "EC|1": [15], "AC|1": [33], "RB|0": [3], "RB|1": [3],
                  "RB|6": [5], "RB|9": [1], "RB|10": [1], "RB|11": [1], "RB|12": [2], "RB|37": [2], "RB|13": [3], "RB|15": [3],
                  "RB|31": [1], "RB|32": [1], "RB|33": [2], "RG|RB/12/RB/33/RB/37": [3], "RB|36": [1], "WP|*": [4,8],
                }
            elif params.pool_preset == "Competitive":
                params.item_pool = {
                  "TP|Grove": [1], "TP|Swamp": [1], "TP|Grotto": [1], "TP|Valley": [1], "TP|Sorrow": [1], "TP|Forlorn": [1],
                  "HC|1": [12], "EC|1": [15], "AC|1": [33], "RB|0": [3], "RB|1": [3], "RB|6": [3],"RB|9": [1], "RB|10": [1],
                  "RB|11": [1], "RB|12": [1], "RB|13": [3], "RB|15": [3],
                }
            elif params.pool_preset == "Hard":
                params.item_pool = { "TP|Grove": [1],  "TP|Swamp": [1], "TP|Grotto": [1], "TP|Valley": [1], "TP|Sorrow": [1], "EC|1": [4]}
            else:
                params.pool_preset = "Standard"
                params.item_pool = { 
                  "TP|Grove": [1], "TP|Swamp": [1], "TP|Grotto": [1], "TP|Valley": [1], "TP|Sorrow": [1], "TP|Ginso": [1],
                  "TP|Horu": [1], "TP|Forlorn": [1], "HC|1": [12], "EC|1": [15], "AC|1": [33], "RB|0": [3], "RB|1": [3], "RB|6": [3], 
                  "RB|9": [1], "RB|10": [1], "RB|11": [1], "RB|12": [1], "RB|13": [3], "RB|15": [3],
                }
        raw_fass = qparams.get("fass")
        if raw_fass:
            params.placements = []
            params.preplaced_coords = []
            # the util.parse_fass shape: [world.]loc:item[@owner]; spawn items never cross worlds
            for fass in raw_fass.split("|"):
                rawloc, _, item = fass.partition(":")
                world, _, loc = rawloc.rpartition(".")
                item, owner = split_owner(item)
                stuff = [Stuff(code=item[:2], id=item[2:], player=world, owner=(owner if loc != "2" else "") or None)]
                params.placements.append(Placement(location=loc, zone="", stuff=stuff))
                if loc == "2":
                    if world in ("", "1"):
                        params.spawn_placement = Placement(location=loc, zone="", stuff=stuff)
                else:
                    params.preplaced_coords.append(int(loc))
        from archipelago.convert import normalize_categories
        params.ap_export = normalize_categories(qparams.getlist("ap_export"))
        params.ap_mode = bool(qparams.get("ap_mode")) or bool(params.ap_export)
        params.ap_death_link = params.ap_mode and bool(qparams.get("ap_death_link"))
        params.player_names = rolled_player_names(qparams.getlist("player_names"), params)
        if params.ap_mode:
            from archipelago.convert import EXPORTABLE_CATEGORIES
            bad = [c for c in params.ap_export if c not in EXPORTABLE_CATEGORIES]
            if bad:
                log.error("Unknown AP export categories %r! returning None", bad)
                return None
        return params.put()

    def to_json(self):
        out = {
            "players": self.players,
            "flagLine": self.flag_line(),
            "seed": self.seed,
            "variations": [v.value for v in self.variations],
            "fillAlg": "Balanced" if self.balanced else "Classic",
            "expPool": self.exp_pool,
            "keyMode": self.key_mode.value,
            "pathMode": get_preset_from_paths(presets, self.logic_paths),
            "pathDiff": self.path_diff.value,
            "cellFreq": self.cell_freq,
            "fragCount": self.frag_count,
            "fragReq": self.frag_req,
            "relicCount": self.relic_count,
            "tracking": self.tracking,
            "coopGameMode": JSON_GAME_MODE.get(self.sync.mode, "Co-op"),
            "coopGenMode": "Cloned Seeds" if (self.sync.cloned or self.sync.mode == MultiplayerGameType.MULTIWORLD) else "Seperate Seeds",
            "paths": [p.value for p in self.logic_paths],
            "shared": [JSON_SHARE(s) for s in self.sync.shared],
            "teamStr": self.sync.get_team_str(),
            "dedupShared": self.sync.dedup,
            "spoilers": len(self.spoilers[0]) > 100 or self.plando_spoiler_key is not None,
            "senseData": self.sense,
            "spawn": self.start,
            "spawnECs": self.starting_energy,
            "spawnHCs": self.starting_health,
            "spawnSKs": self.starting_skills,
            "isPlando": self.is_plando,
            "itemPool": self.item_pool,
            "selectedPool": self.pool_preset,
            "bingoLines": self.bingo_lines,
            "bingoDiff": self.bingo_diff,
            "bingoGoal": self.bingo_goal,
            "bingoSquares": self.bingo_squares,
            "bingoMeta": self.bingo_meta,
            "bingoDisc": self.bingo_disc,
            "spawnWeights": self.spawn_weights,
            "verboseSpoiler": self.verbose_spoiler,
            "playerNames": list(self.player_names),
            "antiBkBias": self.anti_bk_bias,
            "apMode": self.ap_mode,
            "apExport": list(self.ap_export),
            "apDeathLink": self.ap_death_link,
            "worldSettings": [dict(w) for w in self.world_settings],
            # stars i fucking hate this. anyways.
            # fass_json verbatim when present, else rebuilt from preplaced_coords + spawn_placement
            # (placements at loc 2 also hold what seedgen added)
            "fass": self.fass_json if self.fass_json else (
                    [{"loc": p.location, "item":  f"{p.stuff[0].code}|{p.stuff[0].id}"} for p in self.placements
                            if int(p.location) in self.preplaced_coords] + (
                        [{"loc": "2", "item": f"{self.spawn_placement.stuff[0].code}|{self.spawn_placement.stuff[0].id}"}] if (self.spawn_placement) else []))
        }
        # an unset list is left out: the page keeps its own, a null would replace it
        for k in ("itemPool", "spawnWeights", "playerNames", "variations", "paths"):
            if out.get(k) is None:
                out.pop(k, None)
        return out


    def generate(self, preplaced={}):
        if self.placements:
            preplaced = {}
            for placement in self.placements:
                s = placement.stuff[0]
                world = int(s.player) if s.player else 1
                value = s.code + s.id
                if s.owner and s.owner != s.player:
                    value = "%s|%s" % (value, s.owner)  # cross-world: owner rides the tag
                preplaced[(world, int(placement.location))] = value
            self.placements = []
        sg = SeedGenerator()
        raw = sg.setSeedAndPlaceItems(self, preplaced=preplaced)
        self._gen_warnings = [{"level": level, "text": text} for text, level in getattr(sg, "gen_warnings", {}).items()]
        placemap = OrderedDict()
        spoilers = []
        if not raw:
            return False
        if self.ap_mode:
            if self.sync.enabled and self.sync.mode != MultiplayerGameType.MULTIWORLD:
                log.error("AP mode requires Multiworld generation (got %s)", self.sync.mode)
                return False
            from archipelago.convert import ap_convert, ap_export_categories
            keep = set(k if isinstance(k, tuple) else (1, k) for k in preplaced)
            converted, _ = ap_convert([pr[0] for pr in raw],
                                      ap_export_categories(self),
                                      keep_locs=keep)
            raw = [(converted[i], raw[i][1]) for i in range(len(raw))]
        from util import is_mw_manifest_loc
        player = 0
        for player_raw in raw:
            player += 1
            seed, spoiler = tuple(player_raw)
            spoilers.append(spoiler)
            for line in seed.split("\n")[1:-1]:
                if line.startswith("//"):
                    continue  # seed metadata, not a placement
                loc, stuff_code, stuff_id, zone = tuple(line.split("|"))
                if stuff_code == "EN":
                    stuff_id = f"{stuff_id}|{zone}"
                    zone = None
                stuff = Stuff(code=stuff_code, id=stuff_id, player=str(player))
                # real locations share one Placement across players; manifest pseudo-locs are
                # different slots per player and must not merge
                key = (loc, player) if is_mw_manifest_loc(loc) else loc
                if key not in placemap:
                    placemap[key] = Placement(location=loc, zone=zone, stuff=[stuff])
                else:
                    placemap[key].stuff.append(stuff)
        if self.sync.mode in [MultiplayerGameType.SIMUSOLO, MultiplayerGameType.SPLITSHARDS]:
            if player != 1:
                log.error(f"seed count mismatch! Should only be 1 seed for this mode and instead found {player}")
                return False
        elif player != self.players and player != len(self.sync.teams):
            log.error(f"seed count mismatch!, {player} != {self.players} or {len(self.sync.teams)}")
            return False
        self.spoilers = spoilers
        self.placements = list(placemap.values())
        self.put()
        return True

    def teams_inv(self):  # generates {pid: tid}
        return {pid: tid for tid, pids in self.sync.teams.items() for pid in pids}

    def team_pid(self, pid):  # the pid's team (teams are cloned-only), else pid
        # multiworld ignores teams: some older params carry a bogus teams={1: everyone}
        if self.sync.mode == MultiplayerGameType.MULTIWORLD:
            return pid
        return int(self.teams_inv()[pid]) if (self.sync.teams and self.sync.cloned) else pid

    def get_seed(self, player=1, game_id=None, verbose_paths=False, include_sync = True):
        # several variations are client-only flags, so each world needs its own header
        flags = self.world_params(player).flag_line(verbose_paths)
        if self.players > 1 and self.sync.mode in [MultiplayerGameType.SHARED, MultiplayerGameType.MULTIWORLD]:
            flags += f"/{player}"
        if self.tracking and include_sync:
            if not game_id:
                log.warning(f"Trying to get a tracked seed with no gameId! paramId {self.key.id()}")
            else:
                flags = f"Sync{game_id}.{player},{flags}"
        outlines = [flags]
        # 4.2.15+ refuses an unreadable format; clients before 4.2.9 choke on metadata lines
        outlines.append("// SEED_FORMAT: %s" % SEED_FORMAT)
        # an owner above the player count marks a reserved AP line
        outlines.append("// PLAYERS: %s" % self.players)
        if self.ap_mode:
            from archipelago.convert import keytiers_meta
            meta = keytiers_meta(self, player)
            if meta:
                outlines.append(meta)
        seed_data = self.ap_named(self.get_seed_data(player), player, game_id)
        # an EN line's zone is None (it rides in field 3); other fields may be empty
        outlines += ["|".join(p for p in line if p is not None) for line in seed_data]
        # boxes are not locations: a world's lines ride at the end, as written
        box_world = 1 if self.sync.mode in [MultiplayerGameType.SIMUSOLO, MultiplayerGameType.SPLITSHARDS] else int(player)
        outlines += [b.line for b in self.boxes if int(b.player or 1) == box_world]
        return "\n".join(outlines) + "\n"

    def ap_rows(self, game_id):
        """{world: (scouted AP entries, room slot)}; empty until the room has been connected
        and scouted at least once."""
        if not self.ap_mode or not game_id:
            return {}
        try:
            from ap_models import APNames
            return {w: APNames.load(game_id, w) for w in range(1, int(self.players) + 1)}
        except Exception:
            log.exception("couldn't load AP names for game %s", game_id)
            return {}

    def ap_named(self, seed_data, player, game_id):
        """This world's AP lines annotated from the room's scouts (field 6 is the bridge's
        promise map, the rest display only); unscouted passes through."""
        rows = self.ap_rows(game_id)
        if not rows:
            return seed_data
        try:
            from ap_models import APNames
            from archipelago.annotate import annotate
            promises = APNames.load_promises(game_id, int(player))
            return annotate(seed_data, int(self.players), int(player), rows,
                            lambda v: self.get_seed_data(v), promises=promises)
        except Exception:
            log.exception("couldn't annotate AP seed for game %s world %s", game_id, player)
            return seed_data

    def get_seed_data(self, player=1):
        player = int(player)
        if self.sync.mode in [MultiplayerGameType.SIMUSOLO, MultiplayerGameType.SPLITSHARDS]:
            player = 1
        pid = self.team_pid(player)
        rows = []
        next_slot = {}

        def take_slot(owner):
            slot = next_slot.get(owner, 0)
            next_slot[owner] = slot + 1
            if slot >= SeedGenerator.MAX_SLOTS:
                raise MultiworldSlotOverflow("player %s owns more than %s cross-world items"
                                             % (owner, SeedGenerator.MAX_SLOTS))
            return slot

        for p in self.placements:
            for s in p.stuff:
                if s.code == "MU" and "@" in s.id:
                    # a plando piece "SK/0@2" belongs to world 2: it goes out as an MW child
                    mine, manifests = [], []
                    for code, value in decompose_multi_value(s.id):
                        value, owner = split_owner(value)
                        if not owner or owner == s.player:
                            mine.append((code, value))
                            continue
                        slot = take_slot(owner)
                        mine.append(("MW", "%s,%s,%s,%s" % (owner, slot, code, value)))
                        manifests.append((slot, owner, code, value))
                    if int(s.player) == pid:
                        rows.append((str(p.location), "MU", compose_multi_value(mine), p.zone))
                    for slot, owner, code, value in manifests:
                        if int(owner) == pid:
                            rows.append((str(-(slot + 2)), "MW",
                                         "%s,,%s,%s" % (s.player, code, value), p.zone))
                    continue
                if not (s.owner and s.owner != s.player):
                    if int(s.player) == pid:
                        rows.append((str(p.location), s.code, s.id, p.zone))
                    continue
                # slots are numbered over ALL placements in order, so every player's call agrees
                slot = take_slot(s.owner)
                if int(s.player) == pid:
                    rows.append((str(p.location), "MW", "%s,%s,%s,%s" % (s.owner, slot, s.code, s.id), p.zone))
                if int(s.owner) == pid:
                    rows.append((str(-(slot + 2)), "MW", "%s,,%s,%s" % (s.player, s.code, s.id), p.zone))
        return rows

    def get_spoiler(self, player=1, game_id=None):
        if self.sync.mode in [MultiplayerGameType.SIMUSOLO, MultiplayerGameType.SPLITSHARDS]:
            player = 1
        if getattr(self, "ap_mode", False):
            ap = self.ap_spoiler(player, game_id)
            if ap is not None:
                return ap
        if self.is_plando:
            if self.plando_spoiler_key:
                plando = self.plando_spoiler_key.get()
                if plando and plando.spoiler:
                    return plando.spoiler
            return self.spoilers[0]
        spoiler = self.spoilers[self.team_pid(player) - 1]
        if getattr(self, "ap_mode", False):
            # captured before the AP conversion; the room re-places everything exported
            spoiler =("!! Archipelago: exported items were re-placed by the AP room.\n"
                       "!! This file shows the roll before export. Once the room is\n"
                       "!! connected and scouted, this page shows real placements instead.\n\n"
                       + spoiler)
        return spoiler

    def ap_spoiler(self, player, game_id):
        """What each location holds after the AP fill, plus this world's incoming manifest,
        from the room's scouts. None until some world has scouted."""
        if not game_id:
            return None
        rows = self.ap_rows(game_id)
        if not any(entries for entries, _ in rows.values()):
            return None
        try:
            from archipelago.annotate import annotate, _holder_hits
            from archipelago.convert import match_key
            from models import Pickup
            from util import is_mw_manifest_loc
            lines = annotate(self.get_seed_data(player), int(self.players), int(player),
                             rows, lambda v: self.get_seed_data(v))
            hits = _holder_hits(int(self.players), int(player), rows,
                                lambda v: self.get_seed_data(v))
        except Exception:
            log.exception("couldn't build AP spoiler for game %s world %s", game_id, player)
            return None
        shadow = str(int(self.players) + int(player))
        zones, incoming, unscouted = OrderedDict(), [], 0
        exported, native = OrderedDict(), OrderedDict()

        def pickup_name(code, id):
            pickup = Pickup.n(code, id)
            return pickup.name if pickup else "%s|%s" % (code, id)

        for line in lines:
            loc, code, id, zone = line[0], line[1], line[2], line[3]
            if code == "EN" or code + str(id) == "RB81":
                continue
            if is_mw_manifest_loc(int(loc)):
                finder, _holder, icode, iid = id.split(",", 3)
                if finder == shadow:
                    # aggregate: per-copy attribution of duplicated items is
                    # ambiguous, but the scouted multiset is exact
                    row = exported.setdefault(match_key(icode, iid),
                                              [pickup_name(icode, iid), 0])
                    row[1] += 1
                else:
                    row = native.setdefault((pickup_name(icode, iid), finder), [0])
                    row[0] += 1
                continue
            pick = PBC.get(int(loc))
            locname = "%s %s (%s %s)" % (pick.area, pick.name, pick.x, pick.y) if pick else str(loc)
            zname = zone or (pick.zone if pick else "Unknown")
            parts = id.split(",", 5) if code == "MW" else None
            if parts and len(parts) == 6 and parts[0] == shadow:
                # a reserved line names its item in the last two fields; AP
                # means the room's own, whose id is already its name
                content = parts[5] if parts[4] == "AP" else pickup_name(parts[4], parts[5])
                if parts[5].startswith("AP Item #"):
                    unscouted += 1
            else:
                content = pickup_name(code, id)
            zones.setdefault(zname, []).append((locname, content))

        for key, (name, copies) in exported.items():
            placed = hits.get(key, [])[:copies]
            if copies == 1:
                wheres = ["in %s's world%s" % (h, ", %s" % z if z else "") for h, z in placed]
            else:
                wheres = [("%s %s" % (h, z)).strip() for h, z in placed]
            missing = copies - len(placed)
            if missing:
                wheres.append("somewhere in the Archipelago" if not wheres and missing == 1
                              else "%s in the Archipelago" % missing)
            label = name if copies == 1 else "%s x%s" % (name, copies)
            incoming.append((label, "; ".join(wheres)))
        for (name, finder), (copies,) in native.items():
            label = name if copies == 1 else "%s x%s" % (name, copies)
            incoming.append((label, "found by P%s" % finder))

        out = ["Archipelago placement spoiler for Player %s, scouted from the room." % int(player),
               "Lists what each location holds after the Archipelago fill; fill order",
               "and logic spheres live in the room's own spoiler log.", ""]
        if unscouted:
            out += ["(%s locations not scouted yet, shown as AP Item #n)" % unscouted, ""]
        out.append("This world:")
        for zname in sorted(zones):
            out.append("  %s:" % zname)
            width = max(len(n) for n, _ in zones[zname])
            for locname, content in sorted(zones[zname]):
                out.append("    %s  %s" % (locname.ljust(width), content))
        if incoming:
            out += ["", "Incoming (this world's slot manifest):"]
            width = max(len(n) for n, _ in incoming)
            for name, source in sorted(incoming):
                out.append("    %s  %s" % (name.ljust(width), source))
        return "\n".join(out) + "\n"

    def get_aux_spoiler(self, exclude_types, by_zone, player=1, game_id=None):
        """Item list. Multiworld covers every world in one document, the way
        the spoiler does; player picks the world only for a solo seed."""
        if self.players > 1:
            return "\n\n".join(
                "=== Player %s ===\n%s" % (w, self.aux_spoiler_world(exclude_types, by_zone, w, game_id))
                for w in range(1, self.players + 1))
        return self.aux_spoiler_world(exclude_types, by_zone, player, game_id)

    def aux_spoiler_world(self, exclude_types, by_zone, player=1, game_id=None):
        from models import Pickup
        from util import is_mw_manifest_loc
        outlines = []
        seed_data = OrderedDict()
        # game_id is optional and AP-only: with it the reserved AP lines list
        # their real items instead of "AP Item #n", exactly like the seed
        for line in self.ap_named(self.get_seed_data(player), player, game_id):
            coords, pcode, pid = line[0], line[1], line[2]   # annotated AP lines carry a 5th field
            if pcode == "EN" or pcode in exclude_types or pcode + pid == "RB81":
                continue
            if is_mw_manifest_loc(coords):
                continue  # slot manifests aren't map locations
            loc = PBC[int(coords)]
            pickup = Pickup.n(pcode, pid, self.players)
            if pickup:
                name = pickup.name.replace("Repeatable: ", "").replace("Message: Press AltR to ", "").replace(", Warp to", "")
                sect = loc.zone if by_zone else type(pickup).__name__
            else:
                log.warn("couldn't make a pickup out of %s|%s", pcode, pid)
                name = "%s|%s" %(pcode, pid)
                sect = loc.zone if by_zone else "Unknown"

            if sect not in seed_data:
                seed_data[sect] = []
            seed_data[sect].append((loc, name, pcode + pid))
        for section, group in seed_data.items():
            outlines += ["", "%s:" % section]
            outlines += ["\t%-35s %s" % (l.area, n) for (l, n, _) in sorted(group, key=lambda grpline: grpline[2])]
        return "\n".join(outlines[1:])

    def to_ap_yaml(self, world=1):
        """Paired AP yaml for one world, from the stored (converted) placements; None
        unless ap_mode."""
        if not self.ap_mode:
            return None
        from archipelago.convert import (build_ap_config, ap_variations,
                                         keystone_tier_list)
        from archipelago.yaml_emit import emit_yaml
        from ap_models import ap_slot_names
        config = build_ap_config(
            self.get_seed_data(world), players=self.players, world=int(world),
            logic_paths=[lp.value for lp in self.logic_paths],
            key_mode=self.key_mode.value,
            spawn_zone=self.spawn or self.start or "Glades",
            variations=ap_variations(self.variations),
            params_id=self.key.id() if self.key else 0,
            death_link=self.ap_death_link,
            key_tiers=keystone_tier_list(self, int(world)))
        return emit_yaml(config, ap_slot_names(self.players, self.player_names)[int(world) - 1])

    def flag_line(self, verbose_paths=False):
        flags = []
        if self.is_plando:
            flags = self.plando_flags
        else:
            if verbose_paths:
                flags.append("lps=%s" % "+".join([lp.capitalize() for lp in self.logic_paths]))
            else:
                flags.append(get_preset_from_paths(presets, self.logic_paths))
            flags.append(self.key_mode)
            if Variation.WARMTH_FRAGMENTS in self.variations:
                flags.append("Frags/%s/%s" % (self.frag_req, self.frag_count))
            if Variation.WORLD_TOUR in self.variations:
                flags.append("WorldTour=%s" % self.relic_count)
            flags += [v.value for v in self.variations if v not in FLAGLESS_VARS]
            if self.path_diff != PathDifficulty.NORMAL:
                flags.append("prefer_path_difficulty=%s" % self.path_diff.value)
            if self.sync.enabled and self.sync.mode is not MultiplayerGameType.SIMUSOLO:
                if self.sync.shared:
                    flags.append("share=%s" % "+".join(self.sync.shared))
                # the client reads its SyncMode from mode=; multiworld must
                # always carry it, shared categories or not
                if not self.sync.shared or self.sync.mode == MultiplayerGameType.MULTIWORLD:
                    flags.append("mode=%s" % self.sync.mode.value)
            # the client only sends its death counter when the seed says so,
            # so every other seed's tick body stays byte-identical
            if self.ap_mode and self.ap_death_link:
                flags.append("DeathLink")
            if self.balanced:
                flags.append("balanced")
            if self.anti_bk_bias:
                flags.append("anti_bk_bias=%g" % self.anti_bk_bias)
            if self.pool_preset != "Standard":
                flags.append("pool=%s" % self.pool_preset)
            if self.sense:
                flags.append("sense=%s" % self.sense.replace(" ", "+"))
        return "%s|%s" % (",".join(flags), self.seed)

    @staticmethod
    def with_id(id):
        return SeedGenParams.cached_by_id(id)

    @staticmethod
    def cached_by_id(id):
        """The inflated entity via _PARAMS_CACHE (shared: read-only)."""
        pid = int(id)
        with _PARAMS_LOCK:
            hit = _PARAMS_CACHE.get(pid)
        if hit is not None:
            return hit
        params = SeedGenParams.get_by_id(pid)
        if params is not None:
            with _PARAMS_LOCK:
                _PARAMS_CACHE[pid] = params
        return params

    @staticmethod
    def cached_by_key(key):
        return SeedGenParams.cached_by_id(key.id()) if key else None

    @staticmethod
    def _bust_game_flags(params_id):
        # best effort: these hooks run after the datastore write has already
        # committed, and memcache's delete is not exception-guarded
        from cache import Cache   # lazy: cache.py pulls in util, which pulls in seedbuilder
        try:
            Cache.clear_game_flags(params_id)
        except Exception:
            log.exception("could not bust game flags for params %s", params_id)

    def _post_put_hook(self, future):
        # any put invalidates: generation, and the bingo variation append
        with _PARAMS_LOCK:
            _PARAMS_CACHE.pop(self.key.id(), None)
        SeedGenParams._bust_game_flags(self.key.id())

    @classmethod
    def _post_delete_hook(cls, key, future):
        with _PARAMS_LOCK:
            _PARAMS_CACHE.pop(key.id(), None)
        # a game whose seed was deleted (clean_up shares params across games)
        # must go back to rendering "(Seed not found)", not a dead Seed link
        SeedGenParams._bust_game_flags(key.id())
