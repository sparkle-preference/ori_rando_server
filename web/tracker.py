"""The live map and the game pages behind it.

Everything a spectator or a runner reads while a game is running: the map, its
polled updates, the item tracker, plus the game admin the same people need
(history, player list, reset, transfer).
"""
import logging as log
from datetime import timedelta

from flask import Blueprint, redirect, render_template, request, url_for
from google.cloud import ndb

from cache import Cache
from enums import MultiplayerGameType, ShareType, Variation
from models import BingoGameData, Game, Player, User
from pickups import Pickup
from reachable import Map, PlayerState
from util import (INDEX_TEMPLATE, game_flags, is_mw_manifest_loc, param_flag,
                  param_val, template_vals, utcnow, whitelist_ok)
from web.extensions import oidc
from web.responses import json_resp, make_resp, text_resp

bp = Blueprint("tracker", __name__)


def game_list_html(games):
    body = ""
    for game in sorted([g for g in games if g], key=lambda x: x.last_update, reverse=True):
        gid = game.key.id()
        game_link = url_for('tracker.game_show_history', game_id=gid)
        map_link = url_for('tracker.tracker_show_map', game_id=gid)
        slink = ""
        flags = ""
        if game.params:
            flag_line, is_race = game_flags(game.params)
            if flag_line is not None:
                if is_race and not whitelist_ok():
                    continue
                flags = flag_line
                slink = " <a href=%s>Seed</a>" % url_for('main_page', game_id=gid, param_id=game.params.id())
            else:
                slink = " (Seed not found)"
        blink = ""
        if game.bingo_data:
            blink += " <a href='/bingo/board?game_id=%s'>Bingo board</a>" % gid
        body += "<li><a href='%s'>Game #%s</a> <a href='%s'>Map</a>%s%s %s (Last update: %s ago)</li>" % (game_link, gid, map_link, slink, blink, flags, utcnow() - game.last_update)
    return body

GAME_LIST_LIMIT = 50
# what a non-verbose history shows: the categories a game can share
share_types = [ShareType.EVENT, ShareType.SKILL, ShareType.UPGRADE, ShareType.MISC,
               ShareType.TELEPORTER]


@bp.route('/activeGames/')
@bp.route('/activeGames/<hours>/')
def active_games(hours=12):
    hours = int(hours)
    title = "Games active in the last %s hours" % hours
    # bounded, and the "did anyone play" test is a field on the game now: it
    # used to be a history walk (an ancestor query plus a get per player) per
    # game, behind an unlimited query with an even less limited fallback.
    # Games written before has_history existed read None -- unknown, so shown.
    # Widen the window with /activeGames/<hours>/ rather than fetching all.
    # order explicitly: an inequality query defaults to ASCENDING on that
    # property, so a bare fetch(limit) would return the OLDEST games in the
    # window. Same property, so no composite index needed. Over-fetch and
    # slice AFTER filtering, or a run of generated-but-unplayed games fills
    # the budget and reports "no active games" while real ones sit below it.
    games = Game.query(Game.last_update > utcnow() - timedelta(hours=hours)
                       ).order(-Game.last_update).fetch(GAME_LIST_LIMIT * 4)
    games = [game for game in games if game.has_history is not False][:GAME_LIST_LIMIT]
    if not len(games):
        title = "No active games found!"
    body = game_list_html(games)
    out = "<html><head><title>%s - Ori Rando Server</title></head><body>" % title
    if body:
        out += "<h4>%s:</h4><ul>%s</ul></body</html>" % (title, body)
    else:
        out += "<h4>%s</h4></body></html>" % title
    return make_resp(out)
@bp.route('/myGames')
@oidc.require_login
def my_games():
    user = User.get()
    keys = user.games if param_flag("all") else user.games[-10:]
    title = "Games played by %s" % user.name if param_flag("all") else "Last 10 games played by %s" % user.name
    # even ?all is bounded: a long-time player's list is thousands of games,
    # and one batched get beats a fan-out of per-key futures
    if len(keys) > GAME_LIST_LIMIT * 4:
        keys = keys[-GAME_LIST_LIMIT * 4:]
        title = "Most recent games played by %s" % user.name
    body = game_list_html(ndb.get_multi(keys))
    if body:
        out = "<h4>%s:</h4><ul>%s</ul></body</html>" % (title, body)
    else:
        out = "<h4>%s</h4></body></html>" % title
    return make_resp(out)
@bp.route('/game/<int:game_id>/delete/')
def game_delete(game_id):
    if int(game_id) < 10000 and not param_flag("override"):
        return text_resp("No", 403)
    game = Game.with_id(game_id)
    if game:
        game.clean_up()
        return text_resp("All according to daijobu")
    else:
        return text_resp("The game... was already dead...", 401)
