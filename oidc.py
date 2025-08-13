import os

from util import build_testing_secrets, debug
from flask_oidc import OpenIDConnect

try:
    import app_secrets
except ImportError:
    build_testing_secrets()
    import app_secrets

def make_oidc(app):
    app.config["OIDC_CLIENT_SECRETS"] = os.getenv("OIDC_CLIENT_SECRETS", "app_secrets/client_secret.json")
    if debug():
        app.config["OIDC_ENABLED"] = os.getenv("OIDC_ENABLED", "False") == "True"
        app.config["OIDC_TESTING_PROFILE"] = {
            "email": os.getenv("OIDC_TESTING_EMAIL", "test@example.com"),
            "sub": os.getenv("OIDC_USER_ID", "123454321234543212345")
        }
        
    app.secret_key = app_secrets.app_secret_key
    oidc = OpenIDConnect(app)
    oidc.oauth.oidc.authorize_params = {'access_type': 'offline', 'prompt': 'consent'}
    return oidc
