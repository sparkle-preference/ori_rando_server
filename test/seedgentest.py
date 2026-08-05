"""Seed generation tests (python3).

Run from the repo root:  python3 -m unittest test.seedgentest -v
"""
import os
import random
import re
import shutil
import sys
import tempfile
import unittest
from collections import Counter

from cli_gen import CLISeedParams, CLIMultiOptions

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
    # (Last bumped: 2026-07-28 for 4.2.3's impossible-path fixes (#83) —
    # verified by diffing generated seeds across the PR: same items, ~9
    # placements shuffled, exactly what a logic-path change produces.)
    SOLO_CANARY = "da8d5a061a509de4a2e960fc7b320365534cac662aa2bcf9b827f777928de7da"

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
    # (bumped 2026-07-23: CLI MW no longer defaults to shared=Skills+WorldEvents,
    # dropping the inert shared= flag from line 0. Placement bodies verified
    # bit-identical: re-inserting the old flag reproduces the prior hash.)
    # (bumped 2026-07-28: 4.2.3 impossible-path fixes (#83), placements
    # legitimately shuffled -- see SOLO_CANARY note.)
    # (bumped 2026-08-02: exp_pool is now per-world (134701: it was being
    # split across all worlds' slots) -- EX values change, placements don't.)
    MW_CANARY = "6381bb2ada5bfde82ad967a64423ffc7c101538bda8aa42094ef30a3c1e18782"

    def test_exp_pool_is_per_world(self):
        # 134701 report: the global exp budget was being spread across every
        # world's slots, quartering everyone's exp income at 4 players.
        # exp_pool (default 10000) is a PER-WORLD budget. A world's exp lives
        # in two forms: EX placements in its own seed, plus its manifest
        # entries other worlds find for it (-slot|MW|finder,EX,value).
        for p, lines in self.seeds.items():
            placements, manifest = parse_seed(lines)
            total = sum(int(id) for (code, id, zone) in placements.values() if code == "EX")
            total += sum(int(iid) for (finder, icode, iid, zone) in manifest.values() if icode == "EX")
            self.assertGreater(total, 6000, "world %s exp pool deflated: %s" % (p, total))
            self.assertLess(total, 16000, "world %s exp pool inflated: %s" % (p, total))

    def test_mw_output_canary(self):
        import hashlib
        h = hashlib.sha256()
        for p in range(1, self.PLAYERS + 1):
            h.update(("\n".join(self.seeds[p]) + "\n").encode("utf-8"))
        self.assertEqual(h.hexdigest(), self.MW_CANARY,
                         "multiworld seed output changed for an existing seed string -- see comment above")

    # (the variation rejection list is empty now -- only plando preplacement
    # remains unsupported, and that isn't reachable from the CLI)


class MultiworldBiasTests(MultiworldGenTests):
    """All multiworld invariants again, at full anti_bk_bias."""

    ARGS = MultiworldGenTests.ARGS + ["--anti-bk-bias", "1.0"]

    def test_mw_output_canary(self):
        # no canary here; instead prove the knob moves placements, not just flags
        out2 = tempfile.mkdtemp(prefix="seedgentest_mwbias0_")
        try:
            unbiased = MultiworldGenTests._generate_mw(out2)
        finally:
            shutil.rmtree(out2, ignore_errors=True)
        self.assertIn("anti_bk_bias=1", self.seeds[1][0])
        moved = any(parse_seed(self.seeds[p])[0] != parse_seed(unbiased[p])[0]
                    for p in range(1, self.PLAYERS + 1))
        self.assertTrue(moved, "anti_bk_bias=1.0 produced identical placements to 0.0")


class MultiworldSharedGenTests(unittest.TestCase):
    """mw shared singletons: shared-category items are generated once across
    all worlds (the netcode grants finds to everyone); per-world items and
    each world's finale trigger (EV5) are untouched."""

    PLAYERS = 3
    ARGS = MultiworldGenTests.ARGS + ["--shared-items", "skills,teleporters,worldevents,upgrades"]

    @classmethod
    def setUpClass(cls):
        cls.out = tempfile.mkdtemp(prefix="seedgentest_mwshared_")
        old_argv = sys.argv
        sys.argv = cls.ARGS + ["--output-dir", cls.out]
        try:
            CLISeedParams().from_cli()
        finally:
            sys.argv = old_argv
        cls.seeds = {}
        for p in range(1, cls.PLAYERS + 1):
            path = os.path.join(cls.out, "randomizer_%s.dat" % p)
            assert os.path.exists(path), "no seed for player %s" % p
            with open(path) as f:
                cls.seeds[p] = f.read().splitlines()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.out, ignore_errors=True)

    def _all_placements(self):
        world, manifests = [], []
        for p, lines in self.seeds.items():
            placements, manifest = parse_seed(lines)
            for loc, (code, id, zone) in placements.items():
                world.append((p, loc, code, id))
            for slot, (finder, icode, iid, zone) in manifest.items():
                manifests.append((p, slot, icode, iid))
        return world, manifests

    def test_flags_carry_mode_and_shares(self):
        self.assertIn("mode=Multiworld", self.seeds[1][0])
        self.assertIn("shared=", self.seeds[1][0])

    def test_shared_categories_are_singletons(self):
        world, manifests = self._all_placements()
        counts = Counter((code, id) for (p, loc, code, id) in world
                         if code in ("SK", "TP", "EV"))
        for (p, slot, icode, iid) in manifests:
            if icode in ("SK", "TP", "EV"):
                counts[(icode, iid)] += 1
        for (code, id), cnt in sorted(counts.items()):
            expected = self.PLAYERS if (code, id) == ("EV", "5") else 1
            self.assertEqual(cnt, expected,
                             "%s|%s appears %s times (expected %s)" % (code, id, cnt, expected))

    def test_shared_items_never_ride_manifests(self):
        _, manifests = self._all_placements()
        for (p, slot, icode, iid) in manifests:
            self.assertNotIn(icode, ("SK", "TP"),
                             "shared %s|%s in player %s manifest" % (icode, iid, p))
            if icode == "EV":
                self.assertEqual(iid, "5", "shared event in player %s manifest" % p)
            if icode == "RB":
                # only the NOT_SHARED name_only upgrades stay per-world
                self.assertIn(iid, ("0", "1"),
                              "shared RB|%s in player %s manifest" % (iid, p))

    def test_shared_upgrade_totals_match_one_pool(self):
        world, manifests = self._all_placements()
        rb = Counter(id for (p, loc, code, id) in world if code == "RB")
        for (p, slot, icode, iid) in manifests:
            if icode == "RB":
                rb[iid] += 1
        # CLI default pool: shareable upgrades collapse to one copy total
        self.assertEqual(rb.get("6", 0), 3)   # Attack Upgrade: UPGRADE type
        self.assertEqual(rb.get("9", 0), 1)   # Spirit Light Efficiency
        # name_only upgrades are NOT_SHARED at runtime -- generator parity
        self.assertEqual(rb.get("0", 0), 3 * self.PLAYERS)  # Mega Health

    def test_per_world_items_stay_per_world(self):
        world, manifests = self._all_placements()
        ks = sum(1 for (p, loc, code, id) in world if code == "KS")
        ks += sum(1 for (p, slot, icode, iid) in manifests if icode == "KS")
        # 40 per world minus 2 for OpenWorld, times three worlds
        self.assertEqual(ks, self.PLAYERS * 38)


class MultiworldPreplacementTests(unittest.TestCase):
    """MW fass: own-world placements are plain lines, cross-world ones become
    MW pickups with a manifest entry in the owner's seed, and the owner's pool
    copy is consumed either way."""

    PLAYERS = 3
    # P1's Bash at their own 919772; P3's GinsoKey hidden in P2's -280256
    ARGS = MultiworldGenTests.ARGS + ["--fass", "919772:SK0|2.-280256:EV0@3"]

    @classmethod
    def setUpClass(cls):
        cls.out = tempfile.mkdtemp(prefix="seedgentest_mwfass_")
        old_argv = sys.argv
        sys.argv = cls.ARGS + ["--output-dir", cls.out]
        try:
            CLISeedParams().from_cli()
        finally:
            sys.argv = old_argv
        cls.seeds = {}
        for p in range(1, cls.PLAYERS + 1):
            path = os.path.join(cls.out, "randomizer_%s.dat" % p)
            assert os.path.exists(path), "no seed for player %s" % p
            with open(path) as f:
                cls.seeds[p] = f.read().splitlines()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.out, ignore_errors=True)

    def test_own_world_preplacement_is_a_plain_line(self):
        placements, _ = parse_seed(self.seeds[1])
        code, id, zone = placements[919772]
        self.assertEqual((code, id), ("SK", "0"))

    def test_cross_world_preplacement_rides_the_manifest(self):
        placements, _ = parse_seed(self.seeds[2])
        code, id, zone = placements[-280256]
        self.assertEqual(code, "MW")
        owner, slot, name = id.split(",", 2)
        self.assertEqual(int(owner), 3)
        _, manifest = parse_seed(self.seeds[3])
        finder, icode, iid, mzone = manifest[int(slot)]
        self.assertEqual((finder, icode, iid), (2, "EV", "0"))

    def test_pool_copies_are_consumed(self):
        # each preplaced item replaces its owner's pool copy: exactly one
        # Bash for P1 and one GinsoKey for P3 exist anywhere
        def count_for(owner, icode, iid):
            n = 0
            for p, lines in self.seeds.items():
                placements, manifest = parse_seed(lines)
                if p == owner:
                    n += sum(1 for (c, i, z) in placements.values() if (c, i) == (icode, iid))
                    n += sum(1 for (f, c, i, z) in manifest.values() if (c, i) == (icode, iid))
            return n
        self.assertEqual(count_for(1, "SK", "0"), 1)
        self.assertEqual(count_for(3, "EV", "0"), 1)


