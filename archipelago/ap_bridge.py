"""Archipelago room bridge: one outbound websocket per (game, world).

Each AP-mode world w runs a daemon thread joining the room as slot 'Ori<w>':
shadow player K+w's slot bitfield is polled for outgoing LocationChecks,
ReceivedItems fill world w's manifest slots (lowest unused match, monotone
and idempotent so a full replay is safe), the complete path sends
StatusUpdate{CLIENT_GOAL}, and LocationScouts resolves the real names the
seed ships as "AP Item #n". Scouting is best-effort.

LAZY-START ONLY -- importing this module must never start a thread (gunicorn
--preload forks kill import-time threads; see ws.py). Threads arm from the
ap/connect route and heal(). Wire shapes follow Archipelago 0.6.7
MultiServer.py. Design notes: prior_notes/ARCHIPELAGO_NOTES.md.
"""
import json
import logging as log
import os
import socket
import threading
from time import monotonic

from google.cloud import ndb
from simple_websocket import Client as WsClient, ConnectionClosed

from ap_models import APLink, APNames, ap_display_name, ap_slot_name
from cache import Cache
from util import ARCHIPELAGO, is_mw_manifest_loc

AP_GAME_NAME = "Ori DE Rando"
AP_VERSION = {"class": "Version", "major": 0, "minor": 6, "build": 7}
ITEMS_HANDLING = 0b011
CLIENT_GOAL = 30
SCOUT_CHUNK = 100        # locations per LocationScouts message
EX_DENOMS = (50, 100, 200)

POLL_SECS = 2.0          # shadow-outbox poll cadence
RECV_TIMEOUT = 1.0
LINK_RECHECK_SECS = 15.0  # re-read APLink (disable/goal from other processes)
HANDSHAKE_TIMEOUT = 20.0
CONNECT_TIMEOUT = 10.0   # the OS SYN ladder is ~4 min
HEAL_TTL = 45.0          # request-path memo: non-AP games pay a dict lookup
BACKOFF_MIN, BACKOFF_MAX = 1.0, 60.0

_DATA_DIR = os.path.join(os.path.dirname(__file__), "oride_apworld", "oride", "data")
with open(os.path.join(_DATA_DIR, "items.json")) as _f:
    ITEM_KEY_BY_AP_ID = {i["ap_id"]: (i["code"], i["id"]) for i in json.load(_f)}
with open(os.path.join(_DATA_DIR, "locations.json")) as _f:
    AP_LOC_BY_COORD = {l["coord"]: l["ap_id"] for l in json.load(_f)}


class ApRefused(Exception):
    """The room rejected our Connect (bad slot/password/version)."""


def _match_key(code, id):
    """Manifest (code, id) -> the datapackage identity AP knows it by.
    EX exports ride denomination names; ties round down (mirrors
    convert.nearest_ex_denom so both sides bucket identically)."""
    if code == "EX":
        try:
            v = int(id)
        except (TypeError, ValueError):
            v = 0
        return ("EX", str(min(EX_DENOMS, key=lambda d: (abs(d - v), d))))
    return (code, str(id))


# --- per-game mapping tables (params-derived, immutable once built) ---

class GameMaps(object):
    def __init__(self, worlds, outbox, grant_slots):
        self.worlds = worlds            # K
        self.outbox = outbox            # {w: {shadow slot i: ap location id}}
        self.grant_slots = grant_slots  # {w: {match_key: [manifest slot, asc]}}


def maps_from_params(params):
    """Placement tuples -> GameMaps. Reserved slots are the real-coord MW
    lines world w holds for its own shadow K+w; exports are w's manifest
    lines with shadow finder K+w."""
    k = int(params.players)
    outbox, grants = {}, {}
    for w in range(1, k + 1):
        ob, gr = {}, {}
        for (loc, code, id, zone) in params.get_seed_data(w):
            if code != "MW":
                continue
            loc = int(loc)
            if is_mw_manifest_loc(loc):
                finder, icode, iid = id.split(",", 2)
                if int(finder) == k + w:
                    gr.setdefault(_match_key(icode, iid), []).append(-loc - 2)
            else:
                parts = id.split(",", 2)
                if len(parts) == 3 and int(parts[0]) == k + w:
                    ap_id = AP_LOC_BY_COORD.get(loc)
                    if ap_id is None:
                        log.error("APBRIDGE reserved coord %s of world %s not in datapackage", loc, w)
                        continue
                    ob[int(parts[1])] = ap_id
        for lst in gr.values():
            lst.sort()
        outbox[w], grants[w] = ob, gr
    return GameMaps(k, outbox, grants)


