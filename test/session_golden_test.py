"""Route-level golden tests for the transport-neutral session layer (netcode.py).

These pin the (status, body) contract of each session handler — what every
transport adapter (HTTP today, websocket later) must deliver verbatim: status
codes, exact body strings, payload parsing (flag-by-presence query args, form
fields), and the tick fast path serving pure cache. The model-layer wire
format is frozen separately in golden_wire_test.py.

Self-contained like netcode_test: in-memory ndb context, dev PythonCache, no
Flask. Datastore lookups are stubbed at Game.with_id / BingoGameData.with_id
(and get_by_id for the bingo re-fetch paths) in the netcode_test save/restore
style.

Run from the repo root:  python3 -m unittest test.session_golden_test -v
"""
import unittest

import google.auth.credentials
from google.cloud import ndb

import models
import netcode
import util
from cache import Cache
from enums import MultiplayerGameType
from models import Game, BingoGameData, Player


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


class FakeGame(object):
    """Stands in for a Game entity behind Game.with_id: records the calls the
    session layer makes and returns canned results."""

    def __init__(self, mode=MultiplayerGameType.SHARED, players=None):
        self.mode = mode
        self.is_race = False
        self.found_args = None
        self.found_status = 200
        self.released_pid = None
        self.sanity_checks = 0
        self._players = players or {}

    def player(self, pid, *a, **k):
        return self._players[pid]

    def found_pickup(self, *args):
        self.found_args = args
        return self.found_status

    def mw_release(self, pid):
        self.released_pid = pid
        return 3

    def sanity_check(self):
        self.sanity_checks += 1
        return False


class SessionTestCase(NdbTestCase):
    """Stubs Game.with_id per-test; self.game is what it returns (None = 412)."""

    def setUp(self):
        super(SessionTestCase, self).setUp()
        self._with_id = Game.__dict__["with_id"]
        self.game = None
        Game.with_id = staticmethod(lambda gid: self.game)

    def tearDown(self):
        Game.with_id = self._with_id
        super(SessionTestCase, self).tearDown()


class TestFoundPickup(SessionTestCase):
    def test_no_game_is_412(self):
        self.assertEqual(netcode.found_pickup(1201, 1, "1", "SK", "0", {}), (412, "412"))

    def test_bad_pickup_is_406(self):
        self.game = FakeGame()
        self.assertEqual(netcode.found_pickup(1202, 1, "1", "XX", "nope", {}), (406, "406"))

    def test_args_pass_through_and_status_echoes(self):
        self.game = FakeGame()
        self.game.found_status = 410
        payload = {"zone": "Glades", "remove": "", "s3": "7"}
        status, body = netcode.found_pickup(1203, 1, "1", "SK", "0", payload)
        self.assertEqual((status, body), (410, "410"))
        pid, pickup, coords, remove, override, zone, s = self.game.found_args
        self.assertEqual(pid, 1)
        self.assertEqual((pickup.code, pickup.id), ("SK", 0))
        self.assertEqual(coords, 1)
        self.assertTrue(remove)      # flag by key presence, value ignored
        self.assertFalse(override)   # absent key
        self.assertEqual(zone, "Glades")
        self.assertEqual(s, [0, 0, 0, 7, 0, 0, 0, 0])

    def test_race_mode_busts_items_cache(self):
        self.game = FakeGame()
        self.game.is_race = True
        Cache.set_items(1204, 1, ({"a": 1}, {}))
        netcode.found_pickup(1204, 1, "1", "EX", "15", {})
        self.assertEqual(Cache.get_items(1204, 1), ({}, {}))

    def test_prog_pickup_busts_items_cache(self):
        self.game = FakeGame()
        Cache.set_items(1205, 1, ({"a": 1}, {}))
        netcode.found_pickup(1205, 1, "1", "SK", "0", {})
        self.assertEqual(Cache.get_items(1205, 1), ({}, {}))


