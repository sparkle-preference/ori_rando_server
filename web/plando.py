"""Plandomizer seeds: upload, edit, browse, download."""
import json
import logging as log
from collections import Counter

from flask import Blueprint, redirect, render_template, request, url_for

from enums import MultiplayerGameType
from models import Game, LegacyUser, Seed, User
from seedbuilder.seedparams import SeedGenParams
from reachable import Map, PlayerState
from util import (INDEX_TEMPLATE, clone_entity, param_flag, param_val, parse_fass,
                  template_vals)
from web.responses import code_resp, json_resp, make_resp, text_download, text_resp

bp = Blueprint("plando", __name__)


@bp.route('/plando/<seed_name>/upload', methods=['POST'])   #PlandoUpload
def plando_upload(seed_name): 
    user = User.get()
    if not user:
        log.error("Error: unauthenticated upload attempt")
        return code_resp(401)
    seed_data = json.loads(request.form.get("seed"))
    old_name = seed_data["oldName"]
    old_seed = user.plando(old_name)
    if old_seed:
        res = old_seed.update(seed_data)
    else:
        res = Seed.new(seed_data)
    return text_resp(str(res))

@bp.route('/plando/<seed_name>/edit')   #PlandoEdit
def plando_edit(seed_name):
    user = User.get()
    template_values = template_vals("PlandoBuilder", "Plando Editor: %s" % (seed_name), user)
    template_values['seed_name'] = seed_name
    if user:
        seed = user.plando(seed_name)
        template_values['authed'] = "True"
        if seed:
            template_values['seed_desc'] = seed.description
            template_values['seed_hidden'] = seed.hidden or False
            template_values['seed_data'] = seed.get_plando_json()
    return render_template(INDEX_TEMPLATE, **template_values)

@bp.route('/plando/<seed_name>/delete')   #PlandoDelete
def plando_delete(seed_name):
    user = User.get()
    if not user:
        log.error("Error: unauthenticated delete attempt")
        return code_resp(401)
    seed = user.plando(seed_name)
    if not seed:
        log.error("couldn't find seed %s when trying to delete!" % seed_name)
        return code_resp(404)
    seed.key.delete()
    return redirect(url_for("plando.plando_author_index", author_name=user.name))

@bp.route('/plando/<seed_name>/rename/<new_name>')   #PlandoRename
def plando_rename(seed_name, new_name):
    user = User.get()
    if not user:
        return text_resp("Error: unauthenticated rename attempt", 401)
    old_seed = user.plando(seed_name)
    if not old_seed:
        return text_resp("couldn't find old seed when trying to rename!", 404)
    new_seed = clone_entity(old_seed, id="%s:%s" % (user.key.id(), new_name), name=new_name)
    if new_seed.put():
        if not param_flag("cp"):
            old_seed.key.delete()
        return redirect(url_for("plando.plando_view", author_name=user.name, seed_name=new_name))
    else:
        return text_resp("Failed to rename seed", 500)

@bp.route('/plando/<seed_name>/hideToggle')   #PlandoToggleHide
def plando_toggle_hide(seed_name):
    user = User.get()
    if not user:
        log.error("Error: unauthenticated hide attempt")
        return code_resp(401)
    seed = user.plando(seed_name)
    if not seed:
        log.error("couldn't find seed when trying to hide!")
        return code_resp(404)
    seed.hidden = not (seed.hidden or False)
    seed.put()
    return redirect(url_for("plando.plando_view", author_name=user.name, seed_name=seed_name))

@bp.route('/plando/<author_name>/<seed_name>/download') # PlandoDownload
def plando_download(author_name, seed_name):
    seed = Seed.get(author_name, seed_name)
    if seed:
        if seed.hidden:
            user = User.get()
            if not user or user.key != seed.author_key:
                return text_resp("seed %s (by user %s) not found" % (seed_name, author_name), 404)
        params = SeedGenParams.from_plando(seed, param_flag("tracking"))
        url = url_for("main_page", param_id=params.key.id())
        if params.tracking:
            game = Game.from_params(params, param_val("game_id"))
            url += "&game_id=%s" % game.key.id()
        return redirect(url)
    else:
        return text_resp("seed %s (by user %s) not found" % (seed_name, author_name), 404)


@bp.route('/plando/<author_name>/<seed_name>/spoiler') # PlandoSpoiler
def plando_spoiler(author_name, seed_name):
    seed = Seed.get(author_name, seed_name)
    if seed and seed.hidden:
        user = User.get()
        if not user or user.key != seed.author_key:
            seed = None
    if not seed or not seed.spoiler:
        return text_resp("no spoiler for seed %s (by user %s)" % (seed_name, author_name), 404)
    if param_flag("download"):
        return text_download(seed.spoiler.replace("\n", "\r\n"), "%s_spoiler.txt" % seed_name)
    return text_resp(seed.spoiler)


