# py imports
import random
import json
from collections import Counter

# web imports
import logging as log
from urllib import unquote
from webapp2_extras.routes import DomainRoute, PathPrefixRoute, RedirectRoute as Route
from test import TestRunner
from webapp2 import WSGIApplication, RequestHandler, redirect, uri_for
from datetime import datetime, timedelta
from google.appengine.ext import ndb
from google.appengine.ext.webapp import template

# project imports
from seedbuilder.seedparams import SeedGenParams
from seedbuilder.vanilla import seedtext as vanilla_seed
from enums import MultiplayerGameType, ShareType, Variation
from models import Game, Seed, User, BingoGameData, trees_by_coords
from cache import Cache
from util import coord_correction_map, all_locs, picks_by_type_generator, param_val, param_flag, resp_error, debug, path, VER, template_vals
from reachable import Map, PlayerState
from pickups import Pickup

# handlers
from bingo import routes as bingo_routes

VERSION = "%s.%s.%s" % tuple(VER)
PLANDO_VER = "0.5.1"
share_types = [ShareType.EVENT, ShareType.SKILL, ShareType.UPGRADE, ShareType.MISC, ShareType.TELEPORTER]

class CleanUp(RequestHandler):
    def get(self):
        clean_count = Game.clean_old()
        User.prune_games()
        self.response.headers['Content-Type'] = 'text/plain'
        self.response.status = 200
        self.response.write("Cleaned up %s games" % clean_count)


class DeleteGame(RequestHandler):
    def get(game_id, self):
        self.response.headers['Content-Type'] = 'text/plain'
        if int(game_id) < 10000 and not param_flag(self, "override"):
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
        hours = int(hours)
        self.response.headers['Content-Type'] = 'text/html'
        title = "Games active in the last %s hours" % hours
        body = ""
        games = Game.query(Game.last_update > datetime.now() - timedelta(hours=hours)).fetch()
        games = [game for game in games if len(game.get_all_hls()) > 0]
        if not len(games):
            games = Game.query().fetch()
            games = [game for game in games if len(game.get_all_hls()) > 0]
            if not len(games):
                title = "No active games found!"
            else:
                title = "All active games"
        for game in sorted(games, key=lambda x: x.last_update, reverse=True):
            gid = game.key.id()
            game_link = uri_for('game-show-history', game_id=gid)
            map_link = uri_for('map-render', game_id=gid)
            slink = ""
            flags = ""
            if game.params:
                params = game.params.get()
                flags = params.flag_line()
                slink = " <a href=%s>Seed</a>" % uri_for('main-page', game_id=gid, param_id=params.key.id())
            blink = ""
            if game.bingo_data:
                blink += " <a href='/bingo/board?game_id=%s'>Bingo board</a>" % gid
            body += "<li><a href='%s'>Game #%s</a> <a href='%s'>Map</a>%s%s %s (Last update: %s ago)</li>" % (game_link, gid, map_link, slink, blink, flags, datetime.now() - game.last_update)
        out = "<html><head><title>%s - Ori Rando Server</title></head><body>" % title
        if body:
            out += "<h4>%s:</h4><ul>%s</ul></body</html>" % (title, body)
        else:
            out += "<h4>%s</h4></body></html>" % title
        self.response.write(out)


