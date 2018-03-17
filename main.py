#haha this is garbage sorry

import webapp2
import random
import pickle
from math import floor
from datetime import datetime, timedelta
from protorpc import messages
from google.appengine.ext import ndb
from google.appengine.ext.ndb import msgprop
from seedbuilder.generator import placeItems
from seedbuilder.splitter import split_seed
from abc import ABCMeta, abstractproperty
from operator import attrgetter
base_site = "http://orirandocoopserver.appspot.com"
cd ..
def int_to_bits(n, min_len=2):
	raw = [1 if digit=='1' else 0 for digit in bin(n)[2:]]
	if len(raw) < min_len:
		raw = [0]*(min_len-len(raw))+raw
	return raw

def bits_to_int(n):
	return int("".join([str(b) for b in n]),2)

class GameMode(messages.Enum):
	SHARED = 1
	SWAPPED = 2				#not implemented, needs client work
	SPLITSHARDS = 3


class ShareType(messages.Enum):
	DUNGEON_KEY = 1
	UPGRADE = 2
	SKILL = 3
	EVENT = 4
	TELEPORTER = 5
def share_from_url(s):
	if s == "keys":
		return ShareType.DUNGEON_KEY
	if s == "upgrades":
		return ShareType.UPGRADE
	if s == "skills":
		return ShareType.SKILL
	if s == "events":
		return ShareType.EVENT
	if s == "teleporters":
		return ShareType.TELEPORTER

class Pickup(object):
	stacks = False
	def __eq__(self, other):
		return isinstance(other, Pickup) and self.id == other.id
	@classmethod
	def n(cls, code, id):
		for subcls in [Skill, Event, Teleporter, Upgrade]:
			if code == subcls.code:
				return subcls(id)
		return None

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
		inst.id, inst.bit, inst.name = id, Teleporter.bits[id], id
		inst.share_type = ShareType.TELEPORTER
		return inst

class Upgrade(Pickup):
	stacking= set([6,13,15,17,19,21])
	names = {17:  "Water Vein Shard", 19: "Gumon Seal Shard", 21: "Sunstone Shard", 6: "Spirit Flame Upgrade", 13: "Health Regeneration", 15: "Energy Regeneration", 8: "Explosion Power Upgrade", 9:  "Spirit Light Efficiency", 10: "Extra Air Dash", 11:  "Charge Dash Efficiency", 12:  "Extra Double Jump"}
	bits = {17:1, 19:4, 21:16, 6:64, 13:256, 15:1024, 8:4096, 9:8192, 10:16384, 11:32768, 12:65536}
	code = "RB"
	def __new__(cls, id):
		id = int(id)
		if id not in Upgrade.bits or id not in Upgrade.names:
			return None
		inst = super(Upgrade, cls).__new__(cls)
		inst.id, inst.bit, inst.name = id, Upgrade.bits[id], Upgrade.names[id]
		inst.stacks = id in Upgrade.stacking
		inst.share_type = ShareType.DUNGEON_KEY if id in [17, 19, 21] else ShareType.UPGRADE
		return inst

disabled_upgrades = set([])
teleporters_enabled = True
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
	return int(4*floor(abs(float(x)/4))*sign(x))

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


def _pickup_name(hl):
	p = Pickup.n(hl.pickup_code, hl.pickup_id)
	return p.name if p else "%s|%s" % (hl.pickup_code, hl.pickup_id)

class HistoryLine(ndb.Model):
	pickup_code = ndb.StringProperty()
	pickup_id = ndb.StringProperty()
	timestamp = ndb.DateTimeProperty(auto_now_add=True)
	removed = ndb.BooleanProperty()
	coords = ndb.IntegerProperty()
	pickup_name = ndb.ComputedProperty(lambda self: _pickup_name(self))
	def print_line (self,start_time=None):
		t = (self.timestamp - start_time) if start_time else self.timestamp
		if not self.removed:
			coords = unpack(self.coords)
			coords = special_coords[coords] if coords in special_coords else "(%s, %s)" % coords
			return "found %s at %s. (%s)" % (self.pickup_name, coords, t)
		else:
			return "lost %s! (%s)" % (self.pickup_name, t)

class Player(ndb.Model):
	skills	  = ndb.IntegerProperty()
	events	  = ndb.IntegerProperty()
	upgrades	= ndb.IntegerProperty()
	teleporters = ndb.IntegerProperty()
	signals = ndb.StringProperty(repeated=True)
	history = ndb.StructuredProperty(HistoryLine, repeated=True)

