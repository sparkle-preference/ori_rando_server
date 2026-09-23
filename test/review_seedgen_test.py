"""Seedgen review: pins current behavior and marks confirmed defects as expected failures."""
import os
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from collections import OrderedDict
from unittest import mock

from cli_gen import CLISeedParams
from enums import Variation
from seedbuilder.generator import SeedGenerator
from seedbuilder.oriparse import ori_load

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FORLORN_PLANT = -12320248


def cli_seed(extra, seed="test"):
    """Run cli_gen with the standard test flags; returns {filename: text}."""
    out = tempfile.mkdtemp(prefix="reviewseedgen_")
    old = sys.argv
    sys.argv = ["cli_gen", "--output-dir", out, "--preset", "standard", "--open-world",
                "--force-trees", "--seed", seed] + extra
    try:
        CLISeedParams().from_cli()
        files = {}
        for name in os.listdir(out):
            with open(os.path.join(out, name)) as f:
                files[name] = f.read()
        return files
    finally:
        sys.argv = old
        shutil.rmtree(out, ignore_errors=True)


def body(seed_text):
    return [l for l in seed_text.splitlines()[1:] if l and not l.startswith("//")]


def cli_params(extra, seed="test"):
    """The params cli_gen would generate from, without generating."""
    captured = []
    with mock.patch.object(SeedGenerator, "setSeedAndPlaceItems", lambda sg, params, **kw: captured.append(params)):
        cli_seed(extra, seed)
    return captured[0]


class ForlornPlantFassTests(unittest.TestCase):
    def test_plain_plant_holds_its_default(self):
        lines = body(cli_seed([])["randomizer0.bfr"])
        self.assertIn("%s|EX|100|Forlorn" % FORLORN_PLANT, lines)

    # defect: a plant fass is never taken out of the pool, so the item is placed twice
    @unittest.expectedFailure
    def test_plant_fass_places_the_item_once(self):
        lines = body(cli_seed(["--fass=%s:SK0" % FORLORN_PLANT])["randomizer0.bfr"])
        self.assertEqual(len([l for l in lines if l.split("|")[1:3] == ["SK", "0"]]), 1)

    def test_cross_world_plant_fass_is_a_well_formed_mw_line(self):
        seeds = cli_seed(["--fass=1.%s:SK0@2" % FORLORN_PLANT, "--players", "2",
                          "--share-mode", "multiworld", "--tracking"])
        plant = [l for l in body(seeds["randomizer_1.bfr"]) if l.startswith("%s|" % FORLORN_PLANT)]
        self.assertEqual(len(plant), 1)
        fields = plant[0].split("|")
        self.assertEqual(len(fields), 4, plant[0])
        self.assertEqual(fields[1], "MW")
        self.assertTrue(fields[2].startswith("2,") and fields[2].endswith(",SK,0"), plant[0])


class FinaleFassTests(unittest.TestCase):
    FINALE = -2399488

    def test_forced_finale_leaves_no_location_empty(self):
        plain = body(cli_seed([], "f2")["randomizer0.bfr"])
        lines = body(cli_seed(["--fass=%s:RB6" % self.FINALE], "f2")["randomizer0.bfr"])
        self.assertIn("%s|RB|6|Horu" % self.FINALE, lines)
        self.assertEqual({l.split("|")[0] for l in lines}, {l.split("|")[0] for l in plain})
        self.assertEqual(len([l for l in lines if l.split("|")[1:3] == ["RB", "6"]]), 3)

    def test_forced_finale_never_counts_in_logic(self):
        self.assertNotIn("randomizer0.bfr", cli_seed(["--fass=%s:SK0" % self.FINALE], "f1"))


class CellFassTests(unittest.TestCase):
    def test_single_cell_fass_comes_out_of_the_pool(self):
        for cell, count in (("HC1", 12), ("KS1", 38)):
            lines = body(cli_seed(["--fass=919772:%s" % cell], "c1")["randomizer0.bfr"])
            self.assertIn("919772|%s|1|Glades" % cell[:2], lines)
            self.assertEqual(len([l for l in lines if l.split("|")[1] == cell[:2]]), count, cell)


class ClosedDungeonSpawnTests(unittest.TestCase):
    # a SystemExit here would kill the gunicorn worker
    def test_refusal_is_not_a_system_exit(self):
        try:
            cli_seed(["--start", "Horu", "--closed-dungeons"])
        except Exception:
            pass
        except BaseException as e:
            self.fail("generation raised %r" % e)


