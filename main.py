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
from enums import MultiplayerGameType, ShareType, Variation
from models import Game, Seed
from pickups import Pickup
from cache import Cache
from util import coord_correction_map, all_locs, picks_by_type_generator
from reachable import Map, PlayerState

PLANDO_VER = "0.5.1"
debug = os.environ.get('SERVER_SOFTWARE', '').startswith('Dev')
share_types = [ShareType.EVENT, ShareType.SKILL, ShareType.UPGRADE, ShareType.MISC, ShareType.TELEPORTER]

def paramFlag(s, f):
    return s.request.get(f, None) is not None

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
        games = [game for game in games if len([hl for players, hls in game.rebuild_hist().items() for hl in hls]) > 0]
        if not len(games):
            games = Game.query().fetch()
            games = [game for game in games if len([hl for players, hls in game.rebuild_hist().items() for hl in hls]) > 0]
            if not len(games):
                title = "No active games found!"
            else:
                title = "All active games"
        for game in sorted(games, key=lambda x: x.last_update, reverse=True):
            id = game.key.id()
            game_link = uri_for('game-show-history', game_id=id)
            map_link = uri_for('map-render', game_id=id)
            flags = ""
            if game.params:
                params = game.params.get()
                flags = params.flag_line()
            body += "<li><a href='%s'>Game #%s</a> <a href='%s'>Map</a> %s (Last update: %s ago)</li>" % (game_link, id, map_link, flags, datetime.now() - game.last_update)
        out = "<html><head><title>%s - Ori Rando Server</title></head><body>" % title
        if body:
            out += "<h4>%s:</h4><ul>%s</ul></body</html>" % (title, body)
        else:
            out += "<h4>%s</h4></body></html>" % title
        self.response.write(out)

class FoundPickup(RequestHandler):
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
            log.warning("Coord mismatch error! %s not in all_locs or correction map. Sync %s.%s, pickup %s|%s" % (coords, game_id, player_id, kind, id))
        dedup = not paramFlag(self, "override") and not remove and game.mode.is_dedup()
        pickup = Pickup.n(kind, id)
        if not pickup:
            log.error("Couldn't build pickup %s|%s" % (kind, id))
            self.response.status = 406
            return
        self.response.status = game.found_pickup(player_id, pickup, coords, remove, dedup)
        self.response.write(self.response.status)


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
            for hl, pid in sorted([(h, p.key.id().partition('.')[2]) for p in game.get_players() for h in p.history if h.pickup().is_shared(share_types)], key=lambda x: x[0].timestamp, reverse=True):
                output += "\n\t\t Player %s %s" % (pid, hl.print_line(game.start_time))
            self.response.status = 200
            self.response.write(output)
        else:
            self.response.status = 404
            self.response.out.write("Game %s not found!" % game_id)


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
            outlines.append("\t\t" + "\n\t\t".join([hl.print_line(game.start_time) for hl in p.history if hl.pickup().is_shared(share_types)]))

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
        lines = paramVal(self, "seed").split(",")
        game = Game.with_id(game_id)
        hist = Cache.getHist(game_id)
        if not hist:
            Cache.setHist(game_id, player_id, [])
        Cache.setPos(game_id, player_id, 189, -210)
        if not game:
            # TODO: this branch is now probably unnecessary.
            # experiment with deleting it.
            log.error("game was not already created! %s" % game_id)
            flags = lines[0].split("|")
            mode_opt = [f[5:] for f in flags if f.lower().startswith("mode=")]
            shared_opt = [f[7:].split(" ") for f in flags if f.lower().startswith("shared=")]
            mode = mode_opt[0] if mode_opt else None
            shared = shared_opt[0] if shared_opt else None
            game = Game.new(_mode=mode, _shared=shared, id=game_id)
            game.put()
        else:
            game.sanity_check()  # cheap if game is short!
        self.response.headers['Content-Type'] = 'text/plain'
        self.response.status = 200
        self.response.out.write("ok")


