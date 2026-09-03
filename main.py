# The WSGI entry point. Everything that serves a URL lives under web/;
# what is left here is the app object gunicorn names and the index page.
import logging as log
from flask import render_template

import util
from archipelago import build_apworld
from archipelago.yaml_emit import DATA_VERSION as AP_DATA_VERSION
from models import User
from util import INDEX_TEMPLATE, VERSION, template_vals
from web import create_app
from web.patchnotes import latest_note_version

app = create_app()


def ap_versions():
    """Versions the AP setup panel quotes, read from the packaged sources."""
    try:
        world_version = build_apworld.manifest().get("world_version", "")
    except (OSError, ValueError) as e:
        log.error("APWORLD manifest unreadable, version line will be blank: %s", e)
        world_version = ""
    return {'ap_world_version': world_version, 'ap_data_version': AP_DATA_VERSION}


if util.ARCHIPELAGO:
    # an image missing package files still boots and passes its health check,
    # so say so at startup rather than when a tester clicks Get apworld
    _apworld_problems = build_apworld.check(build_apworld.collect())
    if _apworld_problems:
        log.error("APWORLD package cannot be served: %s", "; ".join(_apworld_problems))


@app.route('/quickstart')
@app.route('/')
def main_page():
    template_values = template_vals("MainPage", "Ori DE Randomizer %s" % util.DISPLAY_VERSION, User.get())
    # not the displayed version: this moves on a site-only release, so the link goes unread
    template_values['notes_anchor'] = latest_note_version()
    if util.ARCHIPELAGO:
        template_values.update(ap_versions())
    return render_template(INDEX_TEMPLATE, **template_values)
