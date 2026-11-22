"""Operational surface: what version is live, what flags are on, and the two
admin-only maintenance endpoints.
"""
import logging as log

import collections
import json
import threading
import time

from flask import Blueprint, request
from google.cloud import ndb

import util
from cache import Cache
from models import Game, User
from pickups import Pickup
from util import BETA_VER, MIN_VER, NETPERF_TAG, VER, param_flag, picks_by_type_generator
from web.responses import json_resp, make_resp, text_resp

bp = Blueprint("meta", __name__)


@bp.route('/clean/')
def clean_up():
    if not User.is_admin():
        return text_resp("No", 403)
    log.info("starting clean...")
    clean_count, did_finish = Game.clean_old(param_flag("log_prog"))
    ndb.get_context().clear_cache()
    if did_finish:
        log.info("Cleaned up %s games" % clean_count)
        User.prune_games()
        return text_resp("Cleaned up %s games" % clean_count)
    else:
        log.info("Cleaned up %s games before timeout" % clean_count)
        return text_resp("Cleaned up %s games before timeout" % clean_count)


@bp.route('/cache/clear')
def clear_cache():
    if not User.is_admin():
        return text_resp("No", 403)
    Cache.clear()
    return text_resp("cache cleared!")


@bp.route('/pickupandlocinfo')
def picks_by_type():
    return json_resp({'picks_by_type': picks_by_type_generator(), 'str_ids': Pickup.strtypes()})


@bp.route('/flags')  # verify feature-flag status per revision
def flag_status():
    flags = {"ARCHIPELAGO": util.ARCHIPELAGO}
    rows = "".join("<tr><td style='padding:4px 12px'>%s</td><td style='padding:4px 12px'><b>%s</b></td></tr>"
                   % (name, "ON" if val else "off") for name, val in flags.items())
    return make_resp("<html><body><h3>Feature flags</h3><table border=1>%s</table><p>serving: %s</p></body></html>"
                     % (rows, NETPERF_TAG))


@bp.route('/version/latest')
def version_txt():
    return text_resp("%s.%s.%s" % tuple(VER))


@bp.route('/version/minimum')
def min_version_txt():
    return text_resp("%s.%s.%s" % tuple(MIN_VER))


@bp.route('/version/beta')
def beta_version_txt():
    return text_resp("%s.%s.%s" % tuple(BETA_VER))


@bp.route('/version')
@bp.route('/version/json')
def version_json():
    return json_resp({
        "latest": "%s.%s.%s" % tuple(VER),
        "minimum": "%s.%s.%s" % tuple(MIN_VER),
        "beta": "%s.%s.%s" % tuple(BETA_VER),
    })


# page crash reports; the per-process budget keeps metered logging cheap
CLIENT_ERROR_MAX_BYTES = 16 * 1024
CLIENT_ERROR_BUDGET = (20, 600)
# what report_error sends; a rejection with no reason carries nothing else
CLIENT_ERROR_KINDS = ("render", "window", "promise")
_client_errors = collections.deque()
_client_errors_lock = threading.Lock()


def _client_error_allowed(now=None):
    limit, window = CLIENT_ERROR_BUDGET
    now = time.time() if now is None else now
    with _client_errors_lock:
        while _client_errors and now - _client_errors[0] > window:
            _client_errors.popleft()
        if len(_client_errors) >= limit:
            return False
        _client_errors.append(now)
        return True


@bp.route('/client_error', methods=['POST'])
def client_error():
    if (request.content_length or 0) > CLIENT_ERROR_MAX_BYTES:
        return make_resp("", 413)
    # json only, as the page sends it: another site's form post can't carry that type
    if not request.is_json:
        return make_resp("", 204)
    # a chunked body names no length: the read is what stops it
    raw = request.stream.read(CLIENT_ERROR_MAX_BYTES + 1)
    if len(raw) > CLIENT_ERROR_MAX_BYTES:
        return make_resp("", 413)
    try:
        body = json.loads(raw or b"{}")
    except (ValueError, RecursionError):
        body = None
    # anything else posted here takes no log line and no slot of the budget
    if not (isinstance(body, dict) and (body.get("message") or body.get("stack") or body.get("kind") in CLIENT_ERROR_KINDS)):
        return make_resp("", 204)
    if not _client_error_allowed():
        return make_resp("", 429)
    # the page cuts by UTF-16 unit: half an emoji would fail the log write and lose the line
    text = lambda k, n=2000: str(body.get(k) or "")[:n].encode("utf-8", "replace").decode("utf-8")
    # a warning: an error entry on prod means the server itself broke
    log.warning("CLIENTERR app=%s ver=%s kind=%s url=%s\nmsg=%s\nua=%s\n%s\n%s",
                text("app", 40), text("version", 40), text("kind", 40), text("url", 300),
                text("message", 500), text("ua", 300), text("stack", 4000), text("componentStack", 4000))
    return make_resp("", 204)
