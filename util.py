from protorpc import messages
from math import floor
from collections import defaultdict
from google.appengine.ext import ndb
from google.appengine.ext.ndb import msgprop
from datetime import datetime, timedelta
import sys,os
LIBS = os.path.join(os.path.dirname(os.path.realpath(__file__)),"lib")
if LIBS not in sys.path:
	sys.path.insert(0, LIBS)

class GameMode(messages.Enum):
	SHARED = 1
	SWAPPED = 2				#not implemented, needs client work
	SPLITSHARDS = 3
	SIMUSOLO = 4


DEDUP_MODES = [GameMode.SHARED, GameMode.SWAPPED]

mode_map = {
	"shared": 1,
	"swap": 2,
	"split": 3,
	"none": 4
}

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


def url_from_share(share_types):
	"+".fold(rev_map[type] for type in share_types)

class Cache(object):
	pos = {}
	hist = {}
	lastSanCheck = {}

	@staticmethod
	def canSanCheck(gid):
		gid = int(gid)
		if gid not in Cache.lastSanCheck:
			return True
		return timedelta(seconds=10) < (datetime.now() - Cache.lastSanCheck[gid])

	@staticmethod
	def doSanCheck(gid):
		gid = int(gid)
		Cache.lastSanCheck[gid] = datetime.now()

	@staticmethod
	def setHist(gid, pid, hist):
		gid = int(gid)
		pid = int(pid)
		newHists = Cache.hist[gid] if gid in Cache.hist else {}
		newHists[pid] = hist
		Cache.hist[gid] = newHists


	@staticmethod
	def getHist(gid):
		gid = int(gid)
		return Cache.hist[gid].copy() if gid in Cache.hist else None

	@staticmethod
	def setHist(gid, pid, hist):
		gid = int(gid)
		pid = int(pid)
		newHists = Cache.hist[gid] if gid in Cache.hist else {}
		newHists[pid] = hist
		Cache.hist[gid] = newHists

	@staticmethod
	def removeGame(gid):
		gid = int(gid)
		if gid in Cache.hist:
			del Cache.hist[gid]
		if gid in Cache.pos:
			del Cache.pos[gid]
		if gid in Cache.lastSanCheck:
			del Cache.lastSanCheck[gid]

	@staticmethod
	def removePlayer(gid, pid):
		gid = int(gid)
		newHists = Cache.hist[gid] if gid in Cache.hist else {}
		newHists[pid] = hist
		Cache.hist[gid] = newHists

	@staticmethod
	def getPos(gid):
		gid = int(gid)
		return Cache.pos[gid].copy() if gid in Cache.pos else None

	@staticmethod
	def setPos(gid, pid, x, y):
		gid = int(gid)
		pid = int(pid)
		newPos = Cache.pos[gid] if gid in Cache.pos else {}
		newPos[pid] = (x,y)
		Cache.pos[gid] = newPos
	
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





class Stuff(ndb.Model):
	code = ndb.StringProperty()
	id = ndb.StringProperty()
	player = ndb.StringProperty()

class Placement(ndb.Model):
	location = ndb.StringProperty()
	zone = ndb.StringProperty()
	stuff = ndb.LocalStructuredProperty(Stuff, repeated=True)
	
