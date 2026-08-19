"""Plandos carry an author-written spoiler, edited on the seed page.

The text lives on the Seed; params rolled from a plando only point at it, so a
download does not copy the whole spoiler into a fresh entity.

Run from the repo root:  python3 -m unittest test.plando_spoiler_test -v
"""
import contextlib
import unittest

import google.auth.credentials
from google.cloud import ndb

from models import Seed, User
from seedbuilder.seedparams import SeedGenParams


class PlandoSpoilerTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        creds = google.auth.credentials.AnonymousCredentials()
        cls.ndb_client = ndb.Client(project="unit-test", credentials=creds)

    def setUp(self):
        self._ctx = self.ndb_client.context()
        self._ctx.__enter__()
        self._put = SeedGenParams.put
        SeedGenParams.put = lambda self: None

    def tearDown(self):
        SeedGenParams.put = self._put
        self._ctx.__exit__(None, None, None)

    @staticmethod
    def _plando(**kwargs):
        fields = dict(id="uid:StarterSeed", name="StarterSeed", players=1,
                      flags=["Casual", "Clues", "ForceTrees"], placements=[],
                      author_key=ndb.Key(User, "uid"), description="a one-line blurb")
        fields.update(kwargs)
        return Seed(**fields)

    @staticmethod
    @contextlib.contextmanager
    def _datastore(seed):
        """Resolve Seed keys to `seed` and User keys to its author."""
        author = type("U", (), {"key": seed.author_key})()
        get, put = ndb.Key.get, Seed.put
        ndb.Key.get = lambda self, **kw: seed if self.kind() == "Seed" else author
        Seed.put = lambda self: None
        try:
            yield
        finally:
            ndb.Key.get, Seed.put = get, put

    def test_spoiler_is_served_through_the_plando(self):
        plando = self._plando(spoiler="1: ['Spawn'] {\n}\n")
        with self._datastore(plando):
            params = SeedGenParams.from_plando(plando)
            self.assertEqual(params.get_spoiler(), "1: ['Spawn'] {\n}\n")
        # the pointer, not a copy: params carry only the short description
        self.assertEqual(params.spoilers, ["a one-line blurb"])
        self.assertEqual(params.plando_spoiler_key, plando.key)

    def test_description_is_the_fallback(self):
        for empty in (None, ""):
            plando = self._plando(spoiler=empty)
            with self._datastore(plando):
                params = SeedGenParams.from_plando(plando)
                self.assertIsNone(params.plando_spoiler_key)
                self.assertEqual(params.get_spoiler(), "a one-line blurb")

    def test_spoiler_button_follows_the_spoiler(self):
        # the UI shows its spoiler button off to_json's flag, not off a plando bit
        blurb = self._plando()
        with self._datastore(blurb):
            self.assertFalse(SeedGenParams.from_plando(blurb).to_json()["spoilers"])
        real = self._plando(spoiler="x" * 101)
        with self._datastore(real):
            self.assertTrue(SeedGenParams.from_plando(real).to_json()["spoilers"])

    def _saved(self, payload, spoiler="kept"):
        seed = self._plando(spoiler=spoiler)
        with self._datastore(seed):
            seed.update(dict(payload, name="StarterSeed"))
        return seed

    def test_save_without_a_spoiler_key_keeps_the_stored_one(self):
        # the plando builder never sends spoiler=, and must not wipe it
        self.assertEqual(self._saved({}).spoiler, "kept")

    def test_seed_page_save_round_trips_and_clears(self):
        self.assertEqual(self._saved({"spoiler": "rewritten"}).spoiler, "rewritten")
        self.assertIsNone(self._saved({"spoiler": ""}).spoiler)


if __name__ == "__main__":
    unittest.main()
