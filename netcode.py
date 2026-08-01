"""Transport-neutral session layer for the client netcode.

Each handler is a function of (game_id, player_id, ...path args, payload) ->
(status, body). `payload` is any Mapping with .get()/`in` (the HTTP adapters in
main.py pass request.args or request.form verbatim; a websocket adapter passes
a plain dict). Bodies are the exact strings the shipped C# client parses (see
test/golden_wire_test.py); adapters must wrap them without modification —
HTTP: text_resp(body, status).

This module must stay importable without main.py (no Flask, no OIDC/logging
setup) so route-level golden tests can drive the full handler bodies.
"""
import json
import logging as log
from time import monotonic

from ap_models import APLink
from archipelago import ap_bridge
from cache import Cache
from enums import MultiplayerGameType
from models import Game, BingoGameData, bingo_lock
from pickups import Pickup
from util import all_locs, bfield_checksum, coord_correction_map, debug, netperf, seed_sync_id, version_check, ARCHIPELAGO, BINGO_V2


def _code(status):
    return status, str(status)


def found_pickup(game_id, player_id, coords, kind, id, payload):
    game = Game.with_id(game_id)
    if not game:
        return _code(412)
    remove = "remove" in payload
    zone = payload.get("zone")
    coords = int(coords)
    if coords in coord_correction_map:
        coords = coord_correction_map[coords]
    if coords not in all_locs and abs(coords) != 1:  # +1 is the client's TP-activation pseudo-coord
        log.warning("Coord mismatch error! %s not in all_locs or correction map. Sync %s.%s, pickup %s|%s" % (coords, game_id, player_id, kind, id))
    pickup = Pickup.n(kind, id)
    if not pickup:
        log.error("Couldn't build pickup %s|%s" % (kind, id))
        return _code(406)
    t0 = monotonic()
    status = game.found_pickup(player_id, pickup, coords, remove, "override" in payload, zone, [int(payload.get("s%s" % i) or 0) for i in range(8)])
    netperf("found_pickup", t0, gid=game_id, pid=player_id, coords=coords, kind=kind, status=status)
    if game.is_race:
        Cache.clear_items(game_id)
    elif pickup.code in ["AC", "KS", "HC", "EC", "SK", "EV", "TP"] or (pickup.code == "RB" and pickup.id in [17, 19, 21]):
        Cache.clear_reach(game_id, player_id)
        Cache.clear_items(game_id)
    return _code(status)


def tick(game_id, player_id, payload):
    if ARCHIPELAGO:
        # bridge self-heal rides the 1 Hz tick (memoized: a dict lookup for
        # any game without a live AP link)
        ap_bridge.heal(game_id)
    x = payload.get("x")
    y = payload.get("y")
    if Cache.get_seen_checksum((game_id, player_id)) == bfield_checksum(payload.get("seen_%s" % i, 0) for i in range(8)):
        # checksum and output caching should happen in sync, but it doesn't hurt to check
        cached_output = Cache.get_output((game_id, player_id))
        if cached_output:
            Cache.set_pos(game_id, player_id, x, y)
            return 200, cached_output
    game = Game.with_id(game_id)
    if not game:
        return _code(412)
    p = game.player(player_id)
    # slow path only: the fast path above serves cache and never sees a Player,
    # so version tracking costs nothing on the ~1 Hz steady-state tick
    if p.note_version(payload.get("version"), game_id):
        p.put()
    p.bitfield_updates(payload, game_id)
    Cache.set_pos(game_id, player_id, x, y)
    return 200, p.output(include_slots=(game.mode == MultiplayerGameType.MULTIWORLD))


def tick_output(game_id, player_id):
    """Fresh tick body for a websocket push frame — byte-identical to what
    /tick/ would return for this player, minus the client-payload processing
    (position, bitfield updates, version) only a real tick carries."""
    game = Game.with_id(game_id)
    if not game:
        return None
    p = game.player(player_id)
    return p.output(include_slots=(game.mode == MultiplayerGameType.MULTIWORLD))


