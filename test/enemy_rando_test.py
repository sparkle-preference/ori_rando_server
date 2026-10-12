"""Enemy rando, server side (2026-10-08): the flag rides the header and lure paths leave the walk.

Run from the repo root:  python3 -m unittest test.enemy_rando_test -v
"""
import unittest
from unittest import mock

from enums import Variation
from seedbuilder.generator import SeedGenerator
from test.cli_helpers import cli_lines, cli_params


class _Stop(Exception):
    pass


def areas_after_form(params):
    """The generator's areas right after form_areas, before any walking."""
    sg = SeedGenerator()
    with mock.patch.object(SeedGenerator, "create_warp_paths", side_effect=_Stop):
        try:
            sg.setSeedAndPlaceItems(params)
        except _Stop:
            pass
    return sg.areas


class LurePathsLeaveTheLogic(unittest.TestCase):
    PATHS = ["--custom-logic", "casual-core,standard-core,standard-lure"]

    def _roof_to_gauntlet(self, extra):
        areas = areas_after_form(cli_params(self.PATHS + extra))
        conns = [c for c in areas["DeathGauntletRoof|1"].connections if c.target == "DeathGauntlet|1"]
        self.assertEqual(len(conns), 1)
        return conns[0].get_requirements()

    def test_with_lures_the_edge_is_free(self):
        self.assertIn([], self._roof_to_gauntlet([]))

    def test_enemy_rando_keeps_only_the_stomp(self):
        self.assertEqual(self._roof_to_gauntlet(["--enemy-rando"]), [["Stomp|1"]])


class HeaderFlag(unittest.TestCase):
    def test_the_flag_rides_the_header_and_the_seed_still_rolls(self):
        seed = cli_lines(["--enemy-rando", "--open-world"])["randomizer0.bfr"]
        self.assertIn("EnemyRando", seed[0])
        self.assertEqual(seed[1], "// SEED_FORMAT: 2")

    def test_variation_round_trips(self):
        self.assertEqual(Variation.mk("EnemyRando"), Variation.ENEMY_RANDO)



class BingoDefeatGoals(unittest.TestCase):
    def test_defeat_goals_leave_the_pool(self):
        import random
        from bingo import BingoGenerator, DefeatGoal
        with_ = BingoGenerator.goal_pool(random.Random(1), True, "normal", True)
        without = BingoGenerator.goal_pool(random.Random(1), True, "normal", True, enemy_rando=True)
        self.assertTrue(any(isinstance(g, DefeatGoal) for g in with_))
        self.assertFalse(any(isinstance(g, DefeatGoal) for g in without))