class MyGames(RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'text/html'
        user = User.get()
        if not user:
            return self.redirect(User.login_url('/myGames'))
        title = "Games played by %s" % user.name
        body = ""
        games = [key.get() for key in user.games]
        for game in sorted(games, key=lambda x: x.last_update, reverse=True):
            gid = game.key.id()
            game_link = uri_for('game-show-history', game_id=gid)
            map_link = uri_for('map-render', game_id=gid)
            slink = ""
            flags = ""
            if game.params:
                params = game.params.get()
                flags = params.flag_line()
                slink = " <a href=%s>Seed</a>" % uri_for('main-page', game_id=gid, param_id=params.key.id())
            blink = ""
            if game.bingo_data:
                blink += " <a href='/bingo/board?game_id=%s'>Bingo board</a>" % gid
            body += "<li><a href='%s'>Game #%s</a> <a href='%s'>Map</a>%s%s %s (Last update: %s ago)</li>" % (game_link, gid, map_link, slink, blink, flags, datetime.now() - game.last_update)
        out = "<html><head><title>%s - Ori Rando Server</title></head><body>" % title
        if body:
            out += "<h4>%s:</h4><ul>%s</ul></body</html>" % (title, body)
        else:
            out += "<h4>%s</h4></body></html>" % title
        self.response.write(out)

class FoundPickup(RequestHandler):
    def get(self, game_id, player_id, coords, kind, id):
        game = Game.with_id(game_id)
        if not game:
            self.response.status = 412
            self.response.write(self.response.status)
            return
        remove = param_flag(self, "remove")
        zone = param_val(self, "zone")
        coords = int(coords)
        if coords in coord_correction_map:
            coords = coord_correction_map[coords]
        if coords not in all_locs:
            log.warning("Coord mismatch error! %s not in all_locs or correction map. Sync %s.%s, pickup %s|%s" % (coords, game_id, player_id, kind, id))
        dedup = not param_flag(self, "override") and not remove and game.mode.is_dedup()
        pickup = Pickup.n(kind, id)
        if not pickup:
            log.error("Couldn't build pickup %s|%s" % (kind, id))
            self.response.status = 406
            return
        self.response.status = game.found_pickup(player_id, pickup, coords, remove, dedup, zone)
        self.response.write(self.response.status)

class GetUpdate(RequestHandler):
    def get(self, game_id, player_id, x, y):
        self.response.headers['Content-Type'] = 'text/plain'
        game = Game.with_id(game_id)
        if not game:
            self.response.status = 412
            self.response.write(self.response.status)
            return
        p = game.player(player_id)
        Cache.set_pos(game_id, player_id, x, y)
        self.response.write(p.output())

class ShowHistory(RequestHandler):
    def get(self, game_id):
        self.response.headers['Content-Type'] = 'text/plain'
        game = Game.with_id(game_id)
        if game:
            output = game.summary(int(param_val(self, "p") or 0))
            output += "\nHistory:"
            hls = []
            pids = [int(pid) for pid in param_val(self, "pids").split("|")] if param_val(self, "pids") else []
            hls = game.history(pids) if param_flag(self, "verbose") else [h for h in game.history(pids) if h.pickup().is_shared(share_types)]
            for hl in sorted(hls, key=lambda x: x.timestamp, reverse=True):
                output += "\n\t\t Player %s %s" % (hl.player, hl.print_line(game.start_time))
            self.response.status = 200
            self.response.write(output)
        else:
            self.response.status = 404
            self.response.write("Game %s not found!" % game_id)


class Vanilla(RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'application/x-gzip'
        self.response.headers['Content-Disposition'] = 'attachment; filename=randomizer.dat'
        self.response.write(vanilla_seed)


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
            outlines.append("Player %s: %s" % (p.pid(), p.bitfields))
            outlines.append("\t\t" + "\n\t\t".join([hl.print_line(game.start_time) for hl in game.history([p.pid()]) if hl.pickup().is_shared(share_types)]))

        self.response.headers['Content-Type'] = 'text/plain'
        self.response.status = 200
        self.response.write("\n".join(outlines))


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
            self.response.write("player %s not in %s" % (key, game.players))


class ClearCache(RequestHandler):
    def get(self):
        Cache.clear()
        self.redirect("/")


class SetSeed(RequestHandler):
    def post(self, game_id, player_id):
        lines = self.request.POST["seed"].split(",") if "seed" in self.request.POST else []
        self.handle(game_id, player_id, lines)

    def get(self, game_id, player_id):
        lines = param_val(self, "seed").split(",")
        if "Bingo" in lines[0].split("|"):
            game = Game.with_id(game_id)
            if game:
                p = game.player(player_id)
                p.signal_send("msg:@Bingo dll required for bingo games!@")
        self.handle(game_id, player_id, lines)

    def handle(self, game_id, player_id, lines):
        game = Game.with_id(game_id)
        hist = Cache.get_hist(game_id)
        if not hist:
            Cache.set_hist(game_id, player_id, [])
        if not game:
            # TODO: this branch is now probably unnecessary.
            # experiment with deleting it.
            log.error("game was not already created! %s" % game_id)
            flags = lines[0].split("|")
            mode_opt = [f[5:] for f in flags if f.lower().startswith("mode=")]
            shared_opt = [f[7:].split(" ") for f in flags if f.lower().startswith("shared=")]
            mode = mode_opt[0] if mode_opt else None
            shared = shared_opt[0] if shared_opt else None
            Game.new(_mode=mode, _shared=shared, id=game_id)
        else:
            game.sanity_check()  # cheap if game is short!
        self.response.headers['Content-Type'] = 'text/plain'
        self.response.status = 200
        self.response.write("ok")


class ShowMap(RequestHandler):
    def get(self, game_id):
        template_values = template_vals("GameTracker", "Game %s" % game_id, User.get())
        template_values['game_id'] = game_id
        if debug and param_flag(self, "from_test"):
            game = Game.with_id(game_id)
            pos = Cache.get_pos(game_id)
            hist = Cache.get_hist(game_id)
            if any([x is None for x in [game, pos, hist]]):
                return redirect(uri_for('tests-map-gid', game_id=game_id, from_test=1))

        self.response.write(template.render(path, template_values))


class GetSeenLocs(RequestHandler):
    def get(self, game_id):
        self.response.headers['Content-Type'] = 'application/json'
        self.response.status = 200
        seenLocs = {}
        game = Game.with_id(game_id)
        try:
            hist = Cache.get_hist(game_id)
            if not game:
                self.response.status = 404
                return
            if not hist:
                hist = game.rebuild_hist()
            for player, history_lines in hist.items():
                seenLocs[player] = [hl.coords for hl in history_lines] + [hl.map_coords for hl in history_lines if hl.map_coords]
            self.response.write(json.dumps(seenLocs))
        except AttributeError:
            log.error("cache invalidated for game %s! Rebuilding..." % game_id)
            game.rebuild_hist()
            self.response.write(json.dumps(seenLocs))


class GetSeed(RequestHandler):
    def get(self, game_id, player_id):
        player_id = int(player_id)
        self.response.headers['Content-Type'] = 'application/json'
        game = Game.with_id(game_id)
        if not game or not game.params:
            return resp_error(self, 404, json.dumps({"error": "game %s not found!" % game_id}))
        player = game.player(player_id, False)
        if not player:
            return resp_error(self, 404, json.dumps({"error": "game %s does not contain player %s!" % (game_id, player_id)}))
        res = {"seed": {}, 'name': player.name()}
        params = game.params.get()
        if Variation.BINGO in params.variations:
            bingo = BingoGameData.with_id(game_id)
            if not bingo:
                return resp_error(self, 404, json.dumps({"error": "no bingo data found for game %s" % game_id}))
            team = bingo.team(player_id, cap_only=False)
            if not team:
                return resp_error(self, 404, json.dumps({"error": "No team found for player %s!" % player_id}))
            team = team.pids()
            player_id = team.index(player_id) + 1
        for (coords, code, id, _) in params.get_seed_data(player_id):
            res["seed"][coords] = Pickup.name(code, id)
        self.response.status = 200
        self.response.write(json.dumps(res))


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
        gamedata["players"] = [{'pid': p.pid(), 'name': p.name()} for p in game.get_players()]
        gamedata["closed_dungeons"] = Variation.CLOSED_DUNGEONS in params.variations
        gamedata["open_world"] = Variation.OPEN_WORLD in params.variations
        self.response.write(json.dumps(gamedata))


class GetReachable(RequestHandler):
    def get(self, game_id):
        self.response.headers['Content-Type'] = 'application/json'
        hist = Cache.get_hist(game_id)
        reachable_areas = {}
        if not hist or not param_val(self, "modes"):
            self.response.status = 404
            self.response.write(json.dumps(reachable_areas))
            return
        modes = param_val(self, "modes").split(" ")
        game = Game.with_id(game_id)
        shared_hist = []
        shared_coords = set()
        try:
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
            self.response.write(json.dumps(reachable_areas))
        except AttributeError:
            log.error("cache invalidated for game %s! Rebuilding..." % game_id)
            game.rebuild_hist()
            self.response.write(json.dumps(reachable_areas))


class ItemTracker(RequestHandler):
    def get(self, game_id):
        template_values = template_vals("ItemTracker", "Game %s" % game_id, User.get())
        template_values['game_id'] = game_id
        self.response.write(template.render(path, template_values))


class GetItemTrackerUpdate(RequestHandler):
    def get(self, game_id):
        self.response.headers['Content-Type'] = 'application/json'
        items = Cache.get_items(game_id)
        if not items:
            game_hist = Cache.get_hist(game_id)
            if not game_hist:
                game = Game.with_id(game_id)
                if not game:
                    self.response.status = 404
                    self.response.write(json.dumps({"error": "Game not found"}))
                    return
                game_hist = game.rebuild_hist()
            items = GetItemTrackerUpdate.get_items(game_hist, game_id)
        self.response.write(json.dumps(items))

    @staticmethod
    def get_items(game_hist, game_id):
        relics = Cache.get_relics(game_id)
        if relics is None:
            game = Game.with_id(game_id)
            relics = game.relics
            Cache.set_relics(game_id, relics)
        data = {
            'skills': set(),
            'trees': set(),
            'events': set(),
            'shards': {'wv': 0, 'gs': 0, 'ss': 0},
            'maps': set(),
            'relics_found': set(),
            'relics': relics,
            'teleporters': set()
        }
        hls = [hl for hls in game_hist.values() for hl in hls]
        for hl in hls:
            if hl.pickup_code == "SK":
                data['skills'].add(hl.pickup().name)
            elif hl.pickup_code == "TP":
                data['teleporters'].add(hl.pickup().name.replace(" teleporter", ""))
            elif hl.pickup_code == "EV":
                data['events'].add(hl.pickup().name)
            elif hl.pickup_code == "RB":
                bid = int(hl.pickup_id)
                if bid == 17:
                    data['shards']['wv'] += 1
                elif bid == 19:
                    data['shards']['gs'] += 1
                elif bid == 21:
                    data['shards']['ss'] += 1
                elif bid > 910 and bid < 922:
                    data['relics_found'].add(hl.pickup().name.replace(" Relic", ""))
            if hl.map_coords:
                data['maps'].add(hl.map_coords)
            elif hl.coords in trees_by_coords:
                data['trees'].add(trees_by_coords[hl.coords].name.replace(" Tree", ""))
        if data['shards']['wv'] > 2:
            data['events'].add("Water Vein")
        if data['shards']['gs'] > 2:
            data['events'].add("Gumon Seal")
        if data['shards']['ss'] > 2:
            data['events'].add("Sunstone")
        for thing in ['trees', 'skills', 'events', 'relics_found', 'teleporters']:
            data[thing] = list(data[thing])
        data['maps'] = len(data['maps'])
        Cache.set_items(game_id, data)
        return data

class GetMapUpdate(RequestHandler):
    def get(self, game_id):
        self.response.headers['Content-Type'] = 'application/json'
        players = {}
        pos = Cache.get_pos(game_id)
        game = None
        if not pos:
            pos = {}
        for p, (x, y) in pos.items():
            players[p] = {"pos": [y, x], "seen": [], "reachable": []}  # bc we use tiling software, this is lat/lng

        game_hist = Cache.get_hist(game_id)
        if not game_hist:
            game = Game.with_id(game_id)
            if not game:
                self.response.status = 404
                self.response.write(json.dumps({"error": "Game not found"}))
                return
            game_hist = game.rebuild_hist()
        for p, history_lines in game_hist.items():
            if p not in players:
                players[p] = {}
            players[p]["seen"] = [hl.coords for hl in history_lines] + [hl.map_coords for hl in history_lines if hl.map_coords]
        items = Cache.get_items(game_id) or GetItemTrackerUpdate.get_items(game_hist, game_id)
        reach = Cache.get_reachable(game_id)
        modes = tuple(sorted(param_val(self, "modes").split(" ")))
        need_reach_updates = [p for p in players.keys() if modes not in reach.get(p, {})]
        if need_reach_updates:
            if not game:
                game = Game.with_id(game_id)
                if not game:
                    self.response.status = 404
                    self.response.write(json.dumps({"error": "Game not found"}))
                    return
            shared_hists = {}
            if game.mode == MultiplayerGameType.SHARED:
                groups = game.get_player_groups(int_ids=True)
                for group in groups:
                    g_hist = [hl for p, hls in game_hist.items() for hl in hls if p in group and hl.pickup().is_shared(game.shared)]
                    group_needs_update = any([p in need_reach_updates for p in group])
                    for p in group:
                        if group_needs_update and p not in need_reach_updates:
                            need_reach_updates.append(p)
                        shared_hists[p] = g_hist
            for p in need_reach_updates:
                hist = []
                shared_coords = []
                if p in shared_hists:
                    hist += shared_hists[p]
                    shared_coords = set([h.coords for h in hist])
                hist += [hl for hl in game_hist.get(p, []) if hl.coords not in shared_coords]
                state = PlayerState([(h.pickup_code, h.pickup_id, 1, h.removed) for h in hist])
                areas = {}
                if state.has["KS"] > 8 and "standard-core" in modes:
                    state.has["KS"] += 2 * (state.has["KS"] - 8)
                if p not in reach:
                    reach[p] = {}
                reach[p][modes] = Map.get_reachable_areas(state, modes, False)
            Cache.set_reachable(game_id, reach)
        for p in reach:
            players[p]["reachable"] = reach[p][modes]
        self.response.write(json.dumps({"players": players, "items": items}))


class GetPlayerPositions(RequestHandler):
    def get(self, game_id):
        self.response.headers['Content-Type'] = 'application/json'
        pos = Cache.get_pos(game_id)
        if pos:
            self.response.status = 200
            players = {}
            for p, (x, y) in pos.items():
                players[p] = [y, x]  # bc we use tiling software, this is lat/lng
            self.response.write(json.dumps(players))
        else:
            self.response.status = 404


class PlandoReachable(RequestHandler):
    def post(self):
        modes = json.loads(self.request.POST["modes"])
        codes = []
        for item, count in json.loads(self.request.POST["inventory"]).iteritems():
            codes.append(tuple(item.split("|") + [count, False]))
        self.response.headers['Content-Type'] = 'application/json'
        self.response.status = 200
        areas = {}
        for area, reqs in Map.get_reachable_areas(PlayerState(codes), modes).items():
            areas[area] = [{item: count for (item, count) in req.cnt.items()} for req in reqs if len(req.cnt)]

        self.response.write(json.dumps(areas))


def clone_entity(e, **extra_args):
    klass = e.__class__
    props = dict((v._code_name, v.__get__(e, klass)) for v in klass._properties.itervalues() if
                 type(v) != ndb.ComputedProperty)
    props.update(extra_args)
    return klass(**props)


class PlandoRename(RequestHandler):
    def get(self, seed_name, new_name):
        user = User.get()
        if not user:
            log.error("Error: unauthenticated rename attempt")
            self.response.status = 401
            return
        old_seed = user.plando(seed_name)
        if not old_seed:
            log.error("couldn't find old seed when trying to rename!")
            self.response.status = 404
            return
        new_seed = clone_entity(old_seed, id="%s:%s" % (user.key.id(), new_name), name=new_name)
        if new_seed.put():
            if not param_flag(self, "cp"):
                old_seed.key.delete()
            self.redirect(uri_for("plando-view", author_name=user.name, seed_name=new_name))
        else:
            log.error("Failed to rename seed")
            self.response.status = 500


class PlandoDelete(RequestHandler):
    def get(self, seed_name):
        user = User.get()
        if not user:
            log.error("Error: unauthenticated delete attempt")
            self.response.status = 401
            return
        seed = user.plando(seed_name)
        if not seed:
            log.error("couldn't find seed when trying to delete!")
            self.response.status = 404
            return
        seed.key.delete()
        self.redirect(uri_for("plando-author-index", author_name=user.name))


class PlandoToggleHide(RequestHandler):
    def get(self, seed_name):
        user = User.get()
        if not user:
            log.error("Error: unauthenticated hide attempt")
            self.response.status = 401
            return
        seed = user.plando(seed_name)
        if not seed:
            log.error("couldn't find seed when trying to hide!")
            self.response.status = 404
            return
        seed.hidden = not (seed.hidden or False)
        seed.put()
        self.redirect(uri_for("plando-view", author_name=user.name, seed_name=seed_name))


class PlandoUpload(RequestHandler):
    def post(self, seed_name):
        user = User.get()
        if not user:
            log.error("Error: unauthenticated upload attempt")
            self.response.status = 401
            return
        seed_data = json.loads(self.request.POST["seed"])
        old_name = seed_data["oldName"]
        name = seed_data["name"]
        old_seed = user.plando(old_name)
        if old_seed:
            res = old_seed.update(seed_data)
        else:
            res = Seed.new(seed_data)
        self.response.headers['Content-Type'] = 'text/plain'
        self.response.status = 200
        self.response.write(res)


class PlandoView(RequestHandler):
    def get(self, author_name, seed_name):
        authed = False
        user = User.get()
        seed = Seed.get(author_name, seed_name)
        if seed:
            if user and user.key == seed.author_key:
                authed = True
            template_values = template_vals("SeedDisplayPage", "%s by %s" % (seed_name, author_name), user)
            template_values.update({'players': seed.players, 'seed_data': seed.get_plando_json(),
                'seed_name': seed_name, 'author': author_name, 'authed': authed, 'version': VERSION,
                'seed_desc': seed.description, 'game_id': Game.get_open_gid()})
            hidden = seed.hidden or False
            if not hidden or authed:
                self.response.status = 200
                self.response.headers['Content-Type'] = 'text/html'
                if hidden:
                    template_values['seed_hidden'] = True
                self.response.write(template.render(path, template_values))
                return
        self.response.status = 404
        self.response.headers['Content-Type'] = 'text/plain'
        self.response.write("seed not found")


class PlandoEdit(RequestHandler):
    def get(self, seed_name):
        user = User.get()
        template_values = template_vals("PlandoBuilder", "Plando Editor: %s" % (seed_name), user)
        if user:
            seed = user.plando(seed_name)
            template_values['authed'] = "True"
            if seed:
                template_values['seed_desc'] = seed.description
                template_values['seed_hidden'] = seed.hidden or False
                template_values['seed_data'] = seed.get_plando_json()
        self.response.write(template.render(path, template_values))

class ThemeToggle(RequestHandler):
    def get(self):
        target_url = unquote(param_val(self, "redir")).decode('utf8') or "/"
        user = User.get()
        if user:
            user.dark_theme = not user.dark_theme
            user.put()
        self.redirect(target_url)
    
class HandleLogin(RequestHandler):
    def get(self):
        user = User.get()
        target_url = param_val(self, "redir") or "/"
        if user:
            self.redirect(target_url)
        else:
            self.redirect(User.login_url(target_url))


class HandleLogout(RequestHandler):
    def get(self):
        user = User.get()
        target_url = param_val(self, "redir") or "/"
        if user:
            self.redirect(User.logout_url(target_url))
        else:
            self.redirect(target_url)

class PlandoFillGen(RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'text/plain'
        qparams = self.request.GET
        forced_assignments = dict([(int(a), b) for (a, b) in ([tuple(fass.split(":")) for fass in qparams['fass'].split("|")] if "fass" in qparams else [])])
        param_key = SeedGenParams.from_url(qparams)
        params = param_key.get()
        if params.generate(preplaced=forced_assignments):
            self.response.write(params.get_seed(1))
        else:
            self.response.status = 422

class PlandoDownload(RequestHandler):
    def get(self, author_name, seed_name):
        seed = Seed.get(author_name, seed_name)
        if seed:
            if seed.hidden:
                user = User.get()
                if not user or user.key != seed.author_key:
                    self.response.status = 404
                    self.response.headers['Content-Type'] = 'text/plain'
                    self.response.write("seed not found")
                    return
            params = SeedGenParams.from_plando(seed, param_flag(self, "tracking"))
            url = uri_for("main-page", param_id=params.key.id())
            if params.tracking:
                game = Game.from_params(params, self.request.GET.get("game_id"))
                url += "&game_id=%s" % game.key.id()
            self.redirect(url)
        else:
            self.response.status = 404
            self.response.headers['Content-Type'] = 'text/plain'
            self.response.write("seed not found")

class AllAuthors(RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'text/html'
        seeds = Seed.query(Seed.hidden != True)
        out = '<html><head><title>All Plando Authors</title></head><body><h5>All Seeds</h5><ul style="list-style-type:none;padding:5px">'
        authors = Counter([seed.author_key.get().name if seed.author_key else seed.author for seed in seeds])
        for author, cnt in authors.most_common():
            if cnt > 0:
                url = "/plando/%s" % author
                out += '<li style="padding:2px"><a href="%s">%s</a> (%s plandos)</li>' % (url, author, cnt)
        out += "</ul></body></html>"
        self.response.write(out)


class AuthorIndex(RequestHandler):
    def get(self, author_name):
        self.response.headers['Content-Type'] = 'text/html'
        owner = False
        user = User.get()
        author = User.get_by_name(author_name)
        if author:
            author_name = author.name
            owner = user and user.key.id() == author.key.id()
            query = Seed.query(Seed.author_key == author.key)
            if not owner:
                query = query.filter(Seed.hidden != True)
        else:
            query = Seed.query(Seed.author == author_name).filter(Seed.hidden != True)
        
        seeds = query.fetch()
        if len(seeds):
            out = '<html><head><title>Seeds by %s</title></head><body><div>Seeds by %s:</div><ul style="list-style-type:none;padding:5px">' % (author_name, author_name)
            for seed in seeds:
                url = uri_for("plando-view", author_name=author_name, seed_name=seed.name)
                flags = ",".join(seed.flags)
                out += '<li style="padding:2px"><a href="%s">%s</a>: %s (%s players, %s)' % (url, seed.name, seed.description.partition("\n")[0], seed.players, flags)
                if owner:
                    out += ' <a href="%s">Edit</a>' % uri_for("plando-edit", seed_name=seed.name)
                    if seed.hidden:
                        out += " (hidden)"
                out += "</li>"
            out += "</ul></body></html>"
            self.response.write(out)
        else:
            if owner:
                self.response.write(
                    "<html><body>You haven't made any seeds yet! <a href='%s'>Start a new seed</a></body></html>" % uri_for('plando-edit', seed_name="newSeed"))
            else:
                self.response.write('<html><body>No seeds by user %s</body></html>' % author_name)


class MapTest(RequestHandler):
    def get(self, game_id=101):
        if not debug:
            self.redirect("/")
        game_id = int(game_id)
        game = Game.with_id(game_id)
        if game:
            game.clean_up()
        url = "/generator/build?key_mode=Free&gen_mode=Balanced&var=OpenWorld&var=WorldTour&path=casual-core&path=casual-dboost&exp_pool=10000&cell_freq=40&relics=10&players=3&sync_mode=Shared&sync_shared=WorldEvents&sync_shared=Teleporters&sync_shared=Upgrades&sync_shared=Misc&sync_shared=Skills&test_map_redir=%s&seed=%s" % (game_id, random.randint(100000,1000000))
        self.redirect(url)

class LogicHelper(RequestHandler):
    def get(self):
        template_values = template_vals("LogicHelper", "Logic Helper", User.get())

        template_values.update({'is_spoiler': "True", 'pathmode': param_val(self, 'pathmode'), 'HC': param_val(self, 'HC'),
                           'EC': param_val(self, 'EC'), 'AC': param_val(self, 'AC'), 'KS': param_val(self, 'KS'),
                           'skills': param_val(self, 'skills'), 'tps': param_val(self, 'tps'), 'evs': param_val(self, 'evs')})
        self.response.write(template.render(path, template_values))

class ReactLanding(RequestHandler):
    def get(self):
        template_values = template_vals("MainPage", "Ori DE Randomizer %s" % VERSION, User.get())
        self.response.write(template.render(path, template_values))


class MakeSeedWithParams(RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'application/json'
        param_key = SeedGenParams.from_url(self.request.GET)
        if not param_key:
            return resp_error(self, 500, "Failed to build params!", 'text/plain')
        params = param_key.get()
        if not params.generate():
            return resp_error(self, 500, "Failed to generate seed!", 'text/plain')
        resp = {"paramId": param_key.id(), "playerCount": params.players, "flagLine": params.flag_line(), 'seed': params.seed, "spoilers": True}
        if params.tracking:
            game = Game.from_params(params, self.request.GET.get("game_id"))
            resp["gameId"] = game.key.id()
            if debug and param_flag(self, "test_map_redir"):
                    self.redirect(uri_for("map-render", game_id=resp["gameId"], from_test=1))
        if Variation.BINGO in params.variations:
            resp["doBingoRedirect"] = True

        self.response.write(json.dumps(resp))
    def post(self):
        self.response.headers['Content-Type'] = 'application/json'
        param_key = SeedGenParams.from_json(json.loads(self.request.POST["params"]))
        params = param_key.get()
        if not param_key:
            return resp_error(self, 500, "Failed to build params!", 'text/plain')
        params = param_key.get()
        if not params.generate():
            return resp_error(self, 500, "Failed to generate seed!", 'text/plain')
        resp = {"paramId": param_key.id(), "playerCount": params.players, "flagLine": params.flag_line(), 'seed': params.seed, "spoilers": True}
        if params.tracking:
            game = Game.from_params(params, self.request.GET.get("game_id"))
            resp["gameId"] = game.key.id()
            if debug and param_flag(self, "test_map_redir"):
                    self.redirect(uri_for("map-render", game_id=resp["gameId"], from_test=1))
        if Variation.BINGO in params.variations:
            resp["doBingoRedirect"] = True
        self.response.write(json.dumps(resp))


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
                self.response.write(json.dumps(resp))
                return
        log.error("param gen failed")
        self.response.status = 500

class GetParamMetadata(RequestHandler):
    def get(self, params_id, game_id = None):
        self.response.headers['Content-Type'] = 'application/json'
        params = SeedGenParams.with_id(params_id)
        if not params:
            return resp_error(self, 404, json.dumps({"error": "No params found"}))
        res = params.to_json()
        if params.tracking and not game_id:
            game = Game.from_params(params)
            res["gameId"] = game.key.id()
        self.response.write(json.dumps(res))


class GetSeedFromParams(RequestHandler):
    def get(self, params_id):
        self.response.headers['Content-Type'] = 'text/plain'
        verbose_paths = self.request.GET.get("verbose_paths") is not None
        params = SeedGenParams.with_id(params_id)
        if params:
            pid = int(self.request.GET.get("player_id", 1))
            if params.tracking:
                game_id = self.request.GET.get("game_id")
                seed = params.get_seed(pid, game_id, verbose_paths)
                game = Game.with_id(game_id)
                user = User.get()
                if game and user:
                    player = game.player(pid)
                    player.user = user.key
                    player.put()
                    if game.key not in user.games:
                        user.games.append(game.key)
                        user.put()
            else:
                seed = params.get_seed(pid, verbose_paths=verbose_paths)
            if not debug:
                self.response.headers['Content-Type'] = 'application/x-gzip'
                self.response.headers['Content-Disposition'] = 'attachment; filename=randomizer.dat'
            self.response.write(seed)
        else:
            self.response.status = 404
            self.response.write("Param %s not found" % params_id)

class GetSpoilerFromParams(RequestHandler):
    def get(self, params_id):
        self.response.headers['Content-Type'] = 'text/plain'
        params = SeedGenParams.with_id(params_id)
        if params:
            player = int(self.request.GET.get("player_id", 1))
            spoiler = params.get_spoiler(player)
            if param_flag(self, "download"):
                self.response.headers['Content-Type'] = 'application/x-gzip'
                self.response.headers['Content-Disposition'] = 'attachment; filename=spoiler.txt'
                spoiler = spoiler.replace("\n", "\r\n")
            self.response.write(spoiler)
        else:
            self.response.status = 404
            self.response.write("Param %s not found" % params_id)

class GetAuxSpoilerFromParams(RequestHandler):
    def get(self, params_id):
        self.response.headers['Content-Type'] = 'text/plain'
        params = SeedGenParams.with_id(params_id)
        if params:
            player = int(self.request.GET.get("player_id", 1))
            exclude = (param_val(self, "exclude") or "EX KS AC EC HC MS").split(" ")
            by_zone = param_flag(self, "by_zone")
            spoiler = params.get_aux_spoiler(exclude, by_zone, player)
            if param_flag(self, "download"):
                self.response.headers['Content-Type'] = 'application/x-gzip'
                self.response.headers['Content-Disposition'] = 'attachment; filename=spoiler.txt'
                spoiler = spoiler.replace("\n", "\r\n")
            self.response.write(spoiler)
        else:
            self.response.status = 404
            self.response.write("Param %s not found" % params_id)


class PicksByTypeGen(RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'application/json'
        self.response.write(picks_by_type_generator())
        return

class RebindingsEditor(RequestHandler):
    def get(self):
        template_values = template_vals("RebindingsEditor", "Ori DERebindings Editor", User.get())
        self.response.write(template.render(path, template_values))

class Guides(RequestHandler):
    def get(self):
        template_values = template_vals("HelpAndGuides", "Help and Guides", User.get())
        self.response.write(template.render(path, template_values))

class GetSettings(RequestHandler):
    def get(self):
        res = {}
        res["names"] = [user.name.lower() for user in User.query().fetch()]
        user = User.get()
        if user:
            res["teamname"] = user.teamname or "%s's team" % user.name
            res["theme"] = "dark" if user.dark_theme else "light"
        self.response.headers['Content-Type'] = 'application/json'
        self.response.write(json.dumps(res))


class SetSettings(RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'text/plain'
        user = User.get()
        if user:
            name = param_val(self, "name")
            teamname = param_val(self, "teamname")
            if name and name != user.name:
                if user.rename(name):
                    self.response.write("Rename successful!")
                else:
                    self.response.write("Rename failed!")
            if teamname and teamname != user.teamname:
                user.teamname = teamname
                user.put()
        else:
            self.response.write("You are not logged in!")

class LastestMap(RequestHandler):
    def get(self, name):
        now = datetime.utcnow()
        user = User.get_by_name(name)
        if not user:
            return resp_error(self, 404, "User '%s' not found" % name, "text/plain")
        if not user.games:
            return resp_error(self, 404, "Could not find any tracked games for user '%s'" % name, "text/plain")
        game_key = user.games[-1]
        return redirect(uri_for('map-render', game_id=game_key.id()))


class SetPlayerNum(RequestHandler):
    def get(self, new_num):
        self.response.headers['Content-Type'] = 'text/plain'
        user = User.get()
        if user:
            if int(new_num) > 0:
                user.pref_num = int(new_num)
                user.put()
                self.response.write("Preferred player number for %s set to %s" % (user.name, new_num))
                return
            else:
                return resp_error(self, 400, "Preferred player number must be >0", "text/plain")
        else:
            return resp_error(self, 401, "You are not logged in!", "text/plain")

class SetTheme(RequestHandler):
    def get(self, new_theme):
        self.response.headers['Content-Type'] = 'text/plain'
        user = User.get()
        if user:
            user.theme = new_theme
            user.put()
            self.response.write("theme for %s set to %s" % (user.name, new_theme))
            return
        else:
            return resp_error(self, 401, "You are not logged in!", "text/plain")

class NakedRedirect(RequestHandler):
    def get(self, path):
        return redirect(self.request.url.replace("www.", ""))

app = WSGIApplication(
    routes=[
        DomainRoute('www.orirando.com', [Route('<path:.*>', handler=NakedRedirect)]),
    ] + bingo_routes + [
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
        Route('/metadata/<params_id:\d+>/<game_id:\d+>', handler=GetParamMetadata, name="gen-params-get-metadata-with-game", strict_slash=True),
        Route('/seed/<params_id:\d+>', handler=GetSeedFromParams, name="gen-params-get-seed", strict_slash=True),
        Route('/spoiler/<params_id:\d+>', handler=GetSpoilerFromParams, name="gen-params-get-spoiler", strict_slash=True),
        Route('/aux_spoiler/<params_id:\d+>', handler=GetAuxSpoilerFromParams, name="gen-params-get-aux-spoiler", strict_slash=True),
        Route('/json', handler=SeedGenJson, name="gen-params-get-json")
    ]),
    # tracking map endpoints
    Route('/tracker/spectate/<name>', handler = LastestMap, name = "user-latest-map", strict_slash = True),

    PathPrefixRoute('/tracker/game/<game_id:\d+>', [
        Route('/', redirect_to_name="map-render"),
        Route('/map', handler=ShowMap, name='map-render', strict_slash=True),
        Route('/items', handler=ItemTracker, name='item-tracker', strict_slash=True),
        ] + list(PathPrefixRoute('/fetch', [
            Route('/items', handler=GetItemTrackerUpdate, name='item-tracker-update'),
            Route('/pos', handler=GetPlayerPositions, name="map-fetch-pos"),
            Route('/gamedata', handler=GetGameData, name="map-fetch-game-data"),
            Route('/seen', handler=GetSeenLocs, name="map-fetch-seen"),
            Route('/reachable', handler=GetReachable, name="map-fetch-reachable"),
            Route('/update', handler=GetMapUpdate, name='match-fetch-update'),

            ] + list(PathPrefixRoute('/player/<player_id>', [
                Route('/seed', GetSeed, name="map-fetch-seed"),
                Route('/setSeed', SetSeed, name="map-set-seed"),
            ]).get_routes())
        ).get_routes())
    ),
    # misc / top level endpoints
    Route('/logichelper', handler=LogicHelper, name="logic-helper", strict_slash=True),
    Route('/faq', handler=Guides, name="help-guides", strict_slash=True),
    Route('/', handler=ReactLanding, name="main-page"),
    Route('/user/settings', handler=GetSettings, name="user-settings-get"),
    Route('/user/settings/update', handler=SetSettings, strict_slash=True, name="user-settings-update"),
    Route('/user/settings/number/<new_num:\d+>', handler=SetPlayerNum, strict_slash=True, name="user-set-player-num"),
    Route('/user/settings/theme/<new_theme>', handler=SetTheme, strict_slash=True, name="user-set-player-theme"),
    Route('/activeGames/', handler=ActiveGames, strict_slash=True, name="active-games"),
    Route('/activeGames/<hours:\d+>', handler=ActiveGames, strict_slash=True, name="active-games-hours"),
    ('/rebinds', RebindingsEditor),
    ('/quickstart', ReactLanding),
    (r'/myGames/?', MyGames),
    (r'/clean/?', CleanUp),
    (r'/cache/clear', ClearCache),
    (r'/login/?', HandleLogin),
    (r'/logout/?', HandleLogout),
    ('/vanilla', Vanilla),
    Route('/discord', redirect_to="https://discord.gg/TZfue9V"),
    Route('/dll', redirect_to="https://github.com/turntekGodhead/OriDERandomizer/raw/master/Assembly-CSharp.dll"),
    Route('/dll/bingo', redirect_to="https://github.com/turntekGodhead/OriDERandomizer/raw/master/Assembly-CSharp.dll"),
    Route('/tracker', redirect_to="https://github.com/turntekGodhead/OriDETracker/raw/master/OriDETracker/bin/Latest.zip"),
    Route('/weekly', redirect_to='https://forms.gle/UGeN2uBN6kPbeWzt6', name="weekly-poll"),
    Route('/openBook/form', redirect_to='https://forms.gle/aCyEjh7YWPLo1YK36', name="open-book-form"),
    Route('/openBook/leaderboard', redirect_to='https://docs.google.com/spreadsheets/d/1X6jJpjJVY_mly--9tnV9EGo5I6I_gJ4Sepkf51S9rQ4/edit#gid=1488532179&range=A1', name="open-book-leaderboard"),
    Route('/theme/toggle', handler=ThemeToggle, name="theme-toggle"),
    # netcode endpoints
    PathPrefixRoute('/netcode/game/<game_id:\d+>/player/<player_id:[^/]+>', [
        Route('/found/<coords>/<kind>/<id:.*>', handler=FoundPickup, name="netcode-player-found-pickup"),
        Route('/tick/<x:[^,]+>,<y>', handler=GetUpdate, name="netcode-player-tick"),
        Route('/signalCallback/<signal:.*>', handler=SignalCallback,  name="netcode-player-signal-callback"),
        Route('/callback/<signal:.*>', handler=SignalCallback,  name="netcode-player-signal-callback"),
        Route('/setSeed', handler=SetSeed,  name="netcode-player-set-seed"),
    ]),

    # game endpoints
    PathPrefixRoute('/game/<game_id:\d+>', [
        Route('/delete', handler=DeleteGame, strict_slash=True, name="game-delete"),
        Route('/history', handler=ShowHistory, strict_slash=True, name="game-show-history"),
        Route('/players', handler=ListPlayers, strict_slash=True, name="game-list-players"),
        Route('/player/(\w+)/remove', handler=RemovePlayer, strict_slash=True, name="game-remove-player"),
        Route('/', redirect_to_name="game-show-history"),
    ]),

    # plando endpoints
    Route('/plando/reachable', PlandoReachable, strict_slash=True, name="plando-reachable"),
    Route('/plando/fillgen', PlandoFillGen, strict_slash=True, name="plando-fillgen"),
    Route('/plandos', AllAuthors, strict_slash=True, name="plando-view-all"),

    PathPrefixRoute('/plando/<seed_name:[^ ?=/]+>', [
        Route('/upload', PlandoUpload, strict_slash=True, name="plando-upload"),
        Route('/edit', PlandoEdit, strict_slash=True, name="plando-edit"),
        Route('/delete', PlandoDelete, strict_slash=True, name="plando-delete"),
        Route('/rename/<new_name:[^ ?=/]+>', PlandoRename, strict_slash=True, name="plando-rename"),
        Route('/hideToggle', PlandoToggleHide, strict_slash=True, name="plando-toggle-hide"),
    ]),
    Route('/plando/<author_name:[^ ?=/]+>', AuthorIndex, strict_slash=True, name="plando-author-index"),

    PathPrefixRoute('/plando/<author_name:[^ ?=/]+>/<seed_name:[^ ?=/]+>', [
        Route('/download', PlandoDownload, strict_slash=True, name="plando-download"),
        Route('/', PlandoView, strict_slash=True, name="plando-view"),
    ]),
], debug=debug)
