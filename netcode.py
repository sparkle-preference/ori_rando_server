"""Transport-neutral session layer for the client netcode.

Handlers map (game_id, player_id, ...path args, payload) to (status, body). payload is any
Mapping (request.args/form, or a dict from ws.py); bodies are the exact strings the C# client
parses (golden_wire_test) and adapters pass them through unmodified. No Flask imports here.
"""
import ipaddress
import json
import logging as log
from time import monotonic

from ap_models import APHints, APLink, HINT_OFFERED
from archipelago import ap_bridge
from cache import Cache
from enums import MultiplayerGameType
from models import Game, BingoGameData, Player, User, bingo_lock
from pickups import Pickup
from util import SITE_HOST, all_locs, bfield_checksum, coord_correction_map, debug, netperf, seed_sync_id, version_at_least, version_check, AP_LOCAL_ROOMS, AP_MIN_DLL, ARCHIPELAGO


def _code(status):
    return status, str(status)


def _warn_signal(p, signal):
    """Queue a warning via a fresh-read txn, never a put of the handler's copy."""
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
    # no player count: only naming a cross-world item needs one, and history stores the raw id
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
        # ticks are the activity that keeps a bridge awake; cheap without a live link
        ap_bridge.heal(game_id, active=True)
        # read before the fast path returns
        ap_bridge.request_hints(game_id, player_id, payload.get("aph"))
        ap_bridge.note_deaths(game_id, player_id, payload.get("dl"))
    x = payload.get("x")
    y = payload.get("y")
    if Cache.get_seen_checksum((game_id, player_id)) == bfield_checksum(payload.get("seen_%s" % i, 0) for i in range(8)):
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
    # a fresh-read txn on tick-owned fields: a put of this copy would erase concurrent grants
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
    """The /tick/ body for a push frame, without the payload processing a real tick does."""
    game = Game.with_id(game_id)
    if not game:
        return None
    p = game.player(player_id)
    return p.output(include_slots=(game.mode == MultiplayerGameType.MULTIWORLD))




def game_complete(game_id, player_id):
    """Credits-roll ping; in multiworld, releases the finisher's world to its owners.
    Idempotent, and always logged: no game_complete line means the client never sent it."""
    t0 = monotonic()
    game = Game.with_id(game_id)
    if not game:
        netperf("game_complete", t0, gid=game_id, pid=player_id, status=412)
        return _code(412)
    if game.mode == MultiplayerGameType.MULTIWORLD:
        released = game.mw_release(player_id)
        netperf("mw_release", t0, gid=game_id, pid=player_id, released=released)
        # marked even when nothing was released: the client reads it to stop offering spent locations
        finisher = game.player(player_id)
        if finisher is not None and not finisher.released:
            finisher.released = True
            finisher.put()
            # or an idle finisher's fast path never shows it
            Cache.clear_seen_checksum(finisher.idpts())
        if ARCHIPELAGO:
            # durable goal mark + StatusUpdate; no-op without an AP link
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
    """POST ap/connect {host, port, password}: store or refresh the game's APLink.
    Reconnects keep the per-world recv indexes."""
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
    if _host_is_local(host) and not AP_LOCAL_ROOMS:
        return 400, ("%s is only reachable from your own machine, and the room "
                     "is dialed from our servers. Use an archipelago.gg room, "
                     "or your public address with the port forwarded." % host)
    # an old dll dupes self-items; players who haven't ticked yet report no version
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
    # threads start lazily: --preload forks away any started at import
    ap_bridge.ensure(game_id, link=link)
    return 200, "ok"


def ap_status(game_id):
    """GET ap/status: the stored APLink as JSON, memcached; "-" negative-caches a missing row."""
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
    # cache before heal, or this row could overwrite a bust from the thread heal spawns
    text = json.dumps(link.report())
    Cache.set_aplink_report(game_id, text)
    ap_bridge.heal(game_id)  # passive: re-arms crashed threads, never idle ones
    return 200, text


def _may_buy_hints(game):
    """Anyone may buy for a passwordless room (it takes !hint from anyone with the
    address); a password limits buying to this game's logged-in players."""
    link = APLink.with_id(game.key.id())
    if link is None:
        return False, "No Archipelago link for game %s" % game.key.id()
    if not link.password:
        return True, None
    user = User.get()
    if not user:
        return False, "This room has a password, so buying hints needs a login"
    if any(p is not None and p.user == user.key for p in game.get_players()):
        return True, None
    return False, "Only a player in this game can buy its hints"


