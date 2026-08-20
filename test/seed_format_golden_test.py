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

    # 524288 is Bash in the datapackage; a made-up id is a foreign game's item
    def __init__(self, to="P2", item="Bash", ap_owner=7, ap_item=524288):
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

    def test_manifest_field_three_is_finder_holder_code_id(self):
        for world in self.worlds:
            for line in self.manifest_lines(world):
                parts = fields(line)[2].split(",", 3)
                self.assertEqual(len(parts), 4, line)
                self.assertTrue(parts[0].isdigit(), line)   # finder
                # only the download-time AP join fills a holder in
                self.assertEqual(parts[1], "", line)
                self.assertTrue(Pickup.n(parts[2], parts[3]), "not a pickup: %s" % line)

    def test_the_finder_carries_the_same_code_the_manifest_does(self):
        """The point of the format. A cross-world line names its item the way
        every other line does, so anything that classifies pickups -- Sense
        above all -- sees it too."""
        manifests = {}
        for owner, world in enumerate(self.worlds, start=1):
            for line in self.manifest_lines(world):
                slot = -int(fields(line)[0]) - 2
                _, _, icode, iid = fields(line)[2].split(",", 3)
                manifests[(owner, slot)] = (icode, iid)

        checked = 0
        for world in self.worlds:
            for line in self.finder_lines(world):
                owner_s, slot_s, fcode, fid = fields(line)[2].split(",", 3)
                entry = manifests.get((int(owner_s), int(slot_s)))
                self.assertIsNotNone(entry, "no manifest entry for %s" % line)
                self.assertEqual((fcode, fid), entry, line)
                checked += 1
        self.assertGreater(checked, 0)

    def test_the_reader_round_trips_a_generated_finder_id(self):
        line = self.finder_lines(self.worlds[0])[0]
        owner_s, slot_s, fcode, fid = fields(line)[2].split(",", 3)
        item = Pickup.n("MW", fields(line)[2])
        self.assertIsNotNone(item)
        self.assertEqual((item.owner, item.slot), (int(owner_s), int(slot_s)))
        self.assertEqual((item.item_code, item.item_id), (fcode, fid))
        self.assertEqual(item.name, "Player %s's %s" % (owner_s, Pickup.name(fcode, fid)))


class WarpIdTests(unittest.TestCase):
    """A TW id is "<name>,<x>,<y>,<node>" -- an item id that carries commas of
    its own, which is why the id is the last field and every split is bounded.
    Warps are forced here so the case is structural, not luck of the roll."""

    @classmethod
    def setUpClass(cls):
        cls.out = tempfile.mkdtemp(prefix="seedformat_tw_")
        cls.worlds = [generate(cls.out, ["--players", "2", "--tracking", "--keymode", "clues",
                                         "--share-mode", "multiworld",
                                         "--warps-instead-of-tps", "9"],
                               "randomizer_%s.dat" % p) for p in (1, 2)]

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.out, ignore_errors=True)

    def warp_lines(self):
        return [l for world in self.worlds for l in world[1:]
                if fields(l)[1] == "MW" and ",TW," in fields(l)[2]]

    def test_the_seed_places_cross_world_warps(self):
        self.assertTrue(self.warp_lines(), "no cross-world warps to check")

    def test_the_whole_warp_id_lands_in_the_last_field(self):
        for line in self.warp_lines():
            parts = fields(line)[2].split(",", 3)
            self.assertEqual(len(parts), 4, line)
            code, id = parts[2], parts[3]
            self.assertEqual(code, "TW", line)
            self.assertEqual(id.count(","), 3, line)
            self.assertTrue(Pickup.n("TW", id), line)

    def test_the_reader_recovers_the_warp_intact(self):
        for line in self.warp_lines():
            if is_mw_manifest_loc(int(fields(line)[0])):
                continue  # a manifest id holds a holder where a finder holds a slot
            f3 = fields(line)[2]
            item = Pickup.n("MW", f3)
            self.assertIsNotNone(item, line)
            self.assertEqual(item.item_code, "TW", line)
            self.assertEqual(item.item_id, f3.split(",", 3)[3], line)


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
    """The download-time annotation, which format 2 folds into field 3.

    annotate() is a pure function over seed tuples, so these drive it directly
    rather than standing a room up."""

    PLAYERS = 2
    WORLD = 1
    SHADOW = "3"            # players + world
    RESERVED = ("919772", "MW", "3,0,,-1,AP,AP Item #0", "Glades")

    def _annotate(self, promises=None, entries=None):
        rows = {self.WORLD: (entries if entries is not None else {0: _FakeScout()}, 7)}
        return annotate([self.RESERVED], self.PLAYERS, self.WORLD, rows,
                        lambda v: [], promises=promises)

    def parts(self, line):
        return line[2].split(",", 5)

    def test_an_unscouted_world_passes_straight_through(self):
        out = annotate([self.RESERVED], self.PLAYERS, self.WORLD, {}, lambda v: [])
        self.assertEqual(out, [self.RESERVED])

    def test_a_scouted_line_keeps_four_fields(self):
        """What the additive fields cost, reclaimed: no shape depends on how
        much the room has told us."""
        line = self._annotate()[0]
        self.assertEqual(len(line), 4)
        self.assertEqual((line[0], line[1], line[3]),
                         (self.RESERVED[0], self.RESERVED[1], self.RESERVED[3]))

    def test_the_recipient_rides_field_three(self):
        self.assertEqual(self.parts(self._annotate()[0])[2], "P2")

    def test_the_promised_slot_rides_field_three(self):
        self.assertEqual(self.parts(self._annotate(promises={0: 12})[0])[3], "12")

    def test_no_promise_is_minus_one_rather_than_a_missing_field(self):
        """An abstention has to keep the arity, or the field after it moves."""
        self.assertEqual(self.parts(self._annotate(promises={})[0])[3], "-1")

    def test_an_ori_item_is_named_by_code_and_a_foreign_one_by_name(self):
        """ITEM_BY_AP_ID knows the room's id for anything of ours, so an
        exported Ori item comes back classifiable; only a genuinely foreign
        item falls back to carrying its name."""
        ours = self.parts(self._annotate()[0])
        self.assertEqual(ours[4:], ["SK", "0"])

        foreign = _FakeScout(item="Hush, Hush", ap_item=999999999)
        line = self.parts(self._annotate(entries={0: foreign})[0])
        # the name keeps its comma because it is the last field
        self.assertEqual(line[4:], ["AP", "Hush, Hush"])


if __name__ == "__main__":
    unittest.main()
