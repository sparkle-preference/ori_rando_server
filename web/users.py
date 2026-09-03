"""Who the visitor is: the guest seat, the beta claim, and account settings.

_seat_guest is a before_app_request and its ordering is load-bearing -- it has
to register after flask-oidc's own hook so its g.oidc_user assignment wins.
create_app inits the extensions before it registers any blueprint, which is
what keeps that true.
"""
import hmac
import io
import json
import os
import re
import secrets
import zipfile
from html import escape
from uuid import uuid4

from urllib.parse import unquote

from flask import Blueprint, current_app, g, redirect, request, session, url_for

import util
from models import SITE_THEMES, URL_UNSAFE_NAME_CHARS, USER_SETTINGS, AccountLink, User
from util import debug, param_true, param_val
from web.plando import export_files_for
from web.presets import export_doc_for
from web.responses import json_resp, make_resp, text_resp, zip_download

bp = Blueprint("users", __name__)


def _guest_seat_live():
    """The three latches the guest seat runs on. Prod fails two: real OIDC wins
    outright, and a non-dev revision refuses even a stray GUEST_USERS=1."""
    return bool(util.GUEST_USERS and debug()
                and not current_app.config.get("OIDC_ENABLED"))


class _GuestUser(object):
    """The shape User.get reads off g.oidc_user, for a visitor we invented."""
    logged_in = True

    def __init__(self, sub):
        self.unique_id = sub
        self.name = "Guest-%s" % sub[-6:]
        self.email = "%s@guests.invalid" % sub


@bp.before_app_request
def _seat_guest():
    # create_app inits flask-oidc, so this registers second and its g.oidc_user wins.
    # util.GUEST_USERS is read live: tests flip it per case. Three latches, and
    # prod fails two: real OIDC wins outright, and a non-dev revision refuses
    # even a stray GUEST_USERS=1
    if not _guest_seat_live():
        return
    sub = session.get("guest_sub")
    if not sub:
        sub = "guest-%s" % uuid4().hex[:12]
        session["guest_sub"] = sub
        session.permanent = True  # a month, not a tab: rejoining keeps your games
    g.oidc_user = _GuestUser(sub)


@bp.route('/beta/claim/<secret>')
def beta_claim(secret):
    """Point this browser's guest session at the shared testing account, so
    the one tester who knows the secret keeps its presets and games while
    everyone else stays a guest. Same latches as the guest seat itself."""
    want = os.getenv("GUEST_CLAIM_SECRET")
    if not (want and _guest_seat_live()):
        return text_resp("Nothing here", 404)
    if not hmac.compare_digest(secret, want):
        return text_resp("Nothing here", 404)
    session["guest_sub"] = os.getenv("OIDC_USER_ID", "123454321234543212345")
    session.permanent = True
    return redirect("/")


def _zip_safe(name):
    return re.sub(r"[^A-Za-z0-9._-]", "_", name or "") or "unnamed"


@bp.route('/user/export')
def user_export():
    """Everything you made here, in one zip. A beta account is a cookie, and
    cookies go missing."""
    if not util.BETA_OF:
        return text_resp("Nothing here", 404)
    user = User.get()
    if not user:
        return text_resp("log in to export your things", 401)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("presets.json", json.dumps(export_doc_for(user), indent=2))
        for name, files in export_files_for(user).items():
            for filename, body in files.items():
                zf.writestr("plandos/%s/%s" % (_zip_safe(name), filename), body)
    return zip_download(buf.getvalue(), "orirando-%s.zip" % _zip_safe(user.name))


# Anyone holding the link gets the account, so the page has to say so.
LINK_HTML = """<html><head><title>Account link</title></head><body>
<h5>Account link</h5>
<p>Open this on your other browser or device within %s minutes and it will be
signed in as <b>%s</b>. It works <b>once</b>, and whoever opens it first gets
in &mdash; send it to yourself, not to a channel.</p>
<textarea id="link" readonly rows="3" style="width:100%%;font-family:monospace">%s</textarea>
<p><button type="button" id="copyLink">Copy to clipboard</button></p>
<a href="/">Back to the generator</a>
<script>
document.getElementById("copyLink").onclick = function() {
    var box = document.getElementById("link");
    box.select();
    navigator.clipboard.writeText(box.value).then(
        function() { document.getElementById("copyLink").textContent = "Copied"; },
        function() { document.getElementById("copyLink").textContent = "Press ctrl+c"; });
};
</script></body></html>"""


