"""What a game reset forgets, and what it must not.

Player.clear_progress is datastore-free on purpose, so these drive it directly
rather than needing an emulator.

Run from the repo root:  python3 -m unittest test.reset_test -v
"""
import unittest

import google.auth.credentials
from google.cloud import ndb

from models import Player, hl_dedup_key, HistoryLine, HIST_TAIL


class ResetTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        creds = google.auth.credentials.AnonymousCredentials()
        cls.ndb_client = ndb.Client(project="unit-test", credentials=creds)

    def setUp(self):
        self._ctx = self.ndb_client.context()
        self._ctx.__enter__()

    def tearDown(self):
        self._ctx.__exit__(None, None, None)

    def player(self, **kw):
        return Player(id="9.1", **kw)


class ProgressIsForgotten(ResetTestCase):
    def test_history_records_again_after_a_reset(self):
        """The one that matters. hist_seen is the replay guard: a pickup found
        before the reset would otherwise dedup against the old run forever, and
        the game would silently record nothing."""
        line = HistoryLine(pickup_code="SK", pickup_id="0", coords=123)
        p = self.player()
        chunk = type("_C", (), {"lines": []})()
        self.assertTrue(Player.hl_chunk_append(p, chunk, line))
        # push it out of the tail window, which is what puts it in hist_seen
        for i in range(HIST_TAIL + 1):
            Player.hl_chunk_append(p, chunk, HistoryLine(pickup_code="EX", pickup_id=str(i), coords=1000 + i))
        self.assertIn(hl_dedup_key(line), p.hist_seen)
        self.assertFalse(Player.hl_chunk_append(p, chunk, line), "guard should hold mid-run")

        p.clear_progress()
        fresh = type("_C", (), {"lines": []})()
        self.assertTrue(Player.hl_chunk_append(p, fresh, line),
                        "a re-found pickup must write a history line after a reset")

    def test_the_dedup_bookkeeping_is_cleared(self):
        p = self.player(hist_chunk=3, hist_tail=[1, 2, 3], hist_seen=[4, 5])
        p.clear_progress()
        self.assertEqual((p.hist_chunk, p.hist_tail, p.hist_seen), (0, [], []))

    def test_run_state_is_cleared(self):
        p = self.player(skills=7, events=3, teleporters=5, bonuses={"RB0": 1},
                        hints={"123": 2}, shared_released=[123, 456],
                        bingo_last_tp="Grove", signals=["msg"],
                        seen_bflds=[1] * 8, have_bflds=[2] * 8, slot_bflds=[3] * 8)
        p.clear_progress()
        self.assertEqual(p.skills, 0)
        self.assertEqual(p.bonuses, {})
        self.assertEqual(p.hints, {}, "hints are {coords: finder} from this run")
        self.assertEqual(p.shared_released, [], "shared singletons must be releasable again")
        self.assertIsNone(p.bingo_last_tp, "journey cards would read a well touched before the reset")
        self.assertEqual(p.signals, [])
        self.assertEqual(p.seen_bflds, 8 * [0])
        self.assertEqual(p.slot_bflds, 8 * [0])


class IdentityAndSeedSurvive(ResetTestCase):
    def test_the_seed_and_who_you_are_are_kept(self):
        p = self.player(seed="Standard,Clues|123\n2|MU|EC/1|Glades",
                        nickname="lapis", seed_name="my seed", dll_version="4.3.0")
        p.clear_progress()
        self.assertTrue(p.seed.startswith("Standard,Clues"), "reset replays the same seed")
        self.assertEqual(p.nickname, "lapis")
        self.assertEqual(p.seed_name, "my seed")
        self.assertEqual(p.dll_version, "4.3.0")

    def test_ap_hints_are_kept(self):
        """The AP room still holds these; forgetting them here would not
        un-hint anything there."""
        p = self.player(ap_hints={"3": {"item": "Bash"}})
        p.clear_progress()
        self.assertEqual(p.ap_hints, {"3": {"item": "Bash"}})


if __name__ == "__main__":
    unittest.main()
