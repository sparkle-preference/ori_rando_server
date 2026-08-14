"""The AP seed-download gate: /generator/seed refuses to serve a snapshot
that would keep placeholder names forever, unless the caller forces it.

Stubs in the save/restore style (no mock lib), driving the real route via
test_client so the gate's placement ahead of the seed build is what's tested.

Run from the repo root:  python3 -m unittest test.ap_gate_test -v
"""
import contextlib
import unittest

import ap_models
import main
import models
from seedbuilder.seedparams import SeedGenParams


class _FakeNdbClient(object):
    def context(self):
        return contextlib.nullcontext()


class _FakeParams(object):
    ap_mode = True
    players = 2
    tracking = False

    def get_seed(self, pid, game_id=None, verbose_paths=False):
        return "seed!"


class _FakeLink(object):
    def __init__(self, totals, counts):
        self.name_totals, self.name_counts = totals, counts


class ApSeedGateTestCase(unittest.TestCase):
    def setUp(self):
        self._ndb = models.client
        models.client = _FakeNdbClient()
        self._secret = main.app.secret_key
        main.app.secret_key = main.app.secret_key or "ap-gate-test"
        self._params_with_id = SeedGenParams.__dict__["with_id"]
        self._link_with_id = ap_models.APLink.__dict__["with_id"]
        self.params = _FakeParams()
        self.link = None
        SeedGenParams.with_id = staticmethod(lambda pid: self.params)
        ap_models.APLink.with_id = staticmethod(lambda gid: self.link)
        self.client = main.app.test_client()

    def tearDown(self):
        SeedGenParams.with_id = self._params_with_id
        ap_models.APLink.with_id = self._link_with_id
        main.app.secret_key = self._secret
        models.client = self._ndb

    def test_non_ap_seed_is_untouched(self):
        self.params.ap_mode = False
        r = self.client.get("/generator/seed/x")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"seed!", r.data)

    def test_ap_seed_without_game_is_refused(self):
        r = self.client.get("/generator/seed/x")
        self.assertEqual(r.status_code, 409)
        self.assertIn("no game attached", r.get_json()["error"])

    def test_ap_seed_before_room_connect_is_refused(self):
        r = self.client.get("/generator/seed/x?game_id=99")
        self.assertEqual(r.status_code, 409)
        self.assertIn("Connect the Archipelago room", r.get_json()["error"])
        self.assertTrue(r.get_json()["retryable"])

    def test_ap_seed_with_unscouted_world_is_refused(self):
        # world 2 never reported (-1): the cross-world join would be partial
        self.link = _FakeLink([5, -1], [5, 0])
        r = self.client.get("/generator/seed/x?game_id=99")
        self.assertEqual(r.status_code, 409)
        self.assertIn("location scouts", r.get_json()["error"])

    def test_ap_seed_with_partial_names_is_refused(self):
        self.link = _FakeLink([5, 4], [5, 2])
        r = self.client.get("/generator/seed/x?game_id=99")
        self.assertEqual(r.status_code, 409)
        self.assertIn("7/9", r.get_json()["error"])

    def test_ap_seed_with_complete_names_downloads(self):
        self.link = _FakeLink([5, 4], [5, 4])
        r = self.client.get("/generator/seed/x?game_id=99")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"seed!", r.data)

    def test_world_with_no_ap_locations_counts_as_scouted(self):
        self.link = _FakeLink([0, 0], [0, 0])
        r = self.client.get("/generator/seed/x?game_id=99")
        self.assertEqual(r.status_code, 200)

    def test_force_bypasses_the_gate(self):
        r = self.client.get("/generator/seed/x?game_id=99&force=1")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"seed!", r.data)

    def test_short_count_arrays_read_as_unscouted(self):
        # repeated props start empty; a link that never reported must gate
        self.link = _FakeLink([], [])
        r = self.client.get("/generator/seed/x?game_id=99")
        self.assertEqual(r.status_code, 409)


if __name__ == "__main__":
    unittest.main()
