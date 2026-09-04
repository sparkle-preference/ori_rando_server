"""Rolling a seed and everything you can download from one.

/generator/build is the form post; the rest serve a rolled seed's artifacts by
params id -- the seed itself, spoilers, Archipelago yamls, the apworld.
"""
import json
import logging as log
import random

from flask import Blueprint, redirect, request, url_for

from archipelago import build_apworld
from cache import Cache
from enums import MultiplayerGameType, Variation, presets
from models import Game, Player, User
from seedbuilder.seedparams import SeedGenParams, seed_failure_reason, seed_mode_problem
from seedbuilder.vanilla import seedtext as vanilla_seed
import util
from util import param_flag, param_val
from bingo import bingo_board_url
from web.extensions import oidc
from web.responses import json_resp, text_download, text_resp, zip_download

bp = Blueprint("generator", __name__)

# built once per process and cached; the check runs at boot in main
apworld_zip = None


@bp.route("/generator/build", methods=['GET', 'POST'])
def gen_seed_from_params():
    param_key = SeedGenParams.from_json(json.loads(request.form.get('params'))) if request.method == 'POST' else SeedGenParams.from_url(request.args)
    if not param_key:
        return text_resp("Failed to build params!", 500)
    params = param_key.get()
    problem = seed_mode_problem(params)
    if problem:
        return text_resp(problem, 409)
    if not params.generate():
        # 422 rather than 500: the request was fine, the settings were the problem
        reason = seed_failure_reason(params)
        return text_resp(reason, 422) if reason else text_resp("Failed to generate seed!", 500)
    resp = {"paramId": param_key.id(), "playerCount": params.players, "flagLine": params.flag_line(), 'seed': params.seed, "spoilers": True}
    lines = world_flag_lines(params)
    if lines:
        resp["flagLines"] = lines
    if params.tracking:
        game = Game.from_params(params, param_val("game_id"))
        resp["gameId"] = game.key.id()
    if Variation.BINGO in params.variations:
        resp["doBingoRedirect"] = True
        resp["bingoLines"] = params.bingo_lines

    return json_resp(resp)


@bp.route('/generator/json')
def gen_seed_from_url():
    # from_url's own failures are log-only; a bot cannot read those
    group = param_val("logic_mode")
    if group and group.capitalize() not in presets:
        return json_resp({"error": "Unknown logic_mode %r; expected one of %s"
                                   % (group, ", ".join(sorted(presets)))}, 409)
    param_key = SeedGenParams.from_url(request.args)
    verbose_paths = param_val("verbose_paths") is not None
    if param_key:
        params = param_key.get()
        problem = seed_mode_problem(params)
        if problem:
            return json_resp({"error": problem}, 409)
        if params.generate(preplaced={}):
            players = []
            resp = {}
            if params.tracking:
                game = Game.from_params(params, param_val("game_id"))
                key = game.key
                resp["map_url"] = url_for("tracker.tracker_show_map", game_id=key.id())
                resp["history_url"] = url_for("tracker.game_show_history", game_id=key.id())
            for p in range(1, params.players + 1):
                if params.tracking:
                    seed = params.get_seed(p, key.id(), verbose_paths)
                else:
                    seed = params.get_seed(p, verbose_paths=verbose_paths)
                spoiler = params.get_spoiler(p).replace("\n", "\r\n")
                players.append({"seed": seed, "spoiler": spoiler, "spoiler_url": url_for('generator.get_spoiler_from_params', params_id=param_key.id(), player=p)})
            resp["players"] = players
            return json_resp(resp)
        reason = seed_failure_reason(params)
        if reason:
            return json_resp({"error": reason}, 422)
    log.error("param gen failed")
    return json_resp({"error": "param gen failed"}, 500)


