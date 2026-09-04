"""Bingo: the board, its lobby, and the per-world machinery behind both.

bingo_board_url is shared: presets and the generator both hand a freshly rolled
game here, so it stays importable without dragging the routes along.
"""
import json
import logging as log
import random
import re
from calendar import timegm
from collections import Counter
from datetime import timedelta
from time import monotonic

from flask import Blueprint, redirect, render_template

from bingo import BingoGenerator, bingo_board_url
from cache import Cache
from enums import MultiplayerGameType, Variation
from models import (BingoEvent, BingoGameData, BingoTeam, BingoWorldBoard, Game,
                    Player, User, bingo_lock, pick_discovery_squares)
from pickups import AbilityCell, EnergyCell, HealthCell, Multiple, Pickup, Skill
from seedbuilder.seedparams import bingo_worlds
from seedbuilder.vanilla import seedtext as vanilla_seed
from util import (INDEX_TEMPLATE, debug, netperf, param_flag, param_val,
                  template_vals, utcnow)
# through the module, not by name: a test patches the owner, not each caller
from web import generator
from web.responses import json_resp, text_download, text_resp

bp = Blueprint("bingo", __name__)


@bp.route('/bingo/board') #BingoBoard =     
@bp.route('/bingo/spectate') #BingoBoard =     
def bingo_board():
    user = User.get()
    template_values = template_vals("Bingo", "OriDE Bingo", user)
    return render_template(INDEX_TEMPLATE, **template_values)

@bp.route('/bingo/game/<int:game_id>/fetch') #BingoGetGame =     
def bingo_get_game(game_id):
    now = utcnow()
    first = param_flag("first")
    res = Cache.get_board(game_id)
    if first or not res:
        t0 = monotonic()
        bingo = BingoGameData.with_id(game_id)
        if not bingo:
            return text_resp("Bingo game %s not found" % game_id, 404)
        res = bingo.get_json(first)
        netperf("board_miss", t0, gid=game_id, first=bool(first))
        if not first:
            # repopulate on miss: pre-start lobbies otherwise recompute for every
            # 1 Hz spectator poll (update() only writes this cache after start_time).
            # Copy: set_board strips is_owner, and offset is added to res below.
            Cache.set_board(game_id, dict(res))
        add_client_offset(res, now)
    return json_resp(res)

@bp.route('/bingo/game/<int:game_id>/start') #BingoStartCountdown =
def bingo_start_game(game_id):
    with bingo_lock(game_id):
        return _bingo_start_game_inner(game_id)


def _bingo_start_game_inner(game_id):
    res = {}
    now = utcnow()
    bingo = BingoGameData.with_id(game_id)
    if not bingo:
        return text_resp("Bingo game %s not found" % game_id, 404)
    user = User.get()
    if not user or bingo.creator != user.key:
        return text_resp("Only the creator can start the game", 401)
    if bingo.start_time:
        return text_resp("Game has already started!", 412)
    if bingo.teams_shared:
        p = bingo.game.get().params.get()
        if not p.sync.cloned:
            for team in bingo.teams:
                if p.players != len(team.teammates) + 1:
                    log.error("team %s did not have %s players!", team, p.players)
                    return text_resp("Not all teams have the correct number of players!", 412)
    bingo.start_time = utcnow() + timedelta(seconds=15)
    startStr = "miscBingo Game %s started!" % game_id
    bingo.event_log.append(BingoEvent(event_type=startStr, timestamp=bingo.start_time))
    res = bingo.get_json()
    # cache before the per-client offset is added, so all viewers see the
    # countdown on their next poll instead of after the 60s board TTL
    Cache.set_board(game_id, dict(res))

    add_client_offset(res, now)
    jsonres = json_resp(res)
    bingo.put()
    return jsonres

