"""Golden tests for the netcode wire protocol (2026-07).

These freeze the contract that the shipped C# client (4.1.7) depends on, so
that the session-layer extraction, websocket work, and multiworld changes can
be checked against it. The client's reader is RandomizerSyncManager.CheckPickups
in OriDERandomizer; it splits the tick response body on "," and indexes:

    [0] skills bitfield   (int)
    [1] events bitfield   (int)
    [2] teleporters bitfield (int)
    [3] upgrades: ";"-joined "{id}x{count}" (warps encoded "{x}_{y}x1")
    [4] hints: ";"-joined "{loc}:{finder}"  (client currently ignores)
    [5] signals: "|"-joined, PRESENT ONLY IF NONEMPTY (client gates on
        array.Length > 5, then confirms each via GET /callback/<signal>)

Contract rules these tests pin down:
  * Field order and indices are load-bearing. New fields may only be APPENDED
    (index 6+), and only in game modes that require a new client anyway
    (e.g. multiworld slot bitfields) -- old clients never see them.
  * No field content may contain "," -- it would shift/truncate later fields
    in every deployed client. The warp-upgrade encoding exists precisely to
    strip the commas out of warp ids. This also constrains signal text.
  * The tick fast path serves Cache.get_output verbatim when the posted seen
    checksum matches; output() and the checksum must therefore stay in sync,
    and anything that changes a player's pending output (signal_send/conf)
    must bust the checksum. (The July 2026 dropped-win-signal bug.)

Self-contained like netcode_test: in-memory ndb context, dev PythonCache,
no Flask. Route-level golden tests (status codes, content types) should be
added when the handlers are extracted into the transport-neutral session
layer, which unhooks them from main.py's import-time OIDC/logging setup.

Run from the repo root:  python3 -m unittest test.golden_wire_test -v
"""
import unittest

import google.auth.credentials
from google.cloud import ndb

import cache as cache_mod
import util
from cache import Cache
from models import Player


class NdbTestCase(unittest.TestCase):
    """Provides an ndb context so entities can be constructed locally."""

    @classmethod
    def setUpClass(cls):
        creds = google.auth.credentials.AnonymousCredentials()
        cls.ndb_client = ndb.Client(project="unit-test", credentials=creds)

    def setUp(self):
        self._ctx = self.ndb_client.context()
        self._ctx.__enter__()

    def tearDown(self):
        self._ctx.__exit__(None, None, None)


def make_player(gid, pid, **kw):
    fields = dict(skills=0, events=0, teleporters=0, bonuses={}, hints={})
    fields.update(kw)
    p = Player(id="%s.%s" % (gid, pid), **fields)
    p.put_count = 0

    def fake_put(*a, **k):
        p.put_count += 1
    p.put = fake_put
    return p


class TestPlayerOutputFormat(NdbTestCase):
    def test_empty_player_is_five_empty_tailed_fields(self):
        p = make_player(901, 1)
        out = p.output()
        self.assertEqual(out, "0,0,0,,")
        self.assertEqual(len(out.split(",")), 5)  # no signals -> exactly 5

    def test_field_order_and_indices(self):
        p = make_player(902, 1, skills=1793, events=21, teleporters=515,
                        bonuses={"9": 1, "17": 2}, hints={"5480952": 2})
        fields = p.output().split(",")
        self.assertEqual(fields[0], "1793")
        self.assertEqual(fields[1], "21")
        self.assertEqual(fields[2], "515")
        self.assertEqual(fields[3], "9x1;17x2")
        self.assertEqual(fields[4], "5480952:2")

    def test_warp_bonus_encoding_strips_commas(self):
        # server-side warp bonus ids look like "Warp to Swamp Swim,790,-195";
        # the wire form must be "790_-195x1" (matches client WarpDatas keys)
        p = make_player(903, 1, bonuses={"Warp to Swamp Swim,790,-195": 1})
        fields = p.output().split(",")
        self.assertEqual(fields[3], "790_-195x1")
        self.assertNotIn(",", fields[3])

    def test_signals_are_sixth_field_only_when_present(self):
        p = make_player(904, 1, signals=["msg:hi there", "win:Finished in 1st place!"])
        fields = p.output().split(",")
        self.assertEqual(len(fields), 6)  # client gate: array.Length > 5
        self.assertEqual(fields[5], "msg:hi there|win:Finished in 1st place!")

    def test_signal_text_must_not_contain_commas(self):
        # a comma inside signal text would be split by every deployed client,
        # truncating the signal and orphaning the remainder. Nothing enforces
        # this server-side today; this test documents the constraint for the
        # signal *producers* (win/msg/pickup senders).
        p = make_player(905, 1, signals=["msg:no, really"])
        fields = p.output().split(",")
        self.assertNotEqual(fields[5], "msg:no, really")  # the hazard, frozen

    def test_output_populates_the_fast_path_cache(self):
        p = make_player(906, 1, skills=3)
        out = p.output()
        self.assertEqual(Cache.get_output((906, 1)), out)