def ap_seed_not_ready(params, game_id):
    """Why an AP seed download would come out unannotated, or None when it
    wouldn't. A seed file is a snapshot: downloaded before every world's
    scouts persisted, it keeps "AP Item #n" and the rolled zones forever,
    and nothing detects it. Gates on the persisted scout rows, not the live
    socket -- a room that died after scouting still annotates fully."""
    if not getattr(params, "ap_mode", False):
        return None
    if not game_id:
        return "This Archipelago seed has no game attached; download it from its seed page"
    from ap_models import APLink
    link = APLink.with_id(game_id)
    if not link:
        return "Connect the Archipelago room first, then download (item names bake in at download time)"
    worlds = int(params.players)
    totals = list(link.name_totals) + [-1] * (worlds - len(link.name_totals))
    counts = list(link.name_counts) + [0] * (worlds - len(link.name_counts))
    if any(t < 0 for t in totals[:worlds]) or any(c < t for c, t in zip(counts[:worlds], totals[:worlds])):
        done = sum(max(c, 0) for c in counts[:worlds])
        total = sum(t for t in totals[:worlds] if t > 0)
        return "Waiting for the room's location scouts (%s/%s item names resolved)" % (done, total or "?")
    return None


@bp.route('/generator/seed/<params_id>')
def load_seed_from_params(params_id):
    verbose_paths = param_flag("verbose_paths")
    params = SeedGenParams.with_id(params_id)
    if params:
        pid = int(param_val("player_id") or 1)
        game_id = param_val("game_id")
        if not param_flag("force"):
            not_ready = ap_seed_not_ready(params, game_id)
            if not_ready:
                return json_resp({"error": not_ready, "retryable": True}, 409)
        if params.tracking and game_id:
            seed = params.get_seed(pid, game_id, verbose_paths)
            game = Game.with_id(game_id)
            user = User.get()
            if game and user:
                Player.claim_user_txn(game.player(pid).key, user.key)
                if game.mode == MultiplayerGameType.MULTIWORLD:
                    # names ride the tick output: rebuild it for everyone
                    Cache.clear_names(int(game_id))
                    for p in game.player_nums():
                        Cache.clear_seen_checksum((int(game_id), p))
                if game.key not in user.games:
                    user.games.append(game.key)
                    Cache.set_latest_game(user.name, game.key.id())
                    user.put()
        else:
            seed = params.get_seed(pid, verbose_paths=verbose_paths)
        # a dev box is still a real site; ?text is the way to read a seed in the browser
        if not param_flag("text"):
            return text_download(seed, 'randomizer.bfr')
        return text_resp(seed)
    else:
        return text_resp("Param %s not found" % params_id, 404)


@bp.route('/generator/spoiler/<params_id>')
def get_spoiler_from_params(params_id):
    params = SeedGenParams.with_id(params_id)
    if params:
        player = int(param_val("player_id") or 1)
        spoiler = params.get_spoiler(player, game_id=param_val("game_id"))
        if param_flag("download"):
            spoiler = spoiler.replace("\n", "\r\n")
            return text_download(spoiler, 'spoiler.txt')
        return text_resp(spoiler)
    else:
        return text_resp("Param %s not found" % params_id, 404)


@bp.route('/generator/apyaml/<params_id>/<int:world_id>')
def get_apyaml_from_params(params_id, world_id):
    if not util.ARCHIPELAGO:
        return text_resp("Archipelago support is not enabled", 404)
    params = SeedGenParams.with_id(params_id)
    if not params or not params.ap_mode:
        return text_resp("No Archipelago params %s found" % params_id, 404)
    if world_id < 1 or world_id > params.players:
        return text_resp("Param %s has no world %s" % (params_id, world_id), 404)
    return text_download(params.to_ap_yaml(world_id), 'ap_world_%s.yaml' % world_id)


@bp.route('/generator/apyamls/<params_id>')
def get_apyamls_from_params(params_id):
    # every world in one multi-document yaml
    if not util.ARCHIPELAGO:
        return text_resp("Archipelago support is not enabled", 404)
    params = SeedGenParams.with_id(params_id)
    if not params or not params.ap_mode:
        return text_resp("No Archipelago params %s found" % params_id, 404)
    worlds = [params.to_ap_yaml(w) for w in range(1, params.players + 1)]
    return text_download("---\n".join(worlds), 'ap_worlds_%s.yaml' % params_id)