_maps = {}
_maps_lock = threading.Lock()


def game_maps(gid):
    """Cached GameMaps for a game (needs an active ndb context to build)."""
    gid = int(gid)
    m = _maps.get(gid)
    if m is not None:
        return m
    from models import Game
    game = Game.with_id(gid)
    if not game or not game.params:
        return None
    params = game.params.get()
    if not params or not getattr(params, "ap_mode", False):
        return None
    m = maps_from_params(params)
    with _maps_lock:
        _maps[gid] = m
    return m


# --- datastore touchpoints (active ndb context required; stubbed in tests) ---

def _shadow_slots(gid, world, maps):
    """ap location ids the shadow outbox says this world has checked."""
    key = ndb.Key("Game", int(gid), "Player", "%s.%s" % (int(gid), maps.worlds + world))
    shadow = key.get()
    if shadow is None or not shadow.slot_bflds:
        return set()
    bflds = shadow.slot_bflds
    return {ap_id for slot, ap_id in maps.outbox[world].items()
            if slot // 32 < len(bflds) and (bflds[slot // 32] >> (slot % 32)) & 1}


def _apply_grants(gid, world, slots):
    """Mark manifest slots on REAL player w; their tick delivers the items."""
    from models import Game, Player
    game = Game.with_id(gid)
    if not game:
        return 0
    player = game.player(world)
    newly = Player.mark_slots_txn(player.key, slots)
    if newly:
        Cache.clear_seen_checksum(player.idpts())
    return newly


@ndb.transactional(retries=5)
def _persist_recv(gid, world, count):
    link = APLink.with_id(gid)
    if link is None:
        return
    idx = list(link.recv_index or [])
    while len(idx) < world:
        idx.append(0)
    if idx[world - 1] == count:
        return
    idx[world - 1] = count
    link.recv_index = idx
    link.put()


@ndb.transactional(retries=5)
def _persist_status(gid, status, error):
    link = APLink.with_id(gid)
    if link is None:
        return
    link.status = status
    link.last_error = error
    link.put()


@ndb.transactional(retries=5)
def _persist_goal(gid, world):
    link = APLink.with_id(gid)
    if link is None or world in (link.goal_worlds or []):
        return
    link.goal_worlds = list(link.goal_worlds or []) + [world]
    link.put()


def _goal_worlds(gid):
    link = APLink.with_id(gid)
    return list(link.goal_worlds or []) if link else []


def _at_world(values, world, value):
    """`values` with 1-based index `world` set to `value`, zero-padded to fit
    (a link made before this field existed starts out empty)."""
    out = list(values or [])
    while len(out) < world:
        out.append(0)
    out[world - 1] = value
    return out


@ndb.transactional(retries=5)
def _persist_name_counts(gid, world, total, resolved):
    link = APLink.with_id(gid)
    if link is None:
        return
    totals = _at_world(link.name_totals, world, total)
    counts = _at_world(link.name_counts, world, resolved)
    if (list(link.name_totals or []), list(link.name_counts or [])) == (totals, counts):
        return
    link.name_totals, link.name_counts = totals, counts
    link.put()


def _persist_names(gid, world, total, names):
    """Store one world's scouted names + the counters ap/status reports.
    Two entity groups, so no single transaction covers both -- display data,
    a torn write just under- or over-reports for one poll."""
    APNames.store(gid, world, names)
    _persist_name_counts(gid, world, total, len(names))


# --- wire helpers ---

def _decode(frame):
    if isinstance(frame, bytes):
        frame = frame.decode("utf-8", "replace")
    msgs = json.loads(frame)
    return msgs if isinstance(msgs, list) else [msgs]


def _send(sock, msgs):
    sock.send(json.dumps(msgs))


# --- datapackage cache (process-wide, keyed by AP's own checksum) ---

_dp_cache = {}   # (game, checksum) -> {item id: item name}
_dp_lock = threading.Lock()


def _dp_get(game, checksum):
    with _dp_lock:
        return _dp_cache.get((game, checksum or ""))


def _dp_put(game, checksum, item_name_to_id):
    """AP ships name->id; we resolve the other way. Checksum-keyed, so a
    regenerated room invalidates itself and reconnects never refetch."""
    table = {}
    for name, item_id in (item_name_to_id or {}).items():
        try:
            table[int(item_id)] = name
        except (TypeError, ValueError):
            continue
    with _dp_lock:
        _dp_cache[(game, checksum or "")] = table
    return table


def _preflight(host, port):
    """simple_websocket has no connect timeout, so reach the port ourselves."""
    try:
        socket.create_connection((host, port), timeout=CONNECT_TIMEOUT).close()
    except OSError as e:
        raise OSError("can't reach %s:%s from orirando (%s)" % (host, port, e))


def _open_socket(host, port, scheme_hint=None):
    """wss first (archipelago.gg), ws fallback (local ArchipelagoServer);
    a known-good scheme from the last connection goes first."""
    _preflight(host, port)
    schemes = [scheme_hint] if scheme_hint else []
    schemes += [s for s in ("wss", "ws") if s not in schemes]
    last_err = None
    for scheme in schemes:
        try:
            return WsClient.connect("%s://%s:%s/" % (scheme, host, port)), scheme
        except Exception as e:
            last_err = e
    raise last_err


# --- one authenticated connection for one world ---

class _nullctx(object):
    def __enter__(self):
        return None

    def __exit__(self, *a):
        return False


class ApSession(object):
    """Protocol logic, transport- and datastore-agnostic for tests: sock
    needs send(str) / receive(timeout) -> frame|None, ctx is a context-manager
    factory wrapped around every datastore touchpoint."""

    def __init__(self, gid, world, maps, slot_name, password,
                 stop_event=None, goal_event=None, ctx=None, host=None, port=None):
        self.gid, self.world, self.maps = int(gid), int(world), maps
        self.slot_name = slot_name
        self.password = password
        self.host, self.port = host, port  # room this session connected to
        self.stop_event = stop_event
        self.goal_event = goal_event
        self.ctx = ctx or _nullctx
        self.checked = set()   # room-acknowledged + optimistically sent
        self.fill = {}         # match_key -> next cursor into grant_slots
        self.recv_count = 0    # AP's ReceivedItems index contract
        self.authed = False
        self.goal_sent = False
        # scouting (display names; see the module docstring)
        self.room_checksums = {}  # RoomInfo: game -> datapackage checksum
        self.slot_games = {}      # Connected slot_info: ap slot -> game name
        self.slot_players = {}    # ap slot -> player display name
        self.our_locations = set()  # every location the room says is ours
        self.scout_total = 0      # how many we asked about
        self.scouted = {}         # ap location id -> (item id, owner slot)
        self.dp_pending = set()   # games requested, answer outstanding
        self.named = None         # shadow slot -> display name, as persisted

    def _stopped(self):
        return self.stop_event is not None and self.stop_event.is_set()

    def connect_msg(self):
        return {"cmd": "Connect", "password": self.password, "game": AP_GAME_NAME,
                "name": self.slot_name, "uuid": "orirando-%s-%s" % (self.gid, self.world),
                "version": AP_VERSION, "items_handling": ITEMS_HANDLING,
                "tags": [], "slot_data": False}

    def run(self, sock):
        self._handshake(sock)
        next_poll = monotonic() + POLL_SECS
        next_link = monotonic() + LINK_RECHECK_SECS
        while not self._stopped():
            frame = sock.receive(timeout=RECV_TIMEOUT)
            if frame is not None:
                for msg in _decode(frame):
                    self._dispatch(msg, sock)
            now = monotonic()
            if now >= next_poll:
                self._poll_outbox(sock)
                next_poll = now + POLL_SECS
            if self.goal_event is not None and self.goal_event.is_set():
                self._send_goal(sock)
            if now >= next_link:
                next_link = now + LINK_RECHECK_SECS
                if not self._recheck_link(sock):
                    return

    def _handshake(self, sock):
        deadline = monotonic() + HANDSHAKE_TIMEOUT
        while True:
            msgs = self._recv_deadline(sock, deadline, "RoomInfo")
            room = next((m for m in msgs if m.get("cmd") == "RoomInfo"), None)
            if room is not None:
                sums = room.get("datapackage_checksums")
                self.room_checksums = dict(sums) if isinstance(sums, dict) else {}
                break
        _send(sock, [self.connect_msg()])
        while True:
            msgs = self._recv_deadline(sock, deadline, "Connected")
            for i, msg in enumerate(msgs):
                cmd = msg.get("cmd")
                if cmd == "ConnectionRefused":
                    raise ApRefused(",".join(msg.get("errors") or ["unknown"]))
                if cmd == "Connected":
                    self._on_connected(msg)
                    # the auto-resent ReceivedItems can share this frame
                    for later in msgs[i + 1:]:
                        self._dispatch(later, sock)
                    self._reconcile(sock)
                    return

    def _recv_deadline(self, sock, deadline, waiting_for):
        while True:
            if self._stopped() or monotonic() > deadline:
                raise ConnectionError("timed out waiting for %s" % waiting_for)
            frame = sock.receive(timeout=RECV_TIMEOUT)
            if frame is not None:
                return _decode(frame)

    def _on_connected(self, msg):
        self.authed = True
        self.checked = set(msg.get("checked_locations") or [])
        missing = msg.get("missing_locations") or []
        # authoritative list of THIS slot's locations: scouting anything else
        # is a KeyError inside the room's LocationScouts handler
        self.our_locations = self.checked | set(missing)
        self.fill = {}
        self.recv_count = 0
        self.scouted, self.dp_pending, self.named, self.scout_total = {}, set(), None, 0
        self._safe("slot_info", self._read_slot_info, msg)
        log.info("APBRIDGE connected gid=%s world=%s slot=%r checked=%s missing=%s",
                 self.gid, self.world, self.slot_name, len(self.checked), len(missing))
        with self.ctx():
            _persist_status(self.gid, "connected", None)

    def _safe(self, what, fn, *args):
        """Names are cosmetic; room data that doesn't parse must never take
        the session -- and with it item delivery -- down. Transport failures
        still propagate: those belong to the reconnect loop."""
        try:
            return fn(*args)
        except (ConnectionClosed, ConnectionError, OSError):
            raise
        except Exception:
            log.exception("APBRIDGE %s failed gid=%s world=%s", what, self.gid, self.world)

    def _read_slot_info(self, msg):
        """Connected.slot_info gives every slot's game (which datapackage an
        item id belongs to); .players gives the display names, preferring the
        alias the room shows over the raw slot name."""
        self.slot_games, self.slot_players = {}, {}
        for slot, info in (msg.get("slot_info") or {}).items():
            if not isinstance(info, dict):
                continue
            try:
                slot = int(slot)   # json object keys are strings
            except (TypeError, ValueError):
                continue
            self.slot_games[slot] = info.get("game")
            self.slot_players[slot] = info.get("name")
        for p in msg.get("players") or []:
            if not isinstance(p, dict):
                continue
            try:
                slot = int(p.get("slot"))
            except (TypeError, ValueError):
                continue
            self.slot_players[slot] = p.get("alias") or p.get("name") or self.slot_players.get(slot)

    def _reconcile(self, sock):
        self._poll_outbox(sock)
        with self.ctx():
            goals = _goal_worlds(self.gid)
        if self.world in goals:
            self._send_goal(sock)
        self._safe("scout", self._scout, sock)

    def _dispatch(self, msg, sock):
        cmd = msg.get("cmd")
        if cmd == "ReceivedItems":
            self._on_received_items(msg, sock)
        elif cmd == "RoomUpdate":
            locs = msg.get("checked_locations")
            if locs:
                self.checked.update(locs)
        elif cmd == "LocationInfo":
            self._safe("LocationInfo", self._on_location_info, msg, sock)
        elif cmd == "DataPackage":
            self._safe("DataPackage", self._on_data_package, msg)
        # PrintJSON and friends: ignored

    # --- display names ---

    def _scout(self, sock):
        """Ask the room what is actually in our reserved locations.
        create_as_hint 0: information only, no room-visible hints."""
        targets = sorted(set(self.maps.outbox[self.world].values()) & self.our_locations)
        self.scout_total = len(targets)
        if not targets:
            return
        for i in range(0, len(targets), SCOUT_CHUNK):
            _send(sock, [{"cmd": "LocationScouts",
                          "locations": targets[i:i + SCOUT_CHUNK],
                          "create_as_hint": 0}])

    def _on_location_info(self, msg, sock):
        for entry in msg.get("locations") or []:
            try:
                loc, item, owner = (int(entry["location"]), int(entry["item"]),
                                    int(entry["player"]))
            except (KeyError, TypeError, ValueError):
                continue
            self.scouted[loc] = (item, owner)
        self._fetch_datapackages(sock)
        self._resolve_names()

    def _fetch_datapackages(self, sock):
        """An item id only means something in the OWNING slot's game, so pull
        exactly those games we still lack (never the whole room's package)."""
        want = set()
        for _, owner in self.scouted.values():
            game = self.slot_games.get(owner)
            if (game and game not in self.dp_pending
                    and _dp_get(game, self.room_checksums.get(game)) is None):
                want.add(game)
        if not want:
            return
        self.dp_pending |= want
        _send(sock, [{"cmd": "GetDataPackage", "games": sorted(want)}])

    def _on_data_package(self, msg):
        games = ((msg.get("data") or {}).get("games") or {})
        for game, data in games.items():
            checksum = (data or {}).get("checksum") or self.room_checksums.get(game)
            _dp_put(game, checksum, (data or {}).get("item_name_to_id"))
        self.dp_pending -= set(games)
        self._resolve_names()

    def _dp_for(self, owner):
        game = self.slot_games.get(owner)
        return _dp_get(game, self.room_checksums.get(game)) or {}

    def _resolve_names(self):
        """Scouted (item, owner) + datapackages -> {shadow slot: label}.
        Partial by design: a game we never got a package for simply keeps its
        placeholders."""
        slot_of = {ap_id: slot for slot, ap_id in self.maps.outbox[self.world].items()}
        names = {}
        for loc, (item, owner) in self.scouted.items():
            slot = slot_of.get(loc)
            if slot is None:
                continue
            label = ap_display_name(self._dp_for(owner).get(item), self.slot_players.get(owner))
            if label:
                names[slot] = label
        if not names and self.dp_pending:
            # answers still outstanding (or the room ignored GetDataPackage):
            # never publish a blank over a previous connection's good names
            return
        if names == self.named:
            return
        self.named = names
        with self.ctx():
            _persist_names(self.gid, self.world, self.scout_total, names)
        log.info("APBRIDGE names gid=%s world=%s resolved=%s of %s",
                 self.gid, self.world, len(names), self.scout_total)

    def _on_received_items(self, msg, sock):
        index, items = int(msg.get("index", 0)), msg.get("items") or []
        if index == 0:
            # full resend: rebuild the deterministic fill from scratch
            self.fill = {}
            self.recv_count = 0
        elif index != self.recv_count:
            log.warning("APBRIDGE recv index mismatch gid=%s world=%s got=%s want=%s, Syncing",
                        self.gid, self.world, index, self.recv_count)
            _send(sock, [{"cmd": "Sync"}])
            return
        slots = []
        for item in items:
            key = ITEM_KEY_BY_AP_ID.get(item.get("item"))
            lst = self.maps.grant_slots[self.world].get(key, []) if key else []
            cur = self.fill.get(key, 0)
            if key is None or cur >= len(lst):
                log.error("APBRIDGE no free slot for AP item %s gid=%s world=%s",
                          item.get("item"), self.gid, self.world)
                continue
            self.fill[key] = cur + 1
            slots.append(lst[cur])
        self.recv_count += len(items)
        with self.ctx():
            if slots:
                _apply_grants(self.gid, self.world, slots)
            _persist_recv(self.gid, self.world, self.recv_count)

    def _poll_outbox(self, sock):
        with self.ctx():
            current = _shadow_slots(self.gid, self.world, self.maps)
        pending = current - self.checked
        if pending:
            _send(sock, [{"cmd": "LocationChecks", "locations": sorted(pending)}])
            # optimistic: a lost send kills the socket, and the next
            # connect re-seeds checked from the room's own list
            self.checked |= pending

    def _send_goal(self, sock):
        if self.goal_sent:
            return
        _send(sock, [{"cmd": "StatusUpdate", "status": CLIENT_GOAL}])
        self.goal_sent = True
        log.info("APBRIDGE goal sent gid=%s world=%s", self.gid, self.world)

    def _recheck_link(self, sock):
        with self.ctx():
            link = APLink.with_id(self.gid)
        if link is None or not link.enabled:
            log.info("APBRIDGE link disabled gid=%s world=%s, stopping", self.gid, self.world)
            return False
        if (link.host, link.port, link.password) != (self.host, self.port, self.password):
            # room retargeted via ap/connect: end this session so the
            # reconnect loop re-reads the link and joins the new room
            log.info("APBRIDGE room changed gid=%s world=%s, cycling", self.gid, self.world)
            return False
        if self.world in (link.goal_worlds or []):
            self._send_goal(sock)
        return True


# --- bridge threads + lazy-start registry ---

_bridges = {}      # (gid, world) -> _Bridge
_reg_lock = threading.Lock()
_heal_memo = {}    # gid -> (expiry, enabled, worlds)


class _Bridge(object):
    def __init__(self, gid, world):
        self.gid, self.world = gid, world
        self.stop_event = threading.Event()
        self.goal_event = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True,
                                       name="ap-bridge-%s.%s" % (gid, world))

    def alive(self):
        return self.thread.is_alive()

    def _run(self):
        gid, world = self.gid, self.world
        backoff, scheme = BACKOFF_MIN, None
        try:
            from models import client as ndb_client
            if ndb_client is None:
                log.error("APBRIDGE no ndb client, thread exiting gid=%s world=%s", gid, world)
                return
            while not self.stop_event.is_set():
                try:
                    with ndb_client.context():
                        link = APLink.with_id(gid)
                        if link is None or not link.enabled:
                            return
                        host, port, password = link.host, link.port, link.password
                        names = list(link.slot_names)
                        maps = game_maps(gid)
                    slot_name = names[world - 1] if world <= len(names) else ap_slot_name(world)
                    if maps is None:
                        with ndb_client.context():
                            _persist_status(gid, "error", "game %s is missing or not AP-mode" % gid)
                        return
                except Exception:
                    log.exception("APBRIDGE link read failed gid=%s world=%s", gid, world)
                    if self.stop_event.wait(backoff):
                        return
                    backoff = min(backoff * 2, BACKOFF_MAX)
                    continue
                session = ApSession(gid, world, maps, slot_name, password,
                                    stop_event=self.stop_event, goal_event=self.goal_event,
                                    ctx=ndb_client.context, host=host, port=port)
                sock = None
                try:
                    sock, scheme = _open_socket(host, port, scheme)
                    log.info("APBRIDGE socket up gid=%s world=%s %s://%s:%s", gid, world, scheme, host, port)
                    session.run(sock)
                    return  # clean stop: disabled link or stop_event
                except ApRefused as e:
                    log.warning("APBRIDGE refused gid=%s world=%s: %s", gid, world, e)
                    with ndb_client.context():
                        _persist_status(gid, "refused", "world %s: %s" % (world, e))
                    backoff = BACKOFF_MAX  # a bad slot/password won't fix itself
                except (ConnectionClosed, ConnectionError, OSError) as e:
                    log.warning("APBRIDGE connection lost gid=%s world=%s: %s", gid, world, e)
                    if not self.stop_event.is_set():  # don't clobber the route's 'disconnected'
                        with ndb_client.context():
                            _persist_status(gid, "reconnecting", "world %s: %s" % (world, e))
                except Exception as e:
                    log.exception("APBRIDGE session failed gid=%s world=%s", gid, world)
                    if not self.stop_event.is_set():
                        with ndb_client.context():
                            _persist_status(gid, "error", "world %s: %s" % (world, e))
                finally:
                    if sock is not None:
                        try:
                            sock.close()
                        except Exception:
                            pass
                if session.authed:
                    backoff = BACKOFF_MIN  # the room was reachable; retry fast
                if self.stop_event.wait(backoff):
                    return
                backoff = min(backoff * 2, BACKOFF_MAX)
        except Exception:
            log.exception("APBRIDGE thread crashed gid=%s world=%s", gid, world)
        finally:
            with _reg_lock:
                if _bridges.get((gid, world)) is self:
                    del _bridges[(gid, world)]
            log.info("APBRIDGE thread exit gid=%s world=%s", gid, world)


