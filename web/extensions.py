"""Flask extensions, constructed unbound and attached to the app by init_extensions."""
import os

from flask_oidc import OpenIDConnect
from flask_sock import Sock

from util import WS_PING_INTERVAL, debug

oidc = OpenIDConnect()
sock = Sock()


def init_extensions(app):
    app.config["OIDC_CLIENT_SECRETS"] = os.getenv("OIDC_CLIENT_SECRETS", "oauth/client_secret.json")
    app.config["OIDC_OVERWRITE_REDIRECT_URI"] = os.getenv("OIDC_OVERWRITE_REDIRECT_URI")
    if debug():
        app.config["OIDC_ENABLED"] = os.getenv("OIDC_ENABLED", "False") == "True"
        app.config["OIDC_TESTING_PROFILE"] = {
            "email": os.getenv("OIDC_TESTING_EMAIL", "test@example.com"),
            "sub": os.getenv("OIDC_USER_ID", "123454321234543212345")
        }

    app.secret_key = os.getenv("APP_SECRET_KEY")
    oidc.init_app(app)
    # oidc.oauth does not exist until init_app has built it
    oidc.oauth.oidc.authorize_params = {'access_type': 'offline', 'prompt': 'consent'}

    # client frames are tiny; uncapped, a fragmented message grows without bound
    app.config['SOCK_SERVER_OPTIONS'] = sock_server_options()
    sock.init_app(app)


def sock_server_options(ping_interval=None):
    opts = {'max_message_size': 1 << 20}
    ping = WS_PING_INTERVAL if ping_interval is None else ping_interval
    if ping > 0:
        opts['ping_interval'] = ping
    return opts