class TestTick(SessionTestCase):
    def _payload(self, **kw):
        d = {"x": "10", "y": "-20"}
        for i in range(8):
            d["seen_%s" % i] = "0"
            d["have_%s" % i] = "0"
        d.update(kw)
        return d

    def test_no_game_is_412(self):
        self.assertEqual(netcode.tick(1211, 1, self._payload()), (412, "412"))

    def test_fast_path_serves_cache_without_datastore(self):
        Game.with_id = staticmethod(lambda gid: self.fail("fast path hit the datastore"))
        payload = self._payload()
        Cache.set_seen_checksum((1212, 1), util.bfield_checksum(payload["seen_%s" % i] for i in range(8)))
        Cache.set_output((1212, 1), "0,0,0,,")
        self.assertEqual(netcode.tick(1212, 1, payload), (200, "0,0,0,,"))
        # pos is stored as posted (strings) — display consumers parse it
        self.assertEqual(Cache.get_pos(1212), {1: ("10", "-20")})

    def test_checksum_miss_returns_fresh_output(self):
        p = make_player(1213, 1, skills=1793)
        self.game = FakeGame(players={1: p})
        Cache.set_seen_checksum((1213, 1), 999999)  # stale: forces the slow path
        status, body = netcode.tick(1213, 1, self._payload())
        self.assertEqual(status, 200)
        self.assertEqual(body, "1793,0,0,,")
        # the slow path re-arms the fast path for the next identical tick
        self.assertEqual(Cache.get_output((1213, 1)), body)


class TestGameComplete(SessionTestCase):
    def test_no_game_is_412(self):
        self.assertEqual(netcode.game_complete(1221, 1), (412, "412"))

    def test_normal_mode_is_ok_without_release(self):
        self.game = FakeGame()
        self.assertEqual(netcode.game_complete(1222, 1), (200, "ok"))
        self.assertIsNone(self.game.released_pid)

    def test_multiworld_releases_finisher_world(self):
        self.game = FakeGame(mode=MultiplayerGameType.MULTIWORLD)
        self.assertEqual(netcode.game_complete(1223, 2), (200, "ok"))
        self.assertEqual(self.game.released_pid, 2)


class TestSignalCallback(SessionTestCase):
    def test_no_game_is_412(self):
        self.assertEqual(netcode.signal_callback(1231, 1, "win:gg"), (412, "412"))

    def test_confirms_signal(self):
        p = make_player(1232, 1, signals=["win:gg", "msg:hi"])
        self.game = FakeGame(players={1: p})
        self.assertEqual(netcode.signal_callback(1232, 1, "win:gg"), (200, "cleared"))
        self.assertEqual(p.signals, ["msg:hi"])


class TestConnect(SessionTestCase):
    def test_no_game_is_still_ok(self):
        self.assertEqual(netcode.connect(1241, 1, {}), (200, "ok"))

    def test_stale_version_nags_once(self):
        p = make_player(1242, 1)
        self.game = FakeGame(players={1: p})
        self.assertEqual(netcode.connect(1242, 1, {"version": "0.0.1"}), (200, "ok"))
        self.assertEqual(len(p.signals), 1)
        self.assertIn("dll out of date", p.signals[0])
        self.assertFalse(p.can_nag)
        self.assertEqual(self.game.sanity_checks, 1)

    def test_current_version_does_not_nag(self):
        p = make_player(1243, 1)
        self.game = FakeGame(players={1: p})
        netcode.connect(1243, 1, {"version": "%s.%s.%s" % tuple(util.VER)})
        self.assertEqual(p.signals, [])
        self.assertTrue(p.can_nag)

    def test_wrong_game_seed_warns(self):
        p = make_player(1244, 1, can_nag=False)
        self.game = FakeGame(players={1: p})
        netcode.connect(1244, 1, {"seed": "Sync999.1|stuff,line2"})
        self.assertEqual(len(p.signals), 1)
        self.assertIn("belongs to game 999", p.signals[0])

    def test_wrong_player_seed_warns_only_in_multiworld(self):
        p = make_player(1245, 1, can_nag=False)
        self.game = FakeGame(players={1: p})
        netcode.connect(1245, 1, {"seed": "Sync1245.2|stuff,line2"})
        self.assertEqual(p.signals, [])  # shared teammates share one .dat: fine
        self.game.mode = MultiplayerGameType.MULTIWORLD
        netcode.connect(1245, 1, {"seed": "Sync1245.2|stuff,line2"})
        self.assertEqual(len(p.signals), 1)
        self.assertIn("Player 2's seed", p.signals[0])

    def test_matching_seed_is_silent(self):
        p = make_player(1246, 1, can_nag=False)
        self.game = FakeGame(mode=MultiplayerGameType.MULTIWORLD, players={1: p})
        netcode.connect(1246, 1, {"seed": "Sync1246.1|stuff,line2"})
        self.assertEqual(p.signals, [])


