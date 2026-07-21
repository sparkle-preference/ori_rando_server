"""Seed generation tests (python3).

Run from the repo root:  python3 -m unittest test.seedgentest -v
"""
import os
import re
import shutil
import sys
import tempfile
import unittest

from cli_gen import CLISeedParams

PICKUP_LINE = re.compile(r"^-?\d+\|\w+\|[^|]*\|\w*")


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


if __name__ == "__main__":
    unittest.main()
