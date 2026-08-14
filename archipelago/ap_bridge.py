"""Archipelago room bridge: one outbound websocket per (game, world).

Each AP-mode world w runs a daemon thread joining the room as slot 'Ori<w>':
shadow player K+w's slot bitfield is polled for outgoing LocationChecks,
ReceivedItems fill world w's manifest slots: a self-item (our own item at
our own location) lands exactly on the slot annotate's field 6 promised the
client, everything else takes the lowest open unpromised slot for that item
(monotone and idempotent so a full replay is safe). The client grants a
self-item on contact and relies on the delivery landing where promised --
the 4.2.12 pairing; fills wait for scouting, which the promise map is
derived from. The complete path sends
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
import time
from time import monotonic

from google.cloud import ndb
from simple_websocket import Client as WsClient, ConnectionClosed
from simple_websocket.errors import ConnectionError as WsConnectionError
from wsproto.events import AcceptConnection, RejectConnection, Request
from wsproto.extensions import PerMessageDeflate

from ap_models import (APHints, APLink, APNames, APScout, ap_slot_name,
                       sanitize_display_name, wire_safe_name,
                       HINT_DEFERRED, HINT_PENDING, HINT_RESOLVED,
                       ITEM_NAME_MAX, PLAYER_NAME_MAX)
from cache import Cache
from util import ARCHIPELAGO, is_mw_manifest_loc

AP_GAME_NAME = "Ori DE Rando"
AP_VERSION = {"class": "Version", "major": 0, "minor": 6, "build": 7}
ITEMS_HANDLING = 0b011
CLIENT_GOAL = 30
SCOUT_CHUNK = 100        # locations per LocationScouts message
# hand-mirrored from archipelago.convert (this module stays import-light for
# the lazy-start rule); test.ap_bridge_test pins the two together
EX_DENOMS = (50, 100, 200)
EX_EXACT_CAP = 600

POLL_SECS = 2.0          # shadow-outbox poll cadence
RECV_TIMEOUT = 1.0
PROMISES_TIMEOUT = 90.0  # scout never settled: degrade to arrival-order fills
# a room's goal handler collects then releases, one ReceivedItems per source
# world, so K+1 messages can land microseconds apart. Buffer them into one
# grant transaction rather than one per message straddling the 1Hz tick.
COALESCE_SECS = 0.3
SIGNAL_MAX = 400         # chars of apfrom payload per tick
LINK_RECHECK_SECS = 15.0  # re-read APLink (disable/goal from other processes)
HANDSHAKE_TIMEOUT = 20.0
CONNECT_TIMEOUT = 10.0   # the OS SYN ladder is ~4 min
HEAL_TTL = 45.0          # request-path memo: non-AP games pay a dict lookup
BACKOFF_MIN, BACKOFF_MAX = 1.0, 60.0

# --- DeathLink (see "death link" below) ---
DEATHLINK_TAG = "DeathLink"
DEATHLINK_ECHO_KEEP = 8   # recent send times remembered for echo suppression
# min gap between outgoing deaths; extras are dropped, not queued (a respawn
# loop is one death to the room, not a drumbeat)
DEATHLINK_OUT_COOLDOWN = 15.0

# --- progressive hints (see "hint purchases" below) ---
HINT_QUEUE_MAX = 32      # slots a client may have outstanding at once
HINT_RETRY_SECS = 30.0   # per-slot rate limit on reconsidering a request
HINT_ACK_SECS = 20.0     # !hint said, no Hint and no CommandResult back
HINT_CLAIM_TTL = 900.0   # a PENDING claim this old is a crashed purchase
HINT_LOC_MAX = 30        # chars of a foreign game's location name
HINT_TEXT_MAX = 52       # chars of one answer (clue lines pack three)
FOREIGN_HINT_TEXT = "Archipelago"  # all we can say when the room named no place
HINT_NOTICE_SECS = 600.0  # per-world floor between "can't afford" messages
HINT_SERVICE_SECS = 1.0  # how often a session revisits its wanted set
SCOUT_ROW_TTL = 60.0     # re-read the K worlds' scout rows this often
# Only the three reveal moments may be bought. The client asks; a modified or
# buggy one still cannot spend a player's points on filler, because nothing
# outside this set has a purchase path at all.
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
    """Manifest (code, id) -> the datapackage identity AP knows it by. EX is
    exact up to the cap and rides a denomination above it; a TW warp keeps
    its coordinates in the seed and is named by its destination. Mirrors
    convert.match_key so both sides bucket identically."""
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
        # {w: {shadow slot i: ap location id}}, insertion = seed-line order,
        # which is the promise draw order (dicts hold it; nothing mutates
        # these after build)
        self.outbox = outbox
        self.grant_slots = grant_slots  # {w: {match_key: [manifest slot, asc]}}
        self.zones = zones or {}        # {w: {shadow slot i: reserved zone}}
        self.hint_keys = hint_keys or {}  # {w: {manifest slot: buyable key}}
        self.death_link = bool(death_link)  # seed option, not a runtime toggle


def maps_from_params(params):
    """Placement tuples -> GameMaps. Reserved slots are the real-coord MW
    lines world w holds for its own shadow K+w; exports are w's manifest
    lines with shadow finder K+w."""
    k = int(params.players)
    outbox, grants, zones, hints = {}, {}, {}, {}
    for w in range(1, k + 1):
        ob, gr, zo, hk = {}, {}, {}, {}
        for (loc, code, id, zone) in params.get_seed_data(w):
            if code != "MW":
                continue
            loc = int(loc)
            if is_mw_manifest_loc(loc):
                finder, icode, iid = id.split(",", 2)
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
                    # the zone an Ori hint names; the same string annotate
                    # bakes into a seed it can resolve at download time
                    zo[int(parts[1])] = zone
        for lst in gr.values():
            lst.sort()
        outbox[w], grants[w], zones[w], hints[w] = ob, gr, zo, hk
    return GameMaps(k, outbox, grants, zones, hints,
                    death_link=bool(getattr(params, "ap_death_link", False)))


def promised_slots(maps, world, scouted, our_slot):
    """The manifest slot each of this world's own-item locations is promised
    -- the same values annotate bakes into field 6, drawn the same way:
    per-item pools of manifest slots ascending, consumed in seed-line order
    by the reserved locations the room says hold our own item. Self rows key
    off our own static items table, so no room datapackage is involved.
    test.ap_bridge_test pins the two implementations together.
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
    """'apfrom:<slot>=<sender>;...' for the slots actually granted. An empty
    sender means "you found this yourself". Capped: signals ride every tick
    until the client confirms them, and a release can mark 256 slots at once
    -- past the cap the client falls back to naming Archipelago."""
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
    """'dl:<token>;<source>' on the world's tick. latest-only: a client that
    is offline while the room dies repeatedly owes exactly one death when it
    comes back, not a queue of them."""
    from models import Game, Player
    game = Game.with_id(gid)
    if not game:
        return
    player = game.player(world)
    signal = "dl:%s;%s" % (token, source)
    Player.signal_latest_txn(player.key, "dl:", signal)
    Cache.clear_seen_checksum(player.idpts())


