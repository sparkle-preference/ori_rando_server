"""What a Game keeps per world, and what a reset is allowed to touch."""
import unittest

import models
from enums import Variation
from models import Game
from seedbuilder.seedparams import SeedGenParams
from test.ndb_base import NdbTestCase


class _FakeParams(object):
    """Enough of SeedGenParams for Game.from_params, with per-world relic rows."""

    def __init__(self, players, zones_by_world):
        self.players = players
        self.zones = zones_by_world
        self.variations = [Variation.WORLD_TOUR]
        self.player_names = []
        self.key = None
        self.seed = "relics"

    def get_seed_data(self, player=1):
        return [(0, "WT", "0", z) for z in self.zones[player]]


class RelicsPerWorldTestCase(NdbTestCase):

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




class PerWorldBingoTestCase(NdbTestCase):
    """Bingo is a per-player opt-in: a world takes it on with its own Bingo
    variation, and gets a board built from its own settings."""


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

    def test_the_modal_moves_the_owners_world_and_no_other(self):
        import main
        p = self.params([{"variations": ["Bingo"], "bingoDiff": "easy"},
                         {"variations": ["Bingo"], "bingoDiff": "easy"}])
        opts = {"difficulty": "hard", "discovery": 0, "meta": False,
                "bingo_count": 5, "square_count": None, "goal": "bingos"}
        by_world = {b.world: b for b in main.bingo_boards_for(p, "seedstring", False, 1, opts)}
        self.assertEqual(by_world[1].difficulty, "hard")
        self.assertEqual(by_world[1].bingo_count, 5)
        self.assertEqual(by_world[2].difficulty, "easy", "world 2 was handed its rules with its seed")
        self.assertEqual(by_world[2].bingo_count, p.world_params(2).bingo_lines)

    def test_discovery_is_drawn_only_on_the_owners_board(self):
        import main
        p = self.params([{"variations": ["Bingo"]}, {"variations": ["Bingo"]}])
        opts = {"difficulty": "normal", "discovery": 4, "meta": False}
        by_world = {b.world: b for b in main.bingo_boards_for(p, "seedstring", False, 1, opts)}
        self.assertEqual(by_world[1].discovery, 4)
        self.assertEqual(len(by_world[1].disc_squares), 4)
        self.assertEqual(by_world[2].discovery, p.world_params(2).bingo_disc)
        self.assertEqual(by_world[2].disc_squares, [])

    def test_a_world_1_that_isnt_playing_leaves_the_modal_no_world(self):
        import main
        p = self.params([{"variations": ["OpenWorld"]},
                         {"variations": ["Bingo"], "bingoDiff": "easy"}])
        self.assertIsNone(main.owner_world(main.bingo_worlds(p)))
        boards = main.bingo_boards_for(p, "seedstring", False, None,
                                       {"difficulty": "hard", "discovery": 0, "meta": False})
        self.assertEqual(boards[0].difficulty, "easy")

    def test_a_reroll_moves_cards_and_leaves_other_worlds_rules_alone(self):
        """Rerolling world 1 must not roll back an override world 2 was given
        earlier: a world's rules outlive the cards they shaped."""
        import main
        p = self.params([{"variations": ["Bingo"]}, {"variations": ["Bingo"]}])
        first = main.bingo_boards_for(p, "seedstring", False, 2,
                                      {"difficulty": "hard", "discovery": 0, "meta": False})
        again = main.bingo_boards_for(p, "seedstringRR1", False, 1,
                                      {"difficulty": "easy", "discovery": 0, "meta": False}, first)
        by_world = {b.world: b for b in again}
        self.assertEqual(by_world[1].difficulty, "easy")
        self.assertEqual(by_world[2].difficulty, "hard", "world 2 keeps what it was given")
        self.assertNotEqual([c.name for c in by_world[2].board],
                            [c.name for c in first[1].board], "its cards still moved")

    def test_owner_world_prefers_the_board_the_modal_was_on(self):
        import main
        self.assertEqual(main.owner_world([1, 2, 3], 3), 3)
        self.assertEqual(main.owner_world([1, 2, 3], "2"), 2)
        self.assertEqual(main.owner_world([1, 2, 3], 9), 1, "a world with no board falls back")
        self.assertEqual(main.owner_world([1, 2, 3], "nonsense"), 1)
        self.assertIsNone(main.owner_world([2, 3], 9))

    def test_the_modals_settings_are_authoritative_even_when_absent(self):
        """It opens on one board and posts the whole set back, so no discCount
        means discovery off -- not "leave that world as it rolled"."""
        import main
        with main.app.test_request_context("/?difficulty=hard&lines=4"):
            opts = main.owner_board_opts("hard", 0, False)
        self.assertEqual(opts["discovery"], 0)
        self.assertIs(opts["meta"], False)
        self.assertEqual(opts["bingo_count"], 4)
        self.assertEqual(opts["goal"], "bingos")
        self.assertIsNone(opts["square_count"])
        with main.app.test_request_context("/?difficulty=hard&squares=13&discCount=3&meta=1"):
            opts = main.owner_board_opts("hard", 3, True)
        self.assertEqual(opts["square_count"], 13)
        self.assertEqual(opts["goal"], "squares")
        self.assertNotIn("bingo_count", opts, "squares mode leaves the line count alone")

    def test_board_for_falls_back_to_the_one_board(self):
        from models import BingoGameData
        b = BingoGameData()
        self.assertEqual(b.board_for(1), b.board)
        self.assertEqual(b.board_for(7), b.board, "one board serves every world")
        self.assertEqual(b.all_boards(), [b.board])




