"""The process-local SeedGenParams cache: request paths share one inflated
copy instead of paying ~3000 protobuf decodes per read (about half a second
on a big multiworld). Correct only single-instance, like bingo_lock; entries
are shared and read-only; every put busts via the hooks.

Run from the repo root:  python3 -m unittest test.params_cache_test -v
"""
import unittest

import google.auth.credentials
from google.cloud import ndb

from seedbuilder import seedparams
from seedbuilder.seedparams import SeedGenParams


class ParamsCacheTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        creds = google.auth.credentials.AnonymousCredentials()
        cls.ndb_client = ndb.Client(project="unit-test", credentials=creds)

    def setUp(self):
        self._ctx = self.ndb_client.context()
        self._ctx.__enter__()
        seedparams._PARAMS_CACHE.clear()
        self.reads = []
        self._get = SeedGenParams.__dict__.get("get_by_id")
        self._get_inherited = SeedGenParams.get_by_id
        self.entities = {}
        SeedGenParams.get_by_id = staticmethod(
            lambda pid: self.reads.append(pid) or self.entities.get(pid))

    def tearDown(self):
        if self._get is not None:
            SeedGenParams.get_by_id = self._get
        else:
            del SeedGenParams.get_by_id
        seedparams._PARAMS_CACHE.clear()
        self._ctx.__exit__(None, None, None)

    def _plant(self, pid):
        self.entities[pid] = SeedGenParams(id=pid, seed="cached")
        return self.entities[pid]

    def test_second_read_is_the_same_inflated_object(self):
        planted = self._plant(1234)
        a = SeedGenParams.with_id("1234")   # routes pass strings
        b = SeedGenParams.cached_by_id(1234)
        self.assertIs(a, planted)
        self.assertIs(a, b)
        self.assertEqual(self.reads, [1234])

    def test_cached_by_key_handles_none(self):
        self.assertIsNone(SeedGenParams.cached_by_key(None))
        self.assertEqual(self.reads, [])

    def test_put_busts_the_entry(self):
        planted = self._plant(1234)
        SeedGenParams.with_id(1234)
        planted._post_put_hook(None)        # what ndb fires after any put
        replaced = self._plant(1234)
        self.assertIs(SeedGenParams.with_id(1234), replaced)
        self.assertEqual(self.reads, [1234, 1234])

    def test_delete_busts_the_entry(self):
        planted = self._plant(1234)
        SeedGenParams.with_id(1234)
        SeedGenParams._post_delete_hook(planted.key, None)
        del self.entities[1234]
        self.assertIsNone(SeedGenParams.with_id(1234))
        self.assertEqual(self.reads, [1234, 1234])

    def test_misses_are_not_cached(self):
        # a params id that doesn't exist yet (generation in flight) must not
        # negative-cache: the entity appears moments later
        self.assertIsNone(SeedGenParams.with_id(77))
        self._plant(77)
        self.assertIsNotNone(SeedGenParams.with_id(77))

    def test_the_cache_stays_bounded(self):
        for pid in range(100, 100 + 20):
            self._plant(pid)
            SeedGenParams.with_id(pid)
        self.assertLessEqual(len(seedparams._PARAMS_CACHE),
                             seedparams._PARAMS_CACHE.maxsize)


if __name__ == "__main__":
    unittest.main()
