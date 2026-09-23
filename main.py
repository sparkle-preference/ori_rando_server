# WSGI entry point: the app gunicorn names and the index page; every other route lives in web/
import logging as log
from flask import render_template

import util
from archipelago import build_apworld
from models import User
from util import INDEX_TEMPLATE, VERSION, template_vals
from web import create_app
from web.patchnotes import latest_note_version

app = create_app()


if util.ARCHIPELAGO:
    # a broken apworld package still passes the health check, so say so at boot
    _apworld_problems = build_apworld.check(build_apworld.collect())
    if _apworld_problems:
        log.error("APWORLD package cannot be served: %s", "; ".join(_apworld_problems))


@app.route('/quickstart')
@app.route('/')
def main_page():
    template_values = template_vals("MainPage", "Ori DE Randomizer %s" % util.DISPLAY_VERSION, User.get())
    # the newest note, not VERSION: a site-only release moves only this
    template_values['notes_anchor'] = latest_note_version()
    return render_template(INDEX_TEMPLATE, **template_values)
