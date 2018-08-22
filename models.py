from google.appengine.ext import ndb
from google.appengine.ext.ndb import msgprop

import logging as log

from datetime import datetime, timedelta
from collections import defaultdict
from itertools import ifilter
from seedbuilder.seedparams import SeedGenParams, Placement, Stuff
from seedbuilder.generator import SeedGenerator

from enums import NDB_MultiGameType, NDB_ShareType, MultiplayerGameType, ShareType
from util import special_coords, get_bit, get_taste, unpack, enums_from_strlist

from pickups import Pickup, Skill, Upgrade, Teleporter, Event 
from cache import Cache


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

	
class Seed(ndb.Model):
	# Seed ids are author
	placements = ndb.LocalStructuredProperty(Placement, repeated=True)
	flags = ndb.StringProperty(repeated=True)
	hidden = ndb.BooleanProperty(default=False)
	description = ndb.TextProperty()
	players = ndb.IntegerProperty(default=1)
	author = ndb.StringProperty()
	name = ndb.StringProperty()

	def mode(self):
		mode_opt = [MultiplayerGameType.mk(f[5:]) for f in self.flags if f.lower().startswith("mode=")]
		return mode_opt[0] if mode_opt else None

	def shared(self):
		shared_opt = [f[7:].replace("+"," ").split(" ") for f in self.flags if f.lower().startswith("shared=")]
		return enums_from_strlist(ShareType, shared_opt[0]) if shared_opt else []
	
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
	last_update = ndb.DateTimeProperty(auto_now=True)
	teammates = ndb.KeyProperty('Player',repeated=True)
	
	# post-refactor version of bitfields
	def output(self):
		outlines = [str(x) for x in [self.skills,self.events,self.teleporters]]
		outlines.append(";".join([str(id) + "x%s" % count for (id, count) in self.bonuses.iteritems()]))
		if self.signals:
			outlines.append("|".join(self.signals))
		return ",".join(outlines)
	
	def signal_send(self, signal):
		if signal not in self.signals:
			self.signals.append(signal)
			self.put()
	
	def signal_conf(self, signal):	
		if signal in self.signals:
			self.signals.remove(signal)
		elif signal.startswith("msg:"):
		# basically it is never ok to be spamming ppl, so if we get a message callback 
		# we remove the first message we find if we don't get an exact match.
			for s in self.signals:
				self.signals.remove(s)
				if s.startswith("msg:"):
					log.warning("No exact match for signal %s, removing %s instead (spam protection)" % (signal, s))
					break
		self.put()
	
	def give_pickup(self, pickup, remove=False, delay_put=False):
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
		
			self.upgrades = pickup.add_to_bitfield(self.upgrades, remove)
		elif pickup.code == "SK":
			self.skills = pickup.add_to_bitfield(self.skills, remove)
		elif pickup.code == "TP":
			self.teleporters = pickup.add_to_bitfield(self.teleporters, remove)
		elif pickup.code == "EV":
			self.events = pickup.add_to_bitfield(self.events, remove)
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
	DEFAULT_SHARED = [ShareType.DUNGEON_KEY, ShareType.SKILL, ShareType.EVENT, ShareType.TELEPORTER]

	ndb_mode = msgprop.EnumProperty(NDB_MultiGameType, required=True)
	ndb_shared = msgprop.EnumProperty(NDB_ShareType, repeated=True)
	
	def get_mode(self):			return MultiplayerGameType.from_ndb(self.ndb_mode)
	def set_mode(self, mode): 	self.ndb_mode = mode.to_ndb()
	mode = property(get_mode, set_mode)

	def get_shared(self):			return [ShareType.from_ndb(ndb_st) for ndb_st in self.ndb_shared]
	def set_shared(self, shared): 	self.ndb_shared = [s.to_ndb() for s in shared]
	shared = property(get_shared, set_shared)

	start_time = ndb.DateTimeProperty(auto_now_add=True)
	last_update = ndb.DateTimeProperty(auto_now=True)
	players = ndb.KeyProperty(Player,repeated=True)

		
	def summary(self):
		out_lines = ["%s (%s)" %( self.mode, ",".join([s.name for s in self.shared]))]
		if self.mode in [MultiplayerGameType.SHARED, MultiplayerGameType.SIMUSOLO] and len(self.players):
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
		# helper function, checks if a pickup stacks
		def stacks(pickup):
			if pickup.stacks:
				return True
			if pickup.code != "RB":
				return False
			return pickup.id in [6,12,13,15,17,19,21,28,30,31,32,33]

		if self.mode != MultiplayerGameType.SHARED:
			return
		if not Cache.canSanCheck(self.key.id()):
			log.warning("Skipping sanity check.")
			return
		Cache.doSanCheck(self.key.id())
		players = self.get_players()
		sanFailedSignal = "msg:@Major Error during sanity check. If this persists across multiple alt+l attempts please contact Eiko@"
		hls = [hl for player in players for hl in player.history if hl.pickup().share_type in self.shared]
		inv = defaultdict(lambda : 0)
		for hl in hls:
			inv[(hl.pickup_code,hl.pickup_id)] += -1 if hl.removed else 1
		i = 0
		for key, count in inv.iteritems():
			pickup = Pickup.n(key[0], key[1])
			if not stacks(pickup):
				count = 1
			elif pickup.max:
				count = min(count,pickup.max)
			for player in players:
				has = player.has_pickup(pickup)
				if has < count:
					if has == 0 and count == 1:
						log.error("Player %s should have %s but did not. Fixing..." % (player.key.id(), pickup.name))
					else: 
						log.error("Player %s should have had %s of %s but had %s instead. Fixing..." % (player.key.id(), count, pickup.name, has))
					while(has < count):
						i += 1
						last = has
						player.give_pickup(pickup, delay_put=True)
						has = player.has_pickup(pickup)
						if has == last:
							log.critical("Aborting sanity check for Player %s: tried and failed to increment %s (at %s, should be %s)" % (player.key.id(), pickup.name, has, count))
							return False
						if i > 100:
							player.signal_send(sanFailedSignal)
							log.critical("Aborting sanity check for Player %s after too many iterations." % player.key.id())
							return False
				elif has > count:
					log.error("Player %s should have had %s of %s but had %s instead. Fixing..." % (player.key.id(), count, pickup.name, has))
					while(has > count):
						i += 1
						last = has
						player.give_pickup(pickup, remove=True, delay_put=True)
						has = player.has_pickup(pickup) 
						if has == last:
							log.critical("Aborting sanity check for Player %s: tried and failed to decrement %s (at %s, should be %s)" % (player.key.id(), pickup.name, has, count))
							return False
							
						if i > 100:
							player.signal_send(sanFailedSignal)
							log.critical("Aborting sanity check for Player %s after too many iterations." % player.key.id())
							return False
		[player.put() for player in players]
		return True
		

	def player(self, pid):
		full_pid = "%s.%s" % (self.key.id(), pid)
		player = Player.get_by_id(full_pid)
		if not player:
			if(self.mode == MultiplayerGameType.SHARED and len(self.players)):
				src = self.players[0].get()
				player = Player(id=full_pid, skills = src.skills, events = src.events, upgrades = src.upgrades, teleporters = src.teleporters,bonuses = src.bonuses, history=[], signals=[])
			else:
				player = Player(id=full_pid, skills = 0, events=0, upgrades = 0, teleporters = 0, history=[])
			k = player.put()
			Cache.setHist(self.key.id(), pid, [])
		else:
			k = player.key
		if k not in self.players:
			self.players.append(k)
			self.put()
		return player
	
	def rebuild_hist(self):
		for player in self.get_players():
			gid,_,pid = player.key.id().partition(".")
			Cache.setHist(gid, pid, player.history)
		return Cache.getHist(gid)

	def found_pickup(self, pid, pickup, coords, remove, dedup, old=False):
		retcode = 200
		share = pickup.share_type in self.shared
		finder = self.player(pid)
		players = self.get_players()
		if share and dedup:
			if coords in [h.coords for h in finder.history]:
				retcode = 410
				log.error("Duplicate pickup at location %s from player %s" % (coords,  pid))
				return
			elif coords in [h.coords for teammate in players for h in teammate.history if teammate.key in finder.teammates]:
				retcode = 410
				log.info("Won't grant %s to player %s, as a teammate found it already" % (pickup.name,  pid))
				return
		if self.mode == MultiplayerGameType.SHARED:
			if not share:
				retcode = 406
			else:
				for player in players:
					if player.key != finder.key:
						player.give_pickup(pickup, remove)
				finder.give_pickup(pickup, remove)
		elif self.mode == MultiplayerGameType.SPLITSHARDS:
			if pickup.code != "RB" or pickup.id not in [17, 19, 21]:
				retcode = 406
			else:
				my_shards = len([h.coords for h in finder.history if h.pickup_code == "RB" and int(h.pickup_id) == pickup.id])
				if my_shards < 3:
					shard_locs = [h.coords for player in players for h in player.history if h.pickup_code == "RB" and h.pickup_id in ["17", "19", "21"]]
					if coords in shard_locs:
						log.info("%s at %s already taken, player %s will not get one." % (pickup.name, coords,  pid))
						return
		elif self.mode == MultiplayerGameType.SIMUSOLO:
			pass
		else:
			log.error("game mode %s not implemented" % self.mode)
			retcode = 404
		if retcode != 410: #410 GONE aka "haha nope"
			if pickup.code == "SH" and old:
				try: # workaround for message pickups not working with old clients. Sketchy, so wrapped in try (we learnin')
					found_here = {player.key.id().partition(".")[2]: hl.pickup() for player in players for hl in player.history if hl.coords == coords}
					msgtext = pickup.id
					if finder.seed:
					# for *reasons*, sometimes the message sent from the client is 0 instead of the message text.
					# we take the message from the seed instead to ensure accuracy.
						raw = next(ifilter(lambda line: line.startswith(str(coords)), finder.seed.split("\n")), None)
						if raw:
							msgtext = raw.split(':')[2] # msglines are loc:Message:actual message
					if "for Player" in msgtext or "for Team" in msgtext:
						if any([p.code=="SH" for p in found_here.itervalues()]):
							msgtext = msgtext.replace("@", "")
						hint_pid, found = next(ifilter(lambda (_,pickup): pickup.code != "SH", found_here.iteritems()), (None, None))
						if found:
							msgtext = "$Player %s found %s here$" % (hint_pid, found.name)
					msg = ''.join(ch for ch in msgtext if ch.isalnum() or ch in "_ ()*@$!%").strip()
					finder.signal_send("msg:" + msg)
					log.warning("manually sending message: %s to player %s" % (msg, pid))
				except Exception as error:
					log.error("Failed trying to message workaround. Pickup: %s, player: %s, error: %s" % (pickup, finder, error))
			finder.history.append(HistoryLine(pickup_code = pickup.code, timestamp = datetime.now(), pickup_id = str(pickup.id), coords = coords, removed = remove))
			finder.put()
			Cache.setHist(self.key.id(), pid, finder.history)
			
		return retcode

	def clean_up(self):
		[p.delete() for p in self.players]
		Cache.removeGame(self.key.id())
		log.info("Deleting game %s" % self)
		self.key.delete()

	@staticmethod
	def with_id(id):
		return Game.get_by_id(int(id))

	@staticmethod
	def clean_old(timeout_window = timedelta(hours=12)):
		old = [game for game in Game.query(Game.last_update < datetime.now() - timeout_window)]	
		return len([Game.clean_up(game) for game in old])
		
	@staticmethod
	def get_open_gid():
		id = 1
		game_ids = set([int(game.key.id()) for game in Game.query()])
		while id in game_ids:
			id += 1
		if id > 20:
			Game.clean_old()
		return id
	
	@staticmethod
	def from_params(params, id=None):
		id = int(id) if id else Game.get_open_gid()

		game = Game(id = id, players=[], ndb_shared=[s.to_ndb() for s in params.sync.shared], ndb_mode=params.sync.mode.to_ndb())
		game.put()
		teams = params.sync.teams
		if teams:
			for playerNums in teams.itervalues():
				team = [game.player(p) for p in playerNums]
				teamKeys = [p.key for p in team]
				for player in team:
					tset = set(teamKeys)
					tset.remove(player.key)
					player.teammates = list(tset)
					player.put()
		log.info("Game.from_params(%s, %s): Created game %s ", params.key, id, game)
		return game

	@staticmethod
	def new(_mode = None, _shared = None, id=None):
		if _shared:
			shared = enums_from_strlist(ShareType, _shared)
		else:
			shared = Game.DEFAULT_SHARED
		mode = MultiplayerGameType(_mode) if _mode else MultiplayerGameType.SHARED
		id = int(id) if id else Game.get_open_gid()
		game = Game(id = id, players=[], ndb_shared=[s.to_ndb() for s in shared], ndb_mode=mode.to_ndb())
		log.info("Game.new(%s, %s, %s): Created game %s ", _mode, _shared, id, game)
		return game
