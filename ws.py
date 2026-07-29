"""Websocket adapter over the transport-neutral session layer (netcode.py).

Protocol: text frames of the form "kind:body". Unknown kinds get
"err:<kind>" and the connection stays up (a newer server talking to an
older dll must not kill the socket; a newer dll talking to an older
server sees its frames err'd and falls back to http per channel).

Client -> server frames (bodies use the same form-encoding request.form
would parse; every reply body is byte-identical to the corresponding
http response, frozen by golden_wire_test/session_golden_test):

  tick:<qs>                            -> tick:<body>   (v1; a failing
      tick sends err:tick:<status> and closes — the http fallback takes
      over and surfaces the error UX)
  found:<token>|<qs>|<coords>|<kind>|<id>  -> foundack:<token>|<status>
      (id goes LAST and is parsed greedily: TW ids contain slashes and
      commas. token is client-chosen, echoed verbatim — the client's
      pickup queue correlates acks and keeps its retry/Gone/NotAcceptable
      semantics; qs carries zone= and flag-by-presence remove/override.)
  bingo:<qs>                           -> bingoack:<status>
      (bingoData=<json>&version=..; always acked because the http client
      fast-retries on failure — non-200 lets it keep doing that.)
  conf:<signal>                        -> no reply (http client ignores
      the /callback/ response entirely)
  seed:<qs>                            -> no reply (setSeed; http client
      fires and forgets)
  complete:                            -> no reply (fire and forget)

Server -> client: tick:<body> frames, either as tick replies or pushed
unsolicited (WS_PUSH) — the client treats both identically.

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

# bounded: if the pusher ever wedges, drop pushes (best-effort) instead
# of growing forever
_push_queue = Queue(maxsize=1000)
_push_thread = None
_push_thread_lock = Lock()


def enable_push():
    """Wire cache-bust notifications up. Called at startup when WEBSOCKETS
    and WS_PUSH are both set. The pusher thread is NOT started here: with
    gunicorn --preload this code runs in the master process and threads do
    not survive the fork into the worker (game 134236: WS_PUSH on, sockets
    up, zero pushes, zero errors). The thread starts lazily in whichever
    process actually notifies."""
    push.set_handler(_notify)


def _ensure_pusher():
    global _push_thread
    if _push_thread is not None and _push_thread.is_alive():
        return
    with _push_thread_lock:
        if _push_thread is None or not _push_thread.is_alive():
            _push_thread = Thread(target=_pusher, daemon=True, name="ws-push")
            _push_thread.start()
            log.info("NETPERF ws_push_thread tag=%s ev=start", NETPERF_TAG)


def _notify(gpid):
    # runs on request threads for every checksum bust in every game —
    # only pay the queue hop when the player actually has a socket
    with _socks_lock:
        if gpid not in _socks:
            return
    _ensure_pusher()
    try:
        _push_queue.put_nowait(gpid)
    except Exception:
        log.warning("ws: push queue full, dropping push for %s.%s", gpid[0], gpid[1])


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


def _qs(body):
    # match request.form's parsing: scalar values, blanks kept (flag-by-
    # presence args like "remove" arrive as bare keys with empty values)
    return {k: v[0] for k, v in parse_qs(body, keep_blank_values=True).items()}


def handle_frame(game_id, player_id, frame):
    """One frame in, (reply_or_None, close_after) out."""
    kind, sep, body = frame.partition(":")
    if not sep:
        # a prefix-less frame has no kind at all
        log.warning("ws: unknown frame kind %r from %s.%s", kind, game_id, player_id)
        return "err:%s" % kind, False
    if kind == "tick":
        status, out = netcode.tick(game_id, player_id, _qs(body))
        if status != 200:
            return "err:tick:%s" % status, True
        return "tick:%s" % out, False
    if kind == "found":
        parts = body.split("|", 4)
        if len(parts) != 5:
            return "err:found:malformed", False
        token, qs, coords, pickup_kind, pickup_id = parts
        status, _ = netcode.found_pickup(game_id, player_id, coords, pickup_kind, pickup_id, _qs(qs))
        return "foundack:%s|%s" % (token, status), False
    if kind == "bingo":
        status, _ = netcode.bingo_update(game_id, player_id, _qs(body))
        return "bingoack:%s" % status, False
    if kind == "conf":
        netcode.signal_callback(game_id, player_id, body)
        return None, False
    if kind == "seed":
        netcode.connect(game_id, player_id, _qs(body))
        return None, False
    if kind == "complete":
        netcode.game_complete(game_id, player_id)
        return None, False
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
