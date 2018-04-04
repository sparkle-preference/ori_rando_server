from protorpc import messages
from math import floor

class GameMode(messages.Enum):
	SHARED = 1
	SWAPPED = 2				#not implemented, needs client work
	SPLITSHARDS = 3
	SIMUSOLO = 4


class ShareType(messages.Enum):
	NOT_SHARED = 1
	DUNGEON_KEY = 2
	UPGRADE = 3
	SKILL = 4
	EVENT = 5
	TELEPORTER = 6

share_map = {
	"keys": ShareType.DUNGEON_KEY,
	"upgrades": ShareType.UPGRADE,
	"skills": ShareType.SKILL,
	"events": ShareType.EVENT,
	"teleporters": ShareType.TELEPORTER
}
rev_map = {v:k for k,v in share_map.iteritems()}


def share_from_url(s):
	return share_map[s]

def url_from_share(share_types):
	"+".fold(rev_map[type] for type in share_types)

coord_correction_map = {
	-520160: -560160,
	-4199936: -4600020,
	8599908: 8599904
}
	
class Pickup(object):
	@staticmethod
	def subclasses():
		return [Skill, Event, Teleporter, Upgrade, Experience, AbilityCell, HealthCell, EnergyCell, Keystone, Mapstone]
	
	stacks = False
	def __eq__(self, other):
		return isinstance(other, Pickup) and self.id == other.id
	@classmethod
	def n(cls, code, id):
		for subcls in Pickup.subclasses():
			if code == subcls.code:
				return subcls(id)
		return None
	@classmethod
	def name(cls, code, id):
		for subcls in Pickup.subclasses():
			if code == subcls.code and subcls(id):
				return subcls(id).name
 		return "%s|%s" % (code, id)


class Skill(Pickup):
	bits = {0:1, 2:2, 3:4, 4:8, 5:16, 8:32, 12:64, 14:128, 50:256, 51:512}
	names = {0:"Bash", 2:"Charge Flame", 3:"Wall Jump", 4:"Stomp", 5:"Double Jump",8:"Charge Jump",12:"Climb",14:"Glide",50:"Dash",51:"Grenade"}
	share_type = ShareType.SKILL
	code = "SK"
	def __new__(cls, id):
		id = int(id)
		if id not in Skill.bits or id not in Skill.names:
			return None
		inst = super(Skill, cls).__new__(cls)
		inst.id, inst.bit, inst.name = id, Skill.bits[id], Skill.names[id]
		return inst

class Event(Pickup):
	bits = {0:1, 1:2, 2:4, 3:8, 4:16, 5:32}
	names = {0:"Water Vein", 1:"Clean Water", 2:"Gumon Seal", 3:"Wind Restored", 4:"Sunstone", 5:"Warmth Returned"}
	code = "EV"
	def __new__(cls, id):
		id = int(id)
		if id not in Event.bits or id not in Event.names:
			return None
		inst = super(Event, cls).__new__(cls)
		inst.id, inst.bit, inst.name = id, Event.bits[id], Event.names[id]
		inst.share_type = ShareType.EVENT if id in [1, 3, 5] else ShareType.DUNGEON_KEY
		return inst

class Teleporter(Pickup):
	bits = {"Grove":1, "Swamp":2, "Grotto":4, "Valley":8, "Forlorn":16, "Sorrow":32}
	code = "TP"
	def __new__(cls, id):
		if id not in Teleporter.bits:
			return None
		inst = super(Teleporter, cls).__new__(cls)
		inst.id, inst.bit, inst.name = id, Teleporter.bits[id], id + " teleporter"
		inst.share_type = ShareType.TELEPORTER
		return inst

class Upgrade(Pickup):
	stacking= set([6,13,15,17,19,21])
	name_only = set([0, 1])
	names = {17:  "Water Vein Shard", 19: "Gumon Seal Shard", 21: "Sunstone Shard", 6: "Spirit Flame Upgrade", 13: "Health Regeneration", 15: "Energy Regeneration", 8: "Explosion Power Upgrade", 9:  "Spirit Light Efficiency", 10: "Extra Air Dash", 11:  "Charge Dash Efficiency", 12:  "Extra Double Jump", 0: "Mega Health", 1: "Mega Energy"}
	bits = {17:1, 19:4, 21:16, 6:64, 13:256, 15:1024, 8:4096, 9:8192, 10:16384, 11:32768, 12:65536}
	code = "RB"
	def __new__(cls, id):
		id = int(id)
		if id in Upgrade.name_only:
			inst = super(Upgrade, cls).__new__(cls)
			inst.id, inst.share_type, inst.name = id, ShareType.NOT_SHARED, Upgrade.names[id]
			return inst
		if id not in Upgrade.bits or id not in Upgrade.names:
			return None
		inst = super(Upgrade, cls).__new__(cls)
		inst.id, inst.bit, inst.name = id, Upgrade.bits[id], Upgrade.names[id]
		inst.stacks = id in Upgrade.stacking
		inst.share_type = ShareType.DUNGEON_KEY if id in [17, 19, 21] else ShareType.UPGRADE
		return inst

