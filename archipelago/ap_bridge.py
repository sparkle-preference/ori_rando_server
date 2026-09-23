"""Archipelago room bridge: one outbound websocket per (game, world).

World w joins the room as its slot. Shadow player K+w's slot bits go out as
LocationChecks; ReceivedItems fill w's manifest slots, a self-item on the slot
field 6 promised and everything else on the lowest free unpromised slot.
Fills are idempotent, so a full replay is safe.

Lazy-start only: gunicorn --preload kills import-time threads, so threads
start from ap/connect and heal(). Wire shapes follow AP 0.6.7 MultiServer.py.
"""
import functools
import json
import logging as log
import os
import socket
import threading
import time
from time import monotonic

from google.cloud import ndb
from simple_websocket import Client as WsClient, ConnectionClosed
from simple_websocket.errors import ConnectionError as WsConnectionError
from wsproto.events import AcceptConnection, RejectConnection, Request
from wsproto.extensions import PerMessageDeflate

from ap_models import (APHints, APLink, APNames, APScout, ap_slot_name,
                       sanitize_display_name, wire_safe_name,
                       HINT_DEFERRED, HINT_OFFERED, HINT_PENDING,
                       HINT_REQUESTED, HINT_RESOLVED,
                       ITEM_NAME_MAX, PLAYER_NAME_MAX)
from cache import Cache
from util import ARCHIPELAGO, is_mw_manifest_loc

AP_GAME_NAME = "Ori DE Rando"
AP_VERSION = {"class": "Version", "major": 0, "minor": 6, "build": 7}
ITEMS_HANDLING = 0b011
CLIENT_GOAL = 30
SCOUT_CHUNK = 100        # locations per LocationScouts message
# mirrors archipelago.convert without importing it; test.ap_bridge_test pins them
EX_DENOMS = (50, 100, 200)
EX_EXACT_CAP = 600

POLL_SECS = 2.0          # shadow-outbox poll cadence
RECV_TIMEOUT = 1.0
PROMISES_TIMEOUT = 90.0  # scout never settled: degrade to arrival-order fills
# a collect+release burst is K+1 ReceivedItems at once: one grant txn for all
COALESCE_SECS = 0.3
SIGNAL_MAX = 400         # chars of apfrom payload per tick
LINK_RECHECK_SECS = 15.0  # re-read APLink (disable/goal from other processes)
HANDSHAKE_TIMEOUT = 20.0
CONNECT_TIMEOUT = 10.0   # the OS SYN ladder is ~4 min
HEAL_TTL = 45.0          # request-path memo: non-AP games pay a dict lookup
BACKOFF_MIN, BACKOFF_MAX = 1.0, 60.0
# no ticks this long: threads exit as "idle"; only tick/complete or connect restarts them
AP_IDLE_SECS = 3 * 3600
IDLE_CHECK_SECS = 600.0   # healthy-session staleness check cadence
IDLE_MEMO_TTL = 450.0     # passive heals re-read an idle link this often

# --- DeathLink (see "death link" below) ---
DEATHLINK_TAG = "DeathLink"
DEATHLINK_ECHO_KEEP = 8   # recent send times remembered for echo suppression
# min gap between outgoing deaths; extras are dropped, not queued
DEATHLINK_OUT_COOLDOWN = 15.0

# --- progressive hints (see "hint purchases" below) ---
HINT_QUEUE_MAX = 32      # slots a client may have outstanding at once
HINT_RETRY_SECS = 30.0   # per-slot rate limit on reconsidering a request
HINT_ACK_SECS = 20.0     # !hint said, no Hint and no CommandResult back
HINT_CLAIM_TTL = 900.0   # a PENDING claim this old is a crashed purchase
HINT_POLL_SECS = 5.0     # re-read the row while anything is for sale
HINT_LOC_MAX = 30        # chars of a foreign game's location name
HINT_TEXT_MAX = 52       # chars of one answer (clue lines pack three)
FOREIGN_HINT_TEXT = "Archipelago"  # all we can say when the room named no place
HINT_NOTICE_SECS = 600.0  # per-world floor between "can't afford" messages
HINT_SERVICE_SECS = 1.0  # how often a session revisits its wanted set
SCOUT_ROW_TTL = 60.0     # re-read the K worlds' scout rows this often
# the only purchasable reveals: nothing outside this set has a buy path
HINTABLE_KEYS = frozenset(
    [("EV", "0"), ("EV", "2"), ("EV", "4"),   # Water Vein / Gumon Seal / Sunstone
     ("SK", "4"), ("SK", "51")]               # Stomp / Grenade (Forlorn escape)
    + [("RB", str(rb)) for rb in range(300, 312)])   # keysanity zone keystones

_DATA_DIR = os.path.join(os.path.dirname(__file__), "oride_apworld", "oride", "data")
with open(os.path.join(_DATA_DIR, "items.json")) as _f:
    _ITEMS = json.load(_f)
ITEM_KEY_BY_AP_ID = {i["ap_id"]: (i["code"], i["id"]) for i in _ITEMS}
AP_ID_BY_ITEM_KEY = {(i["code"], str(i["id"])): i["ap_id"] for i in _ITEMS}
# '!hint <name>' takes the datapackage name, so this map has to be exact
ITEM_NAME_BY_AP_ID = {i["ap_id"]: i["name"] for i in _ITEMS}
del _ITEMS
with open(os.path.join(_DATA_DIR, "locations.json")) as _f:
    AP_LOC_BY_COORD = {l["coord"]: l["ap_id"] for l in json.load(_f)}


class ApRefused(Exception):
    """The room rejected our Connect (bad slot/password/version)."""


def _match_key(code, id):
    """Manifest (code, id) -> datapackage identity; mirrors convert.match_key."""
    if code == "EX":
        try:
            v = int(id)
        except (TypeError, ValueError):
            v = 0
        if not 1 <= v <= EX_EXACT_CAP:
            v = min(EX_DENOMS, key=lambda d: (abs(d - v), d))
        return ("EX", str(v))
    if code == "TW":
        return ("TW", str(id).split(",")[0])
    return (code, str(id))


# --- per-game mapping tables (params-derived, immutable once built) ---

class GameMaps(object):
    def __init__(self, worlds, outbox, grant_slots, zones=None, hint_keys=None,
                 death_link=False):
        self.worlds = worlds            # K
        # {w: {shadow slot: ap location id}} in seed-line order, the promise draw order
        self.outbox = outbox
        self.grant_slots = grant_slots  # {w: {match_key: [manifest slot, asc]}}
        self.zones = zones or {}        # {w: {shadow slot i: reserved zone}}
        self.hint_keys = hint_keys or {}  # {w: {manifest slot: buyable key}}
        self.death_link = bool(death_link)  # seed option, not a runtime toggle


def maps_from_params(params):
    """Placement tuples -> GameMaps. Reserved: w's real-coord MW lines owned by
    shadow K+w. Exports: w's manifest lines with finder K+w."""
    k = int(params.players)
    outbox, grants, zones, hints = {}, {}, {}, {}
    for w in range(1, k + 1):
        ob, gr, zo, hk = {}, {}, {}, {}
        for (loc, code, id, zone) in params.get_seed_data(w):
            if code != "MW":
                continue
            loc = int(loc)
            if is_mw_manifest_loc(loc):
                finder, _holder, icode, iid = id.split(",", 3)
                if int(finder) == k + w:
                    key = _match_key(icode, iid)
                    gr.setdefault(key, []).append(-loc - 2)
                    if key in HINTABLE_KEYS:
                        hk[-loc - 2] = key
            else:
                parts = id.split(",", 2)
                if len(parts) == 3 and int(parts[0]) == k + w:
                    ap_id = AP_LOC_BY_COORD.get(loc)
                    if ap_id is None:
                        log.error("APBRIDGE reserved coord %s of world %s not in datapackage", loc, w)
                        continue
                    ob[int(parts[1])] = ap_id
                    # the zone a hint answer names, same string annotate bakes
                    zo[int(parts[1])] = zone
        for lst in gr.values():
            lst.sort()
        outbox[w], grants[w], zones[w], hints[w] = ob, gr, zo, hk
    return GameMaps(k, outbox, grants, zones, hints,
                    death_link=bool(getattr(params, "ap_death_link", False)))


