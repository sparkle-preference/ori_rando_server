# haha this is garbage sorry

# py imports
import random
import os
import json
from collections import Counter

# web imports
import logging as log
from webapp2_extras.routes import PathPrefixRoute, RedirectRoute as Route
from test import TestRunner
from webapp2 import WSGIApplication, RequestHandler, redirect, uri_for
from datetime import datetime, timedelta
from google.appengine.api import users
from google.appengine.ext import ndb
from google.appengine.ext.webapp import template

# project imports
from seedbuilder.seedparams import SeedGenParams
from seedbuilder.vanilla import seedtext as vanilla_seed
from bingo import Card
from enums import MultiplayerGameType, ShareType
from models import Game, Seed
from pickups import Pickup
from cache import Cache
from util import coord_correction_map, all_locs
from reachable import Map, PlayerState

PLANDO_VER = "0.5.1"
debug = os.environ.get('SERVER_SOFTWARE', '').startswith('Dev')
base_site = "http://orirando.com" if not debug else "https://8080-dot-3616814-dot-devshell.appspot.com"


def paramFlag(s, f):
    return s.request.get(f, None) != None
    
def paramVal(s, f):
    return s.request.get(f, None)

class GetGameId(RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'text/plain'
        self.response.status = 200
        shared = paramVal(self, 'shared')
        if shared:
            shared = [s for s in shared.split(" ") if s]
        id = paramVal(self, 'id')
        if "." in id:
            id = id.partition(".")[0]
        self.response.write("GC|%s" % Game.new(paramVal(self, 'mode'), shared, id).key.id())


class CleanUp(RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'text/plain'
        self.response.status = 200
        self.response.write("Cleaned up %s games" % Game.clean_old())


class DeleteGame(RequestHandler):
    def get(game_id, self):
        self.response.headers['Content-Type'] = 'text/plain'
        if int(game_id) < 1000 and not paramFlag(self, "override"):
            self.response.status = 403
            self.response.write("No.")
        game = Game.with_id(game_id)
        if game:
            game.clean_up()
            self.response.status = 200
            self.response.write("All according to daijobu")
        else:
            self.response.status = 401
            self.response.write("The game... was already dead...")


class ActiveGames(RequestHandler):
    def get(self, hours=12):
        self.response.headers['Content-Type'] = 'text/html'
        title = "Games active in the last %s hours" % hours
        body = ""
        games = Game.query(Game.last_update > datetime.now() - timedelta(hours=hours)).fetch()
        if not len(games):
            games = Game.query().fetch()
            if not len(games):
                title = "No active games found!"
            else:
                title = "All active games"
        
        for game in sorted(games, key=lambda x: x.last_update, reverse=True):
            id = game.key.id()
            game_link = uri_for('game-show-history', game_id=id)
            map_link = uri_for('map-render', game_id=id)
            body += "<li><a href='%s'>Game #%s</a> (<a href='%s'>(Map)</a>) (Last update: %s ago)</li>" % (game_link, id, map_link, datetime.now() - game.last_update)
        out = "<html><head><title>%s - ORCS</title></head><body>" % title
        if body:
            out += "<h4>%s:</h4><ul>%s</ul></body</html>" % (title, body)
        else:
            out += "<h4>%s</h4></body></html>" % title
        self.response.write(out)



class FoundPickup(RequestHandler):
    def old(self, game_id, player_id, coords, kind, id):
        return self.get(game_id, player_id, coords, kind, id, old=True)        
        
    def get(self, game_id, player_id, coords, kind, id, old=False):
        game = Game.with_id(game_id)
        if not game:
            self.response.status = 412
            self.response.write(self.response.status)
            return
        remove = paramFlag(self, "remove")
        coords = int(coords)
        if coords in coord_correction_map:
            coords = coord_correction_map[coords]
        if coords not in all_locs:
            log.warning("Coord mismatch error! %s not in all_locs or correction map. Sync %s.%s, pickup %s|%s" % (
            coords, game_id, player_id, kind, id))
        dedup = not paramFlag(self, "override") and not remove and game.mode.is_dedup()
        pickup = Pickup.n(kind, id)
        if not pickup:
            log.error("Couldn't build pickup %s|%s" % (kind, id))
            self.response.status = 406
            return
        self.response.status = game.found_pickup(player_id, pickup, coords, remove, dedup)
        self.response.write(self.response.status)


class Update(RequestHandler):
    def get(self, game_id, player_id, x, y):
        self.response.headers['Content-Type'] = 'text/plain'
        game = Game.with_id(game_id)
        if not game:
            self.response.status = 412
            self.response.write(self.response.status)
            return
        p = game.player(player_id)
        Cache.setPos(game_id, player_id, x, y)
        self.response.write(p.bitfields)


# post-refactor. uses different URL (with /), for dll switching
class GetUpdate(RequestHandler):
    def get(self, game_id, player_id, x, y):
        self.response.headers['Content-Type'] = 'text/plain'
        game = Game.with_id(game_id)
        if not game:
            self.response.status = 412
            self.response.write(self.response.status)
            return
        p = game.player(player_id)
        Cache.setPos(game_id, player_id, x, y)
        self.response.write(p.output())


class ShowHistory(RequestHandler):
    def get(self, game_id):
        self.response.headers['Content-Type'] = 'text/plain'
        game = Game.with_id(game_id)
        if game:
            output = game.summary()
            output += "\nHistory:"
            for hl, pid in sorted([(h, p.key.id().partition('.')[2]) for p in game.get_players() for h in p.history if
                                   h.pickup().share_type != ShareType.NOT_SHARED], key=lambda x: x[0].timestamp,
                                  reverse=True):
                output += "\n\t\t Player %s %s" % (pid, hl.print_line(game.start_time))
            self.response.status = 200
            self.response.write(output)
        else:
            self.response.status = 404
            self.response.out.write("Game %s not found!" % game_id)


class SeedGenForm(RequestHandler):
    def get(self):
        path = os.path.join(os.path.dirname(__file__), 'index.html')
        template_values = {'latest_dll': "N/A", 'plando_version': PLANDO_VER, 'seed': random.randint(10000000, 100000000)}
        self.response.out.write(template.render(path, template_values))

class Vanilla(RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'application/x-gzip'
        self.response.headers['Content-Disposition'] = 'attachment; filename=randomizer.dat'
        self.response.out.write(vanilla_seed)


class SignalCallback(RequestHandler):
    def get(self, game_id, player_id, signal):
        self.response.headers['Content-Type'] = 'text/plain'
        game = Game.with_id(game_id)
        if not game:
            self.response.status = 412
            self.response.write(self.response.status)
            return
        p = game.player(player_id)
        p.signal_conf(signal)
        self.response.status = 200
        self.response.write("cleared")


class HistPrompt(RequestHandler):
    def get(self, game_id):
        return redirect("/game/%s/history" % game_id)


class SignalSend(RequestHandler):
    def get(self, game_id, player_id, signal):
        self.response.headers['Content-Type'] = 'text/plain'
        game = Game.with_id(game_id)
        if not game:
            self.response.status = 412
            self.response.write(self.response.status)
            return
        p = game.player(player_id)
        p.signal_send(signal)
        self.response.status = 200
        self.response.write("sent")


class ListPlayers(RequestHandler):
    def get(self, game_id):
        game = Game.with_id(game_id)
        outlines = []
        for p in game.get_players():
            outlines.append("Player %s: %s" % (p.key.id(), p.bitfields))
            outlines.append("\t\t" + "\n\t\t".join(
                [hl.print_line(game.start_time) for hl in p.history if hl.pickup().share_type != ShareType.NOT_SHARED]))

        self.response.headers['Content-Type'] = 'text/plain'
        self.response.status = 200
        self.response.out.write("\n".join(outlines))


class RemovePlayer(RequestHandler):
    def get(self, game_id, pid):
        key = ".".join([game_id, pid])
        game = Game.with_id(game_id)
        if key in [p.id() for p in game.players]:
            game.remove_player(key)
            return redirect("game/%s/players" % game_id)
        else:
            self.response.headers['Content-Type'] = 'text/plain'
            self.response.status = 404
            self.response.out.write("player %s not in %s" % (key, game.players))


class ShowCache(RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'text/plain'
        self.response.write(str(Cache.pos) + "\n" + str(Cache.hist))


class ClearCache(RequestHandler):
    def get(self):
        Cache.pos = {}
        Cache.hist = {}
        self.redirect("/cache")


class SetSeed(RequestHandler):
    def get(self, game_id, player_id):
        seedlines = []
        lines = paramVal(self, "seed").split(",")
        game = Game.with_id(game_id)
        hist = Cache.getHist(game_id)
        if not hist:
            Cache.setHist(game_id, player_id, [])
        Cache.setPos(game_id, player_id, 189, -210)
        if not game:
            flags = lines[0].split("|")
            mode_opt = [f[5:] for f in flags if f.lower().startswith("mode=")]
            shared_opt = [f[7:].split(" ") for f in flags if f.lower().startswith("shared=")]
            mode = mode_opt[0] if mode_opt else None
            shared = shared_opt[0] if shared_opt else None
            game = Game.new(_mode=mode, _shared=shared, id=game_id)
            game.put()
        else:
            game.sanity_check()  # cheap if game is short!
        for l in lines[1:]:
            line = l.split("|")
            if len(line) < 3:
                log.error("malformed seed line %s, skipping" % l)
            else:
                seedlines.append("%s:%s" % (line[0], Pickup.name(line[1], line[2])))
        player = game.player(player_id)
        player.seed = "\n".join(seedlines)
        player.put()
        self.response.headers['Content-Type'] = 'text/plain'
        self.response.status = 200
        self.response.out.write("ok")


class ShowMap(RequestHandler):
    def get(self, game_id):
        path = os.path.join(os.path.dirname(__file__), 'map/build/index.html')
        template_values = {'app': "gameTracker", 'title': "Game %s" % game_id, 'game_id': game_id,
                           'is_spoiler': paramFlag(self, 'sp'), 'logic_modes': paramVal(self, 'paths')}
        if debug and paramFlag(self, "from_test"):
            game = Game.with_id(game_id)
            pos = Cache.getPos(game_id)
            hist = Cache.getHist(game_id)
            seeds = [p.seed for p in game.get_players()] if game else []
            if any([x is None for x in [game, pos, hist]+seeds]):
                return redirect(uri_for('tests-map-gid', game_id=game_id,from_test=1))

        self.response.out.write(template.render(path, template_values))


class GetSeenLocs(RequestHandler):
    def get(self, game_id):
        self.response.headers['Content-Type'] = 'application/json'
        self.response.status = 200
        seenLocs = {}
        try:
            game = Game.with_id(game_id)
            hist = Cache.getHist(game_id)
            if not game:
                self.response.status = 404
                return
            if not hist:
                hist = game.rebuild_hist()
            for player, history_lines in hist.items():
                seenLocs[player] = [hl.coords for hl in history_lines]
            self.response.out.write(json.dumps(seenLocs))
        except Exception as e:
            log.error("error getting seen locations for game %s! Returning partial list" % game_id, e)
            self.response.out.write(json.dumps(seenLocs))


class GetSeed(RequestHandler):
    def get(self, game_id, player_id):
        game = Game.with_id(game_id)
        if not game:
            self.response.status = 404
            self.response.write(self.response.status)
            return
        player = game.player(player_id)
        self.response.headers['Content-Type'] = 'text/plain'
        self.response.status = 200
        self.response.out.write(player.seed)


class GetReachable(RequestHandler):
    def get(self, game_id):
        self.response.headers['Content-Type'] = 'application/json'
        hist = Cache.getHist(game_id)
        reachable_areas = {}
        if not hist or not paramVal(self, "modes"):
            self.response.status = 404
            self.response.write(json.dumps(reachable_areas))
            return
        modes = paramVal(self, "modes").split(" ")
        self.response.status = 200
        game = Game.with_id(game_id)
        shared_hist = []
        shared_coords = set()
        if game and game.mode == MultiplayerGameType.SHARED:
            shared_hist = [hl for hls in hist.values() for hl in hls if hl.pickup().share_type in game.shared]
            shared_coords = set([hl.coords for hl in shared_hist])
        for player, personal_hist in hist.items():
            print hist.keys(), player, player in hist
            player_hist = [hl for hl in hist[player] if hl.coords not in shared_coords] + shared_hist
            state = PlayerState([(h.pickup_code, h.pickup_id, 1, h.removed) for h in player_hist])
            areas = {}
            for area, reqs in Map.get_reachable_areas(state, modes).items():
                areas[area] = [{item: count for (item, count) in req.cnt.items()} for req in reqs if len(req.cnt)]
            reachable_areas[player] = areas
        self.response.out.write(json.dumps(reachable_areas))


class GetPlayerPositions(RequestHandler):
    def get(self, game_id):
        self.response.headers['Content-Type'] = 'application/json'
        pos = Cache.getPos(game_id)
        if pos:
            self.response.status = 200
            players = {}
            for p, (x, y) in pos.items():
                players[p] = [y, x]  # bc we use tiling software, this is lat/lng
            self.response.out.write(json.dumps(players))
        else:
            self.response.status = 404


class Plando(RequestHandler):
    def get(self):
        path = os.path.join(os.path.dirname(__file__), 'map/build/index.html')
        template_values = {'app': "plandoBuilder", 'title': "Plandomizer Editor " + PLANDO_VER,
                           'pathmode': paramVal(self, 'pathmode'), 'HC': paramVal(self, 'HC'),
                           'EC': paramVal(self, 'EC'), 'AC': paramVal(self, 'AC'), 'KS': paramVal(self, 'KS'),
                           'skills': paramVal(self, 'skills'), 'tps': paramVal(self, 'tps'),  'evs': paramVal(self, 'evs')}
        self.response.out.write(template.render(path, template_values))


class PlandoReachable(RequestHandler):
    def get(self):
        modes = paramVal(self, "modes").split(" ")
        codes = []
        if paramVal(self, "codes"):
            for codemulti in paramVal(self, "codes").split(" "):
                code, _, times = codemulti.partition(":")
                codes.append(tuple(code.split("|")+[int(times), False]))
        self.response.headers['Content-Type'] = 'application/json'
        self.response.status = 200

        areas = {}
        for area, reqs in Map.get_reachable_areas(PlayerState(codes), modes).items():
            areas[area] = [{item: count for (item, count) in req.cnt.items()} for req in reqs if len(req.cnt)]

        self.response.out.write(json.dumps(areas))


def clone_entity(e, **extra_args):
    klass = e.__class__
    props = dict((v._code_name, v.__get__(e, klass)) for v in klass._properties.itervalues() if
                 type(v) != ndb.ComputedProperty)
    props.update(extra_args)
    return klass(**props)


class PlandoRename(RequestHandler):
    def get(self, author, old_name, new_name):
        user = users.get_current_user()
        if user:
            dispname = user.email().partition("@")[0]
            if dispname == author:
                old_seed = Seed.get_by_id("%s:%s" % (author, old_name))
                if not old_seed:
                    log.error("couldn't find old seed when trying to rename!")
                    self.response.status = 404
                    return
                new_seed = clone_entity(old_seed, id="%s:%s" % (author, new_name), name=new_name)
                if new_seed.put():
                    if not paramFlag(self, "cp"):
                        old_seed.key.delete()
                    self.redirect('/plando/%s/%s' % (author, new_name))
                else:
                    log.error("Failed to rename seed")
                    self.response.status = 500
            else:
                log.error("Auth failed, logged in as %s, trying to edit %s's seed" % (dispname, author))
                self.response.status = 401
        else:
            log.error("no auth D:")
            self.response.status = 401


class PlandoDelete(RequestHandler):
    def get(self, author, seed_name):
        user = users.get_current_user()
        if user:
            dispname = user.email().partition("@")[0]
            if dispname == author:
                seed = Seed.get_by_id("%s:%s" % (author, seed_name))
                if seed:
                    seed.key.delete()
                    self.redirect('/plando/%s' % author)
                else:
                    log.error("couldn't find seed!")
                    self.response.status = 404
            else:
                log.error("Auth failed, logged in as %s, trying to edit %s's seed" % (dispname, author))
                self.response.status = 401
        else:
            log.error("no auth D:")
            self.response.status = 401


class PlandoToggleHide(RequestHandler):
    def get(self, author, seed_name):
        user = users.get_current_user()
        if user:
            dispname = user.email().partition("@")[0]
            if dispname == author:
                seed = Seed.get_by_id("%s:%s" % (author, seed_name))
                if seed:
                    seed.hidden = not (seed.hidden or False)
                    seed.put()
                    self.response.out.write(seed.hidden)
                    self.redirect('/plando/%s/%s' % (author, seed_name))
                else:
                    log.error("couldn't find seed!")
                    self.response.status = 404
            else:
                log.error("Auth failed, logged in as %s, trying to edit %s's seed" % (dispname, author))
                self.response.status = 401
        else:
            log.error("no auth D:")
            self.response.status = 401


class PlandoUpload(RequestHandler):
    def post(self, author, plando):
        user = users.get_current_user()
        if user:
            dispname = user.email().partition("@")[0]
            if dispname == author:
                id = author + ":" + plando
                seedLines = self.request.POST["seed"]
                desc = self.request.POST["desc"]
                old_name = paramVal(self, "old_name")
                if old_name:
                    old_seed = Seed.get_by_id("%s:%s" % (author, old_name))
                else:
                    old_seed = Seed.get_by_id("%s:%s" % (author, plando))
                seed = Seed.from_plando(seedLines.split("!"), author, plando, desc)
                if old_seed:
                    seed.hidden = old_seed.hidden
                res = seed.put()
                if res and old_name and old_name != plando:
                    if not old_seed:
                        log.error("couldn't find old seed when trying to rename!")
                    else:
                        old_seed.key.delete()
                self.response.headers['Content-Type'] = 'text/plain'
                self.response.status = 200
                self.response.out.write(res)
            else:
                log.error("Auth failed, logged in as %s, trying to edit %s's seed" % (dispname, author))
                self.response.status = 401
        else:
            log.error("no auth D:")
            self.response.status = 401


class PlandoView(RequestHandler):
    def get(self, author, plando):
        user = users.get_current_user()
        dispname = "Guest"
        if user:
            dispname = user.email().partition("@")[0]
        id = author + ":" + plando
        seed = Seed.get_by_id(id)
        if seed:
            hidden = seed.hidden or False
            if not (hidden and dispname != author):
                self.response.status = 200
                self.response.headers['Content-Type'] = 'text/html'
                path = os.path.join(os.path.dirname(__file__), 'map/build/index.html')
                template_values = {'app': "seedDisplay", 'title': "%s by %s" % (plando, author),
                                   'players': seed.players, 'seed_data': seed.to_lines()[0],
                                   'seed_name': plando, 'author': author, 'authed': True, 'seed_desc': seed.description,
                                   'user': dispname, 'game_id': Game.get_open_gid()}
                if hidden:
                    template_values['seed_hidden'] = True

                self.response.out.write(template.render(path, template_values))
                return
        self.response.status = 404
        self.response.headers['Content-Type'] = 'text/plain'
        self.response.out.write("seed not found")


class PlandoEdit(RequestHandler):
    def get(self, author, plando):
        path = os.path.join(os.path.dirname(__file__), 'map/build/index.html')
        template_values = {'app': "plandoBuilder", 'title': "Plandomizer Editor " + PLANDO_VER, 'seed_name': plando}
        owner = False
        user = users.get_current_user()
        if user:
            dispname = user.email().partition("@")[0]
            owner = dispname == author
        id = author + ":" + plando
        if not owner:
            self.redirect('/login')
        else:
            seed = Seed.get_by_id(id)
            template_values['user'] = dispname
            template_values['authed'] = "True"
            if seed:
                template_values['seed_desc'] = seed.description
                template_values['seed_hidden'] = seed.hidden or False
                template_values['seed_data'] = "\n".join(seed.to_plando_lines())
            self.response.out.write(template.render(path, template_values))


class PlandoOld(RequestHandler):
    def get(self):
        path = os.path.join(os.path.dirname(__file__), 'map/build/index.html')
        user = users.get_current_user()
        if user:
            dispname = user.email().partition("@")[0]
            self.redirect("/plando/%s/seedName/edit" % dispname)
        else:
            template_values = {'app': "plandoBuilder", 'title': "Plandomizer Editor " + PLANDO_VER,
                               'pathmode': paramVal(self, 'pathmode'), 'HC': paramVal(self, 'HC'),
                               'EC': paramVal(self, 'EC'), 'AC': paramVal(self, 'AC'), 'KS': paramVal(self, 'KS'),
                               'skills': paramVal(self, 'skills'), 'tps': paramVal(self, 'tps'), 'evs': paramVal(self, 'evs')}
            self.response.out.write(template.render(path, template_values))


class HandleLogin(RequestHandler):
    def get(self):
        user = users.get_current_user()
        if user:
            dispname = user.email().partition("@")[0]
            self.redirect('plando/' + dispname)
        else:
            self.redirect(users.create_login_url(self.request.uri))


class HandleLogout(RequestHandler):
    def get(self):
        user = users.get_current_user()
        if user:
            self.redirect(users.create_logout_url("/"))
        else:
            self.redirect("/")

class PlandoFillGen(RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'text/plain'
        qparams = self.request.GET
        forced_assignments = dict([(int(a), b) for (a,b) in ([ tuple(fass.split(":")) for fass in qparams['fass'].split("|")] if "fass" in qparams else [])])

        param_key = SeedGenParams.from_url(qparams)
        params = param_key.get()
        if params.generate(preplaced=forced_assignments):
            self.response.out.write(params.get_seed(1))
        else:
            self.response.status = 422

class PlandoDownload(RequestHandler):
    def get(self, author, plando):
        owner = False
        user = users.get_current_user()
        if user:
            dispname = user.email().partition("@")[0]
            owner = dispname == author
        id = author + ":" + plando
        seed = Seed.get_by_id(id)
        if seed:
            gid = paramVal(self, "gid")
            pid = paramVal(self, "pid")
            syncFlag = "Sync%s.%s" % (gid, pid)
            self.response.status = 200
            self.response.headers['Content-Type'] = 'application/x-gzip' if not debug else     'text/plain'
            self.response.headers['Content-Disposition'] = 'attachment; filename=randomizer.dat' if not debug else ""
            seedlines = seed.to_lines(player=int(pid), extraFlags=[syncFlag])
            rand = random.Random()
            rand.seed(seed.name)
            flagline = seedlines.pop(0)
            rand.shuffle(seedlines)
            seedlines.insert(0, flagline)
            self.response.out.write("\n".join(seedlines))
        else:
            self.response.status = 404
            self.response.headers['Content-Type'] = 'text/plain'
            self.response.out.write("seed not found")


        

class AllAuthors(RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'text/html'
        seeds = Seed.query(Seed.hidden != True)
        out = '<html><head><title>All Plando Authors</title></head><body><h5>All Seeds</h5><ul style="list-style-type:none;padding:5px">'
        authors = Counter([seed.author for seed in seeds])
        for author, cnt in authors.most_common():
            if cnt > 0:
                url = "%s/plando/%s" % (base_site, author)
                out += '<li style="padding:2px"><a href="%s">%s</a> (%s plandos)</li>' % (url, author, cnt)
        out += "</ul></body></html>"
        self.response.out.write(out)


class AuthorIndex(RequestHandler):
    def get(self, author):
        self.response.headers['Content-Type'] = 'text/html'
        owner = False
        user = users.get_current_user()
        if user:
            dispname = user.email().partition("@")[0]
            owner = dispname == author

        query = Seed.query(Seed.author == author)
        if not owner:
            query = query.filter(Seed.hidden != True)
        seeds = query.fetch()

        if len(seeds):
            out = '<html><head><title>Seeds by %s</title></head><body><div>Seeds by %s:</div><ul style="list-style-type:none;padding:5px">' % (
            author, author)
            for seed in seeds:
                url = "%s/plando/%s/%s" % (base_site, author, seed.name)
                flags = ",".join(seed.flags)
                out += '<li style="padding:2px"><a href="%s">%s</a>: %s (%s players, %s)' % (
                url, seed.name, seed.description, seed.players, flags)
                if owner:
                    out += ' <a href="%s/edit">Edit</a>' % url
                    if seed.hidden:
                        out += " (hidden)"
                out += "</li>"
            out += "</ul></body></html>"
            self.response.write(out)
        else:
            if owner:
                self.response.write(
                    "<html><body>You haven't made any seeds yet! <a href='/plando/%s/newseed/edit'>Start a new seed</a></body></html>" % author)
            else:
                self.response.write('<html><body>No seeds by user %s</body></html>' % author)


class QuickStart(RequestHandler):
    def get(self):
        self.response.write("""<html><body><pre>Misc info:
- From <a href=http://orirandocoopserver.appspot.com/activeGames>this page</a> you can see a list of active games, and follow links to see a game's history or an active map. 
- If you set game mode to 4 from the seed gen page, you can generate seeds that play out like solo rando seeds but with map tracking.
- The <a href=http://orirandocoopserver.appspot.com/>seed generator</a> currently produces multiplayer seeds by splitting up important pickups, giving each to 1 player and the rest of the players a dummy pickup. With split: hot set, that dummy pickup is warmth returned: otherwise it's 1-100 exp (chosen randomly).
- The plandomizer editor is located <a href=http://orirandocoopserver.appspot.com/plando/simple/>here</a>. The interface is graphical: click on pickups or select them using the zone/location dropdowns, and then fill in what you want to be there. (You may need to change or disable the logic options if your plando does things outside of the logic).
- You can generate a visual spoiler for any seed by importing it into the plando (paste the full text of the .dat file into the text box).
- If you have any questions or bug reports please ping me  ( @SOL | Eiko  on the ori discord)
</pre></body></html>""")


class Bingo(RequestHandler):
    def get(self, cards = 25):
        self.response.headers['Content-Type'] = 'text/plain'
        self.response.write(Card.get_json(int(cards)))

class MapTest(RequestHandler):
    def get(self, game_id = 101):
        game_id = int(game_id)
        if not debug:
            return redirect("/")
        game = Game.with_id(game_id)
        if game:
            game.clean_up()
        seedlines = []
        seed = "Open,Standard,Clues,mode=Shared|shared=WorldEvents+Skills+Teleporters,-280256|EC|1|Glades,-1680104|EX|100|Grove,-12320248|TP|Ginso|Forlorn,-10440008|EX|100|Misty,799776|EV|5|Glades,-120208|EC|1|Glades,1519708|SH|@Skill For Player 1@|Blackroot,1799708|KS|1|Blackroot,1959768|RB|9|Blackroot,-1560272|KS|1|Glades,-600244|EX|46|Glades,-3160308|HC|1|Glades,-2840236|EX|15|Glades,-3360288|MS|1|Glades,-2480208|EX|6|Glades,-2400212|AC|1|Glades,-1840228|HC|1|Glades,919772|KS|1|Glades,-2200184|KS|1|Glades,-1800156|KS|1|Glades,24|KS|1|Mapstone,2919744|KS|1|Blackroot,-1840196|SK|2|Glades,-800192|AC|1|Glades,-2080116|SK|14|Valley,-560160|EX|32|Grove,1479880|AC|1|Grove,599844|KS|1|Grove,2999904|RB|1|Grove,6999916|KS|1|Swamp,6159900|HC|1|Swamp,3639880|EX|27|Grove,5119584|MS|1|Grotto,6199596|MS|1|Grotto,5719620|HC|1|Grotto,5879616|KS|1|Grotto,6279880|KS|1|Swamp,5119900|EX|67|Swamp,39804|EX|9|Glades,28|EV|5|Mapstone,7839588|EX|51|Grotto,2999808|EC|1|Grove,3039696|SK|50|Blackroot,3119768|EX|33|Blackroot,-2200148|HC|1|Glades,-2240084|EX|53|Valley,4199828|EX|15|Grotto,32|AC|1|Mapstone,3439744|EX|44|Blackroot,-160096|EC|1|Grove,4239780|SK|5|Grotto,-480168|RB|13|Glades,-1560188|KS|1|Glades,-2160176|EX|50|Glades,3319936|KS|1|Grove,4759860|KS|1|Grotto,4319892|EX|82|Grotto,3639888|EC|1|Grove,5799932|EX|114|Swamp,4479832|EX|77|Grotto,5439640|EC|1|Grotto,5639752|EX|56|Grotto,0|EX|62|Grotto,4039612|AC|1|Grotto,3919624|EX|27|Grotto,4959628|EV|5|Grotto,4639628|EX|97|Grotto,4479568|EC|1|Grotto,7559600|EX|30|Grotto,3919688|EX|10|Blackroot,5399780|EX|32|Grotto,5119556|MS|1|Grotto,4439632|EX|40|Grotto,4359656|EX|52|Grotto,4919600|EX|97|Grotto,-1800088|EX|66|Valley,639888|EX|97|Grove,36|EV|5|Mapstone,2559800|EX|83|Glades,-2480280|EX|44|Glades,3199820|EC|1|Grove,1719892|RB|15|Grove,2599880|HC|1|Grove,4079964|EX|30|Swamp,4999892|KS|1|Swamp,5399808|KS|1|Grotto,5519856|EV|5|Grotto,3399820|EX|63|Grove,3279644|MS|1|Grotto,7199904|EV|5|Swamp,8599904|RB|0|Swamp,40|EX|99|Mapstone,799804|EX|22|Glades,6359836|EX|103|Swamp,4479704|EX|82|Grotto,5200140|AC|1|Ginso,5280264|KS|1|Ginso,5080304|MS|1|Ginso,5280296|EX|175|Ginso,5400100|EX|92|Ginso,6639952|KS|1|Swamp,2719900|EV|5|Grove,5320328|AC|1|Ginso,5320488|AC|1|Ginso,5080496|KS|1|Ginso,5400276|EC|1|Ginso,2759624|EV|5|Blackroot,959960|AC|1|Grove,6399872|EX|156|Swamp,4319860|EX|40|Grotto,4319676|AC|1|Blackroot,7679852|RB|0|Swamp,5359824|EX|148|Grotto,8839900|KS|1|Swamp,5160384|EX|118|Ginso,5280404|EX|153|Ginso,5360432|KS|1|Ginso,3879576|AC|1|Blackroot,3359580|KS|1|Blackroot,719620|KS|1|Blackroot,1759964|EX|125|Grove,2239640|AC|1|Blackroot,1240020|HC|1|Grove,559720|KS|1|Glades,39756|EX|73|Glades,-400240|RB|0|Glades,-3559936|EX|49|Valley,-4199936|HC|1|Valley,-3600088|AC|1|Valley,1839836|KS|1|Grove,3519820|KS|1|Grove,5919864|KS|1|Swamp,4199724|EX|171|Grotto,3559792|KS|1|Grotto,3359784|AC|1|Grove,-3200164|EX|155|Valley,3959588|KS|1|Grotto,7599824|KS|1|Swamp,6839792|EX|183|Swamp,7959788|HC|1|Swamp,8719856|EX|61|Swamp,4599508|KS|1|Blackroot,3039472|EV|5|Blackroot,5239456|EC|1|Blackroot,-4600020|MS|1|Valley,-5479948|EX|121|Sorrow,-6800032|KS|1|Misty,-8240012|EX|265|Misty,-2919980|AC|1|Valley,-5719844|EX|62|Sorrow,-5119796|EX|267|Sorrow,-4879680|EX|35|Sorrow,-5039728|RB|1|Sorrow,-5159700|MS|1|Sorrow,-5959772|KS|1|Sorrow,-9799980|EX|86|Misty,-10760004|RB|11|Misty,-10120036|EX|48|Misty,-10759968|HC|1|Misty,-4600188|EX|147|Valley,-4160080|EX|25|Valley,-4680068|RB|6|Valley,-3520100|KS|1|Valley,-5640092|EX|152|Valley,-6119704|EX|1|Sorrow,-4359680|EC|1|Sorrow,-8400124|EX|315|Misty,-7960144|EX|94|Misty,-9120036|EX|315|Misty,-7680144|AC|1|Misty,-11040068|AC|1|Misty,1720000|EC|1|Grove,2519668|EX|253|Blackroot,4560564|EC|1|Ginso,-6719712|EX|178|Sorrow,-6079672|EC|1|Sorrow,-6119656|RB|1|Sorrow,-6039640|EX|140|Sorrow,-6159632|EX|297|Sorrow,-6279608|EX|14|Sorrow,8|EX|9|Misty,44|AC|1|Mapstone,48|EV|5|Mapstone,-7040392|EX|62|Forlorn,-8440352|KS|1|Forlorn,-8920328|MS|1|Forlorn,-8880252|EX|256|Forlorn,-8720256|EX|154|Forlorn,5320660|EX|291|Ginso,5360732|AC|1|Ginso,5320824|AC|1|Ginso,5160864|KS|1|Ginso,4|EX|135|Ginso,6080608|AC|1|Ginso,-6799732|AC|1|Sorrow,-6319752|AC|1|Sorrow,-8160268|AC|1|Forlorn,-5160280|AC|1|Valley,-5400236|EX|236|Valley,-10839992|EX|284|Misty,7639816|AC|1|Swamp,-4559584|RB|6|Sorrow,-4159572|RB|13|Sorrow,-5479592|EX|382|Sorrow,-5919556|KS|1|Sorrow,-6280316|EV|5|Forlorn,12|EX|277|Forlorn,52|MS|1|Mapstone,1920384|KS|1|Horu,1480360|MS|1|Horu,2480400|EX|291|Horu,-6080316|AC|1|Forlorn,1880164|RB|12|Horu,2520192|AC|1|Horu,1600136|KS|1|Horu,-1919808|AC|1|Horu,-319852|AC|1|Horu,120164|EX|128|Horu,1280164|EX|115|Horu,960128|HC|1|Horu,3160244|EX|235|Horu,20|EC|1|Horu,1040112|AC|1|Horu,-8600356|AC|1|Forlorn,-6959592|EX|15|Sorrow,-6479528|HC|1|Sorrow,-4799416|EX|382|Sorrow,4680612|EV|5|Ginso,56|EX|322|Mapstone,-5159576|AC|1|Sorrow,16|EV|5|Sorrow,5040476|RB|21|Ginso,4559492|RB|19|Blackroot,399844|RB|19|Grove,-1680140|EV|5|Glades,9119928|EV|5|Swamp,2079568|EV|1|Blackroot,3279920|RB|17|Grove,-4600256|RB|21|Valley,-4440152|RB|21|Valley,919908|RB|17|Grove,1599920|RB|17|Grove,-11880100|RB|21|Misty,-5400104|EV|5|Valley,-6720040|RB|19|Misty,5039560|RB|17|Grotto,5280500|EV|5|Ginso,5160336|EV|5|Ginso"
        lines = seed.split(",")
        flags = lines[0].split("|")
        mode_opt = [f[5:] for f in flags if f.lower().startswith("mode=")]
        shared_opt = [f[7:].split("+") for f in flags if f.lower().startswith("shared=")]
        mode = mode_opt[0] if mode_opt else None
        shared = shared_opt[0] if shared_opt else None
        for l in lines[1:]:
            line = l.split("|")
            if len(line) < 3:
                log.error("malformed seed line %s, skipping" % l)
            else:
                seedlines.append("%s:%s" % (line[0], Pickup.name(line[1], line[2])))
        game = Game.new(_mode=mode, _shared=shared, id=game_id)
        game.put()
        for player_id in [1,2,3]:
            game = Game.with_id(game_id)
            hist = Cache.getHist(game_id)
            if not hist:
                Cache.setHist(game_id, player_id, [])
            Cache.setPos(game_id, player_id, 189, -210)
            player = game.player(player_id)
            player.seed = "\n".join(seedlines)
            player.put()
        url = uri_for("map-render", game_id=game_id, from_test=1)
        return redirect(url)


class LogicHelper(RequestHandler):
    def get(self):
        path = os.path.join(os.path.dirname(__file__), 'map/build/index.html')
        template_values = {'app': "logicHelper", 'title': "Logic Helper!", 'is_spoiler': "True",
                           'pathmode': paramVal(self, 'pathmode'), 'HC': paramVal(self, 'HC'),
                           'EC': paramVal(self, 'EC'), 'AC': paramVal(self, 'AC'), 'KS': paramVal(self, 'KS'),
                           'skills': paramVal(self, 'skills'), 'tps': paramVal(self, 'tps'), 'evs': paramVal(self, 'evs')}
        self.response.out.write(template.render(path, template_values))

class ReactLanding(RequestHandler):
    def get(self):
        user = users.get_current_user()
        dispname = user.email().partition("@")[0] if user else ""
        path = os.path.join(os.path.dirname(__file__), 'map/build/index.html')
        template_values = {'app': "mainPage", 'dll_last_update': "N/A", 'title': "Ori DE Randomizer", 'user': dispname}
        self.response.out.write(template.render(path, template_values))


class MakeSeedWithParams(RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'application/json'
        param_key = SeedGenParams.from_url(self.request.GET)
        params = param_key.get()
        if params.generate():
            resp = {"paramId": param_key.id(), "playerCount": params.players, 
                    "paths": "+".join(params.logic_paths), "flagLine": params.flag_line()}
            if params.tracking:
                game = Game.from_params(params, self.request.GET.get("game_id"))
                key = game.key
                resp["gameId"] = key.id()
            self.response.out.write(json.dumps(resp))
        else:
            self.response.status = 500
            self.response.out.write("Failed to build seed!")


class SeedGenJson(RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'application/json'
        param_key = SeedGenParams.from_url(self.request.GET)
        verbose_paths = self.request.GET.get("verbose_paths") is not None
        params = param_key.get()
        if params.generate(preplaced={}):
            players = []
            resp = {}
            if params.tracking:
                game = Game.from_params(params, self.request.GET.get("game_id"))
                key = game.key
                resp["map_url"] = uri_for("map-render", game_id=key.id(), paths=" ".join(params.logic_paths))
                resp["history_url"] = uri_for("game-show-history", game_id=key.id())
            for p in range(1, params.players+1):
                if params.tracking:
                    seed = params.get_seed(p, key.id(), verbose_paths)
                else:
                    seed = params.get_seed(p, verbose_paths = verbose_paths)
                spoiler = params.get_spoiler(p).replace("\n","\r\n")
                players.append({"seed": seed, "spoiler": spoiler, "spoiler_url": uri_for('gen-params-get-spoiler',params_id=param_key.id(), player=p)})
            resp["players"] = players
            self.response.out.write(json.dumps(resp))    
        else:
            log.error("param gen failed")
            self.response.status = 500

class GetParamMetadata(RequestHandler):
    def get(self, params_id):
        self.response.headers['Content-Type'] = 'application/json'
        params = SeedGenParams.with_id(params_id)
        if params:
            resp = {"playerCount": params.players, "paths": "+".join(params.logic_paths), "flagLine": params.flag_line()}
            self.response.out.write(json.dumps(resp))
        else:
            self.response.status = 404

class GetSeedFromParams(RequestHandler):
    def get(self, params_id):
        self.response.headers['Content-Type'] = 'text/plain'
        verbose_paths = self.request.GET.get("verbose_paths") is not None
        params = SeedGenParams.with_id(params_id)
        if params:
            player = int(self.request.GET.get("player_id",1))
            if params.tracking:
                game_id = self.request.GET.get("game_id")
                seed = params.get_seed(player, game_id, verbose_paths)

            else:
                seed = params.get_seed(player, verbose_paths = verbose_paths)
            if not debug:
                self.response.headers['Content-Type'] = 'application/x-gzip'
                self.response.headers['Content-Disposition'] = 'attachment; filename=randomizer.dat'
            self.response.out.write(seed)
        else:
            self.response.status = 404
            self.response.out.write("Param %s not found" % params_id)

class GetSpoilerFromParams(RequestHandler):
    def get(self, params_id):
        self.response.headers['Content-Type'] = 'text/plain'
        params = SeedGenParams.with_id(params_id)
        if params:
            player = int(self.request.GET.get("player",1))
            spoiler = params.get_spoiler(player)
            self.response.out.write(spoiler)
        else:
            self.response.status = 404
            self.response.out.write("Param %s not found" % params_id)

from util import picks_by_type_generator
class PicksByTypeGen(RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'application/json'
        self.response.out.write(picks_by_type_generator())
        return

app = WSGIApplication(routes=[
    # testing endpoints
    PathPrefixRoute('/tests', [
        Route('/', handler=TestRunner, name='tests-run'),
        Route('/map', handler=MapTest, name='tests-map', strict_slash=True),
        Route('/map/<game_id:\d+>', handler=MapTest, name='tests-map-gid', strict_slash=True),
    ]),
    Route('/tests', redirect_to_name='tests-run'),
    Route('/picksbytype', handler=PicksByTypeGen, name='picks-by-type-gen', strict_slash=True),

    PathPrefixRoute('/generator', [
        Route('/build', handler=MakeSeedWithParams, name="gen-params-build", strict_slash=True),
        Route('/metadata/<params_id:\d+>', handler=GetParamMetadata, name="gen-params-get-metadata", strict_slash=True),
        Route('/seed/<params_id:\d+>', handler=GetSeedFromParams, name="gen-params-get-seed", strict_slash=True),
        Route('/spoiler/<params_id:\d+>', handler=GetSpoilerFromParams, name="gen-params-get-spoiler", strict_slash=True),
        Route('/json', handler=SeedGenJson, name="gen-params-get-json")
    ]),

    
    PathPrefixRoute('/tracker/game/<game_id:\d+>', [
        Route('/', redirect_to_name="map-render"),
        Route('/map', handler=ShowMap, name='map-render', strict_slash=True),

        ] + list(PathPrefixRoute('/fetch', [
            Route('/pos', handler=GetPlayerPositions, name="map-fetch-pos"),
            Route('/seen', handler=GetSeenLocs, name="map-fetch-seen"),
            Route('/reachable', handler=GetReachable, name="map-fetch-reachable"),

            ] + list(PathPrefixRoute('/player/<player_id>', [
                Route('/seed', GetSeed, name="map-fetch-seed"),
                Route('/setSeed', SetSeed, name="map-set-seed"),        
            ]).get_routes())
        ).get_routes())
    ),

    # misc / top level endpoints
    Route('/bingo/<cards:\d+>', handler=Bingo,  name="bingo-json-cards", strict_slash=True),
    Route('/bingo', handler=Bingo, name="bingo-json", strict_slash=True),
    Route('/logichelper', handler=LogicHelper, name="logic-helper", strict_slash=True),
    (r'/logichelper/?', LogicHelper),
    (r'/faq/?', QuickStart),
    ('/vold', SeedGenForm),
    ('/', ReactLanding),
    (r'/activeGames/?', ActiveGames),
    (r'/clean/?', CleanUp),
    (r'/getNewGame/?', GetGameId),
    (r'/cache', ShowCache),
    (r'/cache/clear', ClearCache),
    (r'/login/?', HandleLogin),
    (r'/logout/?', HandleLogout),
    ('/vanilla', Vanilla),

    # new netcode endpoints
    PathPrefixRoute('/netcode/game/<game_id:\d+>/player/<player_id:[^/]+>', [
        Route('/found/<coords>/<kind>/<id>', handler=FoundPickup, name="netcode-player-found-pickup"),
        Route('/tick/<x:[^,]+>,<y>', handler=GetUpdate, name="netcode-player-tick"),
        Route('/callback/<signal>', handler=SignalCallback,  name="netcode-player-signal-callback"),
        Route('/setSeed', handler=SetSeed,  name="netcode-player-set-seed"),
    ]),

    # new game endpoints 
    PathPrefixRoute('/game/<game_id:\d+>', [
        Route('/delete', handler = DeleteGame, strict_slash=True, name="game-delete"),
        Route('/history', handler = ShowHistory, strict_slash=True, name="game-show-history"),
        Route('/players', handler = ListPlayers, strict_slash=True, name="game-list-players"),
        Route('/player/(\w+)/remove', handler = RemovePlayer, strict_slash=True, name="game-remove-player"),
        Route('/', redirect_to_name="game-show-history"),
    ]),

    # plando endpoints
    (r'/plando/reachable', PlandoReachable),
    (r'/plando/fillgen', PlandoFillGen),
    (r'/plando/simple/?', PlandoOld),
    (r'/plando/all/?', AllAuthors),
    (r'/plando/([^ ?=/]+)/([^ ?=/]+)/upload', PlandoUpload),
    (r'/plando/([^ ?=/]+)/([^ ?=/]+)/download', PlandoDownload),
    (r'/plando/([^ ?=/]+)/([^ ?=/]+)/edit/?', PlandoEdit),
    (r'/plando/([^ ?=/]+)/([^ ?=/]+)/delete', PlandoDelete),
    (r'/plando/([^ ?=/]+)/([^ ?=/]+)/rename/([^ ?=/]+)', PlandoRename),
    (r'/plando/([^ ?=/]+)/([^ ?=/]+)/hideToggle', PlandoToggleHide),
    (r'/plando/([^ ?=/]+)/?', AuthorIndex),
    (r'/plando/([^ ?=/]+)/([^ ?=/]+)/?', PlandoView),
], debug=True)