@bp.route('/game/<int:game_id>')
@bp.route('/game/<int:game_id>/history/')
def game_show_history(game_id):
    template_values = template_vals("History", "Game %s" % game_id, User.get())
    game = Game.with_id(game_id)
    if game:
        if (game.params and Variation.RACE in game.fetch_params().variations) and not template_values["race_wl"]:
            return text_resp("Access forbidden", 401)
        output = game.summary(int(param_val("p") or 0))
        output += "\nHistory:"
        hls = []
        pids = [int(pid) for pid in param_val("pids").split("|")] if param_val("pids") else []
        hls = game.history(pids) if param_flag("verbose") else [h for h in game.history(pids) if h.pickup().is_shared(share_types)]
        mw_names = game.mw_names()
        for hl in sorted(hls, key=lambda x: x.timestamp, reverse=True):
            output += "\n\t\t%s Player %s %s" % ((hl.player-1)*"\t\t\t\t", hl.player, hl.print_line(game.start_time, mw_names))
        return text_resp(output)
    else:
        return text_resp("Game %s not found!" % game_id, 404)
@bp.route('/game/<int:game_id>/players/')
def game_list_players(game_id):
        game = Game.with_id(game_id)
        if not game:
            return text_resp("Game %s not found!" % game_id, 404)
        out_lines = []
        mw_names = game.mw_names()
        for p in game.visible_players():
            out_lines.append("Player %s: %s" % (p.pid(), p.output()))
            out_lines.append("\t\t" + "\n\t\t".join([hl.print_line(game.start_time, mw_names) for hl in game.history([p.pid()]) if hl.pickup().is_shared(share_types)]))
        return text_resp("\n".join(out_lines))
@bp.route('/game/<int:game_id>/player/<pid>/remove/')
def game_remove_player(game_id, pid):
    key = ".".join([game_id, pid])
    game = Game.with_id(game_id)
    if not game:
        return text_resp("Game %s not found!" % game_id, 404)
    if key in [p.id() for p in game.players]:
        game.remove_player(key)
        return redirect(url_for("tracker.game_list_players", game_id=game_id))
    else:
        return text_resp("player %s not in %s for" % (key, game.players), 404)
@bp.route('/tracker/game/<int:game_id>/')
@bp.route('/tracker/game/<int:game_id>/map')
def tracker_show_map(game_id):
    template_values = template_vals("GameTracker", "Game %s" % game_id, User.get())
    template_values['game_id'] = game_id
    # if debug() and param_flag("from_test"):
    #     game = Game.with_id(game_id)
    #     pos = Cache.get_pos(game_id)
    #     hist = Cache.get_hist(game_id)
    #     if any([x is None for x in [game, pos, hist]]):
    #         return redirect(url_for('tests_map_gid', game_id=game_id, from_test=1))
    game = Game.with_id(game_id)
    if game and (Variation.RACE in game.fetch_params().variations) and not template_values["race_wl"]:
        return text_resp("Access forbidden", 401)
    return render_template(INDEX_TEMPLATE, **template_values)
@bp.route('/tracker/game/<int:game_id>/fetch/gamedata')
def tracker_fetch_gamedata(game_id):
    gamedata = {}
    game = Game.with_id(game_id)
    if not game or not game.params:
        return json_resp({"error": "Game %s not found!" % game_id}, 404)
    params = game.fetch_params()
    gamedata["paths"] = params.logic_paths
    gamedata["players"] = [p.userdata() for p in game.visible_players()]
    gamedata["closed_dungeons"] = Variation.CLOSED_DUNGEONS in params.variations
    gamedata["open_world"] = Variation.OPEN_WORLD in params.variations
    return json_resp(gamedata)
