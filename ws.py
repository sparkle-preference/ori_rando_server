"""Websocket adapter over the session layer (netcode.py).

Text frames are "kind:body"; qs bodies are form-encoded, and replies match the http bodies
byte for byte. An unknown kind gets "err:<kind>" and the socket stays up.

  tick:<qs>                                -> tick:<body>, or err:tick:<status> and close
  found:<token>|<qs>|<coords>|<kind>|<id>  -> foundack:<token>|<status>  (id may hold |)
  bingo:<qs>                               -> bingoack:<status>
  conf:<signal> / seed:<qs>                -> no reply
  complete:                                -> completeack:<status>
  goals:                                   -> goals:<line> or err:goals:<status>
  areas:<sha256>                           -> areas:ok or areas:<file>
  ghosts:<0|1> / ghostice:<pid> / ghost:<to>:<blob>  -> ghost signalling, below

The server also pushes tick:<body> frames unsolicited; the client treats them as replies.
Each open socket pins a gunicorn thread (util.WS_CONN_LIMIT).
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

# (gid, pid) -> (conn, send lock): simple_websocket's send isn't thread-safe and the pusher
# shares the socket. The last connection for an id wins.
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


# --- ghost signalling: relays opaque WebRTC descriptions between opted-in players and hands
# out relay credentials. Nothing is persisted; membership dies with the socket.
_ghosts = set()

# players nobody could reach directly, for as long as they hold this socket
_ghost_relayed = set()


def _ghost_roster(game_id):
    """(host player id, participating player ids) for one game, live sockets only."""
    with _socks_lock:
        pids = sorted(pid for (gid, pid) in _ghosts if gid == game_id)
        direct = [pid for pid in pids if (game_id, pid) not in _ghost_relayed]
    # lowest pid hosts, so every client derives the same host; a relayed player hosts
    # only when everyone is relayed
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


# relay credentials from TURN_CREDENTIALS_URL, cached per game
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


# --- push: a checksum bust sends that player a fresh tick frame now. Best-effort; their
# next tick is the reliable path.

# bounded: a wedged pusher drops pushes rather than growing
_push_queue = Queue(maxsize=1000)
_push_thread = None
_push_thread_lock = Lock()


def enable_push():
    """Register the push handler. The pusher starts lazily: --preload runs this in the
    master, and threads don't survive the fork."""
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
    # every bust in every game lands here; queue only for players with a socket
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
    # like request.form: scalar values, blanks kept for flag-by-presence args
    return {k: v[0] for k, v in parse_qs(body, keep_blank_values=True).items()}


def handle_frame(game_id, player_id, frame):
    """One frame in, (reply_or_None, close_after) out."""
    kind, sep, body = frame.partition(":")
    if not sep:
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
        # acked: clients resend until heard
        status, _ = netcode.game_complete(game_id, player_id)
        return "completeack:%s" % status, False
    if kind == "goals":
        # asked on every socket open, so a pre-start reroll reaches the client
        status, out = netcode.goals(game_id, player_id)
        if status == 200:
            return "goals:%s" % out, False
        return "err:goals:%s" % status, False
    if kind == "areas":
        # offered once per seed load; a mismatch gets the current file
        areas = Cache.get_areas()
        if hashlib.sha256(areas.encode()).hexdigest() == body.strip().lower():
            return "areas:ok", False
        return "areas:%s" % areas, False
    if kind == "ghosts":
        # "ghosts:1" joins, "ghosts:0" leaves; the reply is the roster
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
        # relay credentials, plus a report that <peer> is unreachable directly. The mark
        # lands on the peer: a host fails against every such peer and must not demote itself.
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
        # relayed verbatim, never parsed or kept
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
            # a non-participant must not see others without being seen
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
                # the ndb context lives as long as the socket and can't nest, so clear it
                # per frame or it serves stale entities and grows forever
                ndb.get_context().clear_cache()
                reply, close = handle_frame(game_id, player_id, frame)
            except Exception:
                # like an http 500: log it and keep the socket
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
