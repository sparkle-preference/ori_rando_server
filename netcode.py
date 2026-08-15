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
import ipaddress
import json
import logging as log
from time import monotonic

from ap_models import APLink
from archipelago import ap_bridge
from cache import Cache
from enums import MultiplayerGameType
from models import Game, BingoGameData, Player, bingo_lock
from pickups import Pickup
from util import all_locs, bfield_checksum, coord_correction_map, debug, netperf, seed_sync_id, version_at_least, version_check, AP_MIN_DLL, ARCHIPELAGO


def _code(status):
    return status, str(status)


def _warn_signal(p, signal):
    """Queue a warning without putting the handler's stale copy: that write
    erased concurrent grant transactions' slot bitfields."""
    if Player.signal_send_txn(p.key, signal):
        Cache.clear_seen_checksum(p.idpts())


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
        # any game without a live AP link). active=True: ticks are the game
        # activity that keeps a bridge awake / wakes an idled one.
        ap_bridge.heal(game_id, active=True)
        # ...and so does the client's progressive-hint request, which must be
        # read before the cached fast path below returns without a payload
        ap_bridge.request_hints(game_id, player_id, payload.get("aph"))
        ap_bridge.note_deaths(game_id, player_id, payload.get("dl"))
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
    vers = payload.get("version")
    seen = [int(payload.get("seen_%s" % i, 0)) for i in range(8)]
    have = [int(payload.get("have_%s" % i)) for i in range(8)]
    # slow path only: the fast path above serves cache and never sees a
    # Player. The write re-reads fresh inside a txn and touches only
    # tick-owned fields — putting the stale handler copy raced concurrent
    # grant txns and erased their bits (134701 lost two shared skills, and
    # multiworld has no sanity check to repair that).
    if (vers and p.dll_version != vers) or p.seen_bflds != seen or p.have_bflds != have:
        if vers and p.dll_version != vers:
            log.info("NETPERF dll_version gid=%s pid=%s vers=%s was=%s", game_id, player_id, vers, p.dll_version)
        p = Player.tick_update_txn(p.key, vers, seen, have)
        # set_have has merge semantics — pass only our own entry
        Cache.set_have(game_id, {p.pid(): p.have_coords()})
    Cache.set_seen_checksum((game_id, player_id), bfield_checksum(payload.get("seen_%s" % i, 0) for i in range(8)))
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
    """The client's credits-roll ping. In multiworld this releases everything
    left in the finisher's world to its owners. Logged unconditionally —
    game 134478's lost release was invisible because non-arrival left no
    trace; now absence-of-line = client never sent, definitively. Idempotent
    (a re-released world yields released=0), so clients retry freely."""
    t0 = monotonic()
    game = Game.with_id(game_id)
    if not game:
        netperf("game_complete", t0, gid=game_id, pid=player_id, status=412)
        return _code(412)
    if game.mode == MultiplayerGameType.MULTIWORLD:
        released = game.mw_release(player_id)
        netperf("mw_release", t0, gid=game_id, pid=player_id, released=released)
        if ARCHIPELAGO:
            # AP-mode world done: durable goal mark + StatusUpdate on its
            # room socket (no-op for games without an AP link)
            ap_bridge.notify_goal(game_id, player_id)
    netperf("game_complete", t0, gid=game_id, pid=player_id, mode=game.mode.name, status=200)
    return 200, "ok"


# --- Archipelago link management (ARCHIPELAGO flag; AP-mode games only) ---

def _host_is_local(host):
    """The bridge dials from orirando, so these never reach the user's PC."""
    name = host.strip().lower()
    if name in ("localhost", "localhost.localdomain") or name.endswith(".local"):
        return True
    try:
        address = ipaddress.ip_address(name)
    except ValueError:
        return False
    return address.is_loopback or address.is_private or address.is_link_local


def ap_connect(game_id, payload):
    """POST ap/connect {host, port, password}: store/refresh the game's
    APLink. Reconnects keep the per-world recv indexes (durable progress);
    only the room coordinates and enablement change."""
    if not ARCHIPELAGO:
        return 404, "Archipelago support is not enabled"
    game = Game.with_id(game_id)
    if not game:
        return 404, "Game %s not found" % game_id
    params = game.fetch_params()
    if not params or not getattr(params, "ap_mode", False):
        return 409, "Game %s is not an Archipelago game" % game_id
    host = (payload.get("host") or "").strip()
    try:
        port = int(payload.get("port"))
    except (TypeError, ValueError):
        port = 0
    if not host or not (0 < port < 65536):
        return 400, "host and port are required"
    if _host_is_local(host):
        return 400, ("%s is only reachable from your own machine, and the room "
                     "is dialed from our servers. Use an archipelago.gg room, "
                     "or your public address with the port forwarded." % host)
    # an old dll against the current bridge dupes self-items, so the room
    # stays closed while any player we can see runs one. Versions arrive on
    # the tick, so players who haven't launched yet are invisible here.
    if not payload.get("force"):
        stale = ["P%s is on %s" % (p.pid(), p.dll_version)
                 for p in game.visible_players()
                 if p.dll_version and not version_at_least(p.dll_version, AP_MIN_DLL)]
        if stale:
            return 409, ("Archipelago needs randomizer %s or newer (%s). "
                         "Update, launch the game, then connect again."
                         % (".".join(str(n) for n in AP_MIN_DLL), "; ".join(stale)))
    link = APLink.with_id(game_id) or APLink.make(game_id, params.players, params.player_names)
    password = payload.get("password") or None
    retarget = (link.host, link.port, link.password) != (host, port, password)
    link.host = host
    link.port = port
    link.password = password
    link.enabled = True
    link.status = "pending"
    if retarget:
        link.last_error = None  # retrying the same room keeps its diagnosis
    link.put()
    # lazy-start the room bridge (ws.py push pattern: request-path start
    # only; gunicorn --preload silently kills import-time threads)
    ap_bridge.ensure(game_id, link=link)
    return 200, "ok"