def _recv_at_least(idx, world, count):
    """New recv_index list, or None when nothing needs writing. Monotone:
    a twin session (deploy overlap) replaying an already-applied batch must
    never move a world's index backwards. Datastore-free for the tests; the
    txn below wraps it."""
    idx = list(idx or [])
    while len(idx) < world:
        idx.append(0)
    if idx[world - 1] >= count:
        return None
    idx[world - 1] = count
    return idx


@ndb.transactional(retries=5)
def _persist_recv(gid, world, count):
    # the txn serializes writers, but a stale twin's smaller count still won
    # the last write before the >= guard: monotone or nothing
    link = APLink.with_id(gid)
    if link is None:
        return
    idx = _recv_at_least(link.recv_index, world, count)
    if idx is not None:
        link.recv_index = idx
        link.put()


def _load_scout_row(gid, world):
    """The persisted APNames row -> ({shadow slot: APScout}, ap_slot).
    Module-level so the tests reroute it like every other touchpoint."""
    return APNames.load(gid, world)


def _persist_promises(gid, world, promised_by_slot):
    """The build's promise map onto the APNames row. Annotate bakes this
    blob into field 6 verbatim, so the self-item draw has one home."""
    APNames.store_promises(gid, world, promised_by_slot)


# undeliverable ReceivedItems entries kept on the link; past this, log-only
DROPPED_CAP = 100


