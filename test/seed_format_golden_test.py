"""Golden tests for the SEED FILE line shapes -- the format the shipped dll
parses, as distinct from the tick protocol frozen in golden_wire_test.

Written 2026-08-19 ahead of the seed-format-2 rework (prior_notes/SEED_FORMAT_2.md),
which moves the cross-world lines to carrying item CODES instead of display names
and folds the additive AP fields 5/6 back into field 3. These pin format 1 so that
rework breaks loudly, at every reader, instead of quietly.

They pin SHAPE, not placements: which fields exist, how they split, and what each
one holds. Seed content is the canaries' job.

Run from the repo root:  python3 -m unittest test.seed_format_golden_test -v
"""
import os
import shutil
import sys
import tempfile
import unittest

from archipelago.annotate import annotate
from cli_gen import CLISeedParams
from pickups import Pickup
from util import is_mw_manifest_loc


def generate(out_dir, extra_args, seedfile):
    """Seed lines for one world, straight off cli_gen."""
    argv = ["cli_gen", "--output-dir", out_dir, "--preset", "standard",
            "--seed", "goldenformat"] + extra_args
    old_argv = sys.argv
    sys.argv = argv
    try:
        CLISeedParams().from_cli()
    finally:
        sys.argv = old_argv
    with open(os.path.join(out_dir, seedfile)) as f:
        return [l for l in f.read().splitlines() if l and not l.startswith("//")]


def fields(line):
    return line.split("|")


class _FakeScout(object):
    """An APNames entry, as annotate() reads it."""

    def __init__(self, to="P2", item="Bash", ap_owner=7, ap_item=999999):
        self.to, self.item, self.ap_owner, self.ap_item = to, item, ap_owner, ap_item

    def label(self):
        return "%s (%s)" % (self.item, self.to)


class MultiworldLineTests(unittest.TestCase):
    """The two cross-world line shapes a multiworld seed carries."""

    @classmethod
    def setUpClass(cls):
        cls.out = tempfile.mkdtemp(prefix="seedformat_")
        cls.worlds = [generate(cls.out, ["--players", "2", "--tracking", "--keymode", "clues",
                                         "--share-mode", "multiworld"],
                               "randomizer_%s.dat" % p) for p in (1, 2)]

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.out, ignore_errors=True)

    def finder_lines(self, world):
        return [l for l in world[1:]
                if fields(l)[1] == "MW" and not is_mw_manifest_loc(int(fields(l)[0]))]

    def manifest_lines(self, world):
        return [l for l in world[1:]
                if fields(l)[1] == "MW" and is_mw_manifest_loc(int(fields(l)[0]))]

    def test_the_seed_has_lines_of_both_kinds(self):
        # a vacuous suite would pass every assertion below
        for p, world in enumerate(self.worlds, start=1):
            self.assertTrue(self.finder_lines(world), "world %s has no MW pickups" % p)
            self.assertTrue(self.manifest_lines(world), "world %s has no manifest" % p)

    def test_every_line_has_exactly_four_fields(self):
        # fields 5 and 6 are an AP-only annotation applied at download time
        for p, world in enumerate(self.worlds, start=1):
            for line in world[1:]:
                self.assertEqual(len(fields(line)), 4, "world %s: %s" % (p, line))

    def test_finder_field_three_is_owner_slot_name(self):
        for world in self.worlds:
            for line in self.finder_lines(world):
                parts = fields(line)[2].split(",", 2)
                self.assertEqual(len(parts), 3, line)
                self.assertTrue(parts[0].isdigit(), line)   # owner
                self.assertTrue(parts[1].isdigit(), line)   # slot
                self.assertTrue(parts[2], line)             # display name

    def test_manifest_field_three_is_finder_code_id(self):
        for world in self.worlds:
            for line in self.manifest_lines(world):
                parts = fields(line)[2].split(",", 2)
                self.assertEqual(len(parts), 3, line)
                self.assertTrue(parts[0].isdigit(), line)   # finder
                self.assertTrue(Pickup.n(parts[1], parts[2]), "not a pickup: %s" % line)

    def test_the_finder_carries_a_name_where_the_manifest_carries_a_code(self):
        """THE line that format 2 changes. The finder says "Bash"; only the
        owner's manifest says SK,0 -- which is why the client can't classify a
        cross-world item, and why Sense is blind to every one of them."""
        manifests = {}
        for owner, world in enumerate(self.worlds, start=1):
            for line in self.manifest_lines(world):
                slot = -int(fields(line)[0]) - 2
                _, icode, iid = fields(line)[2].split(",", 2)
                manifests[(owner, slot)] = (icode, iid)

        checked = 0
        for world in self.worlds:
            for line in self.finder_lines(world):
                owner_s, slot_s, name = fields(line)[2].split(",", 2)
                entry = manifests.get((int(owner_s), int(slot_s)))
                self.assertIsNotNone(entry, "no manifest entry for %s" % line)
                icode, iid = entry
                self.assertEqual(name, Pickup.name(icode, iid).replace("|", "/"), line)
                # the code the client needs is exactly what the finder line lacks
                self.assertNotIn(",", name, line)
                checked += 1
        self.assertGreater(checked, 0)

    def test_the_reader_round_trips_a_generated_finder_id(self):
        line = self.finder_lines(self.worlds[0])[0]
        owner_s, slot_s, name = fields(line)[2].split(",", 2)
        item = Pickup.n("MW", fields(line)[2])
        self.assertIsNotNone(item)
        self.assertEqual((item.owner, item.slot), (int(owner_s), int(slot_s)))
        self.assertEqual(item.name, "Player %s's %s" % (owner_s, name))


