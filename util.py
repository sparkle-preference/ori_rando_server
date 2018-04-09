from protorpc import messages
from math import floor
from google.appengine.ext import ndb
from google.appengine.ext.ndb import msgprop


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

class Cache(object):
	WRITE_EVERY = 5
	NONE_STALE = 300
	s = {}
	@staticmethod
	def id(korid):
		try:
			return str(korid.id())
		except:
			return str(korid)

	@staticmethod
	def get(key):
		id = Cache.id(key)
		if id in Cache.s:
			v, none_reads = Cache.s[id]
			if v:
				return v
			elif none_reads < 0:
				Cache.s[id] = (v, none_reads+1)
				return None

		if "." in id:
			v = Player.get_by_id(id)
		else:
			v = Game.get_by_id(id)
		Cache.s[id] = (v, -Cache.NONE_STALE)
		return v

	@staticmethod
	def delete(korv):
		try:
			key = korv.key
		except:
			key = korv
		id = Cache.id(key)
		key.delete()
		if Cache.has(id):
			del Cache.s[id]
		
	@staticmethod
	def has(key):
		return Cache.id(key) in Cache.s	

	@staticmethod
	def put(value, force=False):
		try:
			key = value.key
			id = Cache.id(key)
			if Cache.has(id):
				_, writes = Cache.s[id]
				if force or writes >= Cache.WRITE_EVERY:
					value.put()
					Cache.s[id] = (value, 0)
				else:
					Cache.s[id] = (value, writes+1)
			else:
				key = value.put()
				id = Cache.id(key)
				Cache.s[id] = (value, 0)
		except:
			key = value.put()
			id = Cache.id(key)
			Cache.s[id] = (value, 0)
		return key

class HistoryLine(ndb.Model):
	pickup_code = ndb.StringProperty()
	pickup_id = ndb.StringProperty()
	timestamp = ndb.DateTimeProperty()
	removed = ndb.BooleanProperty()
	coords = ndb.IntegerProperty()

	def pickup(self):
		return Pickup.n(self.pickup_code, self.pickup_id)

	def print_line (self,start_time=None):
		t = (self.timestamp - start_time) if start_time and self.timestamp else self.timestamp
		if not self.removed:
			coords = unpack(self.coords)
			coords = special_coords[coords] if coords in special_coords else "(%s, %s)" % coords
			return "found %s at %s. (%s)" % (self.pickup().name, coords, t)
		else:
			return "lost %s! (%s)" % (self.pickup().name, t)

class Player(ndb.Model):
	# id = gid.pid
	skills	  = ndb.IntegerProperty()
	events	  = ndb.IntegerProperty()
	upgrades	= ndb.IntegerProperty()
	teleporters = ndb.IntegerProperty()
	seed =    ndb.TextProperty()
	signals = ndb.StringProperty(repeated=True)
	pos_x = ndb.FloatProperty(default=189.0)
	pos_y = ndb.FloatProperty(default=-219.0)
	history = ndb.StructuredProperty(HistoryLine, repeated=True)
	bitfields = ndb.ComputedProperty(lambda p: ",".join([str(x) for x in [p.skills,p.events,p.upgrades,p.teleporters]+(["|".join(p.signals)] if p.signals else [])]))
	
	def update_pos(self, x, y):
		if x == self.pos_x and y == self.pos_y:
			return True
		self.pos_x = float(x)
		self.pos_y = float(y)
		Cache.put(self)
	
	def signal_send(self, signal):
		self.signals.append(signal)
		Cache.put(self)
	
	def signal_conf(self, signal):
		self.signals.remove(signal)
		Cache.put(self, force=True)
				