class Game(ndb.Model):
	# id = Sync ID
	DEFAULT_SHARED = [ShareType.DUNGEON_KEY, ShareType.SKILL, ShareType.UPGRADE, ShareType.EVENT]
	mode = msgprop.EnumProperty(GameMode, required=True)
	shared = msgprop.EnumProperty(ShareType, repeated=True)
	start_time = ndb.DateTimeProperty(auto_now_add=True)
	last_update = ndb.DateTimeProperty(auto_now=True)
	players = ndb.KeyProperty(Player,repeated=True)
	def summary(self):
		out_lines = ["%s (%s)" %( self.mode, ",".join([s.name for s in self.shared]))]
		if self.mode == GameMode.SHARED and len(self.players):
			src = self.players[0].get()
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

	def player(self, pid):
		key = "%s.%s" % (self.key.id(), pid)
		player = Player.get_by_id(key)
		if not player:
			if(self.mode == GameMode.SHARED and len(self.players)):
				src = self.players[0].get()
				player = Player(id=key, skills = src.skills, events = src.events, upgrades = src.upgrades, teleporters = src.teleporters, history=[], signals=[])
			else:
				player = Player(id=key, skills = 0, events=0, upgrades = 0, teleporters = 0, history=[])
				k = player.put()
				self.players.append(k)
				self.put()
		return player

	def found_pickup(self, finder, pickup, coords, remove=False):
		retcode = 200
		player = self.player(finder)
		if (pickup.share_type not in self.shared):
			retcode = 406
		elif (self.mode == GameMode.SHARED):
			for pkey in self.players:
				player = pkey.get()
				for (field, cls) in [("skills", Skill), ("upgrades", Upgrade), ("teleporters", Teleporter), ("events",Event)]:
					if isinstance(pickup, cls):
						if pickup.stacks:
							setattr(player,field,inc_stackable(getattr(player,field), pickup.bit, remove))
						else:
							setattr(player,field,add_single(getattr(player,field), pickup.bit, remove))
		elif self.mode == GameMode.SPLITSHARDS:
			shard_locs = [h.coords for player in self.players for h in player.get().history if h.pickup_code == "RB" and h.pickup_id in ["17", "19", "21"]]
			if coords in shard_locs:
				retcode = 410
		else:
			print "game mode not implemented"
			retcode = 404
		if retcode != 410: #410 GONE aka "haha nope"
			player.history.append(HistoryLine(pickup_code = pickup.code, pickup_id = str(pickup.id), coords = coords, removed = remove))
			player.put()
		return retcode

def clean_old_games():
	old = [game for game in Game.query(Game.last_update < datetime.now() - timedelta(hours=1))]
	[p.delete() for game in old for p in game.players]
	return len([game.key.delete() for game in old])

def get_game(game_id):
	return Game.get_by_id(int(game_id))

def get_new_game(_mode = None, _shared = None, id=None):
	shared = [share_from_url(i) for i in _shared.split(" ")] if _shared else Game.DEFAULT_SHARED
	mode = GameMode(int(_mode)) if _mode else GameMode.SHARED
	game_id = id.split(".")[0] if id else 1
	game_ids = set([game.key.id() for game in Game.query()])
	while game_id in game_ids:
		game_id += 1
	if game_id > 100:
		clean_old_games()
	game = Game(id = int(game_id), players=[], shared=shared, mode=mode)
	game_id = game.put()
	return game_id.id()

class GetGameId(webapp2.RequestHandler):
	def get(self):
		self.response.headers['Content-Type'] = 'text/plain'
		self.response.status = 200
		self.response.write("GC|%s.1" % get_new_game(paramVal(self, 'mode'), paramVal(self, 'shared'), paramVal(self, 'id')))

class CleanUp(webapp2.RequestHandler):
	def get(self):
		self.response.headers['Content-Type'] = 'text/plain'
		self.response.write("Cleaned up %s games" % clean_old_games())



class ActiveGames(webapp2.RequestHandler):
	def get(self):
		self.response.headers['Content-Type'] = 'text/html'
		self.response.write('<html><body><pre>Active games:\n' +
			"\n".join(
				["<a href='/%s/history'>Game #%s</a>:\n\t%s " % (game.key.id(), game.key.id(),game.summary()) for game in Game.query()])+"</pre></body></html>")

def paramFlag(s,f):
	return s.request.get(f,None) != None