class BuriedPlacementTests(unittest.TestCase):
    """Buried pseudo-locations: a fass at loc 20000000+N keeps its items out
    of the pool until N locations are reachable. Classic fill here (balanced
    swaps relocate items after assignment, which is a documented caveat)."""

    BURIED = 20000000

    def _gen_with_records(self, extra, seedfiles=("randomizer0.dat",)):
        """Generate and also record (tagged item, reachable-loc-count) at
        every assignment. -> (records, {seedfile: lines})"""
        from seedbuilder.generator import SeedGenerator
        outdir = tempfile.mkdtemp(prefix="seedgentest_buried_")
        self.addCleanup(shutil.rmtree, outdir, ignore_errors=True)
        records = []
        orig = SeedGenerator.assign_to_location
        def spy(sg, item, location):
            records.append((item, sg.total_locs() - sg.locations()))
            return orig(sg, item, location)
        old_argv = sys.argv
        sys.argv = ["cli_gen", "--output-dir", outdir, "--preset", "standard",
                    "--open-world", "--force-trees", "--seed", "buriedtest3"] + extra
        SeedGenerator.assign_to_location = spy
        try:
            CLISeedParams().from_cli()
        finally:
            SeedGenerator.assign_to_location = orig
            sys.argv = old_argv
        seeds = {}
        for sf in seedfiles:
            path = os.path.join(outdir, sf)
            self.assertTrue(os.path.exists(path), "no seed produced (%s)" % sf)
            with open(path) as f:
                seeds[sf] = f.read().splitlines()
        return records, seeds

    def _depths(self, records, tagged):
        depths = [d for (i, d) in records if i == tagged]
        self.assertTrue(depths, "%s was never assigned" % tagged)
        return depths

    def test_buried_item_stays_buried(self):
        records, seeds = self._gen_with_records(["--fass", "%s:SK51" % (self.BURIED + 150)])
        self.assertGreaterEqual(min(self._depths(records, "Grenade|1")), 150)
        placements, _ = parse_seed(seeds["randomizer0.dat"])
        grenades = [1 for (c, i, z) in placements.values() if (c, i) == ("SK", "51")]
        self.assertEqual(len(grenades), 1, "buried Grenade should still be placed exactly once")

    def test_control_seed_places_grenade_early(self):
        # same seed string, no burial: proves the assertion above can fail
        records, _ = self._gen_with_records([])
        self.assertLess(min(self._depths(records, "Grenade|1")), 150)

    def test_multipickup_buries_each_part(self):
        records, _ = self._gen_with_records(["--fass", "%s:MUSK/3/SK/12" % (self.BURIED + 100)])
        self.assertGreaterEqual(min(self._depths(records, "WallJump|1")), 100)
        self.assertGreaterEqual(min(self._depths(records, "Climb|1")), 100)

    def test_multiworld_buried_with_owner(self):
        # balanced like the MW canon args; the invariant is assignment-time
        records, seeds = self._gen_with_records(
            ["--balanced", "--players", "2", "--share-mode", "multiworld",
             "--fass", "%s:SK51@2" % (self.BURIED + 100)],
            seedfiles=("randomizer_1.dat", "randomizer_2.dat"))
        self.assertGreaterEqual(min(self._depths(records, "Grenade|2")), 100)
        check_mw_invariants(self, {1: seeds["randomizer_1.dat"], 2: seeds["randomizer_2.dat"]})
        # P2's pool copy was consumed: exactly one Grenade for P2 anywhere
        n = 0
        for p, sf in ((1, "randomizer_1.dat"), (2, "randomizer_2.dat")):
            placements, manifest = parse_seed(seeds[sf])
            if p == 2:
                n += sum(1 for (c, i, z) in placements.values() if (c, i) == ("SK", "51"))
            n += sum(1 for (f, c, i, z) in manifest.values() if p == 2 and (c, i) == ("SK", "51"))
        self.assertEqual(n, 1)


class AntiBkBoostTests(unittest.TestCase):
    """Shape of the multiworld starvation weight multiplier."""

    def _sg(self, bias, counts):
        from seedbuilder.generator import SeedGenerator
        sg = SeedGenerator()
        sg.seed_count = len(counts)
        sg.is_multi = True
        sg.params = CLISeedParams()
        sg.params.anti_bk_bias = bias
        for p, c in counts.items():
            sg.locs_by_player[p] = c
        return sg

    def test_boost_shape(self):
        sg = self._sg(1.0, {1: 20, 2: 40, 3: 100})
        self.assertEqual(sg.anti_bk_boost(1), 1.0)  # most starved keeps full weight
        self.assertLess(sg.anti_bk_boost(2), 0.05)
        self.assertLess(sg.anti_bk_boost(3), sg.anti_bk_boost(2))

    def test_boost_off_is_exactly_one(self):
        sg = self._sg(0.0, {1: 20, 2: 400})
        self.assertEqual(sg.anti_bk_boost(2), 1.0)
        solo = self._sg(1.0, {1: 20})
        solo.is_multi = False
        self.assertEqual(solo.anti_bk_boost(1), 1.0)


class AntiBkLocalizeTests(unittest.TestCase):
    """Placement-side balance: an opening world's progression prefers home
    slots in the round's item/location pairing (anti_bk_localize)."""

    def _sg(self, bias, counts, pin=False, shared=()):
        from seedbuilder.generator import SeedGenerator
        sg = SeedGenerator()
        sg.seed_count = len(counts)
        sg.is_multi = True
        sg.params = CLISeedParams()
        sg.params.anti_bk_bias = bias
        sg.ap_ks_pin = pin
        sg.shared_pool_bases = set(shared)
        sg.random = random.Random(7)
        for p, c in counts.items():
            sg.locs_by_player[p] = c
        return sg

    def _loc(self, p):
        from seedbuilder.generator import Location
        return Location(0, 0, "Test", "Test", 1, "Glades", p)

    def test_opening_progression_localizes(self):
        sg = self._sg(1.0, {1: 5, 2: 30})
        items = ["Bash|1", "EX*|2"]
        locs = [self._loc(2), self._loc(1)]
        sg.anti_bk_localize(items, locs)
        self.assertEqual(items, ["EX*|2", "Bash|1"])

    def test_localize_cascades(self):
        # both worlds opening; everyone ends up home
        sg = self._sg(1.0, {1: 5, 2: 5})
        items = ["Bash|1", "EX*|1", "Glide|2"]
        locs = [self._loc(2), self._loc(1), self._loc(1)]
        sg.anti_bk_localize(items, locs)
        self.assertEqual(items, ["Glide|2", "Bash|1", "EX*|1"])

    def test_threshold_ends_localization(self):
        sg = self._sg(1.0, {1: 15, 2: 30})  # world 1 hit ANTI_BK_LOCAL_CHECKS
        items = ["Bash|1", "EX*|2"]
        locs = [self._loc(2), self._loc(1)]
        sg.anti_bk_localize(items, locs)
        self.assertEqual(items, ["Bash|1", "EX*|2"])

    def test_bias_zero_is_inert(self):
        sg = self._sg(0.0, {1: 5, 2: 30})
        items = ["Bash|1", "EX*|2"]
        locs = [self._loc(2), self._loc(1)]
        state = sg.random.getstate()
        sg.anti_bk_localize(items, locs)
        self.assertEqual(items, ["Bash|1", "EX*|2"])
        self.assertEqual(sg.random.getstate(), state, "bias=0 must not draw pRNG")

    def test_ap_pinned_keystones_stay(self):
        sg = self._sg(1.0, {1: 5, 2: 30}, pin=True)
        items = ["Bash|1", "KS|1"]
        locs = [self._loc(2), self._loc(1)]
        sg.anti_bk_localize(items, locs)
        self.assertEqual(items, ["Bash|1", "KS|1"])
        # without the pin a keystone is junk and gets displaced
        sg = self._sg(1.0, {1: 5, 2: 30})
        sg.anti_bk_localize(items, locs)
        self.assertEqual(items, ["KS|1", "Bash|1"])

    def test_shared_progression_is_neutral(self):
        sg = self._sg(1.0, {1: 5, 2: 30}, shared=("Bash",))
        items = ["Bash|1", "EX*|2"]
        locs = [self._loc(2), self._loc(1)]
        sg.anti_bk_localize(items, locs)
        self.assertEqual(items, ["Bash|1", "EX*|2"])

    def test_home_progression_is_not_robbed(self):
        sg = self._sg(1.0, {1: 5, 2: 30})
        items = ["Glide|1", "Bash|1"]
        locs = [self._loc(2), self._loc(1)]
        sg.anti_bk_localize(items, locs)
        self.assertEqual(items, ["Glide|1", "Bash|1"])

    def test_balance_pop_prefers_home(self):
        sg = self._sg(1.0, {1: 5, 2: 30})
        sg.balanceLevel = 3
        home = self._loc(1)
        sg.balanceList = [("EX*|2", self._loc(2), "a", None),
                          ("EX*|2", home, "a", None),
                          ("EX*|2", self._loc(2), "a", None)]
        got = sg.get_location_from_balance_list(prefer_player=1)
        self.assertIs(got, home)
        self.assertEqual(len(sg.balanceList), 2)
        self.assertEqual(sg.balanceListLeftovers, ["EX*|2"])


