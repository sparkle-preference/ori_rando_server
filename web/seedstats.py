"""Seed stats: an unlisted dev page that rolls one preset many times and tallies where items land."""
import logging as log

from flask import Blueprint, render_template, request

from models import User
from seedbuilder.seedparams import SeedGenParams
from util import INDEX_TEMPLATE, template_vals
from web.responses import json_resp, text_resp

bp = Blueprint("seedstats", __name__)

# seeds per request: the page loops, so no one request holds the single instance for long
ROLL_CAP = 10


def roll(settings, seeds):
    """Each seed rolled in memory from one world's settings: [{seed, placements|None}]."""
    out = []
    for seed in seeds[:ROLL_CAP]:
        params = SeedGenParams.from_json(dict(settings, seed=str(seed), players=1), store=False)
        if params is None:
            raise ValueError("those settings don't make a seed")
        ok = False
        try:
            ok = params.generate(store=False)
        except Exception as e:
            log.warning("seedstats: %s failed: %s", seed, e)
        out.append({"seed": str(seed),
                    "placements": [[loc, code, id] for (loc, code, id, _) in params.get_seed_data(1)] if ok else None})
    return out


@bp.route('/seedstats')
def seedstats_page():
    return render_template(INDEX_TEMPLATE, **template_vals("SeedStats", "Seed Stats", User.get()))


@bp.route('/seedstats/roll', methods=['POST'])
def seedstats_roll():
    if not User.get():
        return text_resp("log in to roll seed stats", 401)
    body = request.get_json(silent=True) or {}
    settings = body.get("settings")
    seeds = body.get("seeds")
    if not isinstance(settings, dict) or not isinstance(seeds, list):
        return text_resp("expected settings and seeds", 400)
    try:
        return json_resp({"rolls": roll(settings, seeds)})
    except ValueError as e:
        return text_resp(str(e), 422)