def paramVal(s,f):
	return s.request.get(f,None)

class FoundPickup(webapp2.RequestHandler):
	def get(self, game_id, player_id, coords, kind, id):
		remove = paramFlag(self,"remove")
		coords = int(coords)
		game = get_game(game_id)

		if not remove and not paramFlag(self, "override") and coords in [ h.coords for h in game.player(player_id).history]:
			self.response.status = 410
			self.response.write("Duplicate pickup at location %s from player %s" % (coords,  player_id))
			return


		pickup = Pickup.n(kind, id)
		if not pickup:
			self.response.status = 406
			self.response.write("Pickup %s|%s not tracked" % (kind,id))
			return

		if paramFlag(self,"log_only"):
			self.response.status = 200
			self.response.write("logged")
			return


		self.response.status = game.found_pickup(player_id, pickup, coords, remove)
		game.put()
		self.response.write(self.response.status)

class ListPickups(webapp2.RequestHandler):
	def get(self, game_id, player_id):
		self.response.headers['Content-Type'] = 'text/plain'
		game = get_game(game_id)
		if not game:
			self.response.status = 412
			self.response.write(self.response.status)
			return
		p = game.player(player_id)
		self.response.write(",".join([str(x) for x in [p.skills,p.events,p.upgrades,p.teleporters]+(["|".join(p.signals)] if p.signals else [])]))


class ShowHistory(webapp2.RequestHandler):
	def get(self, game_id):
		self.response.headers['Content-Type'] = 'text/plain'
		game = get_game(game_id)
		output = game.summary()
		output += "\nHistory:"
		for hl,pid in sorted([(h,p.id().partition('.')[2]) for p in game.players for h in p.get().history], key=lambda x: x[0].timestamp, reverse=True):
			output += "\n\t\t Player %s %s" % (pid, hl.print_line(game.start_time))

		self.response.status = 200
		self.response.write(output)