class MultiworldLocalizeGenTests(unittest.TestCase):
    """Full-bias generation without open world: closed openings are exactly
    where localization matters. Invariants must hold, and progression assigned
    while its owner is still opening must land in the owner's world."""

    PLAYERS = 3
    BASE = ["cli_gen", "--preset", "standard", "--force-trees", "--balanced",
            "--seed", "mwlocaltest", "--players", str(PLAYERS), "--share-mode", "multiworld"]

    @classmethod
    def _gen(cls, bias):
        """-> (records, seeds): records = (owner, host world) for every
        progression item assigned while its owner was under the opening
        threshold. reset() clears them so retries don't leave stale rows."""
        from seedbuilder.generator import SeedGenerator, untag
        outdir = tempfile.mkdtemp(prefix="seedgentest_mwlocal_")
        records = []
        orig_assign = SeedGenerator.assign_to_location
        orig_reset = SeedGenerator.reset
        def assign_spy(sg, item, location):
            if item and sg.is_progression(item):
                owner = untag(item)[1]
                if sg.locs_by_player[owner] < sg.ANTI_BK_LOCAL_CHECKS:
                    records.append((owner, location.player))
            return orig_assign(sg, item, location)
        def reset_spy(sg, worried=False):
            records.clear()
            return orig_reset(sg, worried)
        old_argv = sys.argv
        sys.argv = cls.BASE + ["--output-dir", outdir, "--anti-bk-bias", str(bias)]
        SeedGenerator.assign_to_location = assign_spy
        SeedGenerator.reset = reset_spy
        try:
            CLISeedParams().from_cli()
        finally:
            SeedGenerator.assign_to_location = orig_assign
            SeedGenerator.reset = orig_reset
            sys.argv = old_argv
        seeds = {}
        try:
            for p in range(1, cls.PLAYERS + 1):
                with open(os.path.join(outdir, "randomizer_%s.dat" % p)) as f:
                    seeds[p] = f.read().splitlines()
        finally:
            shutil.rmtree(outdir, ignore_errors=True)
        return list(records), seeds

    @classmethod
    def setUpClass(cls):
        cls.brecords, cls.biased = cls._gen(1.0)
        cls.urecords, cls.unbiased = cls._gen(0.0)

    def test_invariants_hold_at_full_bias(self):
        check_mw_invariants(self, self.biased)

    def test_opening_progression_stays_home(self):
        self.assertGreater(len(self.brecords), 0, "no opening-phase progression was placed at all")
        stray_b = [(o, h) for (o, h) in self.brecords if o != h]
        stray_u = [(o, h) for (o, h) in self.urecords if o != h]
        self.assertEqual(stray_b, [],
                         "bias 1.0 let opening progression leave home (of %s placements)" % len(self.brecords))
        # control: without the knob this seed scatters opening progression,
        # so the assertion above is not vacuous
        self.assertGreater(len(stray_u), 0, "control run kept everything home; metric proves nothing")


class SeedModeProblemTests(unittest.TestCase):
    """Web-facing creation gate: removed modes get clear messages; Multiworld
    creation is behind the MULTIWORLD env flag and requires tracking."""

    def _params(self, mode, enabled=True, cloned=True, tracking=True):
        import util
        from enums import MultiplayerGameType
        p = CLISeedParams()
        p.sync = CLIMultiOptions(mode=MultiplayerGameType.mk(mode), enabled=enabled, cloned=cloned)
        p.tracking = tracking
        return p

    def _check(self, flag_value, params, ap_override=False):
        import util
        from seedbuilder import seedparams
        orig = util.MULTIWORLD
        util.MULTIWORLD = flag_value
        try:
            return seedparams.seed_mode_problem(params, ap_override=ap_override)
        finally:
            util.MULTIWORLD = orig

    def _ap_params(self, players=2, enabled=True, mode="Multiworld"):
        p = self._params(mode, enabled=enabled)
        p.players = players
        p.ap_mode = True
        p.ap_export = ["skills"]
        p.sync.shared = []
        return p

    def test_multiworld_gated_by_flag(self):
        self.assertIsNotNone(self._check(False, self._params("Multiworld")))
        self.assertIsNone(self._check(True, self._params("Multiworld")))

    def test_ap_bingo_blocked_even_with_overrides(self):
        """/reroll passes both overrides (the user already has such a game);
        a combination that can't work must still refuse."""
        import util
        from enums import Variation
        from seedbuilder import seedparams
        p = self._ap_params(players=1)
        p.variations = [Variation.BINGO]
        orig = util.ARCHIPELAGO
        util.ARCHIPELAGO = True
        try:
            problem = seedparams.seed_mode_problem(p, mw_override=True, ap_override=True)
            self.assertIn("Bingo", problem)
        finally:
            util.ARCHIPELAGO = orig

    def test_ap_needs_netcode(self):
        """Without sync the bridge has no way to grant: the client would find
        AP slots and drop them silently, so refuse to build one."""
        import util
        orig = util.ARCHIPELAGO
        util.ARCHIPELAGO = True
        try:
            solo = self._ap_params(players=1, enabled=False)
            self.assertIn("tracking", self._check(True, solo, ap_override=True))
            tracked = self._ap_params(players=1)
            tracked.tracking = False
            self.assertIn("tracking", self._check(True, tracked, ap_override=True))
            # K=1 with netcode on is a legitimate AP seed
            self.assertIsNone(self._check(True, self._ap_params(players=1), ap_override=True))
        finally:
            util.ARCHIPELAGO = orig

    def test_ap_mode_gated_by_flag(self):
        import util
        p = self._ap_params()
        orig = util.ARCHIPELAGO
        try:
            util.ARCHIPELAGO = False
            self.assertIn("Archipelago", self._check(True, p))
            util.ARCHIPELAGO = True
            self.assertIsNone(self._check(True, p, ap_override=True))
        finally:
            util.ARCHIPELAGO = orig

    def test_ap_mode_also_gated_by_ap_test_optin(self):
        """Alpha soft gate: ARCHIPELAGO is on in prod, so creation additionally
        wants ?ap_test=1 (mw_override's shape, one layer up)."""
        import util
        orig = util.ARCHIPELAGO
        util.ARCHIPELAGO = True
        try:
            self.assertIn("closed testing", self._check(True, self._ap_params()))
            self.assertIsNone(self._check(True, self._ap_params(), ap_override=True))
            # a K=1 AP world (sync disabled) is still an AP seed, not a free pass
            self.assertIn("closed testing",
                          self._check(True, self._ap_params(players=1, enabled=False, mode="None")))
            # non-AP seeds never see the gate
            self.assertIsNone(self._check(True, self._params("Multiworld")))
            self.assertIsNone(self._check(False, self._params("Shared", cloned=True)))
        finally:
            util.ARCHIPELAGO = orig

    def test_ap_and_bingo_cant_be_combined(self):
        """A bingo board hands its seeds out by board pid, which is unrelated
        to the AP world that pid would have to be."""
        import util
        from enums import Variation
        orig = util.ARCHIPELAGO
        util.ARCHIPELAGO = True
        try:
            for players in (1, 2):
                p = self._ap_params(players=players)
                p.variations = [Variation.OPEN_WORLD, Variation.BINGO]
                self.assertIn("Bingo", self._check(True, p, ap_override=True))
            # neither half is affected on its own
            self.assertIsNone(self._check(True, self._ap_params(), ap_override=True))
            for mode in ("None", "Multiworld"):
                bingo = self._params(mode)
                bingo.variations = [Variation.BINGO]
                self.assertIsNone(self._check(True, bingo))
        finally:
            util.ARCHIPELAGO = orig

    def test_ap_override_bypasses_neither_flag_nor_validation(self):
        import util
        orig = util.ARCHIPELAGO
        try:
            util.ARCHIPELAGO = False
            self.assertIn("aren't available yet", self._check(True, self._ap_params(), ap_override=True))
            util.ARCHIPELAGO = True
            # the export/share clash check still applies
            from enums import ShareType
            p = self._ap_params()
            p.sync.shared = [ShareType.SKILL]
            self.assertIn("overlap", self._check(True, p, ap_override=True))
            # and so does the multiworld tracking requirement
            p = self._ap_params()
            p.tracking = False
            self.assertIn("tracking", self._check(True, p, ap_override=True))
        finally:
            util.ARCHIPELAGO = orig

    def test_mw_override_bypasses_flag(self):
        import util
        from seedbuilder import seedparams
        orig = util.MULTIWORLD
        util.MULTIWORLD = False
        try:
            self.assertIsNone(seedparams.seed_mode_problem(self._params("Multiworld"), mw_override=True))
            # the override doesn't bypass the tracking requirement
            self.assertIsNotNone(seedparams.seed_mode_problem(self._params("Multiworld", tracking=False), mw_override=True))
        finally:
            util.MULTIWORLD = orig

    def test_multiworld_requires_tracking(self):
        self.assertIn("tracking", self._check(True, self._params("Multiworld", tracking=False)))

    def test_multiworld_preplacement_validates_player_refs(self):
        from seedbuilder.seedparams import Placement, Stuff
        p = self._params("Multiworld")
        p.players = 3
        p.placements = [Placement(location="919772", zone="", stuff=[Stuff(code="SK", id="0", player="2", owner="3")])]
        self.assertIsNone(self._check(True, p))  # in range: allowed now
        p.placements = [Placement(location="919772", zone="", stuff=[Stuff(code="SK", id="0", player="2", owner="7")])]
        self.assertIn("player 7", self._check(True, p))
        p.placements = []
        self.assertIsNone(self._check(True, p))

    def test_removed_modes_get_messages(self):
        self.assertIn("SplitShards", self._check(True, self._params("SplitShards")))
        self.assertIn("Seperate Seeds", self._check(True, self._params("Shared", cloned=False)))

    def test_supported_modes_pass(self):
        self.assertIsNone(self._check(False, self._params("Shared", cloned=True)))
        self.assertIsNone(self._check(False, self._params("None")))
        self.assertIsNone(self._check(False, self._params("Shared", enabled=False)))


