"""Thin HTTP adapters over the transport-neutral session layer.

Parse transport params, delegate, wrap the (status, body) it hands back --
nothing else. New netcode behaviour belongs in the top-level netcode.py, which
knows nothing about Flask and is tested without a request context.

`import netcode` below is the top-level module, not this one: absolute imports.
"""
from flask import Blueprint, request

import netcode
import ws
from cache import Cache
from web.extensions import sock
from web.responses import json_resp, text_resp

bp = Blueprint("netcode", __name__)


# Client-netcode routes are thin HTTP adapters over the transport-neutral
# session layer in netcode.py: parse transport params, delegate, wrap
# (status, body) â€” nothing else. New netcode behavior belongs in netcode.py.
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

# Archipelago link management (kill-switched in the session layer: with
# ARCHIPELAGO unset every route 404s).
@bp.route('/netcode/game/<int:game_id>/ap/connect', methods=['POST'])
def netcode_ap_connect(game_id):
    status, body = netcode.ap_connect(game_id, request.form)
    return text_resp(body, status)

@bp.route('/netcode/game/<int:game_id>/ap/status')
def netcode_ap_status(game_id):
    status, body = netcode.ap_status(game_id)
    return json_resp(body, status) if status == 200 else text_resp(body, status)

@bp.route('/netcode/game/<int:game_id>/ap/disconnect', methods=['POST'])
def netcode_ap_disconnect(game_id):
    status, body = netcode.ap_disconnect(game_id)
    return text_resp(body, status)

# websocket transport. The route body lives in ws.py; each connection pins a
# gunicorn thread until it closes, capped by util.WS_CONN_LIMIT.


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