class SeedGenerator(webapp2.RequestHandler):
	def get(self):
		self.response.out.write("""
		  <html>
			<body>
			<div><a href="https://github.com/turntekGodhead/OriDERandomizer/raw/master/Assembly-CSharp.dll">latest dll</a></div>
			<div><a href="/activeGames">Games list</a></div>
			<form action="/" method="post">
			<table class="main" cellspacing="0" cellpadding="0"><tbody><tr><td align="center" style="vertical-align: top;"><table cellspacing="0" cellpadding="0"><tbody><tr><td align="left" style="vertical-align: top;"><div class="title" style="white-space: normal;">Ori DE Randomizer (v2.1.0)</div></td></tr></tbody></table></td></tr><tr>
			<td align="center" style="vertical-align: top;"><table class="row" cellspacing="0" cellpadding="0"><tbody><tr><td align="left" style="vertical-align: top;">
			<td align="left" style="vertical-align: top;"><table class="inner_row" cellspacing="0" cellpadding="0"><tbody><tr><td align="left" style="vertical-align: top;">
			<div class="label" style="white-space: normal;">Mode</div></td><td align="left" style="vertical-align: top;">

			<select size="1" class="dropdown" name="mode"><option>Default</option><option selected="Selected">Shards</option><option>Limitkeys</option><option>Clues</option></select>

			</td></tr></tbody></table></td>

			<td align="left" style="vertical-align: top;"><table class="inner_row" cellspacing="0" cellpadding="0"><tbody><tr><td align="left" style="vertical-align: top;"><div class="label" style="white-space: normal;">Path Difficulty</div></td><td align="left" style="vertical-align: top;">

			<select size="1" class="dropdown" name="pathdiff"><option>Easy</option><option selected="Selected">Normal</option><option>Hard</option></select>

			</td></tr></tbody></table></td></tr></tbody></table></td></tr><tr>
			<td align="center" style="vertical-align: top;"><table class="row" cellspacing="0" cellpadding="0"><tbody><tr><td align="left" style="vertical-align: top;"><div class="section" style="white-space: normal;">Variations</div></td></tr><tr><td align="left" style="vertical-align: top;">
			<table cellspacing="0" cellpadding="0"><tbody><tr><td align="left" style="vertical-align: top;"><table class="var_column" cellspacing="0" cellpadding="0"><tbody><tr><td align="left" style="vertical-align: top;">

			<span class="gwt-CheckBox"><input type="checkbox" name="forcetrees" checked=""><label for="check1">Force Trees</label></span></td></tr><tr><td align="left" style="vertical-align: top;">
			<span class="gwt-CheckBox"><input type="checkbox" name="hardmode"><label for="check2">Hard Mode</label></span></td></tr><tr><td align="left" style="vertical-align: top;">
			<span class="gwt-CheckBox"><input type="checkbox" name="notp"><label for="check3">No Teleporters</label></span></td></tr></tbody></table></td><td align="left" style="vertical-align: top;">

			<table class="var_column" cellspacing="0" cellpadding="0"><tbody><tr><td align="left" style="vertical-align: top;">

			<span class="gwt-CheckBox"><input type="checkbox" name="starved"><label for="check4">Starved</label></span></td></tr><tr><td align="left" style="vertical-align: top;">
			<span class="gwt-CheckBox"><input type="checkbox" name="ohko"><label for="check5">OHKO</label></span></td></tr><tr><td align="left" style="vertical-align: top;">
			<span class="gwt-CheckBox"><input type="checkbox" name="noplants"><label for="check6">No Plants</label></span></td></tr></tbody></table></td>

			<td align="left" style="vertical-align: top;"><table class="var_column" cellspacing="0" cellpadding="0"><tbody><tr><td align="left" style="vertical-align: top;">

			<span class="gwt-CheckBox"><input type="checkbox" name="discmaps"><label for="check7">Discrete Mapstones</label></span></td></tr><tr><td align="left" style="vertical-align: top;">
			<span class="gwt-CheckBox"><input type="checkbox" name="0xp"><label for="check8">0 XP</label></span></td></tr><tr><td align="left" style="vertical-align: top;">
			<span class="gwt-CheckBox"><input type="checkbox" name="nobonus"><label for="check9">No Bonuses</label></span></td></tr></tbody></table></td></tr></tbody></table></td></tr></tbody></table></td></tr>

			<tr><td align="center" style="vertical-align: top;"><table cellspacing="0" cellpadding="0" class="row open"><tbody><tr><td align="left" style="vertical-align: top;"><table><tbody><tr><td></td><td>Logic Paths</td></tr></tbody></table></a></td></tr><tr><td align="left" style="vertical-align: top;"><div style="padding: 0px; overflow: hidden;"><table cellspacing="0" cellpadding="0" class=" content"><tbody><tr><td align="left" style="vertical-align: top;"><table class="logic_column" cellspacing="0" cellpadding="0"><tbody><tr><td align="left" style="vertical-align: top;">
			<span class="gwt-CheckBox"><input type="checkbox" name="normal" checked=""><label for="check10">Normal</label></span></td></tr><tr><td align="left" style="vertical-align: top;">
			<span class="gwt-CheckBox"><input type="checkbox" name="lure" checked=""><label for="check11">Lure</label></span></td></tr><tr><td align="left" style="vertical-align: top;">
			<span class="gwt-CheckBox"><input type="checkbox" name="extended"><label for="check12">Extended</label></span></td></tr><tr><td align="left" style="vertical-align: top;">
			<span class="gwt-CheckBox"><input type="checkbox" name="extreme"><label for="check13">Extreme</label></span></td></tr></tbody></table></td><td align="left" style="vertical-align: top;"><table class="logic_column" cellspacing="0" cellpadding="0"><tbody><tr><td align="left" style="vertical-align: top;">
			<span class="gwt-CheckBox"><input type="checkbox" name="speed" checked=""><label for="check14">Speed</label></span></td></tr><tr><td align="left" style="vertical-align: top;">
			<span class="gwt-CheckBox"><input type="checkbox" name="speed-lure"><label for="check15">Speed-Lure</label></span></td></tr><tr><td align="left" style="vertical-align: top;">
			<span class="gwt-CheckBox"><input type="checkbox" name="extended-damage"><label for="check16">Extended-Damage</label></span></td></tr><tr><td align="left" style="vertical-align: top;">
			<span class="gwt-CheckBox"><input type="checkbox" name="timed-level"><label for="check17">Timed-Level</label></span></td></tr></tbody></table></td><td align="left" style="vertical-align: top;"><table class="logic_column" cellspacing="0" cellpadding="0"><tbody><tr><td align="left" style="vertical-align: top;">
			<span class="gwt-CheckBox"><input type="checkbox" name="dboost-light" checked=""><label for="check18">DBoost-Light</label></span></td></tr><tr><td align="left" style="vertical-align: top;">
			<span class="gwt-CheckBox"><input type="checkbox" name="lure-hard"><label for="check19">Lure-Hard</label></span></td></tr><tr><td align="left" style="vertical-align: top;">
			<span class="gwt-CheckBox"><input type="checkbox" name="dbash"><label for="check20">DBash</label></span></td></tr><tr><td align="left" style="vertical-align: top;">
			<span class="gwt-CheckBox"><input type="checkbox" name="glitched"><label for="check21">Glitched</label></span></td></tr></tbody></table></td><td align="left" style="vertical-align: top;"><table class="logic_column" cellspacing="0" cellpadding="0"><tbody><tr><td align="left" style="vertical-align: top;">
			<span class="gwt-CheckBox"><input type="checkbox" name="dboost"><label for="check22">DBoost</label></span></td></tr><tr><td align="left" style="vertical-align: top;">
			<span class="gwt-CheckBox"><input type="checkbox" name="dboost-hard"><label for="check23">DBoost-Hard</label></span></td></tr><tr><td align="left" style="vertical-align: top;">
			<span class="gwt-CheckBox"><input type="checkbox" name="cdash"><label for="check24">CDash</label></span></td></tr><tr><td align="left" style="vertical-align: top;">
			<span class="gwt-CheckBox"><input type="checkbox" name="cdash-farming"><label for="check25">CDash-Farming</label></span></td></tr></tbody></table></td><td align="left" style="vertical-align: top;"><table class="logic_column" cellspacing="0" cellpadding="0"><tbody><tr><td align="left" style="vertical-align: top;">
			<span class="gwt-CheckBox"><input type="checkbox" name="sk" checked=""><label for="check22">Split: Skills</label></span></td></tr><tr><td align="left" style="vertical-align: top;">
			<span class="gwt-CheckBox"><input type="checkbox" name="ev" checked=""><label for="check23">Split:World Events</label></span></td></tr><tr><td align="left" style="vertical-align: top;">
			<span class="gwt-CheckBox"><input type="checkbox" name="rb" checked=""><label for="check24">Split: Bonuses</label></span></td></tr><tr><td align="left" style="vertical-align: top;">
			<span class="gwt-CheckBox"><input type="checkbox" name="hot" checked=""><label for="check25">Split: Hot</label></span></td></tr><table class="logic_column" cellspacing="0" cellpadding="0">

			</tbody></table></td></tr></tbody></table></div></td></tr></tbody></table></td></tr><tr>

			<tr><td align="center" style="vertical-align: top;"><table class="row" cellspacing="2" cellpadding="2"><tbody><tr><td align="left" style="vertical-align: top;">
			<table cellspacing="2" cellpadding="2"><tbody><tr><td align="left" style="vertical-align: top;"><div class="label" style="white-space: normal;"># of players</div></td><td align="left" style="vertical-align: top;">

			<input name="playerCount" type="number" value="2" /></div></td></button></td></tr></tbody></table></td></tr>
			<td align="center" style="vertical-align: top;"><table class="row" cellspacing="2" cellpadding="2"><tbody><tr><td align="left" style="vertical-align: top;">
			<table cellspacing="2" cellpadding="2"><tbody><tr><td align="left" style="vertical-align: top;"><div  class="label" style="white-space: normal;">Seed</div></td><td align="left" style="vertical-align: top;">
			<input type="text" name="seed"></td></tr></tbody></table></td><td align="left" style="vertical-align: top;"><input class="button" type="submit" text="Generate"></button></td></tr></tbody></table></td></tr></tbody></table>
			  </form>
			</body>
		  </html>""")

	def post(self):
		mode = self.request.get("mode").lower()
		pathdiff = self.request.get("pathdiff").lower()
		variations = set([x for x in ["forcetrees", "hardmode", "notp", "starved", "ohko", "noplants", "discmaps", "0xp", "nobonus"] if self.request.get(x)])
		logic_paths = [x for x in ["normal", "speed", "lure", "speed-lure", "dboost", "dboost-light", "dboost-hard", "cdash", "dbash", "extended", "lure-hard", "timed-level", "glitched", "extended-damage", "extreme"] if self.request.get(x)]
		playercount = self.request.get("playerCount")
		seed = self.request.get("seed")
		if not seed:
			seed = str(random.randint(10000000,100000000))

		urlargs = ["m=%s" % mode]
		urlargs.append("vars=%s" % "|".join(variations))
		urlargs.append("lps=%s" % "|".join(logic_paths))
		urlargs.append("s=%s" % seed)
		urlargs.append("pc=%s" % playercount)
		urlargs.append("pd=%s" % pathdiff)
		for flg in ["ev", "sk", "rb", "hot"]:
			if self.request.get(flg):
				urlargs.append("%s=1" % flg)
		self.response.headers['Content-Type'] = 'text/html'
		out = "<html><body>"
		url = '/getseed?%s' % "&".join(urlargs)
		out += "<div><a target='_blank' href='%s&p=spoiler'>Spoiler</a></div>" % url
		for i in range(1,1+int(playercount)):
			purl = url+"&p=%s" % i
			out += "<div>Player %s: <a target='_blank' href=%s>%s%s</a></div>" % (i, purl , base_site, purl )
		out += "</body></html>"
		self.response.out.write(out)

