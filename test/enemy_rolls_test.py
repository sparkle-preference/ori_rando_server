"""Enemy rando, the server's roll: one variant per placement, pinned where logic needs it."""
import unittest
from collections import Counter
from unittest import mock

from enums import Variation
from seedbuilder import enemyroll
from test.cli_helpers import cli_lines

SWAMP_WORM = "179076552 1311765353 1965435571 -714190241"       # thornfeltSwampB mortar puzzle
BLACKROOT_FROG = "-1085265029 1116939093 62547864 -69710347"     # mangroveFallsGrenadeEscalation inner frog
GINSO_SPIDER = "-1263549180 1170154257 -1067946366 -187927078"  # ginsoTreeTurrets top-left
GINSO_WORM = "-1125269552 1188639931 305142159 -383820321"      # the miniboss worm: a kill arena, free to roll


def rolled(seed="test", world=1, opts=None):
    t = enemyroll.table()
    rolls = enemyroll.roll(seed, world, opts)
    index = {p["guid"]: i for i, p in enumerate(t["placements"])}
    return t, rolls, lambda guid: None if rolls[index[guid]] is None else t["variants"][rolls[index[guid]]]


def parse_meta(line):
    """The rolls on one of our //EnemyRolls= lines, else None."""
    if not line.lower().startswith(enemyroll.META_PREFIX.lower()):
        return None
    version, _, body = line[len(enemyroll.META_PREFIX):].strip().partition(":")
    if version != enemyroll.table()["version"]:
        return None
    rolls = [None if r == "" else int(r) for r in body.split(",")]
    return rolls if len(rolls) == len(enemyroll.table()["placements"]) else None


