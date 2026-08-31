"""Every route that describes a rolled seed owes the page the same flag lines.

The seed tab splits shared flags from per-world ones using `flagLines`. Building
a seed and re-opening its page have to agree, or a refresh silently shows every
player world 1's rules.
"""
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


class WorldFlagLinesTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        creds = google.auth.credentials.AnonymousCredentials()
        cls.ndb_client = ndb.Client(project="unit-test", credentials=creds)

    def setUp(self):
        self._ctx = self.ndb_client.context()
        self._ctx.__enter__()

    def tearDown(self):
        self._ctx.__exit__(None, None, None)

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


if __name__ == "__main__":
    unittest.main()