class SeedDownloader(webapp2.RequestHandler):
	def get(self):
		params = self.request.GET
		mode = params['m']
		variations = params['vars'].split("|")
		logic_paths = params['lps'].split("|")
		seed = params['s']
		playercount = int(params['pc'])
		pathdiff = params['pd']
		player = params['p']

		seed_num = sum([ord(c) * i for c,i in zip(seed, range(len(seed)))])
		if pathdiff == "normal":
			pathdiff == None
		varFlags = {"starved":"starved", "hardmode":"hard","ohko":"OHKO","0xp":"0XP","nobonus":"NoBonus","noplants": "NoPlants", "forcetrees" : "ForceTrees", "discmaps" : "NonProgressMapStones",  "notp" : "NoTeleporters"}
		flags = ["Custom"]
		if mode != "default":
			flags.append(mode)
		if pathdiff:
			flags.append("prefer_path_difficulty=" + pathdiff)
		for v in variations:
			flags.append(varFlags[v])

		flag = ",".join(flags)
		out = ""
		placement = placeItems(seed, 10000,
				"hardmode" in variations,
				"noplants" not in variations,
				mode == "shards",
				mode == "limitkeys",
				mode == "clues",
				"notp" not in variations,
				False, False,
				logic_paths, flag,
				"starved" in variations,
				pathdiff,
				"discmaps" in variations)
		if player == "spoiler":
			self.response.headers['Content-Type'] = 'text/plain'
			self.response.out.write(placement[1])
			return
		player = int(player)
		game_id = get_new_game()
		ss = split_seed(placement[0], game_id, player, playercount, "hot" in params, "sk" in params, "ev" in params, "rb" in params)
		self.response.headers['Content-Type'] = 'application/x-gzip'
		self.response.headers['Content-Disposition'] = 'attachment; filename=randomizer.dat'
		self.response.out.write(ss)

