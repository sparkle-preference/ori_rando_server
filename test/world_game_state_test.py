"""What a Game keeps per world, and what a reset is allowed to touch."""
import unittest

import google.auth.credentials
from google.cloud import ndb

import models
from enums import Variation
from models import Game
from seedbuilder.seedparams import LOBBY_VARIATIONS, SeedGenParams


class _FakeParams(object):
    """Enough of SeedGenParams for Game.from_params, with per-world relic rows."""

    def __init__(self, players, zones_by_world):
        self.players = players
        self.zones = zones_by_world
        self.variations = [Variation.WORLD_TOUR]
        self.player_names = []
        self.key = None
        self.seed = "relics"

    def get_seed_data(self, player=1, no_door_zone=True):
        return [(0, "WT", "0", z) for z in self.zones[player]]


class RelicsPerWorldTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        creds = google.auth.credentials.AnonymousCredentials()
        cls.ndb_client = ndb.Client(project="unit-test", credentials=creds)

    def setUp(self):
        self._ctx = self.ndb_client.context()
        self._ctx.__enter__()

    def tearDown(self):
        self._ctx.__exit__(None, None, None)

    def test_each_world_gets_the_zones_it_was_dealt(self):
        g = Game()
        g.relics_by_world = {"1": ["Glades", "Grove"], "2": ["Horu", "Sorrow"]}
        g.relics = ["Glades", "Grove"]
        self.assertEqual(g.relics_for(1), ["Glades", "Grove"])
        self.assertEqual(g.relics_for(2), ["Horu", "Sorrow"])

    def test_a_game_from_before_the_field_still_answers(self):
        """Games rolled earlier stored one list, which was world 1's."""
        g = Game()
        g.relics = ["Glades", "Grove"]
        self.assertEqual(g.relics_for(1), ["Glades", "Grove"])
        self.assertEqual(g.relics_for(2), ["Glades", "Grove"])

    def test_a_world_with_no_row_falls_back(self):
        g = Game()
        g.relics_by_world = {"1": ["Glades"]}
        g.relics = ["Glades"]
        self.assertEqual(g.relics_for(3), ["Glades"])


class LobbyVariationsTestCase(unittest.TestCase):
    """A game has one bingo board, so a world cannot opt into or out of Bingo."""

    @classmethod
    def setUpClass(cls):
        creds = google.auth.credentials.AnonymousCredentials()
        cls.ndb_client = ndb.Client(project="unit-test", credentials=creds)

    def setUp(self):
        self._ctx = self.ndb_client.context()
        self._ctx.__enter__()

    def tearDown(self):
        self._ctx.__exit__(None, None, None)

    def params(self, base_vars, world_vars):
        from seedbuilder.seedparams import MultiplayerOptions
        from enums import KeyMode, LogicPath, MultiplayerGameType, PathDifficulty
        p = SeedGenParams(seed="lobbyvars")
        p.sync = MultiplayerOptions()
        p.sync.enabled = True
        p.sync.mode = MultiplayerGameType.MULTIWORLD
        p.spoilers, p.placements = [""], []
        p.logic_paths = [LogicPath.CASUAL_CORE]
        p.key_mode = KeyMode.CLUES
        p.path_diff = PathDifficulty.NORMAL
        p.players = 2
        p.variations = base_vars
        p.world_settings = [{}, {"variations": world_vars}]
        return p

    def test_a_world_cannot_drop_bingo(self):
        p = self.params([Variation.BINGO, Variation.FORCE_TREES], ["OpenWorld"])
        self.assertIn(Variation.BINGO, p.world_params(2).variations)

    def test_a_world_cannot_add_bingo(self):
        p = self.params([Variation.FORCE_TREES], ["OpenWorld", "Bingo"])
        self.assertNotIn(Variation.BINGO, p.world_params(2).variations)

    def test_everything_else_still_overrides(self):
        p = self.params([Variation.BINGO, Variation.FORCE_TREES], ["OpenWorld"])
        got = p.world_params(2).variations
        self.assertIn(Variation.OPEN_WORLD, got)
        self.assertNotIn(Variation.FORCE_TREES, got, "a world's own variations still replace the seed's")

    def test_bingo_is_the_only_one_the_lobby_keeps(self):
        """Race is a game mode, not a per-world rule, and cannot reach a
        multiworld at all -- so it needs no pinning here."""
        self.assertEqual(LOBBY_VARIATIONS, (Variation.BINGO,))


class ResetReadsNoSettingsTestCase(unittest.TestCase):
    """A reset is progress-only. Settings live in params, which a reset never
    touches, so a player who re-downloads after one gets their own rulebook
    without any per-world work here."""

    def test_reset_touches_no_params(self):
        import inspect
        src = inspect.getsource(Game.reset)
        for forbidden in ("params", "variations", "world_settings", "flag_line"):
            self.assertNotIn(forbidden, src,
                             "Game.reset started reading settings (%s); per-world state "
                             "would now need fanning out here" % forbidden)


if __name__ == "__main__":
    unittest.main()
