#haha this is garbage sorry

import webapp2
import random
import os
import pickle
from datetime import datetime, timedelta
from protorpc import messages
from google.appengine.ext import ndb
from google.appengine.ext.ndb import msgprop
from seedbuilder.generator import placeItems
from seedbuilder.splitter import split_seed
from abc import ABCMeta, abstractproperty
from operator import attrgetter
from google.appengine.ext.webapp import template
from util import GameMode, ShareType, Pickup, Skill, Event, Teleporter, Upgrade, share_from_url, share_map, special_coords, get_bit, get_taste, add_single, inc_stackable, get, unpack
base_site = "http://orirandocoopserver.appspot.com"

class Cache(object):
	WRITE_EVERY = 1
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
		Cache.put(self)		

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
		Cache.put(self)
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
			self.players.append(k)
			Cache.put(self)
		
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

def clean_old_games():
	old = [game for game in Game.query(Game.last_update < datetime.now() - timedelta(hours=1))]
	[Cache.delete(p) for game in old for p in game.players]
	return len([Cache.delete(game) for game in old])

	
def get_new_game(_mode = None, _shared = None, id=None):
	shared = [share_from_url(i) for i in _shared] if _shared else Game.DEFAULT_SHARED
	mode = GameMode(int(_mode)) if _mode else GameMode.SHARED
	game_id = id
	game = Game(id = str(game_id), players=[], shared=shared, mode=mode)
	key = Cache.put(game)
	return game

class GetGameId(webapp2.RequestHandler):
	def get(self):
		self.response.headers['Content-Type'] = 'text/plain'
		self.response.status = 200
		shared = paramVal(self, 'shared')
		if shared:
			shared = shared.split(" ")
		id = paramVal(self, 'id')
		if "." in id:
			id = id.partition(".")[0]
		self.response.write("GC|%s" % get_new_game(paramVal(self, 'mode'), shared, id).key().id)

class CleanUp(webapp2.RequestHandler):
	def get(self):
		self.response.headers['Content-Type'] = 'text/plain'
		self.response.write("Cleaned up %s games" % clean_old_games())

class ActiveGames(webapp2.RequestHandler):
	def get(self):
		self.response.headers['Content-Type'] = 'text/html'
		self.response.write('<html><body><pre>Active games:\n' +
			"\n".join(
				["<a href='/%s/history'>Game #%s</a> (<a href='/%s/map'>(Map)</a>):\n\t%s " % (game.key.id(), game.key.id(), game.key.id(), game.summary()) for game in Game.query()])+"</pre></body></html>")

def paramFlag(s,f):
	return s.request.get(f,None) != None
def paramVal(s,f):
	return s.request.get(f,None)

class FoundPickup(webapp2.RequestHandler):
	def get(self, game_id, player_id, coords, kind, id):
		remove = paramFlag(self,"remove")
		coords = int(coords)
		game = Cache.get(game_id)
		if not remove and not paramFlag(self, "override") and coords in [ h.coords for h in game.player(player_id).history]:
			self.response.status = 410
			self.response.write("Duplicate pickup at location %s from player %s" % (coords,  player_id))
			return
		pickup = Pickup.n(kind, id)
		if not pickup:
			self.response.status = 406
			return
		if paramFlag(self,"log_only"):
			self.response.status = 200
			self.response.write("logged")
			return
		self.response.status = game.found_pickup(player_id, pickup, coords, remove)
		self.response.write(self.response.status)

class Update(webapp2.RequestHandler):
	def get(self, game_id, player_id, x, y):
		self.response.headers['Content-Type'] = 'text/plain'
		game = Cache.get(game_id)
		if not game:
			self.response.status = 412
			self.response.write(self.response.status)
			return
		p = game.player(player_id)
		p.update_pos(x,y)
		self.response.write(p.bitfields)


class ShowHistory(webapp2.RequestHandler):
	def get(self, game_id):
		self.response.headers['Content-Type'] = 'text/plain'
		game = Cache.get(game_id)
		output = game.summary()
		output += "\nHistory:"
		for hl,pid in sorted([(h,p.key.id().partition('.')[2]) for p in game.get_players() for h in p.history if hl.pickup().share_type != ShareType.NOT_SHARED], key=lambda x: x[0].timestamp, reverse=True):
			output += "\n\t\t Player %s %s" % (pid, hl.print_line(game.start_time))

		self.response.status = 200
		self.response.write(output)