class ApTestGateWiringTests(unittest.TestCase):
    """The opt-in rides the QUERY string of the build POST (the page posts to
    /generator/build?ap_test=1), so it has to survive a form-encoded request.
    Params building and the gate itself are stubbed: this is wiring only."""

    @classmethod
    def setUpClass(cls):
        import contextlib
        import main
        import models

        class _FakeNdbClient(object):
            def context(self):
                return contextlib.nullcontext()
        cls.main, cls.models = main, models
        cls._orig_client = models.client
        models.client = _FakeNdbClient()
        cls._orig_secret = main.app.secret_key
        main.app.secret_key = main.app.secret_key or "ap-test-gate"
        cls.client = main.app.test_client()

    @classmethod
    def tearDownClass(cls):
        cls.models.client = cls._orig_client
        cls.main.app.secret_key = cls._orig_secret

    def setUp(self):
        main = self.main
        self.seen = []
        self._orig_params, self._orig_problem = main.SeedGenParams, main.seed_mode_problem

        class _FakeKey(object):
            def id(self):
                return "ap-params"

            def get(self):
                return object()

        class _FakeParams(object):
            @staticmethod
            def from_json(json_in):
                return _FakeKey()
        main.SeedGenParams = _FakeParams

        def spy(params, mw_override=False, ap_override=False):
            self.seen.append(ap_override)
            return "gated"
        main.seed_mode_problem = spy

    def tearDown(self):
        self.main.SeedGenParams = self._orig_params
        self.main.seed_mode_problem = self._orig_problem

    def _build(self, query=""):
        return self.client.post("/generator/build" + query, data={"params": "{}"})

    def test_plain_build_post_does_not_opt_in(self):
        resp = self._build()
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(self.seen, [False])

    def test_ap_test_query_param_reaches_the_gate(self):
        self._build("?ap_test=1")
        self.assertEqual(self.seen, [True])

    def test_ap_test_survives_an_existing_query_string(self):
        # the page appends &ap_test=1 after ?bingo=1
        self._build("?bingo=1&ap_test=1")
        self.assertEqual(self.seen, [True])


class ApSoloPayloadTests(unittest.TestCase):
    """The K=1 payload the page posts for one Ori world in someone else's
    room. Shipped once with apMode dropped for players=1 (game 134910), so
    pin what from_json must make of it."""

    def _params(self, **extra):
        from seedbuilder.seedparams import MultiplayerOptions
        json_in = {"players": 1, "tracking": True, "apMode": True,
                   "apExport": ["skills", "teleporters", "events"]}
        json_in.update(extra)
        return MultiplayerOptions.from_json(json_in)

    def test_solo_ap_turns_on_multiworld_netcode(self):
        from enums import MultiplayerGameType
        sync = self._params()
        self.assertTrue(sync.enabled, "the bridge grants over netcode")
        self.assertEqual(sync.mode, MultiplayerGameType.MULTIWORLD,
                         "the client only reads slot bitfields in SyncMode 5")

    def test_solo_without_ap_is_untouched(self):
        sync = self._params(apMode=False)
        self.assertFalse(sync.enabled)


class ApworldDownloadTests(unittest.TestCase):
    """The site serves the packaged apworld: a tester's session host needs
    the file and has no repo to build it from."""

    @classmethod
    def setUpClass(cls):
        import contextlib
        import main
        import models
        from archipelago import build_apworld

        class _FakeNdbClient(object):
            def context(self):
                return contextlib.nullcontext()
        cls.main, cls.models, cls.build_apworld = main, models, build_apworld
        cls._orig_client = models.client
        models.client = _FakeNdbClient()
        cls._orig_secret = main.app.secret_key
        main.app.secret_key = main.app.secret_key or "ap-apworld"
        cls.client = main.app.test_client()

    @classmethod
    def tearDownClass(cls):
        cls.models.client = cls._orig_client
        cls.main.app.secret_key = cls._orig_secret

    def setUp(self):
        self._orig = (self.main.ARCHIPELAGO, self.main.apworld_zip)
        self.main.ARCHIPELAGO = True

    def tearDown(self):
        self.main.ARCHIPELAGO, self.main.apworld_zip = self._orig

    def test_serves_a_zip_named_exactly_oride_apworld(self):
        # AP takes the module name from the file stem, so the name is load-bearing
        import io
        import zipfile
        resp = self.client.get("/generator/apworld")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers["Content-Disposition"],
                         "attachment; filename=oride.apworld")
        self.assertEqual(resp.headers["Content-Type"], "application/zip")
        names = zipfile.ZipFile(io.BytesIO(resp.data)).namelist()
        self.assertIn("oride/__init__.py", names)
        self.assertIn("oride/archipelago.json", names)

    def test_body_is_the_packaged_build(self):
        self.assertEqual(self.client.get("/generator/apworld").data,
                         self.build_apworld.zip_bytes())

    def test_bytes_are_cached_after_the_first_request(self):
        self.main.apworld_zip = None
        self.client.get("/generator/apworld")
        self.assertTrue(self.main.apworld_zip)
        self.main.apworld_zip = b"cached"
        self.assertEqual(self.client.get("/generator/apworld").data, b"cached")

    def test_404_with_the_flag_off(self):
        self.main.ARCHIPELAGO = False
        self.assertEqual(self.client.get("/generator/apworld").status_code, 404)

    def test_a_package_that_fails_its_checks_never_ships(self):
        orig = self.build_apworld.check
        self.build_apworld.check = lambda files: ["missing __init__.py"]
        try:
            self.assertRaises(self.build_apworld.BuildError, self.build_apworld.zip_bytes)
        finally:
            self.build_apworld.check = orig

    def test_versions_read_from_the_packaged_sources(self):
        from archipelago.yaml_emit import DATA_VERSION
        vals = self.main.ap_versions()
        self.assertEqual(vals["ap_world_version"],
                         self.build_apworld.manifest()["world_version"])
        self.assertEqual(vals["ap_data_version"], DATA_VERSION)


class BingoBoltOnGateTests(unittest.TestCase):
    """/bingo/from_game clears the game's roster to seat bingo players, which
    on an AP game deletes the shadow players the bridge grants through. The
    board itself is stubbed out; what's under test is which games get one."""

    @classmethod
    def setUpClass(cls):
        import google.auth.credentials
        from google.cloud import ndb
        import main
        import models
        cls.main, cls.models = main, models
        cls._orig_client = models.client
        models.client = ndb.Client(project="unit-test",
                                   credentials=google.auth.credentials.AnonymousCredentials())
        cls._orig_secret = main.app.secret_key
        main.app.secret_key = main.app.secret_key or "ap-bingo-gate"
        cls.client = main.app.test_client()

    @classmethod
    def tearDownClass(cls):
        cls.models.client = cls._orig_client
        cls.main.app.secret_key = cls._orig_secret

    def setUp(self):
        main, test = self.main, self
        from enums import MultiplayerGameType

        class _Sync(object):
            mode = MultiplayerGameType.MULTIWORLD

        class _Params(object):
            ap_mode = False
            seed = "boltongate"
            variations = []
            players = 2
            sync = _Sync()

            def flag_line(self):
                return "boltongate"

        class _ParamsKey(object):
            def get(self):
                return test.params

        class _Player(object):
            def __init__(self, pid):
                self.key = type("K", (), {"id": lambda s, p=pid: p})()

        class _Game(object):
            key = object()
            mode = MultiplayerGameType.MULTIWORLD
            params = _ParamsKey()
            bingo_data = None

            def get_players(self):
                return [_Player(1), _Player(2)]

            def remove_player(self, pid):
                test.removed.append(pid)

            def put(self):
                pass

        class _Bingo(object):
            def __init__(self, **kw):
                self.square_count, self.bingo_count, self.event_log = 0, 3, []
                self.__dict__.update(kw)

            def get_json(self, first):
                return {}

            def put(self):
                return "bingo-key"

        self.params, self.removed, self.cards = _Params(), [], 0
        self._orig = (main.Game, main.User, main.BingoGameData, main.BingoGenerator.get_cards)
        main.Game = type("G", (), {"with_id": staticmethod(lambda gid: _Game())})
        main.User = type("U", (), {"get": staticmethod(lambda: None)})
        main.BingoGameData = _Bingo

        def cards(*a, **k):
            test.cards += 1
            return []
        main.BingoGenerator.get_cards = staticmethod(cards)

    def tearDown(self):
        (self.main.Game, self.main.User, self.main.BingoGameData,
         self.main.BingoGenerator.get_cards) = self._orig

    def test_ap_game_is_refused_before_the_roster_is_touched(self):
        self.params.ap_mode = True
        resp = self.client.get("/bingo/from_game/7")
        self.assertEqual(resp.status_code, 412)
        self.assertIn("Archipelago", resp.data.decode())
        self.assertEqual(self.removed, [], "the gate let the roster wipe run")
        self.assertEqual(self.cards, 0)

    def test_non_ap_game_still_gets_its_board(self):
        resp = self.client.get("/bingo/from_game/7")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.removed, [1, 2])
        self.assertEqual(self.cards, 1)


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


