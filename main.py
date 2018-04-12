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
from operator import attrgetter
from google.appengine.ext.webapp import template
from util import (GameMode, ShareType, Pickup, Skill, Event, Teleporter, Upgrade, share_from_url, share_map, special_coords, get_bit, get_taste, add_single,
				 inc_stackable, get, unpack, coord_correction_map, Cache, HistoryLine, Player, Game, delete_game, get_new_game, clean_old_games, all_locs)

from reachable import Map, PlayerState

base_site = "http://orirandocoopserver.appspot.com"
LAST_DLL = "Mar 27, 2018"
PLANDO_VER = "0.0.8"


def paramFlag(s,f):
	return s.request.get(f,None) != None
def paramVal(s,f):
	return s.request.get(f,None)

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
		self.response.write("GC|%s" % get_new_game(paramVal(self, 'mode'), shared, id).key.id())

class CleanUp(webapp2.RequestHandler):
	def get(self):
		self.response.headers['Content-Type'] = 'text/plain'
		self.response.status = 200
		self.response.write("Cleaned up %s games" % clean_old_games())

class DeleteGame(webapp2.RequestHandler):
	def get(game_id, self):
		self.response.headers['Content-Type'] = 'text/plain'
		if int(game_id) < 1000:
			self.response.status = 403
			self.response.write("No.")
		elif Cache.has(game_id):
			game = Cache.get(game_id)
			delete_game(game)
			self.response.status = 200
			self.response.write("All according to daijobu")		
		else:
			self.response.status = 401
			self.response.write("The game... was already dead...")		
		

class ActiveGames(webapp2.RequestHandler):
	def get(self):
		self.response.headers['Content-Type'] = 'text/html'
		self.response.write('<html><body><pre>Active games:\n' +
			"\n".join(
				["<a href='/%s/history'>Game #%s</a> (<a href='/%s/map'>(Map)</a>):\n\t%s (Last update: %s ago)" % (game.key.id(), game.key.id(), game.key.id(), game.summary(), datetime.now() - game.last_update) for game in sorted(Game.query(), key=lambda x:x.last_update, reverse=True)])+"</pre></body></html>")


class FoundPickup(webapp2.RequestHandler):
	def get(self, game_id, player_id, coords, kind, id):
		remove = paramFlag(self,"remove")
		coords = int(coords)
		if coords in coord_correction_map:
			coords = coord_correction_map[coords]
		if coords not in all_locs:
			print "Coord mismatch error! %s not in all_locs or correction map. Sync %s.%s, pickup %s|%s" % (coords, game_id, player_id, kind, id)
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
		for hl,pid in sorted([(h,p.key.id().partition('.')[2]) for p in game.get_players() for h in p.history if h.pickup().share_type != ShareType.NOT_SHARED], key=lambda x: x[0].timestamp, reverse=True):
			output += "\n\t\t Player %s %s" % (pid, hl.print_line(game.start_time))

		self.response.status = 200
		self.response.write(output)



