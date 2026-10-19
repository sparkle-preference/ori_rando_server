import unittest
from unittest import mock

from seedbuilder.seedparams import SeedGenParams
from web import seedstats

# a saved preset's shape: one world's rules, its item pool included
SETTINGS = {"keyMode": "Clues", "variations": ["ForceTrees"], "expPool": 10000, "cellFreq": 256, "spawn": "Glades",
            "paths": ["standard-core", "casual-core", "standard-dboost", "casual-dboost", "standard-abilities", "standard-lure"],
            "selectedPool": "Standard",
            "itemPool": {"TP|Grove": [1], "TP|Swamp": [1], "TP|Grotto": [1], "TP|Valley": [1], "TP|Sorrow": [1],
                         "TP|Ginso": [1], "TP|Horu": [1], "TP|Forlorn": [1], "HC|1": [12], "EC|1": [15], "AC|1": [33],
                         "RB|0": [3], "RB|1": [3], "RB|6": [3], "RB|9": [1], "RB|10": [1], "RB|11": [1], "RB|12": [1],
                         "RB|13": [3], "RB|15": [3]}}


class RollTestCase(unittest.TestCase):
    def test_rolls_never_touch_the_datastore(self):
        with mock.patch.object(SeedGenParams, "put", side_effect=AssertionError("put")):
            rolls = seedstats.roll(SETTINGS, ["stats1", "stats2"])
        self.assertEqual([r["seed"] for r in rolls], ["stats1", "stats2"])
        for r in rolls:
            self.assertTrue(r["placements"])
            self.assertTrue(all(len(p) == 3 for p in r["placements"]))

    def test_the_same_seed_rolls_the_same(self):
        a, b = seedstats.roll(SETTINGS, ["same"]), seedstats.roll(SETTINGS, ["same"])
        self.assertEqual(a, b)

    def test_a_request_is_capped(self):
        with mock.patch.object(SeedGenParams, "generate", return_value=False):
            rolls = seedstats.roll(SETTINGS, [str(i) for i in range(seedstats.ROLL_CAP + 5)])
        self.assertEqual(len(rolls), seedstats.ROLL_CAP)
        self.assertTrue(all(r["placements"] is None for r in rolls))

    def test_settings_that_make_no_seed_are_refused(self):
        with self.assertRaises(ValueError):
            seedstats.roll(dict(SETTINGS, paths=[]), ["x"])


if __name__ == "__main__":
    unittest.main()