@bp.route('/user/link/new')
def user_link_new():
    """Mint a one-shot URL that seats another browser on this account."""
    if not (util.BETA_OF and _guest_seat_live()):
        return text_resp("Nothing here", 404)
    sub = session.get("guest_sub")
    if not sub:
        return text_resp("no guest session to share", 401)
    user = User.get()
    nonce = secrets.token_urlsafe(32)
    AccountLink.mint(sub, nonce)
    # request.host in dev, the canonical name in front of Cloudflare: _external
    # would read the scheme off a proxied request, where it is http
    host = util.CANONICAL_HOST or request.host
    scheme = "https" if util.CANONICAL_HOST else request.scheme
    url = "%s://%s%s" % (scheme, host, url_for("users.user_link_claim", nonce=nonce))
    minutes = int(AccountLink.TTL.total_seconds() // 60)
    return make_resp(LINK_HTML % (minutes, escape(user.name if user else "this account"),
                                  escape(url)))


@bp.route('/user/link/<nonce>')
def user_link_claim(nonce):
    """First browser through the door becomes the creator's account."""
    if not (util.BETA_OF and _guest_seat_live()):
        return text_resp("Nothing here", 404)
    sub = AccountLink.claim(nonce)
    if not sub:
        return text_resp("That link is spent, expired, or was never real.", 404)
    session["guest_sub"] = sub
    session.permanent = True
    return redirect("/")


@bp.route('/user/settings')
def user_get_settings():
    res = {"themes": list(SITE_THEMES), "badChars": URL_UNSAFE_NAME_CHARS}
    user = User.get()
    if user:
        res["name"] = user.name
        res["teamname"] = user.teamname or "%s's team" % user.name
        res["theme"] = user.site_theme()
        res["verbose"] = user.verbose
        res.update({k: user.setting(k) for k in USER_SETTINGS})
    return json_resp(res)


@bp.route('/user/settings/name-free')
def user_name_free():
    name = param_val("name") or ""
    return json_resp({"name": name, "free": User.name_available(name, User.get())})


@bp.route('/user/settings/update', methods=['POST'])
def user_set_settings():
    user = User.get()
    if not user:
        return text_resp("You are not logged in!", 401)
    changed = []
    name = request.form.get("name")
    if name and name != user.name:
        if not user.rename(name):
            return text_resp("Name '%s' is taken or has a forbidden character" % name, 409)
        changed.append("display name")
    teamname = request.form.get("teamname")
    if teamname and teamname != user.teamname:
        user.teamname = teamname
        changed.append("team name")
    theme = request.form.get("theme")
    if theme is not None and theme != user.site_theme():
        user.set_theme(theme)
        changed.append("theme")
    if "verbose" in request.form:
        want = request.form["verbose"].strip().lower() not in ("0", "false", "no", "off", "")
        if want != user.verbose:
            user.verbose = want
            changed.append("spoiler detail")
    for key, spec in USER_SETTINGS.items():
        if key in request.form:
            want = request.form[key].strip().lower() not in ("0", "false", "no", "off", "")
            if want != user.setting(key):
                user.set_setting(key, want)
                changed.append(spec["label"])
    if changed:
        user.put()
    return json_resp({"changed": changed, "name": user.name, "theme": user.site_theme()})


@bp.route('/theme/toggle')
def user_toggle_darkmode():
    target_url = unquote(param_val("redir")) or "/"
    user = User.get()
    if user:
        # the page sends the state it's switching to: with nothing stored it
        # may be showing the browser's preference, which we can't see
        want = param_true("dark") if param_val("dark") is not None else user.site_theme() != "dark"
        user.set_theme("dark" if want else "light")
        user.put()
    return redirect(target_url)