def promised_slots(maps, world, scouted, our_slot):
    """Manifest slot promised to each own-item location, the draw field 6 bakes.
    -> ({ap location id: slot}, {match_key: [unpromised slot, asc]})"""
    pools = {key: list(slots) for key, slots in maps.grant_slots.get(world, {}).items()}
    promised = {}
    for ap_id in maps.outbox.get(world, {}).values():
        hit = scouted.get(ap_id)
        if hit is None or hit[1] != our_slot:
            continue
        pool = pools.get(ITEM_KEY_BY_AP_ID.get(hit[0]))
        if pool:
            promised[ap_id] = pool.pop(0)
    return promised, pools


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


def _apfrom_signal(senders, slots):
    """'apfrom:<slot>=<sender>;...' for granted slots; "" = found it yourself.
    Capped at SIGNAL_MAX; slots past it render as from Archipelago."""
    if not senders:
        return None
    pairs, size = [], 0
    for slot in slots:
        pair = "%s=%s" % (slot, senders.get(slot, ""))
        if size + len(pair) + 1 > SIGNAL_MAX:
            break
        pairs.append(pair)
        size += len(pair) + 1
    return "apfrom:" + ";".join(pairs) if pairs else None


def _apply_grants(gid, world, slots, senders=None):
    """Mark manifest slots on REAL player w; their tick delivers the items."""
    from models import Game, Player
    game = Game.with_id(gid)
    if not game:
        return 0
    player = game.player(world)
    newly = Player.mark_slots_txn(
        player.key, slots, signal_for=lambda fresh: _apfrom_signal(senders, fresh),
        signal_latest_only=True)
    if newly:
        Cache.clear_seen_checksum(player.idpts())
    return newly


def _send_death_signal(gid, world, token, source):
    """'dl:<token>;<source>' on the world's tick, latest-only: an offline client owes one death."""
    from models import Game, Player
    game = Game.with_id(gid)
    if not game:
        return
    player = game.player(world)
    signal = "dl:%s;%s" % (token, source)
    Player.signal_latest_txn(player.key, "dl:", signal)
    Cache.clear_seen_checksum(player.idpts())


def _recv_at_least(idx, world, count):
    """New recv_index list, or None if nothing to write. Monotone: a twin
    replaying an older batch never moves the index back."""
    idx = list(idx or [])
    while len(idx) < world:
        idx.append(0)
    if idx[world - 1] >= count:
        return None
    idx[world - 1] = count
    return idx


def _busts_report(fn):
    """Bust the ap/status cache after a txn'd APLink writer returns; inside a
    txn the post-put hook fires pre-commit."""
    @functools.wraps(fn)
    def wrapper(gid, *args, **kwargs):
        try:
            return fn(gid, *args, **kwargs)
        finally:
            try:
                Cache.clear_aplink_report(gid)
            except Exception:
                pass   # TTL backstop; a cache hiccup must not fail the write
    return wrapper


@_busts_report
@ndb.transactional(retries=5)
def _persist_recv(gid, world, count):
    # a stale twin's smaller count must lose: monotone or nothing
    link = APLink.with_id(gid)
    if link is None:
        return
    idx = _recv_at_least(link.recv_index, world, count)
    if idx is not None:
        link.recv_index = idx
        link.put()


def _load_scout_row(gid, world):
    """The persisted APNames row -> ({shadow slot: APScout}, ap_slot)."""
    return APNames.load(gid, world)


def _persist_promises(gid, world, promised_by_slot):
    """The promise map onto the APNames row; annotate bakes it into field 6 verbatim."""
    APNames.store_promises(gid, world, promised_by_slot)


# undeliverable ReceivedItems entries kept on the link; past this, log-only
DROPPED_CAP = 100


def _drops_plus(drops, world, stream_i, entry):
    """drops + entry, or None if nothing to write. Keyed by stream position,
    which twins and index-0 resends re-drop identically."""
    if any(d.get("w") == world and d.get("i") == stream_i for d in drops):
        return None
    if len(drops) >= DROPPED_CAP:
        return None
    return drops + [entry]


@_busts_report
@ndb.transactional(retries=5)
def _persist_drop(gid, world, entry):
    """Durable record of an undeliverable item; True only when newly recorded."""
    link = APLink.with_id(gid)
    if link is None:
        return False
    new = _drops_plus(link.drop_list(), world, entry["i"], entry)
    if new is None:
        return False
    link.dropped = json.dumps(new)
    link.put()
    return True


def _notify_drop(gid, world, text):
    """One red line on the player's tick naming an undeliverable item."""
    from models import Game, Player
    game = Game.with_id(gid)
    if not game:
        return
    player = game.player(world)
    if Player.signal_send_txn(player.key, "msg:" + text):
        Cache.clear_seen_checksum(player.idpts())


def _drop_name(ap_item):
    """Wire-safe display name for an item addressed to an Ori world."""
    key = ITEM_KEY_BY_AP_ID.get(ap_item)
    if not key:
        return "AP item %s" % ap_item
    try:
        from pickups import Pickup
        p = Pickup.n(key[0], key[1])
        if p and p.name:
            return wire_safe_name(p.name, ITEM_NAME_MAX)
    except Exception:
        pass
    return wire_safe_name("%s %s" % key, ITEM_NAME_MAX)


# repeats of these skip the put even when the error text differs
_RETRY_STATES = ("reconnecting", "refused", "idle")

# deliberate closes (1000 normal, 1001 going away) are terminal, not retried
_ROOM_CLOSED_CODES = (1000, 1001)
ROOM_CLOSED_MSG = "The Archipelago room closed. Connect again once you have a new one."


def room_closed_for_good(exc):
    """True when the room hung up on purpose; OSErrors carry no reason and retry."""
    try:
        return int(getattr(exc, "reason", None)) in _ROOM_CLOSED_CODES
    except (TypeError, ValueError):
        return False


def _status_is_noop(link, status, error):
    """True when writing (status, error) says nothing new. Retry states dedupe
    on status alone: every put also stamps last_activity."""
    return (link.status == status
            and (status in _RETRY_STATES or link.last_error == error))


def _persist_status_impl(gid, status, error):
    """_persist_status without the transaction, for tests."""
    link = APLink.with_id(gid)
    if link is None or _status_is_noop(link, status, error):
        return
    link.status = status
    link.last_error = error
    link.put()


@_busts_report
@ndb.transactional(retries=5)
def _persist_status(gid, status, error):
    _persist_status_impl(gid, status, error)


@_busts_report
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
    """`values` with 1-based `world` set to `value`. Pads with -1: 0 means a
    world with no AP locations."""
    out = list(values or [])
    while len(out) < world:
        out.append(-1)
    out[world - 1] = value
    return out


@_busts_report
@ndb.transactional(retries=5)
def _bump_death_in(gid, world):
    """Count one DeathLink into a world -> the new total, the signal's token.
    Durable, so a restart never reissues a token the client acked."""
    link = APLink.with_id(gid)
    if link is None:
        return 0
    seen = list(link.dl_in or [])
    token = (seen[world - 1] if len(seen) >= world and seen[world - 1] > 0 else 0) + 1
    link.dl_in = _at_world(seen, world, token)
    link.put()
    return token


@_busts_report
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


def _persist_names(gid, world, total, names, ap_slot=None):
    """One world's scout results + ap/status counters. Two entity groups, no
    shared txn: a torn write misreports for one poll."""
    APNames.store(gid, world, names, ap_slot=ap_slot)
    _persist_name_counts(gid, world, total, len(names))


# --- hint purchases (durable, because a repeat costs real points) ---

def _load_hints(gid, world):
    return APHints.load(gid, world)