class SoloControlTests(unittest.TestCase):
    """A single-world seed must never carry a cross-world line -- which is what
    lets format 2 retire only the seeds it actually breaks."""

    @classmethod
    def setUpClass(cls):
        cls.out = tempfile.mkdtemp(prefix="seedformat_solo_")
        cls.lines = generate(cls.out, [], "randomizer0.dat")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.out, ignore_errors=True)

    def test_no_mw_lines_at_all(self):
        self.assertTrue(len(self.lines) > 150)
        self.assertEqual([l for l in self.lines[1:] if fields(l)[1] == "MW"], [])

    def test_every_line_has_exactly_four_fields(self):
        for line in self.lines[1:]:
            self.assertEqual(len(fields(line)), 4, line)


class ApAnnotationTests(unittest.TestCase):
    """The download-time annotation: fields 5 and 6, which format 2 removes.

    annotate() is a pure function over seed tuples, so these drive it directly
    rather than standing a room up."""

    PLAYERS = 2
    WORLD = 1
    SHADOW = "3"            # players + world
    RESERVED = ("919772", "MW", "3,0,AP Item #0", "Glades")

    def _annotate(self, promises=None, entries=None):
        rows = {self.WORLD: (entries if entries is not None else {0: _FakeScout()}, 7)}
        return annotate([self.RESERVED], self.PLAYERS, self.WORLD, rows,
                        lambda v: [], promises=promises)

    def test_an_unscouted_world_passes_straight_through(self):
        out = annotate([self.RESERVED], self.PLAYERS, self.WORLD, {}, lambda v: [])
        self.assertEqual(out, [self.RESERVED])

    def test_field_five_is_recipient_semicolon_item(self):
        line = self._annotate()[0]
        self.assertEqual(len(line), 5)
        self.assertEqual(line[4], "P2;Bash")

    def test_field_six_is_the_promised_manifest_slot(self):
        line = self._annotate(promises={0: 12})[0]
        self.assertEqual(len(line), 6)
        self.assertEqual(line[5], "12")

    def test_no_promise_means_no_sixth_field(self):
        self.assertEqual(len(self._annotate(promises={})[0]), 5)

    def test_the_first_four_fields_survive_except_the_label(self):
        """The whole reason 5 and 6 are additive: a shipped dll reads 0..3 and
        must keep working. Format 2 gives that up deliberately."""
        line = self._annotate()[0]
        self.assertEqual((line[0], line[1], line[3]),
                         (self.RESERVED[0], self.RESERVED[1], self.RESERVED[3]))
        shadow, slot, label = line[2].split(",", 2)
        self.assertEqual((shadow, slot), (self.SHADOW, "0"))
        # the label bakes the recipient in, because field 5 is invisible to old dlls
        self.assertEqual(label, "Bash (P2)")


if __name__ == "__main__":
    unittest.main()
