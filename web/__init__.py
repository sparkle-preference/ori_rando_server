"""The Flask layer: the app factory, its extensions, hooks and responses.

Nothing under web/ may import main, which stays a leaf of the import graph.
"""
import logging as log
from datetime import timedelta

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from models import ndb_wsgi_middleware
from util import debug, template_root
from web.extensions import init_extensions
from web.hooks import register_hooks
from web.bingo import bp as bingo_bp
from web.generator import bp as generator_bp
from web.meta import bp as meta_bp
from web.plando import bp as plando_bp
from web.presets import bp as presets_bp
from web.netcode import bp as netcode_bp
from web.pages import bp as pages_bp
from web.tracker import bp as tracker_bp
from web.users import bp as users_bp
from web.patchnotes import bp as patchnotes_bp


def configure_logging():
    """Console in dev, Cloud Logging in prod; run by the factory so an import never reaches GCP."""
    if debug():
        root_logger = log.getLogger()
        for handler in root_logger.handlers:
            root_logger.removeHandler(handler)

        import sys
        console_handle = log.StreamHandler(sys.stdout)
        console_handle.setLevel(log.INFO)
        formatter = log.Formatter("%(name)-5s - %(levelname)-8s - %(message)s")
        console_handle.setFormatter(formatter)

        root_logger.addHandler(console_handle)
        root_logger.setLevel(log.INFO)
        log.info("set up dev logging to console!")
    else:
        import google.cloud.logging

        print("trying to setup prod log")
        client = google.cloud.logging.Client()
        client.setup_logging(log_level=log.DEBUG)


def create_app():
    """Call once: web.extensions are module singletons and a second call rebinds them."""
    configure_logging()
    app = Flask(__name__, template_folder=template_root, static_folder=template_root,
                static_url_path='/static')
    app.debug = debug()
    # read as the cookie max_age at context push, before any before_request hook
    app.permanent_session_lifetime = timedelta(days=365)
    app.wsgi_app = ndb_wsgi_middleware(app.wsgi_app)
    # TLS ends upstream, so without this every redirect is http://. Stays outermost;
    # x_for off because nothing reads remote_addr.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    # before the blueprints: the guest seat's hook must run after flask-oidc's to win g.oidc_user
    init_extensions(app)
    register_hooks(app)
    app.register_blueprint(users_bp)
    app.register_blueprint(netcode_bp)
    app.register_blueprint(bingo_bp)
    app.register_blueprint(generator_bp)
    app.register_blueprint(tracker_bp)
    app.register_blueprint(meta_bp)
    app.register_blueprint(plando_bp)
    app.register_blueprint(presets_bp)
    app.register_blueprint(pages_bp)
    app.register_blueprint(patchnotes_bp)
    return app
