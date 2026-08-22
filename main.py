# py imports
import random
import json
import os
import re
import requests
from html import escape
from collections import Counter, defaultdict
from time import sleep, monotonic
from calendar import timegm
from datetime import datetime, timedelta

# web imports
import logging as log
from urllib.request import urlopen
from urllib.parse import unquote, quote_plus
from flask import Flask, render_template, request, make_response, url_for, redirect, g, Response, get_flashed_messages, session
from werkzeug.middleware.proxy_fix import ProxyFix
from google.cloud import ndb
import google.cloud.logging

# project imports
import netcode
from archipelago import build_apworld
from archipelago.yaml_emit import DATA_VERSION as AP_DATA_VERSION
from flask_oidc.signals import after_logout
from oidc import make_oidc
from seedbuilder.seedparams import SeedGenParams, seed_mode_problem
from seedbuilder.vanilla import seedtext as vanilla_seed
from enums import MultiplayerGameType, ShareType, Variation
from models import ndb_wsgi_middleware, Game, Player, SavedSeedParams, Seed, User, BingoGameData, BingoEvent, BingoTeam, CustomLogic, trees_by_coords, LegacyUser, bingo_lock, AnnouncedPatchNotes
from bingo import BingoGenerator
from cache import Cache
from util import parse_fass, coord_correction_map, clone_entity, all_locs, picks_by_type_generator, param_val, param_flag, param_true, debug, template_root, VER, MIN_VER, BETA_VER, game_list_html, version_check, template_vals, layout_json, bfield_checksum, netperf, NETPERF_TAG, json_default, seed_sync_id, is_mw_manifest_loc, MULTIWORLD, ARCHIPELAGO, CANONICAL_HOST, REDIRECT_HOSTS, PATCHNOTES_WEBHOOK_MAIN, PATCHNOTES_WEBHOOK_DEV
from reachable import Map, PlayerState
from pickups import Pickup, Skill, AbilityCell, HealthCell, EnergyCell, Multiple

# handlers
# from bingo import routes as bingo_routes

path='index.html'
app = Flask(__name__, template_folder=template_root, static_folder=template_root, static_url_path='/static')
app.debug = debug()
# open_session reads this as the cookie's max_age during request-context push,
# before any before_request hook, so it has to be set at import.
app.permanent_session_lifetime = timedelta(days=365)
# app.url_map.strict_slashes = False
app.wsgi_app = ndb_wsgi_middleware(app.wsgi_app)
# Google Frontend terminates TLS, so without this every redirect Flask builds
# comes out http://. Must stay outermost. x_for off: nothing reads remote_addr.
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)


oidc = make_oidc(app)


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
    return make_resp(jsonstr if isinstance(jsonstr, str) else json.dumps(jsonstr, default=json_default), status, mimeType = "application/json")

def code_resp(code):
    return text_resp(str(code), code)

def text_download(text, filename, status=200):
    return make_response(text, status, {'Content-Type': 'application/x-gzip', 'Content-Disposition': 'attachment; filename=%s' % filename})

def zip_download(data, filename, status=200):
    return make_response(data, status, {'Content-Type': 'application/zip', 'Content-Disposition': 'attachment; filename=%s' % filename})

def ap_versions():
    """Versions the AP setup panel quotes, read from the packaged sources."""
    try:
        world_version = build_apworld.manifest().get("world_version", "")
    except (OSError, ValueError) as e:
        log.error("APWORLD manifest unreadable, version line will be blank: %s", e)
        world_version = ""
    return {'ap_world_version': world_version, 'ap_data_version': AP_DATA_VERSION}

if ARCHIPELAGO:
    # an image missing package files still boots and passes its health check,
    # so say so at startup rather than when a tester clicks Get apworld
    _apworld_problems = build_apworld.check(build_apworld.collect())
    if _apworld_problems:
        log.error("APWORLD package cannot be served: %s", "; ".join(_apworld_problems))

@app.errorhandler(500)
def server_error(err):
    return make_resp("""
    <html><title>Server Error</title>
    <body><h3>Backend Server Error</h3>
    <div>If this keeps happening, consider reaching out to Eiko in the <a target="_blank" href="/discord/dev">dev discord</a>.</div>
    <div style="padding-top: 2rem;">%s</div></body></html>""" % err, 500)

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


# update as we get more info lol
CLAIMED = {
    "UntestedBrokenPossibleAmazement": "Cereberon",
    "OriDetonatedNibel": "StorybookGumon",
    "OriTurnedIntoABomb": "StorybookGumon",
    "Pain": "StorybookGumon",
    "PowerSkillRush": "StorybookGumon",
}

#@app.route('/userGamesMigrate')

#rerwite every seed to the db one by one bc i hate my wallet (/want this to be done)
def moveSeeds():
    for seed in Seed.query():
        try:
            print(f"migrating seed: {seed.name}")
            seed.put()
        except Exception as e:
            print(f"failed to migrate {seed.name}: {e}")
    return text_resp("done")

# the below are migration functions that we hope to remove eventually but I'm keeping them around for now

def fix_game_associations():
    game_id_seen = set()
    for user in User.query():
        legacy_users = LegacyUser.query(LegacyUser.name == user.name).fetch()
        if not len(legacy_users):
            print(f"No legacy user for {user.name}???")
            continue
        legacy_user = legacy_users[0]
        # i = 0
        # for game in Game.query(Game.legacy_creator == legacy_user.key):
        #     if game.creator != user.key:
        #         if game.key in game_id_seen:
        #             print(f"Wuhoh: {game.key}")
        #         game_id_seen.add(game.key)
        #         game.creator = user.key
        #         game.put()
        #         i += 1
        #         print(f"game {game.key} given back to {user.name}")
        # print(f"gave {i} games back to {user.name}")
        for seed in Seed.query(Seed.legacy_author_key == legacy_user.key):
            if seed.author_key != user.key:
                new_seed = Seed(
                        id=f"{user.key.id()}:{seed.name}",
                        placements = seed.placements,
                        flags = seed.flags,
                        hidden = seed.hidden,
                        description = seed.description,
                        players = seed.players,
                        author_key = user.key,
                        legacy_author_key = legacy_user.key,
                        author = seed.author,
                        name = seed.name
                    )
                if new_seed.put():
                    seed.key.delete()
                    print(f"seed {seed.name} was reassigned to {user.name}'s new account")
                else:
                    print("error saving new seed")

    return text_resp("done")


# @app.route('/plandoMigrate')
def runplandomigration():
    reassign_plandos_to_legacy_users_by_name()
    return text_resp("Done")


def fix_plando_authorname_cases():
    uncased = {}
    for user in LegacyUser.query():
        uncased[user.name.lower()] = user
    for seed in Seed.query():
        if seed.author:
            if seed.author_key:
                user = seed.author_key.get()
                if user.name != seed.author:
                    print(f"{user.name} != {seed.author}, fixing")
                    seed.author = user.name
                    seed.put()
            elif seed.legacy_author_key:
                user = seed.legacy_author_key.get()
                if not user:
                    if seed.author in uncased:
                        print(f"{seed.author} != {uncased[seed.author].name}, fixing..")
                        seed.author = uncased[seed.author].name
                        seed.put()
                        continue
                    print(f"???? {seed.legacy_author_key}, {seed.name}, {seed.key}, {seed.author}")
                    continue
                if user.name != seed.author:
                    print(f"{user.name} != {seed.author}, maybe fix?")

def reassign_plandos_to_legacy_users_by_name():
    for seed in Seed.query():
        if seed.author and not seed.author_key:
            user = User.get_by_name(seed.author)
            legacy_user = LegacyUser.get_by_name(seed.author)
            if user:
                new_seed = Seed(
                        id=f"{user.key.id()}:{seed.name}",
                        placements = seed.placements,
                        flags = seed.flags,
                        hidden = seed.hidden,
                        description = seed.description,
                        players = seed.players,
                        author_key = user.key,
                        legacy_author_key = legacy_user.key if legacy_user else None,
                        author = seed.author,
                        name = seed.name
                    )
                if new_seed.put() and new_seed.key.id() != seed.key.id():
                    print(f"seed {seed.name} was reassigned to {user.name}'s new account")
                else:
                    print("error saving new seed")
            elif legacy_user:
                if seed.legacy_author_key != legacy_user.key:
                    new_seed = Seed(
                            id=f"{legacy_user.key.id()}:{seed.name}",
                            placements = seed.placements,
                            flags = seed.flags,
                            hidden = seed.hidden,
                            description = seed.description,
                            players = seed.players,
                            legacy_author_key = legacy_user.key,
                            author = seed.author,
                            name = seed.name
                        )
                    if new_seed.put():
                        seed.key.delete()
                        print(f"seed {new_seed.name} given to {seed.legacy_author_key} ({legacy_user.name}'s legacy account)")


@app.before_request
def canonical_host_redirect():
    # the orirando.com -> bf.orirando.com move (see util.CANONICAL_HOST).
    # Browsers only: never /netcode/* (the dll fleet treats redirects as
    # errors) and never non-GET (a stray API POST should fail loudly, not
    # vanish into a 301).
    if not CANONICAL_HOST or request.host not in REDIRECT_HOSTS:
        return
    if request.method not in ("GET", "HEAD") or request.path.startswith("/netcode/"):
        return
    target = request.full_path if request.query_string else request.path
    return redirect("https://%s%s" % (CANONICAL_HOST, target), 301)


