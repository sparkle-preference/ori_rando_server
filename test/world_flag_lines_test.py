"""Every route that describes a rolled seed owes the page the same flag lines.

The seed tab splits shared flags from per-world ones using `flagLines`. Building
a seed and re-opening its page have to agree, or a refresh silently shows every
player world 1's rules.
"""
import io
import os
import re
import unittest

import google.auth.credentials
from google.cloud import ndb

import main
from web import generator
from enums import KeyMode, LogicPath, MultiplayerGameType, PathDifficulty, Variation
from seedbuilder.seedparams import MultiplayerOptions, SeedGenParams


def mw_params(worlds):
    p = SeedGenParams(seed="flaglines")
    p.sync = MultiplayerOptions()
    p.sync.enabled = True
    p.sync.mode = MultiplayerGameType.MULTIWORLD
    p.spoilers, p.placements = [""], []
    p.logic_paths = [LogicPath.CASUAL_CORE]
    p.key_mode = KeyMode.CLUES
    p.path_diff = PathDifficulty.NORMAL
    p.variations = [Variation.FORCE_TREES]
    p.players = max(len(worlds), 1)
    p.world_settings = worlds
    return p


class NdbCase(unittest.TestCase):
    """Reading a params field wants a context, and both suites below build one."""

    @classmethod
    def setUpClass(cls):
        creds = google.auth.credentials.AnonymousCredentials()
        cls.ndb_client = ndb.Client(project="unit-test", credentials=creds)

    def setUp(self):
        self._ctx = self.ndb_client.context()
        self._ctx.__enter__()

    def tearDown(self):
        self._ctx.__exit__(None, None, None)


class WorldFlagLinesTestCase(NdbCase):
    def test_one_line_per_world_when_they_differ(self):
        lines = generator.world_flag_lines(mw_params([{}, {"keyMode": "Shards"}]))
        self.assertEqual(len(lines), 2)
        self.assertIn("Clues", lines[0])
        self.assertIn("Shards", lines[1])

    def test_nothing_to_say_when_no_world_overrides(self):
        """Absent means one rulebook, and the page renders as it always did."""
        self.assertIsNone(generator.world_flag_lines(mw_params([])))

    def test_a_params_object_without_the_field_is_fine(self):
        """cli_gen's params carry no world_settings at all."""
        class Bare(object):
            players = 2
        self.assertIsNone(generator.world_flag_lines(Bare()))

    def test_a_line_for_every_player_even_past_the_overrides(self):
        p = mw_params([{}, {"keyMode": "Shards"}])
        p.players = 4
        self.assertEqual(len(generator.world_flag_lines(p)), 4)


class MixedBingoTestCase(NdbCase):
    """Bingo can be on for one world and off for another. Everything that used to
    read the seed's own variations answered world 1 for everybody."""

    def test_only_the_bingo_world_says_bingo(self):
        lines = generator.world_flag_lines(mw_params([{"variations": ["Bingo"]}, {}]))
        self.assertIn("Bingo", lines[0])
        self.assertNotIn("Bingo", lines[1])

    def test_a_mixed_seed_does_not_redirect_to_a_board(self):
        p = mw_params([{"variations": ["Bingo"]}, {}])
        self.assertFalse(generator.every_world_plays_bingo(p))

    def test_every_world_playing_still_redirects(self):
        p = mw_params([{"variations": ["Bingo"]}, {"variations": ["Bingo"]}])
        self.assertTrue(generator.every_world_plays_bingo(p))

    def test_one_rulebook_reads_off_the_seed(self):
        """No overrides means every world is the base, bingo included."""
        p = mw_params([])
        p.players, p.variations = 1, [Variation.BINGO]
        self.assertTrue(generator.every_world_plays_bingo(p))
        p.variations = [Variation.FORCE_TREES]
        self.assertFalse(generator.every_world_plays_bingo(p))


class SeedTabBingoTestCase(unittest.TestCase):
    """The seed tab builds one row per player, so a per-world answer has to be
    asked per row rather than once for the seed."""

    def rows(self):
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "map", "src", "MainPage.js")
        with io.open(path, encoding="utf-8") as f:
            page = f.read()
        got = re.search(r"let playerRows = .*?\n            \}\)", page, re.S)
        self.assertIsNotNone(got, "playerRows no longer matches the page")
        return got.group(0)

    def test_the_row_asks_for_its_own_world(self):
        self.assertIn("worldIsBingo(p)", self.rows())

    def test_no_row_reads_the_seed_wide_flag(self):
        self.assertNotIn("seedIsBingo", self.rows())


if __name__ == "__main__":
    unittest.main()