@ndb.transactional(retries=5)
def _claim_hint(gid, world, slot, ap_item, stale_ok=False):
    """Write-ahead PENDING compare-and-set: True means this process may ask the
    room about `slot`. stale_ok reclaims a PENDING older than HINT_CLAIM_TTL."""
    row = APHints.get_by_id(APHints.key_id(gid, world))
    entries = APHints.unpack(row)
    cur = entries.get(int(slot)) or {}
    state = cur.get("s")
    if state == HINT_RESOLVED:
        return False
    if state == HINT_PENDING and not (stale_ok and time.time() - cur.get("u", 0) > HINT_CLAIM_TTL):
        return False
    entries[int(slot)] = APHints.entry(HINT_PENDING, ap_item=ap_item,
                                      key=cur.get("k", ""))
    APHints.store(gid, world, entries, row=row)
    return True


@ndb.transactional(retries=5)
def _persist_hint(gid, world, slot, state, text="", ap_item=0, key=""):
    """Record a transition. RESOLVED is sticky."""
    row = APHints.get_by_id(APHints.key_id(gid, world))
    entries = APHints.unpack(row)
    cur = entries.get(int(slot)) or {}
    if cur.get("s") == HINT_RESOLVED and state != HINT_RESOLVED:
        return
    if cur.get("s") == state and cur.get("t", "") == text:
        return
    entries[int(slot)] = APHints.entry(state, text=text,
                                       ap_item=ap_item or cur.get("a", 0),
                                       key=key or cur.get("k", ""))
    APHints.store(gid, world, entries, row=row)


@ndb.transactional(retries=5)
def _persist_price(gid, world, points, cost):
    row = APHints.get_by_id(APHints.key_id(gid, world))
    if row is not None and row.points == points and row.cost == cost:
        return
    APHints.store(gid, world, APHints.unpack(row), row=row,
                  points=points, cost=cost)


def _apply_hint_text(gid, world, answers, keep=None):
    """Publish resolved text on the real player (tick field 8)."""
    from models import Game, Player
    game = Game.with_id(gid)
    if not game:
        return
    player = game.player(world)
    if Player.set_ap_hints_txn(player.key, answers, keep=keep):
        Cache.clear_seen_checksum(player.idpts())


def _hint_notice(gid, world, text):
    """One 'you can't afford it yet' line on the player's tick."""
    from models import Game, Player
    game = Game.with_id(gid)
    if not game:
        return
    player = game.player(world)
    if Player.signal_send_txn(player.key, "msg:" + text):
        Cache.clear_seen_checksum(player.idpts())


def _scout_rows(gid, worlds):
    return {v: APNames.load(gid, v) for v in range(1, int(worlds) + 1)}


_notice_at = {}    # (gid, world) -> monotonic of the last affordability message


class _HintBox(object):
    """Manifest slots the client asked about, request thread -> session thread.
    Bounded at HINT_QUEUE_MAX."""

    def __init__(self):
        self.lock = threading.Lock()
        self.slots = set()

    def add(self, slots):
        with self.lock:
            for slot in slots:
                if len(self.slots) >= HINT_QUEUE_MAX:
                    return
                self.slots.add(slot)

    def drain(self):
        with self.lock:
            out, self.slots = self.slots, set()
        return out


class _DeathBox(object):
    """The client's death counters, tick thread -> session thread, as a level.
    net = total - linked, so a death applied from the room never bounces back."""

    def __init__(self):
        self.lock = threading.Lock()
        self.net = None

    def set(self, total, linked):
        with self.lock:
            self.net = max(0, int(total) - int(linked))

    def read(self):
        with self.lock:
            return self.net


def _parse_deaths(raw):
    """Tick field 'dl=<total>.<linked>' -> (total, linked), or None."""
    total, _, linked = str(raw or "").partition(".")
    try:
        total, linked = int(total), int(linked or 0)
    except (TypeError, ValueError):
        return None
    if total < 0 or linked < 0:
        return None
    return total, linked


def _parse_hint_slots(raw):
    """'aph=3.17.204' -> {3, 17, 204}."""
    slots = set()
    for part in str(raw).split(".")[:HINT_QUEUE_MAX]:
        try:
            slot = int(part)
        except (TypeError, ValueError):
            continue
        if 0 <= slot <= 255:
            slots.add(slot)
    return slots


# --- wire helpers ---

def _decode(frame):
    if isinstance(frame, bytes):
        frame = frame.decode("utf-8", "replace")
    msgs = json.loads(frame)
    return msgs if isinstance(msgs, list) else [msgs]


def _send(sock, msgs):
    sock.send(json.dumps(msgs))


# --- datapackage cache (process-wide, keyed by AP's own checksum) ---

_dp_cache = {}   # (game, checksum) -> ({item id: name}, {location id: name})
_dp_lock = threading.Lock()


def _dp_get(game, checksum):
    with _dp_lock:
        return _dp_cache.get((game, checksum or ""))


def _dp_invert(name_to_id):
    table = {}
    for name, id in (name_to_id or {}).items():
        try:
            table[int(id)] = name
        except (TypeError, ValueError):
            continue
    return table


def _dp_put(game, checksum, item_name_to_id, location_name_to_id=None):
    """Cache AP's name->id tables inverted. Checksum-keyed, so reconnects
    never refetch and a regenerated room misses."""
    tables = (_dp_invert(item_name_to_id), _dp_invert(location_name_to_id))
    with _dp_lock:
        _dp_cache[(game, checksum or "")] = tables
    return tables


def _preflight(host, port):
    """simple_websocket has no connect timeout, so reach the port ourselves."""
    try:
        socket.create_connection((host, port), timeout=CONNECT_TIMEOUT).close()
    except OSError as e:
        raise OSError("can't reach %s:%s from orirando (%s)" % (host, port, e))


class DeflateClient(WsClient):
    """Upstream Client handshake plus permessage-deflate, which simple_websocket
    never offers as a client and AP warns about."""

    def handshake(self):
        out_data = self.ws.send(Request(host=self.host, target=self.path,
                                        subprotocols=self.subprotocols,
                                        extra_headers=self.extra_headeers,
                                        extensions=[PerMessageDeflate()]))
        self.sock.send(out_data)
        while True:
            in_data = self.sock.recv(self.receive_bytes)
            self.ws.receive_data(in_data)
            try:
                event = next(self.ws.events())
            except StopIteration:
                pass
            else:
                break
        if isinstance(event, RejectConnection):
            raise WsConnectionError(event.status_code)
        elif not isinstance(event, AcceptConnection):
            raise WsConnectionError(400)
        self.subprotocol = event.subprotocol
        self.connected = True


