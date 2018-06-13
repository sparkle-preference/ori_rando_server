# constants
from random import choice, randint, seed, sample

DUNGEONS = ["Forlorn Ruins", "Ginso Tree", "Mount Horu"]
AREAS_WITH_TPS = ["Ginso Tree", "Forlorn Ruins", "Moon Grotto", "Hollow Grove", "Sunken Glades", "Blackroot Burrows", "Thornfelt Swamp", "Valley of the Wind", "Sorrow Pass", "Lost Grove", "Mount Horu"]
AREAS = AREAS_WITH_TPS + ["Misty Woods"]
AREAS_WITH_MAPSTONES = ["Sunken Glades", "Forlorn Ruins", "Moon Grotto", "Blackroot Burrows", "Thornfelt Swamp", "Valley of the Wind", "Sorrow Pass", "Mount Horu", "Hollow Grove"]
SKILLS = ["Wall Jump", "Charge Flame", "Double Jump", "Bash", "Stomp", "Glide", "Climb", "Charge Jump", "Dash", "Grenade"]
EVENTS = ["Water Vein", "Clean Water", "Gumon Seal", "Wind Restored", "Sunstone", "Warmth Returned"]
BONUS_PICKUPS = ["Extra Double Jump", "Extra Air Dash", "Explosion Power Upgrade", "Charge Dash Efficiency", "Spirit Light Efficiency"]


class Card(object):
	singletons = [
	"Warmth Returned or 1 exp", 
	"Fish Strats or Core Skip",
	"Visit the triforce",
	"Quad Jump",
	"Hear Wilhelm's scream",
	"Collect a regen pickup",
	"Chase Gumo through the Moon Grotto",
	"Escape Kuro outside of Forlorn",
	"Drown an amphibian",
	"Drain the swamp",
	"Kill an enemy with a baneling", 
	"Escape the L4 Lava"
	]
	@staticmethod
	def all_cards():
		return [c.get() for c in Card.__subclasses__()] + Card.singletons
	@staticmethod
	def get_json(num_cards=25):
		return "[%s]" % ",\n".join(['{"name": "%s"}' % c for c in sample(Card.all_cards(), num_cards)])

class HoruRoomXorY(Card):
	@staticmethod
	def get():
		return "Complete %s or %s" % (choice(["L2", "L3", "L4"]), choice(["R2", "R3", "R4"]))

class CollectNMapstones(Card):
	@staticmethod
	def get():
		return "Collect %s mapstones" % (randint(4,6)+randint(0,2)+randint(0,1)+randint(0,1))

class OpenNDoors(Card):
	@staticmethod
	def get():
		return "Open %s keystone doors" % randint(3,6)

class BreakNBarriers(Card):
	@staticmethod
	def get():
		return "Break %s breakable walls" % randint(3,6)


class OpenNrgyDoors(Card):
	@staticmethod
	def get():
		return "Open %s energy doors" % randint(2,4)

class MaxAbilityTree(Card):
	@staticmethod
	def get():
		return "Get every ability in the %s tree" % choice(["Red", "Purple", "Blue"])

class HaveNKeystones(Card):
	@staticmethod
	def get():
		return "Have %s unspent keystones" % randint(8,16)

class DieToXorY(Card):
	@staticmethod
	def get():
		return "Die to %s or %s" % tuple(sample(["Valley Killplane", "Forlorn Approach Baneling", "Horu Lavafalls", "Spidersack spikes", "Misty Baneling", "Lightning above Sorrow Pass", "Lasers above far right Forlorn plant", "Lost Grove Lasers"],2))

class NTotalPickups(Card):	
	@staticmethod
	def get():
		return "Collect %s pickups" % randint(80,120)

class GrenadeLocked(Card):	
	@staticmethod
	def get():
		return "Light %s grenade-lanterns" % randint(3,6)

class CollectNPlants(Card):
	@staticmethod
	def get():
		return "Break %s Plants" % randint(3,6)

class CollectNUnderwater(Card):
	@staticmethod
	def get():
		return "Collect %s pickups underwater" % randint(2,5)

class NHealth(Card):
	@staticmethod
	def get():
		return "Collect %s Health Cells" % randint(4,8)

class NPoints(Card):
	@staticmethod
	def get():
		return "Level up %s abilities in any tree" % randint(12,24)

#disabled until integration
#class ReachLevelN(Card):
#	@staticmethod
#	def get():
#		return "Reach level %s" % randint(8,16)