class WorldTourRepeatableTests(unittest.TestCase):
    def test_every_repeatable_is_placed(self):
        for seed in ["wt%d" % i for i in range(12)]:
            lines = body(cli_seed(["--world-tour", "8", "--bonus-pickups"], seed)["randomizer0.bfr"])
            self.assertEqual(len([l for l in lines if l.split("|")[1] == "RP"]), 6, seed)
            relics = {l.split("|")[0] for l in lines if l.split("|")[1] == "WT"}
            self.assertEqual(len(relics), 8, seed)


class _Params(object):
    """The bits of params assign_random reads."""
    def __init__(self, variations):
        self.variations = variations
        self.anti_bk_bias = 0.0


def _sg(variations, seed):
    sg = SeedGenerator()
    sg.params = _Params(variations)
    sg.world_params = {}
    sg.random = random.Random(seed)
    sg.itemPool = OrderedDict([("Bash|1", 1), ("KS|1", 1)])
    return sg


class AssignRandomLocalBlockedTests(unittest.TestCase):
    def test_blocked_key_is_never_drawn(self):
        for seed in range(50):
            got = _sg([], seed).assign_random(0, local_blocked=frozenset({"KS|1"}))
            self.assertEqual(got, "Bash|1")

    def test_blocked_key_survives_a_starved_reroll(self):
        for seed in range(50):
            got = _sg([Variation.STARVED], seed).assign_random(0, local_blocked=frozenset({"KS|1"}))
            self.assertNotEqual(got, "KS|1", "seed %s" % seed)


class FromUrlFassTests(unittest.TestCase):
    def _from_url(self, fass):
        from werkzeug.datastructures import MultiDict
        from seedbuilder.seedparams import SeedGenParams
        saved = []
        q = MultiDict([("path", "casual-core"), ("players", "2"), ("sync_mode", "Multiworld"),
                       ("fass", fass), ("tracking", "Disabled"), ("seed", "5")])
        with mock.patch.object(SeedGenParams, "put", lambda self: saved.append(self) or "key"):
            SeedGenParams.from_url(q)
        return saved[0]

    def test_plain_fass_parses(self):
        params = self._from_url("919772:SK0")
        self.assertEqual([(p.location, p.stuff[0].code, p.stuff[0].id) for p in params.placements],
                         [("919772", "SK", "0")])

    def test_world_prefixed_fass_parses(self):
        params = self._from_url("1.919772:SK0|2.919772:SK0@1")
        self.assertEqual([(p.location, p.stuff[0].player, p.stuff[0].owner) for p in params.placements],
                         [("919772", "1", None), ("919772", "2", "1")])

    def test_spawn_rows_never_cross_worlds(self):
        params = self._from_url("2.2:SK0@1")
        self.assertIsNone(params.placements[0].stuff[0].owner)
        self.assertIsNone(params.spawn_placement)

    def test_owner_survives_into_the_rolled_seed(self):
        from seedbuilder.seedparams import SeedGenParams
        params = self._from_url("1.919772:SK0@2")
        with mock.patch.object(SeedGenParams, "put", lambda self: None):
            self.assertTrue(params.generate())
        by_world = {(p.location, s.player): s for p in params.placements for s in p.stuff}
        finder = by_world[("919772", "1")]
        self.assertEqual(finder.code, "MW")
        self.assertTrue(finder.id.startswith("2,") and finder.id.endswith(",SK,0"), finder.id)


class FromJsonSeedTests(unittest.TestCase):
    def test_missing_seed_is_refused(self):
        from seedbuilder.seedparams import SeedGenParams
        with mock.patch.object(SeedGenParams, "put", lambda self: "key"):
            self.assertIsNone(SeedGenParams.from_json({"paths": ["casual-core"]}))


class TeamStrTests(unittest.TestCase):
    def test_lists_each_teams_members(self):
        from seedbuilder.seedparams import MultiplayerOptions
        self.assertEqual(MultiplayerOptions(teams={"1": [1, 2], "2": [3]}).get_team_str(), "1,2|3")


class OriParseTests(unittest.TestCase):
    def test_minimal_file_parses(self):
        meta = ori_load(["home: A\n", "conn: B\n", "casual Free\n", "home: B\n"])
        self.assertIn("B", meta["homes"]["A"]["conns"])

    def test_conn_to_missing_home_warns_instead_of_raising(self):
        meta = ori_load(["home: A\n", "conn: B\n", "casual Free\n"])
        self.assertIn("A", meta["homes"])


