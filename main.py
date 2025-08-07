# py imports
import random
import json
from collections import Counter, defaultdict
from time import sleep
from calendar import timegm
from datetime import datetime, timedelta

# web imports
import logging as log
from urllib.request import urlopen
from urllib.parse import unquote
from flask import Flask, render_template, request, make_response, url_for, redirect, g
from google.cloud import ndb
from google.cloud.ndb import transactional
from google.appengine.api import urlfetch
import google.cloud.logging
from flask_oidc import OpenIDConnect

# project imports
from seedbuilder.seedparams import SeedGenParams
from seedbuilder.vanilla import seedtext as vanilla_seed
from enums import MultiplayerGameType, ShareType, Variation
from models import ndb_wsgi_middleware, Game, Seed, User, BingoGameData, BingoEvent, BingoTeam, CustomLogic, trees_by_coords, LegacyUser
from bingo import BingoGenerator
from cache import Cache
from util import coord_correction_map, clone_entity, all_locs, picks_by_type_generator, param_val, param_flag, debug, template_root, VER, MIN_VER, BETA_VER, game_list_html, version_check, template_vals, layout_json, whitelist_ok, bfield_checksum
from reachable import Map, PlayerState
from pickups import Pickup, Skill, AbilityCell, HealthCell, EnergyCell, Multiple
import secrets

# handlers
# from bingo import routes as bingo_routes
from google.appengine.api import wrap_wsgi_app

path='index.html'
app = Flask(__name__, template_folder=template_root)
app.wsgi_app = wrap_wsgi_app(app.wsgi_app)
# app.url_map.strict_slashes = False
app.wsgi_app = ndb_wsgi_middleware(app.wsgi_app)
app.config["OIDC_CLIENT_SECRETS"] = "client_secret.json"

oidc = OpenIDConnect(app)
app.secret_key = secrets.app_secret_key

if debug():
    root_logger = log.getLogger()
    for handler in root_logger.handlers:
        root_logger.removeHandler(handler)

    # create console handler and set level to debug
    import sys
    console_handle = log.StreamHandler(sys.stdout)
    console_handle.setLevel(log.INFO)

    # create formatter
    formatter = log.Formatter("%(name)-5s - %(levelname)-8s - %(message)s")
    console_handle.setFormatter(formatter)

    # now add new handler to logger
    root_logger.addHandler(console_handle)
    root_logger.setLevel(log.INFO)
    log.info("set up dev logging to console!")
else:
    print("trying to setup prod log")
    #Logging setup:
    client = google.cloud.logging.Client()

    # Retrieves a Cloud Logging handler based on the environment
    # you're running in and integrates the handler with the
    # Python logging module. 
    client.setup_logging(log_level=log.DEBUG)

VERSION = "%s.%s.%s" % tuple(VER)
PLANDO_VER = "0.5.1"
share_types = [ShareType.EVENT, ShareType.SKILL, ShareType.UPGRADE, ShareType.MISC, ShareType.TELEPORTER]


def text_resp(body, status=200):
	return make_resp(body, status, 'text/plain')

def make_resp(body, status=200, mimeType = 'text/html'):
	return make_response((body, status, {'Content-Type': mimeType}))

def json_resp(jsonstr, status=200):
    return make_resp(jsonstr if isinstance(jsonstr, str) else json.dumps(jsonstr), status, mimeType = "application/json")

def code_resp(code):
    return text_resp(str(code), code)

def text_download(text, filename, status=200):
    return make_response(text, status, {'Content-Type': 'application/x-gzip', 'Content-Disposition': 'attachment; filename=%s' % filename})


@app.errorhandler(500)
def server_error(err):
    return make_resp("""
    <html><title>Server Error</title>
    <body><h3>Backend Server Error</h3>
    <div>If this keeps happening, consider reaching out to Eiko in the <a target="_blank" href="https://orirando.com/discord/dev">dev discord</a>.</div>
    <div style="padding-top: 2rem;">%s</div></body></html>""" % err, 500)

@app.route('/test')
def user_test():
    if g.oidc_user.logged_in:
        for user in User.query(User.email == g.oidc_user.email):
            user.key.delete()
        log.info("MATCHING" + str(User.query(User.email == g.oidc_user.email).count()))

        bingos = [str(bingo.key) for bingo in BingoGameData.query(BingoGameData.legacy_creator == ndb.Key("User", "100595625574941572248")).fetch()]

        return json_resp({
            "profile": g.oidc_user.profile,
            "id": g.oidc_user.unique_id,
            "email": g.oidc_user.email,
            "bingos": bingos
        })
    else:
        return 'Not logged in'

    

@app.route('/test_logout')
def user_test_logout():
    if g.oidc_user.logged_in:
        return oidc.logout("/test")
    else:
        return 'Not logged in'

@app.route('/clean/')
def clean_up():
    log.info("starting clean...")
    clean_count, did_finish = Game.clean_old(param_flag("log_prog"))
    ndb.get_context().clear_cache()
    if did_finish:
        log.info("Cleaned up %s games" % clean_count)
        User.prune_games()
        return text_resp("Cleaned up %s games" % clean_count)
    else:
        log.info("Cleaned up %s games before timeout" % clean_count)
        return text_resp("Cleaned up %s games before timeout" % clean_count)

@app.route('/activeGames/')
@app.route('/activeGames/<hours>/')
def active_games(hours=12):
    hours = int(hours)
    title = "Games active in the last %s hours" % hours
    games = Game.query(Game.last_update > datetime.now() - timedelta(hours=hours)).fetch()
    games = [game for game in games if len(game.get_all_hls()) > 0]
    if not len(games):
        games = Game.query().fetch()
        games = [game for game in games if len(game.get_all_hls()) > 0]
        if not len(games):
            title = "No active games found!"
        else:
            title = "All active games"
    body = game_list_html(games)
    out = "<html><head><title>%s - Ori Rando Server</title></head><body>" % title
    if body:
        out += "<h4>%s:</h4><ul>%s</ul></body</html>" % (title, body)
    else:
        out += "<h4>%s</h4></body></html>" % title
    return make_resp(out)


@app.route('/quickstart')
@app.route('/')
def main_page():
    log.info(User.get())
    template_values = template_vals("MainPage", "Ori DE Randomizer %s" % VERSION, User.get())
    # _, error = CustomLogic.read()
    # template_values.update({"error_msg": error})
    return render_template(path, **template_values)


@app.route('/myGames')
@oidc.require_login
def my_games():
    user = User.get()
    title = "Games played by %s" % user.name
    title, game_futures = ("Games played by %s" % user.name, [key.get_async() for key in user.games]) if param_flag("all") else (
                           "Last 10 games played by %s" % user.name,[key.get_async() for key in user.games[-10:]])
    body = game_list_html([gf.get_result() for gf in game_futures])
    if body:
        out = "<h4>%s:</h4><ul>%s</ul></body</html>" % (title, body)
    else:
        out = "<h4>%s</h4></body></html>" % title
    return make_resp(out)

@app.route('/login')
@oidc.require_login
def login():
    target_url = param_val("redir") or "/"
    return redirect(target_url)

@app.route('/logout')
def logout():
    user = User.get()
    target_url = param_val("redir") or "/"
    if user:
        return oidc.logout(target_url)
    else:
        return redirect(target_url)


