"""Saved seed params -- "presets" to a user, SSPs in the code.

A preset is the seedgen form minus the multiplayer tab and the seed, so the same
one rolls solo, in co-op, or as one world of a multiworld.
"""
import json
import random
from html import escape

from flask import Blueprint, redirect, request, url_for
from google.cloud import ndb

from enums import Variation
from models import Game, SavedSeedParams, Seed, User
from seedbuilder.seedparams import SeedGenParams, seed_mode_problem
from bingo import bingo_board_url
from web.extensions import oidc
from util import param_flag, utcnow
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


# One paste holds every preset a person owns, so a new account or a second site
# can be seeded from an old one. The blob is the stored form, not the wire form.
EXPORT_FORMAT = 1
IMPORT_MAX = 200


def _export_doc(user, rows):
    return {"orirando_presets": EXPORT_FORMAT,
            "owner": user.name,
            "exported": utcnow().isoformat() + "Z",
            "presets": [{"name": s.name, "desc": s.description,
                         "hidden": bool(s.hidden), "settings": s.settings} for s in rows]}


def _pasted_presets(body):
    """The presets in a pasted document, whatever shape it arrived in: a whole
    export, a bare list, or the single object a share link serves."""
    if isinstance(body, list):
        return body
    if isinstance(body, dict):
        return body["presets"] if isinstance(body.get("presets"), list) else [body]
    return None


def _owned_presets(user):
    return sorted(SavedSeedParams.query(SavedSeedParams.owner_key == user.key),
                  key=lambda s: (s.name or "").lower())


# The clipboard needs a focused window and a secure context, and the box is
# selected either way, so a refusal says what to press instead of going quiet.
TRANSFER_HTML = """
<hr><h5>Copy out</h5>
<p>Everything above, as JSON. Paste it into the box below on another account to
get the same presets there.</p>
<textarea id="export" readonly rows="8" style="width:100%%;font-family:monospace">%s</textarea>
<p><button type="button" id="copyExport">Copy to clipboard</button>
 &middot; <a href="/preset/export">open as a file</a></p>
<script>
document.getElementById('copyExport').onclick = function() {
  var box = document.getElementById('export'), btn = this;
  box.select();
  var say = function(msg) {
    btn.textContent = msg;
    setTimeout(function() { btn.textContent = 'Copy to clipboard'; }, 3000);
  };
  if (navigator.clipboard) {
    navigator.clipboard.writeText(box.value).then(
      function() { say('Copied'); }, function() { say('Press Ctrl+C'); });
  } else {
    say('Press Ctrl+C');
  }
};
</script>
<h5>Paste in</h5>
<form method="POST" action="/preset/import">
<textarea name="presets" rows="8" style="width:100%%;font-family:monospace"
 placeholder="Paste an export here"></textarea>
<p><label><input type="checkbox" name="overwrite" value="1">
 Replace presets I already have with the same name</label></p>
<button type="submit">Import</button>
</form>"""


@bp.route('/preset/export')
def ssp_export():
    """Every preset you own, as one JSON document to copy out."""
    user = User.get()
    if not user:
        return text_resp("log in to export your presets", 401)
    return json_resp(json.dumps(_export_doc(user, _owned_presets(user)), indent=2))


@bp.route('/preset/import', methods=['POST'])
def ssp_import():
    """Take a pasted export back in. Existing names are left alone unless the
    paster asked to overwrite, so a paste can never quietly lose work."""
    user = User.get()
    if not user:
        return text_resp("log in to import presets", 401)
    try:
        entries = _pasted_presets(json.loads(request.form.get("presets") or ""))
    except ValueError as e:
        return text_resp("That isn't JSON: %s" % e, 422)
    if entries is None:
        return text_resp("Expected an export, a list of presets, or one preset.", 422)
    if len(entries) > IMPORT_MAX:
        return text_resp("That's %s presets; %s at a time." % (len(entries), IMPORT_MAX), 422)

    # the page posts the checkbox in the body, which param_flag never reads;
    # ?overwrite=1 stays available for a scripted import
    overwrite = bool(request.form.get("overwrite")) or param_flag("overwrite")
    existing = {s.name: s for s in _owned_presets(user)}
    made, replaced, skipped, refused, writes = [], [], [], [], []
    for entry in entries:
        if not isinstance(entry, dict):
            refused.append((str(entry)[:40], "not a preset"))
            continue
        name = (entry.get("name") or "").strip()
        desc = (entry.get("desc") or entry.get("description") or "").strip()
        problem = SavedSeedParams.name_problem(name) or SavedSeedParams.desc_problem(desc)
        if problem:
            refused.append((name or "(unnamed)", problem))
            continue
        was = existing.get(name)
        if was and not overwrite:
            skipped.append(name)
            continue
        ssp = was or SavedSeedParams(id="%s:%s" % (user.key.id(), name))
        # the same filter a save runs: a hand-edited paste cannot smuggle in the
        # multiplayer half, or another world's forced assignments
        blob = entry.get("settings")
        if blob is None:
            blob = entry.get("blob") or entry.get("params") or {}
        ssp.populate(name=name, owner_key=user.key,
                     description=desc or None,
                     settings=SavedSeedParams.settings_from(blob, 1),
                     hidden=bool(entry.get("hidden")))
        writes.append(ssp)
        (replaced if was else made).append(name)
    if writes:
        ndb.put_multi(writes)

    lines = []
    for label, names in (("Added", made), ("Replaced", replaced), ("Left alone", skipped)):
        if names:
            lines.append("<li>%s: %s</li>" % (label, escape(", ".join(sorted(names)))))
    for name, why in refused:
        lines.append("<li>Refused <b>%s</b>: %s</li>" % (escape(name), escape(why)))
    if not lines:
        lines.append("<li>Nothing in that paste.</li>")
    if skipped:
        lines.append("<li><i>Tick 'overwrite' to replace the ones left alone.</i></li>")
    return make_resp('<html><head><title>Presets imported</title></head><body>'
                     '<h5>Presets imported</h5><ul>%s</ul>'
                     '<a href="/myPresets">Back to my presets</a></body></html>'
                     % "".join(lines))

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
    rows = _owned_presets(user)
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
    out.append('</ul>')
    out.append(_transfer_html(user, rows))
    out.append('</body></html>')
    return make_resp("".join(out))


def _transfer_html(user, rows):
    """Copy every preset out, or paste a set back in. Plain textareas on purpose:
    what people want is something they can put in a message to a friend."""
    return TRANSFER_HTML % escape(json.dumps(_export_doc(user, rows), indent=2))