class Seed(ndb.Model):
	#id = author:name
	placements = ndb.LocalStructuredProperty(Placement, repeated=True)
	flags = ndb.StringProperty(repeated=True)
	hidden = ndb.BooleanProperty(default=False)
	description = ndb.TextProperty()
	players = ndb.IntegerProperty(default=1)
	author = ndb.StringProperty(required=True)
	name = ndb.StringProperty(required=True)

	def mode(self):
		mode_opt = [int(f[5:]) for f in self.flags if f.lower().startswith("mode=")]
		return GameMode(mode_opt[0]) if mode_opt else None
	def shared(self):
		shared_opt = [f[7:].replace("+"," ").split(" ") for f in self.flags if f.lower().startswith("shared=")]
		return [share_map[i] for i in shared_opt[0] if i in share_map] if shared_opt else []

	
	@staticmethod
	def from_plando(lines, author, name, desc):
		s = Seed(id="%s:%s" % (author, name), name=name, author=author, description=desc)
		rawFlags,_,s.name = lines[0].partition("|")
		s.flags = [flag.replace(" ", "+") for flag in rawFlags.split(",") if not flag.lower().startswith("sync")]
		for line in lines[1:]:
			loczone,_,stuffs = line.partition(":")
			loc,_,zone = loczone.partition("|")
			plc = Placement(location=loc,zone=zone)
			for stuff in stuffs.split(","):
				player,_,codeid = stuff.partition(".")
				if int(player) > s.players:
					s.players = int(player)
				code,_,id = codeid.partition("|")
				plc.stuff.append(Stuff(code=code,id=id,player=player))
			s.placements.append(plc)
		
		return s

	def to_plando_lines(self):
		outlines = ["%s|%s" % (",".join(self.flags), self.name)]
		for p in self.placements:
			outlines.append(p.location + ":" + ",".join(["%s.%s|%s" % (s.player, s.code, s.id) for s in p.stuff]))
		return outlines
	
	def to_lines(self, player=1, extraFlags=[]):
		return ["%s|%s" % (",".join(extraFlags + self.flags), self.name)] + ["|".join((str(p.location),s.code,s.id,p.zone))for p in self.placements for s in p.stuff if int(s.player) == player]

		

class Player(ndb.Model):
	# id = gid.pid
	skills	  = ndb.IntegerProperty()
	events	  = ndb.IntegerProperty()
	upgrades	= ndb.IntegerProperty()
	bonuses 	= ndb.JsonProperty(default={})
	teleporters = ndb.IntegerProperty()
	seed =    ndb.TextProperty()
	signals = ndb.StringProperty(repeated=True)
	history = ndb.LocalStructuredProperty(HistoryLine, repeated=True)
	bitfields = ndb.ComputedProperty(lambda p: ",".join([str(x) for x in [p.skills,p.events,p.upgrades,p.teleporters]+(["|".join(p.signals)] if p.signals else [])]))
	
	# post-refactor version of bitfields
	def output(self):
		outlines = [str(x) for x in [self.skills,self.events,self.teleporters]]
		outlines.append(";".join([str(id) + "x%s" % count for (id, count) in self.bonuses.iteritems()]))
		if self.signals:
			outlines.append("|".join(self.signals))
		return ",".join(outlines)
	
	def signal_send(self, signal):
		self.signals.append(signal)
		self.put()
	
	def signal_conf(self, signal):
		self.signals.remove(signal)
		self.put()
	
	def give_pickup(self, pickup, remove=False, delay_put=False):
		print self.key.id(), pickup, remove, delay_put
		if pickup.code == "RB":
			# handle upgrade refactor storage
			pick_id = str(pickup.id)
			if remove:
				if pick_id in self.bonuses:
					self.bonuses[pick_id] -= 1
					if self.bonuses[pick_id] == 0:
						del self.bonuses[pick_id]
			else:
				if pick_id in self.bonuses:
					if not (pickup.max and self.bonuses[pick_id] >= pickup.max):
						self.bonuses[pick_id] += 1
				else:
					self.bonuses[pick_id] = 1
		# bitfields
			self.upgrades = add_pickup_to_bitfield(self.upgrades, pickup, remove)
		elif pickup.code == "SK":
			self.skills = add_pickup_to_bitfield(self.skills, pickup, remove)
		elif pickup.code == "TP":
			self.teleporters = add_pickup_to_bitfield(self.teleporters, pickup, remove)
		elif pickup.code == "EV":
			self.events = add_pickup_to_bitfield(self.events, pickup, remove)
		if delay_put:
			return
		return self.put()
		
	
	def has_pickup(self, pickup):
		if pickup.code == "RB":
			pick_id = str(pickup.id)
			return self.bonuses[pick_id] if pick_id in self.bonuses else 0
		elif pickup.code == "SK":
			return get_bit(self.skills, pickup.bit)
		elif pickup.code == "TP":
			return get_bit(self.teleporters, pickup.bit)
		elif pickup.code == "EV":
			return get_bit(self.events, pickup.bit)
		else:
			return 0


