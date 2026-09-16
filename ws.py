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
  complete:                            -> completeack:<status>
      (acked since 2026-08-01: clients resend until heard, because a lost
      complete strands multiworld releases. game_complete is idempotent.)

Server -> client: tick:<body> frames, either as tick replies or pushed
unsolicited — the client treats both identically.

handle_frame is pure (frame in, reply out) for tests; run_connection owns
the socket loop, the per-frame ndb context, and the connection gauge.

Capacity model: one gunicorn thread per open socket (see Dockerfile
--threads and util.WS_CONN_LIMIT). Saturation is visible in the logs:
"NETPERF ws_conns" gauges on every connect/disconnect, and an explicit
"NETPERF ws_conn_reject" line whenever the limit turns a client away.
"""
import hashlib
import logging as log
import os
from queue import Queue, Empty
from threading import Lock, Thread
from time import monotonic
from urllib.parse import parse_qs
from urllib.request import Request, urlopen

from google.cloud import ndb
from simple_websocket import ConnectionClosed

import netcode
import push
from cache import Cache
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
    dropped = False
    with _socks_lock:
        entry = _socks.get(gpid)
        if entry is not None and entry[0] is conn:
            del _socks[gpid]
            dropped = gpid in _ghosts
            _ghosts.discard(gpid)
            _ghost_relayed.discard(gpid)
    if dropped:
        # the roster shrank, and whoever is left may now be the host
        _broadcast_roster(gpid[0])


# --- ghost multiplayer signalling ---------------------------------------
#
# Players who want to see each other exchange one WebRTC description each; the
# server passes those two strings along and never looks inside them. Nothing is
# persisted, and a failure here costs a cosmetic feature rather than anything in
# the game. It also hands out relay credentials, which it holds for no longer
# than it takes to forward them.
#
# Participation lives beside _socks and dies with the connection, because it
# describes a live socket rather than anything worth keeping. Same
# single-instance assumption the push path already makes -- fine while Cloud
# Run is pinned to max-instances=1, and the failure mode if that changes is
# "ghosts do not connect", not a broken game.
_ghosts = set()

# players nobody could reach directly, for as long as they hold this socket
_ghost_relayed = set()


def _ghost_roster(game_id):
    """(host player id, participating player ids) for one game, live sockets only."""
    with _socks_lock:
        pids = sorted(pid for (gid, pid) in _ghosts if gid == game_id)
        direct = [pid for pid in pids if (game_id, pid) not in _ghost_relayed]
    # lowest id hosts: stable, computable by every client from the same list, and
    # it needs no negotiation round. A relayed host relays for the whole lobby, so
    # it hosts only when nobody else can.
    host = (direct or pids or [0])[0]
    return host, pids


def _send_to(gpid, frame):
    """Send one frame to one player. False if they are not here."""
    with _socks_lock:
        entry = _socks.get(gpid)
    if entry is None:
        return False
    conn, send_lock = entry
    try:
        with send_lock:
            conn.send(frame)
        return True
    except ConnectionClosed:
        return False  # run_connection's finally cleans up the registry
    except Exception:
        log.exception("ws: ghost send failed for %s.%s", gpid[0], gpid[1])
        return False


def _broadcast_roster(game_id):
    host, pids = _ghost_roster(game_id)
    frame = "ghosts:%s:%s" % (host, ",".join(str(p) for p in pids))
    for pid in pids:
        _send_to((game_id, pid), frame)


# Relay credentials, minted elsewhere and never stored here. Cached because this
# runs single-instance and cannot spend a round trip per frame.
_ice_lock = Lock()
_ice_cache = {}
ICE_TTL = 600
ICE_FAIL_TTL = 60
ICE_TIMEOUT = 3


def _ice_config(game_id):
    """The relay's ICE entry as json, or None when there is no relay to offer."""
    url = os.environ.get("TURN_CREDENTIALS_URL")
    token = os.environ.get("TURN_CREDENTIALS_TOKEN")
    if not url or not token:
        return None

    now = monotonic()
    with _ice_lock:
        entry = _ice_cache.get(game_id)
        if entry is not None and entry[0] > now:
            return entry[1]

    # outside the lock: a duplicate fetch beats blocking every other game on it
    payload = None
    try:
        # Cloudflare fronts the relay and 403s urllib's default agent.
        request = Request(
            "%s?name=g%s" % (url, game_id),
            headers={
                "Authorization": "Bearer %s" % token,
                "User-Agent": "ori-rando-server",
            },
        )
        with urlopen(request, timeout=ICE_TIMEOUT) as response:
            payload = response.read().decode()
    except Exception as err:
        log.warning("ws: ice fetch failed for game %s: %s", game_id, err)

    with _ice_lock:
        for key, cached in list(_ice_cache.items()):
            if cached[0] <= now:
                del _ice_cache[key]
        _ice_cache[game_id] = (now + (ICE_TTL if payload else ICE_FAIL_TTL), payload)
    return payload


