from google.cloud import ndb

import logging as log
import random

from util import enums_from_strlist, picks_by_coord, get_preset_from_paths, SEED_FORMAT
from enums import (MultiplayerGameType, ShareType, Variation, LogicPath, KeyMode, PathDifficulty, presets)
from collections import OrderedDict
from threading import Lock
from cachetools import TTLCache
from seedbuilder.generator import SeedGenerator

# Inflating a big multiworld params entity is ~3000 protobuf decodes, about
# half a second per request. Request paths share one process-local inflated
# copy instead. CORRECT ONLY SINGLE-INSTANCE (like models.bingo_lock, which
# already pins the deploy to max-instances=1); the TTL covers deploy-overlap
# windows where another instance's put cannot bust ours. Entries are SHARED
# and READ-ONLY: a path that mutates-and-puts must fetch raw via key.get()
# (the bingo variation append in BingoGameData.get_seed is the one such
# site), and every put busts via the hooks on the model.
_PARAMS_CACHE = TTLCache(maxsize=8, ttl=120)
_PARAMS_LOCK = Lock()

JSON_SHARE = lambda x: x.value if x != ShareType.EVENT else "World Events"

def seed_mode_problem(params, mw_override=False, ap_override=False):
    """User-facing reason a seed request's multiplayer mode can't be built,
    or None. mw_override (mw=1) and ap_override (ap_test=1) are soft gates
    against stumbling in, not security boundaries. Both gate CREATION only:
    existing games keep their routes, since the people playing a tester's
    seed never carry the opt-in."""
    from util import MULTIWORLD, ARCHIPELAGO
    ap_mode = getattr(params, "ap_mode", False)
    if ap_mode:
        # ahead of the singleplayer early return: K=1 AP is still an AP seed
        if not ARCHIPELAGO:
            return "Archipelago seeds aren't available yet."
        if not ap_override:
            return "Archipelago seeds are in closed testing."
        # without netcode the bridge has no way in: the client would find AP
        # slots and silently drop them
        if not (params.sync.enabled and params.tracking):
            return "Archipelago seeds need tracking (the room talks to the game over netcode)."
    if not params.sync.enabled:
        return None
    if params.sync.mode == MultiplayerGameType.MULTIWORLD:
        if not (MULTIWORLD or mw_override):
            return "Multiworld seeds aren't available yet."
        if not params.tracking:
            return "Multiworld requires tracking (it's netcode all the way down)."
        # preplacement is supported; just sanity-check the player references
        # (getattr: CLI params objects don't carry placement fields)
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
    if params.sync.mode == MultiplayerGameType.SPLITSHARDS:
        return "SplitShards was removed (2026-07). Consider Multiworld with Shards keymode."
    if params.sync.mode == MultiplayerGameType.SHARED and not params.sync.cloned:
        return "Seperate Seeds generation was removed (2026-07). Use Cloned Seeds or Multiworld."
    return None
def rolled_player_names(names, params):
    """Sanitize the UI's per-world names. Bingo hands names out by lobby and
    stores none, unless it's an AP board (pid is the world there); trailing
    blanks are dropped."""
    if (Variation.BINGO in (getattr(params, "variations", None) or [])
            and not getattr(params, "ap_mode", False)):
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
    # multiworld preplacement: whose item this is, when it isn't the world
    # it's placed in (player = the world holding the location)
    owner = ndb.StringProperty()

