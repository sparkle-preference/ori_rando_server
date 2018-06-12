# constants
from random import choice, randint, seed, sample

DUNGEONS = ["Forlorn Ruins", "Ginso Tree", "Mount Horu"]
AREAS_WITH_TPS = ["Ginso Tree", "Forlorn Ruins", "Moon Grotto", "Hollow Grove", "Sunken Glades", "Blackroot Burrows", "Thornfelt Swamp", "Valley of the Wind", "Sorrow Pass", "Lost Grove", "Mount Horu"]
AREAS = AREAS_WITH_TPS + ["Misty Woods"]
SKILLS = ["Wall Jump", "Charge Flame", "Double Jump", "Bash", "Stomp", "Glide", "Climb", "Charge Jump", "Dash", "Grenade"]
EVENTS = ["Water Vein", "Clean Water", "Gumon Seal", "Wind Restored", "Sunstone", "Warmth Returned"]
BONUS_PICKUPS = ["Extra Double Jump", "Extra Air Dash", "Explosion Power Upgrade", "Charge Dash Efficiency", "Spirit Light Efficiency"]


class Card(object):
	singletons = [
	"Warmth Returned or 1 exp", 
	"Fish Strats or Core Skip",
	"Save only on spirit wells",
	"Visit the triforce",
	"Quad Jump",
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
		return "Complete %s or %s" % (choice(["L1", "L2", "L3", "L4"]), choice(["R1", "R2", "R3", "R4"]))

class HaveNMapstones(Card):
	@staticmethod
	def get():
		return "Have %s mapstones" % randint(2,4)

class OpenNDoors(Card):
	@staticmethod
	def get():
		return "Open %s keystone doors" % randint(3,6)

class OpenNrgyDoors(Card):
	@staticmethod
	def get():
		return "Open %s energy doors" % randint(2,4)

class MaxAbilityTree(Card):
	@staticmethod
	def get():
		return "Get every ability in the %s tree" % choice(["Red", "Purple"])

class HaveNKeystones(Card):
	@staticmethod
	def get():
		return "Have %s unspent keystones" % randint(8,16)

class DieToXorY(Card):
	@staticmethod
	def get():
		return "Die to %s or %s" % tuple(sample(["Valley Killplane", "Forlorn Approach Baneling", "Lava", "Spidersack spikes", "Misty Baneling", "Lightning above Sorrow Pass", "Lasers above far right Forlorn plant", "Lost Grove Lasers"],2))

class NTotalPickups(Card):	
	@staticmethod
	def get():
		return "Collect %s pickups" % randint(80,120)

class Regen(Card):	
	@staticmethod
	def get():
		return "Collect %s regen pickups" % randint(2,4)

class GrenadeLocked(Card):	
	@staticmethod
	def get():
		return "Collect %s grenade-locked pickups" % randint(3,6)

class CollectNPlants(Card):
	@staticmethod
	def get():
		return "Break %s Plants" % randint(5,12)

class CollectNUnderwater(Card):
	@staticmethod
	def get():
		return "Collect %s pickups underwater" % randint(2,5)

class NHealth(Card):
	@staticmethod
	def get():
		return "Have %s Health" % randint(8,11)

class NPoints(Card):
	@staticmethod
	def get():
		return "Have %s Unspent Ability Points" % randint(5,12)

class Nrgy(Card):
	@staticmethod
	def get():
		return "Have %s Energy" % randint(6,9)

class CollectNUnderwater(Card):
	@staticmethod
	def get():
		return "Collect %s pickups underwater" % randint(2,5)

class EnterDungeon(Card):
	@staticmethod
	def get():
		return "Enter %s" % choice(DUNGEONS)

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
		return "Stomp the peg at %s or %s" % tuple(sample(["Right of Spidersack", "Kuro CS Tree", "Sorrow Tumbleweed Area", "Swamp Post-Stomp", "Valley Enterance"],2))

class ActivateNTrees(Card):
	@staticmethod
	def get():
		return "Activate %s Trees" % randint(3,10)

class CollectNSkills(Card):
	@staticmethod
	def get():
		return "Collect %s Skills" % randint(6,9)

class KillNBanelings(Card):
	@staticmethod
	def get():
		return "Kill %s unique Banelings" % randint(3,6)

class KillNBanelings(Card):
	@staticmethod
	def get():
		return "Kill %s enemies by leveling up" % randint(2,6)

class MapstoneN(Card):
	@staticmethod
	def get():
		return "Mapstone %s" % randint(2,9)

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
		return "Full clear %s, %s, or %s" % tuple(sample(AREAS_WITH_TPS,3))

class XorYEvent(Card):
	@staticmethod
	def get():
		return "%s or %s" % tuple(sample(EVENTS,2))

class XorYBonus(Card):
	@staticmethod
	def get():
		return "%s or %s" % tuple(sample(BONUS_PICKUPS,2))

class GarbagePickupXorY(Card):
	@staticmethod
	def get():
		return "Get the pickup at %s or %s" % tuple(sample(["Lost Grove Underwater AC", "Racist Dad 3 AC", "Sunstone", "Forlorn Escape Plant", "Atsu's Torch", "Validation Exp", "Gladezer EC"],2))

class Never(Card):
	@staticmethod
	def get():
		return "Never %s" % choice(["Double Bash", "Greande Jump", "Rocket Jump"])

class WatchXorY(Card):
	@staticmethod
	def get():
		return "Watch %s or %s" % tuple(sample(["Racist Dad 3", "Spirit Tree Cutscene", "Post-Forlorn Escape Cutscene", "Racist Dad 2", "Sunstone cutscene"],2))

class KillEnemyXorY(Card):
	@staticmethod
	def get():
		return "Kill %s or %s" % tuple(sample(["Wilhelm", "Stomp Tree Rhino", "Grotto Miniboss", "Lower Ginso Miniboss", "Upper Ginso Miniboss", "Misty Minibosses", "Horu Final Miniboss"],2))

class AltRAfter(Card):
	@staticmethod
	def get():
		return "Alt-r after you Find %s" % choice(["1 Experience"]+SKILLS+EVENTS)