def parse_ap_seed(lines, players):
    """Classify a converted AP-mode seed's lines by wire shape:
    -> (plain, native_mw, reserved, native_manifest, ap_manifest) where
    plain is {loc: (code, id, zone)}, native_mw/reserved are
    {loc: (owner, slot, name, zone)} split on owner <=/> players, and the
    manifests are {slot: (finder, code, id, zone)} split on finder."""
    plain, native_mw, reserved = {}, {}, {}
    native_manifest, ap_manifest = {}, {}
    for line in lines[1:]:
        if not line:
            continue
        loc, code, id, zone = line.split("|", 3)
        loc = int(loc)
        if loc in MANIFEST_LOC_RANGE:
            finder, icode, iid = id.split(",", 2)
            entry = (int(finder), icode, iid, zone)
            target = ap_manifest if int(finder) > players else native_manifest
            target[-loc - 2] = entry
        elif code == "MW":
            owner, slot, name = id.split(",", 2)
            entry = (int(owner), int(slot), name, zone)
            target = reserved if int(owner) > players else native_mw
            target[loc] = entry
        else:
            plain[loc] = (code, id, zone)
    return plain, native_mw, reserved, native_manifest, ap_manifest


def generate_ap(outdir, players, ap_export, seed="apgen2"):
    """cli_gen an AP-mode casual seed; -> ({player: seed lines}, {player: yaml text})."""
    old_argv = sys.argv
    sys.argv = ["cli_gen", "--output-dir", outdir, "--preset", "casual",
                "--balanced", "--seed", seed, "--players", str(players),
                "--share-mode", "multiworld", "--ap-export", ap_export]
    try:
        CLISeedParams().from_cli()
    finally:
        sys.argv = old_argv
    seeds, yamls = {}, {}
    for p in range(1, players + 1):
        datfile = "randomizer_%s.dat" % p if players > 1 else "randomizer0.dat"
        path = os.path.join(outdir, datfile)
        assert os.path.exists(path), "no seed for player %s" % p
        with open(path) as f:
            seeds[p] = f.read().splitlines()
        ypath = os.path.join(outdir, "ap_world_%s.yaml" % p)
        assert os.path.exists(ypath), "no AP yaml for player %s" % p
        with open(ypath) as f:
            yamls[p] = f.read()
    return seeds, yamls


class ApModeGenTests(unittest.TestCase):
    """The Archipelago conversion pass (archipelago/convert.py): a normal
    multiworld seed converted so exported-category items become AP slots.
    v3 invariants: ALL cross-landed progression converts (native manifests
    carry only filler), cross-landed EX converts as balancing currency, and
    generic keystones never leave their owner's world. Non-AP output staying
    byte-identical is proven by the SOLO/MW canaries above, which this
    feature must never move."""

    PLAYERS = 2
    EXPORT = "skills,teleporters,events"
    # the apworld's logic universe: nothing from it may ride native manifests
    PROGRESSION_CODES = {"SK", "TP", "EV", "HC", "EC", "AC", "KS", "MS"}
    PROGRESSION_RB_IDS = {"17", "19", "21", "28"} | {str(n) for n in range(300, 312)}

    @classmethod
    def setUpClass(cls):
        cls.out = tempfile.mkdtemp(prefix="seedgentest_ap_")
        cls.seeds, cls.yamls = generate_ap(cls.out, cls.PLAYERS, cls.EXPORT)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.out, ignore_errors=True)

    def test_line_shapes(self):
        for p, lines in self.seeds.items():
            self.assertIn("mode=Multiworld", lines[0])
            bad = [l for l in lines[1:] if l and not PICKUP_LINE.match(l)]
            self.assertEqual(bad, [], "malformed lines for player %s: %s" % (p, bad[:5]))

    def test_reserved_lines_wellformed(self):
        """Converted locations hold MW placeholders owned by the world's own
        shadow (K+p), slots dense 0..n-1, v1 display names."""
        for p, lines in self.seeds.items():
            _, _, reserved, _, _ = parse_ap_seed(lines, self.PLAYERS)
            self.assertGreater(len(reserved), 0)
            slots = []
            for loc, (owner, slot, name, zone) in reserved.items():
                self.assertEqual(owner, self.PLAYERS + p,
                                 "reserved line at %s owned by %s, not this world's shadow" % (loc, owner))
                self.assertEqual(name, "AP Item #%s" % (slot + 1))
                slots.append(slot)
            self.assertEqual(sorted(slots), list(range(len(slots))),
                             "player %s reserved slots not dense" % p)

    def test_exported_balances_reserved_across_the_game(self):
        """AP's real invariant is one item per location room-wide. Per world
        the two differ by cross-world drift; the game-wide totals cannot."""
        total_exported = total_reserved = 0
        for p, lines in self.seeds.items():
            _, _, reserved, _, ap_manifest = parse_ap_seed(lines, self.PLAYERS)
            total_exported += len(ap_manifest)
            total_reserved += len(reserved)
            for slot, (finder, icode, iid, zone) in ap_manifest.items():
                self.assertEqual(finder, self.PLAYERS + p,
                                 "AP manifest entry with finder %s in world %s" % (finder, p))
        self.assertEqual(total_exported, total_reserved)

    def test_ap_manifest_slots_share_space(self):
        """AP manifest entries share the 0..255 slot space with surviving
        native MW slots: no collisions, everything in range, and exports
        fill the free slots from the bottom (deterministic)."""
        for p, lines in self.seeds.items():
            _, _, _, native_manifest, ap_manifest = parse_ap_seed(lines, self.PLAYERS)
            ap_slots = sorted(ap_manifest)
            self.assertTrue(ap_slots, "player %s exports nothing" % p)
            self.assertLess(ap_slots[-1], 256)
            native_slots = set(native_manifest)
            self.assertEqual(native_slots & set(ap_slots), set(),
                             "player %s AP slots collide with native slots" % p)
            free = [s for s in range(256) if s not in native_slots]
            self.assertEqual(ap_slots, free[:len(ap_slots)],
                             "player %s AP slots not lowest-free-first" % p)

    def test_native_crossrefs_still_resolve(self):
        """The native MW fabric under the conversion is still 1:1."""
        pointed = Counter()
        native_keys = set()
        for p, lines in self.seeds.items():
            _, native_mw, _, native_manifest, _ = parse_ap_seed(lines, self.PLAYERS)
            for loc, (owner, slot, name, zone) in native_mw.items():
                self.assertNotEqual(owner, p)
                pointed[(owner, slot)] += 1
            for slot, (finder, icode, iid, zone) in native_manifest.items():
                native_keys.add((p, slot))
                self.assertNotEqual(finder, p)
        self.assertEqual(set(pointed.keys()), native_keys,
                         "native MW pickups and manifests must correspond 1:1")
        self.assertEqual({k: v for k, v in pointed.items() if v != 1}, {})

    def test_exported_codes(self):
        """Exports = selected categories + cross-landed progression + EX
        balancing currency; never generic keystones."""
        for p, lines in self.seeds.items():
            _, _, _, _, ap_manifest = parse_ap_seed(lines, self.PLAYERS)
            codes = set(icode for (finder, icode, iid, zone) in ap_manifest.values())
            self.assertTrue(codes <= {"SK", "TP", "EV", "HC", "EC", "AC", "MS", "RB", "EX"},
                            "player %s exported unexpected codes %s" % (p, codes))
            self.assertNotIn("KS", codes, "player %s exported generic keystones" % p)

    def test_selected_categories_fully_converted(self):
        """Every placed SK/TP/EV became an AP slot: none remain as plain
        lines (same-world convert as selected; cross-landed as progression)."""
        for p, lines in self.seeds.items():
            plain, _, _, _, _ = parse_ap_seed(lines, self.PLAYERS)
            left = {loc: v for loc, v in plain.items()
                    if loc != 2 and v[0] in ("SK", "TP", "EV")}
            self.assertEqual(left, {}, "player %s kept selected-category items" % p)

    def test_native_manifests_carry_only_filler(self):
        """v3: every cross-landed progression item was exported, so native
        manifests hold nothing the apworld's logic can see."""
        for p, lines in self.seeds.items():
            _, _, _, native_manifest, _ = parse_ap_seed(lines, self.PLAYERS)
            bad = [(slot, icode, iid) for slot, (f, icode, iid, z) in native_manifest.items()
                   if icode in self.PROGRESSION_CODES
                   or (icode == "RB" and iid in self.PROGRESSION_RB_IDS)]
            self.assertEqual(bad, [],
                             "player %s native manifest carries progression: %s" % (p, bad))

    def test_nothing_crosses_worlds_natively(self):
        """v4: a standard pool shares one way. Every cross-landed item the
        datapackage can name converts, and it can name all of them, so no
        plain-MW line survives in either direction."""
        for p, lines in self.seeds.items():
            _, native_mw, _, native_manifest, _ = parse_ap_seed(lines, self.PLAYERS)
            self.assertEqual(native_mw, {},
                             "player %s still hosts native cross-world items" % p)
            self.assertEqual(native_manifest, {},
                             "player %s still exports natively" % p)

    def test_exported_ex_keeps_its_exact_amount(self):
        """No denomination bucket: the manifest value and the AP item name
        are the same number, so the amount granted is the amount announced."""
        from archipelago.export_data import EX_EXACT_CAP
        from archipelago.yaml_emit import ITEM_NAMES
        seen = 0
        for p, lines in self.seeds.items():
            _, _, _, _, ap_manifest = parse_ap_seed(lines, self.PLAYERS)
            for slot, (finder, icode, iid, zone) in ap_manifest.items():
                if icode != "EX":
                    continue
                seen += 1
                self.assertTrue(1 <= int(iid) <= EX_EXACT_CAP,
                                "EX %s is outside the exact range" % iid)
                self.assertEqual(ITEM_NAMES[("EX", iid)], "%s experience" % iid)
        self.assertGreater(seen, 0, "no EX exported, so this proves nothing")

    def test_keystones_never_cross_worlds(self):
        """The AP-mode generator constraint: all 40 keystones are plain lines
        in their owner's world; none ride the MW fabric in either direction."""
        for p, lines in self.seeds.items():
            plain, _, _, native_manifest, ap_manifest = parse_ap_seed(lines, self.PLAYERS)
            ks = sum(1 for (code, id, zone) in plain.values() if code == "KS")
            self.assertEqual(ks, 40, "player %s has %s local keystones, not 40" % (p, ks))
            for manifest in (native_manifest, ap_manifest):
                self.assertEqual([e for e in manifest.values() if e[1] == "KS"], [],
                                 "player %s manifest carries a keystone" % p)

    def test_yaml_config_sound(self):
        """The emitted yaml balances, pins local progression, and models the
        FULL keystone pool as local pins (per-world door thresholds need all
        40; under-modeling was the v2 K=2 accessibility failure)."""
        from archipelago.convert import build_ap_config, ap_variations
        from archipelago.yaml_emit import parse_seed as yaml_parse
        from enums import presets
        items = locs = 0
        for p, lines in self.seeds.items():
            _, placements = yaml_parse(lines)
            config = build_ap_config(
                placements, players=self.PLAYERS, world=p,
                logic_paths=[lp.value for lp in presets["Casual"]],
                key_mode="Default", spawn_zone="Glades",
                variations=ap_variations([]))
            items += sum(config["exported_items"].values())
            locs += len(config["reserved_locations"])
            self.assertNotIn("Keystone", config["exported_items"])
            ks_pins = sum(1 for item in config["local_progression"].values()
                          if item == "Keystone")
            self.assertEqual(ks_pins, 40,
                             "player %s yaml pins %s keystones, not the full pool" % (p, ks_pins))
            self.assertIn("name: Ori%s" % p, self.yamls[p])
            self.assertIn("game: Ori DE Rando", self.yamls[p])
        self.assertEqual(items, locs, "the game's yamls don't balance room-wide")

    def test_determinism(self):
        out2 = tempfile.mkdtemp(prefix="seedgentest_ap2_")
        try:
            seeds2, yamls2 = generate_ap(out2, self.PLAYERS, self.EXPORT)
            self.assertEqual(self.seeds, seeds2, "AP seeds not deterministic")
            self.assertEqual(self.yamls, yamls2, "AP yamls not deterministic")
        finally:
            shutil.rmtree(out2, ignore_errors=True)


