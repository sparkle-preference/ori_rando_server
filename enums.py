from protorpc import messages

import sys,os
LIBS = os.path.join(os.path.dirname(os.path.realpath(__file__)),"lib")
if LIBS not in sys.path:
    sys.path.insert(0, LIBS)

from enum import Enum

class StrEnum(str, Enum):
    @classmethod
    def mk(cls, val):
        try:
            return cls(val)
        except ValueError:
            return None


class NDB_MultiGameType(messages.Enum):
    SHARED = 1
    SWAPPED = 2
    SPLITSHARDS = 3
    SIMUSOLO = 4


ndbMultiTypeByName = { v.name:v for v in NDB_MultiGameType }

class MultiplayerGameType(StrEnum):
    SHARED = "Shared"
    SWAPPED = "Swap"
    SPLITSHARDS = "Split"
    SIMUSOLO = "None"

    def is_dedup(self): return self in [MultiplayerGameType.SHARED, MultiplayerGameType.SWAPPED]
    def to_ndb(self): return ndbMultiTypeByName.get(self.name, None)
    @classmethod
    def from_ndb(clazz, ndb_val):
        if ndb_val:
            return {x.name: x for x in clazz.__members__.values()}[ndb_val.name]


class NDB_ShareType(messages.Enum):
    NOT_SHARED = 1    
    DUNGEON_KEY = 2
    UPGRADE = 3
    SKILL = 4
    EVENT = 5
    TELEPORTER = 6

ndbShareTypeByName = { v.name:v for v in NDB_ShareType }

class ShareType(StrEnum):
    NOT_SHARED = "Unshareable"
    DUNGEON_KEY = "Keys"
    UPGRADE = "Upgrades"
    SKILL = "Skills"
    EVENT = "Events"
    TELEPORTER = "Teleporters"
    
    def to_ndb(self): return ndbShareTypeByName.get(self.name, None)
    @classmethod
    def from_ndb(clazz, ndb_val):
        if ndb_val:
            return {x.name: x for x in clazz.__members__.values()}[ndb_val.name]


class NDB_Variation(messages.Enum):
    FORCE_TREES = 1
    HARDMODE = 2
    STARVED = 3
    ONE_HIT_KO = 4
    DISCRETE_MAPSTONES = 5
    ZERO_EXP = 6
    ENTRANCE_SHUFFLE = 7
    FORCE_MAPSTONES = 8
    FORCE_RANDOM_ESCAPE = 9
    EXTRA_BONUS_PICKUPS = 10
    OPEN_MODE = 11
    WORLD_TOUR = 12


oldFlags = {"starved": "Starved", "hardmode": "Hard", "ohko": "OHKO", "0xp": "0XP",  "noplants": "NoPlants", "forcetrees": "ForceTrees", "discmaps": "NonProgressMapStones", "notp": "NoTeleporters", "entshuf": "Entrance", "wild": "BonusPickups", "forcemapstones": "ForceMapStones", "forcerandomescape": "ForceRandomEscape"}
ndbVarByName = { v.name:v for v in NDB_Variation }

class Variation(StrEnum):
    ZERO_EXP = "0XP"
    DISCRETE_MAPSTONES = "NonProgressMapStones"
    ENTRANCE_SHUFFLE = "Entrance"
    FORCE_MAPSTONES = "ForceMapStones"
    FORCE_RANDOM_ESCAPE = "ForceRandomEscape"
    FORCE_TREES = "ForceTrees"
    HARDMODE = "Hard"
    ONE_HIT_KO = "OHKO"
    STARVED = "Starved"
    EXTRA_BONUS_PICKUPS = "BonusPickups"
    OPEN_MODE = "Open"
    WORLD_TOUR = "WorldTour"
    @staticmethod
    def from_old(old):
        low = old.lower()
        if low not in oldFlags:
            return None
        return Variation(oldFlags[old])
    @classmethod
    def from_ndb(clazz, ndb_val):
        if ndb_val:
            return {x.name: x for x in clazz.__members__.values()}[ndb_val.name]
    def to_ndb(self):
        return ndbVarByName.get(self.name, None)


class NDB_LogicPath(messages.Enum):
    CASUAL_CORE = 1
    CASUAL_DBOOST = 2
    STANDARD_CORE = 3
    STANDARD_DBOOST = 4
    STANDARD_LURE = 5
    STANDARD_ABILITIES = 6
    EXPERT_CORE = 7
    EXPERT_DBOOST = 8
    EXPERT_LURE = 9
    EXPERT_ABILITIES = 10
    DBASH = 11
    MASTER_CORE = 12
    MASTER_DBOOST = 13
    MASTER_LURE = 14
    MASTER_ABILITIES = 15
    GJUMP = 16
    GLITCHED = 17
    TIMED_LEVEL = 18
    INSANE = 19

ndbLPByName = { v.name:v for v in NDB_LogicPath }

class LogicPath(StrEnum):
    NORMAL = "normal"
    SPEED = "speed"
    LURE = "lure"
    SPEED_LURE = "speed-lure"
    DBOOST = "dboost"
    DBOOST_LIGHT = "dboost-light"
    DBOOST_HARD = "dboost-hard"
    CDASH = "cdash"
    CDASH_FARMING = "cdash-farming"
    DBASH = "dbash"
    EXTENDED = "extended"
    LURE_HARD = "lure-hard"
    TIMED_LEVEL = "timed-level"
    GLITCHED = "glitched"
    EXTENDED_DAMAGE = "extended-damage"
    EXTREME = "extreme"
    @classmethod
    def from_ndb(clazz, ndb_val):
        if ndb_val:
            return {x.name: x for x in clazz.__members__.values()}[ndb_val.name]
    def to_ndb(self):
        return ndbLPByName.get(self.name, None)


class NDB_KeyMode(messages.Enum):
    SHARDS = 1
    CLUES = 2
    LIMITKEYS = 3
    WARMTH_FRAGS = 4
    NONE = 5
    FREE = 6

ndbKMByName = { v.name:v for v in NDB_KeyMode }

class KeyMode(StrEnum):
    SHARDS = "Shards"
    CLUES = "Clues"
    LIMITKEYS = "Limitkeys"
    WARMTH_FRAGS = "Frags"
    NONE = "Default"
    FREE = "Free"
    @classmethod
    def from_ndb(clazz, ndb_val):
        if ndb_val:
            return {x.name: x for x in clazz.__members__.values()}[ndb_val.name]
    def to_ndb(self):
        return ndbKMByName.get(self.name, None)

class NDB_PathDiff(messages.Enum):
    NORMAL = 1
    EASY = 2
    HARD = 3

ndbPMByName = { v.name:v for v in NDB_PathDiff }

class PathDifficulty(StrEnum):
    EASY = "Easy"
    NORMAL = "Normal"
    HARD = "Hard"
    @classmethod
    def from_ndb(clazz, ndb_val):
        if ndb_val:
            return {x.name: x for x in clazz.__members__.values()}[ndb_val.name]
    def to_ndb(self): return ndbPMByName.get(self.name, None)

ndbPMByName = { v.name:v for v in NDB_PathDiff }