@app.after_request
def fix_logout_redirect(response: Response):
    if response.location == '/logout?reason=expired':
        response.location += '&next=' + quote_plus(request.full_path)

    return response


@app.after_request
def hsts_header(response):
    # never add includeSubDomains: bfnc.orirando.com serves the dll over plain
    # http and the dll has no TLS support
    if request.is_secure:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
    return response


@app.after_request
def delete_flashes(response):
    """Flask-OIDC `flash()`es some messages, but we never read them.
    Delete them here, so they don't accumulate in the session cookie.
    """
    get_flashed_messages()
    return response


@app.before_request
def make_session_permanent():
    """Rolling year-long login cookie, refreshed on every response.

    Only for sessions that hold a token: setting `permanent` writes a key, and a
    non-empty session means a signed cookie on every anonymous hit and every
    /netcode/ poll too.
    """
    if session.get("oidc_auth_token"):
        session.permanent = True


@after_logout.connect
def clear_session_on_logout(sender, **kwargs):
    # logout_view only pops its own keys. Anything left keeps the session
    # truthy, and Flask sends the delete-cookie only for an empty one.
    session.clear()


GAME_LIST_LIMIT = 50


@app.route('/activeGames/')
@app.route('/activeGames/<hours>/')
def active_games(hours=12):
    hours = int(hours)
    title = "Games active in the last %s hours" % hours
    # bounded, and the "did anyone play" test is a field on the game now: it
    # used to be a history walk (an ancestor query plus a get per player) per
    # game, behind an unlimited query with an even less limited fallback.
    # Games written before has_history existed read None -- unknown, so shown.
    # Widen the window with /activeGames/<hours>/ rather than fetching all.
    # order explicitly: an inequality query defaults to ASCENDING on that
    # property, so a bare fetch(limit) would return the OLDEST games in the
    # window. Same property, so no composite index needed. Over-fetch and
    # slice AFTER filtering, or a run of generated-but-unplayed games fills
    # the budget and reports "no active games" while real ones sit below it.
    games = Game.query(Game.last_update > datetime.now() - timedelta(hours=hours)
                       ).order(-Game.last_update).fetch(GAME_LIST_LIMIT * 4)
    games = [game for game in games if game.has_history is not False][:GAME_LIST_LIMIT]
    if not len(games):
        title = "No active games found!"
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
    template_values = template_vals("MainPage", "Ori DE Randomizer %s" % VERSION, User.get())
    # not the displayed version: this moves on a site-only release, so the link goes unread
    template_values['notes_anchor'] = latest_note_version()
    if ARCHIPELAGO:
        template_values.update(ap_versions())
    # _, error = CustomLogic.read()
    # template_values.update({"error_msg": error})
    return render_template(path, **template_values)


@app.route('/myGames')
@oidc.require_login
def my_games():
    user = User.get()
    keys = user.games if param_flag("all") else user.games[-10:]
    title = "Games played by %s" % user.name if param_flag("all") else "Last 10 games played by %s" % user.name
    # even ?all is bounded: a long-time player's list is thousands of games,
    # and one batched get beats a fan-out of per-key futures
    if len(keys) > GAME_LIST_LIMIT * 4:
        keys = keys[-GAME_LIST_LIMIT * 4:]
        title = "Most recent games played by %s" % user.name
    body = game_list_html(ndb.get_multi(keys))
    if body:
        out = "<h4>%s:</h4><ul>%s</ul></body</html>" % (title, body)
    else:
        out = "<h4>%s</h4></body></html>" % title
    return make_resp(out)


# Client-netcode routes are thin HTTP adapters over the transport-neutral
# session layer in netcode.py: parse transport params, delegate, wrap
# (status, body) â€” nothing else. New netcode behavior belongs in netcode.py.
@app.route('/netcode/game/<int:game_id>/player/<int:player_id>/found/<coords>/<kind>/<path:id>/')
@app.route('/netcode/game/<int:game_id>/player/<int:player_id>/found/<coords>/<kind>/<path:id>')
def netcode_found_pickup(game_id, player_id, coords, kind, id):
    status, body = netcode.found_pickup(game_id, player_id, coords, kind, id, request.args)
    return text_resp(body, status)

# do we even use this anymore? i think only for testing.........
@app.route('/netcode/game/<int:game_id>/player/<int:player_id>/tick/<xycoords>', methods=['GET'])
def netcode_tick_get(game_id, player_id, xycoords):
    status, body = netcode.tick_debug(game_id, player_id, xycoords, request.args)
    return text_resp(body, status)

@app.route('/netcode/game/<int:game_id>/player/<int:player_id>/tick/', methods = ['POST'])
@app.route('/netcode/game/<int:game_id>/player/<int:player_id>/tick', methods = ['POST'])
def netcode_tick_post(game_id, player_id):
    status, body = netcode.tick(game_id, player_id, request.form)
    return text_resp(body, status)

@app.route('/netcode/game/<int:game_id>/player/<int:player_id>/complete')
def netcode_game_complete(game_id, player_id):
    status, body = netcode.game_complete(game_id, player_id)
    return text_resp(body, status)

@app.route('/netcode/game/<int:game_id>/player/<int:player_id>/callback/<path:signal>')
def netcode_signal_callback(game_id, player_id, signal):
    status, body = netcode.signal_callback(game_id, player_id, signal)
    return text_resp(body, status)

@app.route('/netcode/game/<int:game_id>/player/<int:player_id>/setSeed', methods=['POST'])
@app.route('/netcode/game/<int:game_id>/player/<int:player_id>/connect', methods=['POST'])
def netcode_connect(game_id, player_id):
    status, body = netcode.connect(game_id, player_id, request.form)
    return text_resp(body, status)

@app.route('/netcode/areas')
def netcode_get_areas_dot_ori():
    return text_resp(Cache.get_areas())

# Archipelago link management (flag-gated in the session layer: with
# ARCHIPELAGO unset every route 404s). Deliberately NOT behind the ap_test
# alpha opt-in: that gate is on seed creation, and everyone already holding a
# seed from an AP game -- testers' friends included -- needs the bridge.
@app.route('/netcode/game/<int:game_id>/ap/connect', methods=['POST'])
def netcode_ap_connect(game_id):
    status, body = netcode.ap_connect(game_id, request.form)
    return text_resp(body, status)

@app.route('/netcode/game/<int:game_id>/ap/status')
def netcode_ap_status(game_id):
    status, body = netcode.ap_status(game_id)
    return json_resp(body, status) if status == 200 else text_resp(body, status)

@app.route('/netcode/game/<int:game_id>/ap/disconnect', methods=['POST'])
def netcode_ap_disconnect(game_id):
    status, body = netcode.ap_disconnect(game_id)
    return text_resp(body, status)

# websocket transport. The route body lives in ws.py; each connection pins a
# gunicorn thread until it closes, capped by util.WS_CONN_LIMIT.
import ws
from flask_sock import Sock
# client frames are tiny (found/bingo/conf); without a cap an incoming
# fragmented message can grow unbounded in memory
app.config['SOCK_SERVER_OPTIONS'] = {'max_message_size': 1 << 20}
sock = Sock(app)

@sock.route('/netcode/game/<int:game_id>/player/<int:player_id>/ws')
def netcode_ws(conn, game_id, player_id):
    ws.run_connection(conn, game_id, player_id)

ws.enable_push()

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
        if (game.params and Variation.RACE in game.fetch_params().variations) and not template_values["race_wl"]:
            return text_code("Access forbidden", 401)
        output = game.summary(int(param_val("p") or 0))
        output += "\nHistory:"
        hls = []
        pids = [int(pid) for pid in param_val("pids").split("|")] if param_val("pids") else []
        hls = game.history(pids) if param_flag("verbose") else [h for h in game.history(pids) if h.pickup().is_shared(share_types)]
        mw_names = game.mw_names()
        for hl in sorted(hls, key=lambda x: x.timestamp, reverse=True):
            output += "\n\t\t%s Player %s %s" % ((hl.player-1)*"\t\t\t\t", hl.player, hl.print_line(game.start_time, mw_names))
        return text_resp(output)
    else:
        return text_resp("Game %s not found!" % game_id, 404)

@app.route('/game/<int:game_id>/players/')
def game_list_players(game_id):
        game = Game.with_id(game_id)
        if not game:
            return text_resp("Game %s not found!" % game_id, 404)
        out_lines = []
        mw_names = game.mw_names()
        for p in game.visible_players():
            out_lines.append("Player %s: %s" % (p.pid(), p.output()))
            out_lines.append("\t\t" + "\n\t\t".join([hl.print_line(game.start_time, mw_names) for hl in game.history([p.pid()]) if hl.pickup().is_shared(share_types)]))
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
    # ap_test=1: the alpha opt-in, sent by the generator page when the visitor
    # opted in. Gates creation only; existing AP games keep their bridge.
    problem = seed_mode_problem(params, ap_override=param_true("ap_test"))
    if problem:
        return text_resp(problem, 409)
    if not params.generate():
        return text_resp("Failed to generate seed!", 500)
    resp = {"paramId": param_key.id(), "playerCount": params.players, "flagLine": params.flag_line(), 'seed': params.seed, "spoilers": True}
    lines = world_flag_lines(params)
    if lines:
        resp["flagLines"] = lines
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
        problem = seed_mode_problem(params, ap_override=param_true("ap_test"))
        if problem:
            return json_resp({"error": problem}, 409)
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

