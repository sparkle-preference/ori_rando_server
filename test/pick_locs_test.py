import unittest
from collections import Counter

from util import picks_by_type_generator


class PickLocsTest(unittest.TestCase):
    def test_each_loc_is_listed_once(self):
        # the map pages key a marker by its pick, so a repeat renders twice
        locs = Counter(p["loc"] for group in picks_by_type_generator().values() for p in group)
        self.assertEqual([loc for loc, n in locs.items() if n > 1], [])


if __name__ == "__main__":
    unittest.main()