@bp.route('/bingo/game/<int:game_id>/reroll') #BingoRerollSeed =
def bingo_reroll_seed(game_id):
    """A new seed on this game's settings, handed to the board builder as if it
    had just come from the generator."""
    game = Game.with_id(game_id)
    if not game:
        return text_resp("Game %s not found!" % game_id, 404)
    if not game.params:
        return text_resp("This bingo game has no seed to reroll", 412)
    params = game.fetch_params()
    if getattr(params, "ap_mode", False):
        return text_resp("An Archipelago seed comes from its room, so it can't be rerolled here", 412)
    new_params, new_game, err = generator._reroll(params)
    if err:
        return err
    bingo = game.bingo_data.get() if game.bingo_data else None
    shared = new_params.sync.enabled and new_params.sync.mode == MultiplayerGameType.SHARED
    return redirect(bingo_board_url(new_game, new_params,
                                     disc=bingo.discovery if bingo else None,
                                     team_max=new_params.players if shared else None))

@bp.route('/bingo/game/<int:game_id>/reroll_board') #BingoRerollBoard =
def bingo_reroll_board(game_id):
    with bingo_lock(game_id):
        return _bingo_reroll_board_inner(game_id)


def _bingo_reroll_board_inner(game_id):
    now = utcnow()
    bingo = BingoGameData.with_id(game_id)
    if not bingo:
        return text_resp("Bingo game %s not found" % game_id, 404)
    user = User.get()
    if not user or bingo.creator != user.key:
        return text_resp("Only the creator can reroll the board", 401)
    # goals travel by channel now, so a reroll is safe until play begins --
    # connected clients re-ask on their next socket open
    if bingo.start_time:
        return text_resp("The game has already started", 412)
    game = Game.with_id(game_id)  # a board's id is its game's
    difficulty = param_val("difficulty") or bingo.difficulty or "normal"
    seed = param_val("seed") or bingo.seed or ""
    if seed == (bingo.seed or ""):
        seed = bump_board_seed(seed)  # a reroll has to move the board even when nothing else changed
    d, lockout, meta = _bingo_query_opts()
    reroll_params = game.fetch_params() if game and game.params else None
    if bingo.boards and reroll_params:
        # ?world= is the board the modal was opened on; without it, the roller's
        owner = owner_world([wb.world for wb in bingo.boards], param_val("world"))
        bingo.boards = bingo_boards_for(reroll_params, seed, lockout, owner,
                                        owner_board_opts(difficulty, d, meta), bingo.boards)
        bingo.board = bingo_board_cards(reroll_params, difficulty, seed, d, meta, lockout,
                                        world=owner or bingo.boards[0].world)
    else:
        bingo.board = bingo_board_cards(reroll_params, difficulty, seed, d, meta, lockout)
    bingo.difficulty = difficulty
    bingo.seed = seed
    bingo.lockout = lockout
    bingo.meta = meta
    bingo.discovery = None
    bingo.disc_squares = []
    if d:
        bingo.discovery_squares(d)
    if param_flag("lines"):
        bingo.bingo_count = int(param_val("lines"))
        bingo.square_count = None
    if param_flag("squares"):
        bingo.square_count = int(param_val("squares"))
    bingo.teams_allowed = (param_flag("teams") or bingo.teams_shared) and not bingo.boards
    bingo.event_log.append(BingoEvent(event_type="miscBoard rerolled!", timestamp=now))
    for p in bingo.get_players():
        if Player.signal_send_txn(p.key, "msg:@Board rerolled! Press alt+L to pick up the new goals@"):
            Cache.clear_seen_checksum(p.idpts())
    bingo.put()
    # in the shape a poll expects, or every viewer sits on the old board for a TTL
    Cache.set_board(game_id, bingo.get_json())
    res = bingo.get_json(True)
    add_client_offset(res, now)
    return json_resp(res)

