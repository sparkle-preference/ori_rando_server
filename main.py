#haha this is garbage sorry

# py imports
import random
import os
from operator import attrgetter
import pickle

# web imports
import webapp2
from datetime import datetime, timedelta
from protorpc import messages
from google.appengine.api import users
from google.appengine.ext import ndb
from google.appengine.ext.ndb import msgprop
from google.appengine.ext.webapp import template

# project impports
from seedbuilder.generator import setSeedAndPlaceItems
from seedbuilder.splitter import split_seed
from util import (GameMode, ShareType, Pickup, Skill, Event, Teleporter, Upgrade, share_map, special_coords, get_bit, get_taste, add_single, Seed, get_open_gid,
				 mode_map, DEDUP_MODES, get, unpack, coord_correction_map, Cache, HistoryLine, Player, Game, delete_game, get_new_game, clean_old_games, all_locs)
from reachable import Map, PlayerState

LAST_DLL = "Mar 27, 2018"
PLANDO_VER = "0.2.0"
debug = os.environ.get('SERVER_SOFTWARE', '').startswith('Dev')
base_site = "http://orirandocoopserver.appspot.com" if not debug else "https://8080-dot-3616814-dot-devshell.appspot.com"


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
			shared = [s for s in shared.split(" ") if s]
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
		game = Game.get_by_id(game_id)
		if game:
			delete_game(game)
			self.response.status = 200
			self.response.write("All according to daijobu")		
		else:
			self.response.status = 401
			self.response.write("The game... was already dead...")		
		

class ActiveGames(webapp2.RequestHandler):
	def get(self):
		self.response.headers['Content-Type'] = 'text/html'
		games = Game.query().fetch()
		if len(games):
			self.response.write('<html><body><pre>Active games:\n' + "\n".join(["<a href='/%s/history'>Game #%s</a> (<a href='/%s/map'>(Map)</a>):\n\t%s (Last update: %s ago)" % (game.key.id(), game.key.id(), game.key.id(), game.summary(), datetime.now() - game.last_update) for game in sorted(games, key=lambda x:x.last_update, reverse=True)])+"</pre></body></html>")
		else:
			self.response.write('<html><body>No active games...</body></html>')


class FoundPickup(webapp2.RequestHandler):
	def get(self, game_id, player_id, coords, kind, id):
		game = Game.get_by_id(game_id)
		if not game:
			self.response.status = 412
			self.response.write(self.response.status)
			return
		
		remove = paramFlag(self,"remove")
		coords = int(coords)
		if coords in coord_correction_map:
			coords = coord_correction_map[coords]
		if coords not in all_locs:
			print "Coord mismatch error! %s not in all_locs or correction map. Sync %s.%s, pickup %s|%s" % (coords, game_id, player_id, kind, id)
		dedup = not paramFlag(self, "override") and not remove and game.mode in DEDUP_MODES
		pickup = Pickup.n(kind, id)
		if not pickup:
			print "ERROR: Couldn't build pickup %s|%s" % (kind, id)
			self.response.status = 406
			return
		self.response.status = game.found_pickup(player_id, pickup, coords, remove, dedup)
		self.response.write(self.response.status)

class Update(webapp2.RequestHandler):
	def get(self, game_id, player_id, x, y):
		self.response.headers['Content-Type'] = 'text/plain'
		game = Game.get_by_id(game_id)
		if not game:
			self.response.status = 412
			self.response.write(self.response.status)
			return
		p = game.player(player_id)
		Cache.setPos(game_id, player_id, x, y)
		self.response.write(p.bitfields)