class SignalCallback(webapp2.RequestHandler):
	def get(self, game_id, player_id, signal):
		self.response.headers['Content-Type'] = 'text/plain'
		game = get_game(game_id)
		if not game:
			self.response.status = 412
			self.response.write(self.response.status)
			return
		p = game.player(player_id)
		p.signals.remove(signal)
		p.put()
		self.response.status = 200
		self.response.write("cleared")

class HistPrompt(webapp2.RequestHandler):
	def get(self, game_id):
		self.response.headers['Content-Type'] = 'text/html'
		self.response.status = 412
		self.response.write("<html><body><a href='%s/history'>go here</a></body></html>" % game_id)
		return


class SignalSend(webapp2.RequestHandler):
	def get(self, game_id, player_id, signal):
		self.response.headers['Content-Type'] = 'text/plain'
		game = get_game(game_id)
		if not game:
			self.response.status = 412
			self.response.write(self.response.status)
			return
		p = game.player(player_id)
		p.signals.append(signal)
		p.put()
		self.response.status = 200
		self.response.write("sent")



app = webapp2.WSGIApplication([
	('/', SeedGenerator),
	('/activeGames', ActiveGames),
	('/clean', CleanUp),
	('/getseed', SeedDownloader),
	('/getNewGame', GetGameId),
	(r'/(\d+)', HistPrompt),
	(r'/(\d+)\.(\w+)/(-?\d+)/(\w+)/(\w+)', FoundPickup),
	(r'/(\d+)\.(\w+)', ListPickups),
	(r'/(\d+)\.(\w+)/SECRET/(\w+)', SignalSend),
	(r'/(\d+)\.(\w+)/signalCallback/(\w+)', SignalCallback),
	(r'/(\d+)/history', ShowHistory)
], debug=True)

