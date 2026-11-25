import hashlib
import unittest

import cache


class LogicCacheKeyTestCase(unittest.TestCase):
    def test_the_key_names_the_logic_file_s_content(self):
        with open("seedbuilder/areas.ori", "rb") as f:
            want = "CURRENT_LOGIC." + hashlib.sha1(f.read()).hexdigest()[:12]
        self.assertEqual(cache.logic_key(), want)

    def test_a_cached_copy_under_another_key_is_never_served(self):
        c = cache.PythonCache()
        c.cache.set(key="CURRENT_LOGIC", value="stale logic", time=3600)
        with open("seedbuilder/areas.ori") as f:
            self.assertEqual(c.get_areas(), f.read())


if __name__ == "__main__":
    unittest.main()
