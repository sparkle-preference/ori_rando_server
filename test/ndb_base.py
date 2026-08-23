"""Shared ndb test bases: a local-context stub and a real-emulator harness."""
import os
import unittest
import urllib.request

import google.auth.credentials
from google.cloud import ndb

# host-published by the datastore_test compose service; in-memory, safe to reset
EMULATOR_HOST = os.environ.get("DATASTORE_TEST_EMULATOR_HOST", "localhost:8001")


class NdbTestCase(unittest.TestCase):
    """Provides an ndb context so entities can be constructed locally."""

    @classmethod
    def setUpClass(cls):
        creds = google.auth.credentials.AnonymousCredentials()
        cls.ndb_client = ndb.Client(project="unit-test", credentials=creds)

    def setUp(self):
        self._ctx = self.ndb_client.context()
        self._ctx.__enter__()

    def tearDown(self):
        self._ctx.__exit__(None, None, None)


class EmulatorTestCase(unittest.TestCase):
    """Runs against the datastore_test emulator, wiped before every test.
    Skips itself when the emulator isn't up (docker compose up -d datastore_test)."""

    @classmethod
    def setUpClass(cls):
        try:
            with urllib.request.urlopen("http://%s/" % EMULATOR_HOST, timeout=2):
                pass
        except OSError:
            raise unittest.SkipTest(
                "no emulator at %s (docker compose up -d datastore_test)" % EMULATOR_HOST)
        cls._prior_host = os.environ.get("DATASTORE_EMULATOR_HOST")
        os.environ["DATASTORE_EMULATOR_HOST"] = EMULATOR_HOST
        cls.ndb_client = ndb.Client(project="orirandov3")

    @classmethod
    def tearDownClass(cls):
        # stub-based cases constructed later must not silently pick up the emulator
        if cls._prior_host is None:
            os.environ.pop("DATASTORE_EMULATOR_HOST", None)
        else:
            os.environ["DATASTORE_EMULATOR_HOST"] = cls._prior_host

    def setUp(self):
        req = urllib.request.Request("http://%s/reset" % EMULATOR_HOST, method="POST")
        with urllib.request.urlopen(req, timeout=5):
            pass
        self._ctx = self.ndb_client.context()
        self._ctx.__enter__()

    def tearDown(self):
        self._ctx.__exit__(None, None, None)
