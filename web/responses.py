"""Response builders; make_resp is the base the others wrap.

Netcode handlers return (status, body) to stay transport-neutral; only their route adapters call these.
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
