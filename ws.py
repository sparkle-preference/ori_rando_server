"""Websocket adapter over the transport-neutral session layer (netcode.py).

v1 protocol: text frames of the form "kind:body". The client sends
"tick:<form-encoded tick payload>" at ~1 Hz; the server replies
"tick:<tick body>" with the body byte-identical to the /tick/ http
response (frozen by golden_wire_test/session_golden_test). Unknown kinds
get "err:<kind>" and the connection stays up (a newer server talking to
an older dll must not kill the socket). A tick that fails (dead game:
412) sends "err:tick:<status>" and closes — the client's http fallback
takes over and surfaces the error UX the same way it always has.

handle_frame is pure (frame in, reply out) for tests; run_connection owns
the socket loop, the per-frame ndb context, and the connection gauge.

Capacity model: one gunicorn thread per open socket (see Dockerfile
--threads and util.WS_CONN_LIMIT). Saturation is visible in the logs:
"NETPERF ws_conns" gauges on every connect/disconnect, and an explicit
"NETPERF ws_conn_reject" line whenever the limit turns a client away.
"""
import logging as log
from queue import Queue, Empty
from threading import Lock, Thread
from time import monotonic
from urllib.parse import parse_qs

from google.cloud import ndb
from simple_websocket import ConnectionClosed

import netcode
import push
from util import WS_CONN_LIMIT, NETPERF_TAG, netperf

_conns_lock = Lock()
_conns = 0

# live sockets by (game_id, player_id). Each entry carries a send lock:
# the connection's own thread sends tick replies and the pusher thread
# sends pushed frames, and simple_websocket's send() is not thread-safe.
# Last connection wins on duplicate ids (reconnects, dual-boxing).
_socks_lock = Lock()
_socks = {}


def _register(gpid, conn):
    with _socks_lock:
        entry = (conn, Lock())
        _socks[gpid] = entry
        return entry[1]


def _unregister(gpid, conn):
    with _socks_lock:
        entry = _socks.get(gpid)
        if entry is not None and entry[0] is conn:
            del _socks[gpid]


# --- push (WS_PUSH): send a fresh tick frame the moment a player's tick
# cache is busted, instead of waiting for their next 1 Hz tick. Best-effort
# by design — the client's own tick remains the reliable delivery path, so
# anything lost here arrives at most one tick later.

_push_queue = Queue()
_push_started = False


def enable_push():
    """Wire cache-bust notifications to a pusher thread. Called once at
    startup when WEBSOCKETS and WS_PUSH are both set."""
    global _push_started
    if _push_started:
        return
    _push_started = True
    Thread(target=_pusher, daemon=True, name="ws-push").start()
    push.set_handler(_notify)


def _notify(gpid):
    # runs on request threads for every checksum bust in every game —
    # only pay the queue hop when the player actually has a socket
    with _socks_lock:
        if gpid not in _socks:
            return
    _push_queue.put(gpid)


def _pusher():
    from models import client as ndb_client
    while True:
        batch = {_push_queue.get()}
        try:
            while True:
                batch.add(_push_queue.get_nowait())
        except Empty:
            pass
        for gpid in batch:
            _push_one(gpid, ndb_client)


def _push_one(gpid, ndb_client):
    with _socks_lock:
        entry = _socks.get(gpid)
    if entry is None:
        return
    conn, send_lock = entry
    t0 = monotonic()
    try:
        with ndb_client.context():
            body = netcode.tick_output(*gpid)
        if body is None:
            return
        with send_lock:
            conn.send("tick:" + body)
        netperf("ws_push", t0, gid=gpid[0], pid=gpid[1])
    except ConnectionClosed:
        pass  # run_connection's finally cleans up the registry
    except Exception:
        log.exception("ws push failed for %s.%s", gpid[0], gpid[1])


def handle_frame(game_id, player_id, frame):
    """One frame in, (reply_or_None, close_after) out."""
    kind, sep, body = frame.partition(":")
    if kind == "tick" and sep:
        # match request.form's parsing: scalar values, blanks kept
        payload = {k: v[0] for k, v in parse_qs(body, keep_blank_values=True).items()}
        status, out = netcode.tick(game_id, player_id, payload)
        if status != 200:
            return "err:tick:%s" % status, True
        return "tick:%s" % out, False
    log.warning("ws: unknown frame kind %r from %s.%s", kind, game_id, player_id)
    return "err:%s" % kind, False


def run_connection(conn, game_id, player_id):
    global _conns
    with _conns_lock:
        if _conns >= WS_CONN_LIMIT:
            log.warning("NETPERF ws_conn_reject tag=%s n=%s gid=%s pid=%s", NETPERF_TAG, _conns, game_id, player_id)
            conn.close(reason=1013, message="server full")  # 1013: try again later
            return
        _conns += 1
        gauge = _conns
    log.info("NETPERF ws_conns tag=%s n=%s ev=connect gid=%s pid=%s", NETPERF_TAG, gauge, game_id, player_id)
    gpid = (game_id, player_id)
    send_lock = _register(gpid, conn)
    try:
        while True:
            frame = conn.receive()
            if frame is None:
                break
            if isinstance(frame, bytes):
                frame = frame.decode("utf-8", "replace")
            try:
                # the middleware's ndb context lives as long as the
                # connection and contexts can't nest on a thread, so clear
                # its cache each frame — otherwise a multi-hour connection
                # serves stale entities and the cache never shrinks
                ndb.get_context().clear_cache()
                reply, close = handle_frame(game_id, player_id, frame)
            except Exception:
                # parity with http, where a failed tick is one 500 and the
                # client just keeps polling — don't tear down the transport
                log.exception("ws: frame handler failed for %s.%s", game_id, player_id)
                continue
            if reply is not None:
                with send_lock:
                    conn.send(reply)
            if close:
                break
    except ConnectionClosed:
        pass
    finally:
        _unregister(gpid, conn)
        with _conns_lock:
            _conns -= 1
            gauge = _conns
        log.info("NETPERF ws_conns tag=%s n=%s ev=disconnect gid=%s pid=%s", NETPERF_TAG, gauge, game_id, player_id)