# testing-only GET variant (see the route comment in main.py)
def tick_debug(game_id, player_id, xycoords, payload):
    x, _, y = xycoords.partition(",")
    game = Game.with_id(game_id)
    if not game:
        return _code(412)
    p = game.player(player_id)
    if debug():
        fake = {"have_%s" % i: (payload.get("s%s" % i) or 0) for i in range(8)}
        for i in range(8):
            fake["seen_%s" % i] = fake["have_%s" % i]
        if Cache.get_seen_checksum((game_id, player_id)) == bfield_checksum(fake.get("seen_%s" % i, 0) for i in range(8)):
            cached_output = Cache.get_output((game_id, player_id))
            if cached_output:
                log.info("got output from cache")
                return 200, cached_output
        p.bitfield_updates(fake, game_id)
        game.sanity_check()
    Cache.set_pos(game_id, player_id, x, y)
    return 200, p.output(include_slots=(game.mode == MultiplayerGameType.MULTIWORLD))


def game_complete(game_id, player_id):
    """The client's credits-roll ping (fire and forget). In multiworld this
    releases everything left in the finisher's world to its owners."""
    game = Game.with_id(game_id)
    if not game:
        return _code(412)
    if game.mode == MultiplayerGameType.MULTIWORLD:
        t0 = monotonic()
        released = game.mw_release(player_id)
        netperf("mw_release", t0, gid=game_id, pid=player_id, released=released)
        if ARCHIPELAGO:
            # AP-mode world done: durable goal mark + StatusUpdate on its
            # room socket (no-op for games without an AP link)
            ap_bridge.notify_goal(game_id, player_id)
    return 200, "ok"


# --- Archipelago link management (ARCHIPELAGO flag; AP-mode games only) ---

def ap_connect(game_id, payload):
    """POST ap/connect {host, port, password}: store/refresh the game's
    APLink. Reconnects keep the per-world recv indexes (durable progress);
    only the room coordinates and enablement change."""
    if not ARCHIPELAGO:
        return 404, "Archipelago support is not enabled"
    game = Game.with_id(game_id)
    if not game:
        return 404, "Game %s not found" % game_id
    params = game.params.get() if game.params else None
    if not params or not getattr(params, "ap_mode", False):
        return 409, "Game %s is not an Archipelago game" % game_id
    host = (payload.get("host") or "").strip()
    try:
        port = int(payload.get("port"))
    except (TypeError, ValueError):
        port = 0
    if not host or not (0 < port < 65536):
        return 400, "host and port are required"
    link = APLink.with_id(game_id) or APLink.make(game_id, params.players)
    link.host = host
    link.port = port
    link.password = payload.get("password") or None
    link.enabled = True
    link.status = "pending"
    link.last_error = None
    link.put()
    # lazy-start the room bridge (ws.py WS_PUSH pattern: request-path start
    # only; gunicorn --preload silently kills import-time threads)
    ap_bridge.ensure(game_id, link=link)
    return 200, "ok"


def ap_status(game_id):
    """GET ap/status: the stored APLink as JSON."""
    if not ARCHIPELAGO:
        return 404, "Archipelago support is not enabled"
    link = APLink.with_id(game_id)
    if not link:
        return 404, "No Archipelago link for game %s" % game_id
    ap_bridge.heal(game_id)  # checking status re-arms dead bridge threads
    return 200, json.dumps(link.report())


def ap_disconnect(game_id):
    """POST ap/disconnect: stop bridging. The link and its recv indexes stay
    stored; a later connect resumes where the bridge left off."""
    if not ARCHIPELAGO:
        return 404, "Archipelago support is not enabled"
    link = APLink.with_id(game_id)
    if not link:
        return 404, "No Archipelago link for game %s" % game_id
    link.enabled = False
    link.status = "disconnected"
    link.put()
    ap_bridge.stop(game_id)
    return 200, "ok"


def signal_callback(game_id, player_id, signal):
    game = Game.with_id(game_id)
    if not game:
        return _code(412)
    p = game.player(player_id)
    p.signal_conf(signal)
    return 200, "cleared"


