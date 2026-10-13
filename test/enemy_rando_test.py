"""Enemy rando, server side: the flag rides the header and lure paths leave the walk."""
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

    def test_the_plando_builder_knows_every_variation(self):
        import os
        import re
        src = open(os.path.join(os.path.dirname(__file__), "..", "map", "src", "PlandoBuilder.js"), encoding="utf-8").read()
        listed = set(re.findall(r'"(\w+)"', re.search(r"const VALID_VARS = \[(.*?)\]", src, re.S).group(1)))
        self.assertEqual(set(v.value for v in Variation) - listed, set())

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

    def test_deaths_to_a_rolled_enemy_leave_the_pool(self):
        import random
        from bingo import BingoGenerator
        rolled = {"Valley Map Baneling", "Valley Floor Frogs", "Ginso Escape Fronkey"}
        names = lambda pool: {g.name for group in pool if group.name == "DieTo" for g in group.goals}
        with_ = names(BingoGenerator.goal_pool(random.Random(1), True, "normal", True))
        without = names(BingoGenerator.goal_pool(random.Random(1), True, "normal", True, enemy_rando=True))
        self.assertEqual(with_ & rolled, rolled)
        self.assertEqual(without & rolled, set())
        # pinned ones stay
        self.assertIn("Stomp Rhino", without)
        self.assertIn("R1 Door Baneling", without)


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
        # an all-unknown pool stays empty, never defaulted
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

    def test_a_world_preset_at_standard_options_does_not_take_world_ones(self):
        from types import SimpleNamespace
        from seedbuilder.seedparams import world_view
        chaos = {"hp": "0.5-2", "dmg": "0.5-2"}
        # a saved preset leaves Standard options out entirely
        base = SimpleNamespace(enemy_opts=chaos, world_settings=[
            {}, {"variations": ["EnemyRando"]}, {"variations": ["EnemyRando"], "enemyOpts": {"walkers": "off"}}])
        self.assertEqual(world_view(base, 1).enemy_opts, chaos)
        self.assertEqual(world_view(base, 2).enemy_opts, {})
        self.assertEqual(world_view(base, 3).enemy_opts, {"walkers": "off"})

    def test_default_options_load_as_an_empty_object(self):
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
        p.enemy_opts = None
        self.assertEqual(p.to_json()["enemyOpts"], {})

    def test_a_plando_rolls_from_its_name(self):
        from models import Seed
        from seedbuilder import enemyroll
        from seedbuilder.seedparams import SeedGenParams
        put, SeedGenParams.put = SeedGenParams.put, lambda self: None
        try:
            params = SeedGenParams.from_plando(Seed(id="uid:En", name="En", players=1, placements=[], flags=["EnemyRando"]))
        finally:
            SeedGenParams.put = put
        params.tracking = False
        self.assertIn(enemyroll.meta_line(enemyroll.roll("En", 1, None)), params.get_seed(1).splitlines())

    def test_a_plando_downloads_the_rolls_its_fill_made(self):
        from models import Seed
        from seedbuilder import enemyroll
        from seedbuilder.seedparams import SeedGenParams
        filled = enemyroll.roll("some fill seed", 1, None)
        self.assertNotEqual(filled, enemyroll.roll("En", 1, None))
        rolls = Seed.get_enemy_rolls({"1": enemyroll.meta_line(filled)})
        put, SeedGenParams.put = SeedGenParams.put, lambda self: None
        try:
            params = SeedGenParams.from_plando(Seed(id="uid:En", name="En", players=1, placements=[], flags=["EnemyRando"],
                                                    enemy_rolls=rolls))
        finally:
            SeedGenParams.put = put
        params.tracking = False
        self.assertIn(enemyroll.meta_line(filled), params.get_seed(1).splitlines())

    def test_only_rolls_made_against_this_table_are_kept(self):
        from models import Seed
        from seedbuilder import enemyroll
        good = enemyroll.roll("x", 1, None)
        line = enemyroll.meta_line(good)
        self.assertEqual(enemyroll.rolls_of(line), good)
        body = line.split(":", 1)[1]
        for bad in (enemyroll.META_PREFIX + "00000000:" + body,     # another table
                    line + ",1",                                    # one placement too many
                    line.replace(":", ":99999,", 1)[:len(line) + 7],  # a variant that doesn't exist
                    enemyroll.META_PREFIX + enemyroll.table()["version"] + ":x",
                    "//Enemies=hp=1", None, 5):
            self.assertIsNone(enemyroll.rolls_of(bad), bad)
        self.assertEqual(Seed.get_enemy_rolls({"1": line, "2": "junk", "w": line}), {"1": good})
        self.assertIsNone(Seed.get_enemy_rolls({"1": "junk"}))
        self.assertIsNone(Seed.get_enemy_rolls(None))

    def test_the_page_presets_mirror_the_server(self):
        import os
        from seedbuilder import enemyopts
        page = open(os.path.join(os.path.dirname(__file__), "..", "map", "src", "MainPage.js"), encoding="utf-8").read()
        mild, chaos = enemyopts.PRESETS["Mild"], enemyopts.PRESETS["Chaos"]
        dropped = [k for k in enemyopts.KINDS if k not in mild["pool"]]
        self.assertIn('Mild: {pool: ENEMY_KINDS.filter(k => ![%s].includes(k)), keep: [%s], arena: "%s", pools: "%s", walkers: "%s"}' % (
            ", ".join('"%s"' % k for k in dropped), ", ".join('"%s"' % k for k in mild["keep"]), mild["arena"], mild["pools"], mild["walkers"]), page)
        self.assertIn('Chaos: {hp: "%s", dmg: "%s", flyingfish: "%s", shootercap: "%s"}' % (chaos["hp"], chaos["dmg"], chaos["flyingfish"], chaos["shootercap"]), page)