def _ap_game(game_id):
    """(game, None) or (None, (status, body)) -- the checks both hint routes
    make before they look at anything."""
    if not ARCHIPELAGO:
        return None, (404, "Archipelago support is not enabled")
    game = Game.with_id(game_id)
    if not game:
        return None, (404, "Game %s not found" % game_id)
    params = game.fetch_params()
    if not params or not getattr(params, "ap_mode", False):
        return None, (409, "Game %s is not an Archipelago game" % game_id)
    return game, None


def ap_hints(game_id):
    """GET ap/hints: what each world could buy, and the room's price.
    An offer is a hint Ori unlocked that nothing free answered."""
    game, problem = _ap_game(game_id)
    if problem:
        return problem
    may, why = _may_buy_hints(game)
    worlds = []
    for world in range(1, (game.players or 1) + 1):
        points, cost = APHints.price(game_id, world)
        offers = []
        for slot, entry in sorted(APHints.load(game_id, world).items()):
            if entry.get("s") != HINT_OFFERED:
                continue
            key = entry.get("k", "")
            code, _, ident = key.partition("|")
            # the page's name table has no keysanity door keystones
            offers.append({"slot": slot, "key": key,
                           "name": Pickup.name(code, ident) if key else ""})
        worlds.append({"world": world, "points": points, "cost": cost,
                       "offers": offers})
    return 200, {"worlds": worlds, "can_buy": may, "why": why}


def ap_buy_hint(game_id, payload):
    """POST ap/hints/buy {world, slot}: mark one offer bought; the bridge spends the points.
    A double press loses a compare-and-set."""
    game, problem = _ap_game(game_id)
    if problem:
        return problem
    may, why = _may_buy_hints(game)
    if not may:
        return 403, why
    try:
        world, slot = int(payload.get("world")), int(payload.get("slot"))
    except (TypeError, ValueError):
        return 400, "world and slot are required"
    if not 1 <= world <= (game.players or 1):
        return 400, "Game %s has no world %s" % (game_id, world)
    points, cost = APHints.price(game_id, world)
    if points < cost:
        return 402, "World %s has %s hint points and a hint costs %s" % (world, points, cost)
    if not APHints.request(game_id, world, slot):
        return 409, "That hint is not for sale"
    ap_bridge.heal(game_id)   # a crashed session must not sit on a paid-for ask
    return 200, "ok"


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
        nag = ("msg:@dll out of date. (%s/dll)@" % SITE_HOST
               if p.can_nag and vers and (not version_check(vers)) else None)
        if Player.connect_update_txn(p.key, vers, nag):
            Cache.clear_seen_checksum(p.idpts())
        uploaded_sync = seed_sync_id(payload.get("seed"))
        if uploaded_sync:
            up_gid, _, up_pid = uploaded_sync.partition(".")
            if up_gid != str(game_id):
                # wrong game: stale randomizer.bfr, warn in every mode
                log.warning("seed sync mismatch: %s.%s uploaded a seed for %s", game_id, player_id, uploaded_sync)
                _warn_signal(p, "msg:@Warning: your loaded seed belongs to game %s but you are connected to game %s. Wrong randomizer.bfr?@" % (up_gid, game_id))
            elif up_pid != str(player_id) and game.mode == MultiplayerGameType.MULTIWORLD:
                # wrong player only matters in multiworld (wrong world's slot
                # manifest); teammates sharing one seed file in cloned games is fine
                log.warning("seed player mismatch: %s.%s uploaded player %s's seed", game_id, player_id, up_pid)
                _warn_signal(p, "msg:@Warning: you loaded Player %s's seed but connected as Player %s. In multiworld you need your own randomizer.bfr!@" % (up_pid, player_id))
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


def goals(game_id, player_id):
    """This player's Goals line, which seed files don't carry (ws goals: or http)."""
    bingo = BingoGameData.with_id(game_id)
    if not bingo:
        return 404, "Bingo game %s not found" % game_id
    if not bingo.plays_bingo(player_id):
        return 404, "world %s has no board here" % player_id
    return 200, bingo.goals_line(player_id).rstrip("\n")


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
            # fresh read under the lock; the 404/412 checks above tolerate a stale one
            bingo = BingoGameData.get_by_id(int(game_id), use_cache=False)
            bingo.update(bingo_data, player_id, game_id)
            # inside the lock, so publishes land in write order
            publish()
        netperf("bingo_update", t0, gid=game_id, pid=player_id, evlog=evlog_len)
        # a tick that read the winner pre-signal can re-arm the fast path after signal_send's bust
        for idpts in getattr(bingo, "_signal_pids", []):
            Cache.clear_seen_checksum(idpts)
        _ap_bingo_goal(bingo, game_id)
        return _code(200)
    except Exception as e:
        log.error("NETPERF bingo_update_fail gid=%s pid=%s err=%s: %s", game_id, player_id, type(e).__name__, e)
        return _code(503)