def _open_socket(host, port, scheme_hint=None):
    """wss first (archipelago.gg), ws fallback (local ArchipelagoServer);
    a known-good scheme from the last connection goes first."""
    _preflight(host, port)
    schemes = [scheme_hint] if scheme_hint else []
    schemes += [s for s in ("wss", "ws") if s not in schemes]
    last_err = None
    for scheme in schemes:
        try:
            return DeflateClient.connect("%s://%s:%s/" % (scheme, host, port)), scheme
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
    """Protocol logic for one connection. sock: send(str) / receive(timeout);
    ctx: context-manager factory wrapped around every datastore touchpoint."""

    def __init__(self, gid, world, maps, slot_name, password,
                 stop_event=None, goal_event=None, ctx=None, host=None, port=None,
                 game_slots=None, hint_box=None, death_box=None):
        self.gid, self.world, self.maps = int(gid), int(world), maps
        self.slot_name = slot_name
        self.password = password
        # every world of this orirando game, index w-1 = world w's slot name
        self.game_slots = list(game_slots or [])
        self.host, self.port = host, port  # room this session connected to
        self.stop_event = stop_event
        self.goal_event = goal_event
        self.ctx = ctx or _nullctx
        self.checked = set()   # room-acknowledged + optimistically sent
        self.fill = {}         # match_key -> next cursor into free_slots
        self.recv_count = 0    # AP's ReceivedItems index contract
        self.pending = []      # slots buffered for the next grant flush
        self.pending_from = {}  # slot -> sender display name ("" = yourself)
        self.flush_at = None   # monotonic deadline for that flush
        # None until the scout settles; ReceivedItems wait in deferred_msgs meanwhile
        self.promised = None       # {ap location id: manifest slot}
        self.free_slots = None     # {match_key: [unpromised slot, asc]}
        self.deferred_msgs = []    # ReceivedItems held until promises exist
        self.promises_deadline = None  # degraded-fill fallback timer
        self.authed = False
        self.goal_sent = False
        # scouting (display names; see the module docstring)
        self.room_checksums = {}  # RoomInfo: game -> datapackage checksum
        self.slot_games = {}      # Connected slot_info: ap slot -> game name
        self.slot_players = {}    # ap slot -> player display name
        self.slot_raw_names = {}  # ap slot -> slot_info name (never the alias)
        self.our_slot = None      # Connected: our own slot number in the room
        self.our_locations = set()  # every location the room says is ours
        self.scout_total = 0      # how many we asked about
        self.scouted = {}         # ap location id -> (item id, owner slot)
        self.dp_pending = set()   # games requested, answer outstanding
        self.named = None         # shadow slot -> display name, as persisted
        # progressive hints (see "hint purchases")
        self.hint_box = hint_box  # slots the client is asking about
        self.hint_wanted = set()  # ... as this session still owes them
        self.hint_state = {}      # durable APHints snapshot for this world
        self.room_hints = []      # every Hint the room says is ours
        self.hint_cost_pct = 0    # RoomInfo: percent of our location count
        self.hint_points = 0      # Connected/RoomUpdate: what we can spend
        self.hint_inflight = None  # (slot, ap item, sent at) -- one at a time
        self.hint_last_try = {}   # slot -> monotonic of the last consideration
        self.hint_next_service = 0.0
        self.hint_next_poll = 0.0    # ... and when to look for a buy
        self.price_written = None    # (points, cost) as last persisted
        self.hint_hydrated = False   # the room has told us what it already holds
        self.hint_asked_at = None    # ... when we asked it to
        self.scout_rows = None    # (monotonic, {world: APNames entries})
        # death link (see "death link")
        self.death_box = death_box   # the client's counters, tick-fed
        self.deaths_seen = None      # last net count we have already relayed
        self.death_times = []        # times we sent, to drop our own echo

    def _stopped(self):
        return self.stop_event is not None and self.stop_event.is_set()

    def connect_msg(self):
        return {"cmd": "Connect", "password": self.password, "game": AP_GAME_NAME,
                "name": self.slot_name, "uuid": "orirando-%s-%s" % (self.gid, self.world),
                "version": AP_VERSION, "items_handling": ITEMS_HANDLING,
                "tags": [DEATHLINK_TAG] if self.maps.death_link else [],
                "slot_data": False}

    def run(self, sock):
        self._handshake(sock)
        next_poll = monotonic() + POLL_SECS
        next_link = monotonic() + LINK_RECHECK_SECS
        next_idle = monotonic() + IDLE_CHECK_SECS
        try:
            while not self._stopped():
                self._service_promises(sock)
                timeout = RECV_TIMEOUT
                if self.flush_at is not None:
                    timeout = max(0.02, self.flush_at - monotonic())
                frame = sock.receive(timeout=timeout)
                if frame is not None:
                    for msg in _decode(frame):
                        self._dispatch(msg, sock)
                now = monotonic()
                if self.flush_at is not None and now >= self.flush_at:
                    self._flush_grants()
                if now >= next_poll:
                    self._poll_outbox(sock)
                    next_poll = now + POLL_SECS
                if now >= self.hint_next_service:
                    self.hint_next_service = now + HINT_SERVICE_SECS
                    self._safe("hints", self._service_hints, sock)
                self._service_deaths(sock)
                if self.goal_event is not None and self.goal_event.is_set():
                    self._send_goal(sock)
                if now >= next_link:
                    next_link = now + LINK_RECHECK_SECS
                    if not self._recheck_link(sock):
                        return
                if now >= next_idle:
                    next_idle = now + IDLE_CHECK_SECS
                    if _idle_stale(self.gid):
                        # live room, idle game: a clean return ends the thread
                        if not self._stopped():
                            with self.ctx():
                                _persist_idle(self.gid)
                            log.info("APBRIDGE idle gid=%s world=%s, closing session",
                                     self.gid, self.world)
                        return
        finally:
            # items already taken off the stream are granted even if the socket died
            self._flush_grants()

    def _handshake(self, sock):
        deadline = monotonic() + HANDSHAKE_TIMEOUT
        while True:
            msgs = self._recv_deadline(sock, deadline, "RoomInfo")
            room = next((m for m in msgs if m.get("cmd") == "RoomInfo"), None)
            if room is not None:
                sums = room.get("datapackage_checksums")
                self.room_checksums = dict(sums) if isinstance(sums, dict) else {}
                try:
                    self.hint_cost_pct = int(room.get("hint_cost") or 0)
                except (TypeError, ValueError):
                    self.hint_cost_pct = 0
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
                    # a world with nothing to scout can fill its connect
                    # backlog right away
                    self._service_promises(sock)
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
        try:
            self.our_slot = int(msg.get("slot"))
        except (TypeError, ValueError):
            self.our_slot = None
        self.checked = set(msg.get("checked_locations") or [])
        missing = msg.get("missing_locations") or []
        # scouting a location outside this list crashes the room's handler
        self.our_locations = self.checked | set(missing)
        self.fill = {}
        self.recv_count = 0
        self.pending, self.pending_from, self.flush_at = [], {}, None
        self.promised, self.free_slots, self.deferred_msgs = None, None, []
        self.promises_deadline = monotonic() + PROMISES_TIMEOUT
        self.scouted, self.dp_pending, self.named, self.scout_total = {}, set(), None, 0
        self.slot_raw_names = {}
        # hints are re-derived per connection from the room's own list
        self.room_hints, self.hint_inflight, self.hint_last_try = [], None, {}
        self.hint_hydrated, self.hint_asked_at = False, None
        self.scout_rows = None
        self.hint_points = self._as_int(msg.get("hint_points"), 0)
        self._safe("slot_info", self._read_slot_info, msg)
        log.info("APBRIDGE connected gid=%s world=%s slot=%r checked=%s missing=%s",
                 self.gid, self.world, self.slot_name, len(self.checked), len(missing))
        with self.ctx():
            _persist_status(self.gid, "connected", None)

    @staticmethod
    def _as_int(value, default=0):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _safe(self, what, fn, *args):
        """Run a cosmetic handler, logging its failures; transport errors still
        propagate to the reconnect loop."""
        try:
            return fn(*args)
        except (ConnectionClosed, ConnectionError, OSError):
            raise
        except Exception:
            log.exception("APBRIDGE %s failed gid=%s world=%s", what, self.gid, self.world)

    def _read_slot_info(self, msg):
        """slot_info -> each slot's game and raw name; players -> display name
        (alias first)."""
        self.slot_games, self.slot_players, self.slot_raw_names = {}, {}, {}
        for slot, info in (msg.get("slot_info") or {}).items():
            if not isinstance(info, dict):
                continue
            try:
                slot = int(slot)   # json object keys are strings
            except (TypeError, ValueError):
                continue
            self.slot_games[slot] = info.get("game")
            self.slot_players[slot] = info.get("name")
            self.slot_raw_names[slot] = info.get("name")
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
            self.hint_state = _load_hints(self.gid, self.world)
        if self.world in goals:
            self._send_goal(sock)
        self._safe("scout", self._scout, sock)
        self._safe("hint hydrate", self._hydrate_hints, sock)

    def _dispatch(self, msg, sock):
        cmd = msg.get("cmd")
        if cmd == "ReceivedItems":
            self._on_received_items(msg, sock)
        elif cmd == "RoomUpdate":
            locs = msg.get("checked_locations")
            if locs:
                self.checked.update(locs)
            if "hint_points" in msg:
                points = self._as_int(msg.get("hint_points"), self.hint_points)
                if points > self.hint_points:
                    # more points is the retry trigger for a deferred hint
                    self.hint_last_try.clear()
                self.hint_points = points
        elif cmd == "LocationInfo":
            self._safe("LocationInfo", self._on_location_info, msg, sock)
        elif cmd == "DataPackage":
            self._safe("DataPackage", self._on_data_package, msg, sock)
        elif cmd == "PrintJSON":
            self._safe("PrintJSON", self._on_print_json, msg, sock)
        elif cmd == "Bounced":
            self._safe("Bounced", self._on_bounced, msg)
        elif cmd in ("Retrieved", "SetReply"):
            self._safe("hint keys", self._on_hint_keys, msg, sock)

    # --- death link (counters via _DeathBox) ---

    def _service_deaths(self, sock):
        if self.death_box is None or not self.maps.death_link:
            return
        net = self.death_box.read()
        if net is None:
            return
        if self.deaths_seen is None or net < self.deaths_seen:
            # first report, or a smaller count (another save): re-baseline silently
            self.deaths_seen = net
            return
        if net == self.deaths_seen:
            return
        self.deaths_seen = net
        if self.death_times and time.time() - self.death_times[-1] < DEATHLINK_OUT_COOLDOWN:
            log.info("APBRIDGE deathlink absorbed gid=%s world=%s (cooldown)",
                     self.gid, self.world)
            return
        self._send_death(sock)

    def _send_death(self, sock):
        now = time.time()
        self.death_times.append(now)
        del self.death_times[:-DEATHLINK_ECHO_KEEP]
        _send(sock, [{"cmd": "Bounce", "tags": [DEATHLINK_TAG],
                      "data": {"time": now, "source": self.slot_name,
                               "cause": "%s died" % self.slot_name}}])
        log.info("APBRIDGE deathlink out gid=%s world=%s", self.gid, self.world)

    def _on_bounced(self, msg):
        if not self.maps.death_link:
            return
        if DEATHLINK_TAG not in (msg.get("tags") or []):
            return
        data = msg.get("data")
        if not isinstance(data, dict):
            return
        when = data.get("time")
        if any(when == sent for sent in self.death_times):
            return  # our own bounce, fanned back to us
        source = data.get("source") or ""
        if source == self.slot_name:
            return  # belt and braces: a resend of ours with a fresh timestamp
        # the name rides a tick signal, whose own separators it may not carry
        who = wire_safe_name(source) or "Archipelago"
        with self.ctx():
            token = _bump_death_in(self.gid, self.world)
            _send_death_signal(self.gid, self.world, token, who)
        log.info("APBRIDGE deathlink in gid=%s world=%s from=%r",
                 self.gid, self.world, source)

    # --- display names ---

    def _scout(self, sock):
        """Ask the room what sits in our reserved locations, without creating hints."""
        targets = sorted(set(self.maps.outbox[self.world].values()) & self.our_locations)
        self.scout_total = len(targets)
        if not targets:
            # nothing to name: publish the complete 0 of 0 so the UI settles
            self.named = {}
            with self.ctx():
                _persist_names(self.gid, self.world, 0, {}, ap_slot=self.our_slot)
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
        """Request datapackages for owning games we lack; item ids are per game."""
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

    def _on_data_package(self, msg, sock=None):
        games = ((msg.get("data") or {}).get("games") or {})
        for game, data in games.items():
            checksum = (data or {}).get("checksum") or self.room_checksums.get(game)
            _dp_put(game, checksum, (data or {}).get("item_name_to_id"),
                    (data or {}).get("location_name_to_id"))
        self.dp_pending -= set(games)
        self._resolve_names()
        if sock is not None and self.hint_wanted:
            # a hint waiting on a location name is exactly what just arrived
            self._service_hints(sock)

    def _dp_tables(self, owner):
        game = self.slot_games.get(owner)
        return _dp_get(game, self.room_checksums.get(game)) or ({}, {})

    def _dp_for(self, owner):
        return self._dp_tables(owner)[0]

    def _recipient(self, owner):
        """Display token for an item's recipient: 'P<world>' for a sibling world,
        else the room name."""
        world = self.sibling_world(owner)
        if world:
            return "P%s" % world
        # a name that sanitizes away would render as "Found 's Bash!"
        return wire_safe_name(self.slot_players.get(owner), PLAYER_NAME_MAX) or "Archipelago"

    def sibling_world(self, slot):
        """Room slot -> the world of this orirando game on it, or 0. Matched on
        the raw slot name, never the player-editable alias."""
        if slot == self.our_slot:
            return self.world
        if self.slot_games.get(slot) != AP_GAME_NAME:
            return 0
        raw = self.slot_raw_names.get(slot)
        for w, slot_name in enumerate(self.game_slots, start=1):
            if raw and raw == slot_name:
                return w
        return 0

    def _resolve_names(self):
        """Scouted (item, owner) + datapackages -> {shadow slot: APScout}; a game
        with no package keeps its placeholders."""
        slot_of = {ap_id: slot for slot, ap_id in self.maps.outbox[self.world].items()}
        names = {}
        for loc, (item, owner) in self.scouted.items():
            slot = slot_of.get(loc)
            if slot is None:
                continue
            item_name = sanitize_display_name(self._dp_for(owner).get(item), ITEM_NAME_MAX)
            if item_name:
                names[slot] = APScout(
                    item_name, sanitize_display_name(self.slot_players.get(owner), PLAYER_NAME_MAX),
                    self._recipient(owner), item, owner)
        if not names and self.dp_pending:
            # answers still outstanding (or the room ignored GetDataPackage):
            # never publish a blank over a previous connection's good names
            return
        if names == self.named:
            return
        self.named = names
        with self.ctx():
            _persist_names(self.gid, self.world, self.scout_total, names,
                           ap_slot=self.our_slot)
        log.info("APBRIDGE names gid=%s world=%s resolved=%s of %s",
                 self.gid, self.world, len(names), self.scout_total)

    def _sender_name(self, finder):
        """Display name for whoever found an item we received; "" = ourselves."""
        world = self.sibling_world(finder)
        if world == self.world:
            return ""
        if world:
            return "P%s" % world
        return wire_safe_name(self.slot_players.get(finder), PLAYER_NAME_MAX)

    # --- hint purchases: the client asks (tick 'aph'), the server buys. Gates in
    # order: free answers (own scouts, room hints), affordability, claim, one Say.

    def _hint_key(self):
        return "_read_hints_0_%s" % self.our_slot

    def _hydrate_hints(self, sock):
        """Ask for the room's hint list for our slot (free, silent), and
        subscribe to it: a hint the room holds is never bought again."""
        if self.our_slot is None:
            return
        self.hint_asked_at = monotonic()
        _send(sock, [{"cmd": "Get", "keys": [self._hint_key()]},
                     {"cmd": "SetNotify", "keys": [self._hint_key()]}])

    def _hint_buying_allowed(self):
        """Buy only after the room's hint list arrived, or HINT_ACK_SECS after
        asking for it."""
        if self.hint_hydrated:
            return True
        return self.hint_asked_at is not None and monotonic() - self.hint_asked_at > HINT_ACK_SECS

    def _on_hint_keys(self, msg, sock):
        """Retrieved (our Get) and SetReply (the room's push) both carry the
        whole hint list for our slot."""
        key = self._hint_key()
        if msg.get("cmd") == "SetReply":
            value = msg.get("value") if msg.get("key") == key else None
        else:
            value = (msg.get("keys") or {}).get(key)
        if not isinstance(value, list):
            return
        # only hints we receive answer a reveal
        self.room_hints = [h for h in value if isinstance(h, dict)
                           and h.get("receiving_player") == self.our_slot]
        self.hint_hydrated = True
        self.hint_last_try.clear()
        self._service_hints(sock)

    def _on_print_json(self, msg, sock):
        kind = msg.get("type")
        if kind == "Hint":
            item = msg.get("item") or {}
            hint = {"receiving_player": self._as_int(msg.get("receiving"), -1),
                    "finding_player": self._as_int(item.get("player"), -1),
                    "location": self._as_int(item.get("location"), -1),
                    "item": self._as_int(item.get("item"), -1)}
            if hint["receiving_player"] != self.our_slot:
                return          # a hint about someone else's item, not an answer
            self.room_hints.append(hint)
            if (self.hint_inflight is not None
                    and hint["item"] == self.hint_inflight[1]):
                self.hint_inflight = None      # the purchase landed
            # a new hint is exactly what the retry window was waiting out
            self.hint_last_try.clear()
            self._service_hints(sock)
        elif kind == "CommandResult" and self.hint_inflight is not None:
            text = "".join(p.get("text") or "" for p in (msg.get("data") or [])
                           if isinstance(p, dict))
            if "afford" in text.lower():
                slot, ap_item, _ = self.hint_inflight
                self.hint_inflight = None
                self._defer(slot, ap_item, self._afford_text())

    def _hint_cost(self):
        """MultiServer.get_hint_cost: a percentage of OUR location count."""
        if not self.hint_cost_pct:
            return 0
        return max(1, int(self.hint_cost_pct * 0.01 * len(self.our_locations)))

    def _afford_text(self):
        # constant text, so signal_send's dedup can match a repeat
        return "Not enough Archipelago hint points -- clues fill in as you find more checks"

    def _service_hints(self, sock):
        if self.hint_box is not None:
            self.hint_wanted |= self.hint_box.drain()
        if self.hint_inflight is not None and monotonic() - self.hint_inflight[2] > HINT_ACK_SECS:
            # unanswered: the claim stays PENDING, an ambiguous purchase is never retried
            log.warning("APBRIDGE hint unanswered gid=%s world=%s slot=%s",
                        self.gid, self.world, self.hint_inflight[0])
            self.hint_inflight = None
        if not self.authed or not self.hint_wanted:
            return
        now = monotonic()
        self._publish_price()
        if now >= self.hint_next_poll and self._anything_for_sale():
            self.hint_next_poll = now + HINT_POLL_SECS
            with self.ctx():
                fresh = _load_hints(self.gid, self.world)
            # only a site buy (OFFERED -> REQUESTED) is taken from the row
            for slot, cur in fresh.items():
                if cur.get("s") == HINT_REQUESTED and self.hint_state.get(slot, {}).get("s") == HINT_OFFERED:
                    self.hint_state[slot] = cur
                    self.hint_last_try.pop(slot, None)
        for slot in sorted(self.hint_wanted):
            last = self.hint_last_try.get(slot)
            if last is not None and now - last < HINT_RETRY_SECS:
                continue
            if self._service_hint(slot, sock):
                self.hint_last_try[slot] = now

    def _service_hint(self, slot, sock):
        """One requested slot. False means retry next second instead of after
        HINT_RETRY_SECS."""
        key = self.maps.hint_keys.get(self.world, {}).get(slot)
        ap_item = AP_ID_BY_ITEM_KEY.get(key) if key else None
        if ap_item is None:
            # not a hintable reveal: refused silently
            self.hint_wanted.discard(slot)
            return True
        entry = self.hint_state.get(slot) or {}
        if entry.get("s") == HINT_RESOLVED:
            # answered from storage; republishing repairs a player row that lost it
            self._publish(slot, entry.get("t") or "", ap_item, store=False)
            return True
        known = self._known_locations(ap_item, sock)
        if known is None:
            return False                      # a location name is still in the post
        copies = self.maps.grant_slots.get(self.world, {}).get(key, [slot])
        index = copies.index(slot) if slot in copies else 0
        if index < len(known):
            self._publish(slot, known[index], ap_item)
            return True
        if entry.get("s") == HINT_PENDING and self.hint_inflight is None:
            # claimed and no purchase in flight, yet no place for this copy:
            # settle for the generic text rather than buying again
            self._publish(slot, FOREIGN_HINT_TEXT, ap_item)
            return True
        if entry.get("s") != HINT_REQUESTED:
            # for sale until somebody presses buy on the seed page
            self._offer(slot, ap_item, key="%s|%s" % key if key else "")
            return True
        if self.hint_inflight is not None or not self._hint_buying_allowed():
            # one purchase at a time, so a CommandResult is unambiguous
            return False
        cost = self._hint_cost()
        if self.hint_points < cost:
            self._defer(slot, ap_item, self._afford_text())
            return True
        name = ITEM_NAME_BY_AP_ID.get(ap_item)
        if not name:
            self.hint_wanted.discard(slot)
            return True
        with self.ctx():
            # multi-copy never reclaims: a repeat '!hint' buys the next copy
            claimed = _claim_hint(self.gid, self.world, slot, ap_item,
                                  stale_ok=len(copies) == 1)
        if not claimed:
            return True
        self.hint_state[slot] = APHints.entry(HINT_PENDING, ap_item=ap_item)
        self.hint_inflight = (slot, ap_item, monotonic())
        _send(sock, [{"cmd": "Say", "text": "!hint " + name}])
        log.info("APBRIDGE hint buy gid=%s world=%s slot=%s item=%r cost=%s points=%s",
                 self.gid, self.world, slot, name, cost, self.hint_points)
        return True

    def _known_locations(self, ap_item, sock):
        """Free answer texts for this item: our scout rows, then room hints,
        deduped on (finder, location). None while a location name is fetched."""
        seen, out = set(), []
        for finder, loc, text in self._scouted_copies(ap_item):
            if (finder, loc) not in seen:
                seen.add((finder, loc))
                out.append(text)
        for hint in self._room_hints_for(ap_item):
            fl = (hint["finding_player"], hint["location"])
            if fl in seen:
                continue
            text = self._hint_text(hint, sock)
            if text is None:
                return None
            seen.add(fl)
            out.append(text)
        return out

    def _scouted_copies(self, ap_item):
        """(finder slot, location, text) for copies AP placed inside this
        orirando game, read from the K worlds' scout rows."""
        if self.our_slot is None:
            return []
        now = monotonic()
        if self.scout_rows is None or now - self.scout_rows[0] > SCOUT_ROW_TTL:
            with self.ctx():
                self.scout_rows = (now, _scout_rows(self.gid, self.maps.worlds))
        out = []
        for world, (entries, world_slot) in sorted(self.scout_rows[1].items()):
            for shadow_slot, scout in sorted(entries.items()):
                if scout.ap_owner != self.our_slot or scout.ap_item != ap_item:
                    continue
                zone = self.maps.zones.get(world, {}).get(shadow_slot, "")
                out.append((world_slot, self.maps.outbox.get(world, {}).get(shadow_slot, -1),
                            ("P%s %s" % (world, zone)).strip()))
        return out

    def _room_hints_for(self, ap_item):
        mine, seen = [], set()
        for hint in self.room_hints:
            fl = (hint.get("finding_player"), hint.get("location"))
            if (hint.get("receiving_player") != self.our_slot
                    or hint.get("item") != ap_item or fl in seen):
                continue
            seen.add(fl)
            mine.append(hint)
        mine.sort(key=lambda h: (h.get("finding_player", 0), h.get("location", 0)))
        return mine

    def _hint_text(self, hint, sock):
        """Room hint -> clue text: 'P3 Valley' for a sibling world, else
        '<room name> <AP location>'. None while the location name is fetched."""
        finder = self._as_int(hint.get("finding_player"), -1)
        loc = self._as_int(hint.get("location"), -1)
        world = self.sibling_world(finder)
        if world:
            slot_of = {ap_id: s for s, ap_id in self.maps.outbox.get(world, {}).items()}
            zone = self.maps.zones.get(world, {}).get(slot_of.get(loc), "")
            return ("P%s %s" % (world, zone)).strip()
        names = self._dp_tables(finder)[1]
        if not names and self.slot_games.get(finder):
            self._want_datapackage(finder, sock)
            return None
        who = wire_safe_name(self.slot_players.get(finder), PLAYER_NAME_MAX) or "Archipelago"
        where = wire_safe_name(names.get(loc), HINT_LOC_MAX)
        return ("%s %s" % (who, where)).strip()[:HINT_TEXT_MAX]

    def _want_datapackage(self, slot, sock):
        game = self.slot_games.get(slot)
        if (game and game not in self.dp_pending
                and _dp_get(game, self.room_checksums.get(game)) is None):
            self.dp_pending.add(game)
            _send(sock, [{"cmd": "GetDataPackage", "games": [game]}])

    def _publish(self, slot, text, ap_item, store=True):
        text = (text or "")[:HINT_TEXT_MAX]
        with self.ctx():
            if store:
                _persist_hint(self.gid, self.world, slot, HINT_RESOLVED,
                              text=text, ap_item=ap_item)
            # keep = still asked for; other answers may be evicted under the cap
            _apply_hint_text(self.gid, self.world, {slot: text},
                             keep=set(self.hint_wanted) | {slot})
        self.hint_state[slot] = APHints.entry(HINT_RESOLVED, text=text, ap_item=ap_item)
        self.hint_wanted.discard(slot)
        if store:
            log.info("APBRIDGE hint resolved gid=%s world=%s slot=%s -> %r",
                     self.gid, self.world, slot, text)

    def _anything_for_sale(self):
        return any((self.hint_state.get(slot) or {}).get("s") == HINT_OFFERED
                   for slot in self.hint_wanted)

    def _publish_price(self):
        """Persist (points, cost) when changed; called from the hint service only."""
        cost = self._hint_cost()
        if (self.hint_points, cost) == self.price_written:
            return
        self.price_written = (self.hint_points, cost)
        with self.ctx():
            _persist_price(self.gid, self.world, self.hint_points, cost)

    def _offer(self, slot, ap_item, key=""):
        """Mark a slot for sale on the seed page (no Say). The key lets the page
        name it without the manifest."""
        if (self.hint_state.get(slot) or {}).get("s") == HINT_OFFERED:
            return
        with self.ctx():
            _persist_hint(self.gid, self.world, slot, HINT_OFFERED,
                          ap_item=ap_item, key=key)
        self.hint_state[slot] = APHints.entry(HINT_OFFERED, ap_item=ap_item, key=key)
        log.info("APBRIDGE hint offered gid=%s world=%s slot=%s", self.gid, self.world, slot)

    def _defer(self, slot, ap_item, why):
        """Unaffordable: record DEFERRED and say nothing to the room (a doomed
        '!hint' still broadcasts); more hint_points retries it."""
        with self.ctx():
            _persist_hint(self.gid, self.world, slot, HINT_DEFERRED, ap_item=ap_item)
        self.hint_state[slot] = APHints.entry(HINT_DEFERRED, ap_item=ap_item)
        log.info("APBRIDGE hint deferred gid=%s world=%s slot=%s: %s",
                 self.gid, self.world, slot, why)
        now = monotonic()
        if now - _notice_at.get((self.gid, self.world), -HINT_NOTICE_SECS) >= HINT_NOTICE_SECS:
            _notice_at[(self.gid, self.world)] = now
            with self.ctx():
                _hint_notice(self.gid, self.world, why)

    def _on_received_items(self, msg, sock):
        if self.promised is None:
            # hold everything until promises exist: the fill is a pure function of the stream
            self.deferred_msgs.append(msg)
            return
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
        for offset, item in enumerate(items):
            slot = None
            try:
                if int(item.get("player")) == self.our_slot:
                    # own item at own location: land on the slot the client granted on contact
                    slot = self.promised.get(item.get("location"))
            except (TypeError, ValueError):
                pass
            if slot is None:
                key = ITEM_KEY_BY_AP_ID.get(item.get("item"))
                lst = self.free_slots.get(key, []) if key else []
                cur = self.fill.get(key, 0)
                if key is None or cur >= len(lst):
                    log.error("APBRIDGE no free slot for AP item %s gid=%s world=%s",
                              item.get("item"), self.gid, self.world)
                    self._note_drop(index + offset, item)
                    continue
                self.fill[key] = cur + 1
                slot = lst[cur]
            self.pending.append(slot)
            try:
                self.pending_from[slot] = self._sender_name(int(item.get("player")))
            except (TypeError, ValueError):
                self.pending_from[slot] = ""
        self.recv_count += len(items)
        if self.flush_at is None:
            self.flush_at = monotonic() + COALESCE_SECS

    def _note_drop(self, stream_i, item):
        """Record an undeliverable delivery durably and tell the player once,
        keyed by stream index."""
        ap_item = item.get("item")
        name = _drop_name(ap_item)
        try:
            sender = self._sender_name(int(item.get("player")))
        except (TypeError, ValueError):
            sender = ""
        entry = {"w": self.world, "i": int(stream_i), "a": ap_item,
                 "f": sender, "n": name, "t": int(time.time())}
        try:
            with self.ctx():
                if _persist_drop(self.gid, self.world, entry):
                    _notify_drop(self.gid, self.world,
                                 "@Undeliverable from Archipelago: %s (no free slot - console send?)@" % name)
        except Exception:
            log.exception("APBRIDGE drop bookkeeping failed gid=%s world=%s",
                          self.gid, self.world)

    def _service_promises(self, sock):
        if self.promised is None:
            self._build_promises()
        if self.promised is not None and self.deferred_msgs:
            deferred, self.deferred_msgs = self.deferred_msgs, []
            for msg in deferred:
                self._on_received_items(msg, sock)

    def _build_promises(self):
        """Build promises once every scout answered. Past the deadline, use the
        persisted scout row annotate reads; with none, degrade to arrival order."""
        if self.our_slot is None or not self.authed:
            return
        if len(self.scouted) >= self.scout_total:
            self.promised, self.free_slots = promised_slots(
                self.maps, self.world, self.scouted, self.our_slot)
            log.info("APBRIDGE promises gid=%s world=%s self_items=%s",
                     self.gid, self.world, len(self.promised))
            self._publish_promises()
            return
        if self.promises_deadline is not None and monotonic() > self.promises_deadline:
            stored = self._stored_scouts()
            if stored is not None:
                self.promised, self.free_slots = promised_slots(
                    self.maps, self.world, stored, self.our_slot)
                log.warning("APBRIDGE promises from stored scouts gid=%s world=%s "
                            "self_items=%s (live scouts %s/%s)", self.gid, self.world,
                            len(self.promised), len(self.scouted), self.scout_total)
                self._publish_promises()  # older rows may predate the blob
                return
            log.error("APBRIDGE promises timed out gid=%s world=%s; degraded fills",
                      self.gid, self.world)
            self.promised = {}
            self.free_slots = {k: list(v) for k, v in self.maps.grant_slots.get(self.world, {}).items()}

    def _publish_promises(self):
        """Persist promises keyed by shadow slot. An empty map is still
        published: 'computed none' differs from 'never built'."""
        slot_by_loc = {loc: s for s, loc in self.maps.outbox.get(self.world, {}).items()}
        blob = {slot_by_loc[loc]: mslot for loc, mslot in (self.promised or {}).items()
                if loc in slot_by_loc}
        try:
            with self.ctx():
                _persist_promises(self.gid, self.world, blob)
        except Exception:
            log.exception("APBRIDGE promise publish failed gid=%s world=%s",
                          self.gid, self.world)

    def _stored_scouts(self):
        """The persisted scout row reshaped for promised_slots, or None unless it
        is complete and was written for this connection's ap_slot."""
        try:
            with self.ctx():
                entries, ap_slot = _load_scout_row(self.gid, self.world)
        except Exception:
            log.exception("APBRIDGE stored-scout read failed gid=%s world=%s",
                          self.gid, self.world)
            return None
        outbox = self.maps.outbox.get(self.world, {})
        if ap_slot != self.our_slot or len(entries) < len(outbox):
            return None
        return {outbox[slot]: (s.ap_item, s.ap_owner)
                for slot, s in entries.items() if slot in outbox}

    def _flush_grants(self):
        """One grant transaction for everything buffered since the window opened."""
        if self.flush_at is None:
            return
        slots, senders = self.pending, self.pending_from
        self.pending, self.pending_from, self.flush_at = [], {}, None
        with self.ctx():
            if slots:
                _apply_grants(self.gid, self.world, slots, senders)
            _persist_recv(self.gid, self.world, self.recv_count)

    def _poll_outbox(self, sock):
        with self.ctx():
            current = _shadow_slots(self.gid, self.world, self.maps)
        pending = current - self.checked
        if pending:
            _send(sock, [{"cmd": "LocationChecks", "locations": sorted(pending)}])
            # optimistic: a lost send kills the socket, and Connected re-seeds checked
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
            # room retargeted: the thread exits and the next heal() dials the new room
            log.info("APBRIDGE room changed gid=%s world=%s, cycling", self.gid, self.world)
            return False
        if self.world in (link.goal_worlds or []):
            self._send_goal(sock)
        return True


