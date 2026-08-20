"""A negative pickup id removes one instead of granting it, and must be named
so. RB has always said "Remove X"; the cells and stones were named exactly like
a grant, because HealthCell("-1") builds happily and the subclass loop answered
before the negative check could.

Reported by AsmPrgmC3, 2026-08-20.

Run from the repo root:  python3 -m unittest test.negative_pickup_name_test -v
"""
import unittest

from pickups import Pickup


class NegativeNameTests(unittest.TestCase):
    def test_the_cells_and_stones_say_remove(self):
        for code, name in [("HC", "Health Cell"), ("EC", "Energy Cell"),
                           ("AC", "Ability Cell"), ("KS", "Keystone"),
                           ("MS", "Mapstone")]:
            self.assertEqual(Pickup.name(code, "-1"), "Remove " + name, code)

    def test_a_bonus_skill_still_says_remove(self):
        self.assertEqual(Pickup.name("RB", "-101"), "Remove Polarity Shift")

    def test_an_upgrade_still_says_remove(self):
        self.assertEqual(Pickup.name("RB", "-15"), "Remove Energy Regeneration")

    def test_a_positive_is_untouched(self):
        for code, name in [("HC", "Health Cell"), ("KS", "Keystone"),
                           ("RB", "Polarity Shift")]:
            pid = "1" if code != "RB" else "101"
            self.assertEqual(Pickup.name(code, pid), name, code)

    def test_an_id_that_merely_contains_a_dash_is_not_a_removal(self):
        self.assertEqual(Pickup.name("SH", "a-b"), "Message: a-b")
        self.assertEqual(Pickup.name("TW", "Warp,1,-2,Zone"), "Warp")

    def test_an_unknown_negative_falls_through_rather_than_lying(self):
        self.assertEqual(Pickup.name("RB", "-999999"), "RB|-999999")


if __name__ == "__main__":
    unittest.main()
