"""Saved seed params -- "presets" to a user, SSPs in the code.

A preset is the seedgen form minus the multiplayer tab and the seed, so the same
one rolls solo, in co-op, or as one world of a multiworld.
"""
import json
import random

from flask import Blueprint, redirect, request, url_for
from google.cloud import ndb

from enums import Variation
from models import Game, SavedSeedParams, Seed, User
from seedbuilder.seedparams import SeedGenParams, seed_mode_problem
from web.bingo import bingo_board_url
from web.extensions import oidc
from web.responses import json_resp, make_resp, text_resp

bp = Blueprint("presets", __name__)


# --- presets (SSPs in code) --------------------------------------------------
# A preset is the seedgen form minus the multiplayer tab and the seed, so the
# same one rolls solo, in co-op, or as one world of a multiworld.


def _ssp_or_404(owner_name, name):
    ssp = SavedSeedParams.get(owner_name, name)
    if not ssp:
        return None, text_resp("no preset named %s by %s" % (name, owner_name), 404)
    if ssp.hidden and not ssp.owned_by(User.get()):
        return None, text_resp("no preset named %s by %s" % (name, owner_name), 404)
    return ssp, None


@bp.route('/preset/save', methods=['POST'])
def ssp_save():
    user = User.get()
    if not user:
        return text_resp("log in to save presets", 401)
    body = json.loads(request.form.get("preset") or "{}")
    name = (body.get("name") or "").strip()
    problem = SavedSeedParams.name_problem(name) or SavedSeedParams.desc_problem(body.get("desc"))
    if problem:
        return text_resp(problem, 422)
    ssp = user.saved_params(name) or SavedSeedParams(id="%s:%s" % (user.key.id(), name))
    ssp.populate(
        name=name,
        owner_key=user.key,
        # absent means leave it: an options-only save must not blank the description
        description=((body.get("desc") or "").strip() or None) if "desc" in body else ssp.description,
        settings=SavedSeedParams.settings_from(body.get("params") or {}, body.get("world") or 1),
        hidden=bool(body.get("hidden", ssp.hidden)),
    )
    ssp.put()
    return json_resp({"name": ssp.name, "owner": user.name})


@bp.route('/preset/list')
def ssp_list():
    """Presets for the seedgen page's dropdown. Anonymous users get an empty list
    rather than a 401: the page greys the controls out instead of erroring."""
    user = User.get()
    if not user:
        return json_resp({"owner": None, "hasLatest": False, "restoreLastSeed": True, "settings": []})
    rows = sorted(SavedSeedParams.query(SavedSeedParams.owner_key == user.key),
                  key=lambda s: (s.name or "").lower())
    # what /preset/latest and /reroll both need, so a lit button is one that works
    last = user.games[-1].get() if user.games else None
    # the blob rides along so the page can match a loaded form against a preset
    return json_resp({"owner": user.name,
                      "hasLatest": bool(last and last.params),
                      # whether the page opens on that last seed. Off still keeps it:
                      # Last Seed stays pickable and /reroll still has something to reroll
                      "restoreLastSeed": user.setting("restoreLastSeed"),
                      "settings": [{"name": s.name, "desc": s.description,
                                    "hidden": s.hidden, "blob": s.settings} for s in rows]})


@bp.route('/preset/latest')
def ssp_latest():
    """The user's last game's options, lobby included.

    Alone among the loads this keeps players/coop/AP: it is never assigned to someone else's world."""
    user = User.get()
    if not user:
        return text_resp("log in to load your last seed's options", 401)
    if not user.games:
        return text_resp("you have no games to take options from", 404)
    game = user.games[-1].get()
    if not game or not game.params:
        return text_resp("your last game has no options to load", 404)
    settings = game.fetch_params().to_json()
    # the page drops these too; a preset never carries a seed or a finished seed's output
    for output_only in ("seed", "flagLine", "isPlando", "spoilers", "teamStr"):
        settings.pop(output_only, None)
    return json_resp({"name": "Last Seed", "owner": None, "withLobby": True,
                      "settings": settings})


@bp.route('/preset/<owner_name>/<name>')
def ssp_get(owner_name, name):
    """The preset itself. A share link COPIES it into the opener's form; it does
    not stay bound to this entity, so editing yours never changes what someone
    else's link rolls."""
    ssp, err = _ssp_or_404(owner_name, name)
    return err or json_resp({"name": ssp.name, "owner": owner_name,
                             "desc": ssp.description, "settings": ssp.settings})


@bp.route('/preset/<owner_name>/<name>/roll')
def ssp_roll(owner_name, name):
    ssp, err = _ssp_or_404(owner_name, name)
    if err:
        return err
    settings = dict(ssp.settings or {})
    settings["seed"] = str(random.randint(0, 1000000000))
    settings["players"] = 1      # a setting says nothing about a lobby
    param_key = SeedGenParams.from_json(settings)
    if not param_key:
        return text_resp("this preset can no longer be built", 422)
    params = param_key.get()
    problem = seed_mode_problem(params)
    if problem:
        return text_resp(problem, 409)
    if not params.generate():
        return text_resp("this preset can no longer be rolled: no completable seed "
                         "could be built from it", 422)
    if not params.tracking:
        return redirect("%s?param_id=%s" % (url_for('main_page'), param_key.id()))
    game = Game.from_params(params)
    if Variation.BINGO in params.variations:
        return redirect(bingo_board_url(game, params))
    return redirect("%s?param_id=%s&game_id=%s"
                    % (url_for('main_page'), param_key.id(), game.key.id()))