# --- push: send a fresh tick frame the moment a player's tick cache is
# busted, instead of waiting for their next 1 Hz tick. Best-effort
# by design — the client's own tick remains the reliable delivery path, so
# anything lost here arrives at most one tick later.

# bounded: if the pusher ever wedges, drop pushes (best-effort) instead
# of growing forever
_push_queue = Queue(maxsize=1000)
_push_thread = None
_push_thread_lock = Lock()


def enable_push():
    """Wire cache-bust notifications up. Called at startup from main.py.
    The pusher thread is NOT started here: with gunicorn --preload this code
    runs in the master process and threads do not survive the fork into the
    worker. The thread starts lazily in whichever process actually notifies."""
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
        # acked so the client can resend-until-heard: a lost complete used
        # to strand multiworld releases (game 134478)
        status, _ = netcode.game_complete(game_id, player_id)
        return "completeack:%s" % status, False
    if kind == "goals":
        # asked on every socket open while a bingo seed is loaded, so a
        # pre-start reroll reaches the client on its next connect
        status, out = netcode.goals(game_id, player_id)
        if status == 200:
            return "goals:%s" % out, False
        return "err:goals:%s" % status, False
    if kind == "areas":
        # the client offers its areas.ori hash once per seed load; a match
        # gets "ok", anything else the current file. This channel replaces
        # the retiring http fetch.
        areas = Cache.get_areas()
        if hashlib.sha256(areas.encode()).hexdigest() == body.strip().lower():
            return "areas:ok", False
        return "areas:%s" % areas, False
    if kind == "ghosts":
        # "ghosts:1" opts in, "ghosts:0" out. The reply is the roster, so one
        # frame both joins and tells the client who else is here.
        want = body.strip() == "1"
        gpid = (game_id, player_id)
        with _socks_lock:
            changed = (gpid in _ghosts) != want
            if want:
                _ghosts.add(gpid)
            else:
                _ghosts.discard(gpid)
                _ghost_relayed.discard(gpid)
        if changed:
            _broadcast_roster(game_id)
        host, pids = _ghost_roster(game_id)
        return "ghosts:%s:%s" % (host, ",".join(str(p) for p in pids)), False
    if kind == "ghostice":
        # "ghostice:<peer>" -- relay credentials, and the report that <peer> could
        # not be reached directly. The mark lands on <peer>, never on the asker: a
        # host fails against every unreachable peer and must not demote itself.
        try:
            peer_pid = int(body.strip())
        except ValueError:
            return "err:ghostice:malformed", False
        gpid = (game_id, player_id)
        peer = (game_id, peer_pid)
        with _socks_lock:
            if gpid not in _ghosts:
                return "err:ghostice:notjoined", False
            marked = peer in _ghosts and peer not in _ghost_relayed
            if marked:
                _ghost_relayed.add(peer)
        if marked:
            log.info("ws: ghost relay for %s.%s, reported by %s", game_id, peer_pid, player_id)
            # the host may have just become the wrong player
            _broadcast_roster(game_id)
        payload = _ice_config(game_id)
        if payload is None:
            return "err:ghostice:unavailable", False
        return "ice:%s" % payload, False
    if kind == "ghost":
        # "ghost:<to>:<blob>" -- one description, relayed verbatim. The server
        # does not parse the blob and does not keep it.
        target, sep2, payload = body.partition(":")
        if not sep2:
            return "err:ghost:malformed", False
        try:
            to_pid = int(target)
        except ValueError:
            return "err:ghost:malformed", False
        gpid = (game_id, player_id)
        with _socks_lock:
            joined = gpid in _ghosts
            reachable = (game_id, to_pid) in _ghosts
        if not joined:
            # relaying for someone who has not opted in would let them be seen
            # without being visible, which is the one thing the setting promises
            return "err:ghost:notjoined", False
        if not reachable:
            return "err:ghost:away", False
        if _send_to((game_id, to_pid), "ghost:%s:%s" % (player_id, payload)):
            return None, False
        return "err:ghost:away", False
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
