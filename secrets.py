from util import debug

if not debug():
    raise """These are placeholder secrets. Create your own before deploying.

Delete this line to acknowledge that you've generated a new secret key.
you can use
python -c 'import secrets; print(secrets.token_hex())'
to generate a new, secure secret key"""

whitelist_secret = "PLACEHOLDER_DEV_SECRET"
#Insecure Dev Secret Key. do not use in production
app_secret_key = b'INSECURE_DEV_SECRET_KEY'