class Placement(ndb.Model):
    location = ndb.StringProperty()
    zone = ndb.StringProperty()
    stuff = ndb.LocalStructuredProperty(Stuff, repeated=True)

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
        # a lone Ori world in someone else's AP room still needs the netcode:
        # the bridge delivers through it
        ap_mode = bool(json.get("apMode", False))
        opts.enabled = json.get("players", 1) > 1 or ap_mode
        opts.teams = json.get("teams", {})
        if opts.enabled:
            jsonMode = json.get("coopGameMode", "None")
            opts.mode = JSON_MODE_GAME[jsonMode] if jsonMode in JSON_MODE_GAME else MultiplayerGameType(jsonMode)
            if ap_mode:
                opts.mode = MultiplayerGameType.MULTIWORLD  # SyncMode 5: the client only reads slot bitfields there
            # cloned/teams are SHARED-mode concepts; multiworld players each
            # have their own world (a stray teams={1: everyone} here made
            # every player download player 1's seed -- game 133746)
            opts.cloned = json.get("coopGenMode") != "disjoint" and opts.mode != MultiplayerGameType.MULTIWORLD
            if opts.cloned:
                opts.teams = {1: list(range(1, json.get("players", 1) + 1))}
                opts.dedup = bool(json.get("dedupShared", False))
            opts.shared = enums_from_strlist( ShareType, [a.replace(" ", "") for a in json.get("syncShared", json.get("shared", []))]) #shit fuck ass jank shit
        return opts

    def get_team_str(self):
        if self.teams:
            return "|".join([",".join(team) for team in self.teams])
        return ""

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
    # the fass list as the UI sent it, kept verbatim for rerolls (the legacy
    # reconstruction from placements can't carry world/owner)
    fass_json = ndb.JsonProperty()
    placements = ndb.LocalStructuredProperty(Placement, repeated=True, compressed=True)
    spawn_placement = ndb.LocalStructuredProperty(Placement)
    preplaced_coords = ndb.IntegerProperty(repeated=True)
    spoilers = ndb.TextProperty(repeated=True, compressed=True)
    sense = ndb.StringProperty()
    is_plando = ndb.BooleanProperty(default=False)
    # set only when that plando has a spoiler, so it doubles as the "show the
    # button" bit; the text stays on the Seed instead of being copied per roll
    plando_spoiler_key = ndb.KeyProperty(kind="Seed")
    plando_flags = ndb.StringProperty(repeated=True)
    # {world: [[home, target], ...]} -- the placement walk's keystone door
    # order, set by the generator when generic keystones export
    ks_door_order = ndb.JsonProperty()
    item_pool = ndb.JsonProperty()
    pool_preset = ndb.StringProperty()
    bingo_lines = ndb.IntegerProperty(default=3)
    start = ndb.StringProperty(default="Glades")
    spawn = ndb.StringProperty(default="Glades")
    starting_health = ndb.IntegerProperty(default=3)
    starting_energy = ndb.IntegerProperty(default=1)
    starting_skills = ndb.IntegerProperty(default=0)
    spawn_weights = ndb.FloatProperty(repeated=True)
    verbose_spoiler = ndb.BooleanProperty(default=False)
    # Archipelago mode: multiworld generation + the AP conversion pass
    # (archipelago/convert.py). ap_export = category names handed to the AP
    # pool; empty means the default set.
    ap_mode = ndb.BooleanProperty(default=False)
    ap_export = ndb.StringProperty(repeated=True)
    # per-world names chosen at roll time, index 0 = player 1. Blank entries
    # (and bingo games, which have their own lobby names) fall back to
    # "Player N" / "OriN".
    player_names = ndb.StringProperty(repeated=True)
    # DeathLink: the room's deaths kill this world's Ori, and its deaths kill
    # the room's. A property of the seed, so a game either has it or doesn't.
    ap_death_link = ndb.BooleanProperty(default=False)
    do_loc_analysis = False
    areas_ori_path = ""

    @staticmethod
    def from_plando(plando, tracking=True):
        params = SeedGenParams(
            seed = plando.name,
            players = plando.players,
            tracking = tracking,
            is_plando=True, 
            plando_flags = plando.flags,
            placements = plando.placements,
            spoilers = [plando.description],
            plando_spoiler_key = plando.key if plando.spoiler else None,
            )
        params.sync = MultiplayerOptions()
        params.sync.enabled = plando.players > 1
        mode = plando.mode()
        if mode is None and plando.players > 1:
            # Plandos saved by older builder versions never persisted their mode= flag.
            # Without this fallback, sync.mode defaults to SIMUSOLO and get_seed_data()
            # coerces every player to 1, serving player 1's seed to the whole lobby.
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
        params.seed = str(json.get("seed"))
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
        params.item_pool = json.get("itemPool", {})
        params.bingo_lines = json.get("bingoLines", 3)
        params.pool_preset = json.get("selectedPool", "Standard")
        params.placements = []
        params.preplaced_coords = []
        params.fass_json = json.get("fass", []) or None
        for fass in json.get("fass", []):
            if "item" in fass: # this is stupid af but it's a faster way to handle the json mismatch than the other fixes available
                pcode, _, pid = fass["item"].partition("|")
            else:
                pcode, pid  = fass["code"], fass["id"]
            world = str(fass.get("world", 1) or 1)
            # spawn items are granted at that world's start, never cross-world
            owner = world if fass["loc"] == "2" else str(fass.get("owner", world) or world)
            params.placements.append(Placement(location=fass["loc"], zone="", stuff=[Stuff(code=pcode, id=pid, player=world, owner=owner)]))
            if fass["loc"] == "2" and world == "1": # this has to be special-cased because some seedgen options will put extra bullshit here and that breaks rerolls!
                params.spawn_placement = Placement(location=fass["loc"], zone="", stuff=[Stuff(code=pcode, id=pid, player=world)])
            elif fass["loc"] != "2":
                params.preplaced_coords.append(int(fass["loc"]))
        params.starting_energy = json.get("spawnECs", 1)
        params.starting_health = json.get("spawnHCs", 3)
        params.starting_skills = json.get("spawnSKs", 0)
        params.start = json.get("spawn", "Glades")
        params.spawn_weights = json.get("spawnWeights", [])
        params.verbose_spoiler = json.get("verboseSpoiler", False)
        from archipelago.convert import normalize_categories
        params.ap_export = normalize_categories(str(c) for c in json.get("apExport", []))
        params.ap_mode = bool(json.get("apMode")) or bool(params.ap_export)
        params.ap_death_link = params.ap_mode and bool(json.get("apDeathLink"))
        params.player_names = rolled_player_names(json.get("playerNames", []), params)
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
        params.seed = qparams.get("seed")
        if not params.seed:
            log.error("No seed in %r! returning None" % qparams)
            return None
        params.variations = enums_from_strlist(Variation, qparams.getlist("var"))
        params.logic_paths = enums_from_strlist(LogicPath, qparams.getlist("path"))
        if not params.logic_paths:
            log.error("No logic paths in %r! returning None" % qparams)
            return None
        params.key_mode = KeyMode(qparams.get("key_mode", "Clues"))
        params.path_diff = PathDifficulty(qparams.get("path_diff", "Normal"))
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
            for itemcnt in raw_pool.split("|"):
                item, _, count = itemcnt.partition(":")
                params.item_pool[item] = int(count)
        else:
            if Variation.EXTRA_BONUS_PICKUPS in params.variations or params.pool_preset == "Extra Bonus":
                params.pool_preset = "Extra Bonus"
                params.item_pool = { 
                  "TP|Grove": [1], "TP|Swamp": [1], "TP|Grotto": [1], "TP|Valley": [1], "TP|Sorrow": [1], "TP|Ginso": [1],
                  "TP|Horu": [1], "TP|Forlorn": [1], "TP|Blackroot": [1], "HC|1": [12], "EC|1": [15], "AC|1": [33], "RP|RB/0": [3], "RP|RB/1": [3], 
                  "RB|6": [5], "RB|9": [1], "RB|10": [1], "RB|11": [1], "RB|12": [3], "RB|37": [3], "RB|13": [3], "RB|15": [3],
                  "RB|31": [1], "RB|32": [1], "RB|33": [3], "BS|*": [4], "WP|*": [4, 8],
                }
            elif params.pool_preset == "Bonus Lite":
                params.item_pool = {
                  "TP|Grove": [1], "TP|Swamp": [1], "TP|Grotto": [1], "TP|Valley": [1], "TP|Sorrow": [1], "TP|Ginso": [1],
                  "TP|Horu": [1], "TP|Forlorn": [1], "TP|Blackroot": [1], "HC|1": [12], "EC|1": [15], "AC|1": [33], "RB|0": [3], "RB|1": [3],
                  "RB|6": [5], "RB|9": [1], "RB|10": [1], "RB|11": [1], "RB|12": [3], "RB|37": [3], "RB|13": [3], "RB|15": [3],
                   "RB|31": [1], "RB|32": [1], "RB|33": [3], "RB|36": [1], "WP|*": [4,8],                }
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
            for fass in raw_fass.split("|"):
                loc, _, item = fass.partition(":")
                stuff = [Stuff(code=item[:2], id=item[2:], player="")]
                params.placements.append(Placement(location=loc, zone="", stuff=stuff))
                if loc == "2":
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
        return {
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
            "spawnWeights": self.spawn_weights,
            "verboseSpoiler": self.verbose_spoiler,
            "playerNames": list(self.player_names),
            "antiBkBias": self.anti_bk_bias,
            "apMode": self.ap_mode,
            "apExport": list(self.ap_export),
            "apDeathLink": self.ap_death_link,
            # stars i fucking hate this. anyways. forced assignments are: the
            # verbatim fass_json when we have it (world/owner survive), else
            # the legacy reconstruction:
            "fass": self.fass_json if self.fass_json else (
                    [{"loc": p.location, "item":  f"{p.stuff[0].code}|{p.stuff[0].id}"} for p in self.placements # placements on preplaced_coords
                            if int(p.location) in self.preplaced_coords] + (
                        [{"loc": "2", "item": f"{self.spawn_placement.stuff[0].code}|{self.spawn_placement.stuff[0].id}"}] if (self.spawn_placement) else []))
                        # and then specifically also the spawn_placement at 2, because we can't rely on self.placements[2] because NEW THINGS GET ADDED by seedgen (sometimes)
        }


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
                # real locations share one Placement across players (same spot,
                # same zone in every world), but multiworld manifest pseudo-locs
                # describe *different slots per player* -- merging them stored
                # player 1's zone for everyone (the game-133746 wrong-zone bug)
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

    def team_pid(self, pid):  # given pid, get team or return pid if no teams exist (REMINDER: TEAMS ARE CLONED ONLY)
        # multiworld guard: params created via the web before the from_json
        # fix carry a bogus teams={1: everyone}; every player must keep their
        # own pid or they all get player 1's seed
        if self.sync.mode == MultiplayerGameType.MULTIWORLD:
            return pid
        return int(self.teams_inv()[pid]) if (self.sync.teams and self.sync.cloned) else pid

    def get_seed(self, player=1, game_id=None, verbose_paths=False, include_sync = True):
        flags = self.flag_line(verbose_paths)
        if self.players > 1 and self.sync.mode in [MultiplayerGameType.SHARED, MultiplayerGameType.MULTIWORLD]:
            flags += f"/{player}"
        if self.tracking and include_sync:
            if not game_id:
                log.warning(f"Trying to get a tracked seed with no gameId! paramId {self.key.id()}")
            else:
                flags = f"Sync{game_id}.{player},{flags}"
        outlines = [flags]
        # 4.2.15+ checks this and refuses a format it cannot read; 4.2.9 to
        # 4.2.14 skip metadata lines, and pre-4.2.9 ones choke on them
        outlines.append("// SEED_FORMAT: %s" % SEED_FORMAT)
        if self.ap_mode:
            from archipelago.convert import keytiers_meta
            meta = keytiers_meta(self, player)
            if meta:
                outlines.append(meta)
        seed_data = self.ap_named(self.get_seed_data(player, no_door_zone = True), player, game_id)
        # AP-annotated lines join positionally: the zone of an item nobody
        # can locate is empty, and dropping it would promote field 5 into it
        outlines += ["|".join(line) if len(line) > 4 else "|".join(p for p in line if p)
                     for line in seed_data]
        return "\n".join(outlines) + "\n"

    def ap_rows(self, game_id):
        """Every world's scouted Archipelago placements, {world: (entries,
        room slot)}. Empty until the game's room has been connected at least
        once (the bridge learns them from LocationScouts), so a seed
        downloaded before then keeps its "AP Item #n" placeholders and its
        rolled zones until it is downloaded again."""
        if not self.ap_mode or not game_id:
            return {}
        try:
            from ap_models import APNames
            return {w: APNames.load(game_id, w) for w in range(1, int(self.players) + 1)}
        except Exception:
            log.exception("couldn't load AP names for game %s", game_id)
            return {}

    def ap_named(self, seed_data, player, game_id):
        """Annotate this world's AP lines with what the room actually did
        with them. Display only except field 6, which is the bridge's own
        persisted promise map; an unscouted world passes straight through."""
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

    def get_seed_data(self, player=1, no_door_zone = True):
        player = int(player)
        if self.sync.mode in [MultiplayerGameType.SIMUSOLO, MultiplayerGameType.SPLITSHARDS]:
            player = 1
        return [(str(p.location), s.code, s.id, p.zone) for p in self.placements for s in p.stuff if int(s.player) == self.team_pid(player)]

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
            # the spoiler is captured before the AP conversion, and the room's
            # own fill re-places everything exported after that
            spoiler = ("!! Archipelago: exported items were re-placed by the AP room.\n"
                       "!! This file shows the roll before export. Once the room is\n"
                       "!! connected and scouted, this page shows real placements instead.\n\n"
                       + spoiler)
        return spoiler

    def ap_spoiler(self, player, game_id):
        """Placement spoiler for an AP world, built from the room's scout
        rows: what each location HOLDS after the Archipelago fill, plus this
        world's incoming slot manifest. None until some world has scouted --
        before that the only truthful text is the pre-export roll. The fill
        ORDER is never ours to tell (it lives in the room's own spoiler log),
        and the generation-time walkthrough this replaces is false for every
        exported line once the room refills."""
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
                finder, icode, iid = id.split(",", 2)
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
            parts = id.split(",", 2) if code == "MW" else None
            if parts and len(parts) == 3 and parts[0] == shadow:
                content = parts[2]  # the scout's label, or the placeholder
                if content.startswith("AP Item #"):
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
            pickup = Pickup.n(pcode, pid)
            if pickup:
                name = pickup.name.replace("Repeatable: ", "").replace("Message: Press AltR to ", "").replace(", Warp to", "")
                sect = loc.zone if by_zone else type(Pickup.n(pcode, pid)).__name__
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
        """Paired Archipelago yaml for one world of an AP-mode seed, derived
        from the stored (already-converted) placements. None if this isn't
        an AP params."""
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
        """The inflated entity via the process cache (see the cache's comment
        for the sharing rules)."""
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
