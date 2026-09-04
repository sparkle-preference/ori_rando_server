"""Operational surface: what version is live, what flags are on, and the two
maintenance endpoints Cloud Scheduler calls.
"""
import logging as log

import collections
import time

from flask import Blueprint, request
from google.cloud import ndb

import util
from cache import Cache
from models import Game, User
from pickups import Pickup
from util import BETA_VER, MIN_VER, NETPERF_TAG, VER, debug, param_flag, picks_by_type_generator
from web.responses import json_resp, make_resp, text_resp

bp = Blueprint("meta", __name__)


@bp.route('/clean/')
def clean_up():
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


# Crash reports from the page. Beta and dev boxes only: prod logging is metered, and the
# page shows the user what happened either way. A per-process budget keeps a looping
# page from filling the log.
CLIENT_ERROR_MAX_BYTES = 16 * 1024
CLIENT_ERROR_BUDGET = (20, 600)
_client_errors = collections.deque()


def _client_error_allowed(now=None):
    limit, window = CLIENT_ERROR_BUDGET
    now = time.time() if now is None else now
    while _client_errors and now - _client_errors[0] > window:
        _client_errors.popleft()
    if len(_client_errors) >= limit:
        return False
    _client_errors.append(now)
    return True


@bp.route('/client_error', methods=['POST'])
def client_error():
    if not (util.BETA_OF or debug()):
        return make_resp("", 204)
    if (request.content_length or 0) > CLIENT_ERROR_MAX_BYTES:
        return make_resp("", 413)
    if not _client_error_allowed():
        return make_resp("", 429)
    body = request.get_json(silent=True) or {}
    text = lambda k, n=2000: str(body.get(k) or "")[:n]
    log.error("CLIENTERR app=%s ver=%s kind=%s url=%s\nmsg=%s\nua=%s\n%s\n%s",
              text("app", 40), text("version", 40), text("kind", 40), text("url", 300),
              text("message", 500), text("ua", 300), text("stack", 4000), text("componentStack", 4000))
    return make_resp("", 204)