class ApModeSoloTests(unittest.TestCase):
    """K=1 AP mode: no cross-world landings, so no balancing reverts --
    every exportable item converts, counts match by construction."""

    def _gen(self, ap_export):
        outdir = tempfile.mkdtemp(prefix="seedgentest_apsolo_")
        self.addCleanup(shutil.rmtree, outdir, ignore_errors=True)
        seeds, yamls = generate_ap(outdir, 1, ap_export)
        return seeds[1], yamls[1]

    def test_solo_conversion_is_total(self):
        lines, _ = self._gen("skills,teleporters,events")
        plain, native_mw, reserved, native_manifest, ap_manifest = parse_ap_seed(lines, 1)
        self.assertEqual(native_mw, {}, "solo seeds have no native MW pickups")
        self.assertEqual(native_manifest, {})
        # zero reverts: nothing of an exported category is left in place
        left_behind = {loc: v for loc, v in plain.items()
                       if loc != 2 and v[0] in ("SK", "TP", "EV")}
        self.assertEqual(left_behind, {})
        self.assertEqual(len(ap_manifest), len(reserved))
        self.assertEqual(sorted(ap_manifest), list(range(len(ap_manifest))),
                         "solo AP manifest slots start dense at 0")
        for loc, (owner, slot, name, zone) in reserved.items():
            self.assertEqual(owner, 2)  # K + 1

    def test_stones_export_never_includes_generic_keystones(self):
        lines, _ = self._gen("stones,cells")
        plain, _, reserved, _, ap_manifest = parse_ap_seed(lines, 1)
        exported_codes = Counter(icode for (f, icode, iid, z) in ap_manifest.values())
        self.assertNotIn("KS", exported_codes, "generic Keystone exported")
        self.assertGreater(exported_codes["MS"], 0, "stones should export mapstones")
        self.assertGreater(exported_codes["HC"] + exported_codes["EC"] + exported_codes["AC"], 0)
        # keystones all stayed put
        ks = sum(1 for (code, id, zone) in plain.values() if code == "KS")
        self.assertEqual(ks, 40, "casual closed-world seeds place 40 keystones")
        self.assertEqual(len(ap_manifest), len(reserved))


class ApExportSlotCapTests(unittest.TestCase):
    """A player carries 8x32 slot bits and nothing more (models.Player.
    mark_slot refuses 256+), so a world can neither host nor export more than
    256 Archipelago items. Past the cap the seed would render fine and the
    surplus grants would silently evaporate, so conversion has to fail first.
    Driven with synthetic seed text: real seeds can't reach the cap (only 256
    pickup locations exist per world), which is exactly why it needs a test."""

    FLAGS = "Sync0.0,test|mode=Multiworld"

    def _world(self, lines):
        return self.FLAGS + "\n" + "".join(line + "\n" for line in lines)

    def _exports(self, n, start=1000000):
        """n same-world skill placements: each becomes a reserved AP slot in
        this world and an exported item owned by this world."""
        return ["%s|SK|0|Glades" % (start + i) for i in range(n)]

    def _natives(self, n):
        """n native (non-AP) manifest entries, which keep holding their slots
        through conversion because filler may ride the native MW fabric."""
        return ["%s|MW|1,RB,6|Glades" % (-(slot + 2)) for slot in range(n)]

    def _convert(self, texts, categories=("skills",)):
        from archipelago.convert import ap_convert
        return ap_convert(list(texts), list(categories))

    def test_at_the_cap_still_converts(self):
        """256 is legal -- slots 0..255 -- and the last one really is 255."""
        from archipelago.convert import MAX_SLOTS
        self.assertEqual(MAX_SLOTS, 256)
        texts, info = self._convert([self._world(self._exports(MAX_SLOTS))])
        self.assertEqual(len(info["reserved"][1]), MAX_SLOTS)
        self.assertEqual(info["ap_slots"][1][-1], MAX_SLOTS - 1)
        manifest = [l for l in texts[0].split("\n") if l.startswith("-")]
        self.assertEqual(len(manifest), MAX_SLOTS)
        self.assertTrue(manifest[-1].startswith("-257|MW|"), manifest[-1])

    def test_over_the_cap_fails_with_world_and_count(self):
        from archipelago.convert import ApConversionError
        with self.assertRaises(ApConversionError) as caught:
            self._convert([self._world(self._exports(257))])
        message = str(caught.exception)
        self.assertIn("world 1", message)
        self.assertIn("257", message)
        self.assertIn("256", message)

    def test_the_cap_names_the_offending_world(self):
        """K=2, world 2 over the cap: the error must not blame world 1."""
        from archipelago.convert import ApConversionError
        with self.assertRaises(ApConversionError) as caught:
            self._convert([self._world([]), self._world(self._exports(300))])
        self.assertIn("world 2", str(caught.exception))

    def test_natives_holding_slots_count_against_the_cap(self):
        """The reachable half of the guard: surviving native manifest entries
        keep their slots, so the exports that fit is 256 minus those."""
        from archipelago.convert import ApConversionError
        # 200 natives + 56 exports exactly fills the space
        _, info = self._convert([self._world([]),
                                 self._world(self._exports(56) + self._natives(200))])
        self.assertEqual(len(info["exported"][2]), 56)
        self.assertEqual(sorted(info["ap_slots"][2]), list(range(200, 256)))
        with self.assertRaises(ApConversionError) as caught:
            self._convert([self._world([]),
                           self._world(self._exports(57) + self._natives(200))])
        message = str(caught.exception)
        self.assertIn("world 2", message)
        self.assertIn("57", message)   # what it wanted
        self.assertIn("56", message)   # what was free

    def test_no_slot_past_the_cap_is_ever_emitted(self):
        """Belt and braces: whatever converts, every slot number on the wire
        is one models.Player.mark_slot will accept."""
        from archipelago.convert import MAX_SLOTS
        texts, info = self._convert([self._world([]),
                                     self._world(self._exports(56) + self._natives(200))])
        for world_slots in info["ap_slots"].values():
            for slot in world_slots:
                self.assertTrue(0 <= slot < MAX_SLOTS, slot)
        for text in texts:
            for line in text.split("\n"):
                if line.startswith("-"):
                    loc = int(line.split("|", 1)[0])
                    self.assertTrue(-257 <= loc <= -2, line)


