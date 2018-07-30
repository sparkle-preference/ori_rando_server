from protorpc import messages

import logging as log
import re

from util import is_int

import sys,os
LIBS = os.path.join(os.path.dirname(os.path.realpath(__file__)),"lib")
if LIBS not in sys.path:
	sys.path.insert(0, LIBS)
from enum import Enum, IntEnum

	

class NDB_MultiGameType(messages.Enum):
	SHARED = 1
	SWAPPED = 2
	SPLITSHARDS = 3
	SIMUSOLO = 4

class MultiplayerGameType(IntEnum):
	SHARED = 1
	SWAPPED = 2	
	SPLITSHARDS = 3
	SIMUSOLO = 4
	
	def is_dedup(self):
		return self in [MultiplayerGameType.SHARED, MultiplayerGameType.SWAPPED]

	@classmethod
	def from_ndb(clazz, ndb_val):
		return {x.name: x for x in clazz.__members__.values()}[ndb_val.name]
	@classmethod
	def to_dict(clazz):
		return { x.value: x for x in clazz.__members__.values()}	
	def to_ndb(self):
		return NDB_MultiGameType(self.value)
	def __str__(self):
		return "wraps(%s)" % self.to_ndb()

	@staticmethod
	def url_names():
		return {
			"shared": MultiplayerGameType.SHARED,
			"swap": MultiplayerGameType.SWAPPED,
			"split": MultiplayerGameType.SPLITSHARDS,
			"none": MultiplayerGameType.SIMUSOLO
		}

	@staticmethod
	def from_url(raw):
		low = raw.lower()
		names = MultiplayerGameType.url_names()
		if low in names:
			return names[low] 
		mk = MultiplayerGameType.to_dict()
		if is_int(low) and int(low) in mk:
			return mk[int(low)]
		log.warning("could not convert %s into a MultiplayerGameType! Defaulting to SIMUSOLO" % raw)
		return MultiplayerGameType.SIMUSOLO
		
class NDB_ShareType(messages.Enum):
	NOT_SHARED = 1
	DUNGEON_KEY = 2
	UPGRADE = 3
	SKILL = 4
	EVENT = 5
	TELEPORTER = 6

class ShareType(Enum):
	NOT_SHARED = 1
	DUNGEON_KEY = 2
	UPGRADE = 3
	SKILL = 4
	EVENT = 5
	TELEPORTER = 6
	
	@classmethod
	def from_ndb(clazz, ndb_val):
		return {x.name: x for x in clazz.__members__.values()}[ndb_val.name]
	@classmethod
	def to_dict(clazz):
		return { x.value: x for x in clazz.__members__.values()}	
	def to_ndb(self):
		return NDB_ShareType(self.value)
	def __str__(self):
		return "wraps(%s)" % self.to_ndb()

	@staticmethod
	def url_names():
		return {
		"keys": ShareType.DUNGEON_KEY,
		"upgrades": ShareType.UPGRADE,
		"skills": ShareType.SKILL,
		"events": ShareType.EVENT,
		"teleporters": ShareType.TELEPORTER
	}
		
	@staticmethod
	def from_url(raw):
		return [st for st in [ShareType.from_str(t) for t in re.split("+|", raw)] if st]

	@staticmethod
	def from_str(raw):
		low = raw.lower()
		names = ShareType.url_names()
		if low in names:
			return names[low]
		mk = ShareType.to_dict()
		if is_int(low) and int(low) in mk:
			return mk[int(low)]
		log.warning("could not convert %s into a ShareType! Returning None" % raw)
		return None
	
	def url_name(self):
		return {v:k for k,v in ShareType.url_names().items()}.get(self, "")
		

class StrEnum(str, Enum):
	pass
	

varToFlag = {"starved": "Starved", "hardmode": "Hard", "ohko": "OHKO", "0xp": "0XP",  "noplants": "NoPlants", "forcetrees": "ForceTrees", "discmaps": "NonProgressMapStones", "notp": "NoTeleporters", "entshuf": "Entrance", "wild": "BonusPickups", "forcemapstones": "ForceMapStones", "forcerandomescape": "ForceRandomEscape"}

class NDB_Variation(messages.Enum):
	FORCE_TREES = 1
	HARDMODE = 2
	NO_TELEPORTERS = 3
	STARVED = 4
	ONE_HIT_KO = 5
	NO_PLANTS = 6
	DISCRETE_MAPSTONES = 7
	ZERO_EXP = 8
	ENTRANCE_SHUFFLE = 9
	FORCE_MAPSTONES = 10
	FORCE_RANDOM_ESCAPE = 11
	EXTRA_BONUS_PICKUPS = 12

reverseVar = NDB_Variation.to_dict()

class Variation(StrEnum):
	FORCE_TREES = "forcetrees"
	HARDMODE = "hardmode"
	NO_TELEPORTERS = "notp"
	STARVED = "starved"
	ONE_HIT_KO = "ohko"
	NO_PLANTS = "noplants"
	DISCRETE_MAPSTONES = "discmaps"
	ZERO_EXP = "0xp"
	ENTRANCE_SHUFFLE = "entshuf"
	FORCE_MAPSTONES = "forcemapstones"
	FORCE_RANDOM_ESCAPE = "forcerandomescape"
	EXTRA_BONUS_PICKUPS = "wild"
	def to_flag(self):
		return varToFlag.get(self.value, self.value)
	@classmethod
	def from_ndb(clazz, ndb_val):
		return {x.name: x for x in clazz.__members__.values()}[ndb_val.name]
	@classmethod
	def to_dict(clazz):
		return { k:v for k,v  in clazz.__members__.iteritems()}
	def to_ndb(self):
		return reverseVar.get(self.value, None)
#	def __str__(self):
#		return "wraps(%s)" % self.to_ndb()

class LogicPath(StrEnum):
	NORMAL ="normal"
	SPEED ="speed"
	LURE ="lure"
	SPEED_LURE ="speed-lure"
	DBOOST ="dboost"
	DBOOST_LIGHT ="dboost-light"
	DBOOST_HARD ="dboost-hard"
	CDASH ="cdash"
	CDASH_FARMING ="cdash-farming"
	DBASH ="dbash"
	EXTENDED ="extended"
	LURE_HARD ="lure-hard"
	TIMED_LEVEL ="timed-level"
	GLITCHED ="glitched"
	EXTENDED_DAMAGE ="extended-damage"
	EXTREME ="extreme"

class KeyMode(StrEnum):
	SHARDS = "shards"
	CLUES = "clues"
	LIMITKEYS = "limitkeys"
	WARMTH_FRAGS = "frags"
	NONE = "default"

class PathDifficulty(StrEnum):
	EASY = "easy"
	NORMAL = "normal"
	HARD = "hard"