def _drops_plus(drops, world, stream_i, entry):
    """drops + entry, or None when nothing needs writing: the fill is a pure
    function of the stream, so twin sessions and every index-0 resend re-drop
    the same stream position. Datastore-free; the txn below wraps it."""
    if any(d.get("w") == world and d.get("i") == stream_i for d in drops):
        return None
    if len(drops) >= DROPPED_CAP:
        return None
    return drops + [entry]


@ndb.transactional(retries=5)
def _persist_drop(gid, world, entry):
    """Durable record of an undeliverable item. True when newly recorded --
    only the first record gets to tell the player."""
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
    """One red line on the player's tick: a silently vanishing console rescue
    cost 135658 its remediation (nine keystones, only ERROR lines to show)."""
    from models import Game, Player
    game = Game.with_id(gid)
    if not game:
        return
    player = game.player(world)
    if Player.signal_send_txn(player.key, "msg:" + text):
        Cache.clear_seen_checksum(player.idpts())


def _drop_name(ap_item):
    """Display name for an item addressed to an Ori world (so: our own
    datapackage), wire-safe for a signal payload."""
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
    """`values` with 1-based `world` set to `value`. Pads with -1, not 0: a
    real 0 means a world with no AP locations, already done."""
    out = list(values or [])
    while len(out) < world:
        out.append(-1)
    out[world - 1] = value
    return out


@ndb.transactional(retries=5)
def _bump_death_in(gid, world):
    """Count one DeathLink delivered to a world; -> the new total, which the
    signal carries as its token. Durable so a bridge restart can't hand the
    client a token it already acked and dropped as seen."""
    link = APLink.with_id(gid)
    if link is None:
        return 0
    seen = list(link.dl_in or [])
    token = (seen[world - 1] if len(seen) >= world and seen[world - 1] > 0 else 0) + 1
    link.dl_in = _at_world(seen, world, token)
    link.put()
    return token


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
    """Store one world's scout results + the counters ap/status reports.
    Two entity groups, so no single transaction covers both -- display data,
    a torn write just under- or over-reports for one poll."""
    APNames.store(gid, world, names, ap_slot=ap_slot)
    _persist_name_counts(gid, world, total, len(names))


# --- hint purchases (durable, because a repeat costs real points) ---

def _load_hints(gid, world):
    return APHints.load(gid, world)


@ndb.transactional(retries=5)
def _claim_hint(gid, world, slot, ap_item, stale_ok=False):
    """Write-ahead PENDING: True means THIS process may now ask the room
    about `slot`. Everything that could buy twice -- K sessions, several
    gunicorn processes, a reconnect, a seed reload, a 1 Hz client that never
    stops asking -- loses the compare-and-set instead.

    stale_ok reclaims a PENDING older than HINT_CLAIM_TTL, and is passed only
    for single-copy items: for a multi-copy one the next '!hint' buys the
    NEXT copy, so an ambiguous outcome must never be retried blind.
    """
    row = APHints.get_by_id(APHints.key_id(gid, world))
    entries = APHints.unpack(row)
    cur = entries.get(int(slot)) or {}
    state = cur.get("s")
    if state == HINT_RESOLVED:
        return False
    if state == HINT_PENDING and not (stale_ok and time.time() - cur.get("u", 0) > HINT_CLAIM_TTL):
        return False
    entries[int(slot)] = APHints.entry(HINT_PENDING, ap_item=ap_item)
    APHints.store(gid, world, entries)
    return True


@ndb.transactional(retries=5)
def _persist_hint(gid, world, slot, state, text="", ap_item=0):
    """Record a transition. RESOLVED is sticky: a later DEFERRED (say, a
    reconnect that re-derives affordability) must not un-answer a slot."""
    row = APHints.get_by_id(APHints.key_id(gid, world))
    entries = APHints.unpack(row)
    cur = entries.get(int(slot)) or {}
    if cur.get("s") == HINT_RESOLVED and state != HINT_RESOLVED:
        return
    if cur.get("s") == state and cur.get("t", "") == text:
        return
    entries[int(slot)] = APHints.entry(state, text=text,
                                       ap_item=ap_item or cur.get("a", 0))
    APHints.store(gid, world, entries)