class SeedGenerator(webapp2.RequestHandler):
	def get(self):
                path = os.path.join(os.path.dirname(__file__), 'index.html')
                template_values = {}
                self.response.out.write(template.render(path, template_values))

	def post(self):
		mode = self.request.get("mode").lower()
		pathdiff = self.request.get("pathdiff").lower()
		variations = set([x for x in ["forcetrees", "hardmode", "notp", "starved", "ohko", "noplants", "discmaps", "0xp", "nobonus"] if self.request.get(x)])
		logic_paths = [x for x in ["normal", "speed", "lure", "speed-lure", "dboost", "dboost-light", "dboost-hard", "cdash", "dbash", "extended", "lure-hard", "timed-level", "glitched", "extended-damage", "extreme"] if self.request.get(x)]
		playercount = self.request.get("playerCount")
		seed = self.request.get("seed")
		if not seed:
			seed = str(random.randint(10000000,100000000))

		share_types = [f for f in share_map.keys() if self.request.get(f)]
		game_id = get_new_game(_mode=1, _shared=" ".join(share_types))
		
		urlargs = ["m=%s" % mode]
		urlargs.append("vars=%s" % "|".join(variations))
		urlargs.append("lps=%s" % "|".join(logic_paths))
		urlargs.append("s=%s" % seed)
		urlargs.append("pc=%s" % playercount)
		urlargs.append("pd=%s" % pathdiff)
		urlargs.append("shr=%s" % "+".join(share_types))
		urlargs.append("gid=%s" % game_id)
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
		game_id = int(params['gid'])
		seed_num = sum([ord(c) * i for c,i in zip(seed, range(len(seed)))])
		if pathdiff == "normal":
			pathdiff == None
		varFlags = {"starved":"starved", "hardmode":"hard","ohko":"OHKO","0xp":"0XP","nobonus":"NoBonus","noplants": "NoPlants", "forcetrees" : "ForceTrees", "discmaps" : "NonProgressMapStones",  "notp" : "NoTeleporters"}
		share_types = params['shr']
		flags = ["Custom", "shared=%s" % share_types.replace(" ", "+")]
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
				"notp" in variations,
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
		ss = split_seed(placement[0], game_id, player, playercount, "hot" in params, "sk" in params, "ev" in params, "rb" in params)
		self.response.headers['Content-Type'] = 'application/x-gzip'
		self.response.headers['Content-Disposition'] = 'attachment; filename=randomizer.dat'
		self.response.out.write(ss)

class SignalCallback(webapp2.RequestHandler):
	def get(self, game_id, player_id, signal):
		self.response.headers['Content-Type'] = 'text/plain'
		game = Cache.get(game_id)
		if not game:
			self.response.status = 412
			self.response.write(self.response.status)
			return
		p = game.player(player_id)
		p.signal_conf(signal)
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
		game = Cache.get(game_id)
		if not game:
			self.response.status = 412
			self.response.write(self.response.status)
			return
		p = game.player(player_id)
		p.signal_send(signal)
		self.response.status = 200
		self.response.write("sent")

class ListPlayers(webapp2.RequestHandler):
	def get(self, game_id):
		game = Cache.get(game_id)
		outlines = []
		for p in game.get_players():
			outlines.append("Player %s: %s" % (p.key.id(), p.bitfields))
			outlines.append("\t\t"+"\n\t\t".join([hl.print_line(game.start_time) for hl in p.history if hl.pickup().share_type != ShareType.NOT_SHARED]))
			
		self.response.headers['Content-Type'] = 'text/plain'
		self.response.status = 200
		self.response.out.write("\n".join(outlines))

class RemovePlayer(webapp2.RequestHandler):
	def get(self, game_id, pid):
		key = ".".join([game_id, pid])
		game = Cache.get(game_id)
		if key in [p.id() for p in game.players]:
			game.remove_player(key)
			return webapp2.redirect("/%s/players" % game_id)
		else:
			print game.players,
			self.response.headers['Content-Type'] = 'text/plain'
			self.response.status = 404
			self.response.out.write("player %s not in %s" % (key, game.players))