class EnemyOptions(unittest.TestCase):
    def test_defaults_make_no_line(self):
        from seedbuilder import enemyopts
        self.assertIsNone(enemyopts.meta_line({}))
        self.assertIsNone(enemyopts.meta_line({"hp": "zone", "pool": enemyopts.KINDS, "logic": "on"}))

    def test_round_trip_and_order(self):
        from seedbuilder import enemyopts
        opts = {"logic": "off", "pool": ["Slimes", "Frogs"], "hp": "0.5-2"}
        line = enemyopts.meta_line(opts)
        self.assertEqual(line, "//Enemies=pool=Slimes+Frogs;hp=0.5-2;logic=off")
        self.assertEqual(enemyopts.parse_meta(line), enemyopts.normalize(opts))

    def test_bad_values_are_dropped(self):
        from seedbuilder import enemyopts
        self.assertIsNone(enemyopts.normalize({"hp": "9-0.1", "arena": "sure", "zzz": 1}))
        # an all-unknown pool stays empty so problem() can refuse it
        self.assertEqual(enemyopts.normalize({"pool": ["Dragons"]}), {"pool": []})
        self.assertEqual(enemyopts.normalize({"pool": ["Dragons", "Frogs"]}), {"pool": ["Frogs"]})

    def test_an_empty_pool_is_refused(self):
        from seedbuilder import enemyopts
        self.assertIn("at least one", enemyopts.problem({"pool": []}))
        self.assertIsNone(enemyopts.problem({"pool": ["Frogs"]}))
        from seedbuilder.seedparams import seed_mode_problem
        from types import SimpleNamespace
        p = SimpleNamespace(players=1, start="Glades", variations=[Variation.ENEMY_RANDO], world_settings=None,
                            ap_mode=False, sync=SimpleNamespace(enabled=False), enemy_opts={"pool": []})
        self.assertIn("at least one", seed_mode_problem(p))

    def test_the_presets_say_what_they_mean(self):
        from seedbuilder import enemyopts
        self.assertIsNone(enemyopts.meta_line(enemyopts.PRESETS["Standard"]))
        self.assertEqual(enemyopts.meta_line(enemyopts.PRESETS["Mild"]),
                         "//Enemies=pool=Fronkeys+Frogs+Slimes+Banelings+DropSlugs+Worms+Birds+Swarms+Spiders+Fish;keep=Worms;arena=kind;pools=off;walkers=off")
        self.assertEqual(enemyopts.meta_line(enemyopts.PRESETS["Chaos"]), "//Enemies=hp=0.5-2;dmg=0.5-2;flyingfish=on;shootercap=off")

    def test_the_cli_seed_carries_the_line(self):
        seed = cli_lines(["--enemy-rando", "--open-world", "--enemy-opts", "hp=0.5-2;pool=Frogs+Slimes;walkers=off"])["randomizer0.bfr"]
        self.assertIn("//Enemies=pool=Frogs+Slimes;hp=0.5-2;walkers=off", seed)
        plain = cli_lines(["--enemy-rando", "--open-world"])["randomizer0.bfr"]
        self.assertFalse(any(l.startswith("//Enemies=") for l in plain))


class EnemyOptionsDownload(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import google.auth.credentials
        from google.cloud import ndb
        cls.ndb_client = ndb.Client(project="unit-test", credentials=google.auth.credentials.AnonymousCredentials())

    def setUp(self):
        self._ctx = self.ndb_client.context()
        self._ctx.__enter__()

    def tearDown(self):
        self._ctx.__exit__(None, None, None)

    def test_the_line_is_rebuilt_on_download(self):
        from enums import KeyMode, LogicPath, PathDifficulty
        from seedbuilder.seedparams import MultiplayerOptions, SeedGenParams
        p = SeedGenParams(seed="enemies")
        p.sync = MultiplayerOptions()
        p.spoilers, p.placements = [""], []
        p.logic_paths = [LogicPath.CASUAL_CORE]
        p.key_mode = KeyMode.CLUES
        p.path_diff = PathDifficulty.NORMAL
        p.variations = [Variation.ENEMY_RANDO]
        p.players = 1
        p.tracking = False
        p.enemy_opts = {"walkers": "off", "pool": ["Frogs"]}
        self.assertIn("//Enemies=pool=Frogs;walkers=off", p.get_seed(1).splitlines())
        p.enemy_opts = None
        self.assertFalse(any(l.startswith("//Enemies=") for l in p.get_seed(1).splitlines()))


class EnemyOptionsRefusals(unittest.TestCase):
    def _params(self, variations, opts=None):
        from types import SimpleNamespace
        return SimpleNamespace(players=1, start="Glades", variations=variations, world_settings=None,
                               ap_mode=False, sync=SimpleNamespace(enabled=False), enemy_opts=opts)

    def test_a_bad_range_is_refused_not_dropped(self):
        from seedbuilder.seedparams import seed_mode_problem
        self.assertIn("health range", seed_mode_problem(self._params([Variation.ENEMY_RANDO], {"hp": "0.1-2"})))
        self.assertIn("damage range", seed_mode_problem(self._params([Variation.ENEMY_RANDO], {"dmg": "2-1"})))
        self.assertIsNone(seed_mode_problem(self._params([Variation.ENEMY_RANDO], {"hp": "0.5-2", "dmg": "vanilla"})))

    def test_a_non_string_mode_is_a_refusal(self):
        from seedbuilder.seedparams import seed_mode_problem
        self.assertIn("health range", seed_mode_problem(self._params([Variation.ENEMY_RANDO], {"hp": 3})))


if __name__ == "__main__":
    unittest.main()