def ap_seed_not_ready(params, game_id):
    """Why an AP seed download would come out unannotated, or None when it
    wouldn't. A seed file is a snapshot: downloaded before every world's
    scouts persisted, it keeps "AP Item #n" and the rolled zones forever,
    and nothing detects it. Gates on the persisted scout rows, not the live
    socket -- a room that died after scouting still annotates fully."""
    if not getattr(params, "ap_mode", False):
        return None
    if not game_id:
        return "This Archipelago seed has no game attached; download it from its seed page"
    from ap_models import APLink
    link = APLink.with_id(game_id)
    if not link:
        return "Connect the Archipelago room first, then download (item names bake in at download time)"
    worlds = int(params.players)
    totals = list(link.name_totals) + [-1] * (worlds - len(link.name_totals))
    counts = list(link.name_counts) + [0] * (worlds - len(link.name_counts))
    if any(t < 0 for t in totals[:worlds]) or any(c < t for c, t in zip(counts[:worlds], totals[:worlds])):
        done = sum(max(c, 0) for c in counts[:worlds])
        total = sum(t for t in totals[:worlds] if t > 0)
        return "Waiting for the room's location scouts (%s/%s item names resolved)" % (done, total or "?")
    return None


@app.route('/generator/seed/<params_id>')
def load_seed_from_params(params_id):
    verbose_paths = param_flag("verbose_paths")
    params = SeedGenParams.with_id(params_id)
    if params:
        pid = int(param_val("player_id") or 1)
        game_id = param_val("game_id")
        if not param_flag("force"):
            not_ready = ap_seed_not_ready(params, game_id)
            if not_ready:
                return json_resp({"error": not_ready, "retryable": True}, 409)
        if params.tracking and game_id:
            seed = params.get_seed(pid, game_id, verbose_paths)
            game = Game.with_id(game_id)
            user = User.get()
            if game and user:
                Player.claim_user_txn(game.player(pid).key, user.key)
                if game.mode == MultiplayerGameType.MULTIWORLD:
                    # names ride the tick output: rebuild it for everyone
                    Cache.clear_names(int(game_id))
                    for p in game.player_nums():
                        Cache.clear_seen_checksum((int(game_id), p))
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
        spoiler = params.get_spoiler(player, game_id=param_val("game_id"))
        if param_flag("download"):
            spoiler = spoiler.replace("\n", "\r\n")
            return text_download(spoiler, 'spoiler.txt')
        return text_resp(spoiler)
    else:
        return text_resp("Param %s not found" % params_id, 404)

@app.route('/generator/apyaml/<params_id>/<int:world_id>')
def get_apyaml_from_params(params_id, world_id):
    # ARCHIPELAGO only, no ap_test: the params already exist, and the yamls are
    # what makes them playable (see the ap routes above)
    if not ARCHIPELAGO:
        return text_resp("Archipelago support is not enabled", 404)
    params = SeedGenParams.with_id(params_id)
    if not params or not params.ap_mode:
        return text_resp("No Archipelago params %s found" % params_id, 404)
    if world_id < 1 or world_id > params.players:
        return text_resp("Param %s has no world %s" % (params_id, world_id), 404)
    return text_download(params.to_ap_yaml(world_id), 'ap_world_%s.yaml' % world_id)

@app.route('/generator/apyamls/<params_id>')
def get_apyamls_from_params(params_id):
    # every world in one multi-document yaml
    if not ARCHIPELAGO:
        return text_resp("Archipelago support is not enabled", 404)
    params = SeedGenParams.with_id(params_id)
    if not params or not params.ap_mode:
        return text_resp("No Archipelago params %s found" % params_id, 404)
    worlds = [params.to_ap_yaml(w) for w in range(1, params.players + 1)]
    return text_download("---\n".join(worlds), 'ap_worlds_%s.yaml' % params_id)

apworld_zip = None

@app.route('/generator/apworld')
def get_apworld():
    # ARCHIPELAGO only, no ap_test: a tester's session host needs the world
    # even though they never touch the seed page (see the ap routes above)
    if not ARCHIPELAGO:
        return text_resp("Archipelago support is not enabled", 404)
    global apworld_zip
    if apworld_zip is None:
        # raises on a package that fails its own checks: 500 beats a dud
        apworld_zip = build_apworld.zip_bytes()
    # the filename IS the module name Archipelago imports (worlds/__init__.py
    # takes Path(path).stem), so anything but oride.apworld fails to load
    return zip_download(apworld_zip, 'oride.apworld')

@app.route('/generator/aux_spoiler/<params_id>')
def get_aux_spoiler_from_params(params_id):
    params = SeedGenParams.with_id(params_id)
    if params:
        player = int(param_val("player_id") or 1)
        exclude = (param_val("exclude") or "EX KS AC EC HC MS").split(" ") if param_val("exclude") != "" else []
        by_zone = param_flag("by_zone")
        # optional game_id: AP seeds' reserved lines get their scouted item
        # names, same as the seed file (no game, no names -- never an error)
        spoiler = params.get_aux_spoiler(exclude, by_zone, player,
                                         game_id=param_val("game_id"))
        if param_flag("download"):
            return text_download(spoiler.replace("\n", "\r\n"), 'spoiler.txt')
        return text_resp(spoiler)
    else:
        return text_resp("Param %s not found" % params_id, 404)

def world_flag_lines(params):
    """One flag line per world, or None when a single line says it all."""
    if not getattr(params, "world_settings", None):
        return None
    return [params.world_params(p).flag_line() for p in range(1, (params.players or 1) + 1)]


@app.route('/generator/metadata/<param_id>')
def get_metadata_no_gid(param_id):
    return get_param_metadata(param_id, None)

@app.route('/generator/metadata/<param_id>/<int:game_id>')
def get_param_metadata(param_id, game_id):
    params = SeedGenParams.with_id(param_id)
    if not params:
        return json_resp({"error": "No params found"}, 404)
    res = params.to_json()
    lines = world_flag_lines(params)
    if lines:
        res["flagLines"] = lines
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
    if game and (Variation.RACE in game.fetch_params().variations) and not template_values["race_wl"]:
        return text_resp("Access forbidden", 401)
    return render_template(path, **template_values)

@app.route('/tracker/game/<int:game_id>/fetch/gamedata')
def tracker_fetch_gamedata(game_id):
    gamedata = {}
    game = Game.with_id(game_id)
    if not game or not game.params:
        return json_resp({"error": "Game %s not found!" % game_id}, 404)
    params = game.fetch_params()
    gamedata["paths"] = params.logic_paths
    gamedata["players"] = [p.userdata() for p in game.visible_players()]
    gamedata["closed_dungeons"] = Variation.CLOSED_DUNGEONS in params.variations
    gamedata["open_world"] = Variation.OPEN_WORLD in params.variations
    return json_resp(gamedata)

@app.route('/tracker/game/<int:game_id>/fetch/update')
def tracker_update_map(game_id):
    players = {}
    username = param_val("usermap")
    gid_changed = False
    if username:
        # once, not twice: this is the 1Hz route, and a falsy answer (unknown
        # user, or a user with no games) must not become the game id
        latest = User.latest_game(username)
        if latest and latest != int(game_id):
            game_id = latest
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
        coords = { p.pid(): p.have_coords() for p in game.visible_players() }
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
            inventories = game.get_inventories(game.visible_players(), True, True)
        spawn = game.fetch_params().spawn or "Glades"
        for p in need_reach_updates:
            inventory = [(pcode, pid, count, False) for ((pcode, pid), count) in inventories["unshared"][p].items()]
            inventory  += [(pcode, pid, count, False) for group, inv in inventories.items()  if group != "unshared" and p in group for ((pcode, pid), count) in inv.items()]
            state = PlayerState(inventory)
            if state.has["KS"] > 8 and "standard-core" in modes:
                state.has["KS"] += 2 * (state.has["KS"] - 8)
            if p not in reach:
                reach[p] = {}
            reach[p][modes] = Map.get_reachable_areas(state, modes, spawn, False)
        # merge semantics: write back only the recomputed players, so this slow
        # compute can't clobber other players' entries written meanwhile
        Cache.set_reachable(game_id, {p: reach[p] for p in need_reach_updates})
    # iterate the rendered players, not the cache: the merge-semantics writeback
    # above never removes entries, so reach can carry pids (or mode sets) that
    # players/need_reach_updates knows nothing about
    for p in players:
        if modes in reach.get(p, {}):
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
        coords = { p.pid(): p.have_coords() for p in game.visible_players() }
        Cache.set_have(game_id, coords)
    return json_resp(coords)


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
    spawn = game.fetch_params().spawn or "Glades"
    shared_hist = []
    shared_coords = set()
    try:
        if game and game.mode == MultiplayerGameType.SHARED:
            shared_hist = [hl for hls in hist.values() for hl in hls if hl.pickup().is_shared(game.shared)]
            shared_coords = set([hl.coords for hl in shared_hist])
        visible = set(p.pid() for p in game.visible_players()) if game else None
        for player, personal_hist in hist.items():
            # a shadow's pid can already be in the cache map: Player creation
            # seeds an empty hist key, and that predates any rebuild
            if visible is not None and player not in visible:
                continue
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
            coords = { p.pid(): p.have_coords() for p in game.visible_players() }
            Cache.set_have(game_id, coords)
        items, _ = _get_item_tracker_items(coords.get(player_id, []), game, player_id)
    return json_resp(items)