@bp.route('/bingo/game/<int:game_id>/add/<int:player_id>') #BingoAddPlayer =
def bingo_add_player(game_id, player_id):
    # all writers of a game's BingoGameData serialize on the same per-game
    # lock; a plain-put update can't swallow a concurrent join.
    with bingo_lock(game_id):
        return _bingo_add_player_inner(game_id, player_id)


def _bingo_reseat_world(bingo, game_id, player_id):
    """Put a removed world back. Its board survived the removal and comes back
    untouched; the Player did not, so the world starts its squares again."""
    user = User.get()
    if not (User.is_admin() or (user and bingo.creator and bingo.creator == user.key)):
        return text_resp("This game's players come from its multiworld seed; "
                         "get your seed from whoever rolled it.", 412)
    if player_id not in [wb.world for wb in bingo.boards]:
        return text_resp("World %s has no board in this game" % player_id, 412)
    if player_id in bingo.player_nums():
        return text_resp("World %s is already on the board" % player_id, 409)
    bingo.teams.append(BingoTeam(captain=bingo.init_player(player_id).key, teammates=[]))
    bingo.event_log.append(BingoEvent(event_type="miscWorld %s is back, with a clear board." % player_id,
                                      timestamp=utcnow()))
    bingo.put()
    res = bingo.get_json()
    Cache.set_board(game_id, dict(res))
    return json_resp(res)


def _bingo_add_player_inner(game_id, player_id):
    bingo = BingoGameData.with_id(game_id)
    join_team = param_flag("joinTeam")
    if not bingo:
        return text_resp("Bingo game %s not found" % game_id, 404)
    if join_team and not bingo.teams_allowed:
        return text_resp("Teams are forbidden in this game", 412)
    # a multiworld player's pid is baked into the seed the host handed them, so
    # there is no slot here to claim -- only a removed one for the owner to undo
    if bingo.boards:
        return _bingo_reseat_world(bingo, game_id, player_id)
    if player_id in bingo.player_nums():
        return text_resp("Player id already in use!", 409)
    player = bingo.init_player(player_id)
    if join_team:
        cap_id = int(param_val("joinTeam") or join_team)
        team = bingo.team(cap_id)
        if not team:
            return text_resp("Team %s not found" % cap_id, 412)
        if player_id in team.pids():
            return text_resp("%s already in team %s" % (player_id, cap_id), 412)
        team.teammates.append(player.key)
    else:
        bingo.teams.append(BingoTeam(captain = player.key, teammates = []))
    seed = bingo.get_seed(player_id)
    if not seed:
        return text_resp( "Team has maximum number of players allowed!", 412)
    user = User.get()
    if user:
        player.user = user.key
        player.put()
        if bingo.game not in user.games:
            user.games.append(bingo.game)
            Cache.set_latest_game(user.name, int(game_id), True)
            user.put()
    res = bingo.get_json()
    if bingo.meta:
        bingo.update({}, player_id, game_id, True)  # lock held by caller
        board = getattr(bingo, "_board_json", None)
        if board is not None:
            Cache.set_board(game_id, board)  # NB: strips is_owner from board
            res = dict(board)
    else:
        # push the new roster into the board cache immediately, or every viewer
        # (including the joiner's own next poll) sees the stale pre-join board
        # for up to 60s. Shallow copy so player_seed below stays per-response.
        Cache.set_board(game_id, dict(res))
    res['player_seed'] = seed
    bingo.put()
    return json_resp(res)


@bp.route('/bingo/game/<int:game_id>/remove/<int:player_id>') #BingoRemovePlayer =
def bingo_remove_player(game_id, player_id):
    with bingo_lock(game_id):
        return _bingo_remove_player_inner(game_id, player_id)


def _bingo_remove_player_inner(game_id, player_id):
    bingo = BingoGameData.with_id(game_id)
    if not bingo:
        return text_resp("Bingo game %s not found" % game_id, 404)
    user = User.get()
    if not user or bingo.creator != user.key:
        return text_resp("Only the creator can remove players", 401)
    bingo = bingo.remove_player(player_id).get()
    res = bingo.get_json()
    Cache.set_board(game_id, dict(res))
    return json_resp(res)

