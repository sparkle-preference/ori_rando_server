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


class _FakeTrackerParams(object):
    ap_mode = True
    players = 2
    variations = []

    def __init__(self):
        self.named_calls = []

    def get_seed_data(self, player=1):
        return [("919908", "MW", "3,0,,-1,AP,AP Item #1", "Grove"),
                ("959960", "MW", "3,1,,-1,AP,AP Item #2", "Sorrow"),
                ("919772", "MW", "3,2,,-1,AP,AP Item #3", "Grove"),
                ("799804", "MW", "3,3,,-1,AP,AP Item #4", "Grove"),
                ("1799708", "MW", "2,55,TP,Valley", "Valley"),
                ("-2", "MW", "3,,SK,0", "Glades"),
                ("2", "SK", "0", "Glades")]

    def ap_named(self, seed_data, player, game_id):
        self.named_calls.append(game_id)
        annotated = {
            # another Ori world's item, a self item, a foreign game's item
            "919908": ("919908", "MW", "3,0,P2,-1,RB,302", "Grove"),
            "959960": ("959960", "MW", "3,1,P1,-1,SK,0", "Sorrow"),
            "919772": ("919772", "MW", "3,2,Cleric,-1,AP,Progressive Sword", "Grove"),
        }
        return [annotated.get(line[0], line) for line in seed_data]


class _FakeTrackerGame(object):
    def __init__(self, params):
        class _Key(object):
            def __init__(self, p):
                self._p = p

            def get(self):
                return self._p
        self.params = _Key(params)

    def fetch_params(self):
        return self.params.get()

    def player(self, pid, create=True, delay_put=False):
        class _P(object):
            def is_ap_shadow(self):
                return False

            def name(self):
                return "tester"

            def mw_names_field(self):
                # the live wire-names the in-game client resolves against
                return "1.Asm;2.Cap;3.Archipelago;4.Archipelago"
        return _P()


class TrackerSeedAnnotationTestCase(unittest.TestCase):
    """The tracker seed view speaks scouted labels for AP lines -- without
    this, AP locations tooltip "AP Item #n" forever -- and never renders a
    shadow pid as a player name."""

    def setUp(self):
        self._ndb = models.client
        models.client = _FakeNdbClient()
        self._secret = main.app.secret_key
        main.app.secret_key = main.app.secret_key or "tracker-seed-test"
        self._with_id = models.Game.__dict__["with_id"]
        self.params = _FakeTrackerParams()
        game = _FakeTrackerGame(self.params)
        models.Game.with_id = staticmethod(lambda gid: game)
        self.client = main.app.test_client()

    def tearDown(self):
        models.Game.with_id = self._with_id
        main.app.secret_key = self._secret
        models.client = self._ndb

    def test_reserved_lines_speak_the_in_game_format(self):
        r = self.client.get("/tracker/game/135658/fetch/player/1/seed")
        self.assertEqual(r.status_code, 200)
        seed = r.get_json()["seed"]
        self.assertEqual(self.params.named_calls, [135658])
        # one shape everywhere: bare for self, live-named possessive for
        # everyone else -- Ori sibling, foreign game, and native MW alike
        self.assertEqual(seed["959960"], "Bash")
        self.assertEqual(seed["919908"], "Cap's Grotto Keystone")
        self.assertEqual(seed["919772"], "Cleric's Progressive Sword")
        self.assertEqual(seed["1799708"], "Cap's Valley teleporter")
        # unscouted stays the honest placeholder
        self.assertEqual(seed["799804"], "AP Item #4")
        # manifest pseudo-locations still aren't map locations
        self.assertNotIn("-2", seed)
        self.assertIn("2", seed)

    def test_non_ap_games_never_touch_the_rows(self):
        self.params.ap_mode = False
        r = self.client.get("/tracker/game/77/fetch/player/1/seed")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.params.named_calls, [])
        # the placeholder label is what the raw line carries
        self.assertIn("919908", r.get_json()["seed"])


if __name__ == "__main__":
    unittest.main()
