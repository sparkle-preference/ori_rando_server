"""A plando's shared categories come from its share= flag (shared= in older plandos).

Run from the repo root:  python3 -m unittest test.plando_share_test -v
"""
import unittest

import google.auth.credentials
from google.cloud import ndb

from enums import MultiplayerGameType, ShareType
from models import Seed
from seedbuilder.seedparams import SeedGenParams


class PlandoShareTestCase(unittest.TestCase):
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
    def _plando(*flags):
        return Seed(id="uid:Mw", name="Mw", players=4, placements=[], flags=["Master", *flags])

    def test_share_reaches_the_game(self):
        params = SeedGenParams.from_plando(self._plando("share=Skills+WorldEvents+Teleporters", "mode=Multiworld"))
        self.assertEqual(params.sync.mode, MultiplayerGameType.MULTIWORLD)
        self.assertEqual(params.sync.shared, [ShareType.SKILL, ShareType.EVENT, ShareType.TELEPORTER])

    def test_older_plandos_say_shared(self):
        plando = self._plando("shared=Skills+Teleporters", "mode=Shared")
        self.assertEqual(plando.shared(), [ShareType.SKILL, ShareType.TELEPORTER])

    def test_the_last_one_wins(self):
        # an older editor appended its shared= after a fill's leftover share=
        plando = self._plando("share=Skills+WorldEvents", "shared=Teleporters", "mode=Multiworld")
        self.assertEqual(plando.shared(), [ShareType.TELEPORTER])

    def test_no_flag_shares_nothing(self):
        self.assertEqual(self._plando("mode=Multiworld").shared(), [])


if __name__ == "__main__":
    unittest.main()