# --- bridge threads + lazy-start registry ---

_bridges = {}      # (gid, world) -> _Bridge
_reg_lock = threading.Lock()
_heal_memo = {}    # gid -> (expiry, state, worlds); state: False | True | "idle"
# gid -> monotonic() of the last active heal or thread start; passive heals never stamp
_last_active = {}
_shared_stamp_at = {}   # gid -> monotonic() of the last shared-beacon write


def _idle_stale(gid):
    return monotonic() - _last_active.get(gid, 0.0) > AP_IDLE_SECS


def _stamp_active(gid):
    """Process-local activity stamp plus a throttled cross-instance beacon."""
    _last_active[gid] = monotonic()
    if monotonic() - _shared_stamp_at.get(gid, 0.0) > 60:
        _shared_stamp_at[gid] = monotonic()
        try:
            Cache.set_ap_active(gid, AP_IDLE_SECS)
        except Exception:
            pass


def _shared_active_recent(gid):
    """The cross-instance activity beacon; a miss proves nothing (cache restarts)."""
    try:
        return bool(Cache.get_ap_active(gid))
    except Exception:
        return False


def _persist_idle(gid):
    """Write "idle" unless the link is disabled, pending or disconnected, or
    another instance's beacon says the game is active."""
    link = APLink.with_id(gid)
    if link is None or not link.enabled:
        return
    if getattr(link, "status", "") in ("pending", "disconnected"):
        return
    if _shared_active_recent(gid):
        return
    _persist_status(gid, "idle", "ori side quiet; bridge paused until next tick")