class Game(ndb.Model):
	# id = Sync ID	
	DEFAULT_SHARED = [ShareType.DUNGEON_KEY, ShareType.SKILL, ShareType.UPGRADE, ShareType.EVENT, ShareType.TELEPORTER]
	mode = msgprop.EnumProperty(GameMode, required=True)
	shared = msgprop.EnumProperty(ShareType, repeated=True)
	start_time = ndb.DateTimeProperty(auto_now_add=True)
	last_update = ndb.DateTimeProperty(auto_now=True)
	players = ndb.KeyProperty(Player,repeated=True)
	
	@staticmethod
	def with_id(id):
		return Game.get_by_id(int(id))
	
	def summary(self):
		out_lines = ["%s (%s)" %( self.mode, ",".join([s.name for s in self.shared]))]
		if self.mode in [GameMode.SHARED, GameMode.SIMUSOLO] and len(self.players):
			src = self.players[0].get()
			for (field, cls) in [("skills", Skill), ("upgrades", Upgrade), ("teleporters", Teleporter), ("events",Event)]:
				bitmap = getattr(src,field)
				names = []
				for id,bit in cls.bits.iteritems():
					i = cls(id)
					if i:
						if i.stacks:
							cnt = get_taste(bitmap,i.bit)
							if cnt>0:
								names.append("%sx %s" %(cnt, i.name))
						elif get_bit(bitmap,i.bit):
							names.append(i.name)
				out_lines.append("%s: %s" % (field, ", ".join(names)))
		return "\n\t"+"\n\t".join(out_lines)
	
	def get_players(self):
		return [p.get() for p in self.players]

	def remove_player(self, key):
		key = ndb.Key(Player, key)
		self.players.remove(key)
		key.delete()
		self.put()
		
	def sanity_check(self):
		if self.mode != GameMode.SHARED:
			return
		if not Cache.canSanCheck(self.key.id()):
			print "WARNING: Skipping sanity check."
			return
		Cache.doSanCheck(self.key.id())
		players = self.get_players()
		hls = [hl for player in players for hl in player.history if hl.pickup().share_type in self.shared]
		inv = defaultdict(lambda : 0)
		for hl in hls:
			inv[(hl.pickup_code,hl.pickup_id)] += -1 if hl.removed else 1
		
		for key, count in inv.iteritems():
			pickup = Pickup.n(key[0], key[1])
			for player in players:
				has = player.has_pickup(pickup)
				if has < count:
					if has == 0 and count == 1:
						print "ERROR: Player %s should have %s but did not. Fixing..." % (player.key.id(), pickup.name)
					else: 
						print "ERROR: Player %s should have had %s of %s but had %s instead. Fixing..." % (player.key.id(), count, pickup.name, has)
					while(player.has_pickup(pickup) < count):
						player.give_pickup(pickup, delay_put=True)
				elif has > count:
					print "ERROR: Player %s has too many %s! Fixing..." % (player.key.id(), pickup.name)
					while(player.has_pickup(pickup) > count):
						player.give_pickup(pickup, remove=True, delay_put=True)
		
		[player.put() for player in players]
		

	def player(self, pid):
		full_pid = "%s.%s" % (self.key.id(), pid)
		player = Player.get_by_id(full_pid)
		if not player:
			if(self.mode == GameMode.SHARED and len(self.players)):
				src = self.players[0].get()
				player = Player(id=full_pid, skills = src.skills, events = src.events, upgrades = src.upgrades, teleporters = src.teleporters,bonuses = src.bonuses, history=[], signals=[])
			else:
				player = Player(id=full_pid, skills = 0, events=0, upgrades = 0, teleporters = 0, history=[])
			k = player.put()
			Cache.setHist(self.key.id(), pid, [])
			if k not in self.players:
				self.players.append(k)
				self.put()
		return player

	def found_pickup(self, pid, pickup, coords, remove, dedup):
		retcode = 200
		share = pickup.share_type in self.shared
		finder = self.player(pid)
		if share and dedup and coords in [h.coords for h in finder.history]:
			retcode = 410
			print "ERROR: Duplicate pickup at location %s from player %s" % (coords,  pid)
		elif self.mode == GameMode.SHARED:
			if not share:
				retcode = 406
			else:
				for player in self.get_players():
					if player.key.id() != finder.key.id():
						key = player.give_pickup(pickup, remove)
				finder.give_pickup(pickup, remove)

		elif self.mode == GameMode.SPLITSHARDS:
			if pickup.code != "RB" or pickup.id not in [17, 19, 21]:
				retcode = 406
			else:
				my_shards = len([h.coords for h in finder.history if h.pickup_code == "RB" and int(h.pickup_id) == pickup.id])
				if my_shards < 3:
					shard_locs = [h.coords for player in self.players for h in player.get().history if h.pickup_code == "RB" and h.pickup_id in ["17", "19", "21"]]
					if coords in shard_locs:
						retcode = 410
		elif self.mode == GameMode.SIMUSOLO:
			pass
		else:
			print "ERROR: game mode %s not implemented" % self.mode
			retcode = 404
		if retcode != 410: #410 GONE aka "haha nope"
			finder.history.append(HistoryLine(pickup_code = pickup.code, timestamp = datetime.now(), pickup_id = str(pickup.id), coords = coords, removed = remove))
			finder.put()
			Cache.setHist(self.key.id(), pid, finder.history)
		return retcode

