"""The tracker engine's keystone doors: the spend model for seeds our own
walk placed, the room's cumulative tiers for AP seeds."""
import unittest

from archipelago.convert import keystone_tier_map, tier_map_from_list
from reachable import Map, PlayerState

MODES = ("casual-core", "casual-dboost")
CANONICAL = [2, 4, 6, 8, 12, 16, 20, 24, 28, 32, 36, 40]
GLADES = ("GladesFirstKeyDoor", "GladesFirstKeyDoorOpened")
UPPER_GINSO = ("UpperGinsoDoorClosed", "UpperGinsoDoorOpened")
TP_GINSO = ("TP", "Ginso", 1, False)


def reach(ks, tiers=None, extra=()):
    state = PlayerState([("KS", "1", ks, False)] + list(extra))
    areas = Map.get_reachable_areas(state, MODES, "Glades", need_reached_with=False,
                                    ks_tiers=tiers)
    return set(areas), state


class SpendModelTests(unittest.TestCase):
    def test_doors_spend_the_keystones_they_cost(self):
        areas, state = reach(3)
        self.assertIn("GladesFirstKeyDoorOpened", areas)
        self.assertNotIn("SpiritCavernsDoorOpened", areas, "Glades took two of the three")
        self.assertEqual(state.has["KS"], 1)
        areas, _ = reach(4)
        self.assertIn("SpiritCavernsDoorOpened", areas)


class TierModelTests(unittest.TestCase):
    def test_doors_charge_lifetime_against_their_tier_and_spend_nothing(self):
        tiers = tier_map_from_list(CANONICAL)
        areas, state = reach(4, tiers, extra=[TP_GINSO])
        self.assertIn("GladesFirstKeyDoorOpened", areas)
        self.assertIn("SpiritCavernsDoorOpened", areas)
        self.assertIn("UpperGinsoDoorClosed", areas, "the teleporter reaches the door")
        self.assertNotIn("UpperGinsoDoorOpened", areas, "but its tier is 20")
        self.assertEqual(state.has["KS"], 4, "nothing is deducted")
        self.assertNotIn("UpperGinsoDoorOpened", reach(19, tiers, extra=[TP_GINSO])[0])
        self.assertIn("UpperGinsoDoorOpened", reach(20, tiers, extra=[TP_GINSO])[0])

    def test_gaining_an_item_never_loses_an_area(self):
        tiers = tier_map_from_list(CANONICAL)
        before, _ = reach(13, tiers)
        after, _ = reach(13, tiers, extra=[TP_GINSO])
        self.assertLessEqual(before, after)

    def test_tier_map_follows_the_params(self):
        class P(object):
            ap_mode = True
            variations = []
            ks_door_order = {"1": [list(UPPER_GINSO), list(GLADES)]}
        tiers = keystone_tier_map(P(), 1)
        self.assertEqual(tiers[UPPER_GINSO], 4, "first-seen door gets the cheapest tier")
        self.assertEqual(tiers[GLADES], 6)
        self.assertEqual(len(tiers), 12)
        self.assertEqual(keystone_tier_map(P(), 2)[GLADES], 2, "no recorded order: canonical")

        class OpenWorld(P):
            variations = ["OpenWorld"]
        self.assertNotIn(GLADES, keystone_tier_map(OpenWorld(), 1), "the Glades door is pre-opened")

        class Keysanity(P):
            variations = ["Keysanity"]
        self.assertIsNone(keystone_tier_map(Keysanity(), 1))

        class NotAp(P):
            ap_mode = False
        self.assertIsNone(keystone_tier_map(NotAp(), 1), "our own walk placed it: spend model")


if __name__ == "__main__":
    unittest.main()
