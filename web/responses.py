"""How a route says what it is returning.

`make_resp` is the base and the others wrap it, so content type is set in exactly
one place. The netcode handlers deliberately do NOT use these: they return
`(status, body)` and stay transport-neutral, and their route adapters call
`text_resp` on the way out.
"""
import json

from flask import make_response

from util import json_default


def make_resp(body, status=200, mimeType='text/html'):
    return make_response((body, status, {'Content-Type': mimeType}))


def text_resp(body, status=200):
    return make_resp(body, status, 'text/plain')


def json_resp(jsonstr, status=200):
    return make_resp(jsonstr if isinstance(jsonstr, str) else json.dumps(jsonstr, default=json_default), status, mimeType="application/json")


def code_resp(code):
    return text_resp(str(code), code)


def text_download(text, filename, status=200):
    return make_response(text, status, {'Content-Type': 'application/x-gzip', 'Content-Disposition': 'attachment; filename=%s' % filename})


def zip_download(data, filename, status=200):
    return make_response(data, status, {'Content-Type': 'application/zip', 'Content-Disposition': 'attachment; filename=%s' % filename})