@app.route('/netcode/game/<int:game_id>/player/<int:player_id>/found/<coords>/<kind>/<path:id>/')
@app.route('/netcode/game/<int:game_id>/player/<int:player_id>/found/<coords>/<kind>/<path:id>')
def netcode_found_pickup(game_id, player_id, coords, kind, id):
    status = 200
    game = Game.with_id(game_id)
    if not game:
        return code_resp(412)
    remove = param_flag("remove")
    zone = param_val("zone")
    coords = int(coords)
    if coords in coord_correction_map:
        coords = coord_correction_map[coords]
    if coords not in all_locs:
        log.warning("Coord mismatch error! %s not in all_locs or correction map. Sync %s.%s, pickup %s|%s" % (coords, game_id, player_id, kind, id))
    pickup = Pickup.n(kind, id)
    if not pickup:
        log.error("Couldn't build pickup %s|%s" % (kind, id))
        return code_resp(406)
    status = game.found_pickup(player_id, pickup, coords, remove, param_flag("override"), zone, [int(param_val("s%s"%i) or 0) for i in range(8)])
    if game.is_race:
        Cache.clear_items(game_id)
    elif pickup.code in ["AC", "KS", "HC", "EC", "SK", "EV", "TP"] or (pickup.code == "RB" and pickup.id in [17, 19, 21]):
        Cache.clear_reach(game_id, player_id)
        Cache.clear_items(game_id)
    return code_resp(status)

# do we even use this anymore? i think only for testing.........
@app.route('/netcode/game/<int:game_id>/player/<int:player_id>/tick/<xycoords>', methods=['GET'])
def netcode_tick_get(game_id, player_id, xycoords):
    x,_,y = xycoords.partition(",")
    game = Game.with_id(game_id)
    if not game:
        return code_resp(412)
    p = game.player(player_id)
    if debug():
        fake = {"have_%s" % i: (param_val("s%s"%i) or 0) for i in range(8)}
        for i in range(8):
            fake["seen_%s" % i] = fake["have_%s" % i]
        if Cache.get_seen_checksum((game_id, player_id)) == bfield_checksum(fake.get("seen_%s" % i, 0) for i in range(8)):
            cached_output = Cache.get_output((game_id, player_id))
            if cached_output:
                log.info("got output from cache")
                return text_resp(cached_output)
        p.bitfield_updates(fake, game_id)
        game.sanity_check()
    Cache.set_pos(game_id, player_id, x, y)
    return text_resp(p.output())

@app.route('/netcode/game/<int:game_id>/player/<int:player_id>/tick/', methods = ['POST'])
@app.route('/netcode/game/<int:game_id>/player/<int:player_id>/tick', methods = ['POST'])
def netcode_tick_post(game_id, player_id):
    x = request.form.get("x")
    y = request.form.get("y")
    if Cache.get_seen_checksum((game_id, player_id)) == bfield_checksum(request.form.get("seen_%s" % i, 0) for i in range(8)):
        # checksum and output caching should happen in sync, but it doesn't hurt to check
        cached_output = Cache.get_output((game_id, player_id))
        if cached_output:
            Cache.set_pos(game_id, player_id, x, y)
            return text_resp(cached_output)
    game = Game.with_id(game_id)
    if not game:
        return code_resp(412)
    p = game.player(player_id)
    x = request.form.get("x")
    y = request.form.get("y")
    p.bitfield_updates(request.form, game_id)
    Cache.set_pos(game_id, player_id, x, y)
    return text_resp(p.output())

@app.route('/netcode/game/<int:game_id>/player/<int:player_id>/callback/<path:signal>')
def netcode_signal_callback(game_id, player_id, signal):
    game = Game.with_id(game_id)
    if not game:
        return code_resp(412)
    p = game.player(player_id)
    p.signal_conf(signal)
    return text_resp("cleared")

@app.route('/netcode/game/<int:game_id>/player/<int:player_id>/setSeed', methods=['POST'])
@app.route('/netcode/game/<int:game_id>/player/<int:player_id>/connect', methods=['POST'])
def netcode_connect(game_id, player_id):
    game = Game.with_id(game_id)
    hist = Cache.get_hist(game_id)
    if not hist:
        Cache.set_hist(game_id, player_id, [])
    if game:
        p = game.player(player_id)
        vers = request.form.get("version")
        if p.can_nag and vers and (not version_check(vers)):
            p.signal_send("msg:@dll out of date. (orirando.com/dll)@")
            p.can_nag = False
            p.put()
        game.sanity_check()  # cheap if game is short!
    else:
        # we no longer support uploading seeds
        log.error("game was not already created! %s" % game_id)
    return text_resp("ok")

@app.route('/netcode/areas')
def netcode_get_areas_dot_ori():
    return text_resp(Cache.get_areas())

@app.route('/game/<int:game_id>/delete/')
def game_delete(game_id):
    if int(game_id) < 10000 and not param_flag("override"):
        return text_resp("No", 403)
    game = Game.with_id(game_id)
    if game:
        game.clean_up()
        return text_resp("All according to daijobu")
    else:
        return text_resp("The game... was already dead...", 401)

@app.route('/game/<int:game_id>')
@app.route('/game/<int:game_id>/history/')
def game_show_history(game_id):
    template_values = template_vals("History", "Game %s" % game_id, User.get())
    game = Game.with_id(game_id)
    if game:
        if (game.params and Variation.RACE in game.params.get().variations) and not template_values["race_wl"]:
            return text_code("Access forbidden", 401)
        output = game.summary(int(param_val("p") or 0))
        output += "\nHistory:"
        hls = []
        pids = [int(pid) for pid in param_val("pids").split("|")] if param_val("pids") else []
        hls = game.history(pids) if param_flag("verbose") else [h for h in game.history(pids) if h.pickup().is_shared(share_types)]
        for hl in sorted(hls, key=lambda x: x.timestamp, reverse=True):
            output += "\n\t\t%s Player %s %s" % ((hl.player-1)*"\t\t\t\t", hl.player, hl.print_line(game.start_time))
        return text_resp(output)
    else:
        return text_resp("Game %s not found!" % game_id, 404)

@app.route('/game/<int:game_id>/players/')
def game_list_players(game_id):
        game = Game.with_id(game_id)
        if not game:
            return text_resp("Game %s not found!" % game_id, 404)
        out_lines = []
        for p in game.get_players():
            out_lines.append("Player %s: %s" % (p.pid(), p.bitfields))
            out_lines.append("\t\t" + "\n\t\t".join([hl.print_line(game.start_time) for hl in game.history([p.pid()]) if hl.pickup().is_shared(share_types)]))
        return text_resp("\n".join(out_lines))

@app.route('/game/<int:game_id>/player/<pid>/remove/')
def game_remove_player(game_id, pid):
    key = ".".join([game_id, pid])
    game = Game.with_id(game_id)
    if not game:
        return text_resp("Game %s not found!" % game_id, 404)
    if key in [p.id() for p in game.players]:
        game.remove_player(key)
        return redirect(url_for("game_list_players", game_id=game_id))
    else:
        return text_resp("player %s not in %s for" % (key, game.players), 404)

@app.route("/generator/build", methods=['GET', 'POST'])
def gen_seed_from_params():
    param_key = SeedGenParams.from_json(json.loads(request.form.get('params'))) if request.method == 'POST' else SeedGenParams.from_url(request.args)
    if not param_key:
        return text_resp("Failed to build params!", 500)
    params = param_key.get()
    if not params.generate():
        return text_resp("Failed to generate seed!", 500)
    resp = {"paramId": param_key.id(), "playerCount": params.players, "flagLine": params.flag_line(), 'seed': params.seed, "spoilers": True}
    if params.tracking:
        game = Game.from_params(params, param_val("game_id"))
        resp["gameId"] = game.key.id()
        if debug() and param_flag("test_map_redir"):
                return redirect(url_for("tracking_map", game_id=resp["gameId"], from_test=1))
    if Variation.BINGO in params.variations:
        resp["doBingoRedirect"] = True
        resp["bingoLines"] = params.bingo_lines

    return json_resp(resp)

