from google.appengine.ext import ndb
from google.appengine.ext.ndb import msgprop

import logging as log

from util import enums_from_strlist
from enums import (NDB_MultiGameType, NDB_ShareType, NDB_Variation, NDB_LogicPath, NDB_KeyMode, NDB_PathDiff,
                   MultiplayerGameType, ShareType, Variation, LogicPath, KeyMode, PathDifficulty)
from collections import OrderedDict
from seedbuilder.generator import SeedGenerator

presets = {
    "Casual":    set([LogicPath.NORMAL, LogicPath.DBOOST_LIGHT]),
    "Standard":    set([LogicPath.NORMAL, LogicPath.SPEED, LogicPath.LURE, LogicPath.DBOOST_LIGHT]),
    "Expert":    set([LogicPath.NORMAL, LogicPath.SPEED, LogicPath.LURE, LogicPath.SPEED_LURE, LogicPath.DBOOST, LogicPath.DBOOST_LIGHT, LogicPath.CDASH, LogicPath.EXTENDED, LogicPath.EXTENDED_DAMAGE]),
    "Master":    set([LogicPath.NORMAL, LogicPath.SPEED, LogicPath.LURE, LogicPath.SPEED_LURE, LogicPath.DBOOST, LogicPath.DBOOST_LIGHT, LogicPath.DBOOST_HARD, LogicPath.CDASH, LogicPath.DBASH, LogicPath.EXTENDED, LogicPath.EXTENDED_DAMAGE, LogicPath.LURE_HARD, LogicPath.EXTREME]),
    "Glitched":    set([LogicPath.NORMAL, LogicPath.SPEED, LogicPath.DBOOST_LIGHT, LogicPath.DBOOST, LogicPath.LURE, LogicPath.SPEED_LURE, LogicPath.LURE_HARD, LogicPath.DBOOST_HARD, LogicPath.EXTENDED, LogicPath.EXTENDED_DAMAGE, LogicPath.DBASH, LogicPath.CDASH, LogicPath.EXTREME, LogicPath.TIMED_LEVEL, LogicPath.GLITCHED, LogicPath.CDASH_FARMING]),
    #    "0xp":        set([LogicPath.NORMAL, LogicPath.SPEED, LogicPath.LURE, LogicPath.DBOOST_LIGHT]),
    #   0xp has the same LPs as standard. Gotta distinguish elsewhere :C
    "Hard":        set([LogicPath.NORMAL, LogicPath.SPEED, LogicPath.LURE, LogicPath.DBOOST_LIGHT, LogicPath.CDASH, LogicPath.DBASH, LogicPath.EXTENDED]),
    "Ohko":        set([LogicPath.NORMAL, LogicPath.SPEED, LogicPath.LURE, LogicPath.CDASH, LogicPath.DBASH, LogicPath.EXTENDED])
}


class Stuff(ndb.Model):
    code = ndb.StringProperty()
    id = ndb.StringProperty()
    player = ndb.StringProperty()


class Placement(ndb.Model):
    location = ndb.StringProperty()
    zone = ndb.StringProperty()
    stuff = ndb.LocalStructuredProperty(Stuff, repeated=True)


class WarmthFragmentOptions(ndb.Model):
    enabled = ndb.BooleanProperty(default=False)
    count = ndb.IntegerProperty()
    key_1 = ndb.IntegerProperty()
    key_2 = ndb.IntegerProperty()
    key_3 = ndb.IntegerProperty()
    required = ndb.IntegerProperty()
    tolerance = ndb.IntegerProperty()

    @staticmethod
    def from_url(qparams):
        opts = WarmthFragmentOptions()
        opts.enabled = bool(qparams.get("frag_count"))
        if opts.enabled:
            opts.count = int(qparams.get("frag_count", 40))
            opts.key_1 = int(qparams.get("frag_key_1", 7))
            opts.key_2 = int(qparams.get("frag_key_2", 14))
            opts.key_3 = int(qparams.get("frag_key_3", 21))
            opts.required = int(qparams.get("frag_required", 28))
            opts.tolerance = int(qparams.get("frag_tolerance", 3))
        return opts


class MultiplayerOptions(ndb.Model):
    ndb_mode = msgprop.EnumProperty(
        NDB_MultiGameType, default=NDB_MultiGameType.SIMUSOLO)
    ndb_shared = msgprop.EnumProperty(NDB_ShareType, repeated=True)

    def get_mode(self): return MultiplayerGameType.from_ndb(self.ndb_mode)

    def set_mode(self, mode):         self.ndb_mode = mode.to_ndb()

    def get_shared(self): return [ShareType.from_ndb(ndb_st)
                               for ndb_st in self.ndb_shared]

    def set_shared(self, shared):    self.ndb_shared = [s.to_ndb() for s in shared]

    mode = property(get_mode, set_mode)
    shared = property(get_shared, set_shared)
    enabled = ndb.BooleanProperty(default=False)
    cloned = ndb.BooleanProperty(default=True)
    hints = ndb.BooleanProperty(default=True)
    teams = ndb.PickleProperty(default={})

    @staticmethod
    def from_url(qparams):
        opts = MultiplayerOptions()
        opts.enabled = int(qparams.get("players", 1)) > 1
        if opts.enabled:
            opts.mode = MultiplayerGameType(qparams.get("sync_mode", "None"))
            opts.cloned = qparams.get("sync_gen") != "disjoint"
            opts.hints = bool(opts.cloned and qparams.get("sync_hints"))
            opts.shared = enums_from_strlist(ShareType, qparams.getall("sync_shared"))

            teamsRaw = qparams.get("teams")
            if teamsRaw and opts.mode == MultiplayerGameType.SHARED and opts.cloned:
                cnt = 1
                teams = {}
                for teamRaw in teamsRaw.split("|"):
                    teams[cnt] = [int(p) for p in teamRaw.split(",")]
                    cnt += 1
                opts.teams = teams
        return opts