@bp.route('/tracker/game/<int:game_id>/fetch/update')
def tracker_update_map(game_id):
    players = {}
    username = param_val("usermap")
    gid_changed = False
    if username:
        # once, not twice: this is the 1Hz route, and a falsy answer (unknown
        # user, or a user with no games) must not become the game id
        latest = User.latest_game(username)
        if latest and latest != int(game_id):
            game_id = latest
            gid_changed = True
    pos = Cache.get_pos(game_id)
    inventories = None
    game = None
    if not pos:
        pos = {}
    for p, (x, y) in pos.items():
        players[p] = {"pos": [y, x], "seen": [], "reachable": []}  # bc we use tiling software, this is lat/lng, and thus coords need inverting

    coords = Cache.get_have(game_id)
    if not coords:
        game = Game.with_id(game_id)
        if not game:
            return json_resp({"error": "Game %s not found" % game_id}, 404)
        coords = { p.pid(): p.have_coords() for p in game.visible_players() }
        Cache.set_have(game_id, coords)
    for p, coords in coords.items():
        if p not in players:
            players[p] = {}
        players[p]["seen"] = coords
    reach = Cache.get_reachable(game_id)
    modes = tuple(sorted(param_val("modes").split(" ")))
    need_reach_updates = [p for p in players.keys() if modes not in reach.get(p, {})]
    if need_reach_updates:
        if not game:
            game = Game.with_id(game_id)
            if not game:
                return json_resp({"error": "Game %s not found" % game_id}, 404)
        if not inventories:
            inventories = game.get_inventories(game.visible_players(), True, True)
        spawn = game.fetch_params().spawn or "Glades"
        for p in need_reach_updates:
            inventory = [(pcode, pid, count, False) for ((pcode, pid), count) in inventories["unshared"][p].items()]
            inventory  += [(pcode, pid, count, False) for group, inv in inventories.items()  if group != "unshared" and p in group for ((pcode, pid), count) in inv.items()]
            state = PlayerState(inventory)
            if state.has["KS"] > 8 and "standard-core" in modes:
                state.has["KS"] += 2 * (state.has["KS"] - 8)
            if p not in reach:
                reach[p] = {}
            reach[p][modes] = Map.get_reachable_areas(state, modes, spawn, False)
        # merge semantics: write back only the recomputed players, so this slow
        # compute can't clobber other players' entries written meanwhile
        Cache.set_reachable(game_id, {p: reach[p] for p in need_reach_updates})
    # iterate the rendered players, not the cache: the merge-semantics writeback
    # above never removes entries, so reach can carry pids (or mode sets) that
    # players/need_reach_updates knows nothing about
    for p in players:
        if modes in reach.get(p, {}):
            players[p]["reachable"] = reach[p][modes]
    res = {"players": players} # , "items": items
    if gid_changed:
        res["newGid"] = game_id
    return json_resp(res)
@bp.route('/tracker/game/<int:game_id>/fetch/items/<int:player_id>')
def tracker_get_items_update(game_id, player_id):
    items, _ = Cache.get_items(game_id, player_id)
    if not items:
        coords = Cache.get_have(game_id)
        game = Game.with_id(game_id)
        if not coords:
            if not game:
                return json_resp({"error": "Game %s not found" % game_id}, 404)
            coords = { p.pid(): p.have_coords() for p in game.visible_players() }
            Cache.set_have(game_id, coords)
        items, _ = _get_item_tracker_items(coords.get(player_id, []), game, player_id)
    return json_resp(items)
def _get_item_tracker_items(coords, game, player=1):
    relics = game.relics_for(player)
    data = {
        'skills': set(),
        'trees': set(),
        'events': set(),
        'shards': {'wv': 0, 'gs': 0, 'ss': 0},
        'maps': 0,
        'relics_found': set(),
        'relics': relics,
        'teleporters': set()
    }
    inventories = game.get_inventories(game.visible_players(), True, True)

    inv = [v for k,v in inventories.items() if k != "unshared"][0] if game.mode == MultiplayerGameType.SHARED else inventories["unshared"][player]
    for ((pcode, pid), count) in inv.items():
        p = Pickup.n(pcode, pid)
        if not p:
            log.warn("couldn't build pickup %s|%s" % (pcode, pid))
            continue
        if pcode == "SK":
            data['skills'].add(p.name)
        elif pcode == "TP":
            data['teleporters'].add(p.name.replace(" teleporter", ""))
        elif pcode == "EV":
            data['events'].add(p.name)
        elif pcode == "RB":
            bid = int(pid)
            if bid == 17:
                data['shards']['wv'] = count
            elif bid == 19:
                data['shards']['gs'] = count
            elif bid == 21:
                data['shards']['ss'] = count
            elif bid > 910 and bid < 922:
                data['relics_found'].add(p.name.replace(" Relic", ""))
            elif bid >= 900 and bid < 910:
                data['trees'].add(p.name.replace(" Tree", ""))
    if data['shards']['wv'] > 2:
        data['events'].add("Water Vein")
    if data['shards']['gs'] > 2:
        data['events'].add("Gumon Seal")
    if data['shards']['ss'] > 2:
        data['events'].add("Sunstone")
    for thing in ['trees', 'skills', 'events', 'relics_found', 'teleporters']:
        data[thing] = list(data[thing])
    data['maps'] = len([1 for c in coords if c in range(24, 60, 4)])
    Cache.set_items(game.key.id(), player, (data, inventories), game.is_race)
    return data, inventories