@app.route('/generator/json')
def gen_seed_from_url():
    param_key = SeedGenParams.from_url(request.args)
    verbose_paths = param_val("verbose_paths") is not None
    if param_key:
        params = param_key.get()
        if params.generate(preplaced={}):
            players = []
            resp = {}
            if params.tracking:
                game = Game.from_params(params, param_val("game_id"))
                key = game.key
                resp["map_url"] = url_for("tracker_show_map", game_id=key.id())
                resp["history_url"] = url_for("game_show_history", game_id=key.id())
            for p in range(1, params.players + 1):
                if params.tracking:
                    seed = params.get_seed(p, key.id(), verbose_paths)
                else:
                    seed = params.get_seed(p, verbose_paths=verbose_paths)
                spoiler = params.get_spoiler(p).replace("\n", "\r\n")
                players.append({"seed": seed, "spoiler": spoiler, "spoiler_url": url_for('get_spoiler_from_params', params_id=param_key.id(), player=p)})
            resp["players"] = players
            return json_resp(resp)
    log.error("param gen failed")
    return json_resp({"error": "param gen failed"}, 500)

@app.route('/generator/seed/<params_id>')
def load_seed_from_params(params_id):
    verbose_paths = param_flag("verbose_paths")
    params = SeedGenParams.with_id(params_id)
    if params:
        pid = int(param_val("player_id") or 1)
        game_id = param_val("game_id")
        if params.tracking and game_id:
            seed = params.get_seed(pid, game_id, verbose_paths)
            game = Game.with_id(game_id)
            user = User.get()
            if game and user:
                player = game.player(pid)
                player.user = user.key
                player.put()
                if game.key not in user.games:
                    user.games.append(game.key)
                    Cache.set_latest_game(user.name, game.key.id())
                    user.put()
        else:
            seed = params.get_seed(pid, verbose_paths=verbose_paths)
        if not debug():
            return text_download(seed, 'randomizer.dat')
        return text_resp(seed)
    else:
        return text_resp("Param %s not found" % params_id, 404)

@app.route('/generator/spoiler/<params_id>')
def get_spoiler_from_params(params_id):
    params = SeedGenParams.with_id(params_id)
    if params:
        player = int(param_val("player_id") or 1)
        spoiler = params.get_spoiler(player)
        if param_flag("download"):
            spoiler = spoiler.replace("\n", "\r\n")
            return text_download(spoiler, 'spoiler.txt')
        return text_resp(spoiler)
    else:
        return text_resp("Param %s not found" % params_id, 404)

@app.route('/generator/aux_spoiler/<params_id>')
def get_aux_spoiler_from_params(params_id):
    params = SeedGenParams.with_id(params_id)
    if params:
        player = int(param_val("player_id") or 1)
        exclude = (param_val("exclude") or "EX KS AC EC HC MS").split(" ") if param_val("exclude") != "" else []
        by_zone = param_flag("by_zone")
        spoiler = params.get_aux_spoiler(exclude, by_zone, player)
        if param_flag("download"):
            return text_download(spoiler.replace("\n", "\r\n"), 'spoiler.txt')
        return text_resp(spoiler)
    else:
        return text_resp("Param %s not found" % params_id, 404)

@app.route('/generator/metadata/<param_id>')
def get_metadata_no_gid(param_id):
    return get_param_metadata(param_id, None)

@app.route('/generator/metadata/<param_id>/<int:game_id>')
def get_param_metadata(param_id, game_id):
    params = SeedGenParams.with_id(param_id)
    if not params:
        return json_resp({"error": "No params found"}, 404)
    res = params.to_json()
    if params.tracking and not game_id:
        game = Game.from_params(params)
        res["gameId"] = game.key.id()
    return json_resp(res)

@app.route('/cache/clear')
def clear_cache():
    Cache.clear()
    return text_resp("cache cleared!")

@app.route('/vanilla')
def get_vanilla_seed():
    return text_download(vanilla_seed, "randomizer.dat")

@app.route('/pickupandlocinfo')
def picks_by_type():
    return json_resp({'picks_by_type': picks_by_type_generator(), 'str_ids': Pickup.strtypes()})

@app.route('/tracker/game/<int:game_id>/')
@app.route('/tracker/game/<int:game_id>/map')
def tracker_show_map(game_id):
    template_values = template_vals("GameTracker", "Game %s" % game_id, User.get())
    template_values['game_id'] = game_id
    # if debug() and param_flag("from_test"):
    #     game = Game.with_id(game_id)
    #     pos = Cache.get_pos(game_id)
    #     hist = Cache.get_hist(game_id)
    #     if any([x is None for x in [game, pos, hist]]):
    #         return redirect(url_for('tests_map_gid', game_id=game_id, from_test=1))
    game = Game.with_id(game_id)
    if game and (Variation.RACE in game.params.get().variations) and not template_values["race_wl"]:
        return text_resp("Access forbidden", 401)
    return render_template(path, **template_values)

@app.route('/tracker/game/<int:game_id>/fetch/gamedata')
def tracker_fetch_gamedata(game_id):
    gamedata = {}
    game = Game.with_id(game_id)
    if not game or not game.params:
        return json_resp({"error": "Game %s not found!" % game_id}, 404)
    params = game.params.get()
    gamedata["paths"] = params.logic_paths
    gamedata["players"] = [p.userdata() for p in game.get_players()]
    gamedata["closed_dungeons"] = Variation.CLOSED_DUNGEONS in params.variations
    gamedata["open_world"] = Variation.OPEN_WORLD in params.variations
    return json_resp(gamedata)

@app.route('/tracker/game/<int:game_id>/fetch/update')
def tracker_update_map(game_id):
    players = {}
    username = param_val("usermap")
    gid_changed = False
    if username and User.latest_game(username) != int(game_id):
        game_id = User.latest_game(username)
        gid_changed = True
    pos = Cache.get_pos(game_id)
    inventories = None
    game = None
    if not pos:
        pos = {}
    for p, (x, y) in pos.items():
        players[p] = {"pos": [y, x], "seen": [], "reachable": []}  # bc we use tiling software, this is lat/lng, and thus coords need inverting

    coords = Cache.get_have(game_id)
    if not coords:
        game = Game.with_id(game_id)
        if not game:
            return json_resp({"error": "Game %s not found" % game_id}, 404)
        coords = { p.pid(): p.have_coords() for p in game.get_players() }
        Cache.set_have(game_id, coords)
    for p, coords in coords.items():
        if p not in players:
            players[p] = {}
        players[p]["seen"] = coords
    reach = Cache.get_reachable(game_id)
    modes = tuple(sorted(param_val("modes").split(" ")))
    need_reach_updates = [p for p in players.keys() if modes not in reach.get(p, {})]
    if need_reach_updates:
        if not game:
            game = Game.with_id(game_id)
            if not game:
                return json_resp({"error": "Game %s not found" % game_id}, 404)
        if not inventories:
            inventories = game.get_inventories(game.get_players(), True, True)
        spawn = game.params.get().spawn or "Glades"
        for p in need_reach_updates:
            inventory = [(pcode, pid, count, False) for ((pcode, pid), count) in inventories["unshared"][p].items()]
            inventory  += [(pcode, pid, count, False) for group, inv in inventories.items()  if group != "unshared" and p in group for ((pcode, pid), count) in inv.items()]
            state = PlayerState(inventory)
            if state.has["KS"] > 8 and "standard-core" in modes:
                state.has["KS"] += 2 * (state.has["KS"] - 8)
            if p not in reach:
                reach[p] = {}
            reach[p][modes] = Map.get_reachable_areas(state, modes, spawn, False)
        Cache.set_reachable(game_id, reach)
    for p in reach:
        players[p]["reachable"] = reach[p][modes]
    res = {"players": players} # , "items": items
    if gid_changed:
        res["newGid"] = game_id
    return json_resp(res)

@app.route('/tracker/game/<int:game_id>/fetch/seen')
def tracker_get_seen(game_id):
    coords = Cache.get_have(game_id)
    if not coords:
        game = Game.with_id(game_id)
        if not game:
            return code_resp(404)
        return json_resp({ p.pid(): p.have_coords() for p in game.get_players() })