def ap_status(game_id):
    """GET ap/status: the stored APLink as JSON. Served from memcache (every
    APLink put busts via post-put hook); "-" negative-caches a missing row so
    pre-connect polling never reaches the datastore."""
    if not ARCHIPELAGO:
        return 404, "Archipelago support is not enabled"
    cached = Cache.get_aplink_report(game_id)
    if cached == "-":
        return 404, "No Archipelago link for game %s" % game_id
    if cached:
        ap_bridge.heal(game_id)  # passive: re-arms crashed threads, never idle ones
        return 200, cached
    link = APLink.with_id(game_id)
    if not link:
        Cache.set_aplink_report(game_id, "-", negative=True)
        return 404, "No Archipelago link for game %s" % game_id
    # cache before heal: a thread heal spawns could persist + bust while we
    # hold the pre-spawn row, and a set after that bust would pin stale data
    text = json.dumps(link.report())
    Cache.set_aplink_report(game_id, text)
    ap_bridge.heal(game_id)  # passive: re-arms crashed threads, never idle ones
    return 200, text


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
    Player.signal_conf_txn(p.key, signal)
    Cache.clear_seen_checksum(p.idpts())
    return 200, "cleared"


def connect(game_id, player_id, payload):
    game = Game.with_id(game_id)
    hist = Cache.get_hist(game_id)
    if not hist:
        Cache.set_hist(game_id, player_id, [])
    if game:
        p = game.player(player_id)
        vers = payload.get("version")
        nag = ("msg:@dll out of date. (orirando.com/dll)@"
               if p.can_nag and vers and (not version_check(vers)) else None)
        if Player.connect_update_txn(p.key, vers, nag):
            Cache.clear_seen_checksum(p.idpts())
        uploaded_sync = seed_sync_id(payload.get("seed"))
        if uploaded_sync:
            up_gid, _, up_pid = uploaded_sync.partition(".")
            if up_gid != str(game_id):
                # wrong game: stale randomizer.dat, warn in every mode
                log.warning("seed sync mismatch: %s.%s uploaded a seed for %s", game_id, player_id, uploaded_sync)
                _warn_signal(p, "msg:@Warning: your loaded seed belongs to game %s but you are connected to game %s. Wrong randomizer.dat?@" % (up_gid, game_id))
            elif up_pid != str(player_id) and game.mode == MultiplayerGameType.MULTIWORLD:
                # wrong player only matters in multiworld (wrong world's slot
                # manifest); teammates sharing one .dat in cloned games is fine
                log.warning("seed player mismatch: %s.%s uploaded player %s's seed", game_id, player_id, up_pid)
                _warn_signal(p, "msg:@Warning: you loaded Player %s's seed but connected as Player %s. In multiworld you need your own randomizer.dat!@" % (up_pid, player_id))
        game.sanity_check()  # cheap if game is short!
    else:
        # we no longer support uploading seeds
        log.error("game was not already created! %s" % game_id)
    return 200, "ok"


def _ap_bingo_goal(bingo, game_id):
    """A won AP board is its worlds' Archipelago goal. Without this the room
    only hears about the credits roll, which a bingo player never reaches."""
    if not ARCHIPELAGO:
        return
    for world in getattr(bingo, "_ap_goal_worlds", []):
        ap_bridge.notify_goal(game_id, world)


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
        # _board_json is stashed by update(); None = nothing to publish
        board = getattr(bingo, "_board_json", None)
        if board is not None:
            Cache.set_board(game_id, board)
    try:
        with bingo_lock(game_id):
            # fresh read under the lock; the pre-checks above used an
            # unlocked (possibly stale) read, which is fine for 404/412s
            bingo = BingoGameData.get_by_id(int(game_id), use_cache=False)
            bingo.update(bingo_data, player_id, game_id)
            # publish inside the lock: ordering is trivially correct because
            # no other writer of this game can run concurrently
            publish()
        netperf("bingo_update", t0, gid=game_id, pid=player_id, evlog=evlog_len)
        # late re-bust: a tick that read the winner pre-signal can re-arm
        # the fast path after signal_send's own bust (see _update_inner)
        for idpts in getattr(bingo, "_signal_pids", []):
            Cache.clear_seen_checksum(idpts)
        _ap_bingo_goal(bingo, game_id)
        return _code(200)
    except Exception as e:
        log.error("NETPERF bingo_update_fail gid=%s pid=%s err=%s: %s", game_id, player_id, type(e).__name__, e)
        return _code(503)