def _alive(gid, world):
    with _reg_lock:
        b = _bridges.get((gid, world))
    return b is not None and b.alive()


def ensure(game_id, link=None):
    """Start any missing/dead bridge threads for an AP-enabled game. Needs an
    active ndb context (request path only). Never raises; returns count started."""
    if not ARCHIPELAGO:
        return 0
    started = 0
    try:
        gid = int(game_id)
        link = link or APLink.with_id(gid)
        enabled = bool(link and link.enabled)
        worlds = len(link.slot_names) if link else 0
        _heal_memo[gid] = (monotonic() + HEAL_TTL, enabled, worlds)
        if not enabled:
            return 0
        for w in range(1, worlds + 1):
            with _reg_lock:
                # start under the lock: a concurrent ensure() must see the
                # freshly-registered bridge as alive, not double-spawn it
                if _bridges.get((gid, w)) is not None and _bridges[(gid, w)].alive():
                    continue
                b = _Bridge(gid, w)
                _bridges[(gid, w)] = b
                b.thread.start()
            started += 1
            log.info("APBRIDGE thread start gid=%s world=%s", gid, w)
    except Exception:
        log.exception("ap_bridge: ensure failed for %s", game_id)
    return started


def heal(game_id):
    """Request-path self-heal hook (ws.py pusher pattern): memoized so the
    steady-state cost for every game is one dict lookup; expired or
    dead-thread states fall through to ensure(). Never raises."""
    if not ARCHIPELAGO:
        return
    try:
        gid = int(game_id)
        expiry, enabled, worlds = _heal_memo.get(gid, (0.0, False, 0))
        if monotonic() < expiry:
            if not enabled:
                return
            if all(_alive(gid, w) for w in range(1, worlds + 1)):
                return
        ensure(gid)
    except Exception:
        log.exception("ap_bridge: heal failed for %s", game_id)


def stop(game_id):
    """Signal the game's bridge threads to exit (ap/disconnect). The threads
    unwind on their next timeout tick; the link row is the durable state."""
    try:
        gid = int(game_id)
        _heal_memo.pop(gid, None)
        with _reg_lock:
            targets = [b for (g, _), b in _bridges.items() if g == gid]
        for b in targets:
            b.stop_event.set()
    except Exception:
        log.exception("ap_bridge: stop failed for %s", game_id)


def notify_goal(game_id, player_id):
    """World completed (netcode complete path): record it durably on APLink
    and wake the world's session to send StatusUpdate{CLIENT_GOAL}. Needs an
    active ndb context. Never raises (the credits ping must not break)."""
    if not ARCHIPELAGO:
        return
    try:
        gid, world = int(game_id), int(player_id)
        link = APLink.with_id(gid)
        if link is None or world < 1 or world > len(link.slot_names):
            return
        _persist_goal(gid, world)
        with _reg_lock:
            b = _bridges.get((gid, world))
        if b is not None:
            b.goal_event.set()
        ensure(gid, link=link)
    except Exception:
        log.exception("ap_bridge: notify_goal failed for %s.%s", game_id, player_id)