@app.route('/tracker/game/<int:game_id>/fetch/pos')
def tracker_get_positions(game_id):
    pos = Cache.get_pos(game_id)
    if pos:
        players = {}
        for p, (x, y) in pos.items():
            players[p] = [y, x]  # bc we use tiling software, this is lat/lng
        return json_resp(players)
    else:
        return code_resp(404)


@app.route('/tracker/game/<int:game_id>/fetch/reachable')
def tracker_get_reachable(game_id):
    hist = Cache.get_hist(game_id)
    reachable_areas = {}
    if not hist or not param_val("modes"):
        return json_resp({}, 404)
    modes = param_val("modes").split(" ")
    game = Game.with_id(game_id)
    spawn = game.params.get().spawn or "Glades"
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
            for area, reqs in Map.get_reachable_areas(state, modes, spawn).items():
                areas[area] = [{item: count for (item, count) in req.cnt.items()} for req in reqs if len(req.cnt)]
            reachable_areas[player] = areas
        return json_resp(reachable_areas)
    except AttributeError:
        log.error("cache invalidated for game %s! Rebuilding..." % game_id)
        game.rebuild_hist()
        return json_resp(reachable_areas)

@app.route('/tracker/game/<int:game_id>/fetch/items/<int:player_id>')
def tracker_get_items_update(game_id, player_id):
    items, _ = Cache.get_items(game_id, player_id)
    if not items:
        coords = Cache.get_have(game_id)
        game = Game.with_id(game_id)
        if not coords:
            if not game:
                return json_resp({"error": "Game %s not found" % game_id}, 404)
            coords = { p.pid(): p.have_coords() for p in game.get_players() }
            Cache.set_have(game_id, coords)
        items, _ = _get_item_tracker_items(coords[pid], game, player_id)
    return json_resp(items)

# why is it like this??
def _get_item_tracker_items(coords, game, player=1):
    relics = game.relics
    data = {
        'skills': set(),
        'trees': set(),
        'events': set(),
        'shards': {'wv': 0, 'gs': 0, 'ss': 0},
        'maps': 0,
        'relics_found': set(),
        'relics': relics,
        'teleporters': set()
    }
    inventories = game.get_inventories(game.get_players(), True, True)
    
    inv = [v for k,v in inventories.items() if k != "unshared"][0] if game.mode == MultiplayerGameType.SHARED else inventories["unshared"][player]
    for ((pcode, pid), count) in inv.items():
        p = Pickup.n(pcode, pid)
        if not p:
            log.warn("couldn't build pickup %s|%s" % (pcode, pid))
            continue
        if pcode == "SK":
            data['skills'].add(p.name)
        elif pcode == "TP":
            data['teleporters'].add(p.name.replace(" teleporter", ""))
        elif pcode == "EV":
            data['events'].add(p.name)
        elif pcode == "RB":
            bid = int(pid)
            if bid == 17:
                data['shards']['wv'] = count
            elif bid == 19:
                data['shards']['gs'] = count
            elif bid == 21:
                data['shards']['ss'] = count
            elif bid > 910 and bid < 922:
                data['relics_found'].add(p.name.replace(" Relic", ""))
            elif bid >= 900 and bid < 910:
                data['trees'].add(p.name.replace(" Tree", ""))
    if data['shards']['wv'] > 2:
        data['events'].add("Water Vein")
    if data['shards']['gs'] > 2:
        data['events'].add("Gumon Seal")
    if data['shards']['ss'] > 2:
        data['events'].add("Sunstone")
    for thing in ['trees', 'skills', 'events', 'relics_found', 'teleporters']:
        data[thing] = list(data[thing])
    data['maps'] = len([1 for c in coords if c in range(24, 60, 4)])
    Cache.set_items(game.key.id(), player, (data, inventories), game.is_race)
    return data, inventories


@app.route('/tracker/game/<int:game_id>/fetch/player/<int:player_id>/seed')
def tracker_fetch_seed(game_id, player_id):
    game = Game.with_id(game_id)
    if not game or not game.params:
        return json_resp({"error": "game %s not found!" % game_id}, 404)
    player = game.player(player_id, False)
    if not player:
        return json_resp({"error": "game %s does not contain player %s!" % (game_id, player_id, 404)})
    res = {"seed": {}, 'name': player.name()}
    params = game.params.get()
    if Variation.BINGO in params.variations:
        bingo = BingoGameData.with_id(game_id)
        if not bingo:
            return json_resp({"error": "no bingo data found for game %s" % game_id}, 404)
        team = bingo.team(player_id, cap_only=False)
        if not team:
            return json_resp({"error": "No team found for player %s!" % player_id}, 404)
        team = team.pids()
        player_id = team.index(player_id) + 1
    for (coords, code, id, _) in params.get_seed_data(player_id):
        res["seed"][coords] = Pickup.name(code, id)
    return json_resp(res)

@app.route('/tracker/game/<int:game_id>/items')
@app.route('/tracker/game/<int:game_id>/<int:player_id>/items')
def tracker_item_tracker(game_id, player_id=1):
    game = Game.with_id(game_id)
    template_values = template_vals("ItemTracker", "Game %s" % game_id, User.get())
    if game and Variation.RACE in game.params.get().variations and not template_values["race_wl"]:
        return text_code("Access forbidden", 401)
    template_values['game_id'] = game_id
    template_values['player_id'] = player_id
    return render_template(path, **template_values)

@app.route('/user/settings')
def user_get_settings():
    res = {}
    res["names"] = [user.name.lower() for user in User.query().fetch()]
    user = User.get()
    if user:
        res["teamname"] = user.teamname or "%s's team" % user.name
        res["theme"] = "dark" if user.dark_theme else "light"
    return json_resp(res)

@app.route('/user/settings/update')
def user_set_settings():
    user = User.get()
    if user:
        name = param_val("name")
        teamname = param_val("teamname")
        if name and name != user.name:
            if not user.rename(name):
                return text_resp("Rename failed!")
        if teamname and teamname != user.teamname:
            user.teamname = teamname
            user.put()
        if name or teamname:
            return text_resp("Rename successful!")
        else:
            return text_resp("No settings changed")
        

    else:
        return text_resp("You are not logged in!")

@app.route('/user/settings/number/<new_num>') 
def user_set_number(new_num):
    user = User.get()
    if user:
        if int(new_num) > 0:
            user.pref_num = int(new_num)
            user.put()
            return resp_text("Preferred player number for %s set to %s" % (user.name, new_num))
        else:
            return resp_text("Preferred player number must be >0", 400)
    else:
        return resp_text("You are not logged in!", 401)

@app.route('/user/settings/theme/<new_theme>')
def user_set_theme(new_theme):
    user = User.get()
    if user:
        user.theme = new_theme
        user.put()
        return resp_text("theme for %s set to %s" % (user.name, new_theme))
    else:
        return resp_text("You are not logged in!", 401)

@app.route('/theme/toggle')
def user_toggle_darkmode():
    target_url = unquote(param_val("redir")) or "/"
    user = User.get()
    if user:
        user.dark_theme = not user.dark_theme
        user.put()
    return redirect(target_url)

@app.route('/user/settings/verbose') # ToggleVerbose,
def user_toggle_verbose():
    user = User.get()
    if user:
        user.verbose = not user.verbose
        user.put()
        return text_resp("verbose seed spoilers set to %s" % user.verbose)
    else:
        return resp_text("You are not logged in!", 401)

@app.route('/tracker/spectate/<name>') # LatestMap
def get_map_by_name(name):
    latest = User.latest_game(name)
    if latest:
        return redirect("%s?%s" % (url_for('tracker_show_map', game_id=latest), "&".join(["usermap=" + name] + ["%s=%s" % (k, v) for k, v in request.args.items()])))
    else:
        return text_resp("User not found or had no games on record", 404)