class ShowMap(RequestHandler):
    def get(self, game_id):
        path = os.path.join(os.path.dirname(__file__), 'map/build/index.html')
        template_values = {'app': "GameTracker", 'title': "Game %s" % game_id, 'game_id': game_id}
        if debug and paramFlag(self, "from_test"):
            game = Game.with_id(game_id)
            pos = Cache.getPos(game_id)
            hist = Cache.getHist(game_id)
            if any([x is None for x in [game, pos, hist]]):
                return redirect(uri_for('tests-map-gid', game_id=game_id, from_test=1))

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
        self.response.headers['Content-Type'] = 'application/json'
        game = Game.with_id(game_id)
        if not game or not game.params:
            self.response.status = 404
            self.response.write(json.dumps({}))
            return
        seed = {}
        params = game.params.get()
        for (coords, code, id, _) in params.get_seed_data(player_id):
            seed[coords] = Pickup.name(code, id)
        self.response.status = 200
        self.response.out.write(json.dumps(seed))


class GetGameData(RequestHandler):
    def get(self, game_id):
        self.response.headers['Content-Type'] = 'application/json'
        gamedata = {}
        game = Game.with_id(game_id)
        if not game or not game.params:
            self.response.write(json.dumps({"error": "Game not found!"}))
            self.response.status = 404
            return
        params = game.params.get()
        gamedata["paths"] = params.logic_paths
        gamedata["playerCount"] = params.players
        gamedata["closed_dungeons"] = Variation.CLOSED_DUNGEONS in params.variations
        gamedata["open_world"] = Variation.OPEN_WORLD in params.variations
        self.response.write(json.dumps(gamedata))


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
            shared_hist = [hl for hls in hist.values() for hl in hls if hl.pickup().is_shared(game.shared)]
            shared_coords = set([hl.coords for hl in shared_hist])
        for player, personal_hist in hist.items():
            player_hist = [hl for hl in hist[player] if hl.coords not in shared_coords] + shared_hist
            state = PlayerState([(h.pickup_code, h.pickup_id, 1, h.removed) for h in player_hist])
            areas = {}
            if state.has["KS"] > 8 and "standard-core" in modes:
                state.has["KS"] += 2 * (state.has["KS"] - 8)
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
        template_values = {'app': "PlandoBuilder", 'title': "Plandomizer Editor " + PLANDO_VER,
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
                codes.append(tuple(code.split("|") + [int(times), False]))
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
                seed_data = json.loads(self.request.POST["seed"])
                desc = self.request.POST["desc"]
                old_name = paramVal(self, "old_name")
                if old_name:
                    old_seed = Seed.get_by_id("%s:%s" % (author, old_name))
                else:
                    old_seed = Seed.get_by_id("%s:%s" % (author, plando))
                seed = Seed.from_plando(seed_data, author, plando, desc)
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
                template_values = {'app': "SeedDisplay", 'title': "%s by %s" % (plando, author),
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
        template_values = {'app': "PlandoBuilder", 'title': "Plandomizer Editor " + PLANDO_VER, 'seed_name': plando}
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
            template_values = {'app': "PlandoBuilder", 'title': "Plandomizer Editor (Beta)",
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
        forced_assignments = dict([(int(a), b) for (a, b) in ([tuple(fass.split(":")) for fass in qparams['fass'].split("|")] if "fass" in qparams else [])])

        param_key = SeedGenParams.from_url(qparams)
        params = param_key.get()
        if params.generate(preplaced=forced_assignments):
            self.response.out.write(params.get_seed(1))
        else:
            self.response.status = 422

class PlandoDownload(RequestHandler):
    def get(self, author, plando):
        id = author + ":" + plando
        seed = Seed.get_by_id(id)
        if seed:
            gid = paramVal(self, "gid")
            pid = paramVal(self, "pid")
            syncFlag = "Sync%s.%s" % (gid, pid)
            self.response.status = 200
            self.response.headers['Content-Type'] = 'application/x-gzip' if not debug else 'text/plain'
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
                url = "/plando/%s" % author
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
            out = '<html><head><title>Seeds by %s</title></head><body><div>Seeds by %s:</div><ul style="list-style-type:none;padding:5px">' % (author, author)
            for seed in seeds:
                url = "/plando/%s/%s" % (author, seed.name)
                flags = ",".join(seed.flags)
                out += '<li style="padding:2px"><a href="%s">%s</a>: %s (%s players, %s)' % (url, seed.name, seed.description, seed.players, flags)
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


class Bingo(RequestHandler):
    def get(self, cards=25):
        self.response.headers['Content-Type'] = 'text/plain'
        self.response.write(Card.get_json(paramFlag(self, "rando"), int(cards)))


class MapTest(RequestHandler):
    def get(self, game_id=101):
        if not debug:
            self.redirect("/")
        game_id = int(game_id)
        game = Game.with_id(game_id)
        if game:
            game.clean_up()
        url = "/generator/build?key_mode=Free&gen_mode=Balanced&var=OpenWorld&var=WorldTour&path=casual-core&path=casual-dboost&exp_pool=10000&cell_freq=40&relics=10&players=3&sync_mode=Shared&sync_shared=WorldEvents&sync_shared=Teleporters&sync_shared=WorldEvents&sync_shared=Skills&sync_hints=1&test_map_redir=%s&seed=%s" % (game_id, random.randint(100000,1000000))
        self.redirect(url)

class DiscordRedirect(RequestHandler):
    def get(self):
        self.redirect("https://discord.gg/TZfue9V")

class LogicHelper(RequestHandler):
    def get(self):
        path = os.path.join(os.path.dirname(__file__), 'map/build/index.html')
        template_values = {'app': "LogicHelper", 'title': "Logic Helper!", 'is_spoiler': "True",
                           'pathmode': paramVal(self, 'pathmode'), 'HC': paramVal(self, 'HC'),
                           'EC': paramVal(self, 'EC'), 'AC': paramVal(self, 'AC'), 'KS': paramVal(self, 'KS'),
                           'skills': paramVal(self, 'skills'), 'tps': paramVal(self, 'tps'), 'evs': paramVal(self, 'evs')}
        self.response.out.write(template.render(path, template_values))

class ReactLanding(RequestHandler):
    def get(self):
        user = users.get_current_user()
        dispname = user.email().partition("@")[0] if user else ""
        path = os.path.join(os.path.dirname(__file__), 'map/build/index.html')
        template_values = {'app': "MainPage", 'dll_last_update': "N/A", 'title': "Ori DE Randomizer", 'user': dispname}
        self.response.out.write(template.render(path, template_values))


class MakeSeedWithParams(RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'application/json'
        param_key = SeedGenParams.from_url(self.request.GET)
        params = param_key.get()
        if params.generate():
            resp = {"paramId": param_key.id(), "playerCount": params.players, "flagLine": params.flag_line()}
            if params.tracking:
                game = Game.from_params(params, self.request.GET.get("game_id"))
                game_id = game.key.id()
                resp["gameId"] = game_id
                if debug and paramFlag(self, "test_map_redir"):
                    self.redirect(uri_for("map-render", game_id=resp["gameId"], from_test=1))
            self.response.out.write(json.dumps(resp))
        else:
            self.response.status = 500
            self.response.out.write("Failed to build seed!")


class SeedGenJson(RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'application/json'
        param_key = SeedGenParams.from_url(self.request.GET)
        verbose_paths = self.request.GET.get("verbose_paths") is not None
        if param_key:
            params = param_key.get()
            if params.generate(preplaced={}):
                players = []
                resp = {}
                if params.tracking:
                    game = Game.from_params(params, self.request.GET.get("game_id"))
                    key = game.key
                    resp["map_url"] = uri_for("map-render", game_id=key.id())
                    resp["history_url"] = uri_for("game-show-history", game_id=key.id())
                for p in range(1, params.players + 1):
                    if params.tracking:
                        seed = params.get_seed(p, key.id(), verbose_paths)
                    else:
                        seed = params.get_seed(p, verbose_paths=verbose_paths)
                    spoiler = params.get_spoiler(p).replace("\n", "\r\n")
                    players.append({"seed": seed, "spoiler": spoiler, "spoiler_url": uri_for('gen-params-get-spoiler', params_id=param_key.id(), player=p)})
                resp["players"] = players
                self.response.out.write(json.dumps(resp))
                return
        log.error("param gen failed")
        self.response.status = 500

class GetParamMetadata(RequestHandler):
    def get(self, params_id):
        self.response.headers['Content-Type'] = 'application/json'
        params = SeedGenParams.with_id(params_id)
        if params:
            resp = {"playerCount": params.players, "flagLine": params.flag_line()}
            self.response.out.write(json.dumps(resp))
        else:
            self.response.status = 404

class GetSeedFromParams(RequestHandler):
    def get(self, params_id):
        self.response.headers['Content-Type'] = 'text/plain'
        verbose_paths = self.request.GET.get("verbose_paths") is not None
        params = SeedGenParams.with_id(params_id)
        if params:
            player = int(self.request.GET.get("player_id", 1))
            if params.tracking:
                game_id = self.request.GET.get("game_id")
                seed = params.get_seed(player, game_id, verbose_paths)
            else:
                seed = params.get_seed(player, verbose_paths=verbose_paths)
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
            player = int(self.request.GET.get("player", 1))
            spoiler = params.get_spoiler(player)
            if paramFlag(self, "download"):
                self.response.headers['Content-Type'] = 'application/x-gzip'
                self.response.headers['Content-Disposition'] = 'attachment; filename=spoiler.txt'
                spoiler = spoiler.replace("\n", "\r\n")
            self.response.out.write(spoiler)
        else:
            self.response.status = 404
            self.response.out.write("Param %s not found" % params_id)

class PicksByTypeGen(RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'application/json'
        self.response.out.write(picks_by_type_generator())
        return

class RebindingsEditor(RequestHandler):
    def get(self):
        path = os.path.join(os.path.dirname(__file__), 'map/build/index.html')
        template_values = {'app': "RebindingsEditor", 'title': "Ori DE Rebindings Editor"}
        self.response.out.write(template.render(path, template_values))

class VanillaPlusSeeds(RequestHandler):
    def get(self):
        skills = int(paramVal(self, "skills") or 3)
        cells = int(paramVal(self, "cells") or 4)
        skill_pool = ["SK/0", "SK/2", "SK/3", "SK/4", "SK/5", "SK/8", "SK/12", "SK/14", "SK/50", "SK/51"]
        start_with = random.sample(skill_pool, skills)
        start_with += [random.choice(["AC/1/AC/1", "HC/1", "EC/1"]) for _ in range(cells)]
        mu_line = "2|MU|TP/Valley/TP/Swamp/" + "/".join(start_with) + "|Glades"
        base = vanilla_seed.split("\n")
        base[0] = "OpenWorld|BingoSeed"
        base.insert(1, mu_line)
        self.response.headers['Content-Type'] = 'application/x-gzip' if not debug else 'text/plain'
        self.response.headers['Content-Disposition'] = 'attachment; filename=randomizer.dat' if not debug else ""
        self.response.out.write("\n".join(base))


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
            Route('/gamedata', handler=GetGameData, name="map-fetch-game-data"),
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
    ('/', ReactLanding),
    ('/rebinds', RebindingsEditor),
    ('/quickstart', ReactLanding),
    (r'/activeGames/?', ActiveGames),
    (r'/clean/?', CleanUp),
    (r'/getNewGame/?', GetGameId),
    (r'/cache', ShowCache),
    (r'/cache/clear', ClearCache),
    (r'/login/?', HandleLogin),
    (r'/logout/?', HandleLogout),
    ('/vanilla', Vanilla),
    ('/vanillaplus', VanillaPlusSeeds),
    ('/discord', DiscordRedirect),

    # new netcode endpoints
    PathPrefixRoute('/netcode/game/<game_id:\d+>/player/<player_id:[^/]+>', [
        Route('/found/<coords>/<kind>/<id:.*>', handler=FoundPickup, name="netcode-player-found-pickup"),
        Route('/tick/<x:[^,]+>,<y>', handler=GetUpdate, name="netcode-player-tick"),
        Route('/callback/<signal>', handler=SignalCallback,  name="netcode-player-signal-callback"),
        Route('/setSeed', handler=SetSeed,  name="netcode-player-set-seed"),
    ]),

    # new game endpoints
    PathPrefixRoute('/game/<game_id:\d+>', [
        Route('/delete', handler=DeleteGame, strict_slash=True, name="game-delete"),
        Route('/history', handler=ShowHistory, strict_slash=True, name="game-show-history"),
        Route('/players', handler=ListPlayers, strict_slash=True, name="game-list-players"),
        Route('/player/(\w+)/remove', handler=RemovePlayer, strict_slash=True, name="game-remove-player"),
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