class EnemyOptionsRefusals(unittest.TestCase):
    def _params(self, variations, opts=None):
        from types import SimpleNamespace
        return SimpleNamespace(players=1, start="Glades", variations=variations, world_settings=None,
                               ap_mode=False, sync=SimpleNamespace(enabled=False), enemy_opts=opts)

    def test_archipelago_is_refused(self):
        from types import SimpleNamespace
        from seedbuilder.seedparams import seed_mode_problem
        with mock.patch("util.ARCHIPELAGO", True):
            p = self._params([Variation.ENEMY_RANDO])
            p.ap_mode, p.tracking = True, True
            self.assertEqual(seed_mode_problem(p), "Enemy Rando can't be combined with Archipelago yet.")
            # a world's own preset counts too
            p.variations, p.players = [], 2
            p.world_settings = [{}, {"variations": ["EnemyRando"]}]
            self.assertEqual(seed_mode_problem(p), "Enemy Rando can't be combined with Archipelago yet.")
            p.world_settings = None
            self.assertNotIn("Enemy Rando", seed_mode_problem(p) or "")

    def test_a_bad_range_is_refused_not_dropped(self):
        from seedbuilder.seedparams import seed_mode_problem
        self.assertIn("health range", seed_mode_problem(self._params([Variation.ENEMY_RANDO], {"hp": "0.1-2"})))
        self.assertIn("damage range", seed_mode_problem(self._params([Variation.ENEMY_RANDO], {"dmg": "2-1"})))
        self.assertIsNone(seed_mode_problem(self._params([Variation.ENEMY_RANDO], {"hp": "0.5-2", "dmg": "vanilla"})))

    def test_the_cli_refuses_bad_options(self):
        with self.assertRaises(SystemExit):
            cli_params(["--enemy-rando", "--enemy-opts", "hp=9-1"])

    def test_a_non_string_mode_is_a_refusal(self):
        from seedbuilder.seedparams import seed_mode_problem
        self.assertIn("health range", seed_mode_problem(self._params([Variation.ENEMY_RANDO], {"hp": 3})))


if __name__ == "__main__":
    unittest.main()