class Nrgy(Card):
	@staticmethod
	def get():
		return "Collect %s Energy Cells" % randint(4,8)

class CollectNUnderwater(Card):
	@staticmethod
	def get():
		return "Collect %s pickups underwater" % randint(2,5)

class EnterArea(Card):
	@staticmethod
	def get():
		return "Enter %s" % choice(["Forlorn Ruins", "Lost Grove", "Sorrow Pass", "Misty Woods", "Ginso Tree"])

class DungeonEscape(Card):
	@staticmethod
	def get():
		return "Complete the %s escape" % choice(["Forlorn Ruins", "Ginso Tree"])

class ActivateNTPs(Card):
	@staticmethod
	def get():
		return "Activate %s Spirit Wells" % randint(3,6)

class StompPegXorY(Card):
	@staticmethod
	def get():
		return "Stomp the peg at %s or %s" % tuple(sample(["Hollow Groves Spider Lake", "Kuro CS Tree", "Sorrow Tumbleweed Area", "Swamp Post-Stomp", "Valley Enterance", "Above Death Gauntlet"],2))

class ActivateNTrees(Card):
	@staticmethod
	def get():
		return "Activate %s Trees" % randint(4,10)

class CollectNSkills(Card):
	@staticmethod
	def get():
		return "Collect %s Skills" % randint(6,9)

class KillByLevelup(Card):
	@staticmethod
	def get():
		return "Kill %s enemies by leveling up" % randint(2,6)

class MapstoneN(Card):
	@staticmethod
	def get():
		return "Turn in Mapstone %s" % randint(2,9)

class XorYTp(Card):
	@staticmethod
	def get():
		return "%s, %s, or %s TP" % tuple(sample(AREAS_WITH_TPS,3))

class XorYSkill(Card):
	@staticmethod
	def get():
		return "%s or %s" % tuple(sample(SKILLS,2))

class XandYSkill(Card):
	@staticmethod
	def get():
		return "%s and %s" % tuple(sample(SKILLS,2))

class XorYFullClear(Card):
	@staticmethod
	def get():
		return "Get every pickup in %s, %s, or %s" % tuple(sample(AREAS_WITH_TPS,3))

class FindXInY(Card):
	@staticmethod
	def get():
		return "Get %s pickups from %s" % (randint(2,10), choice(AREAS_WITH_TPS))

class XorYEvent(Card):
	@staticmethod
	def get():
		return "%s or %s" % tuple(sample(EVENTS,2))

class XandYMapstoneTurnins(Card):
	@staticmethod
	def get():
		return "Activate the %s and %s Mapstones" % tuple(sample(AREAS_WITH_MAPSTONES,2))

class XorYBonus(Card):
	@staticmethod
	def get():
		return "%s or %s" % tuple(sample(BONUS_PICKUPS,2))

class GarbagePickupXorY(Card):
	@staticmethod
	def get():
		return "Get the pickup at %s or %s" % tuple(sample(["Lost Grove Underwater AC", "Sunstone", "Forlorn Escape Plant", "Validation Exp", "Gladezer EC", "Forlorn HC", "R3 Plant", "Misty Grenade Pickup", "Valley Enterance Long Swim EC"],2))

class EventLocationXorY(Card):
	@staticmethod
	def get():
		return "Collect the pickup at vanilla %s or %s" % tuple(sample(["Water Vein", "Clean Water", "Gumon Seal", "Wind Restored", "Sunstone"], 2))

class WatchXorY(Card):
	@staticmethod
	def get():
		return "Watch (don't skip) %s or %s" % tuple(sample(["Racist Dad 3", "Spirit Tree Cutscene", "Post-Forlorn Escape Cutscene", "Racist Dad 2", "Sunstone cutscene", "Kuro CS"],2))

class XorYTree(Card):
	@staticmethod
	def get():
		return "Get the %s or %s Tree" % tuple(sample(SKILLS,2))

class KillEnemyXorY(Card):
	@staticmethod
	def get():
		return "Kill %s or %s" % tuple(sample(["Stomp Tree Rhino", "Grotto Miniboss", "Lower Ginso Miniboss", "Lost Grove Fight Room", "Upper Ginso Miniboss", "Misty Minibosses", "Horu Final Miniboss"],2))

class AltRAfter(Card):
	@staticmethod
	def get():
		return "Alt-r after you Find %s" % choice(["1 Experience"]+SKILLS+EVENTS)
