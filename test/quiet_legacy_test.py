"""Old bingo rows and plando flag lines read without logging errors.

Run from the repo root:  python3 -m unittest test.quiet_legacy_test -v
"""
import unittest
from datetime import datetime

import google.auth.credentials
from google.cloud import ndb

from enums import Variation
from models import BingoEvent, BingoGameData, BingoTeam, Game, Player, Seed
from seedbuilder.seedparams import SeedGenParams


class _Ctx(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ndb_client = ndb.Client(project="unit-test", credentials=google.auth.credentials.AnonymousCredentials())

    def setUp(self):
        self._ctx = self.ndb_client.context()
        self._ctx.__enter__()

    def tearDown(self):
        self._ctx.__exit__(None, None, None)


class OldBingoRowsTestCase(_Ctx):
    def test_an_event_with_no_player_names_none_quietly(self):
        ev = BingoEvent(event_type="square", square=3, timestamp=datetime(2025, 3, 22))
        with self.assertNoLogs(level="WARNING"):
            self.assertIsNone(ev.to_json(None)["player"])

    def test_a_team_whose_captain_holds_no_seat_is_left_off_the_board(self):
        bingo = BingoGameData(id=88769, game=ndb.Key(Game, 88769), players=[], board=[],
                              teams=[BingoTeam(captain=ndb.Key(Player, "88769.11"), score=18)])
        with self.assertNoLogs(level="WARNING"):
            self.assertEqual(bingo.get_json()["teams"], {})


class PlandoFlagsTestCase(_Ctx):
    def setUp(self):
        super().setUp()
        self._put = SeedGenParams.put
        SeedGenParams.put = lambda self: None

    def tearDown(self):
        SeedGenParams.put = self._put
        super().tearDown()

    def test_only_variations_reach_the_variation_parser(self):
        plando = Seed(id="uid:P", name="P", players=1, placements=[],
                      flags=["Standard", "Clues", "Shards", "forcetrees", "WorldTour=3", "pool=Custom"])
        with self.assertNoLogs(level="WARNING"):
            params = SeedGenParams.from_plando(plando)
        self.assertIn(Variation.FORCE_TREES, params.variations)


if __name__ == "__main__":
    unittest.main()
