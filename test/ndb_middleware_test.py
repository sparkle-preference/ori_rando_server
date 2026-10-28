"""models.ndb_wsgi_middleware: a request rides whatever client models holds when it arrives.

Run from the repo root:  python -m unittest test.ndb_middleware_test -v
"""
import contextlib
import unittest

import models


class _Client(object):
    def __init__(self):
        self.entered = 0

    @contextlib.contextmanager
    def context(self):
        self.entered += 1
        yield


def _app(environ, start_response):
    return [b"ok"]


class NdbMiddlewareTestCase(unittest.TestCase):
    def setUp(self):
        self.addCleanup(setattr, models, "client", models.client)

    def test_a_client_set_after_wrapping_opens_its_context(self):
        # CI imports models with no emulator, then tests hand it their own client
        models.client = None
        app = models.ndb_wsgi_middleware(_app)
        fake = models.client = _Client()
        self.assertEqual(app({}, None), [b"ok"])
        self.assertEqual(fake.entered, 1)

    def test_no_client_passes_straight_through(self):
        models.client = None
        self.assertEqual(models.ndb_wsgi_middleware(_app)({}, None), [b"ok"])