@app.route('/logichelper') #  LogicHelper
def logic_helper():
        template_values = template_vals("LogicHelper", "Logic Helper", User.get())
        template_values.update({'is_spoiler': "True", 'pathmode': param_val('pathmode'), 'HC': param_val('HC'),
                           'EC': param_val('EC'), 'AC': param_val('AC'), 'KS': param_val('KS'),
                           'skills': param_val('skills'), 'tps': param_val('tps'), 'evs': param_val('evs')})
        return render_template(path, **template_values)

@app.route('/faq') #  Guides
def faqs_guides():
    template_values = template_vals("HelpAndGuides", "Help and Guides", User.get())
    return render_template(path, **template_values)


@app.route('/rebinds') # RebindingsEditor
def rebinding_tool():
    template_values = template_vals("RebindingsEditor", "Ori DERebindings Editor", User.get())
    return render_template(path, **template_values)

@app.route('/reroll')
@oidc.require_login
def reroll_seed():
    user = User.get()
    if not user.games:
        return text_resp("no games found", 404)
    game_key = user.games[-1]
    old_game = game_key.get()
    if not old_game.params:
        return text_resp("latest game does not have params", 404)
    old_params = old_game.params.get().to_json()
    old_params['seed'] = str(random.randint(0, 1000000000))
    new_params = SeedGenParams.from_json(old_params).get()
    if not new_params.generate():
        return text_resp( "Failed to generate seed!", 500)
    game = Game.from_params(new_params)
    if Variation.BINGO in new_params.variations:
        url = "/bingo/board?game_id=%s&fromGen=1&seed=%s&bingoLines=%s" % (game.key.id(), new_params.seed, new_params.bingo_lines)
        b = old_game.bingo_data.get()
        if b.discovery and b.discovery > 0:
            url += "&disc=%s" % b.discovery
        return redirect(url)
    return redirect("%s?param_id=%s&game_id=%s" % (url_for('main_page'), new_params.key.id(), game.key.id()))

@app.route('/discord')
def discord_redirect():
    return redirect("https://discord.gg/TZfue9V")

@app.route('/discord/dev')
def dev_discord_redirect():
    return redirect("https://discord.gg/sfUr8ra5P7")

@app.route('/reset/<int:game_id>') # handler=ResetGame
def reset_game(game_id):
    game = Game.with_id(game_id)
    if not game:
        return text_resp("Game %s not found!" % game_id, 404)
    user = User.get()
    if User.is_admin() or (user and user.key == game.creator):
        game.reset()
        return text_resp("Game reset successfully")
    else:
        return text_resp("Can't restart a game you didn't create...", 401)

@app.route('/transfer/<int:game_id>/<int:player_id>') # ResetAndTransfer
def reset_and_transfer_game(game_id, player_id):
    game = Game.with_id(game_id)
    if not game:
        return text_resp("Game %s not found!" % game_id, 404)
        user = User.get()
        if (User.is_admin() or (user and user.key == game.creator)):
            new_user = User.get_by_name(new_owner)
            if not new_user:
                 return text_resp("Couldn't find user %s" % new_owner, 404)
            old_creator = game.creator
            game.creator = new_user.key
            game.reset()
            return text_resp("Game reset; ownership transferred from %s to %s" % (user.name, new_user.name))
        else:
            return text_resp("Can't restart a game you didn't create...", 401)

@app.route('/plando/<seed_name>/upload', methods=['POST'])   #PlandoUpload
def plando_upload(seed_name): 
    user = User.get()
    if not user:
        log.error("Error: unauthenticated upload attempt")
        return code_resp(401)
    seed_data = json.loads(request.form.get("seed"))
    old_name = seed_data["oldName"]
    old_seed = user.plando(old_name)
    if old_seed:
        res = old_seed.update(seed_data)
    else:
        res = Seed.new(seed_data)
    return text_resp(str(res))

@app.route('/plando/<seed_name>/edit')   #PlandoEdit
def plando_edit(seed_name):
    user = User.get()
    template_values = template_vals("PlandoBuilder", "Plando Editor: %s" % (seed_name), user)
    template_values['seed_name'] = seed_name
    if user:
        seed = user.plando(seed_name)
        template_values['authed'] = "True"
        if seed:
            template_values['seed_desc'] = seed.description
            template_values['seed_hidden'] = seed.hidden or False
            template_values['seed_data'] = seed.get_plando_json()
    return render_template(path, **template_values)

@app.route('/plando/<seed_name>/delete')   #PlandoDelete
def plando_delete(seed_name):
    user = User.get()
    if not user:
        log.error("Error: unauthenticated delete attempt")
        return code_resp(401)
    seed = user.plando(seed_name)
    if not seed:
        log.error("couldn't find seed %s when trying to delete!" % seed_name)
        return code_resp(404)
    seed.key.delete()
    return redirect(url_for("plando_author_index", author_name=user.name))

@app.route('/plando/<seed_name>/rename/<new_name>')   #PlandoRename
def plando_rename(seed_name, new_name):
    user = User.get()
    if not user:
        return text_resp("Error: unauthenticated rename attempt", 401)
    old_seed = user.plando(seed_name)
    if not old_seed:
        return text_resp("couldn't find old seed when trying to rename!", 404)
    new_seed = clone_entity(old_seed, id="%s:%s" % (user.key.id(), new_name), name=new_name)
    if new_seed.put():
        if not param_flag("cp"):
            old_seed.key.delete()
        return redirect(url_for("plando_view", author_name=user.name, seed_name=new_name))
    else:
        return text_resp("Failed to rename seed", 500)

@app.route('/plando/<seed_name>/hideToggle')   #PlandoToggleHide
def plando_toggle_hide(seed_name):
    user = User.get()
    if not user:
        log.error("Error: unauthenticated hide attempt")
        return code_resp(401)
    seed = user.plando(seed_name)
    if not seed:
        log.error("couldn't find seed when trying to hide!")
        return code_resp(404)
    seed.hidden = not (seed.hidden or False)
    seed.put()
    return redirect(url_for("plando_view", author_name=user.name, seed_name=seed_name))

@app.route('/plando/<author_name>/<seed_name>/download') # PlandoDownload
def plando_download(author_name, seed_name):
    seed = Seed.get(author_name, seed_name)
    if seed:
        if seed.hidden:
            user = User.get()
            if not user or user.key != seed.author_key:
                return text_resp("seed %s (by user %s) not found" % (seed_name, author_name), 404)
        params = SeedGenParams.from_plando(seed, param_flag("tracking"))
        url = url_for("main_page", param_id=params.key.id())
        if params.tracking:
            game = Game.from_params(params, param_val("game_id"))
            url += "&game_id=%s" % game.key.id()
        return redirect(url)
    else:
        return text_resp("seed %s (by user %s) not found" % (seed_name, author_name), 404)


@app.route('/plando/<author_name>/<seed_name>/') # PlandoView,
def plando_view(author_name, seed_name):
    authed = False
    user = User.get()
    seed = Seed.get(author_name, seed_name)
    if seed:
        if user and user.key == seed.author_key:
            authed = True
        template_values = template_vals("SeedDisplayPage", "%s by %s" % (seed_name, author_name), user)
        template_values.update({'players': seed.players, 'seed_data': seed.get_plando_json(),
            'seed_name': seed_name, 'author': author_name, 'authed': authed, 
            'seed_desc': seed.description, 'game_id': Game.get_open_gid()})
        hidden = seed.hidden or False
        if not hidden or authed:
            if hidden:
                template_values['seed_hidden'] = True
            return render_template(path, **template_values)
    return text_resp("seed %s (by user %s) not found" % (seed_name, author_name), 404)