def _apply_hint_text(gid, world, answers, keep=None):
    """Publish resolved text on the real player: tick field 8, pushed the
    moment the checksum is busted."""
    from models import Game, Player
    game = Game.with_id(gid)
    if not game:
        return
    player = game.player(world)
    if Player.set_ap_hints_txn(player.key, answers, keep=keep):
        Cache.clear_seen_checksum(player.idpts())


def _hint_notice(gid, world, text):
    """One 'you can't afford it yet' line on the player's tick, rate limited
    per world -- a deferred hint is re-derived every reconnect."""
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
    """Manifest slots the client has asked about, handed from request threads
    to the world's session thread. Bounded: a client that asks for more than
    it could ever afford must not grow a queue."""

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
    """The client's death counters, handed from tick threads to the world's
    session thread. A LEVEL, not a queue: the tick reports totals, so a lost
    tick costs nothing and a burst of ticks costs one read.

    `total` is every death this run; `linked` is the subset the client itself
    caused applying an incoming DeathLink. total - linked is what the room
    may hear about, which is why an incoming death can never bounce back out.
    """

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
    """Tick field 'dl=<total>.<linked>' -> (total, linked), or None. Dotted
    because ',' and '|' are the tick's own separators (same as 'aph')."""
    total, _, linked = str(raw or "").partition(".")
    try:
        total, linked = int(total), int(linked or 0)
    except (TypeError, ValueError):
        return None
    if total < 0 or linked < 0:
        return None
    return total, linked