class Experience(Pickup):
	code="EX"
	def __new__(cls, id):
		id = int(id)
		inst = super(Experience, cls).__new__(cls)
		inst.id, inst.bit, inst.name = id, None, "%s experience" % id
		inst.share_type = ShareType.NOT_SHARED
		return inst

class AbilityCell(Pickup):
	code="AC"
	def __new__(cls, id):
		id = int(id)
		inst = super(AbilityCell, cls).__new__(cls)
		inst.id, inst.bit, inst.name = id, None, "Ability Cell"
		inst.share_type = ShareType.NOT_SHARED
		return inst

class HealthCell(Pickup):
	code="HC"
	def __new__(cls, id):
		id = int(id)
		inst = super(HealthCell, cls).__new__(cls)
		inst.id, inst.bit, inst.name = id, None, "Health Cell"
		inst.share_type = ShareType.NOT_SHARED
		return inst

class EnergyCell(Pickup):
	code="EC"
	def __new__(cls, id):
		id = int(id)
		inst = super(EnergyCell, cls).__new__(cls)
		inst.id, inst.bit, inst.name = id, None, "Energy Cell"
		inst.share_type = ShareType.NOT_SHARED
		return inst

class Mapstone(Pickup):
	code="MS"
	def __new__(cls, id):
		id = int(id)
		inst = super(Mapstone, cls).__new__(cls)
		inst.id, inst.bit, inst.name = id, None, "Mapstone"
		inst.share_type = ShareType.NOT_SHARED
		return inst

class Keystone(Pickup):
	code="KS"
	def __new__(cls, id):
		id = int(id)
		inst = super(Keystone, cls).__new__(cls)
		inst.id, inst.bit, inst.name = id, None, "Keystone"
		inst.share_type = ShareType.NOT_SHARED
		return inst



def int_to_bits(n, min_len=2):
	raw = [1 if digit=='1' else 0 for digit in bin(n)[2:]]
	if len(raw) < min_len:
		raw = [0]*(min_len-len(raw))+raw
	return raw

def bits_to_int(n):
	return int("".join([str(b) for b in n]),2)



log_2 = {1:0, 2:1, 4:2, 8:3, 16:4, 32:5, 64:6, 128:7, 256:8, 512:9, 1024:10, 2048:11, 4096:12, 8192:13, 16384:14, 32768:15, 65536:16}
special_coords = {(0,0): "Vanilla Water Vein",
	(0,4): "Ginso Escape Finish",
	(0,8): "Misty Orb Turn-In",
	(0,12): "Forlorn Escape Start",
	(0,16): "Vanilla Sunstone",
	(0,20): "Final Escape Start"}

special_coords.update({(0,20+4*x): "Mapstone %s" % x for x in range(1,10)})

def get_bit(bits_int, bit):
	return int_to_bits(bits_int, log_2[bit]+1)[-(1+log_2[bit])]

def get_taste(bits_int, bit):
	bits = int_to_bits(bits_int,log_2[bit]+2)[-(2+log_2[bit]):][:2]
	return 2*bits[0]+bits[1]

def add_single(bits_int, bit, remove=False):
	if bits_int >= bit:
		if remove:
			return bits_int-bit
		if get_bit(bits_int, bit) == 1:
			return bits_int
	return bits_int + bit

def inc_stackable(bits_int, bit, remove=False):
	if remove:
		if get_taste(bits_int, bit) > 0:
			return bits_int - bit
		return bits_int

	if get_taste(bits_int, bit) > 2:
		return bits_int
	return bits_int+bit


def get(x,y):
	return x*10000 + y

def sign(x):
	return 1 if x>=0 else -1

def rnd(x):
	return int(4*floor(float(x)/4.0)*sign(x))

def unpack(coord):
	y = coord % (sign(coord)*10000)
	if y > 2000:
		y -= 10000
	elif y < -2000:
		y += 10000
	if y < 0:
		coord -= y
	x = rnd(coord/10000)
	return x,y

