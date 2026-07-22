"""Seed generation tests (python3).

Run from the repo root:  python3 -m unittest test.seedgentest -v
"""
import os
import re
import shutil
import sys
import tempfile
import unittest
from collections import Counter

from cli_gen import CLISeedParams

PICKUP_LINE = re.compile(r"^-?\d+\|\w+\|[^|]*\|[\w ]*")
# multiworld slot manifests live at pseudo-locations -2..-257
MANIFEST_LOC_RANGE = range(-257, -1)


class SeedGenTests(unittest.TestCase):
    def setUp(self):
        self.out = tempfile.mkdtemp(prefix="seedgentest_")

    def tearDown(self):
        shutil.rmtree(self.out, ignore_errors=True)

    def _generate(self, extra_args, seedfile="randomizer0.dat", spoilerfile="spoiler0.txt"):
        argv = ["cli_gen", "--output-dir", self.out, "--preset", "standard",
                "--open-world", "--force-trees", "--balanced", "--seed", "test"]
        argv += extra_args
        old_argv = sys.argv
        sys.argv = argv
        try:
            params = CLISeedParams()
            params.from_cli()
        finally:
            sys.argv = old_argv
        seed_path = os.path.join(self.out, seedfile)
        self.assertTrue(os.path.exists(seed_path),
                        "no seed produced for args %s" % extra_args)
        with open(seed_path) as f:
            lines = f.read().splitlines()
        self.assertTrue(os.path.exists(os.path.join(self.out, spoilerfile)))
        return lines

    def _check_structure(self, lines, expect_flag=None):
        # line 1 is the flagline|seedname; the rest are pickup placements
        self.assertGreater(len(lines), 150, "suspiciously short seed (%s lines)" % len(lines))
        self.assertLess(len(lines), 500, "suspiciously long seed (%s lines)" % len(lines))
        self.assertIn("|test", lines[0])
        if expect_flag:
            self.assertIn(expect_flag, lines[0])
        bad = [l for l in lines[1:] if not PICKUP_LINE.match(l)]
        self.assertEqual(bad, [], "malformed placement lines: %s" % bad[:5])

    def test_default_keymode(self):
        self._check_structure(self._generate([]))

    def test_shards(self):
        lines = self._generate(["--keymode", "Shards"])
        self._check_structure(lines, expect_flag="Shards")

    def test_clues(self):
        lines = self._generate(["--keymode", "Clues"])
        self._check_structure(lines, expect_flag="Clues")

    def test_limitkeys(self):
        lines = self._generate(["--keymode", "LimitKeys"])
        self._check_structure(lines, expect_flag="Limitkeys")  # sic: flagline casing

    def test_determinism(self):
        first = self._generate([])
        shutil.rmtree(self.out)
        self.out = tempfile.mkdtemp(prefix="seedgentest_")
        second = self._generate([])
        self.assertEqual(first, second, "same seed string produced different seeds")

    # Seed-output canary. If this fails, generation output changed for
    # existing seed strings: that can be fine (deliberate generator change),
    # but it means users re-generating an old seed get a DIFFERENT seed.
    # Bump the hash AND make sure the user-facing "seeds generated before
    # version X differ" warning gets updated. Do not "fix" this test blindly.
    # (Last bumped: 2026-07-22, the multiworld tagged-universe port.)
    SOLO_CANARY = "70b63fae1c1cf13dbb138910074825dab6bd26b2a8a70885c4eedbcf0704c73b"

    def test_solo_output_canary(self):
        import hashlib
        lines = self._generate([])
        digest = hashlib.sha256(("\n".join(lines) + "\n").encode("utf-8")).hexdigest()
        self.assertEqual(digest, self.SOLO_CANARY,
                         "solo seed output changed for an existing seed string -- see comment above")

    def test_separate_seeds_generation_removed(self):
        argv = ["cli_gen", "--output-dir", self.out, "--preset", "standard",
                "--open-world", "--balanced", "--seed", "test",
                "--players", "2", "--share-mode", "shared"]  # no --cloned: the old Seperate Seeds
        old_argv = sys.argv
        sys.argv = argv
        try:
            params = CLISeedParams()
            params.from_cli()
        finally:
            sys.argv = old_argv
        self.assertFalse(os.path.exists(os.path.join(self.out, "randomizer_1.dat")),
                         "Seperate Seeds generation should be removed")

    def test_cloned_seeds_are_identical(self):
        lines = self._generate(["--players", "2", "--share-mode", "shared", "--cloned"],
                               seedfile="randomizer_1.dat", spoilerfile="spoiler_1.txt")
        with open(os.path.join(self.out, "randomizer_2.dat")) as f:
            lines2 = f.read().splitlines()
        self.assertEqual(lines, lines2, "cloned seeds must be byte-identical")
        self.assertEqual([l for l in lines if "|MW|" in l], [], "no MW pickups outside multiworld mode")