def connect(game_id, player_id, payload):
    game = Game.with_id(game_id)
    hist = Cache.get_hist(game_id)
    if not hist:
        Cache.set_hist(game_id, player_id, [])
    if game:
        p = game.player(player_id)
        vers = payload.get("version")
        needs_put = p.note_version(vers, game_id)
        if p.can_nag and vers and (not version_check(vers)):
            p.signal_send("msg:@dll out of date. (orirando.com/dll)@")
            p.can_nag = False
            needs_put = True
        if needs_put:
            p.put()
        uploaded_sync = seed_sync_id(payload.get("seed"))
        if uploaded_sync:
            up_gid, _, up_pid = uploaded_sync.partition(".")
            if up_gid != str(game_id):
                # wrong game: stale randomizer.dat, warn in every mode
                log.warning("seed sync mismatch: %s.%s uploaded a seed for %s", game_id, player_id, uploaded_sync)
                p.signal_send("msg:@Warning: your loaded seed belongs to game %s but you are connected to game %s. Wrong randomizer.dat?@" % (up_gid, game_id))
            elif up_pid != str(player_id) and game.mode == MultiplayerGameType.MULTIWORLD:
                # wrong player only matters in multiworld (wrong world's slot
                # manifest); teammates sharing one .dat in cloned games is fine
                log.warning("seed player mismatch: %s.%s uploaded player %s's seed", game_id, player_id, up_pid)
                p.signal_send("msg:@Warning: you loaded Player %s's seed but connected as Player %s. In multiworld you need your own randomizer.dat!@" % (up_pid, player_id))
        game.sanity_check()  # cheap if game is short!
    else:
        # we no longer support uploading seeds
        log.error("game was not already created! %s" % game_id)
    return 200, "ok"


def bingo_update(game_id, player_id, payload):
    bingo = BingoGameData.with_id(game_id)
    if not bingo:
        return 404, "Bingo game %s not found" % game_id
    if int(player_id) not in bingo.player_nums():
        return 412, "player not in game! %s" % bingo.player_nums()
    bingo_data = json.loads(payload.get("bingoData")) if payload.get("bingoData") else None
    t0 = monotonic()
    evlog_len = len(bingo.event_log)
    def publish():
        # Publish the board only after the transaction committed — publishing inside
        # update() let doomed concurrent attempts overwrite the cache with state that
        # was about to be rolled back (goal flicker). Publish IMMEDIATELY after commit
        # (before logging) to minimize the window in which another thread's newer
        # commit+publish could be overwritten by our older board.
        board = getattr(bingo, "_board_json", None)
        if board is not None:
            Cache.set_board(game_id, board)
    if BINGO_V2:
        try:
            with bingo_lock(game_id):
                # fresh read under the lock; the pre-checks above used an
                # unlocked (possibly stale) read, which is fine for 404/412s
                bingo = BingoGameData.get_by_id(int(game_id), use_cache=False)
                bingo.update_v2(bingo_data, player_id, game_id)
                # publish inside the lock: ordering is trivially correct because
                # no other writer of this game can run concurrently
                publish()
            netperf("bingo_update", t0, gid=game_id, pid=player_id, evlog=evlog_len, v2=1)
            # late re-bust: a tick that read the winner pre-signal can re-arm
            # the fast path after signal_send's own bust (see _update_inner)
            for idpts in getattr(bingo, "_signal_pids", []):
                Cache.clear_seen_checksum(idpts)
            return _code(200)
        except Exception as e:
            log.error("NETPERF bingo_update_fail gid=%s pid=%s v2=1 err=%s: %s", game_id, player_id, type(e).__name__, e)
            return _code(503)
    try:
        bingo.update(bingo_data, player_id, game_id)
        publish()
        netperf("bingo_update", t0, gid=game_id, pid=player_id, evlog=evlog_len, retried=0)
    except Exception as e:
        log.warning("NETPERF bingo_update_err gid=%s pid=%s err=%s: %s", game_id, player_id, type(e).__name__, e)
        # Re-fetch before retrying: the failed transaction rolled back the datastore
        # but NOT the in-memory entity, which update() already mutated (event_log
        # appends, card state). CRITICAL: use_cache=False — the ndb context cache
        # would hand back that same mutated object, making the retry see its own
        # uncommitted changes as prior state → no event, need_write stays False,
        # the BingoGameData put is skipped, and the gain is published to the board
        # cache but never persisted. Next poster reverts it: the E2 flicker in 133486.
        # No sleep — the contention window is sub-second, and on a second failure the
        # client re-POSTs its full (durable) state within a few ticks anyway.
        bingo = BingoGameData.get_by_id(int(game_id), use_cache=False)
        try:
            bingo.update(bingo_data, player_id, game_id)
            publish()
            netperf("bingo_update", t0, gid=game_id, pid=player_id, evlog=evlog_len, retried=1)
        except Exception as e2:
            log.error("NETPERF bingo_update_fail gid=%s pid=%s err=%s: %s", game_id, player_id, type(e2).__name__, e2)
            return _code(503)
    for idpts in getattr(bingo, "_signal_pids", []):
        Cache.clear_seen_checksum(idpts)
    return _code(200)