class FakeBingo(object):
    def __init__(self, pids=(1, 2), fail_times=0):
        self._pids = list(pids)
        self.event_log = []
        self.updates = []
        self.fail_times = fail_times
        self._board_json = None

    def player_nums(self):
        return self._pids

    def _update(self, bingo_data, player_id, game_id):
        if self.fail_times > 0:
            self.fail_times -= 1
            raise RuntimeError("contention!")
        self.updates.append((bingo_data, int(player_id), int(game_id)))
        self._board_json = {"updated_by": int(player_id)}

    update = _update
    update_v2 = _update


class TestBingoUpdate(NdbTestCase):
    def setUp(self):
        super(TestBingoUpdate, self).setUp()
        self._with_id = BingoGameData.__dict__["with_id"]
        self._v2 = netcode.BINGO_V2
        self.bingo = None
        self.refetched = None  # what get_by_id(use_cache=False) hands back
        BingoGameData.with_id = staticmethod(lambda gid: self.bingo)
        BingoGameData.get_by_id = staticmethod(lambda gid, use_cache=True: self.refetched)

    def tearDown(self):
        BingoGameData.with_id = self._with_id
        del BingoGameData.get_by_id  # restore the inherited ndb classmethod
        netcode.BINGO_V2 = self._v2
        super(TestBingoUpdate, self).tearDown()

    def test_no_game_is_404_with_exact_body(self):
        self.assertEqual(netcode.bingo_update(1251, 1, {}),
                         (404, "Bingo game 1251 not found"))

    def test_unknown_player_is_412_with_roster(self):
        self.bingo = FakeBingo(pids=(1, 2))
        self.assertEqual(netcode.bingo_update(1252, 9, {}),
                         (412, "player not in game! [1, 2]"))

    def test_legacy_update_parses_json_and_publishes(self):
        netcode.BINGO_V2 = False
        self.bingo = FakeBingo()
        status, body = netcode.bingo_update(1253, 1, {"bingoData": '{"sq": true}'})
        self.assertEqual((status, body), (200, "200"))
        self.assertEqual(self.bingo.updates, [({"sq": True}, 1, 1253)])
        self.assertEqual(Cache.get_board(1253), {"updated_by": 1})

    def test_legacy_retry_refetches_then_succeeds(self):
        netcode.BINGO_V2 = False
        self.bingo = FakeBingo(fail_times=1)
        self.refetched = FakeBingo()
        status, body = netcode.bingo_update(1254, 2, {"bingoData": '{"sq": 1}'})
        self.assertEqual((status, body), (200, "200"))
        self.assertEqual(self.bingo.updates, [])         # first attempt failed
        self.assertEqual(len(self.refetched.updates), 1)  # retry used the fresh read
        self.assertEqual(Cache.get_board(1254), {"updated_by": 2})

    def test_legacy_double_failure_is_503(self):
        netcode.BINGO_V2 = False
        self.bingo = FakeBingo(fail_times=1)
        self.refetched = FakeBingo(fail_times=1)
        self.assertEqual(netcode.bingo_update(1255, 1, {"bingoData": '{"sq": 1}'}),
                         (503, "503"))

    def test_v2_updates_fresh_read_under_lock(self):
        netcode.BINGO_V2 = True
        self.bingo = FakeBingo()
        self.refetched = FakeBingo()
        status, body = netcode.bingo_update(1256, 1, {"bingoData": '{"sq": 1}'})
        self.assertEqual((status, body), (200, "200"))
        self.assertEqual(self.bingo.updates, [])          # stale pre-check copy untouched
        self.assertEqual(len(self.refetched.updates), 1)  # locked fresh read did the work
        self.assertEqual(Cache.get_board(1256), {"updated_by": 1})

    def test_v2_failure_is_503(self):
        netcode.BINGO_V2 = True
        self.bingo = FakeBingo()
        self.refetched = FakeBingo(fail_times=1)
        self.assertEqual(netcode.bingo_update(1257, 1, {"bingoData": '{"sq": 1}'}),
                         (503, "503"))


if __name__ == "__main__":
    unittest.main()