@app.route('/plando/reachable', methods=['POST']) #PlandoReachable
def plando_reachable():
    modes = json.loads(request.form.get("modes"))
    codes = []
    for item, count in json.loads(request.form.get("inventory")).items():
        codes.append(tuple(item.split("|") + [count, False]))
    areas = {}
    for area, reqs in Map.get_reachable_areas(PlayerState(codes), modes).items():
        areas[area] = [{item: count for (item, count) in req.cnt.items()} for req in reqs if len(req.cnt)]
    return json_resp(areas)

@app.route('/plando/fillgen') #PlandoFillGen
def plando_fillgen():
    qparams = request.args
    forced_assignments = dict([(int(a), b) for (a, b) in ([tuple(fass.split(":")) for fass in (qparams.get('fass') or "").split("|") if fass])])
    param_key = SeedGenParams.from_url(qparams)
    params = param_key.get()
    if params.generate(preplaced=forced_assignments):
        return text_resp(params.get_seed(1))
    else:
        return code_resp(422)

@app.route('/plandos')      #AllAuthors
def plando_index():
    seeds = Seed.query(Seed.hidden != True)
    out = '<html><head><title>All Plando Authors</title></head><body><h5>All Seeds</h5><ul style="list-style-type:none;padding:5px">'
    authors = Counter([seed.author_key.get().name if seed.author_key else seed.author for seed in seeds])
    for author, cnt in authors.most_common():
        if cnt > 0:
            url = "/plando/%s" % author
            out += '<li style="padding:2px"><a href="%s">%s</a> (%s plandos)</li>' % (url, author, cnt)
    out += "</ul></body></html>"
    return make_resp(out)

@app.route('/plando/<author_name>')
def plando_author_index(author_name):
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
            url = url_for("plando_view", author_name=author_name, seed_name=seed.name)
            flags = ",".join(seed.flags)
            out += '<li style="padding:2px"><a href="%s">%s</a>: %s (%s players, %s)' % (url, seed.name, seed.description.partition("\n")[0], seed.players, flags)
            if owner:
                out += ' <a href="%s">Edit</a>' % url_for("plando_edit", seed_name=seed.name)
                if seed.hidden:
                    out += " (hidden)"
            out += "</li>"
        out += "</ul></body></html>"
        return make_resp(out)
    else:
        if owner:
            return make_resp("<html><body>You haven't made any seeds yet! <a href='%s'>Start a new seed</a></body></html>" % url_for('plando_edit', seed_name="newSeed"))
        else:
            return make_resp('<html><body>No seeds by user %s</body></html>' % author_name)

@app.route('/dll')                 
def dll():
    return redirect("https://github.com/sparkle-preference/OriDERandomizer/raw/master/Assembly-CSharp.dll")

@app.route('/dll/beta')            
def dll_beta():
    return redirect("https://github.com/sparkle-preference/OriDERandomizer/raw/master/Assembly-CSharp.dll")
@app.route('/tracker')             
def tracker():
    return redirect("https://github.com/jeflefou/OriDETracker/releases/tag/v3.3.2")

@app.route('/league/rules')
def league_rules():
    return redirect("https://docs.google.com/document/d/1TDmDPb-zDFQ6gxw_RN-b4S9UxcDQu0ySuXfuWefLZ9c/edit?tab=t.0")

@app.route('/trickglossary')       
def trickglossary():
    return redirect('https://docs.google.com/document/d/1vjDiXz8UPiIOtUVKPlgzjBn9lrCE4y95EwPt0WnQF_U/')

@app.route('/trickrepo')           
def trickrepo():
    return redirect('https://www.youtube.com/channel/UCowq0m-wHdwi0vpG3jY1hFA')


@app.route('/bingo/board') #BingoBoard =     
@app.route('/bingo/spectate') #BingoBoard =     
def bingo_board():
    user = User.get()
    template_values = template_vals("Bingo", "OriDE Bingo", user)
    if user and user.pref_num:
        template_values['pref_num'] = user.pref_num
    return render_template(path, **template_values)

@app.route('/bingo/game/<int:game_id>/fetch') #BingoGetGame =     
def bingo_get_game(game_id):
    now = datetime.utcnow()
    first = param_flag("first")
    res = Cache.get_board(game_id)
    if first or not res:
        bingo = BingoGameData.with_id(game_id)
        if not bingo:
            return text_resp("Bingo game %s not found" % game_id, 404)
        res = bingo.get_json(first)
        if param_flag("time"):
            server_now = timegm(now.timetuple()) * 1000
            client_now = int(param_val("time"))
            res["offset"] = server_now - client_now
    return json_resp(res)

@app.route('/bingo/game/<int:game_id>/start') #BingoStartCountdown =     
def bingo_start_game(game_id):
    res = {}
    now = datetime.utcnow()
    bingo = BingoGameData.with_id(game_id)
    if not bingo:
        return text_resp("Bingo game %s not found" % game_id, 404)
    user = User.get()
    if not user or bingo.creator != user.key:
        return text_resp("Only the creator can start the game", 401)
    if bingo.start_time:
        return text_resp("Game has already started!", 412)
    if bingo.teams_shared:
        p = bingo.game.get().params.get()
        if not p.sync.cloned:
            for team in bingo.teams:
                if p.players != len(team.teammates) + 1:
                    log.error("team %s did not have %s players!", team, p.players)
                    return text_resp("Not all teams have the correct number of players!", 412)
    bingo.start_time = datetime.utcnow() + timedelta(seconds=15)
    startStr = "miscBingo Game %s started!" % game_id
    bingo.event_log.append(BingoEvent(event_type=startStr, timestamp=bingo.start_time))
    res = bingo.get_json()

    server_now = timegm(now.timetuple()) * 1000
    client_now = int(param_val("time"))
    res["offset"] = server_now - client_now
    jsonres = json_resp(res)
    bingo.put()
    return jsonres

@app.route('/bingo/game/<int:game_id>/add/<int:player_id>') #BingoAddPlayer =     
@transactional(xg=True)
def bingo_add_player(game_id, player_id):
    bingo = BingoGameData.with_id(game_id)
    join_team = param_flag("joinTeam")
    if not bingo:
        return text_resp("Bingo game %s not found" % game_id, 404)
    if join_team and not bingo.teams_allowed:
        return text_resp("Teams are forbidden in this game", 412)
    if player_id in bingo.player_nums():
        return text_resp("Player id already in use!", 409)

    player = bingo.init_player(player_id)
    if join_team:
        cap_id = int(param_val("joinTeam"))
        team = bingo.team(cap_id)
        if not team:
            return text_resp("Team %s not found" % cap_id, 412)
        if player_id in team.pids():
            return text_resp("%s already in team %s" % (player_id, cap_id), 412)
        team.teammates.append(player.key)
    else:
        bingo.teams.append(BingoTeam(captain = player.key, teammates = []))
    seed = bingo.get_seed(player_id)
    if not seed:
        return text_resp( "Team has maximum number of players allowed!", 412)
    user = User.get()
    if user:
        player.user = user.key
        player.put()
        if bingo.game not in user.games:
            user.games.append(bingo.game)
            Cache.set_latest_game(user.name, int(game_id), True)
            user.put()
    res = bingo.get_json()
    if bingo.meta:
        bingo.update({}, player_id, game_id, True)
        res = Cache.get_board(game_id)
    res['player_seed'] = seed
    bingo.put()
    return json_resp(res)


@app.route('/bingo/game/<int:game_id>/remove/<int:player_id>') #BingoRemovePlayer =     
def bingo_remove_player(game_id, player_id):
    bingo = BingoGameData.with_id(game_id)
    if not bingo:
        return text_resp("Bingo game %s not found" % game_id, 404)
    user = User.get()
    if not user or bingo.creator != user.key:
        return text_resp("Only the creator can remove players", 401)
    bingo = bingo.remove_player(player_id).get()
    res = bingo.get_json()
    return json_resp(res)