# why is it like this??
def _get_item_tracker_items(coords, game, player=1):
    relics = game.relics_for(player)
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
    inventories = game.get_inventories(game.visible_players(), True, True)

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
    if not player or player.is_ap_shadow():
        return json_resp({"error": "game %s does not contain player %s!" % (game_id, player_id)}, 404)
    res = {"seed": {}, 'name': player.name()}
    params = game.fetch_params()
    if Variation.BINGO in params.variations:
        bingo = BingoGameData.with_id(game_id)
        if not bingo:
            return json_resp({"error": "no bingo data found for game %s" % game_id}, 404)
        team = bingo.team(player_id, cap_only=False)
        if not team:
            return json_resp({"error": "No team found for player %s!" % player_id}, 404)
        team = team.pids()
        player_id = team.index(player_id) + 1
    seed_lines = params.get_seed_data(player_id)
    shadow = None
    if getattr(params, "ap_mode", False):
        # scouted labels for the reserved AP lines; without them the
        # tooltips say "AP Item #n" forever
        seed_lines = params.ap_named(seed_lines, player_id, game_id)
        shadow = str(int(params.players) + int(player_id))
    names = {}
    if any(l[1] == "MW" for l in seed_lines):
        for part in (player.mw_names_field() or "").split(";"):
            pid_s, dot, nm = part.partition(".")
            if dot and pid_s.isdigit():
                names[int(pid_s)] = nm

    def owned(owner, item):
        # in-game shape: bare for your own, "<name>'s" for anyone else's
        if owner == player_id:
            return item
        return "%s's %s" % (names.get(owner, "Player %s" % owner), item)

    for line in seed_lines:
        coords, code, id = line[0], line[1], line[2]
        if is_mw_manifest_loc(coords):
            continue  # multiworld slot manifests aren't map locations
        if code == "MW":
            parts = id.split(",", 5)
            if shadow is not None and len(parts) == 6 and parts[0] == shadow:
                to, icode, iid = parts[2], parts[4], parts[5]
                item = iid if icode == "AP" else Pickup.name(icode, iid)
                if to.startswith("P") and to[1:].isdigit():
                    res["seed"][coords] = owned(int(to[1:]), item)
                elif to:
                    res["seed"][coords] = "%s's %s" % (to, item)
                else:
                    res["seed"][coords] = item  # nobody has scouted it yet
                continue
            parts = id.split(",", 3)
            if len(parts) == 4 and parts[0].isdigit():
                res["seed"][coords] = owned(int(parts[0]), Pickup.name(parts[2], parts[3]))
                continue
        res["seed"][coords] = Pickup.name(code, id)
    return json_resp(res)

@app.route('/tracker/game/<int:game_id>/items')
@app.route('/tracker/game/<int:game_id>/<int:player_id>/items')
def tracker_item_tracker(game_id, player_id=1):
    game = Game.with_id(game_id)
    template_values = template_vals("ItemTracker", "Game %s" % game_id, User.get())
    if game and Variation.RACE in game.fetch_params().variations and not template_values["race_wl"]:
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
            return text_resp("Preferred player number for %s set to %s" % (user.name, new_num))
        else:
            return text_resp("Preferred player number must be >0", 400)
    else:
        return text_resp("You are not logged in!", 401)

@app.route('/user/settings/theme/<new_theme>')
def user_set_theme(new_theme):
    user = User.get()
    if user:
        user.theme = new_theme
        user.put()
        return text_resp("theme for %s set to %s" % (user.name, new_theme))
    else:
        return text_resp("You are not logged in!", 401)

@app.route('/theme/toggle')
def user_toggle_darkmode():
    target_url = unquote(param_val("redir")) or "/"
    user = User.get()
    if user:
        # the page sends the state it's switching to: with nothing stored it
        # may be showing the browser's preference, which we can't see
        user.dark_theme = param_true("dark") if param_val("dark") is not None else not user.dark_theme
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
        return text_resp("You are not logged in!", 401)

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
    old_params = old_game.fetch_params().to_json()
    old_params['seed'] = str(random.randint(0, 1000000000))
    new_params = SeedGenParams.from_json(old_params).get()
    # the overrides pass modes this user already has a game of; combinations
    # that can't work at all still refuse
    problem = seed_mode_problem(new_params, mw_override=True, ap_override=True)
    if problem:
        return text_resp(problem, 409)
    if not new_params.generate():
        return text_resp( "Failed to generate seed!", 500)
    game = Game.from_params(new_params)
    if Variation.BINGO in new_params.variations:
        url = "/bingo/board?game_id=%s&fromGen=1&seed=%s&bingoLines=%s" % (game.key.id(), new_params.seed, new_params.bingo_lines)
        b = old_game.bingo_data.get() if old_game.bingo_data else None
        if b and b.discovery and b.discovery > 0:
            url += "&disc=%s" % b.discovery
        return redirect(url)
    return redirect("%s?param_id=%s&game_id=%s" % (url_for('main_page'), new_params.key.id(), game.key.id()))

# --- presets (SSPs in code) --------------------------------------------------
# A preset is the seedgen form minus the multiplayer tab and the seed, so the
# same one rolls solo, in co-op, or as one world of a multiworld.

def _ssp_or_404(owner_name, name):
    ssp = SavedSeedParams.get(owner_name, name)
    if not ssp:
        return None, text_resp("no preset named %s by %s" % (name, owner_name), 404)
    if ssp.hidden and not ssp.owned_by(User.get()):
        return None, text_resp("no preset named %s by %s" % (name, owner_name), 404)
    return ssp, None


@app.route('/preset/save', methods=['POST'])
def ssp_save():
    user = User.get()
    if not user:
        return text_resp("log in to save presets", 401)
    body = json.loads(request.form.get("preset") or "{}")
    name = (body.get("name") or "").strip()
    problem = SavedSeedParams.name_problem(name) or SavedSeedParams.desc_problem(body.get("desc"))
    if problem:
        return text_resp(problem, 422)
    ssp = user.saved_params(name) or SavedSeedParams(id="%s:%s" % (user.key.id(), name))
    ssp.populate(
        name=name,
        owner_key=user.key,
        # absent means leave it: an options-only save must not blank the description
        description=((body.get("desc") or "").strip() or None) if "desc" in body else ssp.description,
        settings=SavedSeedParams.settings_from(body.get("params") or {}, body.get("world") or 1),
        hidden=bool(body.get("hidden", ssp.hidden)),
    )
    ssp.put()
    return json_resp({"name": ssp.name, "owner": user.name})


@app.route('/preset/list')
def ssp_list():
    """Presets for the seedgen page's dropdown. Anonymous users get an empty list
    rather than a 401: the page greys the controls out instead of erroring."""
    user = User.get()
    if not user:
        return json_resp({"owner": None, "hasLatest": False, "settings": []})
    rows = sorted(SavedSeedParams.query(SavedSeedParams.owner_key == user.key),
                  key=lambda s: (s.name or "").lower())
    # what /preset/latest and /reroll both need, so a lit button is one that works
    last = user.games[-1].get() if user.games else None
    # the blob rides along so the page can match a loaded form against a preset
    return json_resp({"owner": user.name,
                      "hasLatest": bool(last and last.params),
                      "settings": [{"name": s.name, "desc": s.description,
                                    "hidden": s.hidden, "blob": s.settings} for s in rows]})


@app.route('/preset/latest')
def ssp_latest():
    """The user's last game's options, lobby included.

    Alone among the loads this keeps players/coop/AP: it is never assigned to someone else's world."""
    user = User.get()
    if not user:
        return text_resp("log in to load your last seed's options", 401)
    if not user.games:
        return text_resp("you have no games to take options from", 404)
    game = user.games[-1].get()
    if not game or not game.params:
        return text_resp("your last game has no options to load", 404)
    settings = game.fetch_params().to_json()
    # the page drops these too; a preset never carries a seed or a finished seed's output
    for output_only in ("seed", "flagLine", "isPlando", "spoilers", "teamStr"):
        settings.pop(output_only, None)
    return json_resp({"name": "Last Seed", "owner": None, "withLobby": True,
                      "settings": settings})


@app.route('/preset/<owner_name>/<name>')
def ssp_get(owner_name, name):
    """The preset itself. A share link COPIES it into the opener's form; it does
    not stay bound to this entity, so editing yours never changes what someone
    else's link rolls."""
    ssp, err = _ssp_or_404(owner_name, name)
    return err or json_resp({"name": ssp.name, "owner": owner_name,
                             "desc": ssp.description, "settings": ssp.settings})