class TheRoll(unittest.TestCase):
    def test_one_entry_per_placement_and_the_same_every_time(self):
        t, a, _ = rolled()
        self.assertEqual(len(a), len(t["placements"]))
        self.assertEqual(a, enemyroll.roll("test", 1, None))
        self.assertNotEqual(a, enemyroll.roll("test", 2, None))
        self.assertNotEqual(a, enemyroll.roll("other", 1, None))

    def test_puzzle_pins_hold_even_with_logic_off(self):
        for opts in (None, {"logic": "off"}):
            _, _, at = rolled(opts=opts)
            self.assertTrue(at(SWAMP_WORM)["prefab"].startswith("mortarWorm"), opts)
            self.assertEqual(at(BLACKROOT_FROG)["prefab"], "spitterEnemy", opts)

    def test_a_kept_shooter_stays_in_its_family_and_never_becomes_a_laser(self):
        for seed in ("a", "b", "c", "d", "e"):
            _, _, at = rolled(seed)
            v = at(GINSO_SPIDER)
            self.assertIn(v["kind"], ("Spiders", "Elementals"), seed)
            self.assertNotEqual(v["prefab"], "floatingRockLaserEnemy", seed)

    def test_the_ginso_miniboss_worm_is_free(self):
        kinds = {rolled(seed)[2](GINSO_WORM)["kind"] for seed in ("a", "b", "c", "d", "e", "f")}
        self.assertGreater(len(kinds), 1)

    def test_pool_keep_and_arena_options_bite(self):
        t, rolls, _ = rolled(opts={"pool": ["Frogs"]})
        for p, r in zip(t["placements"], rolls):
            if r is not None:
                self.assertIn(t["variants"][r]["kind"], ("Frogs", p["kind"]))
        t, rolls, _ = rolled(opts={"keep": ["Slimes"]})
        self.assertTrue(all(r is None for p, r in zip(t["placements"], rolls) if p["kind"] == "Slimes"))
        t, rolls, _ = rolled(opts={"arena": "kind"})
        self.assertTrue(all(r is None for p, r in zip(t["placements"], rolls) if p["arena"]))

    def test_floor_spots_lean_toward_slimes_and_away_from_the_bruisers(self):
        t = enemyroll.table()
        counts = Counter()
        for seed in range(12):
            for p, r in zip(t["placements"], enemyroll.roll(str(seed), 1, None)):
                # level floor spots that held none of the weighted kinds: every candidate is a change there
                if r is not None and p["spot"] == "floor" and p["flat"] and p["kind"] in ("Fronkeys", "Frogs", "Worms"):
                    counts[t["variants"][r]["kind"]] += 1
        for bruiser in ("Rhinos", "Sharks", "Banelings"):
            self.assertGreater(counts["Slimes"], 2 * counts[bruiser], bruiser)
            self.assertGreater(counts["Fronkeys"], counts[bruiser], bruiser)

    def test_the_shooter_cap_and_flying_fish_switches(self):
        t = enemyroll.table()
        ranged = lambda rolls: sum(1 for r in rolls if r is not None and t["variants"][r]["kind"] in enemyroll.RANGED)
        capped, free = enemyroll.roll("test", 1, None), enemyroll.roll("test", 1, {"shootercap": "off"})
        self.assertGreater(ranged(free), ranged(capped))
        fish = lambda rolls: sum(1 for p, r in zip(t["placements"], rolls) if r is not None and t["variants"][r]["kind"] == "Fish" and p["spot"] != "water")
        self.assertEqual(fish(capped), 0)
        self.assertGreater(fish(enemyroll.roll("test", 1, {"flyingfish": "on"})), 0)

    def test_grounded_kinds_take_level_or_gentle_ground_and_the_grotto_shark_is_scripted(self):
        t = enemyroll.table()
        for seed in ("a", "b", "c", "d", "e", "f"):
            rolls = enemyroll.roll(seed, 1, None)
            for p, r in zip(t["placements"], rolls):
                kind = t["variants"][r]["kind"] if r is not None else None
                if p["spot"] == "floor" and kind in enemyroll.GROUNDED and p["kind"] != kind:
                    self.assertTrue(p["gentle"] if kind in enemyroll.SLOPE_OK else p["flat"], (seed, p["scene"], kind))
                if p["scene"] == "moonGrottoEnemyPuzzle" and p["kind"] == "Sharks":
                    self.assertIsNone(r)

    def test_banelings_and_rhinos_take_gentle_slopes_and_sharks_do_not(self):
        t = enemyroll.table()
        sloped = [i for i, p in enumerate(t["placements"])
                  if p["spot"] == "floor" and p["gentle"] and not p["flat"] and p["kind"] not in enemyroll.GROUNDED]
        self.assertTrue(sloped)
        landed = Counter()
        for seed in range(60):
            rolls = enemyroll.roll(str(seed), 1, None)
            for i in sloped:
                if rolls[i] is not None:
                    landed[t["variants"][rolls[i]]["kind"]] += 1
        self.assertGreater(landed["Banelings"], 0)
        self.assertGreater(landed["Rhinos"], 0)
        self.assertEqual(landed["Sharks"], 0)

    def test_an_elemental_behind_a_purple_door_wants_a_killer(self):
        t = enemyroll.table()
        index = {p["guid"]: i for i, p in enumerate(t["placements"])}
        rolls = [None] * len(t["placements"])
        rolls[index[GINSO_WORM]] = next(i for i, v in enumerate(t["variants"]) if v["prefab"] == "floatTurretEnemyFire")
        # vanilla's own elemental rooms and the swamp rhino are always listed
        self.assertEqual(enemyroll.arena_threats([None] * len(rolls)),
                         {"ginsoTreeResurrection": ["Elementals"], "mountHoruProjectileCorridor": ["Elementals"], "thornfeltSwampStompAbility": ["Rhinos"]})
        self.assertEqual(enemyroll.arena_threats(rolls)["ginsoTreePuzzles"], ["Elementals"])
        self.assertEqual(enemyroll.gated_edges({"ginsoTreePuzzles": ["Elementals"], "nowhere": ["Rhinos"]}), {("LowerGinsoTree", "GinsoMiniBossDoor"): ["Elementals"]})
        self.assertEqual(enemyroll.kill_paths((("casual",), "WallJump"), ["Elementals"]), [(("casual",), "WallJump", k) for k in enemyroll.KILLERS["Elementals"]])
        self.assertEqual(enemyroll.kill_paths((("casual",), "Bash", "Grenade"), ["Elementals"]), [(("casual",), "Bash", "Grenade")])
        # a rhino and an elemental together: Bash alone isn't enough, Stomp alone is
        self.assertEqual(enemyroll.kill_paths((("casual",), "Bash"), ["Elementals", "Rhinos"]), [(("casual",), "Bash", k) for k in ("Stomp", "ChargeFlame", "Grenade")])
        self.assertEqual(enemyroll.kill_paths((("casual",), "Stomp"), ["Elementals", "Rhinos"]), [(("casual",), "Stomp")])
        from test.enemy_rando_test import areas_after_form
        from test.cli_helpers import cli_params
        with mock.patch.object(enemyroll, "roll", return_value=rolls):
            areas = areas_after_form(cli_params(["--enemy-rando"]))
        conns = [c for c in areas["LowerGinsoTree|1"].connections if c.target == "GinsoMiniBossDoor|1"]
        self.assertEqual(len(conns), 1)
        for req in conns[0].get_requirements():
            self.assertTrue(any(k + "|1" in req for k in enemyroll.KILLERS["Elementals"]), req)

    def test_the_line_round_trips(self):
        t, rolls, _ = rolled()
        line = enemyroll.meta_line(rolls)
        self.assertTrue(line.startswith("//EnemyRolls=" + t["version"] + ":"))
        self.assertEqual(parse_meta(line), rolls)
        self.assertIsNone(parse_meta("//EnemyRolls=00000000:1,2"))
        self.assertIsNone(parse_meta("//Enemies=hp=zone"))


class TheSeedCarriesIt(unittest.TestCase):
    def test_cli_seed_and_spoiler(self):
        files = cli_lines(["--enemy-rando"])
        seed, spoiler = files["randomizer0.bfr"], files["spoiler0.txt"]
        lines = [l for l in seed if l.startswith("//EnemyRolls=")]
        self.assertEqual(len(lines), 1)
        self.assertIsNotNone(parse_meta(lines[0]))
        self.assertFalse(any("Enemies" in l for l in spoiler))

    def test_no_line_without_the_variation(self):
        seed = cli_lines([])["randomizer0.bfr"]
        self.assertFalse(any(l.startswith("//EnemyRolls=") for l in seed))


class TheDownloadRebuildsIt(unittest.TestCase):
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

    def test_the_stored_rolls_ride_every_download(self):
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
        rolls = enemyroll.roll("enemies", 1, None)
        p.enemy_rolls = {"1": rolls}
        self.assertIn(enemyroll.meta_line(rolls), p.get_seed(1).splitlines())
        # nothing stored (a plando): rolled from the name on the way out
        p.enemy_rolls = None
        self.assertIn(enemyroll.meta_line(rolls), p.get_seed(1).splitlines())


if __name__ == "__main__":
    unittest.main()
