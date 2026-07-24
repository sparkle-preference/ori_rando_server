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

from cache import Cache
from enums import MultiplayerGameType
from models import Game, BingoGameData, bingo_lock
from pickups import Pickup
from util import all_locs, bfield_checksum, coord_correction_map, debug, netperf, seed_sync_id, version_check, BINGO_V2


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
    p.bitfield_updates(payload, game_id)
    Cache.set_pos(game_id, player_id, x, y)
    return 200, p.output(include_slots=(game.mode == MultiplayerGameType.MULTIWORLD))


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
        if p.can_nag and vers and (not version_check(vers)):
            p.signal_send("msg:@dll out of date. (orirando.com/dll)@")
            p.can_nag = False
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
    return _code(200)