@app.route('/preset/<owner_name>/<name>/roll')
def ssp_roll(owner_name, name):
    ssp, err = _ssp_or_404(owner_name, name)
    if err:
        return err
    settings = dict(ssp.settings or {})
    settings["seed"] = str(random.randint(0, 1000000000))
    settings["players"] = 1      # a setting says nothing about a lobby
    param_key = SeedGenParams.from_json(settings)
    if not param_key:
        return text_resp("this preset can no longer be built", 422)
    params = param_key.get()
    problem = seed_mode_problem(params)
    if problem:
        return text_resp(problem, 409)
    if not params.generate():
        return text_resp("this preset can no longer be rolled: no completable seed "
                         "could be built from it", 422)
    if not params.tracking:
        return redirect("%s?param_id=%s" % (url_for('main_page'), param_key.id()))
    game = Game.from_params(params)
    if Variation.BINGO in params.variations:
        return redirect("/bingo/board?game_id=%s&fromGen=1&seed=%s&bingoLines=%s"
                        % (game.key.id(), params.seed, params.bingo_lines))
    return redirect("%s?param_id=%s&game_id=%s"
                    % (url_for('main_page'), param_key.id(), game.key.id()))


def _preset_body():
    """The posted json as a dict, or (None, response). Parses behind the login
    check and tolerates any shape, so a bad body is a 400 rather than a 500."""
    if not User.get():
        return None, text_resp("log in to manage your presets", 401)
    try:
        body = json.loads(request.form.get("preset") or "{}")
    except ValueError:
        return None, text_resp("could not read that request", 400)
    if not isinstance(body, dict):
        return None, text_resp("could not read that request", 400)
    return body, None


def _str_field(body, key, default=""):
    value = body.get(key)
    return (value if isinstance(value, str) else default).strip()


def _rename_preset_body(user, old_name, new_name, desc, hidden):
    """Move a preset to a new name, returning a problem string or None.

    The id carries the name, so this is a create plus a delete across two keys,
    and the "is the target free?" read has to sit in the same transaction."""
    ssp = user.saved_params(old_name)
    if not ssp:
        return "no preset named %s" % old_name
    if user.saved_params(new_name):
        return "you already have a preset named %s" % new_name
    SavedSeedParams(id="%s:%s" % (user.key.id(), new_name), name=new_name,
                    owner_key=user.key, description=desc,
                    settings=ssp.settings, hidden=hidden).put()
    ssp.key.delete()
    return None


_rename_preset = ndb.transactional(retries=5)(_rename_preset_body)


def _my_preset(name):
    """The caller's own preset by name, or (None, None, response). Ownership is
    the lookup: saved_params only returns presets keyed to this user."""
    user = User.get()
    if not user:
        return None, None, text_resp("log in to manage your presets", 401)
    ssp = user.saved_params(name)
    if not ssp:
        return None, None, text_resp("no preset named %s" % name, 404)
    return user, ssp, None


@app.route('/preset/edit', methods=['POST'])
def preset_edit():
    """Rename / describe / hide, without touching the saved options."""
    body, err = _preset_body()
    if err:
        return err
    user, ssp, err = _my_preset(_str_field(body, "name"))
    if err:
        return err
    new_name = _str_field(body, "newName") or ssp.name
    problem = SavedSeedParams.name_problem(new_name) or SavedSeedParams.desc_problem(_str_field(body, "desc"))
    if problem:
        return text_resp(problem, 422)
    desc = _str_field(body, "desc") or None
    hidden = bool(body.get("hidden", ssp.hidden))
    if new_name == ssp.name:
        ssp.description, ssp.hidden = desc, hidden
        ssp.put()
        return json_resp({"name": ssp.name})
    problem = _rename_preset(user, ssp.name, new_name, desc, hidden)
    if problem:
        return text_resp(problem, 409)
    return json_resp({"name": new_name})


@app.route('/preset/delete', methods=['POST'])
def preset_delete():
    body, err = _preset_body()
    if err:
        return err
    _, ssp, err = _my_preset(_str_field(body, "name"))
    if err:
        return err
    ssp.key.delete()
    return json_resp({"deleted": ssp.name})


@app.route('/preset/mine/<name>/delete')
@oidc.require_login
def ssp_delete(name):
    _, ssp, err = _my_preset(name)
    if err:
        return err
    ssp.key.delete()
    return redirect(url_for('my_settings'))


@app.route('/preset/mine/<name>/rename/<new_name>')
@oidc.require_login
def ssp_rename(name, new_name):
    user, ssp, err = _my_preset(name)
    if err:
        return err
    problem = SavedSeedParams.name_problem(new_name)
    if problem:
        return text_resp(problem, 422)
    problem = _rename_preset(user, ssp.name, new_name, ssp.description, ssp.hidden)
    if problem:
        return text_resp(problem, 409)
    return redirect(url_for('my_settings'))


@app.route('/preset/mine/<name>/hideToggle')
@oidc.require_login
def ssp_hide_toggle(name):
    _, ssp, err = _my_preset(name)
    if err:
        return err
    ssp.hidden = not ssp.hidden
    ssp.put()
    return redirect(url_for('my_settings'))


@app.route('/myPresets')
@oidc.require_login
def my_settings():
    user = User.get()
    rows = sorted(SavedSeedParams.query(SavedSeedParams.owner_key == user.key),
                  key=lambda s: (s.name or "").lower())
    out = ['<html><head><title>My Presets</title></head><body>'
           '<h5>My Presets</h5>']
    if not rows:
        out.append("<p>You haven't saved any presets yet. "
                   "Save one from the <a href='/'>seed generator</a>.</p>")
    out.append('<ul style="list-style-type:none;padding:5px">')
    for ssp in rows:
        share = "%spreset/%s/%s" % (request.host_url, user.name, ssp.name)
        out.append(
            '<li style="padding:4px">'
            '<b>%s</b>%s%s<br>'
            '<a href="/preset/%s/%s/roll">roll seed</a> &middot; '
            '<a href="/?preset=%s:%s">load into the form</a> &middot; '
            '<a href="%s">share link</a> &middot; '
            '<a href="/preset/mine/%s/hideToggle">%s</a> &middot; '
            '<a href="/preset/mine/%s/delete">delete</a>'
            '</li>' % (
                ssp.name,
                " (hidden)" if ssp.hidden else "",
                (" &mdash; %s" % ssp.description) if ssp.description else "",
                user.name, ssp.name,
                user.name, ssp.name,
                share,
                ssp.name, "unhide" if ssp.hidden else "hide",
                ssp.name))
    out.append('</ul></body></html>')
    return make_resp("".join(out))


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
    # Was dead code (mis-indented under the not-found return, with new_owner undefined);
    # rebuilt 2026-07-19: transfers ownership to the user attached to player <player_id>.
    game = Game.with_id(game_id)
    if not game:
        return text_resp("Game %s not found!" % game_id, 404)
    user = User.get()
    if not (User.is_admin() or (user and user.key == game.creator)):
        return text_resp("Can't restart a game you didn't create...", 401)
    p = game.player(player_id)
    new_user = p.user.get() if p and p.user else None
    if not new_user:
        return text_resp("Couldn't find a user attached to player %s" % player_id, 404)
    game.creator = new_user.key
    game.put()
    game.reset()
    return text_resp("Game reset; ownership transferred from %s to %s" % (user.name if user else "admin", new_user.name))

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


@app.route('/plando/<author_name>/<seed_name>/spoiler') # PlandoSpoiler
def plando_spoiler(author_name, seed_name):
    seed = Seed.get(author_name, seed_name)
    if seed and seed.hidden:
        user = User.get()
        if not user or user.key != seed.author_key:
            seed = None
    if not seed or not seed.spoiler:
        return text_resp("no spoiler for seed %s (by user %s)" % (seed_name, author_name), 404)
    if param_flag("download"):
        return text_download(seed.spoiler.replace("\n", "\r\n"), "%s_spoiler.txt" % seed_name)
    return text_resp(seed.spoiler)


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
            'seed_desc': seed.description, 'game_id': Game.get_open_gid(),
            # the body is for the author's editor only; everyone else just gets the link
            'seed_has_spoiler': bool(seed.spoiler),
            'seed_spoiler': (seed.spoiler or "") if authed else ""})
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
    """Fill a plando's empty locations. Answers {player: seed text}: one world
    for everyone when the fill is cloned, one per player in multiworld."""
    qparams = request.args
    try:
        preplaced = parse_fass(qparams.get('fass'))
    except ValueError:
        return text_resp("a forced assignment named a location that isn't a number", 422)
    param_key = SeedGenParams.from_url(qparams)
    params = param_key.get()
    if not params.generate(preplaced=preplaced):
        return code_resp(422)
    worlds = range(1, params.players + 1) if params.sync.mode == MultiplayerGameType.MULTIWORLD else [1]
    return json_resp({str(p): params.get_seed(p) for p in worlds})

def count_plandos(seed):
    if seed.author_key:
        return seed.author_key
    if seed.legacy_author_key:
        return seed.legacy_author_key
    return seed.author