@bp.route('/bingo/game/<int:game_id>/seed/<int:player_id>') #BingoDownloadSeed =     
def bingo_download_seed(game_id, player_id):
    bingo = BingoGameData.with_id(game_id)
    if not bingo:
        return text_resp("Bingo game %s not found" % game_id, 404)
    # same gate as the seed page, same force=1 escape: an AP seed is a
    # snapshot, and one taken before the scouts persist keeps placeholders
    game = Game.with_id(game_id)
    params = game.fetch_params() if game else None
    if params and not param_flag("force"):
        not_ready = generator.ap_seed_not_ready(params, int(game_id))
        if not_ready:
            return text_resp(not_ready, 409)
    seed = bingo.get_seed(player_id)
    if not seed:
        return text_resp("No seed found for player %s.%s" % (game_id, player_id), 412)

    if not debug():
        return text_download(seed, 'randomizer.bfr')
    else:
        return text_resp(seed)

RR_SUFFIX = re.compile(r"RR(\d+)$")


def bump_board_seed(seed):
    """The next board seed after this one. Mirrored in Bingo.js so the reroll
    modal shows the seed it will actually use; this side is authoritative."""
    seed = seed or ""
    match = RR_SUFFIX.search(seed)
    if match:
        return seed[:match.start()] + "RR%s" % (int(match.group(1)) + 1)
    return seed + "RR1"


def bingo_board_cards(params, difficulty, seed, disc, meta, lockout, world=1):
    """A fresh board. params is the seed behind a rando board, or None for a
    vanilla+ one; world picks whose rulebook and spawn the goals are built from."""
    rand = random.Random()
    rand.seed(seed)
    if not params:
        return BingoGenerator.get_cards(rand, 25, False, difficulty, True, disc, meta, lockout, False)
    wp = params.world_params(world)
    return BingoGenerator.get_cards(rand, 25, True, difficulty, Variation.OPEN_WORLD in wp.variations,
                                    disc, meta, lockout, Variation.KEYSANITY in wp.variations,
                                    spawn = params.spawn_for(world) or "Glades")


def mw_bingo_worlds(params):
    """The worlds getting their own board. Multiworld splits boards, Archipelago
    included; any other shape plays the one board it always did."""
    if params.sync.mode != MultiplayerGameType.MULTIWORLD:
        return []
    if getattr(params, "ap_mode", False):
        # a board bolted onto a room covers every Ori world in it, opted in or not
        return list(range(1, int(params.players) + 1))
    return bingo_worlds(params)


def owner_board_opts(difficulty, d, meta):
    """The board settings the create/reroll modal sends. They belong to whichever
    world had the modal open, never to a world handed a seed that already told it
    how its board works. The modal opens on one board and posts the whole set
    back, so difficulty, discovery and meta are authoritative even when absent."""
    opts = {"difficulty": difficulty, "discovery": d or 0, "meta": bool(meta)}
    if param_flag("lines"):
        opts.update(bingo_count=int(param_val("lines")), square_count=None, goal="bingos")
    if param_flag("squares"):
        opts.update(square_count=int(param_val("squares")), goal="squares")
    return opts


def owner_world(worlds, asked=None):
    """The world the modal speaks for: whoever asked, else the roller. World 1 is
    the seedgen form itself, so it is the roller's own -- and None when world 1
    isn't playing, because then the modal has no world to move."""
    try:
        if asked is not None and int(asked) in worlds:
            return int(asked)
    except (TypeError, ValueError):
        pass
    return 1 if 1 in worlds else None