@bp.route('/plando/<author_name>/<seed_name>/') # PlandoView,
def plando_view(author_name, seed_name):
    authed = False
    user = User.get()
    seed = Seed.get(author_name, seed_name)
    if seed:
        if user and user.key == seed.author_key:
            authed = True
        template_values = template_vals("SeedDisplayPage", "%s by %s" % (seed_name, author_name), user)
        template_values.update({'players': seed.players, 'seed_data': seed.get_plando_json(),
            'seed_name': seed_name, 'author': author_name, 'authed': authed,
            'seed_desc': seed.description, 'game_id': Game.get_open_gid(),
            # the body is for the author's editor only; everyone else just gets the link
            'seed_has_spoiler': bool(seed.spoiler),
            'seed_spoiler': (seed.spoiler or "") if authed else ""})
        hidden = seed.hidden or False
        if not hidden or authed:
            if hidden:
                template_values['seed_hidden'] = True
            return render_template(INDEX_TEMPLATE, **template_values)
    return text_resp("seed %s (by user %s) not found" % (seed_name, author_name), 404)

@bp.route('/plando/reachable', methods=['POST']) #PlandoReachable
def plando_reachable():
    modes = json.loads(request.form.get("modes"))
    codes = []
    for item, count in json.loads(request.form.get("inventory")).items():
        codes.append(tuple(item.split("|") + [count, False]))
    areas = {}
    for area, reqs in Map.get_reachable_areas(PlayerState(codes), modes).items():
        areas[area] = [{item: count for (item, count) in req.cnt.items()} for req in reqs if len(req.cnt)]
    return json_resp(areas)

@bp.route('/plando/fillgen') #PlandoFillGen
def plando_fillgen():
    """Fill a plando's empty locations. Answers {player: seed text}: one world
    for everyone when the fill is cloned, one per player in multiworld."""
    qparams = request.args
    try:
        preplaced = parse_fass(qparams.get('fass'))
    except ValueError:
        return text_resp("a forced assignment named a location that isn't a number", 422)
    param_key = SeedGenParams.from_url(qparams)
    params = param_key.get()
    if not params.generate(preplaced=preplaced):
        return code_resp(422)
    worlds = range(1, params.players + 1) if params.sync.mode == MultiplayerGameType.MULTIWORLD else [1]
    return json_resp({str(p): params.get_seed(p) for p in worlds})

def count_plandos(seed):
    if seed.author_key:
        return seed.author_key
    if seed.legacy_author_key:
        return seed.legacy_author_key
    return seed.author

PLANDO_DISCLAIMER = """<div><i>
(If one or more of your plandos are missing, please reach out to @Eiko or @Skyedelaciel in the <a target="_blank" href="/discord">Ori Discord</a> - we have the data, we just don't know whose seeds are whose for a small number of users)
</i></div>"""
@bp.route('/plandos')      #AllAuthors
def plando_index():
    out = '<html><head><title>All Plando Authors</title></head><body><h5>All Seeds</h5><ul style="list-style-type:none;padding:5px">'
    authors = Counter(count_plandos(seed) for seed in Seed.query(Seed.hidden != True, projection=[Seed.author, Seed.author_key, Seed.legacy_author_key]))
    for author, cnt in authors.most_common():
        if cnt > 0:
            if not isinstance(author, str):
                if author.get():
                    author = author.get().name
                else:
                    author = str(author.id() if author.id() else author)
            url = "/plando/%s" % author
            out += '<li style="padding:2px"><a href="%s">%s</a> (%s plandos)</li>' % (url, author, cnt)
    out += f"</ul>{PLANDO_DISCLAIMER}</body></html>"
    return make_resp(out)

@bp.route('/plando/<author_name>')
def plando_author_index(author_name):
    start_at = int(param_val("offset") or 0)
    owner = False
    user = User.get()
    author = User.get_by_name(author_name)
    proj = [Seed.name, Seed.description, Seed.players, Seed.flagline]
    if author:
        author_name = author.name
        owner = user and user.key.id() == author.key.id()
        if owner:
            query = Seed.query(Seed.author_key == author.key, projection=[Seed.hidden, *proj])
        else:
            query = Seed.query(Seed.author_key == author.key, Seed.hidden != True, projection=proj)
    else:
        legacy_author = LegacyUser.get_by_name(author_name)
        if legacy_author:
            query = Seed.query(Seed.legacy_author_key == legacy_author.key, Seed.hidden != True, projection=proj)
        else: 
            query = Seed.query(Seed.author == author_name, Seed.hidden != True, projection=proj)
    seeds = query.fetch(limit=int(param_val("limit") or 1), offset=start_at) if start_at else query.fetch()
    if len(seeds):
        out = '<html><head><title>Seeds by %s</title></head><body><div>Seeds by %s:</div><ul style="list-style-type:none;padding:5px">' % (author_name, author_name)
        for seed in sorted(seeds, key=lambda s: s.name):
            url = url_for("plando.plando_view", author_name=author_name, seed_name=seed.name)
            out += f'<li style="padding:2px"><a href="{url}">{seed.name}</a>: {seed.description.partition("\n")[0]} ({seed.players} players, {seed.flagline})'
            if owner:
                out += f' <a href="{url_for("plando.plando_edit", seed_name=seed.name)}">Edit</a>'
                if seed.hidden:
                    out += " (hidden)"
            out += "</li>"
        out += f"</ul>{PLANDO_DISCLAIMER}</body></html>"
        return make_resp(out)
    else:
        if owner:
            return make_resp(f"<html><body>You haven't made any seeds yet! <a href='{url_for('plando.plando_edit', seed_name="newSeed")}'>Start a new seed</a></body>{PLANDO_DISCLAIMER}</html>")
        else:
            return make_resp(f"<html><body>No seeds by user {author_name}</body>{PLANDO_DISCLAIMER}</html>")