class Game(ndb.Model):
	# id = Sync ID
	DEFAULT_SHARED = [ShareType.DUNGEON_KEY, ShareType.SKILL, ShareType.UPGRADE, ShareType.EVENT, ShareType.TELEPORTER]
	mode = msgprop.EnumProperty(GameMode, required=True)
	shared = msgprop.EnumProperty(ShareType, repeated=True)
	start_time = ndb.DateTimeProperty(auto_now_add=True)
	last_update = ndb.DateTimeProperty(auto_now=True)
	players = ndb.KeyProperty(Player,repeated=True)
	def summary(self):
		out_lines = ["%s (%s)" %( self.mode, ",".join([s.name for s in self.shared]))]
		if self.mode in [GameMode.SHARED, GameMode.SIMUSOLO] and len(self.players):
			src = Cache.get(self.players[0])
			for (field, cls) in [("skills", Skill), ("upgrades", Upgrade), ("teleporters", Teleporter), ("events",Event)]:
				bitmap = getattr(src,field)
				names = []
				for id,bit in cls.bits.iteritems():
					i = cls(id)
					if i.stacks:
						cnt = get_taste(bitmap,i.bit)
						if cnt>0:
							names.append("%sx %s" %(cnt, i.name))
					elif get_bit(bitmap,i.bit):
						names.append(i.name)
				out_lines.append("%s: %s" % (field, ", ".join(names)))
		return "\n\t"+"\n\t".join(out_lines)
	
	def get_players(self):
		return [Cache.get(p) for p in self.players]

	def remove_player(self, key):
		key = ndb.Key(Player, key)
		self.players.remove(key)
		Cache.put(self, force=True)
		Cache.delete(key)

	def player(self, pid):
		key = "%s.%s" % (self.key.id(), pid)
		if not Cache.has(key):
			if(self.mode == GameMode.SHARED and len(self.players)):
				src = Cache.get(self.players[0].id())
				player = Player(id=key, skills = src.skills, events = src.events, upgrades = src.upgrades, teleporters = src.teleporters, history=[], signals=[])
			else:
				player = Player(id=key, skills = 0, events=0, upgrades = 0, teleporters = 0, history=[])
			k = Cache.put(player)
			if k not in self.players:
				# weird things can happen... lmao
				self.players.append(k)
			Cache.put(self, force=True)
		
		return Cache.get(key)

	def found_pickup(self, finder, pickup, coords, remove=False):
		retcode = 200
		found_player = self.player(finder)
		if (pickup.share_type not in self.shared):
			retcode = 406
		elif (self.mode == GameMode.SHARED):
			for player in self.get_players():
				for (field, cls) in [("skills", Skill), ("upgrades", Upgrade), ("teleporters", Teleporter), ("events",Event)]:
					if isinstance(pickup, cls):
						if pickup.stacks:
							setattr(player,field,inc_stackable(getattr(player,field), pickup.bit, remove))
						else:
							setattr(player,field,add_single(getattr(player,field), pickup.bit, remove))
						Cache.put(player)
		elif self.mode == GameMode.SPLITSHARDS:
			shard_locs = [h.coords for player in self.players for h in player.get().history if h.pickup_code == "RB" and h.pickup_id in ["17", "19", "21"]]
			if coords in shard_locs:
				retcode = 410
		elif (self.mode == GameMode.SIMUSOLO):
			found_player.history.append(HistoryLine(pickup_code = pickup.code, timestamp = datetime.now(), pickup_id = str(pickup.id), coords = coords, removed = remove))
			Cache.put(found_player)
			return 200
		else:
			print "game mode not implemented"
			retcode = 404
		if retcode != 410: #410 GONE aka "haha nope"
			found_player.history.append(HistoryLine(pickup_code = pickup.code, timestamp = datetime.now(), pickup_id = str(pickup.id), coords = coords, removed = remove))
			Cache.put(found_player)
		return retcode

def delete_game(game):
	"""Expects game, NOT game id"""
	[Cache.delete(p) for p in game.players]
	Cache.delete(game)

def clean_old_games():
	old = [game for game in Game.query(Game.last_update < datetime.now() - timedelta(hours=12))]
	return len([delete_game(game) for game in old])
	
def get_new_game(_mode = None, _shared = None, id=None):
	shared = [share_from_url(i) for i in _shared] if _shared else Game.DEFAULT_SHARED
	mode = GameMode(int(_mode)) if _mode else GameMode.SHARED
	if not id:
		id = 1
		game_ids = set([int(game.key.id()) for game in Game.query()])
		while id in game_ids:
			id += 1
		if id > 20:
			clean_old_games()

	game_id = id
	game = Game(id = str(game_id), players=[], shared=shared, mode=mode)
	key = Cache.put(game, force=True)
	return game

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
	-4600020: -4199936,
	8599908: 8599904,
	2959744: 2919744, 
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

