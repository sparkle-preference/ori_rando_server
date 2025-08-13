import os

from util import debug
from flask_oidc import OpenIDConnect

def make_oidc(app):
    app.config["OIDC_CLIENT_SECRETS"] = os.getenv("OIDC_CLIENT_SECRETS", "oauth/client_secret.json")
    app.config["OIDC_OVERWRITE_REDIRECT_URI"] = os.getenv("OIDC_OVERWRITE_REDIRECT_URI", "https://orirando.com/authorize")
    if debug():
        app.config["OIDC_ENABLED"] = os.getenv("OIDC_ENABLED", "False") == "True"
        app.config["OIDC_TESTING_PROFILE"] = {
            "email": os.getenv("OIDC_TESTING_EMAIL", "test@example.com"),
            "sub": os.getenv("OIDC_USER_ID", "123454321234543212345")
        }
        
    app.secret_key = os.getenv("APP_SECRET_KEY")
    oidc = OpenIDConnect(app)
    oidc.oauth.oidc.authorize_params = {'access_type': 'offline', 'prompt': 'consent'}
    return oidc