def _preset_body():
    """The posted json as a dict, or (None, response). Parses behind the login
    check and tolerates any shape, so a bad body is a 400 rather than a 500."""
    if not User.get():
        return None, text_resp("log in to manage your presets", 401)
    try:
        body = json.loads(request.form.get("preset") or "{}")
    except ValueError:
        return None, text_resp("could not read that request", 400)
    if not isinstance(body, dict):
        return None, text_resp("could not read that request", 400)
    return body, None


def _str_field(body, key, default=""):
    value = body.get(key)
    return (value if isinstance(value, str) else default).strip()


def _rename_preset_body(user, old_name, new_name, desc, hidden):
    """Move a preset to a new name, returning a problem string or None.

    The id carries the name, so this is a create plus a delete across two keys,
    and the "is the target free?" read has to sit in the same transaction."""
    ssp = user.saved_params(old_name)
    if not ssp:
        return "no preset named %s" % old_name
    if user.saved_params(new_name):
        return "you already have a preset named %s" % new_name
    SavedSeedParams(id="%s:%s" % (user.key.id(), new_name), name=new_name,
                    owner_key=user.key, description=desc,
                    settings=ssp.settings, hidden=hidden).put()
    ssp.key.delete()
    return None


_rename_preset = ndb.transactional(retries=5)(_rename_preset_body)


def _my_preset(name):
    """The caller's own preset by name, or (None, None, response). Ownership is
    the lookup: saved_params only returns presets keyed to this user."""
    user = User.get()
    if not user:
        return None, None, text_resp("log in to manage your presets", 401)
    ssp = user.saved_params(name)
    if not ssp:
        return None, None, text_resp("no preset named %s" % name, 404)
    return user, ssp, None


@bp.route('/preset/edit', methods=['POST'])
def preset_edit():
    """Rename / describe / hide, without touching the saved options."""
    body, err = _preset_body()
    if err:
        return err
    user, ssp, err = _my_preset(_str_field(body, "name"))
    if err:
        return err
    new_name = _str_field(body, "newName") or ssp.name
    problem = SavedSeedParams.name_problem(new_name) or SavedSeedParams.desc_problem(_str_field(body, "desc"))
    if problem:
        return text_resp(problem, 422)
    desc = _str_field(body, "desc") or None
    hidden = bool(body.get("hidden", ssp.hidden))
    if new_name == ssp.name:
        ssp.description, ssp.hidden = desc, hidden
        ssp.put()
        return json_resp({"name": ssp.name})
    problem = _rename_preset(user, ssp.name, new_name, desc, hidden)
    if problem:
        return text_resp(problem, 409)
    return json_resp({"name": new_name})


@bp.route('/preset/delete', methods=['POST'])
def preset_delete():
    body, err = _preset_body()
    if err:
        return err
    _, ssp, err = _my_preset(_str_field(body, "name"))
    if err:
        return err
    ssp.key.delete()
    return json_resp({"deleted": ssp.name})


@bp.route('/preset/mine/<name>/delete')
@oidc.require_login
def ssp_delete(name):
    _, ssp, err = _my_preset(name)
    if err:
        return err
    ssp.key.delete()
    return redirect(url_for('presets.my_settings'))


@bp.route('/preset/mine/<name>/hideToggle')
@oidc.require_login
def ssp_hide_toggle(name):
    _, ssp, err = _my_preset(name)
    if err:
        return err
    ssp.hidden = not ssp.hidden
    ssp.put()
    return redirect(url_for('presets.my_settings'))


@bp.route('/myPresets')
@oidc.require_login
def my_settings():
    user = User.get()
    rows = sorted(SavedSeedParams.query(SavedSeedParams.owner_key == user.key),
                  key=lambda s: (s.name or "").lower())
    out = ['<html><head><title>My Presets</title></head><body>'
           '<h5>My Presets</h5>']
    if not rows:
        out.append("<p>You haven't saved any presets yet. "
                   "Save one from the <a href='/'>seed generator</a>.</p>")
    out.append('<ul style="list-style-type:none;padding:5px">')
    for ssp in rows:
        share = "%spreset/%s/%s" % (request.host_url, user.name, ssp.name)
        out.append(
            '<li style="padding:4px">'
            '<b>%s</b>%s%s<br>'
            '<a href="/preset/%s/%s/roll">roll seed</a> &middot; '
            '<a href="/?preset=%s:%s">load into the form</a> &middot; '
            '<a href="%s">share link</a> &middot; '
            '<a href="/preset/mine/%s/hideToggle">%s</a> &middot; '
            '<a href="/preset/mine/%s/delete">delete</a>'
            '</li>' % (
                ssp.name,
                " (hidden)" if ssp.hidden else "",
                (" &mdash; %s" % ssp.description) if ssp.description else "",
                user.name, ssp.name,
                user.name, ssp.name,
                share,
                ssp.name, "unhide" if ssp.hidden else "hide",
                ssp.name))
    out.append('</ul></body></html>')
    return make_resp("".join(out))