def parse_seed(lines):
    """-> (placements, manifest): placements is {loc: (code, id, zone)} for real
    locations, manifest is {slot: (finder, code, id, zone)}."""
    placements, manifest = {}, {}
    for line in lines[1:]:
        if not line:
            continue
        loc, code, id, zone = line.split("|", 3)
        loc = int(loc)
        if loc in MANIFEST_LOC_RANGE:
            assert code == "MW", "non-manifest line at manifest loc: %s" % line
            finder, icode, iid = id.split(",", 2)
            manifest[-loc - 2] = (int(finder), icode, iid, zone)
        else:
            placements[loc] = (code, id, zone)
    return placements, manifest


class MultiworldGenTests(unittest.TestCase):
    """Structural invariants for multiworld generation. Generates once per
    class (generation is fast but not free) and checks everything against it."""

    PLAYERS = 3
    ARGS = ["cli_gen", "--preset", "standard", "--open-world", "--force-trees",
            "--balanced", "--seed", "mwtest",
            "--players", str(PLAYERS), "--share-mode", "multiworld"]

    @classmethod
    def setUpClass(cls):
        cls.out = tempfile.mkdtemp(prefix="seedgentest_mw_")
        cls.seeds = cls._generate_mw(cls.out)
        # a solo seed with the same flags, as the per-world baseline
        cls.solo_out = tempfile.mkdtemp(prefix="seedgentest_mwsolo_")
        old_argv = sys.argv
        sys.argv = ["cli_gen", "--output-dir", cls.solo_out, "--preset", "standard",
                    "--open-world", "--force-trees", "--balanced", "--seed", "mwtest"]
        try:
            CLISeedParams().from_cli()
        finally:
            sys.argv = old_argv
        with open(os.path.join(cls.solo_out, "randomizer0.dat")) as f:
            cls.solo_seed = f.read().splitlines()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.out, ignore_errors=True)
        shutil.rmtree(cls.solo_out, ignore_errors=True)

    @classmethod
    def _generate_mw(cls, outdir):
        old_argv = sys.argv
        sys.argv = cls.ARGS + ["--output-dir", outdir]
        try:
            CLISeedParams().from_cli()
        finally:
            sys.argv = old_argv
        seeds = {}
        for p in range(1, cls.PLAYERS + 1):
            path = os.path.join(outdir, "randomizer_%s.dat" % p)
            assert os.path.exists(path), "no seed for player %s" % p
            with open(path) as f:
                seeds[p] = f.read().splitlines()
        return seeds

    def test_line_shapes(self):
        for p, lines in self.seeds.items():
            self.assertIn("mode=Multiworld", lines[0])
            bad = [l for l in lines[1:] if l and not PICKUP_LINE.match(l)]
            self.assertEqual(bad, [], "malformed lines for player %s: %s" % (p, bad[:5]))

    def test_every_world_fully_populated(self):
        solo_locs = set(parse_seed(self.solo_seed)[0].keys())
        for p, lines in self.seeds.items():
            locs = set(parse_seed(lines)[0].keys())
            self.assertEqual(locs, solo_locs,
                             "player %s world has different locations than a solo seed" % p)

    def test_mw_crossrefs_resolve(self):
        """Every MW pickup points at a live slot in its owner's manifest, and
        every manifest entry is pointed at by exactly one MW pickup."""
        pointed = Counter()  # (owner, slot) -> times referenced
        for p, lines in self.seeds.items():
            placements, _ = parse_seed(lines)
            for loc, (code, id, zone) in placements.items():
                if code != "MW":
                    continue
                owner, slot, name = id.split(",", 2)
                owner, slot = int(owner), int(slot)
                self.assertNotEqual(owner, p, "player %s has an MW pickup for themselves" % p)
                self.assertIn(owner, self.seeds)
                self.assertLess(slot, 256)
                pointed[(owner, slot)] += 1

        manifest_entries = {}
        for p, lines in self.seeds.items():
            _, manifest = parse_seed(lines)
            for slot, (finder, icode, iid, zone) in manifest.items():
                manifest_entries[(p, slot)] = finder
                self.assertIn(finder, self.seeds)
                self.assertNotEqual(finder, p)

        self.assertEqual(set(pointed.keys()), set(manifest_entries.keys()),
                         "MW pickups and manifests must correspond 1:1")
        multi_pointed = {k: v for k, v in pointed.items() if v != 1}
        self.assertEqual(multi_pointed, {}, "slots referenced by multiple MW pickups")

    def test_item_conservation(self):
        """Each player receives exactly one solo pool's worth of (non-EX)
        items: their own world's non-MW placements plus their manifest."""
        def normalize(code, id):
            if code == "EX":
                return ("EX", "*")  # values vary; only count them
            return (code, id)

        solo_placements, _ = parse_seed(self.solo_seed)
        solo_pool = Counter(normalize(c, i) for (c, i, z) in solo_placements.values())

        for p, lines in self.seeds.items():
            placements, manifest = parse_seed(lines)
            received = Counter()
            for (code, id, zone) in placements.values():
                if code != "MW":
                    received[normalize(code, id)] += 1
            for (finder, icode, iid, zone) in manifest.values():
                received[normalize(icode, iid)] += 1
            non_ex_received = {k: v for k, v in received.items() if k[0] != "EX"}
            non_ex_solo = {k: v for k, v in solo_pool.items() if k[0] != "EX"}
            self.assertEqual(non_ex_received, non_ex_solo,
                             "player %s does not receive a full pool" % p)

    def test_determinism(self):
        out2 = tempfile.mkdtemp(prefix="seedgentest_mw2_")
        try:
            again = self._generate_mw(out2)
            self.assertEqual(self.seeds, again, "multiworld generation is not deterministic")
        finally:
            shutil.rmtree(out2, ignore_errors=True)

    # same deal as SeedGenTests.SOLO_CANARY: a change here means regenerated
    # multiworld seeds differ; bump deliberately, never blindly.
    # (bumped 2026-07-22: per-world warp candidate draws shifted the MW RNG
    # stream; MW was unreleased, no user warning owed. Solo canary unmoved.)
    MW_CANARY = "4fc083624e327d61b5f5f64694b68a8a9ae9cd7a56aeac2811959aec2c9e0057"

    def test_mw_output_canary(self):
        import hashlib
        h = hashlib.sha256()
        for p in range(1, self.PLAYERS + 1):
            h.update(("\n".join(self.seeds[p]) + "\n").encode("utf-8"))
        self.assertEqual(h.hexdigest(), self.MW_CANARY,
                         "multiworld seed output changed for an existing seed string -- see comment above")

    # (the variation rejection list is empty now -- only plando preplacement
    # remains unsupported, and that isn't reachable from the CLI)


