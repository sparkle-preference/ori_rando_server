"""Golden tests for deriving multiworld wire lines from a plando's INTENT.

A plando stores a cross-world item as the world holding it plus whose it is
(Stuff.player / Stuff.owner). The finder line and the owner's slot manifest are
derived at serve time by get_seed_data, never stored -- so a hand-edit of one
half cannot desync it from the other, and nobody has to track slot numbers.

These pin that derivation: which lines each world gets, and that the slot the
finder points at is the slot the owner's manifest describes.

Run from the repo root:  python3 -m unittest test.plando_mw_test -v
"""
import unittest

from enums import MultiplayerGameType
from seedbuilder.generator import MultiworldSlotOverflow
from seedbuilder.seedparams import MultiplayerOptions, Placement, SeedGenParams, Stuff
from util import parse_fass


def plando(players, *placements):
    """Params standing in for a saved multiworld plando."""
    params = SeedGenParams(players=players, is_plando=True)
    params.sync = MultiplayerOptions()
    params.sync.enabled = players > 1
    params.sync.mode = MultiplayerGameType.MULTIWORLD
    params.placements = [
        Placement(location=loc, zone=zone,
                  stuff=[Stuff(code=code, id=pid, player=str(holder),
                               owner=str(owner) if owner else None)])
        for loc, zone, code, pid, holder, owner in placements
    ]
    return params


def lines(params, player):
    return ["|".join(row) for row in params.get_seed_data(player)]


class PlandoOwnershipTests(unittest.TestCase):
    def test_an_ordinary_placement_is_untouched(self):
        p = plando(2, ("719620", "Glades", "SK", "0", 1, None))
        self.assertEqual(lines(p, 1), ["719620|SK|0|Glades"])
        self.assertEqual(lines(p, 2), [])

    def test_a_cross_world_item_splits_into_a_pair(self):
        p = plando(2, ("719620", "Glades", "SK", "0", 1, 2))
        # world 1 holds it and points at world 2's slot 0
        self.assertEqual(lines(p, 1), ["719620|MW|2,0,SK,0|Glades"])
        # world 2 is told what lands in that slot, and who finds it
        self.assertEqual(lines(p, 2), ["-2|MW|1,,SK,0|Glades"])

    def test_the_finder_slot_is_the_manifest_slot(self):
        p = plando(2,
                   ("1", "Glades", "SK", "0", 1, 2),
                   ("2", "Grove", "HC", "1", 1, 2),
                   ("3", "Grotto", "EC", "1", 1, 2))
        finders = lines(p, 1)
        manifests = lines(p, 2)
        self.assertEqual(len(finders), 3)
        self.assertEqual(len(manifests), 3)
        for finder, manifest in zip(finders, manifests):
            slot = finder.split("|")[2].split(",")[1]
            self.assertEqual(manifest.split("|")[0], str(-(int(slot) + 2)), (finder, manifest))

    def test_slots_are_per_owner(self):
        p = plando(3,
                   ("1", "Glades", "SK", "0", 1, 2),
                   ("2", "Grove", "SK", "4", 1, 3),
                   ("3", "Grotto", "SK", "8", 1, 2))
        # each owner counts from zero on their own
        self.assertEqual(lines(p, 1), ["1|MW|2,0,SK,0|Glades",
                                       "2|MW|3,0,SK,4|Grove",
                                       "3|MW|2,1,SK,8|Grotto"])
        self.assertEqual(lines(p, 2), ["-2|MW|1,,SK,0|Glades", "-3|MW|1,,SK,8|Grotto"])
        self.assertEqual(lines(p, 3), ["-2|MW|1,,SK,4|Grove"])

    def test_slot_numbering_does_not_depend_on_who_is_asking(self):
        """Every world's call walks all placements, so the numbers agree
        without being stored."""
        p = plando(3,
                   ("1", "Glades", "SK", "0", 2, 3),
                   ("2", "Grove", "HC", "1", 1, 3))
        first = lines(p, 3)
        self.assertEqual(first, lines(p, 3))            # stable across calls
        self.assertEqual([l.split("|")[0] for l in first], ["-2", "-3"])

    def test_an_item_owned_by_its_holder_is_not_cross_world(self):
        p = plando(2, ("719620", "Glades", "SK", "0", 1, 1))
        self.assertEqual(lines(p, 1), ["719620|SK|0|Glades"])
        self.assertEqual(lines(p, 2), [])

    def test_a_generated_mw_line_passes_straight_through(self):
        """A generated seed stores cross-world lines already in wire form, with
        no owner set; it must not be derived a second time."""
        p = plando(2, ("719620", "Glades", "MW", "2,7,SK,0", 1, None))
        self.assertEqual(lines(p, 1), ["719620|MW|2,7,SK,0|Glades"])

    def test_an_id_carrying_commas_survives(self):
        p = plando(2, ("1", "Sorrow", "TW", "Warp to Three Bird AC,646,-127,Swamp", 1, 2))
        self.assertEqual(lines(p, 1), ["1|MW|2,0,TW,Warp to Three Bird AC,646,-127,Swamp|Sorrow"])
        self.assertEqual(lines(p, 2), ["-2|MW|1,,TW,Warp to Three Bird AC,646,-127,Swamp|Sorrow"])

    def test_too_many_slots_for_one_owner_is_refused(self):
        p = plando(2, *[(str(i), "Glades", "EX", "100", 1, 2) for i in range(300)])
        with self.assertRaises(MultiworldSlotOverflow):
            lines(p, 1)



