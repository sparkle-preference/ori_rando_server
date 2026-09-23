"""Request-lifecycle hooks every route gets. Family-specific hooks live with their blueprint."""

from urllib.parse import quote_plus

from flask import Response, get_flashed_messages, redirect, request, session
from flask_oidc.signals import after_logout

import util
from web.responses import make_resp


def server_error(err):
    return make_resp("""
    <html><title>Server Error</title>
    <body><h3>Backend Server Error</h3>
    <div>If this keeps happening, consider reaching out to Eiko in the <a target="_blank" href="/discord/dev">dev discord</a>.</div>
    <div style="padding-top: 2rem;">%s</div></body></html>""" % err, 500)


def canonical_host_redirect():
    # browsers only: the dll treats a redirect as an error, and a POST must fail loudly, not 301
    if not util.CANONICAL_HOST or request.host not in util.REDIRECT_HOSTS:
        return
    if request.method not in ("GET", "HEAD") or request.path.startswith("/netcode/"):
        return
    target = request.full_path if request.query_string else request.path
    return redirect("https://%s%s" % (util.CANONICAL_HOST, target), 301)


def fix_logout_redirect(response: Response):
    if response.location == '/logout?reason=expired':
        response.location += '&next=' + quote_plus(request.full_path)

    return response


def hsts_header(response):
    # never includeSubDomains: bfnc.orirando.com serves the TLS-less dll over plain http
    if request.is_secure:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
    return response


def delete_flashes(response):
    """Drop flask-oidc's unread flash() messages so they don't pile up in the session cookie."""
    get_flashed_messages()
    return response


def make_session_permanent():
    """Rolling year-long login cookie, only for sessions holding a token: setting permanent
    writes a key, and a non-empty session sends a cookie on every anonymous hit and netcode poll."""
    if session.get("oidc_auth_token"):
        session.permanent = True


# the signal is global rather than per-app, so this connects at import
@after_logout.connect
def clear_session_on_logout(sender, **kwargs):
    # logout_view pops only its own keys, and Flask deletes the cookie only for an empty session
    session.clear()


def register_hooks(app):
    app.before_request(canonical_host_redirect)
    app.before_request(make_session_permanent)
    app.after_request(fix_logout_redirect)
    app.after_request(hsts_header)
    app.after_request(delete_flashes)
    app.errorhandler(500)(server_error)