def _parse_hint_slots(raw):
    """'aph=3.17.204' -> {3, 17, 204}. Dot-separated because ',' and '|' are
    the tick's own separators."""
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
    """AP ships name->id; we resolve the other way. Locations ride along
    because a hint answers with one. Checksum-keyed, so a regenerated room
    invalidates itself and reconnects never refetch."""
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
    """simple_websocket 1.1.0 offers permessage-deflate as a server but never
    proposes it as a client, which AP warns about and plans to require. Same
    handshake as upstream plus the extension."""

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
    """Protocol logic, transport- and datastore-agnostic for tests: sock
    needs send(str) / receive(timeout) -> frame|None, ctx is a context-manager
    factory wrapped around every datastore touchpoint."""

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
        # deterministic self-item fills (see promised_slots). None until the
        # scout settles; ReceivedItems wait in deferred_msgs so the fill stays
        # a pure function of the stream
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
        finally:
            # a dropped socket must not swallow items already taken off the
            # stream: the grant is a datastore write and does not need it
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
        # authoritative list of THIS slot's locations: scouting anything else
        # is a KeyError inside the room's LocationScouts handler
        self.our_locations = self.checked | set(missing)
        self.fill = {}
        self.recv_count = 0
        self.pending, self.pending_from, self.flush_at = [], {}, None
        self.promised, self.free_slots, self.deferred_msgs = None, None, []
        self.promises_deadline = monotonic() + PROMISES_TIMEOUT
        self.scouted, self.dp_pending, self.named, self.scout_total = {}, set(), None, 0
        self.slot_raw_names = {}
        # hints are re-derived per connection: the room is the authority on
        # what has already been bought, and it tells us on the way in
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

    # --- death link ---
    # Deaths ride the tick as a counter (client save item 1590), and a death
    # the client applied FROM the room increments a second one we subtract --
    # so an incoming death can never emit an outgoing one. Rationale in
    # prior_notes/ARCHIPELAGO_NOTES.md.

    def _service_deaths(self, sock):
        if self.death_box is None or not self.maps.death_link:
            return
        net = self.death_box.read()
        if net is None:
            return
        if self.deaths_seen is None or net < self.deaths_seen:
            # first report of the run, or a smaller count: a different save
            # file or a fresh slot. Re-baseline silently -- nobody owes the
            # room deaths that happened before we were watching.
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
        """Ask the room what is actually in our reserved locations.
        create_as_hint 0: information only, no room-visible hints."""
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
        """Display token for the slot an item is going to. Another world of
        THIS orirando game gets 'P<world>', which the client already knows
        how to turn into that player's own name; anyone else gets their room
        name."""
        world = self.sibling_world(owner)
        if world:
            return "P%s" % world
        # a name that sanitizes away (unicode-only aliases are common) would
        # otherwise render as "Found 's Bash!"
        return wire_safe_name(self.slot_players.get(owner), PLAYER_NAME_MAX) or "Archipelago"

    def sibling_world(self, slot):
        """Room slot -> the world of THIS orirando game sitting on it, or 0.
        Matched on the raw slot name the link stored, never the alias: an
        alias is player-editable and any room can hold a second Ori game."""
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
        """Scouted (item, owner) + datapackages -> {shadow slot: APScout}.
        Partial by design: a game we never got a package for simply keeps its
        placeholders."""
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
        """Display name for whoever found an item we received. Empty means
        we found it ourselves, which the client renders with no suffix."""
        world = self.sibling_world(finder)
        if world == self.world:
            return ""
        if world:
            return "P%s" % world
        return wire_safe_name(self.slot_players.get(finder), PLAYER_NAME_MAX)

    # --- hint purchases ---
    #
    # Ori reveals its clues progressively: dungeon-key clues at 3/6/9 trees,
    # a keysanity door hint when you touch the door, Stomp/Grenade when the
    # Forlorn escape ends. All three conditions are CLIENT state, so the
    # client asks (tick field 'aph') and the server buys. Every gate lives
    # here, because '!hint' spends points the player can never earn back:
    # free answers first (our own scouts, then the room's existing hints),
    # then affordability, then a write-ahead claim, then exactly one Say.

    def _hint_key(self):
        return "_read_hints_0_%s" % self.our_slot

    def _hydrate_hints(self, sock):
        """The room's own hint list, free and silent: no Say, no chat line,
        no points. This is the idempotence anchor -- a hint the room already
        holds is never bought again, whoever bought it."""
        if self.our_slot is None:
            return
        self.hint_asked_at = monotonic()
        _send(sock, [{"cmd": "Get", "keys": [self._hint_key()]},
                     {"cmd": "SetNotify", "keys": [self._hint_key()]}])

    def _hint_buying_allowed(self):
        """Never buy before the room has said what it already holds -- that
        answer is free and may make the purchase unnecessary. A room that
        ignores the Get is not allowed to block hints forever."""
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
        # the room tells us about hints we FIND as well as hints we receive;
        # only the latter answer a reveal, and keeping only those bounds this
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
        # no live point count: the text has to repeat exactly, or signal_send's
        # dedup never matches and every deferral stacks another line
        return "Find more Archipelago checks to afford this hint"

    def _service_hints(self, sock):
        if self.hint_box is not None:
            self.hint_wanted |= self.hint_box.drain()
        if self.hint_inflight is not None and monotonic() - self.hint_inflight[2] > HINT_ACK_SECS:
            # said into the void. The claim stays PENDING on purpose: an
            # ambiguous purchase must never be retried blind.
            log.warning("APBRIDGE hint unanswered gid=%s world=%s slot=%s",
                        self.gid, self.world, self.hint_inflight[0])
            self.hint_inflight = None
        if not self.authed or not self.hint_wanted:
            return
        now = monotonic()
        for slot in sorted(self.hint_wanted):
            last = self.hint_last_try.get(slot)
            if last is not None and now - last < HINT_RETRY_SECS:
                continue
            if self._service_hint(slot, sock):
                self.hint_last_try[slot] = now

    def _service_hint(self, slot, sock):
        """One requested slot. False means 'ask me again next second', which
        is only ever the wait for a datapackage."""
        key = self.maps.hint_keys.get(self.world, {}).get(slot)
        ap_item = AP_ID_BY_ITEM_KEY.get(key) if key else None
        if ap_item is None:
            # not one of the three reveals (or not an AP game at all):
            # refused for free, without a word to the room
            self.hint_wanted.discard(slot)
            return True
        entry = self.hint_state.get(slot) or {}
        if entry.get("s") == HINT_RESOLVED:
            # a repeat request is answered from storage; re-publishing costs
            # nothing and repairs a player row that lost its copy
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
            # bought, answered, and the room still named fewer places than
            # this item has copies: it has no more to give, so settle for
            # what we can say rather than buying the same answer again
            self._publish(slot, FOREIGN_HINT_TEXT, ap_item)
            return True
        if self.hint_inflight is not None or not self._hint_buying_allowed():
            # one purchase at a time, so a CommandResult is unambiguous; come
            # back next second rather than sitting out the retry window
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
            # a single-copy item may re-buy a claim old enough to be a crash;
            # for a multi-copy one the next '!hint' buys the NEXT copy, so it
            # never may
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
        """Where every copy of this item is, as far as we can tell for free:
        our own scout rows first, then the room's hint list. Deduped on
        (finding slot, location) -- one copy can appear in both. None means
        a foreign location name is still being fetched."""
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
        """Copies Archipelago left inside this orirando game. Each world
        scouts its own reserved locations, so the K rows together place them
        without asking the room anything -- which is also the whole answer
        when the key never left Ori."""
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
        """One room hint -> the string an Ori clue prints. A sibling world
        renders exactly like a baked clue ('P3 Valley'); anyone else gets
        their room name and the AP location name."""
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
            # keep = what the client still asks about, so answers it stopped
            # reading are evicted before the cap can refuse a fresh one
            _apply_hint_text(self.gid, self.world, {slot: text},
                             keep=set(self.hint_wanted) | {slot})
        self.hint_state[slot] = APHints.entry(HINT_RESOLVED, text=text, ap_item=ap_item)
        self.hint_wanted.discard(slot)
        if store:
            log.info("APBRIDGE hint resolved gid=%s world=%s slot=%s -> %r",
                     self.gid, self.world, slot, text)

    def _defer(self, slot, ap_item, why):
        """Unaffordable: leave the baked placeholder alone, say nothing to
        the room (a doomed '!hint' still broadcasts what we are looking for),
        and let the next RoomUpdate's hint_points retry it."""
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
            # self-item fills need the scout-derived promise map, and the
            # fill must stay a pure function of the stream: hold everything
            # (the connect backlog included) until the map exists
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
                    # our own item at our own location: the client granted the
                    # promised slot on contact; the delivery must land there
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
        """Record an undeliverable delivery durably and tell the player once.
        The stream index is the dedup key: the fill re-derives on every
        index-0 resend, so the same overage re-drops in every session."""
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
        """Promise map, once every scout has answered (self rows need nothing
        else -- their item keys come from our own static table). Past the
        deadline, rebuild from the persisted scout row first: it is the same
        row annotate reads, so those promises agree with every gated seed
        download by construction -- 135658's twin sessions diverged exactly
        here, one healthy and one arrival-order. Only with no usable row does
        the session degrade to arrival-order fills."""
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
        """The promise map, keyed by shadow slot (the form annotate can look
        up straight off a reserved line, no datapackage involved). An empty
        map is still published: 'computed none' and 'never built' differ."""
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
        """A complete persisted scout row, reshaped for promised_slots, or
        None. Demands the row's ap_slot match this connection's (a retargeted
        room's leftover row must not seed promises) and every reserved slot
        answered -- the same completeness the download gate demands, so any
        row this accepts is one annotated seeds were built from."""
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
        """One grant transaction for everything buffered since the window
        opened, so a collect+release burst is one message in game."""
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


def request_hints(game_id, player_id, raw):
    """Tick field 'aph': the manifest slots this client's own reveals now
    need. A level, not an event -- the client re-sends until it has an
    answer, and every exactly-once concern (double purchase above all) is
    settled on the session thread against the durable record. Costs a
    non-AP game one `if`, since nothing else ever sends the field."""
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
    """Tick field 'dl': this world's death counters. Same shape as the hint
    request -- a level the client re-reports every second, read here and
    diffed on the session thread (the socket belongs to it). Costs a game
    without death link one `if`, since only a DeathLink seed sends the
    field at all."""
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