class SeedGenParams(ndb.Model):
    ndb_vars = msgprop.EnumProperty(NDB_Variation, repeated=True)
    ndb_paths = msgprop.EnumProperty(NDB_LogicPath, repeated=True)
    ndb_pathdiff = msgprop.EnumProperty(NDB_PathDiff, default=NDB_PathDiff.NORMAL)
    ndb_keymode = msgprop.EnumProperty(NDB_KeyMode, default=NDB_KeyMode.CLUES)

    def get_pathdiff(self): return PathDifficulty.from_ndb(self.ndb_pathdiff)

    def set_pathdiff(self, pathdiff): self.ndb_pathdiff = pathdiff.to_ndb()

    def get_vars(self): return [Variation.from_ndb(ndb_var) for ndb_var in self.ndb_vars]

    def set_vars(self, vars): self.ndb_vars = [v.to_ndb() for v in vars]

    def get_paths(self): return [LogicPath.from_ndb(ndb_path) for ndb_path in self.ndb_paths]

    def set_paths(self, paths): self.ndb_paths = [p.to_ndb() for p in paths]

    def get_keymode(self): return KeyMode.from_ndb(self.ndb_keymode)

    def set_keymode(self, key_mode):     self.ndb_keymode = key_mode.to_ndb()

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
    warmth = ndb.LocalStructuredProperty(WarmthFragmentOptions)
    placements = ndb.LocalStructuredProperty(
        Placement, repeated=True, compressed=True)
    spoilers = ndb.TextProperty(repeated=True, compressed=True)

    @staticmethod
    def from_url(qparams):
        params = SeedGenParams()
        params.seed = qparams.get("seed")
        if not params.seed:
            log.error("No seed in %r! returning None" % qparams)
            return None
        params.variations = enums_from_strlist(Variation, qparams.getall("var"))
        params.logic_paths = enums_from_strlist(LogicPath, qparams.getall("path"))
        if not params.logic_paths:
            log.error("No logic paths in %r! returning None" % qparams)
            return None
        params.key_mode = KeyMode(qparams.get("key_mode", "Clues"))
        params.path_diff = PathDifficulty(qparams.get("path_diff", "Normal"))
        params.exp_pool = int(qparams.get("exp_pool", 10000))
        params.balanced = qparams.get("gen_mode") != "Classic"
        params.players = int(qparams.get("players", 1))
        params.tracking = qparams.get("tracking") != "Disabled"
        params.warmth = WarmthFragmentOptions.from_url(qparams)
        params.sync = MultiplayerOptions.from_url(qparams)
        raw_fass = qparams.get("fass")
        if raw_fass:
            params.placements = []
            for fass in raw_fass.split("|"):
                loc, _, item = fass.partition(":")
                stuff = [Stuff(code=item[:2], id=item[2:], player="")]
                params.placements.append(Placement(location=loc, zone="", stuff=stuff))
        return params.put()

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
                stuff = Stuff(code=stuff_code, id=stuff_id, player=str(player))
                if loc not in placemap:
                    placemap[loc] = Placement(location=loc, zone=zone, stuff=[stuff])
                else:
                    placemap[loc].stuff.append(stuff)
        if player != self.players and player != len(self.sync.teams):
            log.error("seed count mismatch!, %s != %s or %s", player, self.players, len(self.teams))
            return False
        self.spoilers = spoilers
        self.placements = placemap.values()
        self.put()
        return True

    def teams_inv(self):  # generates {pid: tid}
        return {pid: tid for tid, pids in self.sync.teams.iteritems() for pid in pids}

    def team_pid(self, pid):  # given pid, get team or return pid if no teams exist
        return self.teams_inv()[pid] if self.sync.teams else pid

    def get_seed(self, player=1, game_id=None, verbose_paths= False):
        flags = self.flag_line(verbose_paths)
        if self.tracking:
            flags = "Sync%s.%s," % (game_id, player) + flags
        outlines = [flags]
        outlines += ["|".join((str(p.location), s.code, s.id, p.zone))
               for p in self.placements for s in p.stuff if int(s.player) == self.team_pid(player)]
        return "\n".join(outlines)+"\n"

    def get_spoiler(self, player=1):
        return self.spoilers[self.team_pid(player)-1]

    def get_preset(self):
        pathset = set(self.logic_paths)
        for name, lps in presets.iteritems():
            if lps == pathset:
                if name == "Standard" and Variation.ZERO_EXP in self.variations:
                    return "0xp"
                return name
        return "Custom"

    def flag_line(self, verbose_paths=False):
        flags = []
        if verbose_paths:
            flags.append("lps=%s" %
                         "+".join([lp.capitalize() for lp in self.logic_paths]))
        else:
            flags.append(self.get_preset())
        flags.append(self.key_mode)
        if self.warmth.enabled:
            flags.append("Frags/%s/%s/%s/%s/%s/%s" % (self.warmth.count, self.warmth.key_1,
                                             self.warmth.key_2, self.warmth.key_3, self.warmth.required, self.warmth.tolerance))
        flags += [v.value for v in self.variations]
        if self.path_diff != PathDifficulty.NORMAL:
            flags.append("prefer_path_difficulty=%s" % self.path_diff.value)
        if self.sync.enabled:
            flags.append("mode=%s" % self.sync.mode.value)
            if self.sync.shared:
                flags.append("shared=%s" % "+".join(self.sync.shared))
        if self.balanced:
            flags.append("balanced")
        return "%s|%s" % (",".join(flags), self.seed)

    @staticmethod
    def with_id(id):
        return SeedGenParams.get_by_id(int(id))
