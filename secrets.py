whitelist_secret = "PLACEHOLDER_DEV_SECRET"
#Insecure Dev Secret Key. do not use in production
app_secret_key = b'INSECURE_DEV_SECRET_KEY'

raise """Delete this line to acknowledge that you've generated a new secret key if you're in production. 
you can use
python -c 'import secrets; print(secrets.token_hex())'
to generate a new, secure secret key"""