class ApFullConversionTests(unittest.TestCase):
    """v4 conversion rules driven with synthetic seed text: everything the
    datapackage can name leaves the native MW fabric, everything it cannot
    stays on it, and the game-wide totals balance while per-world ones do
    not. Real seeds never contain a TW warp or an above-cap EX, which is
    exactly why these need a fixture."""

    FLAGS = "Sync0.0,test|mode=Multiworld"

    def _convert(self, worlds, categories=("skills",)):
        from archipelago.convert import ap_convert
        texts = [self.FLAGS + "\n" + "".join(l + "\n" for l in lines) for lines in worlds]
        return ap_convert(texts, list(categories))

    def _cross(self, loc, owner, slot, zone="Glades"):
        return "%s|MW|%s,%s,item|%s" % (loc, owner, slot, zone)

    def _mani(self, slot, finder, code, id, zone="Glades"):
        return "%s|MW|%s,%s,%s|%s" % (-(slot + 2), finder, code, id, zone)

    def test_cross_landed_filler_converts(self):
        """A bonus RB in someone else's world used to ride a native manifest
        forever; now it is an AP item like everything else."""
        _, info = self._convert([
            [self._cross(1000000, 2, 0, "Grove")],       # world 1 hosts world 2's RB
            [self._mani(0, 1, "RB", "6", "Swamp")],
        ])
        self.assertEqual(len(info["reserved"][1]), 1)
        self.assertEqual(info["exported"][2], [("RB", "6", 0)])
        self.assertEqual(info["exported"][1], [])

    def test_unnameable_cross_items_stay_native(self):
        """TW warp ids are per-seed strings, so they can never be static
        datapackage items -- they keep the native MW fabric to themselves."""
        texts, info = self._convert([
            [self._cross(1000000, 2, 0, "Grove")],
            [self._mani(0, 1, "TW", "Warp to Stompless AC,-358,65,Cell", "Swamp")],
        ])
        self.assertEqual(info["exported"][2], [])
        self.assertEqual(info["reserved"][1], [])
        self.assertIn("|MW|1,TW,Warp to Stompless AC,-358,65,Cell|", texts[1])
        self.assertIn(self._cross(1000000, 2, 0, "Grove"), texts[0])

    def test_cross_landed_progression_the_datapackage_cannot_name_fails(self):
        """The one case that must not silently degrade: a logic item left
        native under-models the world."""
        from archipelago.convert import ApConversionError
        with self.assertRaises(ApConversionError) as caught:
            self._convert([
                [self._cross(1000000, 2, 0, "Grove")],
                [self._mani(0, 1, "SK", "999", "Swamp")],
            ])
        self.assertIn("not in the datapackage", str(caught.exception))

    def test_per_world_counts_may_differ_while_the_game_balances(self):
        """Two of world 2's items land in world 1 and none the other way:
        world 1 over-reserves by exactly what world 2 over-exports."""
        _, info = self._convert([
            [self._cross(1000000, 2, 0, "Grove"), self._cross(1000001, 2, 1, "Grove")],
            [self._mani(0, 1, "RB", "6", "Swamp"), self._mani(1, 1, "RB", "13", "Swamp")],
        ])
        counts = {p: (len(info["exported"][p]), len(info["reserved"][p])) for p in (1, 2)}
        self.assertEqual(counts, {1: (0, 2), 2: (2, 0)})
        self.assertEqual(sum(e for e, r in counts.values()),
                         sum(r for e, r in counts.values()))

    def test_ex_above_the_cap_rewrites_the_manifest_too(self):
        """Display and delivery have to agree: past the cap the AP item name
        rounds, so the amount the client grants rounds with it."""
        from archipelago.export_data import EX_EXACT_CAP
        texts, info = self._convert([
            [self._cross(1000000, 2, 0, "Grove"), self._cross(1000001, 2, 1, "Grove")],
            [self._mani(0, 1, "EX", str(EX_EXACT_CAP), "Swamp"),
             self._mani(1, 1, "EX", str(EX_EXACT_CAP + 1), "Swamp")],
        ])
        self.assertEqual(info["exported"][2],
                         [("EX", str(EX_EXACT_CAP), 0), ("EX", "200", 1)])
        self.assertIn("|MW|4,EX,%s|" % EX_EXACT_CAP, texts[1])
        self.assertIn("|MW|4,EX,200|", texts[1])


class ApDataVersionTests(unittest.TestCase):
    """The yaml carries the version of the data contract it was emitted
    against, and the apworld refuses what it can't read. The two constants
    are hand-maintained on opposite sides of a zip boundary, so the first
    test here is the thing that stops a one-sided bump from shipping."""

    @staticmethod
    def _apworld_version():
        """Load the apworld's version module without Archipelago on the
        path: oride/__init__.py imports BaseClasses, version.py imports
        nothing at all (deliberately)."""
        import importlib.util
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "archipelago", "oride_apworld", "oride", "version.py")
        spec = importlib.util.spec_from_file_location("oride_version_undertest", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_emitter_and_apworld_agree(self):
        """Today's yamls must generate against today's apworld."""
        from archipelago.yaml_emit import DATA_VERSION
        version = self._apworld_version()
        self.assertLessEqual(version.COMPATIBLE_DATA_VERSION, version.DATA_VERSION)
        self.assertLessEqual(version.COMPATIBLE_DATA_VERSION, DATA_VERSION,
                             "the apworld rejects the yamls we emit as too old")
        self.assertLessEqual(DATA_VERSION, version.DATA_VERSION,
                             "the apworld rejects the yamls we emit as too new")

    def test_config_and_yaml_carry_the_version(self):
        from archipelago.yaml_emit import DATA_VERSION, emit_yaml, make_config
        config = make_config({}, [], {}, [], params_id=7, world=2)
        self.assertEqual(config["data_version"], DATA_VERSION)
        self.assertIn("data_version: %s" % DATA_VERSION, emit_yaml(config, "Ori2"))

    def test_current_blob_is_accepted(self):
        from archipelago.yaml_emit import make_config
        version = self._apworld_version()
        self.assertIsNone(version.data_version_problem(make_config({}, [], {}, [])))

    def test_pre_versioning_yamls_still_generate(self):
        """Yamls emitted before data_version existed have no such key."""
        version = self._apworld_version()
        self.assertIsNone(version.data_version_problem({"world": 1}))

    def test_a_newer_seed_says_to_update_the_apworld(self):
        version = self._apworld_version()
        problem = version.data_version_problem(
            {"data_version": version.DATA_VERSION + 1})
        self.assertIsNotNone(problem)
        self.assertIn("oride.apworld", problem)
        self.assertIn(str(version.DATA_VERSION + 1), problem)
        self.assertIn(str(version.DATA_VERSION), problem)

    def test_an_older_seed_says_to_redownload_the_yaml(self):
        version = self._apworld_version()
        problem = version.data_version_problem(
            {"data_version": version.COMPATIBLE_DATA_VERSION - 1})
        self.assertIsNotNone(problem)
        self.assertIn("yaml", problem)

    def test_a_garbage_version_is_a_message_not_a_traceback(self):
        version = self._apworld_version()
        for bad in ("tomorrow", None, [1]):
            problem = version.data_version_problem({"data_version": bad})
            self.assertIsNotNone(problem, bad)
            self.assertIn("yaml", problem)

    def test_the_world_checks_the_version_before_reading_any_table(self):
        """Pinned by source, since importing the world needs Archipelago:
        generate_early must consult the version before the item/location
        lookups whose KeyErrors it exists to prevent."""
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "archipelago", "oride_apworld", "oride", "__init__.py")
        with open(path) as f:
            source = f.read()
        body = source.split("def generate_early", 1)[1].split("\n    def ", 1)[0]
        self.assertLess(body.index("data_version_problem"), body.index("ITEM_TABLE"),
                        "the data version check has to run before the tables are read")


