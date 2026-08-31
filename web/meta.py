"""Operational surface: what version is live, what flags are on, and the two
maintenance endpoints Cloud Scheduler calls.
"""
import logging as log

from flask import Blueprint
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