class TestSignalFlow(NdbTestCase):
    """signal_send/signal_conf must keep the tick fast path honest: any change
    to pending signals busts the seen checksum, or an idle player (unchanged
    bitfields) is served stale cached output forever and never sees the signal
    -- the July 2026 dropped-win-signal bug, frozen here."""

    def _armed_player(self, gid):
        p = make_player(gid, 1)
        Cache.set_seen_checksum((gid, 1), 12345)
        Cache.set_output((gid, 1), "0,0,0,,")
        return p

    def test_send_appends_dedups_and_busts_checksum(self):
        p = self._armed_player(911)
        p.signal_send("win:gg")
        self.assertEqual(p.signals, ["win:gg"])
        self.assertIsNone(Cache.get_seen_checksum((911, 1)))
        p.signal_send("win:gg")  # exact duplicate: no-op
        self.assertEqual(p.signals, ["win:gg"])

    def test_send_busts_checksum_even_when_none_armed(self):
        # regression guard: dev PythonCache.clear_seen_checksum used a bare
        # del and raised KeyError when no checksum existed (prod memcached
        # delete tolerates missing keys; dev must match)
        p = make_player(912, 1)
        p.signal_send("win:gg")  # must not raise
        self.assertEqual(p.signals, ["win:gg"])

    def test_conf_exact_match_removes_and_busts_checksum(self):
        p = self._armed_player(913)
        p.signals = ["win:gg", "msg:hi"]
        p.signal_conf("win:gg")
        self.assertEqual(p.signals, ["msg:hi"])
        self.assertIsNone(Cache.get_seen_checksum((913, 1)))

    def test_conf_unmatched_msg_removes_first_msg(self):
        # "spam protection": an inexact msg: callback removes the first msg:
        # signal found rather than nothing
        p = self._armed_player(914)
        p.signals = ["msg:one", "msg:two"]
        p.signal_conf("msg:zzz")
        self.assertEqual(p.signals, ["msg:two"])

    def test_conf_unmatched_msg_with_mixed_queue_current_behavior(self):
        # KNOWN QUIRK, frozen deliberately: the fallback loop removes list
        # elements while iterating, so with a non-msg signal queued first, an
        # unmatched msg: callback eats the *non-msg* signal and leaves the msg.
        # If this test starts failing because the behavior was fixed to only
        # remove msg: signals, that is an improvement -- update the test.
        p = self._armed_player(915)
        p.signals = ["win:gg", "msg:one"]
        p.signal_conf("msg:zzz")
        self.assertEqual(p.signals, ["msg:one"])

    def test_conf_unmatched_nonmsg_removes_nothing(self):
        p = self._armed_player(916)
        p.signals = ["win:gg"]
        p.signal_conf("pickup:SK|0")
        self.assertEqual(p.signals, ["win:gg"])


class TestBitfieldUpdates(NdbTestCase):
    """Tick input handling: the posted seen_i/have_i fields update the entity,
    the have cache (merge semantics), and arm the fast-path checksum."""

    @staticmethod
    def _post(seen, have):
        d = {"seen_%s" % i: str(v) for i, v in enumerate(seen)}
        d.update({"have_%s" % i: str(v) for i, v in enumerate(have)})
        return d

    def test_update_writes_entity_cache_and_checksum(self):
        p = make_player(921, 1)
        seen, have = [1] + [0] * 7, [1] + [0] * 7
        post = self._post(seen, have)
        p.bitfield_updates(post, 921)
        self.assertEqual(p.seen_bflds, seen)
        self.assertEqual(p.have_bflds, have)
        self.assertEqual(p.put_count, 1)
        # have cache gets only this player's entry (merge semantics)
        self.assertEqual(Cache.get_have(921)[1], p.have_coords())
        # checksum armed with exactly what was posted (string forms)
        expected = util.bfield_checksum(post.get("seen_%s" % i, 0) for i in range(8))
        self.assertEqual(Cache.get_seen_checksum((921, 1)), expected)

    def test_unchanged_post_arms_checksum_without_put(self):
        p = make_player(922, 1)
        post = self._post([5] * 8, [5] * 8)
        p.bitfield_updates(post, 922)
        self.assertEqual(p.put_count, 1)
        p.bitfield_updates(post, 922)  # identical: no entity write
        self.assertEqual(p.put_count, 1)
        self.assertIsNotNone(Cache.get_seen_checksum((922, 1)))

    def test_coords_carry_spawn_sentinel(self):
        # seen/have coord lists always end with the spawn sentinel coord 2;
        # tracker/reachable consumers rely on it
        p = make_player(923, 1)
        p.bitfield_updates(self._post([0] * 8, [0] * 8), 923)
        self.assertEqual(p.seen_coords(), [2])
        self.assertEqual(p.have_coords(), [2])

    def test_fast_path_pair_is_in_sync_after_standard_sequence(self):
        # the tick POST handler's contract: after bitfield_updates + output(),
        # a repeat of the same post may be served entirely from cache. Both
        # halves of that pair must exist and agree.
        p = make_player(924, 1, skills=7)
        post = self._post([9] * 8, [9] * 8)
        p.bitfield_updates(post, 924)
        out = p.output()
        self.assertEqual(Cache.get_output((924, 1)), out)
        self.assertEqual(Cache.get_seen_checksum((924, 1)),
                         util.bfield_checksum(post.get("seen_%s" % i, 0) for i in range(8)))


class TestDevCacheParity(unittest.TestCase):
    def test_clear_seen_checksum_tolerates_missing_key(self):
        pc = cache_mod.PythonCache()
        pc.clear_seen_checksum((999, 1))  # must not raise (memcached parity)
        pc.set_seen_checksum((999, 1), 1)
        pc.clear_seen_checksum((999, 1))
        self.assertIsNone(pc.get_seen_checksum((999, 1)))

    def test_remove_game_tolerates_missing_keys(self):
        pc = cache_mod.PythonCache()
        pc.set_hist(998, 1, ["h"])
        pc.remove_game(998)  # only some keys exist: must not raise
        self.assertIsNone(pc.get_hist(998))


if __name__ == "__main__":
    unittest.main()