class ApSeedAnnotationTests(unittest.TestCase):
    """get_seed rewrites this world's AP lines from what the room actually
    did with them (archipelago/annotate.py). Fields 0-3 keep their exact
    meaning for every shipped client; field 5 is the new half. Scout rows
    come from APNames, stubbed here."""

    K = 2       # two worlds, so world 1's shadow is pid 3 and world 2's is 4
    WORLD = 1
    GID = 4242
    BASH_AP_ID = 524288

    @classmethod
    def setUpClass(cls):
        import google.auth.credentials
        from google.cloud import ndb
        creds = google.auth.credentials.AnonymousCredentials()
        cls.ndb_client = ndb.Client(project="unit-test", credentials=creds)

    def setUp(self):
        from ap_models import APNames
        self._ctx = self.ndb_client.context()
        self._ctx.__enter__()
        self.stored = {}
        self._orig_load = APNames.load
        APNames.load = staticmethod(
            lambda gid, world: self.stored.get((int(gid), int(world)), ({}, None)))

    def tearDown(self):
        from ap_models import APNames
        APNames.load = staticmethod(self._orig_load)
        self._ctx.__exit__(None, None, None)

    @staticmethod
    def _scout(item, who, to, ap_item=0, ap_owner=9):
        from ap_models import APScout
        return APScout(item, who, to, ap_item, ap_owner)

    def _store(self, world, entries, ap_slot=1):
        self.stored[(self.GID, world)] = (entries, ap_slot)

    def _params(self):
        from enums import MultiplayerGameType
        from seedbuilder.seedparams import SeedGenParams, MultiplayerOptions, Placement, Stuff
        sync = MultiplayerOptions(str_mode=MultiplayerGameType.MULTIWORLD.value)
        def place(loc, code, id, zone):
            return Placement(location=loc, zone=zone,
                             stuff=[Stuff(code=code, id=id, player="1")])
        return SeedGenParams(
            seed="apnames", players=self.K, tracking=False, ap_mode=True,
            ap_export=["skills"], sync=sync, placements=[
                place("2", "SK", "0", "Glades"),                      # plain line
                place("919908", "MW", "3,0,AP Item #1", "Grove"),     # reserved slot 0
                place("959960", "MW", "3,1,AP Item #2", "Sorrow"),    # reserved slot 1
                place("1799708", "MW", "2,55,Valley teleporter", "Valley"),  # plain cross-world
                place("-2", "MW", "3,SK,0", "Glades"),                # our AP manifest slot
                place("-3", "MW", "2,HC,1", "Glades"),                # native manifest
            ])

    def _lines(self, params, game_id=GID):
        return {l.split("|")[0]: l for l in
                params.get_seed(self.WORLD, game_id=game_id).splitlines()[1:]}

    def test_scouted_slots_get_real_names(self):
        self._store(self.WORLD, {0: self._scout("Progressive Sword", "TestQuest", "TestQuest")})
        lines = self._lines(self._params())
        self.assertEqual(lines["919908"],
                         "919908|MW|3,0,Progressive Sword (TestQuest)|Grove|TestQuest;Progressive Sword")
        # slot 1 was never scouted: placeholder intact, no field 5
        self.assertEqual(lines["959960"], "959960|MW|3,1,AP Item #2|Sorrow")

    def test_the_first_four_fields_are_exactly_what_they_were(self):
        """An old dll splits on '|' and reads 0..3, so the whole annotation
        has to be invisible to it apart from the name it already showed."""
        self._store(self.WORLD, {0: self._scout("Bash", "Ori2", "P2")})
        lines = self._lines(self._params())
        parts = lines["919908"].split("|")
        self.assertEqual(parts[:4], ["919908", "MW", "3,0,Bash (Ori2)", "Grove"])
        self.assertEqual(len(parts), 5)

    def test_field_five_carries_the_recipient_and_the_bare_item(self):
        self._store(self.WORLD, {0: self._scout("Bow, Arrows", "Zelda", "Zelda")})
        recipient, item = self._lines(self._params())["919908"].split("|")[4].split(";", 1)
        self.assertEqual((recipient, item), ("Zelda", "Bow, Arrows"))

    def test_annotated_line_still_parses_as_the_client_and_server_do(self):
        from pickups import Pickup
        self._store(self.WORLD, {1: self._scout("Bow, Arrows", "Zelda", "Zelda")})
        parts = self._lines(self._params())["959960"].split("|")
        pickup = Pickup.n(parts[1], parts[2])
        self.assertEqual((pickup.owner, pickup.slot), (3, 1))
        self.assertEqual(pickup.name, "Player 3's Bow, Arrows (Zelda)")
        self.assertEqual(parts[3], "Sorrow")

    def test_nothing_outside_the_ap_lines_moves(self):
        before = self._lines(self._params())
        self._store(self.WORLD, {0: self._scout("Bash", "Ori2", "P2")})
        after = self._lines(self._params())
        self.assertEqual(sorted(before), sorted(after))
        for loc in ("2", "1799708", "-3"):
            self.assertEqual(before[loc], after[loc], "line %s changed" % loc)

    def test_an_item_nobody_can_locate_keeps_its_original_line(self):
        """The rolled zone is where the item was taken FROM, so after AP's
        fill it is usually wrong -- but blanking it strips the hint entirely
        on every shipped client, so an unresolved entry is left alone."""
        self._store(self.WORLD, {0: self._scout("Bash", "Ori2", "P2")})
        self.assertEqual(self._lines(self._params())["-2"], "-2|MW|3,SK,0|Glades")

    def test_a_sibling_world_gives_the_true_zone_and_the_holder(self):
        """The cross-world join: our Bash turns up in one of the K worlds'
        reserved locations, so both where and who are known exactly."""
        self._store(self.WORLD, {
            0: self._scout("Bash", "Ori1", "P1", ap_item=self.BASH_AP_ID, ap_owner=1),
            1: self._scout("Something Else", "Ori2", "P2", ap_item=1, ap_owner=2)})
        self.assertEqual(self._lines(self._params())["-2"], "-2|MW|3,SK,0|Grove|P1")

    def test_two_copies_of_one_item_are_left_unresolved(self):
        """Two identical exports are indistinguishable in the room's answers,
        so the join declines rather than picking one."""
        params = self._params()
        from seedbuilder.seedparams import Placement, Stuff
        params.placements.append(Placement(location="-4", zone="Glades",
                                           stuff=[Stuff(code="MW", id="3,SK,0", player="1")]))
        self._store(self.WORLD, {
            0: self._scout("Bash", "Ori1", "P1", ap_item=self.BASH_AP_ID, ap_owner=1)})
        lines = self._lines(params)
        self.assertEqual(lines["-2"], "-2|MW|3,SK,0|Glades")
        self.assertEqual(lines["-4"], "-4|MW|3,SK,0|Glades")

    def test_other_worlds_rows_are_not_borrowed(self):
        # world 2's row must never name world 1's slots: world 1's reserved
        # lines are owned by shadow 3, not 4
        self._store(2, {0: self._scout("Wrong World", "Ori2", "P2")})
        lines = self._lines(self._params())
        self.assertEqual(lines["919908"], "919908|MW|3,0,AP Item #1|Grove")

    def test_no_game_id_means_placeholders(self):
        # a seed pulled straight off the generator page has no room to ask
        self._store(self.WORLD, {0: self._scout("Bash", "Ori2", "P2")})
        lines = self._lines(self._params(), game_id=None)
        self.assertEqual(lines["919908"], "919908|MW|3,0,AP Item #1|Grove")
        self.assertEqual(lines["-2"], "-2|MW|3,SK,0|Glades")

    def test_non_ap_params_never_look_names_up(self):
        from ap_models import APNames
        params = self._params()
        params.ap_mode = False
        APNames.load = staticmethod(
            lambda gid, world: self.fail("non-AP seed hit APNames"))
        self._lines(params)

    def test_lookup_failure_is_not_fatal(self):
        from ap_models import APNames
        def boom(gid, world):
            raise RuntimeError("datastore is having a day")
        APNames.load = staticmethod(boom)
        lines = self._lines(self._params())
        self.assertEqual(lines["919908"], "919908|MW|3,0,AP Item #1|Grove")

    def test_annotation_failure_is_not_fatal(self):
        """A seed that won't download is worse than one without names."""
        import archipelago.annotate as annotate_mod
        orig = annotate_mod.annotate
        annotate_mod.annotate = lambda *a, **k: 1 / 0
        self.addCleanup(setattr, annotate_mod, "annotate", orig)
        self._store(self.WORLD, {0: self._scout("Bash", "Ori2", "P2")})
        lines = self._lines(self._params())
        self.assertEqual(lines["919908"], "919908|MW|3,0,AP Item #1|Grove")

    def test_aux_spoiler_uses_the_names_too(self):
        self._store(self.WORLD, {0: self._scout("Bash", "Ori2", "P2")})
        params = self._params()
        spoiler = params.get_aux_spoiler([], False, self.WORLD, game_id=self.GID)
        self.assertIn("Player 3's Bash (Ori2)", spoiler)
        self.assertIn("Player 3's AP Item #2", spoiler)  # unscouted slot
        # and without a game id it is the old, placeholder-only output
        self.assertNotIn("Bash (Ori2)", params.get_aux_spoiler([], False, self.WORLD))


if __name__ == "__main__":
    unittest.main()