class _Bridge(object):
    def __init__(self, gid, world):
        self.gid, self.world = gid, world
        # a bridge born with no activity record gets one AP_IDLE_SECS of grace
        _last_active.setdefault(gid, monotonic())
        self.stop_event = threading.Event()
        self.goal_event = threading.Event()
        self.hint_box = _HintBox()
        self.death_box = _DeathBox()
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
                if _idle_stale(gid):
                    # stop() pops the stamp, which reads as stale: don't clobber its status
                    if not self.stop_event.is_set():
                        with ndb_client.context():
                            _persist_idle(gid)
                        log.info("APBRIDGE idle gid=%s world=%s, thread exiting", gid, world)
                    return
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
                                    ctx=ndb_client.context, host=host, port=port,
                                    game_slots=names, hint_box=self.hint_box,
                                    death_box=self.death_box)
                sock = None
                try:
                    sock, scheme = _open_socket(host, port, scheme)
                    log.info("APBRIDGE socket up gid=%s world=%s %s://%s:%s", gid, world, scheme, host, port)
                    session.run(sock)
                    return  # clean return: disabled, stopped, retargeted or idle
                except ApRefused as e:
                    log.warning("APBRIDGE refused gid=%s world=%s: %s", gid, world, e)
                    with ndb_client.context():
                        _persist_status(gid, "refused", "world %s: %s" % (world, e))
                    backoff = BACKOFF_MAX  # a bad slot/password won't fix itself
                except (ConnectionClosed, ConnectionError, OSError) as e:
                    log.warning("APBRIDGE connection lost gid=%s world=%s: %s", gid, world, e)
                    if not self.stop_event.is_set():  # don't clobber the route's 'disconnected'
                        with ndb_client.context():
                            if room_closed_for_good(e):
                                # terminal: only an explicit connect reopens it
                                _persist_status(gid, "closed", ROOM_CLOSED_MSG)
                                return
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