def delete_game(game):
	[p.delete() for p in game.players]
	Cache.removeGame(game.key.id())
	game.key.delete()

def clean_old_games(timeout_window = timedelta(hours=12)):
	old = [game for game in Game.query(Game.last_update < datetime.now() - timeout_window)]	
	return len([delete_game(game) for game in old])

def get_open_gid():
	id = 1
	game_ids = set([int(game.key.id()) for game in Game.query()])
	while id in game_ids:
		id += 1
	if id > 20:
		clean_old_games()
	return id

	
def get_new_game(_mode = None, _shared = None, id=None):
	shared = [share_map[i] for i in _shared if i in share_map] if _shared else Game.DEFAULT_SHARED
	mode = GameMode(int(_mode)) if _mode else GameMode.SHARED
	id = int(id) if id else get_open_gid()
	game = Game(id = id, players=[], shared=shared, mode=mode)
	return game


coord_correction_map = {
	679620: 719620,
	-4560020: -4600020,
	-520160: -560160,
#	-4199936: -4600020, Past me WHY, WHY DID YOU DO THIS
	8599908: 8599904,
	2959744: 2919744, 
}
	
class Pickup(object):
	@staticmethod
	def subclasses():
		return [Skill, Event, Teleporter, Upgrade, Experience, AbilityCell, HealthCell, EnergyCell, Keystone, Mapstone, Message]
	
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
	bits = {"Grove":1, "Swamp":2, "Grotto":4, "Valley":8, "Forlorn":16, "Sorrow":32, "Lost": 64}
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
	name_only = set([0, 1, 2])
	maxes = {17: 3, 19: 3, 21: 3}
	names = {17:  "Water Vein Shard", 19: "Gumon Seal Shard", 21: "Sunstone Shard", 6: "Spirit Flame Upgrade", 13: "Health Regeneration", 2: "Go Home",
			15: "Energy Regeneration", 8: "Explosion Power Upgrade", 9:  "Spirit Light Efficiency", 10: "Extra Air Dash", 1:  "Charge Dash Efficiency", 
			12: "Extra Double Jump", 0: "Mega Health", 1: "Mega Energy", 30: "Bleeding", 31: "Lifesteal", 32: "Manavamp", 33: "Skill Velocity Upgrade",
			101: "Polarity Shift", 102: "Gravity Swap", 103: "Drag Racer", 104: "Airbrake"}
	bits = {17:1, 19:4, 21:16, 6:64, 13:256, 15:1024, 8:4096, 9:8192, 10:16384, 11:32768, 12:65536}
	code = "RB"
	def __new__(cls, id):
		id = int(id)
		if id in Upgrade.name_only:
			inst = super(Upgrade, cls).__new__(cls)
			inst.id, inst.share_type, inst.name = id, ShareType.NOT_SHARED, Upgrade.names[id]
			return inst
		if id not in Upgrade.names:
			return None
		inst = super(Upgrade, cls).__new__(cls)
		inst.id, inst.name = id, Upgrade.names[id]
		inst.bit = Upgrade.bits[id] if id in Upgrade.bits else -1
		inst.max = Upgrade.maxes[id] if id in Upgrade.maxes else None

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

class Message(Pickup):
	code = "SH"
	def __new__(cls, id):
		inst = super(Message, cls).__new__(cls)
		inst.id, inst.bit, inst.name = id,None, id + "Message: "
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