PLANDO_DISCLAIMER = """<div><i>
(If one or more of your plandos are missing, please reach out to @Eiko or @Skyedelaciel in the <a target="_blank" href="/discord">Ori Discord</a> - we have the data, we just don't know whose seeds are whose for a small number of users)
</i></div>"""
@app.route('/plandos')      #AllAuthors
def plando_index():
    out = '<html><head><title>All Plando Authors</title></head><body><h5>All Seeds</h5><ul style="list-style-type:none;padding:5px">'
    authors = Counter(count_plandos(seed) for seed in Seed.query(Seed.hidden != True, projection=[Seed.author, Seed.author_key, Seed.legacy_author_key]))
    for author, cnt in authors.most_common():
        if cnt > 0:
            if not isinstance(author, str):
                if author.get():
                    author = author.get().name
                else:
                    author = str(author.id() if author.id() else author)
            url = "/plando/%s" % author
            out += '<li style="padding:2px"><a href="%s">%s</a> (%s plandos)</li>' % (url, author, cnt)
    out += f"</ul>{PLANDO_DISCLAIMER}</body></html>"
    return make_resp(out)

@app.route('/plando/<author_name>')
def plando_author_index(author_name):
    start_at = int(param_val("offset") or 0)
    owner = False
    user = User.get()
    author = User.get_by_name(author_name)
    proj = [Seed.name, Seed.description, Seed.players, Seed.flagline]
    if author:
        author_name = author.name
        owner = user and user.key.id() == author.key.id()
        if owner:
            query = Seed.query(Seed.author_key == author.key, projection=[Seed.hidden, *proj])
        else:
            query = Seed.query(Seed.author_key == author.key, Seed.hidden != True, projection=proj)
    else:
        legacy_author = LegacyUser.get_by_name(author_name)
        if legacy_author:
            query = Seed.query(Seed.legacy_author_key == legacy_author.key, Seed.hidden != True, projection=proj)
        else: 
            query = Seed.query(Seed.author == author_name, Seed.hidden != True, projection=proj)
    seeds = query.fetch(limit=int(param_val("limit") or 1), offset=start_at) if start_at else query.fetch()
    if len(seeds):
        out = '<html><head><title>Seeds by %s</title></head><body><div>Seeds by %s:</div><ul style="list-style-type:none;padding:5px">' % (author_name, author_name)
        for seed in sorted(seeds, key=lambda s: s.name):
            url = url_for("plando_view", author_name=author_name, seed_name=seed.name)
            out += f'<li style="padding:2px"><a href="{url}">{seed.name}</a>: {seed.description.partition("\n")[0]} ({seed.players} players, {seed.flagline})'
            if owner:
                out += f' <a href="{url_for("plando_edit", seed_name=seed.name)}">Edit</a>'
                if seed.hidden:
                    out += " (hidden)"
            out += "</li>"
        out += f"</ul>{PLANDO_DISCLAIMER}</body></html>"
        return make_resp(out)
    else:
        if owner:
            return make_resp(f"<html><body>You haven't made any seeds yet! <a href='{url_for('plando_edit', seed_name="newSeed")}'>Start a new seed</a></body>{PLANDO_DISCLAIMER}</html>")
        else:
            return make_resp(f"<html><body>No seeds by user {author_name}</body>{PLANDO_DISCLAIMER}</html>")

@app.route('/dll')                 
def dll():
    return redirect("https://github.com/sparkle-preference/OriDERandomizer/raw/master/Assembly-CSharp.dll")

@app.route('/dll/beta')            
def dll_beta():
    return redirect("https://github.com/sparkle-preference/OriDERandomizer/raw/master/Assembly-CSharp.dll")
@app.route('/tracker')
def tracker():
    return redirect("https://github.com/jeflefou/OriDETracker/releases/tag/v3.3.2")

@app.route('/apworld')
def apworld():
    # short link for the discord, same shape as /dll; point it at a github
    # release once the item tables stop moving
    return redirect("/generator/apworld")

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
        t0 = monotonic()
        bingo = BingoGameData.with_id(game_id)
        if not bingo:
            return text_resp("Bingo game %s not found" % game_id, 404)
        res = bingo.get_json(first)
        netperf("board_miss", t0, gid=game_id, first=bool(first))
        if not first:
            # repopulate on miss: pre-start lobbies otherwise recompute for every
            # 1 Hz spectator poll (update() only writes this cache after start_time).
            # Copy: set_board strips is_owner, and offset is added to res below.
            Cache.set_board(game_id, dict(res))
        if param_flag("time"):
            server_now = timegm(now.timetuple()) * 1000
            client_now = int(param_val("time"))
            res["offset"] = server_now - client_now
    return json_resp(res)

@app.route('/bingo/game/<int:game_id>/start') #BingoStartCountdown =
def bingo_start_game(game_id):
    with bingo_lock(game_id):
        return _bingo_start_game_inner(game_id)

def _bingo_start_game_inner(game_id):
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
    # cache before the per-client offset is added, so all viewers see the
    # countdown on their next poll instead of after the 60s board TTL
    Cache.set_board(game_id, dict(res))

    server_now = timegm(now.timetuple()) * 1000
    client_now = int(param_val("time"))
    res["offset"] = server_now - client_now
    jsonres = json_resp(res)
    bingo.put()
    return jsonres

@app.route('/bingo/game/<int:game_id>/reroll') #BingoRerollSeed =
def bingo_reroll_seed(game_id):
    """A new seed on this game's settings, handed to the board builder as if it
    had just come from the generator."""
    game = Game.with_id(game_id)
    if not game:
        return text_resp("Game %s not found!" % game_id, 404)
    if not game.params:
        return text_resp("This bingo game has no seed to reroll", 412)
    params = game.fetch_params()
    if getattr(params, "ap_mode", False):
        return text_resp("An Archipelago seed comes from its room, so it can't be rerolled here", 412)
    old_params = params.to_json()
    old_params['seed'] = str(random.randint(0, 1000000000))
    new_params = SeedGenParams.from_json(old_params).get()
    # as in /reroll: modes this game already exists in pass, impossible ones refuse
    problem = seed_mode_problem(new_params, mw_override=True, ap_override=True)
    if problem:
        return text_resp(problem, 409)
    if not new_params.generate():
        return text_resp("Failed to generate seed!", 500)
    new_game = Game.from_params(new_params)
    url = "/bingo/board?game_id=%s&fromGen=1&seed=%s&bingoLines=%s" % (new_game.key.id(), new_params.seed, new_params.bingo_lines)
    bingo = game.bingo_data.get() if game.bingo_data else None
    if bingo and bingo.discovery:
        url += "&disc=%s" % bingo.discovery
    if new_params.sync.enabled and new_params.sync.mode == MultiplayerGameType.SHARED:
        url += "&teamMax=%s" % new_params.players
    return redirect(url)

@app.route('/bingo/game/<int:game_id>/reroll_board') #BingoRerollBoard =
def bingo_reroll_board(game_id):
    with bingo_lock(game_id):
        return _bingo_reroll_board_inner(game_id)

def _bingo_reroll_board_inner(game_id):
    now = datetime.utcnow()
    bingo = BingoGameData.with_id(game_id)
    if not bingo:
        return text_resp("Bingo game %s not found" % game_id, 404)
    user = User.get()
    if not user or bingo.creator != user.key:
        return text_resp("Only the creator can reroll the board", 401)
    # a joined player is holding a seed file with this board's goals baked into
    # it; the join route shares this lock, so nobody slips in mid-reroll
    if bingo.players or bingo.teams:
        return text_resp("Someone has already joined this board", 412)
    game = Game.with_id(game_id)  # a board's id is its game's
    difficulty = param_val("difficulty") or bingo.difficulty or "normal"
    seed = param_val("seed") or bingo.seed or ""
    if seed == (bingo.seed or ""):
        seed = bump_board_seed(seed)  # a reroll has to move the board even when nothing else changed
    d = int(param_val("discCount") or 0)
    lockout = bool(int(param_val("lockout") or 0))
    meta = param_flag("meta")
    bingo.board = bingo_board_cards(game.fetch_params() if game and game.params else None,
                                    difficulty, seed, d, meta, lockout)
    bingo.difficulty = difficulty
    bingo.seed = seed
    bingo.lockout = lockout
    bingo.meta = meta
    bingo.discovery = None
    bingo.disc_squares = []
    if d:
        bingo.discovery_squares(d)
    if param_flag("lines"):
        bingo.bingo_count = int(param_val("lines"))
        bingo.square_count = None
    if param_flag("squares"):
        bingo.square_count = int(param_val("squares"))
    bingo.teams_allowed = param_flag("teams") or bingo.teams_shared or bool(bingo.ap_worlds)
    bingo.event_log.append(BingoEvent(event_type="miscBoard rerolled!", timestamp=now))
    bingo.put()
    # in the shape a poll expects, or every viewer sits on the old board for a TTL
    Cache.set_board(game_id, bingo.get_json())
    res = bingo.get_json(True)
    if param_flag("time"):
        server_now = timegm(now.timetuple()) * 1000
        client_now = int(param_val("time"))
        res["offset"] = server_now - client_now
    return json_resp(res)

@app.route('/bingo/game/<int:game_id>/add/<int:player_id>') #BingoAddPlayer =
def bingo_add_player(game_id, player_id):
    # all writers of a game's BingoGameData serialize on the same per-game
    # lock; a plain-put update can't swallow a concurrent join.
    with bingo_lock(game_id):
        return _bingo_add_player_inner(game_id, player_id)