def bingo_boards_for(params, seed, lockout, owner=None, opts=None, base=None):
    """One board per participating world, each from that world's own settings.
    Seeded apart, so two worlds on the same settings still get different goals.

    opts moves the owner's world and no other. base is the boards being replaced:
    a reroll moves cards, and a world's rules outlive the cards they shaped."""
    out = []
    was = {b.world: b for b in (base or [])}
    for w in mw_bingo_worlds(params):
        wp = params.world_params(w)
        rules = {"difficulty": wp.bingo_diff, "discovery": wp.bingo_disc, "meta": wp.bingo_meta,
                 "bingo_count": wp.bingo_lines, "square_count": wp.bingo_squares,
                 "goal": wp.bingo_goal}
        if w in was:
            rules = {k: getattr(was[w], k) for k in rules}
        if opts and w == owner:
            rules.update(opts)
        board_seed = "%s.%s" % (seed, w)
        cards = bingo_board_cards(params, rules["difficulty"], board_seed,
                                  rules["discovery"], rules["meta"], lockout, world=w)
        out.append(BingoWorldBoard(
            world=w, board=cards,
            disc_squares=pick_discovery_squares(cards, board_seed, rules["discovery"]) if rules["discovery"] else [],
            **rules))
    return out

@bp.route('/bingo/new') #BingoCreate =
def bingo_create_game():
        now = utcnow()
        difficulty = param_val("difficulty") or "normal"
        skills = param_val("skills")
        cells = param_val("cells")
        skills = int(skills) if skills and skills != "NaN" else 3
        cells = int(cells) if cells and cells != "NaN" else 3
        show_info = param_flag("showInfo")
        misc_raw = param_val("misc")
        misc_pickup = Pickup.from_str(misc_raw) if misc_raw and misc_raw != "NO|1" else None
        skill_pool = [Skill(x) for x in [0, 2, 3, 4, 5, 8, 12, 14, 50, 51]]
        cell_pool  = [Multiple.with_pickups([AbilityCell(1), AbilityCell(1)]), HealthCell(1), EnergyCell(1)]
        seed = param_val("seed")
        rand = random.Random()
        rand.seed(seed)

        start_pickups = rand.sample(skill_pool, skills)
        for _ in range(cells):
            start_pickups.append(rand.choice(cell_pool))
        if misc_pickup:
            start_pickups.append(misc_pickup)
        start_with = Multiple.with_pickups(start_pickups)
        key = Game.new(_mode = "Bingo", _shared = [])
        if show_info and start_with:
            tps = []
            skills = []
            misc = []
            cells = Counter()
            for pick in start_with.children:
                if pick.code == "TP":
                    tps.append(pick.name[:-11])
                elif pick.code == "SK":
                    skills.append(pick.name)
                elif pick.code in ["HC", "EC", "AC"]:
                    cells[pick.code]+=1
                else:
                    misc.append(pick.name)
            sw_parts = []
            if skills:
                sw_parts.append("Skills: " + ", ".join(skills))
            if tps:
                sw_parts.append("TPs: " + ", ".join(tps))
            if cells:
                sw_parts.append("Cells: " + ", ".join([cell if amount == 1 else "%s %ss" % (amount, cell) for cell,amount in cells.items()]))
            if misc:
                sw_parts.append(", ".join(misc))
        base = vanilla_seed.split("\n")
        base[0] = "OpenWorld,Bingo|Bingo Game %s" % key.id()
        if start_with:
            mu_line = "2|MU|%s|Glades" % start_with.id
            base.insert(1, mu_line)
        
        game = key.get()
        d, lockout, meta = _bingo_query_opts()
        bingo = BingoGameData(
            id            = key.id(),
            board         = BingoGenerator.get_cards(rand, 25, False, difficulty, True, d, meta, lockout, False),
            difficulty    = difficulty,
            teams_allowed = param_flag("teams"),
            game          = key,
            rand_dat      = "\n".join(base),
            lockout       = lockout,
            meta          = meta,
            seed          = seed  # kept whether or not discovery needs it: a reroll bumps it
        )
        if d:
            bingo.discovery = d
        eventStr = _bingo_setup_tail(bingo, now, key.id())
        if show_info:
            bingo.subtitle = " | ".join(sw_parts)
            eventStr += ", starting with: " + ", ".join(sw_parts)
        bingo.event_log.append(BingoEvent(event_type=eventStr, timestamp=now))
        res = bingo.get_json(True)

        add_client_offset(res, now)

        bkey = bingo.put()
        game.bingo_data = bkey
        game.put()
        return json_resp(res)