@app.route('/bingo/game/<int:game_id>/seed/<int:player_id>') #BingoDownloadSeed =     
def bingo_download_seed(game_id, player_id):
    bingo = BingoGameData.with_id(game_id)
    if not bingo:
        return text_resp("Bingo game %s not found" % game_id, 404)
    seed = bingo.get_seed(player_id)
    if not seed:
        return text_resp("No seed found for player %s.%s" % (game_id, player_id), 412)

    if not debug():
        return text_download(seed, 'randomizer.dat')
    else:
        return text_resp(seed)

@app.route('/bingo/new') #BingoCreate =     
def bingo_create_game():
        now = datetime.utcnow()
        difficulty = param_val("difficulty") or "normal"
        skills = param_val("skills")
        cells = param_val("cells")
        skills = int(skills) if skills and skills != "NaN" else 3
        cells = int(cells) if cells and cells != "NaN" else 3
        show_info = param_flag("showInfo")
        misc_raw = param_val("misc")
        misc_pickup = Pickup.from_str(misc_raw) if misc_raw and misc_raw != "NO|1" else None
        skill_pool = [Skill(x) for x in [0, 2, 3, 4, 5, 8, 12, 14, 50, 51]]
        cell_pool  = [Multiple.with_pickups([AbilityCell(1), AbilityCell(1)]), HealthCell(1), EnergyCell(1)]
        seed = param_val("seed")
        rand = random.Random()
        rand.seed(seed)

        start_pickups = rand.sample(skill_pool, skills)
        for _ in range(cells):
            start_pickups.append(rand.choice(cell_pool))
        if misc_pickup:
            start_pickups.append(misc_pickup)
        start_with = Multiple.with_pickups(start_pickups)
        key = Game.new(_mode = "Bingo", _shared = [])
        if show_info and start_with:
            tps = []
            skills = []
            misc = []
            cells = Counter()
            for pick in start_with.children:
                if pick.code == "TP":
                    tps.append(pick.name[:-11])
                elif pick.code == "SK":
                    skills.append(pick.name)
                elif pick.code in ["HC", "EC", "AC"]:
                    cells[pick.code]+=1
                else:
                    misc.append(pick.name)
            sw_parts = []
            if skills:
                sw_parts.append("Skills: " + ", ".join(skills))
            if tps:
                sw_parts.append("TPs: " + ", ".join(tps))
            if cells:
                sw_parts.append("Cells: " + ", ".join([cell if amount == 1 else "%s %ss" % (amount, cell) for cell,amount in cells.items()]))
            if misc:
                sw_parts.append(", ".join(misc))
        base = vanilla_seed.split("\n")
        base[0] = "OpenWorld,Bingo|Bingo Game %s" % key.id()
        if start_with:
            mu_line = "2|MU|%s|Glades" % start_with.id
            base.insert(1, mu_line)
        
        game = key.get()
        d = int(param_val("discCount") or 0)
        lockout = bool(int(param_val("lockout") or 0))
        meta = param_flag("meta")
        bingo = BingoGameData(
            id            = key.id(),
            board         = BingoGenerator.get_cards(rand, 25, False, difficulty, True, d, meta, lockout, False),
            difficulty    = difficulty,
            teams_allowed = param_flag("teams"),
            game          = key,
            rand_dat      = "\n".join(base),
            lockout       = lockout,
            meta          = meta
        )
        if d:
            bingo.discovery = d
            bingo.seed = seed
        if param_flag("lines"):
            bingo.bingo_count  = int(param_val("lines"))
        if param_flag("squares"):
            bingo.square_count = int(param_val("squares"))
        user = User.get()
        eventStr = "misc"
        if user:
            bingo.creator = user.key
        if not user or param_flag("noTimer"):
            bingo.start_time = now
            eventStr += "Bingo Game %s started!" % key.id()
        else:
            eventStr += "Bingo Game %s created!" % key.id()

        if bingo.square_count and bingo.square_count > 0:
            eventStr += " squares to win: %s" % bingo.square_count
            if bingo.lockout:
                eventStr += ", lockout"
        elif bingo.bingo_count > 0:
            eventStr += " bingos to win: %s" % bingo.bingo_count
        if show_info:
            bingo.subtitle = " | ".join(sw_parts)
            eventStr += ", starting with: " + ", ".join(sw_parts)
        bingo.event_log.append(BingoEvent(event_type=eventStr, timestamp=now))
        res = bingo.get_json(True)

        if param_flag("time"):
            server_now = timegm(now.timetuple()) * 1000
            client_now = int(param_val("time"))
            res["offset"] = server_now - client_now

        bkey = bingo.put()
        game.bingo_data = bkey
        game.put()
        return json_resp(res)

@app.route('/bingo/spectate/<name>') #BingoUserSpectate =     
def bingo_user_board(name):
    game_id = Cache.get_latest_game(name, bingo=True)
    if not game_id:
        user = User.get_by_name(name)
        if not user:
            return text_resp("User '%s' not found" % name, 404)
        game_keys = user.games[::-1]
        game_id = None
        for key in game_keys:
            game = key.get()
            if game.bingo_data:
                game_id = game.key.id()
                break
        if not game_id:
            return text_resp("Could not find any bingo games for user '%s'" % name, 404)
    return redirect(url_for('bingo_board_spectate', game_id=4 + game_id*7))

@app.route('/bingo/userboard/<name>/') #BingoUserboard =     
def bingo_userboard(name):
    user = User.get_by_name(name)
    if not user:
        return text_resp("User '%s' not found" % name, 404)
    template_values = {'app': "Bingo", 'title': "%s's Bingo Board" % user.name}
    template_values['user'] = user.name
    template_values['dark'] = user.dark_theme
    if user.pref_num:
        template_values['pref_num'] = user.pref_num
    if user.theme:
        template_values['theme'] = user.theme
    return render_template(path, **template_values)

@app.route('/bingo/userboard/<name>/fetch/<game_id>') #UserboardTick =     
def bingo_userboard_tick(name, game_id):
    cur_gid = int(game_id)
    now = datetime.utcnow()
    game_id = Cache.get_latest_game(name, bingo=True)
    if not game_id:
        user = User.get_by_name(name)
        if not user:
            return text_resp("User '%s' not found" % name, 404)
        game_keys = user.games[::-1]
        game_id = None
        for key in game_keys:
            game = key.get()
            if game.bingo_data:
                game_id = game.key.id()
                break
        if not game_id:
            return text_resp("Could not find any bingo games for user '%s'" % name, 404)
    first = cur_gid != game_id
    res = {}
    bingo = BingoGameData.with_id(game_id)
    if not bingo:
        return text_resp("Bingo game %s not found" % game_id, 404)
    res = bingo.get_json(first)
    if param_flag("time"):
        server_now = timegm(now.timetuple()) * 1000
        client_now = int(param_val("time"))
        res["offset"] = server_now - client_now
    return json_resp(res)