class ShowHistory(webapp2.RequestHandler):
	def get(self, game_id):
		self.response.headers['Content-Type'] = 'text/plain'
		game = Game.get_by_id(game_id)
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
		syncmode = self.request.get("syncmode").lower()
		syncmode = mode_map[syncmode] if syncmode in mode_map else int(syncmode)
		seed = self.request.get("seed")
		share_types = [f for f in share_map.keys() if self.request.get(f)]

		game_id = False
		if not seed:
			seed = str(random.randint(10000000,100000000))
		if syncid:
			syncid = int(syncid)
			oldGame = Game.get_by_id(syncid)
			if oldGame != None:
				if syncid > 999:
					delete_game(oldGame)				
					game_id = get_new_game(_mode=syncmode, _shared=share_types, id=syncid).key.id()
				else:
					self.response.status = 405
					self.response.write("Seed ID in use! Leave blank or pick a different number.")
					return
			else:
				game_id = get_new_game(_mode=syncmode, _shared=share_types, id=syncid).key.id()		

		if not game_id:
			game_id = get_new_game(_mode=syncmode, _shared=share_types).key.id()			

		urlargs = ["m=%s" % mode]
		urlargs.append("vars=%s" % "|".join(variations))
		urlargs.append("lps=%s" % "|".join(logic_paths))
		urlargs.append("s=%s" % seed)
		urlargs.append("pc=%s" % playercount)
		urlargs.append("pd=%s" % pathdiff)
		urlargs.append("shr=%s" % "+".join(share_types))
		urlargs.append("sym=%s" % syncmode)
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
		syncmode = params["sym"]
		seed = params['s']
		playercount = int(params['pc'])
		pathdiff = params['pd']
		player = params['p']
		game_id = int(params['gid'])
		if pathdiff == "normal":
			pathdiff = None
		varFlags = {"starved":"starved", "hardmode":"hard","ohko":"OHKO","0xp":"0XP","nobonus":"NoBonus","noplants": "NoPlants", "forcetrees" : "ForceTrees", "discmaps" : "NonProgressMapStones",  "notp" : "NoTeleporters"}
		share_types = params['shr']
		flags = ["Custom", "shared=%s" % share_types.replace(" ", "+"),"mode=%s" % syncmode]
		if mode != "default":
			flags.append(mode)
		if pathdiff:
			flags.append("prefer_path_difficulty=" + pathdiff)
		for v in variations:
			flags.append(varFlags[v])

		flag = ",".join(flags)
		out = ""
		placement = setSeedAndPlaceItems(seed, 10000,
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
		game = Game.get_by_id(game_id)
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
		game = Game.get_by_id(game_id)
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
		game = Game.get_by_id(game_id)
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
		game = Game.get_by_id(game_id)
		if key in [p.id() for p in game.players]:
			game.remove_player(key)
			return webapp2.redirect("/%s/players" % game_id)
		else:
			self.response.headers['Content-Type'] = 'text/plain'
			self.response.status = 404
			self.response.out.write("player %s not in %s" % (key, game.players))

class ShowCache(webapp2.RequestHandler):
	def get(self):
		self.response.headers['Content-Type'] = 'text/plain'
		self.response.write(str(Cache.pos)+"\n"+str(Cache.hist))

class ClearCache(webapp2.RequestHandler):
	def get(self):
		Cache.pos = {} 
		Cache.hist = {}
		self.redirect("/cache")


class Plando(webapp2.RequestHandler):
	def get(self):
		path = os.path.join(os.path.dirname(__file__), 'map/build/index.html')
		template_values = {'app': "plandoBuilder", 'title': "Plandomizer Editor "+PLANDO_VER, 
							'pathmode': paramVal(self, 'pathmode'), 'HC': paramVal(self, 'HC'),
							'EC': paramVal(self, 'EC'), 'AC': paramVal(self, 'AC'), 'KS': paramVal(self, 'KS'),
							'skills': paramVal(self, 'skills'), 'tps': paramVal(self, 'tps')}
		self.response.out.write(template.render(path, template_values))
			
class PlandoReachable(webapp2.RequestHandler):
	def get(self):
		modes = paramVal(self,"modes").split(" ")
		codes = [tuple(c.split("|")+[False]) for c in paramVal(self,"codes").split(" ")] if paramVal(self,"codes") else []
		codes.append(("EC", "1", False))
		self.response.headers['Content-Type'] = 'text/plain'
		self.response.status = 200
		self.response.out.write("|".join(Map.get_reachable_areas(PlayerState(codes), modes)))


class SetSeed(webapp2.RequestHandler):
	def get(self, game_id, player_id):
		seedlines = []
		lines = paramVal(self, "seed").split(",")		
		game = Game.get_by_id(game_id)
		hist = Cache.getHist(game_id)
		if not hist:
			Cache.setHist(game_id, player_id, [])
		pos = Cache.getPos(game_id)
		if not pos:
			Cache.setPos(game_id, player_id, 0, 0)
		if not game:
			flags = lines[0].split("|")
			mode_opt = [f[5:] for f in flags if f.lower().startswith("mode=")]
			shared_opt = [f[7:].split(" ") for f in flags if f.lower().startswith("shared=")]
			mode = mode_opt[0].lower() if mode_opt else None
			mode = mode_map[mode] if mode in mode_map else int(mode)

			shared = shared_opt[0] if shared_opt else None
			game = get_new_game(_mode = mode, _shared = shared, id=game_id)
		for l in lines[1:]:
			line = l.split("|")
			if len(line) < 3:
				print "ERROR: malformed seed line %s, skipping" % l
			else:
				seedlines.append("%s:%s" % (line[0], Pickup.name(line[1],line[2])))
		player = game.player(player_id)
		player.seed = "\n".join(seedlines)
		player.put()
		self.response.headers['Content-Type'] = 'text/plain'
		self.response.status = 200
		self.response.out.write("ok")

class ShowMap(webapp2.RequestHandler):
	def get(self, game_id):
		path = os.path.join(os.path.dirname(__file__), 'map/build/index.html')
		template_values = {'app': "gameTracker", 'title': "Game %s" % game_id, 'game_id': game_id, 'is_spoiler': paramFlag(self, 'sp'), 'logic_modes': paramVal(self, 'paths')}
		self.response.out.write(template.render(path, template_values))

class GetSeenLocs(webapp2.RequestHandler):
	def get(self, game_id):
		game = Game.get_by_id(game_id)
		hist = Cache.getHist(game_id)
		if not hist:
			self.response.status = 404
			self.response.write(self.response.status)
			return
		self.response.headers['Content-Type'] = 'text/plain'
		self.response.status = 200
		self.response.out.write("|".join(
			["%s:%s" % (p, ",".join([str(h.coords) for h in hls])) for p,hls in hist.iteritems()]
		))

class GetSeed(webapp2.RequestHandler):
	def get(self, game_id, player_id):
		game = Game.get_by_id(game_id)
		if not game:
			self.response.status = 404
			self.response.write(self.response.status)
			return
		player = game.player(player_id)
		self.response.headers['Content-Type'] = 'text/plain'
		self.response.status = 200
		self.response.out.write(player.seed)

class GetReachable(webapp2.RequestHandler):
	def get(self, game_id):
		hist = Cache.getHist(game_id)
		if not hist or not paramVal(self, "modes"):
			self.response.status = 404
			self.response.write(self.response.status)
			return
		modes = paramVal(self,"modes").split(" ")
		self.response.headers['Content-Type'] = 'text/plain'
		self.response.status = 200
		self.response.out.write("|".join(
			["%s:%s" % (p, ",".join(
				Map.get_reachable_areas(PlayerState([(h.pickup_code, h.pickup_id, h.removed) for h in hls]), modes)
			)) for p,hls in hist.iteritems()]
		))

class GetPlayerPositions(webapp2.RequestHandler):
	def get(self, game_id):
		pos = Cache.getPos(game_id)
		if pos:
			self.response.headers['Content-Type'] = 'text/plain'
			self.response.status = 200
			self.response.out.write("|".join(["%s:%s,%s" % (p,x,y) for p, (x,y) in pos.iteritems()]))
		else:
			self.response.headers['Content-Type'] = 'text/plain'
			self.response.status = 404


class PlandoUpload(webapp2.RequestHandler):
	def post(self, author, plando):
		user = users.get_current_user()
		if user:
			dispname = user.email().partition("@")[0]
			if dispname == author:
				id = author+":"+plando
				seedLines = self.request.POST["seed"]
				desc = self.request.POST["desc"]
				seed = Seed.from_plando(seedLines.split("!"), author, plando, desc)
				res = seed.put()
				self.response.headers['Content-Type'] = 'text/plain'
				self.response.status = 200
				self.response.out.write(res)
			else:
				print "ERROR: Auth failed, logged in as %s, trying to access %s" % (dispname, author)
		else:
			print "ERROR: no auth D:"



class PlandoView(webapp2.RequestHandler):
	def get(self, author, plando):
		user = users.get_current_user()
		if user:
			dispname = user.email().partition("@")[0]
		id = author+":"+plando
		seed = Seed.get_by_id(id)
		if seed:
			self.response.status = 200
			self.response.headers['Content-Type'] = 'text/html'
			path = os.path.join(os.path.dirname(__file__), 'map/build/index.html')
			template_values = {'app': "seedDisplay", 'title': "%s by %s" % (plando, author), 'players': seed.players, 'seed_data': seed.to_lines()[0], 
				  				'seed_name': plando, 'author': author, 'seed_desc': seed.description, 'user': dispname, 'game_id': get_open_gid()}
			self.response.out.write(template.render(path, template_values))
		else:
			self.response.status = 404
			self.response.headers['Content-Type'] = 'text/plain'
			self.response.out.write("seed not found")


class PlandoEdit(webapp2.RequestHandler):
	def get(self, author, plando):
		path = os.path.join(os.path.dirname(__file__), 'map/build/index.html')
		template_values = {'app': "plandoBuilder", 'title': "Plandomizer Editor "+PLANDO_VER, 'seed_name': plando}
		owner = False
		user = users.get_current_user()
		if user:
			dispname = user.email().partition("@")[0]
			owner = dispname == author			
		id = author+":"+plando
		if not owner:
			self.redirect('/login')
		else:
			seed = Seed.get_by_id(id)
			template_values['user'] = dispname
			template_values['authed'] = "True"
			if seed:
				template_values['seed_desc'] = seed.description
				template_values['seed_data'] = "\n".join(seed.to_plando_lines())
			self.response.out.write(template.render(path, template_values))
				
	
class PlandoOld(webapp2.RequestHandler):
	def get(self):
		path = os.path.join(os.path.dirname(__file__), 'map/build/index.html')
		user = users.get_current_user()
		if user:
			dispname = user.email().partition("@")[0]
			self.redirect("/%s/seedName/edit" % dispname)
		else:
			template_values = {'app': "plandoBuilder", 'title': "Plandomizer Editor "+PLANDO_VER, 
								'pathmode': paramVal(self, 'pathmode'), 'HC': paramVal(self, 'HC'), 
								'EC': paramVal(self, 'EC'), 'AC': paramVal(self, 'AC'), 'KS': paramVal(self, 'KS'),
								'skills': paramVal(self, 'skills'), 'tps': paramVal(self, 'tps')}
			self.response.out.write(template.render(path, template_values))

class HandleLogin(webapp2.RequestHandler):
	def get(self):
		user = users.get_current_user()
		if user:
			dispname = user.email().partition("@")[0]
			self.redirect('/'+dispname)
		else:
			self.redirect(users.create_login_url(self.request.uri))
	
class HandleLogout(webapp2.RequestHandler):
	def get(self):
		user = users.get_current_user()
		if user:
			self.redirect(users.create_logout_url("/"))
		else:
			self.redirect("/")

class PlandoDownload(webapp2.RequestHandler):
	def get(self, author, plando):
		owner = False
		user = users.get_current_user()
		if user:
			dispname = user.email().partition("@")[0]
			owner = dispname == author			
		id = author+":"+plando
		seed = Seed.get_by_id(id)
		if seed:
			gid = paramVal(self, "gid")
			pid = paramVal(self, "pid")
			syncFlag = "Sync%s.%s" % (gid, pid)
			self.response.status = 200
			self.response.headers['Content-Type'] = 'application/x-gzip'
			self.response.headers['Content-Disposition'] = 'attachment; filename=randomizer.dat'
			self.response.out.write("\n".join(seed.to_lines(player=int(pid), extraFlags=[syncFlag])))
		else:
			self.response.status = 404
			self.response.headers['Content-Type'] = 'text/plain'
			self.response.out.write("seed not found")

class AuthorIndex(webapp2.RequestHandler):
	def get(self,author):
		self.response.headers['Content-Type'] = 'text/html'
		seeds = Seed.query(Seed.author == author).fetch()
		owner = False
		user = users.get_current_user()
		if user:
			dispname = user.email().partition("@")[0]
			owner = dispname == author
		if owner:
			if len(seeds):
				self.response.write('<html><body><pre>Seeds by %s:\n' % author + "\n".join(["<a href='/%s/%s'>%s</a>: %s (%s players, %s) <a href='/%s/%s/edit'>Edit</a>" % (author, seed.name, seed.name, seed.description, seed.players, ",".join(seed.flags), author, seed.name) for seed in seeds])+"</pre></body></html>")
			else:
				self.response.write("<html><body>You haven't made any seeds yet! <a href='/%s/newseed/edit'>Start a new seed</a></body></html>" % author)		
		else:
			if len(seeds):
				self.response.write('<html><body><pre>Seeds by %s:\n' % author + "\n".join(["<a href='/%s/%s'>%s</a>: %s (%s players, %s) " % (author, seed.name, seed.name, seed.description, seed.players, ",".join(seed.flags)) for seed in seeds])+"</pre></body></html>")
			else:
				self.response.write('<html><body>No seeds by user %s</body></html>' % author)
class QuickStart(webapp2.RequestHandler):
	def get(self):
		self.response.write("""<html><body><pre>Misc info:
- From <a href=http://orirandocoopserver.appspot.com/activeGames>this page</a> you can see a list of active games, and follow links to see a game's history or an active map. 
- If you set game mode to 4 from the seed gen page, you can generate seeds that play out like solo rando seeds but with map tracking.
- The <a href=http://orirandocoopserver.appspot.com/>seed generator</a> currently produces multiplayer seeds by splitting up important pickups, giving each to 1 player and the rest of the players a dummy pickup. With split: hot set, that dummy pickup is warmth returned: otherwise it's 1-100 exp (chosen randomly).
- The plandomizer editor is located <a href=http://orirandocoopserver.appspot.com/plando>here</a>. The interface is graphical: click on pickups or select them using the zone/location dropdowns, and then fill in what you want to be there. (You may need to change or disable the logic options if your plando does things outside of the logic).
- You can generate a visual spoiler for any seed by importing it into the plando (paste the full text of the .dat file into the text box).
- If you have any questions or bug reports please ping me  ( @SOL | Eiko  on the ori discord)
</pre></body></html>""")

app = webapp2.WSGIApplication([
	('/faq/', QuickStart),
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
	(r'/(\d+)/_getPos', GetPlayerPositions),
	(r'/cache', ShowCache),
	(r'/cache/clear', ClearCache),
	(r'/(\d+)/_seen', GetSeenLocs),
	(r'/(\d+)\.(\w+)/_seed', GetSeed),
	(r'/(\d+)\.(\w+)/setSeed', SetSeed),
	(r'/(\d+)/_reachable', GetReachable),
	(r'/reachable', PlandoReachable),
	(r'/login', HandleLogin),
	(r'/logout', HandleLogout),
	(r'/plando', PlandoOld),
	(r'/([^ ?=/]+)/([^ ?=/]+)/upload', PlandoUpload),
	(r'/([^ ?=/]+)/([^ ?=/]+)/download', PlandoDownload),
	(r'/([^ ?=/]+)/([^ ?=/]+)/edit', PlandoEdit),
	(r'/([^ ?=/]+)', AuthorIndex),
	(r'/([^ ?=/]+)/([^ ?=/]+)', PlandoView)
], debug=True)