@bp.route('/tracker/game/<int:game_id>/fetch/player/<int:player_id>/seed')
def tracker_fetch_seed(game_id, player_id):
    game = Game.with_id(game_id)
    if not game or not game.params:
        return json_resp({"error": "game %s not found!" % game_id}, 404)
    player = game.player(player_id, False)
    if not player or player.is_ap_shadow():
        return json_resp({"error": "game %s does not contain player %s!" % (game_id, player_id)}, 404)
    res = {"seed": {}, 'name': player.name()}
    params = game.fetch_params()
    if Variation.BINGO in params.variations:
        bingo = BingoGameData.with_id(game_id)
        if not bingo:
            return json_resp({"error": "no bingo data found for game %s" % game_id}, 404)
        if not bingo.boards:
            team = bingo.team(player_id, cap_only=False)
            if not team:
                return json_resp({"error": "No team found for player %s!" % player_id}, 404)
            team = team.pids()
            player_id = team.index(player_id) + 1
    seed_lines = params.get_seed_data(player_id)
    shadow = None
    if getattr(params, "ap_mode", False):
        # scouted labels for the reserved AP lines; without them the
        # tooltips say "AP Item #n" forever
        seed_lines = params.ap_named(seed_lines, player_id, game_id)
        shadow = str(int(params.players) + int(player_id))
    names = {}
    if any(l[1] == "MW" for l in seed_lines):
        for part in (player.mw_names_field() or "").split(";"):
            pid_s, dot, nm = part.partition(".")
            if dot and pid_s.isdigit():
                names[int(pid_s)] = nm

    def owned(owner, item):
        # in-game shape: bare for your own, "<name>'s" for anyone else's
        if owner == player_id:
            return item
        return "%s's %s" % (names.get(owner, "Player %s" % owner), item)

    for line in seed_lines:
        coords, code, id = line[0], line[1], line[2]
        if is_mw_manifest_loc(coords):
            continue  # multiworld slot manifests aren't map locations
        if code == "MW":
            parts = id.split(",", 5)
            if shadow is not None and len(parts) == 6 and parts[0] == shadow:
                to, icode, iid = parts[2], parts[4], parts[5]
                item = iid if icode == "AP" else Pickup.name(icode, iid)
                if to.startswith("P") and to[1:].isdigit():
                    res["seed"][coords] = owned(int(to[1:]), item)
                elif to:
                    res["seed"][coords] = "%s's %s" % (to, item)
                else:
                    res["seed"][coords] = item  # nobody has scouted it yet
                continue
            parts = id.split(",", 3)
            if len(parts) == 4 and parts[0].isdigit():
                res["seed"][coords] = owned(int(parts[0]), Pickup.name(parts[2], parts[3]))
                continue
        res["seed"][coords] = Pickup.name(code, id)
    return json_resp(res)
@bp.route('/tracker/game/<int:game_id>/items')
@bp.route('/tracker/game/<int:game_id>/<int:player_id>/items')
def tracker_item_tracker(game_id, player_id=1):
    game = Game.with_id(game_id)
    template_values = template_vals("ItemTracker", "Game %s" % game_id, User.get())
    if game and Variation.RACE in game.fetch_params().variations and not template_values["race_wl"]:
        return text_resp("Access forbidden", 401)
    template_values['game_id'] = game_id
    template_values['player_id'] = player_id
    return render_template(INDEX_TEMPLATE, **template_values)
@bp.route('/tracker/spectate/<name>') # LatestMap
def get_map_by_name(name):
    latest = User.latest_game(name)
    if latest:
        return redirect("%s?%s" % (url_for('tracker.tracker_show_map', game_id=latest), "&".join(["usermap=" + name] + ["%s=%s" % (k, v) for k, v in request.args.items()])))
    else:
        return text_resp("User not found or had no games on record", 404)
@bp.route('/reset/<int:game_id>') # handler=ResetGame
def reset_game(game_id):
    game = Game.with_id(game_id)
    if not game:
        return text_resp("Game %s not found!" % game_id, 404)
    user = User.get()
    if User.is_admin() or (user and user.key == game.creator):
        game.reset()
        return text_resp("Game reset successfully")
    else:
        return text_resp("Can't restart a game you didn't create...", 401)
@bp.route('/transfer/<int:game_id>/<int:player_id>') # ResetAndTransfer
def reset_and_transfer_game(game_id, player_id):
    # Was dead code (mis-indented under the not-found return, with new_owner undefined);
    # rebuilt 2026-07-19: transfers ownership to the user attached to player <player_id>.
    game = Game.with_id(game_id)
    if not game:
        return text_resp("Game %s not found!" % game_id, 404)
    user = User.get()
    if not (User.is_admin() or (user and user.key == game.creator)):
        return text_resp("Can't restart a game you didn't create...", 401)
    p = game.player(player_id)
    new_user = p.user.get() if p and p.user else None
    if not new_user:
        return text_resp("Couldn't find a user attached to player %s" % player_id, 404)
    game.creator = new_user.key
    game.put()
    game.reset()
    return text_resp("Game reset; ownership transferred from %s to %s" % (user.name if user else "admin", new_user.name))
@bp.route('/tracker')
def tracker():
    return redirect("https://github.com/jeflefou/OriDETracker/releases/tag/v3.3.2")