class SeedGenerator(webapp2.RequestHandler):
	def get(self):
                path = os.path.join(os.path.dirname(__file__), 'index.html')
                template_values = {'latest_dll': LAST_DLL, 'plando_version': PLANDO_VER}
                self.response.out.write(template.render(path, template_values))

	def post(self):
		mode = self.request.get("mode").lower()
		pathdiff = self.request.get("pathdiff").lower()
		variations = set([x for x in ["forcetrees", "hardmode", "notp", "starved", "ohko", "noplants", "discmaps", "0xp", "nobonus"] if self.request.get(x)])
		logic_paths = [x for x in ["normal", "speed", "lure", "speed-lure", "dboost", "dboost-light", "dboost-hard", "cdash", "dbash", "extended", "lure-hard", "timed-level", "glitched", "extended-damage", "extreme"] if self.request.get(x)]
		playercount = self.request.get("playerCount")
		syncid = self.request.get("syncid")
		syncmode = int(self.request.get("syncmode"))
		seed = self.request.get("seed")
		share_types = [f for f in share_map.keys() if self.request.get(f)]

		game_id = False
		if not seed:
			seed = str(random.randint(10000000,100000000))
		if syncid:
			syncid = int(syncid)
			if Cache.has(syncid):
				if syncid > 999:
					if Cache.has(syncid):
						game = Cache.get(syncid)
						delete_game(game)				
					game_id = get_new_game(_mode=syncmode, _shared=share_types, id=syncid).key.id()
				else:
					self.response.status = 405
					self.response.write("Seed ID in use! Leave blank or pick a different number.")
					return				
		if not game_id:
			if syncid:
				game_id = get_new_game(_mode=syncmode, _shared=share_types, id=syncid).key.id()			
			else:
				game_id = get_new_game(_mode=syncmode, _shared=share_types).key.id()			

		urlargs = ["m=%s" % mode]
		urlargs.append("vars=%s" % "|".join(variations))
		urlargs.append("lps=%s" % "|".join(logic_paths))
		urlargs.append("s=%s" % seed)
		urlargs.append("pc=%s" % playercount)
		urlargs.append("pd=%s" % pathdiff)
		urlargs.append("shr=%s" % "+".join(share_types))
		urlargs.append("gid=%s" % game_id)
		for flg in ["dk", "ev", "sk", "rb", "tp", "hot"]:
			if self.request.get(flg):
				urlargs.append("%s=1" % flg)
		self.response.headers['Content-Type'] = 'text/html'
		out = "<html><body>"
		url = '/getseed?%s' % "&".join(urlargs)
		out += "<div><a target='_blank' href='%s&p=spoiler'>Spoiler</a></div>" % url
		out += "<div><a target='_blank' href='/%s/map?paths=%s'>Map</a></div>" % (game_id, "+".join(logic_paths))
		out += "<div><a target='_blank' href='/%s/history'>History</a></div>" % game_id
		
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
			pathdiff = None
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
		ss = split_seed(placement[0], game_id, player, playercount, "hot" in params, "dk" in params, 
						"sk" in params, "ev" in params, "rb" in params, "tp" in params)
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


class Plando(webapp2.RequestHandler):
	def get(self):
		path = os.path.join(os.path.dirname(__file__), 'map/build/index.html')
		template_values = {'app': "plandoBuilder", 'title': "Plandomizer Editor "+PLANDO_VER, 
							'pathmode': paramVal(self, 'pathmode'), 'HC': paramVal(self, 'HC'),
							'EC': paramVal(self, 'EC'), 'AC': paramVal(self, 'AC'), 'KS': paramVal(self, 'KS'),
							'skills': paramVal(self, 'skills'), 'tps': paramVal(self, 'tps')}
		self.response.out.write(template.render(path, template_values))
			
class ShowMap(webapp2.RequestHandler):
	def get(self, game_id):
		path = os.path.join(os.path.dirname(__file__), 'map/build/index.html')
		template_values = {'app': "gameTracker", 'title': "Game %s" % game_id, 'game_id': game_id, 'is_spoiler': paramFlag(self, 'sp'), 'logic_modes': paramVal(self, 'paths')}
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
			shared_opt = [f[7:].split(" ") for f in flags if f.lower().startswith("shared=")]
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

class GetReachable(webapp2.RequestHandler):
	def get(self, game_id):
		game = Cache.get(game_id)
		if not game or not paramVal(self, "modes"):
			self.response.status = 404
			self.response.write("Stop")
			return
		modes = paramVal(self,"modes").split(" ")
		self.response.headers['Content-Type'] = 'text/plain'
		self.response.status = 200
		players = game.get_players()
		self.response.out.write("|".join(["%s:%s" % (player.key.id().partition(".")[2], ",".join(Map.get_reachable_areas(PlayerState.from_player(player), modes))) for player in players]))



class PlandoReachable(webapp2.RequestHandler):
	def get(self):
		modes = paramVal(self,"modes").split(" ")
		codes = [tuple(c.split("|")+[False]) for c in paramVal(self,"codes").split(" ")] if paramVal(self,"codes") else []
		self.response.headers['Content-Type'] = 'text/plain'
		self.response.status = 200
		self.response.out.write("|".join(Map.get_reachable_areas(PlayerState.from_codes(codes), modes)))


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
	(r'/(\d+)/delete', DeleteGame),
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
	(r'/(\d+)/reachable', GetReachable),
	(r'/reachable', PlandoReachable),
	(r'/plando', Plando)
], debug=True)


