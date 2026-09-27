"""HTTP adapters over netcode.py: parse, delegate, wrap. Behavior belongs in netcode.py.

`import netcode` below is the top-level module, not this one.
"""
from urllib.parse import unquote_to_bytes

from flask import Blueprint, request

import netcode
import ws
from cache import Cache
from web.extensions import sock
from web.responses import json_resp, text_resp

bp = Blueprint("netcode", __name__)


@bp.route('/netcode/game/<int:game_id>/player/<int:player_id>/found/<coords>/<kind>/<path:id>/')
@bp.route('/netcode/game/<int:game_id>/player/<int:player_id>/found/<coords>/<kind>/<path:id>')
def netcode_found_pickup(game_id, player_id, coords, kind, id):
    status, body = netcode.found_pickup(game_id, player_id, coords, kind, id, request.args)
    return text_resp(body, status)


@bp.route('/netcode/game/<int:game_id>/player/<int:player_id>/tick/', methods = ['POST'])
@bp.route('/netcode/game/<int:game_id>/player/<int:player_id>/tick', methods = ['POST'])
def netcode_tick_post(game_id, player_id):
    status, body = netcode.tick(game_id, player_id, request.form)
    return text_resp(body, status)


@bp.route('/netcode/game/<int:game_id>/player/<int:player_id>/complete')
def netcode_game_complete(game_id, player_id):
    status, body = netcode.game_complete(game_id, player_id)
    return text_resp(body, status)


@bp.route('/netcode/game/<int:game_id>/player/<int:player_id>/callback/<path:signal>')
def netcode_signal_callback(game_id, player_id, signal):
    # clients send the signal unescaped, so any "?" in it began the query string
    raw_uri = request.environ.get("RAW_URI") or request.environ.get("REQUEST_URI") or ""
    if request.query_string or "?" in raw_uri:
        signal += "?" + unquote_to_bytes(request.query_string).decode("utf-8", "replace")
    status, body = netcode.signal_callback(game_id, player_id, signal)
    return text_resp(body, status)


@bp.route('/netcode/game/<int:game_id>/player/<int:player_id>/setSeed', methods=['POST'])
@bp.route('/netcode/game/<int:game_id>/player/<int:player_id>/connect', methods=['POST'])
def netcode_connect(game_id, player_id):
    status, body = netcode.connect(game_id, player_id, request.form)
    return text_resp(body, status)


@bp.route('/netcode/areas')
def netcode_get_areas_dot_ori():
    return text_resp(Cache.get_areas())

# Archipelago link management; every route 404s unless ARCHIPELAGO is set


@bp.route('/netcode/game/<int:game_id>/ap/connect', methods=['POST'])
def netcode_ap_connect(game_id):
    status, body = netcode.ap_connect(game_id, request.form)
    return text_resp(body, status)


@bp.route('/netcode/game/<int:game_id>/ap/status')
def netcode_ap_status(game_id):
    status, body = netcode.ap_status(game_id)
    return json_resp(body, status) if status == 200 else text_resp(body, status)


@bp.route('/netcode/game/<int:game_id>/ap/hints')
def netcode_ap_hints(game_id):
    status, body = netcode.ap_hints(game_id)
    return json_resp(body, status) if status == 200 else text_resp(body, status)


@bp.route('/netcode/game/<int:game_id>/ap/hints/buy', methods=['POST'])
def netcode_ap_buy_hint(game_id):
    status, body = netcode.ap_buy_hint(game_id, request.form)
    return text_resp(body, status)


@bp.route('/netcode/game/<int:game_id>/ap/disconnect', methods=['POST'])
def netcode_ap_disconnect(game_id):
    status, body = netcode.ap_disconnect(game_id)
    return text_resp(body, status)

# each open socket pins a gunicorn thread, capped by util.WS_CONN_LIMIT


@sock.route('/netcode/game/<int:game_id>/player/<int:player_id>/ws')
def netcode_ws(conn, game_id, player_id):
    ws.run_connection(conn, game_id, player_id)

ws.enable_push()


@bp.route('/netcode/game/<int:game_id>/player/<int:player_id>/goals')
def netcode_goals(game_id, player_id):
    status, body = netcode.goals(game_id, player_id)
    return text_resp(body, status)


@bp.route('/netcode/game/<int:game_id>/player/<int:player_id>/bingo', methods=['POST']) #HandleBingoUpdate
def netcode_player_bingo_tick(game_id, player_id):
    status, body = netcode.bingo_update(game_id, player_id, request.form)
    return text_resp(body, status)