def _bingo_add_player_inner(game_id, player_id):
    bingo = BingoGameData.with_id(game_id)
    join_team = param_flag("joinTeam")
    if not bingo:
        return text_resp("Bingo game %s not found" % game_id, 404)
    if join_team and not bingo.teams_allowed:
        return text_resp("Teams are forbidden in this game", 412)
    if player_id in bingo.player_nums():
        return text_resp("Player id already in use!", 409)
    if bingo.ap_worlds:
        # the pid IS the Archipelago world, so it has to be one of them, and
        # everyone shares the one team the first joiner opens
        if not 1 <= player_id <= bingo.ap_worlds:
            return text_resp("This Archipelago board has one world; you're player 1." if bingo.ap_worlds == 1
                             else "This is an Archipelago board: pick a player number from 1 to %s."
                             % bingo.ap_worlds, 412)
        if bingo.teams:
            join_team = str(bingo.teams[0].pids()[0])

    player = bingo.init_player(player_id)
    if join_team:
        cap_id = int(param_val("joinTeam") or join_team)
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
        bingo.update({}, player_id, game_id, True)  # lock held by caller
        board = getattr(bingo, "_board_json", None)
        if board is not None:
            Cache.set_board(game_id, board)  # NB: strips is_owner from board
            res = dict(board)
    else:
        # push the new roster into the board cache immediately, or every viewer
        # (including the joiner's own next poll) sees the stale pre-join board
        # for up to 60s. Shallow copy so player_seed below stays per-response.
        Cache.set_board(game_id, dict(res))
    res['player_seed'] = seed
    bingo.put()
    return json_resp(res)


@app.route('/bingo/game/<int:game_id>/remove/<int:player_id>') #BingoRemovePlayer =
def bingo_remove_player(game_id, player_id):
    with bingo_lock(game_id):
        return _bingo_remove_player_inner(game_id, player_id)

def _bingo_remove_player_inner(game_id, player_id):
    bingo = BingoGameData.with_id(game_id)
    if not bingo:
        return text_resp("Bingo game %s not found" % game_id, 404)
    user = User.get()
    if not user or bingo.creator != user.key:
        return text_resp("Only the creator can remove players", 401)
    bingo = bingo.remove_player(player_id).get()
    res = bingo.get_json()
    Cache.set_board(game_id, dict(res))
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

RR_SUFFIX = re.compile(r"RR(\d+)$")

def bump_board_seed(seed):
    """The next board seed after this one. Mirrored in Bingo.js so the reroll
    modal shows the seed it will actually use; this side is authoritative."""
    seed = seed or ""
    match = RR_SUFFIX.search(seed)
    if match:
        return seed[:match.start()] + "RR%s" % (int(match.group(1)) + 1)
    return seed + "RR1"

def bingo_board_cards(params, difficulty, seed, disc, meta, lockout):
    """A fresh board. params is the seed behind a rando board, or None for a
    vanilla+ one."""
    rand = random.Random()
    rand.seed(seed)
    if not params:
        return BingoGenerator.get_cards(rand, 25, False, difficulty, True, disc, meta, lockout, False)
    return BingoGenerator.get_cards(rand, 25, True, difficulty, Variation.OPEN_WORLD in params.variations,
                                    disc, meta, lockout, Variation.KEYSANITY in params.variations,
                                    spawn = params.spawn or "Glades")

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
            meta          = meta,
            seed          = seed  # kept whether or not discovery needs it: a reroll bumps it
        )
        if d:
            bingo.discovery = d
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

def latest_bingo_game(name):
    """(game id, error text) for a username's most recent bingo game. The
    walk costs a name query plus a get per game the user has ever played, and
    the userboard polls once a minute -- so the derived answer is cached."""
    game_id = Cache.get_latest_game(name, bingo=True)
    if game_id:
        return game_id, None
    user = User.get_by_name(name)
    if not user:
        return None, "User '%s' not found" % name
    for key in user.games[::-1]:
        game = key.get()
        if game and game.bingo_data:   # cleanup leaves dangling keys behind
            Cache.set_latest_bingo_game(name, game.key.id())
            return game.key.id(), None
    return None, "Could not find any bingo games for user '%s'" % name


@app.route('/bingo/spectate/<name>') #BingoUserSpectate =
def bingo_user_board(name):
    game_id, err = latest_bingo_game(name)
    if err:
        return text_resp(err, 404)
    return redirect(url_for('bingo_board_spectate', game_id=4 + game_id*7))

@app.route('/bingo/userboard/<name>/') #BingoUserboard =     
def bingo_userboard(name):
    user = User.get_by_name(name)
    if not user:
        return text_resp("User '%s' not found" % name, 404)
    template_values = {'app': "Bingo", 'title': "%s's Bingo Board" % user.name}
    template_values['user'] = user.name
    if user.dark_theme is not None:
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
    game_id, err = latest_bingo_game(name)
    if err:
        return text_resp(err, 404)
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
        params = game.fetch_params()
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
                cards = BingoGenerator.get_cards(rand, 25, True, difficulty, Variation.OPEN_WORLD in params.variations, d, meta, lockout, Variation.KEYSANITY in params.variations, spawn = params.spawn or "Glades")

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
            board         = bingo_board_cards(params, difficulty, seed, d, meta, lockout),
            difficulty    = difficulty,
            subtitle      = params.flag_line(),
            teams_allowed = param_flag("teams"),
            teams_shared  = params.players > 1 and params.sync.mode == MultiplayerGameType.SHARED,
            game          = game.key,
            lockout       = lockout,
            meta          = meta,
            seed          = seed  # kept whether or not discovery needs it: a reroll bumps it
        )
        if d:
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
        ap_bingo = getattr(params, "ap_mode", False)
        if ap_bingo:
            # one team, one world each, so the board's pids ARE the AP worlds.
            # Shadow players (pid > K) hold the bridge's outbox and must survive
            # the roster wipe below.
            bingo.teams_allowed = True
            bingo.ap_worlds = int(params.players)
        # after the AP fields: the creator's page reads ap_worlds off this
        res = bingo.get_json(True)
        if param_flag("time"):
            server_now = timegm(now.timetuple()) * 1000
            client_now = int(param_val("time"))
            res["offset"] = server_now - client_now

        for p in game.get_players():
            if ap_bingo and p.pid() > int(params.players):
                continue
            game.remove_player(p.key.id())
        bkey = bingo.put()
        game.bingo_data = bkey
        game.put()
        return json_resp(json.dumps(res))

@app.route('/netcode/game/<int:game_id>/player/<int:player_id>/bingo', methods=['POST']) #HandleBingoUpdate
def netcode_player_bingo_tick(game_id, player_id):
    status, body = netcode.bingo_update(game_id, player_id, request.form)
    return text_resp(body, status)

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

@app.route('/flags')  # verify feature-flag status per revision
def flag_status():
    flags = {"MULTIWORLD": MULTIWORLD, "ARCHIPELAGO": ARCHIPELAGO}
    rows = "".join("<tr><td style='padding:4px 12px'>%s</td><td style='padding:4px 12px'><b>%s</b></td></tr>"
                   % (name, "ON" if val else "off") for name, val in flags.items())
    return make_resp("<html><body><h3>Feature flags</h3><table border=1>%s</table><p>serving: %s</p></body></html>"
                     % (rows, NETPERF_TAG))

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


    
@app.route('/patchnotes') #  PatchNotes
def patchnotes():
    template_values = template_vals("PatchNotes", "Patch Notes", User.get())
    return render_template(path, **template_values)

# the old per-line doc links are anchors on the one page now
PATCHNOTE_ALIASES = {"3.x": "3.0", "4.0.x": "4.0.0", "4.1.x": "4.1.0"}

@app.route('/patchnotes/<version>')
def patchnotes_version(version):
    return redirect("/patchnotes#%s" % PATCHNOTE_ALIASES.get(version, version))


# Atom ids are permanent identities rather than locations, so they must not move
# when the site is served from another host (bf.orirando.com, localhost, ...).
FEED_TAG_HOST = "orirando.com"

# map/src/patchnotes.json is what the frontend bundles, so the feeds can never
# drift from the page. Loaded lazily and cached: if the file ever fails to ship,
# only these two routes break instead of the whole app failing to import.
_patchnotes_cache = None

class PatchnotesMissing(Exception):
    pass

def patchnotes_doc():
    global _patchnotes_cache
    if _patchnotes_cache is None:
        src = os.path.join(os.path.dirname(__file__), 'map/src/patchnotes.json')
        try:
            with open(src, encoding='utf-8') as f:
                _patchnotes_cache = json.load(f)
        except FileNotFoundError:
            # says what to fix instead of a bare 500 six months from now
            raise PatchnotesMissing(
                "patchnotes.json is not in the image; check its COPY line in the Dockerfile")
    return _patchnotes_cache


def version_tuple(v):
    try:
        return tuple(int(x) for x in v.split("."))
    except ValueError:
        return ()


def latest_note_version():
    """The newest release in the notes: VER, plus a fourth number when the site
    shipped alone. Falls back to VERSION, so a missing file 503s only its own routes."""
    try:
        releases = patchnotes_doc()["releases"]
    except PatchnotesMissing:
        return VERSION
    return releases[0]["version"] if releases else VERSION


