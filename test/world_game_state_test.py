"""What a Game keeps per world, and what a reset is allowed to touch."""
import unittest

import google.auth.credentials
from google.cloud import ndb

import models
from enums import Variation
from models import Game
from seedbuilder.seedparams import SeedGenParams


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




class PerWorldBingoTestCase(unittest.TestCase):
    """Bingo is a per-player opt-in: a world takes it on with its own Bingo
    variation, and gets a board built from its own settings."""

    @classmethod
    def setUpClass(cls):
        creds = google.auth.credentials.AnonymousCredentials()
        cls.ndb_client = ndb.Client(project="unit-test", credentials=creds)

    def setUp(self):
        self._ctx = self.ndb_client.context()
        self._ctx.__enter__()

    def tearDown(self):
        self._ctx.__exit__(None, None, None)

    def params(self, worlds, base_vars=None):
        from enums import KeyMode, LogicPath, MultiplayerGameType, PathDifficulty
        from seedbuilder.seedparams import MultiplayerOptions, SeedGenParams
        p = SeedGenParams(seed="perworldbingo")
        p.sync = MultiplayerOptions()
        p.sync.enabled = True
        p.sync.mode = MultiplayerGameType.MULTIWORLD
        p.spoilers, p.placements = [""], []
        p.logic_paths = [LogicPath.CASUAL_CORE]
        p.key_mode = KeyMode.CLUES
        p.path_diff = PathDifficulty.NORMAL
        p.players = len(worlds)
        p.variations = base_vars if base_vars is not None else []
        p.world_settings = worlds
        return p

    def test_one_bingo_player_in_a_multiworld(self):
        import main
        p = self.params([{"variations": ["Bingo"]}, {"variations": ["OpenWorld"]}])
        self.assertEqual(main.bingo_worlds(p), [1], "only the world that opted in plays")

    def test_a_late_world_can_be_the_only_one(self):
        import main
        p = self.params([{"variations": ["OpenWorld"]}, {"variations": ["Bingo"]}])
        self.assertEqual(main.bingo_worlds(p), [2])

    def test_two_worlds_on_the_same_settings_still_get_different_boards(self):
        import main
        p = self.params([{"variations": ["Bingo"]}, {"variations": ["Bingo"]}])
        self.assertEqual(main.bingo_worlds(p), [1, 2])
        boards = main.bingo_boards_for(p, "seedstring", False)
        self.assertEqual([b.world for b in boards], [1, 2])
        first = [c.name for c in boards[0].board]
        second = [c.name for c in boards[1].board]
        self.assertNotEqual(first, second, "each world is seeded apart")

    def test_a_world_plays_by_its_own_board_settings(self):
        import main
        p = self.params([{"variations": ["Bingo"], "bingoDiff": "easy"},
                         {"variations": ["Bingo"], "bingoDiff": "hard"}])
        self.assertEqual(p.world_params(1).bingo_diff, "easy")
        self.assertEqual(p.world_params(2).bingo_diff, "hard")
        self.assertEqual(p.world_params(1).bingo_lines, p.bingo_lines, "unset keeps the seed's")

    def test_nobody_opted_in_is_no_boards(self):
        import main
        p = self.params([{}, {}])
        self.assertEqual(main.bingo_worlds(p), [])
        self.assertEqual(main.bingo_boards_for(p, "seedstring", False), [])

    def test_board_for_falls_back_to_the_one_board(self):
        from models import BingoGameData
        b = BingoGameData()
        self.assertEqual(b.board_for(1), b.board)
        self.assertEqual(b.board_for(7), b.board, "one board serves every world")
        self.assertEqual(b.all_boards(), [b.board])


if __name__ == "__main__":
    unittest.main()