def latest_bingo_game(name):
    """(game id, error text) for a username's most recent bingo game. The
    walk costs a name query plus a get per game the user has ever played, and
    the userboard polls once a minute -- so the derived answer is cached."""
    game_id = Cache.get_latest_game(name, bingo=True)
    if game_id:
        return game_id, None
    user = User.get_by_name(name)
    if not user:
        return None, "User '%s' not found" % name
    for key in user.games[::-1]:
        game = key.get()
        if game and game.bingo_data:   # cleanup leaves dangling keys behind
            Cache.set_latest_bingo_game(name, game.key.id())
            return game.key.id(), None
    return None, "Could not find any bingo games for user '%s'" % name


@bp.route('/bingo/spectate/<name>') #BingoUserSpectate =
def bingo_user_board(name):
    game_id, err = latest_bingo_game(name)
    if err:
        return text_resp(err, 404)
    return redirect("/bingo/spectate?game_id=%s" % (4 + game_id * 7))

@bp.route('/bingo/userboard/<name>/') #BingoUserboard =     
def bingo_userboard(name):
    user = User.get_by_name(name)
    if not user:
        return text_resp("User '%s' not found" % name, 404)
    template_values = {'app': "Bingo", 'title': "%s's Bingo Board" % user.name}
    template_values['user'] = user.name
    template_values['theme'] = user.site_theme()
    if user.theme_dark() is not None:
        template_values['dark'] = user.theme_dark()
    return render_template(INDEX_TEMPLATE, **template_values)

@bp.route('/bingo/userboard/<name>/fetch/<game_id>') #UserboardTick =     
def bingo_userboard_tick(name, game_id):
    cur_gid = int(game_id)
    now = utcnow()
    game_id, err = latest_bingo_game(name)
    if err:
        return text_resp(err, 404)
    first = cur_gid != game_id
    res = {}
    bingo = BingoGameData.with_id(game_id)
    if not bingo:
        return text_resp("Bingo game %s not found" % game_id, 404)
    res = bingo.get_json(first)
    add_client_offset(res, now)
    return json_resp(res)


def _bingo_query_opts():
    """The board options every bingo creation route reads the same way."""
    return (int(param_val("discCount") or 0),
            bool(int(param_val("lockout") or 0)),
            param_flag("meta"))


def _bingo_setup_tail(bingo, now, gid):
    """The shared back half of board creation: count overrides, creator, start
    timing. Returns the event string for the caller to extend and log."""
    if param_flag("lines"):
        bingo.bingo_count = int(param_val("lines"))
    if param_flag("squares"):
        bingo.square_count = int(param_val("squares"))
    user = User.get()
    event = "misc"
    if user:
        bingo.creator = user.key
    if not user or param_flag("noTimer"):
        bingo.auto_start = True
        event += "Bingo Game %s created! The clock starts with its first player." % gid
    else:
        event += "Bingo Game %s created!" % gid
    if bingo.square_count and bingo.square_count > 0:
        event += " squares to win: %s" % bingo.square_count
        if bingo.lockout:
            event += ", lockout"
    elif bingo.bingo_count > 0:
        event += " bingos to win: %s" % bingo.bingo_count
    return event


def add_client_offset(res, now):
    """The board clock rides every payload: server minus client, milliseconds."""
    if param_flag("time"):
        res["offset"] = timegm(now.timetuple()) * 1000 - int(param_val("time"))