@app.route('/patchnotes.json')
def patchnotes_json():
    """The notes as data. ?since=4.2.9 returns only releases newer than that,
    which is what a bot wants when it last announced 4.2.9. ?highlights=1 drops
    the minor changes, matching the page's default view."""
    try:
        doc = patchnotes_doc()
    except PatchnotesMissing as e:
        return text_resp(str(e), 503)
    releases = doc["releases"]

    since = param_val("since")
    if since:
        cutoff = version_tuple(since)
        if not cutoff:
            return text_resp("bad since= version: %s" % since, 400)
        releases = [r for r in releases if version_tuple(r["version"]) > cutoff]

    if param_flag("highlights"):
        releases = [dict(r, changes=[c for c in r["changes"] if c["importance"] == "major"])
                    for r in releases]

    # the newest note, not the dll version: it's what a caller passes back as since=
    body = json.dumps({"categories": doc["categories"], "current": latest_note_version(), "releases": releases})
    resp = make_response(body)
    resp.headers["Content-Type"] = "application/json"
    return resp


# "all" (the default when a release says nothing) reaches both channels, "dev"
# only the dev one, "none" neither.
ANNOUNCE_CHANNELS = {
    "main": lambda a: a == "all",
    "dev": lambda a: a in ("all", "dev"),
}

def announce_webhook(channel):
    return {"main": PATCHNOTES_WEBHOOK_MAIN, "dev": PATCHNOTES_WEBHOOK_DEV}[channel]


def site_only_note(version):
    """The aside a site-only release carries, or None for an ordinary one.
    Mirrored in PatchNotes.js, which renders the same line on the page."""
    parts = version.split(".")
    if len(parts) <= 3:
        return None
    return "(this is a site-only update. %s is still the latest dll)" % ".".join(parts[:3])


def announce_embed(release, base, everything=False):
    # the dev channel takes the whole list: it is the audience that wants the
    # minor entries, and a dev-only release is often all minor
    shown = [c for c in release["changes"] if everything or c["importance"] == "major"]
    lines = []
    note = site_only_note(release["version"])
    if note:
        lines.append("-# *%s*" % note)  # -# is discord's subtext
    if release.get("headline"):
        lines.append(release["headline"])
    for c in shown:
        lines.append("- %s" % c["text"])
        for s in c.get("sub", []):
            lines.append("  - %s" % s)
    if not shown and not release.get("headline"):
        lines.append("Small fixes only - see the full notes.")
    title = "%s%s" % (release["version"], " - %s" % release["title"] if release.get("title") else "")
    # discord truncates a description past 4096 rather than rejecting it, but
    # cutting it here keeps the "read the rest" link meaningful
    body = "\n".join(lines)
    if len(body) > 3900:
        body = body[:3900].rsplit("\n", 1)[0] + "\n- ..."
    return {"title": title, "url": "%s/patchnotes#%s" % (base, release["version"]), "description": body}


def announce_patchnotes(base, force=False, channels=None):
    """Post any releases newer than each channel's marker. Returns a per-channel
    summary. Inert unless a webhook is configured for that channel.

    channels limits which channels are considered; None means all of them, so
    catching one channel up cannot repost to a channel that has already seen it."""
    doc = patchnotes_doc()
    releases = doc["releases"]
    if not releases:
        return {}
    newest = releases[0]["version"]
    out = {}

    for channel, wants in ANNOUNCE_CHANNELS.items():
        if channels is not None and channel not in channels:
            continue
        hook = announce_webhook(channel)
        if not hook:
            # worth saying only when the caller named this channel; the boot
            # path runs on every deploy and would just be noise
            if channels is not None:
                out[channel] = "no webhook configured"
            continue
        was = AnnouncedPatchNotes.claim(channel, newest)
        if was is None:
            # marker already current (or just seeded); force resends the newest
            # only -- never the whole back catalogue
            if not force:
                out[channel] = "nothing new"
                continue
            pending = releases[:1]
        else:
            cutoff = version_tuple(was)
            pending = [r for r in releases if version_tuple(r["version"]) > cutoff]
        pending = [r for r in pending if wants(r.get("announce", "all"))]
        if not pending:
            out[channel] = "nothing for this channel"
            continue
        # oldest first so the channel reads chronologically, 10 embeds per message
        embeds = [announce_embed(r, base, everything=(channel == "dev"))
                  for r in reversed(pending)][-10:]
        try:
            resp = requests.post(hook, json={"embeds": embeds}, timeout=10)
            resp.raise_for_status()
            out[channel] = "posted %s" % ", ".join(r["version"] for r in reversed(pending))
            log.info("patchnotes: announced %s to %s", [r["version"] for r in pending], channel)
        except Exception as e:
            # the marker already moved, so this release will not retry by itself
            out[channel] = "FAILED: %s" % e
            log.error("patchnotes: %s announce POST failed for %s: %s",
                      channel, [r["version"] for r in pending], e)
    return out


_announce_checked = False

@app.before_request
def announce_on_first_request():
    """Runs once per process. A deploy restarts the process, which is the only
    thing that can change VERSION, so this fires exactly once per release."""
    global _announce_checked
    if _announce_checked or not (PATCHNOTES_WEBHOOK_MAIN or PATCHNOTES_WEBHOOK_DEV):
        return
    # never make a game wait on Discord: the webhook POST is synchronous, so
    # let a browser request be the one that pays for it
    if request.path.startswith("/netcode/"):
        return
    _announce_checked = True  # set first: a failure must not retry every request
    try:
        announce_patchnotes(request.host_url.rstrip("/"))
    except Exception:
        log.exception("patchnotes: announce check failed")


@app.route('/patchnotes/announce')
def patchnotes_announce():
    """Manual resend, for when a POST failed and the marker already moved.
    ?force=1 reposts the newest release even if the marker is current.
    ?channel=main|dev|all picks which channels to post to (default all)."""
    if not User.is_admin():
        return text_resp("admins only", 401)
    if not (PATCHNOTES_WEBHOOK_MAIN or PATCHNOTES_WEBHOOK_DEV):
        return text_resp("no PATCHNOTES_WEBHOOK_MAIN or PATCHNOTES_WEBHOOK_DEV set", 503)
    channel = (param_val("channel") or "all").lower()
    if channel != "all" and channel not in ANNOUNCE_CHANNELS:
        return text_resp("channel must be all, %s" % ", ".join(ANNOUNCE_CHANNELS), 400)
    try:
        result = announce_patchnotes(request.host_url.rstrip("/"), force=param_flag("force"),
                                     channels=None if channel == "all" else {channel})
    except PatchnotesMissing as e:
        return text_resp(str(e), 503)
    return text_resp(json.dumps(result, indent=2))


@app.route('/patchnotes.xml')
def patchnotes_feed():
    """Atom feed of the highlights, newest first -- for feed readers and the
    Discord bots that can consume one without anybody writing a poster."""
    try:
        doc = patchnotes_doc()
    except PatchnotesMissing as e:
        return text_resp(str(e), 503)
    # CANONICAL_HOST is an env var that is often unset, so fall back to whatever
    # host the feed was actually fetched from rather than emitting "https:///".
    base = ("https://%s" % CANONICAL_HOST) if CANONICAL_HOST else request.host_url.rstrip("/")
    releases = doc["releases"][:25]

    def entry(r):
        major = [c for c in r["changes"] if c["importance"] == "major"]
        items = "".join(
            "<li>%s%s</li>" % (
                escape(c["text"]),
                "<ul>%s</ul>" % "".join("<li>%s</li>" % escape(s) for s in c["sub"]) if c.get("sub") else "")
            for c in major)
        summary = "<p>%s</p>" % escape(r["headline"]) if r.get("headline") else ""
        content = "%s<ul>%s</ul>" % (summary, items) if items else (summary or "<p>Small fixes only.</p>")
        title = "%s%s" % (r["version"], " - %s" % r["title"] if r.get("title") else "")
        url = "%s/patchnotes#%s" % (base, r["version"])
        return (
            "<entry>"
            "<title>%s</title>"
            "<id>tag:%s,%s:patchnotes/%s</id>"  # stable identity, not a location
            "<link href=\"%s\"/>"
            "<updated>%sT00:00:00Z</updated>"
            "<content type=\"html\">%s</content>"
            "</entry>"
        ) % (escape(title), FEED_TAG_HOST, r["date"], r["version"], url, r["date"], escape(content))

    feed = (
        "<?xml version=\"1.0\" encoding=\"utf-8\"?>"
        "<feed xmlns=\"http://www.w3.org/2005/Atom\">"
        "<title>Ori DE Randomizer patch notes</title>"
        "<id>%s/patchnotes.xml</id>"
        "<link href=\"%s/patchnotes\"/>"
        "<link rel=\"self\" href=\"%s/patchnotes.xml\"/>"
        "<updated>%sT00:00:00Z</updated>"
        "%s</feed>"
    ) % (base, base, base, releases[0]["date"] if releases else "1970-01-01",
         "".join(entry(r) for r in releases))

    resp = make_response(feed)
    resp.headers["Content-Type"] = "application/atom+xml; charset=utf-8"
    return resp