def ensure(game_id, link=None, wake_idle=True):
    """Start missing/dead bridge threads (ndb context required); -> count started.
    Never raises. wake_idle=False skips "idle" links; "closed" is always skipped."""
    if not ARCHIPELAGO:
        return 0
    started = 0
    try:
        gid = int(game_id)
        link = link or APLink.with_id(gid)
        enabled = bool(link and link.enabled)
        worlds = len(link.slot_names) if link else 0
        # checked before idle and deaf to wake_idle: a ticking player doesn't reopen a room
        if enabled and (link.status or "") == "closed":
            _heal_memo[gid] = (monotonic() + IDLE_MEMO_TTL, "closed", worlds)
            return 0
        if enabled and not wake_idle and (link.status or "") == "idle":
            _heal_memo[gid] = (monotonic() + IDLE_MEMO_TTL, "idle", worlds)
            return 0
        _heal_memo[gid] = (monotonic() + HEAL_TTL, enabled, worlds)
        if not enabled:
            return 0
        if wake_idle:
            # passive restarts ride _Bridge.__init__'s grace stamp instead
            _stamp_active(gid)
        for w in range(1, worlds + 1):
            with _reg_lock:
                # start under the lock so a concurrent ensure() sees it alive
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


def heal(game_id, active=False):
    """Request-path self-heal, memoized to a dict lookup per game. Never raises.
    active=True (tick/complete) refreshes the idle clock and wakes idle bridges."""
    if not ARCHIPELAGO:
        return
    try:
        gid = int(game_id)
        expiry, state, worlds = _heal_memo.get(gid, (0.0, False, 0))
        if monotonic() < expiry:
            if state == "closed":
                return
            if state == "idle":
                if not active:
                    return
            elif not state:
                return
            elif all(_alive(gid, w) for w in range(1, worlds + 1)):
                if active:
                    # keep the idle clock fresh while the memo skips ensure()
                    _stamp_active(gid)
                return
        ensure(gid, wake_idle=active)
    except Exception:
        log.exception("ap_bridge: heal failed for %s", game_id)


