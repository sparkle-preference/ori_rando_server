from google.cloud import ndb

import logging as log
import random

from util import enums_from_strlist, picks_by_coord, get_preset_from_paths
from enums import (MultiplayerGameType, ShareType, Variation, LogicPath, KeyMode, PathDifficulty, presets)
from collections import OrderedDict
from seedbuilder.generator import SeedGenerator

JSON_SHARE = lambda x: x.value if x != ShareType.EVENT else "World Events"
FLAGLESS_VARS = [Variation.WARMTH_FRAGMENTS, Variation.WORLD_TOUR]
JSON_GAME_MODE = {MultiplayerGameType.SHARED: "Co-op", MultiplayerGameType.SIMUSOLO: "Race", MultiplayerGameType.SPLITSHARDS: "SplitShards"}
JSON_MODE_GAME = {v:k for k,v in JSON_GAME_MODE.items()}
PBC = picks_by_coord(extras=True)

class Stuff(ndb.Model):
    code = ndb.StringProperty()
    id = ndb.StringProperty()
    player = ndb.StringProperty()

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
        opts.enabled = json.get("players", 1) > 1
        opts.teams = json.get("teams", {})
        if opts.enabled:
            jsonMode = json.get("coopGameMode", "None")
            opts.mode = JSON_MODE_GAME[jsonMode] if jsonMode in JSON_MODE_GAME else MultiplayerGameType(jsonMode)
            opts.cloned = json.get("coopGenMode") != "disjoint"
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
    placements = ndb.LocalStructuredProperty(Placement, repeated=True, compressed=True)
    spawn_placement = ndb.LocalStructuredProperty(Placement)
    preplaced_coords = ndb.IntegerProperty(repeated=True)
    spoilers = ndb.TextProperty(repeated=True, compressed=True)
    sense = ndb.StringProperty()
    is_plando = ndb.BooleanProperty(default=False)
    plando_flags = ndb.StringProperty(repeated=True)
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
            spoilers = [plando.description]
            )
        params.sync = MultiplayerOptions()
        if plando.mode():
            params.sync.mode = plando.mode()
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
        params.tracking = json.get("tracking")
        params.frag_count = json.get("fragCount", 30)
        params.frag_req = json.get("fragReq", 20)
        params.relic_count = json.get("relicCount", 8)
        params.cell_freq = json.get("cellFreq", 256)
        params.sync = MultiplayerOptions.from_json(json)
        params.sense = json.get("senseData")
        params.item_pool = json.get("itemPool", {})
        params.bingo_lines = json.get("bingoLines", 3)
        params.pool_preset = json.get("selectedPool", "Standard")
        params.placements = []
        params.preplaced_coords = []
        for fass in json.get("fass", []):
            if "item" in fass: # this is stupid af but it's a faster way to handle the json mismatch than the other fixes available
                pcode, _, pid = fass["item"].partition("|")
            else:
                pcode, pid  = fass["code"], fass["id"]
            params.placements.append(Placement(location=fass["loc"], zone="", stuff=[Stuff(code=pcode, id=pid, player="")]))
            if fass["loc"] == "2": # this has to be special-cased because some seedgen options will put extra bullshit here and that breaks rerolls!
                params.spawn_placement = Placement(location=fass["loc"], zone="", stuff=[Stuff(code=pcode, id=pid, player="")])
            else:
                params.preplaced_coords.append(int(fass["loc"]))
        params.starting_energy = json.get("spawnECs", 1)
        params.starting_health = json.get("spawnHCs", 3)
        params.starting_skills = json.get("spawnSKs", 0)
        params.start = json.get("spawn", "Glades")
        params.spawn_weights = json.get("spawnWeights", [])
        params.verbose_spoiler = json.get("verboseSpoiler", False)
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
            "coopGenMode": "Cloned Seeds" if self.sync.cloned else "Seperate Seeds",
            "paths": [p.value for p in self.logic_paths],
            "shared": [JSON_SHARE(s) for s in self.sync.shared],
            "teamStr": self.sync.get_team_str(),
            "dedupShared": self.sync.dedup,
            "spoilers": len(self.spoilers[0]) > 100,
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
            # stars i fucking hate this. anyways. forced assignments are:
            "fass": [{"loc": p.location, "item":  f"{p.stuff[0].code}|{p.stuff[0].id}"} for p in self.placements # placements on preplaced_coords
                            if int(p.location) in self.preplaced_coords] + (
                        [{"loc": "2", "item": f"{self.spawn_placement.stuff[0].code}|{self.spawn_placement.stuff[0].id}"}] if (self.spawn_placement) else [])
                        # and then specifically also the spawn_placement at 2, because we can't rely on self.placements[2] because NEW THINGS GET ADDED by seedgen (sometimes)
        }


    def generate(self, preplaced={}):
        if self.placements:
            preplaced = {}
            for placement in self.placements:
                s = placement.stuff[0]
                preplaced[int(placement.location)] = s.code + s.id
            self.placements = []
        sg = SeedGenerator()
        raw = sg.setSeedAndPlaceItems(self, preplaced=preplaced)
        placemap = OrderedDict()
        spoilers = []
        if not raw:
            return False
        player = 0
        for player_raw in raw:
            player += 1
            seed, spoiler = tuple(player_raw)
            spoilers.append(spoiler)
            for line in seed.split("\n")[1:-1]:
                loc, stuff_code, stuff_id, zone = tuple(line.split("|"))
                if stuff_code == "EN":
                    stuff_id = f"{stuff_id}|{zone}"
                    zone = None
                stuff = Stuff(code=stuff_code, id=stuff_id, player=str(player))
                if loc not in placemap:
                    placemap[loc] = Placement(location=loc, zone=zone, stuff=[stuff])
                else:
                    placemap[loc].stuff.append(stuff)
        if self.sync.mode in [MultiplayerGameType.SIMUSOLO, MultiplayerGameType.SPLITSHARDS]:
            if player != 1:
                log.error(f"seed count mismatch! Should only be 1 seed for this mode and instead found {player}")
                return False
        elif player != self.players and player != len(self.sync.teams):
            log.error(f"seed count mismatch!, {players} != {self.players} or {len(self.sync.teams)}")
            return False
        self.spoilers = spoilers
        self.placements = list(placemap.values())
        self.put()
        return True

    def teams_inv(self):  # generates {pid: tid}
        return {pid: tid for tid, pids in self.sync.teams.items() for pid in pids}

    def team_pid(self, pid):  # given pid, get team or return pid if no teams exist (REMINDER: TEAMS ARE CLONED ONLY)
        return int(self.teams_inv()[pid]) if (self.sync.teams and self.sync.cloned) else pid

    def get_seed(self, player=1, game_id=None, verbose_paths=False, include_sync = True):
        flags = self.flag_line(verbose_paths)
        if self.players > 1 and self.sync.mode == MultiplayerGameType.SHARED:
            flags += f"/{player}"
        if self.tracking and include_sync:
            if not game_id:
                log.warning(f"Trying to get a tracked seed with no gameId! paramId {self.key.id()}")
            else:
                flags = f"Sync{game_id}.{player},{flags}"
        outlines = [flags]
        outlines += ["|".join(p for p in line if p) for line in self.get_seed_data(player, no_door_zone = True)]
        return "\n".join(outlines) + "\n"

    def get_seed_data(self, player=1, no_door_zone = True):
        player = int(player)
        if self.sync.mode in [MultiplayerGameType.SIMUSOLO, MultiplayerGameType.SPLITSHARDS]:
            player = 1
        return [(str(p.location), s.code, s.id, p.zone) for p in self.placements for s in p.stuff if int(s.player) == self.team_pid(player)]

    def get_spoiler(self, player=1):
        if self.sync.mode in [MultiplayerGameType.SIMUSOLO, MultiplayerGameType.SPLITSHARDS]:
            player = 1
        if self.is_plando:
            return self.spoilers[0]
        return self.spoilers[self.team_pid(player) - 1]

    def get_aux_spoiler(self, exclude_types, by_zone, player=1):
        from models import Pickup
        outlines = []
        seed_data = OrderedDict()
        for coords, pcode, pid, _ in self.get_seed_data(player):
            if pcode == "EN" or pcode in exclude_types or pcode + pid == "RB81":
                continue
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
                else:
                    flags.append("mode=%s" % self.sync.mode.value)
            if self.balanced:
                flags.append("balanced")
            if self.pool_preset != "Standard":
                flags.append("pool=%s" % self.pool_preset)
            if self.sense:
                flags.append("sense=%s" % self.sense.replace(" ", "+"))
        return "%s|%s" % (",".join(flags), self.seed)

    @staticmethod
    def with_id(id):
        return SeedGenParams.get_by_id(int(id))