_REACH_SCRIPT = """
import sys
sys.path.insert(0, %r)
from reachable import Map, full_state
state = full_state()
state.has["KS"] = 4
modes = ("casual-core", "casual-dboost", "standard-core", "standard-dboost", "standard-lure", "standard-abilities")
print(len(Map.get_reachable_areas(state, modes, "Glades", need_reached_with=False)))
""" % ROOT


class ReachableTests(unittest.TestCase):
    def _count(self, hashseed):
        env = dict(os.environ, PYTHONHASHSEED=str(hashseed))
        out = subprocess.run([sys.executable, "-c", _REACH_SCRIPT], env=env, cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout
        return int(out.strip().splitlines()[-1])

    # keystone spending follows visit order, so the hash seed must not change it
    def test_same_inventory_same_areas_in_every_process(self):
        self.assertEqual(self._count(0), self._count(1))

    # 64 request threads share one Map
    def test_interleaved_call_leaves_requirement_lists_alone(self):
        from reachable import Area, Map, PlayerState, full_state
        modes = ("casual-core", "casual-dboost")
        real = Area.get_reachable
        calls = []

        def counting(self, *a, **kw):
            calls.append(1)
            if len(calls) == fire_at:  # another request lands just before this walk finishes
                Map.get_reachable_areas(PlayerState([]), modes)
            return real(self, *a, **kw)

        fire_at = 0
        with mock.patch.object(Area, "get_reachable", counting):
            clean = Map.get_reachable_areas(full_state(), modes)
            fire_at, calls[:] = len(calls), []
            got = Map.get_reachable_areas(full_state(), modes)
        self.assertEqual({k: sorted(map(str, v)) for k, v in got.items()},
                         {k: sorted(map(str, v)) for k, v in clean.items()})

class CliParamsTests(unittest.TestCase):
    def test_start_is_case_insensitive(self):
        self.assertEqual(cli_params(["--start", "random"]).start, "Random")


class GeneratorParamsRestoredTests(unittest.TestCase):
    def test_retry_skill_bump_is_not_kept(self):
        params = cli_params(["--start", "Grotto", "--starting-skills", "1"])
        seen = []

        def failing(sg, depth=0, worried=False):
            sg.reset(worried)
            sg.reservedLocations = []
            seen.append(sg.params.starting_skills)

        with mock.patch.object(SeedGenerator, "placeItems", failing):
            self.assertIsNone(SeedGenerator().setSeedAndPlaceItems(params))
        self.assertGreater(max(seen), 1, "late retries still get the extra skill")
        self.assertEqual(params.starting_skills, 1)

    def test_balanced_survives_a_failed_finale(self):
        params = cli_params([])
        real = SeedGenerator.assign_to_location

        def boom(sg, item, location):
            if location.orig == "EVWarmth":
                raise RuntimeError("finale")
            return real(sg, item, location)

        with mock.patch.object(SeedGenerator, "assign_to_location", boom):
            with self.assertRaises(RuntimeError):
                SeedGenerator().setSeedAndPlaceItems(params)
        self.assertTrue(params.balanced)


if __name__ == "__main__":
    unittest.main()


class ClosedDungeonSpawnGate(unittest.TestCase):
    def test_the_request_is_refused_before_generation(self):
        from types import SimpleNamespace
        from enums import Variation
        from seedbuilder.seedparams import seed_mode_problem
        p = SimpleNamespace(players=1, start="Ginso", variations=[Variation.CLOSED_DUNGEONS], world_settings=None)
        self.assertIn("Closed Dungeons", seed_mode_problem(p))


class PlayerCap(unittest.TestCase):
    def _params(self, players):
        from types import SimpleNamespace
        return SimpleNamespace(players=players, start="Glades", variations=[], world_settings=None,
                               sync=SimpleNamespace(enabled=False))

    def test_the_default_cap_is_sixteen(self):
        from seedbuilder.seedparams import seed_mode_problem
        self.assertIsNone(seed_mode_problem(self._params(16)))
        self.assertIn("16 players", seed_mode_problem(self._params(17)))

    def test_the_cap_follows_the_env_setting(self):
        import util
        from seedbuilder.seedparams import player_cap_problem
        self.addCleanup(setattr, util, "MAX_PLAYERS", util.MAX_PLAYERS)
        util.MAX_PLAYERS = 4
        self.assertIsNotNone(player_cap_problem(self._params(5)))
        self.assertIsNone(player_cap_problem(self._params(4)))