def stop(game_id):
    """Signal the game's bridge threads to exit (ap/disconnect)."""
    try:
        gid = int(game_id)
        with _reg_lock:
            targets = [b for (g, _), b in _bridges.items() if g == gid]
        # events first: a popped stamp reads as stale to the idle check
        for b in targets:
            b.stop_event.set()
        _heal_memo.pop(gid, None)
        _last_active.pop(gid, None)
        _shared_stamp_at.pop(gid, None)
    except Exception:
        log.exception("ap_bridge: stop failed for %s", game_id)


def request_hints(game_id, player_id, raw):
    """Tick field 'aph': manifest slots the client's reveals need. A level the
    client re-sends; purchases are deduped on the session thread."""
    if not ARCHIPELAGO or not raw:
        return
    try:
        gid, world = int(game_id), int(player_id)
        with _reg_lock:
            bridge = _bridges.get((gid, world))
        if bridge is None:
            return   # no room for this world: refused for free, silently
        slots = _parse_hint_slots(raw)
        if slots:
            bridge.hint_box.add(slots)
    except Exception:
        log.exception("ap_bridge: request_hints failed for %s.%s", game_id, player_id)


def note_deaths(game_id, player_id, raw):
    """Tick field 'dl': this world's death counters, a level diffed on the
    session thread."""
    if not ARCHIPELAGO or not raw:
        return
    try:
        counts = _parse_deaths(raw)
        if counts is None:
            return
        gid, world = int(game_id), int(player_id)
        with _reg_lock:
            bridge = _bridges.get((gid, world))
        if bridge is None:
            return   # no room for this world: nothing to relay to
        bridge.death_box.set(*counts)
    except Exception:
        log.exception("ap_bridge: note_deaths failed for %s.%s", game_id, player_id)


def notify_goal(game_id, player_id):
    """World completed: record it on APLink and wake its session to send the
    goal. Needs an ndb context; never raises."""
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