@bp.route('/generator/apworld')
def get_apworld():
    # a session host needs this even though they never touch the seed page
    if not util.ARCHIPELAGO:
        return text_resp("Archipelago support is not enabled", 404)
    global apworld_zip
    if apworld_zip is None:
        # raises on a package that fails its own checks: 500 beats a dud
        apworld_zip = build_apworld.zip_bytes()
    # the filename IS the module name Archipelago imports (worlds/__init__.py
    # takes Path(path).stem), so anything but oride.apworld fails to load
    return zip_download(apworld_zip, 'oride.apworld')


@bp.route('/generator/aux_spoiler/<params_id>')
def get_aux_spoiler_from_params(params_id):
    params = SeedGenParams.with_id(params_id)
    if params:
        player = int(param_val("player_id") or 1)
        exclude = (param_val("exclude") or "EX KS AC EC HC MS").split(" ") if param_val("exclude") != "" else []
        by_zone = param_flag("by_zone")
        # optional game_id: AP seeds' reserved lines get their scouted item
        # names, same as the seed file (no game, no names -- never an error)
        spoiler = params.get_aux_spoiler(exclude, by_zone, player,
                                         game_id=param_val("game_id"))
        if param_flag("download"):
            return text_download(spoiler.replace("\n", "\r\n"), 'spoiler.txt')
        return text_resp(spoiler)
    else:
        return text_resp("Param %s not found" % params_id, 404)


def world_flag_lines(params):
    """One flag line per world, or None when a single line says it all."""
    if not getattr(params, "world_settings", None):
        return None
    return [params.world_params(p).flag_line() for p in range(1, (params.players or 1) + 1)]


@bp.route('/generator/metadata/<param_id>')
def get_metadata_no_gid(param_id):
    return get_param_metadata(param_id, None)


@bp.route('/generator/metadata/<param_id>/<int:game_id>')
def get_param_metadata(param_id, game_id):
    params = SeedGenParams.with_id(param_id)
    if not params:
        return json_resp({"error": "No params found"}, 404)
    res = params.to_json()
    lines = world_flag_lines(params)
    if lines:
        res["flagLines"] = lines
    if params.tracking and not game_id:
        game = Game.from_params(params)
        res["gameId"] = game.key.id()
    return json_resp(res)


@bp.route('/vanilla')
def get_vanilla_seed():
    return text_download(vanilla_seed, "randomizer.bfr")


def _reroll(params):
    """Same settings, fresh seed. Returns (new_params, game, error_response)."""
    old = params.to_json()
    old['seed'] = str(random.randint(0, 1000000000))
    new_params = SeedGenParams.from_json(old).get()
    problem = seed_mode_problem(new_params)
    if problem:
        return None, None, text_resp(problem, 409)
    if not new_params.generate():
        reason = seed_failure_reason(new_params)
        return None, None, (text_resp(reason, 422) if reason else text_resp("Failed to generate seed!", 500))
    return new_params, Game.from_params(new_params), None


@bp.route('/reroll')
@oidc.require_login
def reroll_seed():
    user = User.get()
    if not user.games:
        return text_resp("no games found", 404)
    game_key = user.games[-1]
    old_game = game_key.get()
    if not old_game.params:
        return text_resp("latest game does not have params", 404)
    new_params, game, err = _reroll(old_game.fetch_params())
    if err:
        return err
    if Variation.BINGO in new_params.variations:
        b = old_game.bingo_data.get() if old_game.bingo_data else None
        return redirect(bingo_board_url(game, new_params, disc=b.discovery if b else None))
    return redirect("%s?param_id=%s&game_id=%s" % (url_for('main_page'), new_params.key.id(), game.key.id()))
