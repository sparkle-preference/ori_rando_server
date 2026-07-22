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
    MW_CANARY = "dcf12ab71e68927fa54c7ed8b13fb92361af2ba172ee2b4f560cd8efb28dffe2"

    def test_mw_output_canary(self):
        import hashlib
        h = hashlib.sha256()
        for p in range(1, self.PLAYERS + 1):
            h.update(("\n".join(self.seeds[p]) + "\n").encode("utf-8"))
        self.assertEqual(h.hexdigest(), self.MW_CANARY,
                         "multiworld seed output changed for an existing seed string -- see comment above")

    def test_rejects_unsupported_combos(self):
        for extra in (["--entrance"], ["--keymode", "LimitKeys"], ["--world-tour", "8"]):
            outdir = tempfile.mkdtemp(prefix="seedgentest_mwrej_")
            try:
                old_argv = sys.argv
                sys.argv = self.ARGS + ["--output-dir", outdir] + extra
                try:
                    CLISeedParams().from_cli()
                finally:
                    sys.argv = old_argv
                self.assertFalse(os.path.exists(os.path.join(outdir, "randomizer_1.dat")),
                                 "multiworld should reject %s" % extra)
            finally:
                shutil.rmtree(outdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
