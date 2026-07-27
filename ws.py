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
from urllib.parse import parse_qs
from threading import Lock

from google.cloud import ndb
from simple_websocket import ConnectionClosed

import netcode
from util import WS_CONN_LIMIT, NETPERF_TAG

_conns_lock = Lock()
_conns = 0


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
                conn.send(reply)
            if close:
                break
    except ConnectionClosed:
        pass
    finally:
        with _conns_lock:
            _conns -= 1
            gauge = _conns
        log.info("NETPERF ws_conns tag=%s n=%s ev=disconnect gid=%s pid=%s", NETPERF_TAG, gauge, game_id, player_id)
