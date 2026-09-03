# The WSGI entry point. Everything that serves a URL lives under web/;
# what is left here is the app object gunicorn names and the index page.
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
    return render_template(INDEX_TEMPLATE, **template_values)