def _bingo_recreate_problem(game, bingo):
    """A second from_game wipes a live board, so it's the owner's call."""
    if User.is_admin():
        return None
    user = User.get()
    owners = [k for k in (game.creator, bingo.creator) if k]
    if user and user.key in owners:
        return None
    return "game %s already has a bingo board" % game.key.id()


@bp.route('/bingo/from_game/<int:game_id>') #AddBingoToGame =     
def add_bingo_to_game(game_id):
        now = utcnow()
        game_id = int(game_id)
        difficulty = param_val("difficulty") or "normal"
        if not game_id or int(game_id) < 1:
            return text_resp("please provide a valid game id", 404)
        game = Game.with_id(game_id)
        if not game:
            return text_resp("game not found", 404)
        if not game.params:
            return text_resp("game did not have required seed data", 412)
        if game.bingo_data:
            existing = game.bingo_data.get()
            if existing:
                problem = _bingo_recreate_problem(game, existing)
                if problem:
                    return text_resp(problem, 403)
        if game.mode in [MultiplayerGameType.SPLITSHARDS]:
            return text_resp("splitshards bingo are not currently supported", 412)
        params = game.fetch_params()
        seed = param_val("seed") or params.seed
        rand = random.Random()
        rand.seed(seed)

        d, lockout, meta = _bingo_query_opts()
        test_iters = int(param_val("testIters") or 0)
        if test_iters: # this is like having test code
            edges = [0,1,2,3,4,5,9,10,14,15,19,20,21,22,23,24]
            metacnt = 0
            symcnt = 0
            actvcnt = 0
            edgesymcnt = 0
            doublesymcnt = 0
            edgedisccnt = 0
            symdisccnt = 0
            
            for i in range(test_iters):
                iseed = seed+str(i)
                rand.seed(iseed)
                cards = BingoGenerator.get_cards(rand, 25, True, difficulty, Variation.OPEN_WORLD in params.variations, d, meta, lockout, Variation.KEYSANITY in params.variations, spawn = params.spawn or "Glades")

                if not all([card.square in range(2,23,5) for card in cards if card.name == "VertSym"]):
                    log.error("seed %s: VertSym: %s", iseed, [(card.square, card.square in range(2,23,5)) for card in cards if card.name == "VertSym"])
                if not all([card.square in range(10,15) for card in cards if card.name == "HorizSym"]):
                    log.error("seed %s: HorizSym: %s", iseed, [(card.square, card.square in range(10,15)) for card in cards if card.name == "HorizSym"])
                if not all([(len(sg['name']) <3) for card in cards if card.name == "Activate Squares" for sg in card.subgoals ]):
                    log.error("seed %s: Activate Squares: %s", iseed, [((sg['name'])) for card in cards if card.name == "Activate Squares" for sg in card.subgoals])
                if not len([c for c in cards if c.meta]) <= 5:
                    log.error("seed %s:total count: %s", iseed, len([c for c in cards if c.meta]))
                metacnt += len([c for c in cards if c.meta])
                actvcnt += len([c for c in cards if c.name == "Activate Squares"])
                syms = [c for c in cards if "Sym" in c.name]
                symcnt += len(syms)
                edgesymcnt += len([c for c in syms if c.square in edges])
                doublesymcnt += (1 if len(syms) == 2 else 0)
                if d:
                    bingo = BingoGameData(
                        id            = game_id,
                        board         = cards,
                        difficulty    = difficulty,
                        subtitle      = params.flag_line(),
                        teams_allowed = param_flag("teams"),
                        teams_shared  = params.players > 1 and params.sync.mode == MultiplayerGameType.SHARED,
                        game          = game.key,
                        lockout       = lockout,
                        meta          = meta,
                        seed          = iseed
                    )
                    discsquares = bingo.discovery_squares(d)
                    symdisccnt += len([c for c in syms if c.square in discsquares])
                    edgedisccnt += len([s for s in discsquares if s in edges])
            log.info('-------------')
            for name, num in [("meta squares", metacnt), ("square cards", actvcnt), ("symmetry squares", symcnt), ("symmetry squares on edges", edgesymcnt), ("boards with both symmetry squares", doublesymcnt), ("discovery squares on the edge", edgedisccnt), ("symmetry discovery squares", symdisccnt)]:
                log.info("%s %3d/%s = %s", (name+":").ljust(36), num, test_iters, float(num)/float(test_iters))
            return text_resp("test retry", 420)

        # any multiworld opt-in is per-world: even a lone bingo player keeps
        # board pids == world numbers, which is what the seeds went out carrying
        worlds = mw_bingo_worlds(params)
        per_world = bool(worlds)
        if per_world:
            lockout = False     # separate boards never share a square to take
        # the modal belongs to whoever rolled the seed, and that is world 1
        owner = owner_world(worlds)
        bingo = BingoGameData(
            id            = game_id,
            board         = bingo_board_cards(params, difficulty, seed, d, meta, lockout,
                                              world=owner or (worlds[0] if worlds else 1)),
            boards        = bingo_boards_for(params, seed, lockout, owner,
                                             owner_board_opts(difficulty, d, meta)) if per_world else [],
            difficulty    = difficulty,
            subtitle      = params.flag_line(),
            teams_allowed = param_flag("teams") and not per_world,
            teams_shared  = params.players > 1 and params.sync.mode == MultiplayerGameType.SHARED,
            game          = game.key,
            lockout       = lockout,
            meta          = meta,
            seed          = seed  # kept whether or not discovery needs it: a reroll bumps it
        )
        if d:
            bingo.discovery_squares(d)

        if bingo.teams_shared and not bingo.teams_allowed:
            log.warning("Teams are required for shared seeds! Overriding invalid config")
            bingo.teams_allowed = True

        eventStr = _bingo_setup_tail(bingo, now, game_id)
        bingo.event_log.append(BingoEvent(event_type=eventStr, timestamp=now))
        if getattr(params, "ap_mode", False):
            # the boards are per-world like any multiworld's; this only marks
            # that winning one is its world's Archipelago goal
            bingo.ap_worlds = int(params.players)
        # wipe before seating, or the wipe eats the captains seated below and
        # their bare lazy replacements break every later board fetch
        for p in game.get_players():
            # spares the AP shadows (pid > K) too: they hold the bridge's outbox
            if per_world and p.pid() not in worlds:
                continue
            game.remove_player(p.key.id())
        if per_world:
            # the board's pids ARE the multiworld's worlds, and the seeds went out
            # with those numbers in them, so the roster is settled here
            for w in worlds:
                bingo.teams.append(BingoTeam(captain=bingo.init_player(w).key, teammates=[]))
        # after the AP fields: the creator's page reads ap_worlds off this
        res = bingo.get_json(True)
        add_client_offset(res, now)

        bkey = bingo.put()
        game.bingo_data = bkey
        game.put()
        return json_resp(json.dumps(res))


@bp.route('/bingo/bingothon/<int:game_id>/player/<int:player_id>') #GetBingothonJson    
def bingothon_fetch_data(game_id, player_id):
    res = {"cards": []}
    bingo = BingoGameData.with_id(game_id)
    if not bingo:
        return json_resp({"error": "bingo game not found"}, 404)
    p = bingo.player(player_id)
    if not p:
        return json_resp({"error": "player not found in game"}, 404)
    for card in bingo.board_for(player_id):
        res["cards"].append(card.bingothon_json(p))
    disc = next((list(wb.disc_squares) for wb in bingo.boards
                 if wb.world == int(player_id) and wb.discovery), None)
    if disc is not None:
        res["disc_squares"] = disc
    elif not bingo.boards and bingo.discovery:
        res["disc_squares"] = bingo.disc_squares
    return json_resp(res)