@app.route('/bingo/from_game/<int:game_id>') #AddBingoToGame =     
def add_bingo_to_game(game_id):
        now = datetime.utcnow()
        game_id = int(game_id)
        difficulty = param_val("difficulty") or "normal"
        if not game_id or int(game_id) < 1:
            return text_resp("please provide a valid game id", 404)
        game = Game.with_id(game_id)
        if not game:
            return text_resp("game not found", 404)
        if not game.params:
            return text_resp("game did not have required seed data", 412)
        if game.mode in [MultiplayerGameType.SPLITSHARDS]:
            return text_resp("splitshards bingo are not currently supported", 412)
        params = game.params.get()
        seed = param_val("seed") or params.seed
        rand = random.Random()
        rand.seed(seed)

        d = int(param_val("discCount") or 0)
        lockout = bool(int(param_val("lockout") or 0))
        meta = param_flag("meta")
        test_iters = int(param_val("testIters") or 0)
        if test_iters: # this is like having test code
            edges = [0,1,2,3,4,5,9,10,14,15,19,20,21,22,23,24]
            metacnt = 0
            symcnt = 0
            actvcnt = 0
            edgesymcnt = 0
            doublesymcnt = 0
            edgedisccnt = 0
            symdisccnt = 0
            
            for i in range(test_iters):
                iseed = seed+str(i)
                rand.seed(iseed)
                cards = BingoGenerator.get_cards(rand, 25, True, difficulty, Variation.OPEN_WORLD in params.variations, d, meta, lockout, Variation.KEYSANITY in params.variations)

                if not all([card.square in range(2,23,5) for card in cards if card.name == "VertSym"]):
                    log.error("seed %s: VertSym: %s", iseed, [(card.square, card.square in range(2,23,5)) for card in cards if card.name == "VertSym"])
                if not all([card.square in range(10,15) for card in cards if card.name == "HorizSym"]):
                    log.error("seed %s: HorizSym: %s", iseed, [(card.square, card.square in range(10,15)) for card in cards if card.name == "HorizSym"])
                if not all([(len(sg['name']) <3) for card in cards if card.name == "Activate Squares" for sg in card.subgoals ]):
                    log.error("seed %s: Activate Squares: %s", iseed, [((sg['name'])) for card in cards if card.name == "Activate Squares" for sg in card.subgoals])
                if not len([c for c in cards if c.meta]) <= 5:
                    log.error("seed %s:total count: %s", iseed, len([c for c in cards if c.meta]))
                metacnt += len([c for c in cards if c.meta])
                actvcnt += len([c for c in cards if c.name == "Activate Squares"])
                syms = [c for c in cards if "Sym" in c.name]
                symcnt += len(syms)
                edgesymcnt += len([c for c in syms if c.square in edges])
                doublesymcnt += (1 if len(syms) == 2 else 0)
                if d:
                    bingo = BingoGameData(
                        id            = game_id,
                        board         = cards,
                        difficulty    = difficulty,
                        subtitle      = params.flag_line(),
                        teams_allowed = param_flag("teams"),
                        teams_shared  = params.players > 1 and params.sync.mode == MultiplayerGameType.SHARED,
                        game          = game.key,
                        lockout       = lockout,
                        meta          = meta,
                        seed          = iseed
                    )
                    discsquares = bingo.discovery_squares(d)
                    symdisccnt += len([c for c in syms if c.square in discsquares])
                    edgedisccnt += len([s for s in discsquares if s in edges])
            log.info('-------------')
            for name, num in [("meta squares", metacnt), ("square cards", actvcnt), ("symmetry squares", symcnt), ("symmetry squares on edges", edgesymcnt), ("boards with both symmetry squares", doublesymcnt), ("discovery squares on the edge", edgedisccnt), ("symmetry discovery squares", symdisccnt)]:
                log.info("%s %3d/%s = %s", (name+":").ljust(36), num, test_iters, float(num)/float(test_iters))
            return text_resp("test retry", 420)

        bingo = BingoGameData(
            id            = game_id,
            board         = BingoGenerator.get_cards(rand, 25, True, difficulty, Variation.OPEN_WORLD in params.variations, d, meta, lockout, Variation.KEYSANITY in params.variations),
            difficulty    = difficulty,
            subtitle      = params.flag_line(),
            teams_allowed = param_flag("teams"),
            teams_shared  = params.players > 1 and params.sync.mode == MultiplayerGameType.SHARED,
            game          = game.key,
            lockout       = lockout,
            meta          = meta
        )
        if d:
            bingo.seed = seed
            bingo.discovery_squares(d)

        if bingo.teams_shared and not bingo.teams_allowed:
            log.warning("Teams are required for shared seeds! Overriding invalid config")
            bingo.teams_allowed = True

        if param_flag("lines"):
            bingo.bingo_count  = int(param_val("lines"))
        if param_flag("squares"):
            bingo.square_count = int(param_val("squares"))
        user = User.get()
        eventStr = "misc"
        if user:
            bingo.creator = user.key
        if not user or param_flag("noTimer"):
            bingo.start_time = now
            eventStr += "Bingo Game %s started!" % game_id
        else:
            eventStr += "Bingo Game %s created!" % game_id
        if bingo.square_count and bingo.square_count > 0:
            eventStr += " squares to win: %s" % bingo.square_count
            if bingo.lockout:
                eventStr += ", lockout"
        elif bingo.bingo_count > 0:
            eventStr += " bingos to win: %s" % bingo.bingo_count
        bingo.event_log.append(BingoEvent(event_type=eventStr, timestamp=now))
        res = bingo.get_json(True)
        if param_flag("time"):
            server_now = timegm(now.timetuple()) * 1000
            client_now = int(param_val("time"))
            res["offset"] = server_now - client_now

        for p in game.get_players():
            game.remove_player(p.key.id())
        bkey = bingo.put()
        game.bingo_data = bkey
        game.put()
        return json_resp(json.dumps(res))

@app.route('/netcode/game/<int:game_id>/player/<int:player_id>/bingo', methods=['POST']) #HandleBingoUpdate    
def netcode_player_bingo_tick(game_id, player_id):
    bingo = BingoGameData.with_id(game_id)
    if not bingo:
        return text_resp("Bingo game %s not found" % game_id, 404)
    if int(player_id) not in bingo.player_nums():
        return text_resp("player not in game! %s" % bingo.player_nums(), 412)
    bingo_data = json.loads(request.form.get("bingoData")) if request.form.get("bingoData") else None
    # if debug and player_id in test_data:
    #     bingo_data = test_data[player_id]['bingoData']
    try:
        bingo.update(bingo_data, player_id, game_id)
    except:
        sleep(3)
        bingo.update(bingo_data, player_id, game_id)
    return code_resp(200)

@app.route('/bingo/bingothon/<int:game_id>/player/<int:player_id>') #GetBingothonJson    
def bingothon_fetch_data(game_id, player_id):
    res = {"cards": []}
    bingo = BingoGameData.with_id(game_id)
    if not bingo:
        return json_resp({"error": "bingo game not found"}, 404)
    p = bingo.player(player_id)
    if not p:
        return json_resp({"error": "player not found in game"}, 404)
    for card in bingo.board:
        res["cards"].append(card.bingothon_json(p))
    if bingo.discovery:
        res["disc_squares"] = bingo.disc_squares
    return json_resp(res)

@app.route('/version/latest')
def version_txt():
    return text_resp("%s.%s.%s" % tuple(VER))

@app.route('/version/minimum')
def min_version_txt():
    return text_resp("%s.%s.%s" % tuple(MIN_VER))

@app.route('/version/beta')
def beta_version_txt():
    return text_resp("%s.%s.%s" % tuple(BETA_VER))


@app.route('/version')
@app.route('/version/json')
def version_json():
    return json_resp({
        "latest": "%s.%s.%s" % tuple(VER),
        "minimum": "%s.%s.%s" % tuple(MIN_VER),
        "beta": "%s.%s.%s" % tuple(BETA_VER),
    })


    
@app.route('/patchnotes/3.x')
def v3_patchnotes_redir():
    return redirect("https://docs.google.com/document/d/1tprqq7mUJMGcgAA0TM-O5FeOklzz4dOReB0Nru3QlsI")

@app.route('/patchnotes/4.0.x')
def v4_0_patchnotes_redir():
    return redirect("https://docs.google.com/document/d/1781ALoPPN1k_yo5rfoapjTIiX3iyihXPty_pVVG26LQ")

@app.route('/patchnotes')
@app.route('/patchnotes/4.1.x')
def v4_1_patchnotes_redir():
    return redirect("https://docs.google.com/document/d/16xmoy3ooM9275vdY6BPeS5wmnplzSxR2YEzCapZy4Wc")