def check_mw_invariants(tc, seeds):
    """Shared multiworld sanity: parseable lines, MW pickups and manifests
    correspond 1:1, nobody holds their own MW pickup."""
    pointed = Counter()
    for p, lines in seeds.items():
        bad = [l for l in lines[1:] if l and not PICKUP_LINE.match(l)]
        tc.assertEqual(bad, [], "malformed lines for player %s: %s" % (p, bad[:5]))
        placements, _ = parse_seed(lines)
        for loc, (code, id, zone) in placements.items():
            if code != "MW":
                continue
            owner, slot, name = id.split(",", 2)
            tc.assertNotEqual(int(owner), p)
            pointed[(int(owner), int(slot))] += 1
    manifest_keys = set()
    for p, lines in seeds.items():
        _, manifest = parse_seed(lines)
        for slot, (finder, icode, iid, zone) in manifest.items():
            manifest_keys.add((p, slot))
            tc.assertNotEqual(finder, p)
    tc.assertEqual(set(pointed.keys()), manifest_keys)
    tc.assertEqual({k: v for k, v in pointed.items() if v != 1}, {})


class MultiworldOptionsTests(unittest.TestCase):
    """The option combos enabled for multiworld (2026-07-22 decisions):
    world tour (independent zones, world-local relics), entrance shuffle
    (independent per world), and shared non-Glades spawns."""

    PLAYERS = 2

    def _gen(self, extra):
        outdir = tempfile.mkdtemp(prefix="seedgentest_mwopt_")
        self.addCleanup(shutil.rmtree, outdir, ignore_errors=True)
        old_argv = sys.argv
        sys.argv = ["cli_gen", "--output-dir", outdir, "--preset", "standard",
                    "--open-world", "--force-trees", "--balanced", "--seed", "mwtest",
                    "--players", str(self.PLAYERS), "--share-mode", "multiworld"] + extra
        try:
            CLISeedParams().from_cli()
        finally:
            sys.argv = old_argv
        seeds = {}
        for p in range(1, self.PLAYERS + 1):
            path = os.path.join(outdir, "randomizer_%s.dat" % p)
            self.assertTrue(os.path.exists(path), "no seed for player %s with %s" % (p, extra))
            with open(path) as f:
                seeds[p] = f.read().splitlines()
        return seeds

    def test_world_tour(self):
        seeds = self._gen(["--world-tour", "6"])
        check_mw_invariants(self, seeds)
        for p, lines in seeds.items():
            placements, manifest = parse_seed(lines)
            relics = [1 for (code, id, zone) in placements.values() if code == "WT"]
            self.assertEqual(len(relics), 6, "player %s should have 6 relics in their world" % p)
            # world-local: relics never cross as MW items
            crossed = [1 for (f, code, id, zone) in manifest.values() if code == "WT"]
            self.assertEqual(crossed, [], "relics must not cross worlds")

    def test_entrance_shuffle(self):
        seeds = self._gen(["--entrance"])
        check_mw_invariants(self, seeds)
        en_maps = {}
        for p, lines in seeds.items():
            # EN lines parse as loc|EN|x|y
            en_maps[p] = sorted(l for l in lines if l.split("|")[1:2] == ["EN"])
            # R1 pair + dungeon-outer/lobby pair + 10 dead-end pairs = 12 pairs
            self.assertEqual(len(en_maps[p]), 24, "12 door pairs = 24 EN lines")
        self.assertNotEqual(en_maps[1], en_maps[2],
                            "independent shuffles should differ (if this seed string "
                            "coincidentally matches, change the seed, don't delete the test)")

    def test_shared_nonglades_spawn(self):
        seeds = self._gen(["--start", "Grotto", "--starting-health", "3",
                           "--starting-energy", "1", "--starting-skills", "1"])
        check_mw_invariants(self, seeds)
        for p, lines in seeds.items():
            placements, _ = parse_seed(lines)
            self.assertIn(2, placements, "player %s has no spawn line" % p)
            code, id, zone = placements[2]
            self.assertIn("TP/Grotto", id, "named starts are shared by every world")

    def test_random_spawns_roll_per_world(self):
        seeds = self._gen(["--start", "Random"])
        check_mw_invariants(self, seeds)
        spawn_ids = {}
        for p, lines in seeds.items():
            placements, _ = parse_seed(lines)
            self.assertIn(2, placements, "player %s has no spawn line" % p)
            spawn_ids[p] = placements[2][1]
        # independent rolls: with this seed string the worlds land in
        # different spots (deterministic; if a future canary bump makes them
        # coincide, change the seed string here rather than weakening this)
        self.assertGreater(len(set(spawn_ids.values())), 1,
                           "random spawns should differ per world: %s" % spawn_ids)

    def _warps_received(self, seeds):
        """-> {player: number of TW (warp) pickups they receive}."""
        received = {p: 0 for p in seeds}
        for p, lines in seeds.items():
            placements, manifest = parse_seed(lines)
            for (code, id, zone) in placements.values():
                if code == "TW":
                    received[p] += 1
            for (finder, icode, iid, zone) in manifest.values():
                if icode == "TW":
                    received[p] += 1
        return received

    def test_warp_count(self):
        for extra in ([], ["--in-logic-warps"]):
            seeds = self._gen(["--warp-count", "4"] + extra)
            check_mw_invariants(self, seeds)
            for p, count in self._warps_received(seeds).items():
                self.assertEqual(count, 4, "player %s should receive exactly 4 warps (%s)" % (p, extra))

    def test_warps_instead_of_tps(self):
        seeds = self._gen(["--warps-instead-of-tps", "3"])
        check_mw_invariants(self, seeds)
        warps = self._warps_received(seeds)
        for p, lines in seeds.items():
            placements, manifest = parse_seed(lines)
            tps = sum(1 for (code, id, zone) in placements.values() if code == "TP")
            tps += sum(1 for (f, icode, iid, zone) in manifest.values() if icode == "TP")
            # a TP leaves the pool only when a warp in its area was available,
            # so warps+TPs is conserved at the standard pool's 8 TPs per world
            self.assertEqual(tps + warps[p], 8,
                             "player %s: TPs (%s) + warps (%s) != 8" % (p, tps, warps[p]))

    def test_bonus_pickups_pool(self):
        # Extra Bonus pool: BS|* resolves per world, WP|* becomes warps
        seeds = self._gen(["--bonus-pickups"])
        check_mw_invariants(self, seeds)
        warps = self._warps_received(seeds)
        counts = set(warps.values())
        self.assertEqual(len(counts), 1, "WP* count is drawn once, same for every world: %s" % warps)
        self.assertTrue(4 <= counts.pop() <= 8, "WP|* pool is [4,8]: %s" % warps)

    def test_limitkeys_cross_world(self):
        seeds = self._gen(["--keymode", "LimitKeys"])
        check_mw_invariants(self, seeds)
        limit_pool = {-3160308, -560160, 2919744, 719620, 7839588, 5320328, 8599904,
                      -4600020, -6959592, -11880100, 5480952, 4999752, -7320236,
                      -7200024, -5599400}
        dungeon_locked = {5480952, 5320328, -7320236}
        key_events = {"0": "GinsoKey", "2": "ForlornKey", "4": "HoruKey"}
        received = {p: Counter() for p in seeds}
        for p, lines in seeds.items():
            placements, manifest = parse_seed(lines)
            for loc, (code, id, zone) in placements.items():
                is_key = (code == "EV" and id in key_events) or \
                         (code == "MW" and any(n in id for n in ["Water Vein", "Gumon Seal", "Sunstone"]))
                if is_key:
                    self.assertIn(loc, limit_pool, "dungeon key off the limitkeys locs (player %s loc %s)" % (p, loc))
                    self.assertNotIn(loc, dungeon_locked, "dungeon key at a dungeon-locked loc: deadlock risk")
                if code == "EV" and id in key_events:
                    received[p][id] += 1
            for slot, (finder, icode, iid, zone) in manifest.items():
                if icode == "EV" and iid in key_events:
                    received[p][iid] += 1
        for p, counts in received.items():
            self.assertEqual(counts, Counter({"0": 1, "2": 1, "4": 1}),
                             "player %s must receive exactly one of each dungeon key: %s" % (p, counts))


if __name__ == "__main__":
    unittest.main()