class BoardPayloadTestCase(NdbTestCase):
    """The payload carries a board per world, with the rules it finishes by."""


    def test_a_world_board_reports_its_own_rules(self):
        from models import BingoWorldBoard
        wb = BingoWorldBoard(world=2, board=[], bingo_count=5, square_count=13,
                             goal="bingos", difficulty="hard", meta=False, discovery=0)
        got = wb.to_json([], initial=True)
        self.assertEqual(got["bingo_count"], 5)
        self.assertEqual(got["difficulty"], "hard")
        self.assertIs(got["meta"], False)
        self.assertNotIn("discovery", got, "no revealed squares when discovery is off")

    def test_a_poll_carries_cards_without_the_rules(self):
        from models import BingoWorldBoard
        wb = BingoWorldBoard(world=1, board=[], bingo_count=3)
        got = wb.to_json([], initial=False)
        self.assertEqual(list(got), ["cards"], "a tick is progress only")




class BingoMultiworldNamesTestCase(NdbTestCase):
    """A bingo lobby hands names out itself; a multiworld names its worlds."""


    def params(self, mode, variations, worlds=None):
        from enums import KeyMode, LogicPath, MultiplayerGameType, PathDifficulty
        from seedbuilder.seedparams import MultiplayerOptions, SeedGenParams
        p = SeedGenParams(seed="bingonames")
        p.sync = MultiplayerOptions()
        p.sync.enabled = mode is not None
        if mode:
            p.sync.mode = mode
        p.spoilers, p.placements = [""], []
        p.logic_paths = [LogicPath.CASUAL_CORE]
        p.key_mode = KeyMode.CLUES
        p.path_diff = PathDifficulty.NORMAL
        p.players = 2
        p.variations = variations
        p.world_settings = worlds or []
        return p

    def test_a_bingo_multiworld_keeps_its_names(self):
        from enums import MultiplayerGameType
        from seedbuilder.seedparams import rolled_player_names
        p = self.params(MultiplayerGameType.MULTIWORLD, [Variation.BINGO])
        self.assertEqual(rolled_player_names(["Lapis", "Xemsys"], p), ["Lapis", "Xemsys"])

    def test_a_plain_bingo_lobby_still_stores_none(self):
        from enums import MultiplayerGameType
        from seedbuilder.seedparams import rolled_player_names
        p = self.params(MultiplayerGameType.SHARED, [Variation.BINGO])
        self.assertEqual(rolled_player_names(["Lapis", "Xemsys"], p), [])

    def test_from_params_sees_a_world_that_opted_in(self):
        from enums import MultiplayerGameType
        from seedbuilder.seedparams import bingo_worlds
        p = self.params(MultiplayerGameType.MULTIWORLD, [],
                        [{}, {"variations": ["Bingo"]}])
        self.assertEqual(bingo_worlds(p), [2], "the seed itself carries no Bingo")


if __name__ == "__main__":
    unittest.main()