class MultipickupOwnershipTests(unittest.TestCase):
    """A multipickup can hand different pieces to different people. The plando
    stores that as an "@owner" suffix per sub-item; the wire has no such
    suffix and carries an MW child, which found_pickup already walks into."""

    def test_a_mixed_multipickup_splits(self):
        p = plando(2, ("1", "Glades", "MU", "SK/0@2/HC/1", 1, None))
        # the holder keeps HC and hands SK to player 2, through an MW child
        self.assertEqual(lines(p, 1), ["1|MU|MW/2,0,SK,0/HC/1|Glades"])
        self.assertEqual(lines(p, 2), ["-2|MW|1,,SK,0|Glades"])

    def test_every_piece_can_be_someone_elses(self):
        # each owner counts slots on their own, so both are slot 0
        p = plando(3, ("1", "Glades", "MU", "SK/0@2/HC/1@3", 1, None))
        self.assertEqual(lines(p, 1), ["1|MU|MW/2,0,SK,0/MW/3,0,HC,1|Glades"])
        self.assertEqual(lines(p, 2), ["-2|MW|1,,SK,0|Glades"])
        self.assertEqual(lines(p, 3), ["-2|MW|1,,HC,1|Glades"])

    def test_a_suffix_naming_the_holder_is_not_cross_world(self):
        p = plando(2, ("1", "Glades", "MU", "SK/0@1/HC/1", 1, None))
        self.assertEqual(lines(p, 1), ["1|MU|SK/0/HC/1|Glades"])
        self.assertEqual(lines(p, 2), [])

    def test_a_plain_multipickup_is_untouched(self):
        p = plando(2, ("1", "Glades", "MU", "SK/0/HC/1", 1, None))
        self.assertEqual(lines(p, 1), ["1|MU|SK/0/HC/1|Glades"])

    def test_multipickup_slots_share_the_single_item_sequence(self):
        """Both kinds draw from one per-owner counter, or a pair would collide."""
        p = plando(2,
                   ("1", "Glades", "SK", "0", 1, 2),
                   ("2", "Grove", "MU", "HC/1@2/EC/1", 1, None))
        self.assertEqual(lines(p, 1), ["1|MW|2,0,SK,0|Glades", "2|MU|MW/2,1,HC,1/EC/1|Grove"])
        self.assertEqual(lines(p, 2), ["-2|MW|1,,SK,0|Glades", "-3|MW|1,,HC,1|Grove"])


class ForcedAssignmentParseTests(unittest.TestCase):
    """util.parse_fass, shared by cli_gen and /plando/fillgen. The web route
    used to int() the whole location, so a world-prefixed one threw."""

    def test_a_bare_location_is_world_one(self):
        self.assertEqual(parse_fass("919772:SK0"), {(1, 919772): "SK0"})

    def test_a_world_prefix_is_honoured(self):
        self.assertEqual(parse_fass("2.919772:SK0"), {(2, 919772): "SK0"})

    def test_an_owner_rides_the_value(self):
        self.assertEqual(parse_fass("1.919772:SK0@2"), {(1, 919772): "SK0|2"})

    def test_several_are_pipe_joined(self):
        self.assertEqual(parse_fass("1.1:SK0@2|2.2:HC1"),
                         {(1, 1): "SK0|2", (2, 2): "HC1"})

    def test_a_negative_location_survives(self):
        self.assertEqual(parse_fass("1.-160:EC1"), {(1, -160): "EC1"})

    def test_empty_is_empty(self):
        self.assertEqual(parse_fass(""), {})
        self.assertEqual(parse_fass(None), {})

    def test_a_non_numeric_location_is_refused(self):
        with self.assertRaises(ValueError):
            parse_fass("Glades:SK0")


if __name__ == "__main__":
    unittest.main()