all_locs = set([0, 2999808, 4, 5280264, -4159572, 12, 16, 4479832, 4559492, 919772, -3360288, 24, -8400124, 28, 32, 1599920, -6479528, 36, 40, 3359580, 2759624, 44, 4959628, 4919600, 3279920, -12320248, 1479880, 52, 56, 3160244, 960128, 799804, -6159632, -800192, 
				5119584, 5719620, -6279608, -3160308, 5320824, 4479568, 9119928, -319852, 1719892, -480168, 919908, 1519708, 20, -6079672, 2999904, -6799732, -11040068, 5360732, 559720, 4039612, 4439632, 1480360, -2919980, -120208, -2480280, 4319860, -7040392, 
				-1800088, -4680068, 4599508, 2919744, 3319936, 1720000, 120164, -4600188, 5320328, 6999916, 3399820, 1920384, -400240, -6959592, 4319892, 2239640, 2719900, -160096, 3559792, 1759964, -5160280, 6359836, 5080496, 5359824, 1959768, 5039560, 4560564, 
				-10440008, 2519668, -2240084, -10760004, -4879680, 799776, -5640092, -6080316, 6279880, 4239780, -5119796, 7599824, 5919864, -4160080, 4999892, 3359784, 4479704, -1800156, -6280316, -5719844, -8600356, -2160176, 5399780, -6119704, 5639752, 3439744, 
				7959788, 5080304, 5320488, -10120036, -7960144, -1680140, 8, -8920328, 1839836, 2520192, 1799708, 5399808, -8720256, 639888, 719620, 6639952, 3919624, -4600020, 5200140, 39756, 2480400, 959960, 6839792, -1680104, -8880252, 5320660, 3279644, -6719712, 
				48, 599844, -3600088, 8839900, 4199724, 3039472, -4559584, -1560272, 1600136, 4759860, 5280500, 2559800, 3119768, 6159900, 5879616, -10759968, 5280296, 3919688, -2080116, 5119900, 3199820, 2079568, -5400236, -4199936, -8240012, -5479592, -3200164, 
				8599904, -5039728, 7839588, -5159576, 4079964, -1840196, 7679852, 5400100, -7680144, -6720040, -5919556, 1880164, -3559936, -6319752, 5280404, 39804, 6399872, -280256, -9799980, 1280164, -1560188, -2200184, 6080608, -1919808, 4639628, 7639816, -6800032,
				5160336, 3879576, 4199828, 3959588, 5119556, 5400276, -1840228, 5160864, 1040112, 4680612, -11880100, -4440152, -3520100, 7199904, -2200148, 7559600, -10839992, 5040476, -8160268, 4319676, 5160384, 5239456, -2400212, 2599880, 3519820, -9120036, 
				3639880, -6119656, 3039696, 1240020, -5159700, -4359680, -5400104, -5959772, 5439640, -8440352, 3639888, -2480208, 399844, -560160, 4359656, -4799416, 8719856, -6039640, -5479948, 5519856, 6199596, -4600256, -2840236, 5799932, -600244, 5360432])


def get_bit(bits_int, bit):
	return int_to_bits(bits_int, log_2[bit]+1)[-(1+log_2[bit])]

def get_taste(bits_int, bit):
	bits = int_to_bits(bits_int,log_2[bit]+2)[-(2+log_2[bit]):][:2]
	return 2*bits[0]+bits[1]

def add_pickup_to_bitfield(bits_int, pickup, remove=False):
	if pickup.stacks:
		return inc_stackable(bits_int, pickup.bit, remove)
	return add_single(bits_int, pickup.bit, remove)


def add_single(bits_int, bit, remove=False):
	if bit<0:
		return bits_int
	if bits_int >= bit:
		if remove:
			return bits_int-bit
		if get_bit(bits_int, bit) == 1:
			return bits_int
	return bits_int + bit

def inc_stackable(bits_int, bit, remove=False):
	if bit<0:
		return bits_int
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

def dll_last_update():
	if os.environ.get('SERVER_SOFTWARE', '').startswith('Dev'):
		return "N/A"
	from github import Github
	# hidiously bad practice but the token only has read rights so w/eeeeee
	return Github("d060d7ef01443cdf653" + "" + "eb2e9ae7b66f37313b769").get_repo(124633989).get_commits(path="Assembly-CSharp.dll")[0].commit.last_modified