class GetPlayerPositions(webapp2.RequestHandler):
	def get(self, game_id):
		game = Cache.get(game_id)
		if game:
			players = game.get_players()
			self.response.headers['Content-Type'] = 'text/plain'
			self.response.status = 200
			self.response.out.write("|".join(["%s:%s,%s" % (p.key.id().partition(".")[2], p.pos_x, p.pos_y) for p in players]))
		else:
			self.response.headers['Content-Type'] = 'text/plain'
			self.response.status = 404
			self.response.out.write("Stop")

class ShowCache(webapp2.RequestHandler):
	def get(self):
		self.response.headers['Content-Type'] = 'text/plain'
		self.response.write(str(Cache.s))

class ClearCache(webapp2.RequestHandler):
	def get(self):
		self.response.headers['Content-Type'] = 'text/plain'
		Cache.s = {}
		self.response.write(str(Cache.s))
			
class ShowMap(webapp2.RequestHandler):
	def get(self, game_id):
		path = os.path.join(os.path.dirname(__file__), 'map/build/index.html')
		template_values = {'game_id': game_id, 'is_spoiler': paramFlag(self, 'sp')}
		self.response.out.write(template.render(path, template_values))

class GetSeenLocs(webapp2.RequestHandler):
	def get(self, game_id):
		game = Cache.get(game_id)
		if not game:
			self.response.headers['Content-Type'] = 'text/plain'
			self.response.status = 404
			self.response.out.write("Stop")
			return
		players = game.get_players()
		self.response.out.write("|".join([ "%s:%s" % (p.key.id().partition(".")[2], ",".join([str(h.coords) for h in p.history])) for p in players]))

class SetSeed(webapp2.RequestHandler):
	def get(self, game_id, player_id):
		seedlines = []
		lines = paramVal(self, "seed").split(",")		
		game = Cache.get(game_id)
		if not game:
			flags = lines[0].split("|")
			mode_opt = [int(f[5:]) for f in flags if f.lower().startswith("mode=")]
			shared_opt = [f[7:].split("+") for f in flags if f.lower().startswith("shared=")]
			mode = mode_opt[0] if mode_opt else None
			shared = shared_opt[0] if shared_opt else None
			game = get_new_game(_mode = mode, _shared = shared, id=game_id)
		for l in lines[1:]:
			line = l.split("|")
			seedlines.append("%s: %s" % (line[0], Pickup.name(line[1],line[2])))
		player = game.player(player_id)
		player.seed = "\n".join(seedlines)
		Cache.put(player)
		self.response.headers['Content-Type'] = 'text/plain'
		self.response.status = 200
		self.response.out.write("ok")

class GetSeed(webapp2.RequestHandler):
	def get(self, game_id, player_id):
		game = Cache.get(game_id)
		if not game:
			self.response.status = 412
			self.response.write(self.response.status)
			return
		player = game.player(player_id)
		self.response.headers['Content-Type'] = 'text/plain'
		self.response.status = 200
		self.response.out.write(player.seed)

app = webapp2.WSGIApplication([
	('/', SeedGenerator),
	('/activeGames', ActiveGames),
	('/clean', CleanUp),
	('/getseed', SeedDownloader),
	('/getNewGame', GetGameId),
	(r'/(\d+)', HistPrompt),
	(r'/(\d+)\.(\w+)/(-?\d+)/(\w+)/(\w+)', FoundPickup),
	(r'/(\d+)\.(\w+)/(-?\d+.?\d*),(-?\d+.?\d*)', Update),
	(r'/(\d+)\.(\w+)/signalCallback/(\w+)', SignalCallback),
	(r'/(\d+)/history', ShowHistory),
	(r'/(\d+)/players', ListPlayers),
	(r'/(\d+)\.(\w+)/remove', RemovePlayer),
	(r'/(\d+)/map', ShowMap),
	(r'/(\d+)/getPos', GetPlayerPositions),
	(r'/cache', ShowCache),
	(r'/cache/clear', ClearCache),
	(r'/(\d+)/seen', GetSeenLocs),
	(r'/(\d+)\.(\w+)/seed', GetSeed),
	(r'/(\d+)\.(\w+)/setSeed', SetSeed),
], debug=True)


