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
        # mirror the real txn's semantics against the FakeGame's in-memory
        # entity (no datastore here): fresh-read + tick-owned fields only
        self._tick_txn = Player.__dict__["tick_update_txn"]

        def fake_tick_txn(pkey, vers, seen, have):
            _, _, pid = pkey.id().partition(".")
            p = self.game.player(int(pid))
            changed = False
            if vers and p.dll_version != vers:
                p.dll_version = vers
                changed = True
            if p.seen_bflds != seen:
                p.seen_bflds = list(seen)
                changed = True
            if p.have_bflds != have:
                p.have_bflds = list(have)
                changed = True
            if changed:
                p.put()
            return p
        Player.tick_update_txn = staticmethod(fake_tick_txn)

        # same deal for the signal writes, which stopped being plain puts once
        # a stale one was found erasing concurrent grants' slot bitfields
        from models import _conf_signals
        self._conf_txn = Player.__dict__["signal_conf_txn"]
        self._send_txn = Player.__dict__["signal_send_txn"]
        self._connect_txn = Player.__dict__["connect_update_txn"]

        def _fresh(pkey):
            _, _, pid = pkey.id().partition(".")
            return self.game.player(int(pid))

        def fake_conf_txn(pkey, signal):
            p = _fresh(pkey)
            before = list(p.signals)
            _conf_signals(p.signals, signal)
            if p.signals == before:
                return False
            p.put()
            return True

        def fake_send_txn(pkey, signal):
            p = _fresh(pkey)
            if signal in p.signals:
                return False
            p.signals.append(signal)
            p.put()
            return True

        def fake_connect_txn(pkey, vers, nag_signal=None):
            p = _fresh(pkey)
            changed = p.note_version(vers)
            if nag_signal and p.can_nag:
                if nag_signal not in p.signals:
                    p.signals.append(nag_signal)
                p.can_nag = False
                changed = True
            if changed:
                p.put()
            return changed

        Player.signal_conf_txn = staticmethod(fake_conf_txn)
        Player.signal_send_txn = staticmethod(fake_send_txn)
        Player.connect_update_txn = staticmethod(fake_connect_txn)

    def tearDown(self):
        Game.with_id = self._with_id
        Player.tick_update_txn = self._tick_txn
        Player.signal_conf_txn = self._conf_txn
        Player.signal_send_txn = self._send_txn
        Player.connect_update_txn = self._connect_txn
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

    def test_slow_path_records_dll_version(self):
        p = make_player(1214, 1)
        self.game = FakeGame(players={1: p})
        Cache.set_seen_checksum((1214, 1), 999999)
        netcode.tick(1214, 1, self._payload(version="4.1.10"))
        self.assertEqual(p.dll_version, "4.1.10")
        puts = p.put_count
        netcode.tick(1214, 1, self._payload(version="4.1.10"))
        self.assertEqual(p.put_count, puts)  # unchanged version costs no write

    def test_fast_path_never_touches_the_player(self):
        # version tracking must not drag a datastore read onto the 1 Hz tick
        Game.with_id = staticmethod(lambda gid: self.fail("fast path hit the datastore"))
        payload = self._payload(version="4.1.10")
        Cache.set_seen_checksum((1215, 1), util.bfield_checksum(payload["seen_%s" % i] for i in range(8)))
        Cache.set_output((1215, 1), "0,0,0,,")
        self.assertEqual(netcode.tick(1215, 1, payload), (200, "0,0,0,,"))

    def test_slow_path_output_reflects_the_txn_entity(self):
        # 134701: the old plain put of the stale handler copy erased skills
        # granted between the tick's read and its write. The fix renders
        # output from the entity the txn returns (fresh), not the handler's
        # stale read — this pins that plumbing.
        stale = make_player(1216, 1)
        fresh = make_player(1216, 1, skills=1793)
        self.game = FakeGame(players={1: stale})
        real_stub = Player.__dict__["tick_update_txn"]
        Player.tick_update_txn = staticmethod(lambda pkey, vers, seen, have: fresh)
        try:
            Cache.set_seen_checksum((1216, 1), 999999)
            status, body = netcode.tick(1216, 1, self._payload(version="9.9.9"))
        finally:
            Player.tick_update_txn = real_stub
        self.assertEqual((status, body), (200, "1793,0,0,,"))

    def test_checksum_miss_returns_fresh_output(self):
        p = make_player(1213, 1, skills=1793)
        self.game = FakeGame(players={1: p})
        Cache.set_seen_checksum((1213, 1), 999999)  # stale: forces the slow path
        status, body = netcode.tick(1213, 1, self._payload())
        self.assertEqual(status, 200)
        self.assertEqual(body, "1793,0,0,,")
        # the slow path re-arms the fast path for the next identical tick
        self.assertEqual(Cache.get_output((1213, 1)), body)


class TestTickHintRequests(SessionTestCase):
    """Tick field 'aph': the manifest slots a client's own reveals now need.
    It has to be read before the cached fast path returns, and it has to cost
    nothing at all to the games that never send it."""

    def _payload(self, **kw):
        d = {"x": "1", "y": "2"}
        for i in range(8):
            d["seen_%s" % i] = "0"
            d["have_%s" % i] = "0"
        d.update(kw)
        return d

    def setUp(self):
        SessionTestCase.setUp(self)
        self.seen = []
        self.heals = []
        self._flag, self._req = netcode.ARCHIPELAGO, netcode.ap_bridge.request_hints
        self._heal = netcode.ap_bridge.heal
        netcode.ARCHIPELAGO = True
        netcode.ap_bridge.heal = lambda gid, active=False: self.heals.append((gid, active))
        netcode.ap_bridge.request_hints = lambda gid, pid, raw: self.seen.append((gid, pid, raw))

    def tearDown(self):
        netcode.ARCHIPELAGO = self._flag
        netcode.ap_bridge.request_hints = self._req
        netcode.ap_bridge.heal = self._heal
        SessionTestCase.tearDown(self)

    def test_the_tick_heal_is_active(self):
        # ticks are the game activity that wakes an idled bridge; a passive
        # default here would regress to bridges that never resume
        p = make_player(1234, 1)
        self.game = FakeGame(players={1: p})
        netcode.tick(1234, 1, self._payload())
        self.assertEqual(self.heals, [(1234, True)])

    def test_the_request_survives_the_cached_fast_path(self):
        # the fast path serves a cached body and never looks at a Player, so
        # a hint request read after it would be dropped on every quiet tick
        Game.with_id = staticmethod(lambda gid: self.fail("fast path hit the datastore"))
        payload = self._payload(aph="5.6")
        Cache.set_seen_checksum((1231, 1), util.bfield_checksum(payload["seen_%s" % i] for i in range(8)))
        Cache.set_output((1231, 1), "0,0,0,,")
        self.assertEqual(netcode.tick(1231, 1, payload), (200, "0,0,0,,"))
        self.assertEqual(self.seen, [(1231, 1, "5.6")])

    def test_a_tick_without_the_field_still_calls_through_with_nothing(self):
        p = make_player(1232, 1)
        self.game = FakeGame(players={1: p})
        netcode.tick(1232, 1, self._payload())
        self.assertEqual(self.seen, [(1232, 1, None)])

    def test_the_flag_off_never_looks(self):
        netcode.ARCHIPELAGO = False
        p = make_player(1233, 1)
        self.game = FakeGame(players={1: p})
        netcode.tick(1233, 1, self._payload(aph="5"))
        self.assertEqual(self.seen, [])


class TestTickDeathCounters(SessionTestCase):
    """Tick field 'dl': the death counters a DeathLink seed reports. Same
    contract as 'aph' -- read ahead of the cached fast path, invisible to
    every seed that doesn't send it, and never echoed back."""

    def _payload(self, **kw):
        d = {"x": "1", "y": "2"}
        for i in range(8):
            d["seen_%s" % i] = "0"
            d["have_%s" % i] = "0"
        d.update(kw)
        return d

    def setUp(self):
        SessionTestCase.setUp(self)
        self.seen = []
        self._flag = netcode.ARCHIPELAGO
        self._note, self._req = netcode.ap_bridge.note_deaths, netcode.ap_bridge.request_hints
        self._heal = netcode.ap_bridge.heal
        netcode.ARCHIPELAGO = True
        netcode.ap_bridge.heal = lambda gid, active=False: None
        netcode.ap_bridge.request_hints = lambda gid, pid, raw: None
        netcode.ap_bridge.note_deaths = lambda gid, pid, raw: self.seen.append((gid, pid, raw))

    def tearDown(self):
        netcode.ARCHIPELAGO = self._flag
        netcode.ap_bridge.note_deaths = self._note
        netcode.ap_bridge.request_hints = self._req
        netcode.ap_bridge.heal = self._heal
        SessionTestCase.tearDown(self)

    def test_the_counters_survive_the_cached_fast_path(self):
        # an idle player's tick never reaches a Player, and a death is
        # exactly the thing that happens while standing still
        Game.with_id = staticmethod(lambda gid: self.fail("fast path hit the datastore"))
        payload = self._payload(dl="12.3")
        Cache.set_seen_checksum((1241, 1), util.bfield_checksum(payload["seen_%s" % i] for i in range(8)))
        Cache.set_output((1241, 1), "0,0,0,,")
        self.assertEqual(netcode.tick(1241, 1, payload), (200, "0,0,0,,"))
        self.assertEqual(self.seen, [(1241, 1, "12.3")])

    def test_a_seed_without_the_option_sends_nothing_to_read(self):
        p = make_player(1242, 1)
        self.game = FakeGame(players={1: p})
        netcode.tick(1242, 1, self._payload())
        self.assertEqual(self.seen, [(1242, 1, None)])

    def test_the_field_does_not_change_the_tick_body(self):
        p = make_player(1243, 1)
        self.game = FakeGame(players={1: p})
        without = netcode.tick(1243, 1, self._payload())
        Cache.set_seen_checksum((1243, 1), 999999)
        with_field = netcode.tick(1243, 1, self._payload(dl="4.0"))
        self.assertEqual(with_field, without)

    def test_the_flag_off_never_looks(self):
        netcode.ARCHIPELAGO = False
        p = make_player(1244, 1)
        self.game = FakeGame(players={1: p})
        netcode.tick(1244, 1, self._payload(dl="4.0"))
        self.assertEqual(self.seen, [])


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
        self.assertEqual(p.signals, [])  # shared teammates share one .bfr: fine
        self.game.mode = MultiplayerGameType.MULTIWORLD
        netcode.connect(1245, 1, {"seed": "Sync1245.2|stuff,line2"})
        self.assertEqual(len(p.signals), 1)
        self.assertIn("Player 2's seed", p.signals[0])

    def test_matching_seed_is_silent(self):
        p = make_player(1246, 1, can_nag=False)
        self.game = FakeGame(mode=MultiplayerGameType.MULTIWORLD, players={1: p})
        netcode.connect(1246, 1, {"seed": "Sync1246.1|stuff,line2"})
        self.assertEqual(p.signals, [])


class FakeVersionedPlayer(object):
    """pid + dll_version, all the connect gate reads."""

    def __init__(self, pid, dll_version):
        self._pid, self.dll_version = pid, dll_version

    def pid(self):
        return self._pid


class FakeApGame(object):
    """A Game whose params carry (or lack) the ap_mode marker."""

    def __init__(self, ap_mode=True, players=2, has_params=True, roster=None):
        class _Params(object):
            pass

        class _ParamsKey(object):
            def __init__(self, p):
                self._p = p

            def get(self):
                return self._p
        self.params = None
        self.roster = roster or []
        if has_params:
            p = _Params()
            p.ap_mode = ap_mode
            p.players = players
            p.player_names = []
            self.params = _ParamsKey(p)

    def visible_players(self):
        return list(self.roster)

    def fetch_params(self):
        return self.params.get() if self.params else None


class TestApRoutes(SessionTestCase):
    """ap/connect | ap/status | ap/disconnect: ARCHIPELAGO gating, AP-mode
    validation, and APLink storage semantics. APLink datastore ops are
    stubbed at get_by_id/put (in-memory store), netcode_test style."""

    def setUp(self):
        super(TestApRoutes, self).setUp()
        from ap_models import APLink
        self._flag = netcode.ARCHIPELAGO
        netcode.ARCHIPELAGO = True
        self.links = {}

        def fake_put(link, *a, **k):
            self.links[link.key.id()] = link
            return link.key
        APLink.put = fake_put
        APLink.get_by_id = staticmethod(lambda gid: self.links.get(int(gid)))
        # report cache off: fake_put fires no post-put hook, so busts would
        # never come. This class tests storage semantics; TestApStatusCache
        # owns the cache behavior.
        self._rep = (Cache.get_aplink_report, Cache.set_aplink_report)
        Cache.get_aplink_report = lambda gid: None
        Cache.set_aplink_report = lambda gid, text, negative=False: None

    def tearDown(self):
        from ap_models import APLink
        netcode.ARCHIPELAGO = self._flag
        del APLink.put          # restore the inherited ndb methods
        del APLink.get_by_id
        Cache.get_aplink_report, Cache.set_aplink_report = self._rep
        super(TestApRoutes, self).tearDown()

    def test_flag_off_is_404_everywhere(self):
        netcode.ARCHIPELAGO = False
        self.game = FakeApGame()
        self.assertEqual(netcode.ap_connect(1301, {"host": "h", "port": "38281"})[0], 404)
        self.assertEqual(netcode.ap_status(1301)[0], 404)
        self.assertEqual(netcode.ap_disconnect(1301)[0], 404)
        self.assertEqual(self.links, {})

    def test_connect_no_game_is_404(self):
        self.assertEqual(netcode.ap_connect(1302, {"host": "h", "port": "1"}),
                         (404, "Game 1302 not found"))

    def test_connect_non_ap_game_is_409(self):
        self.game = FakeApGame(ap_mode=False)
        status, body = netcode.ap_connect(1303, {"host": "h", "port": "1"})
        self.assertEqual((status, body), (409, "Game 1303 is not an Archipelago game"))
        self.game = FakeApGame(has_params=False)
        self.assertEqual(netcode.ap_connect(1303, {"host": "h", "port": "1"})[0], 409)
        self.assertEqual(self.links, {})

    def test_connect_validates_host_and_port(self):
        self.game = FakeApGame()
        self.assertEqual(netcode.ap_connect(1304, {"port": "38281"})[0], 400)
        self.assertEqual(netcode.ap_connect(1304, {"host": "ap.example"})[0], 400)
        self.assertEqual(netcode.ap_connect(1304, {"host": "ap.example", "port": "nope"})[0], 400)
        self.assertEqual(netcode.ap_connect(1304, {"host": "ap.example", "port": "0"})[0], 400)
        self.assertEqual(self.links, {})

    def test_connect_stores_link_with_world_defaults(self):
        self.game = FakeApGame(players=3)
        self.assertEqual(netcode.ap_connect(1305, {"host": "ap.example", "port": "38281",
                                                   "password": "hunter2"}), (200, "ok"))
        link = self.links[1305]
        self.assertEqual(link.host, "ap.example")
        self.assertEqual(link.port, 38281)
        self.assertEqual(link.password, "hunter2")
        self.assertEqual(link.slot_names, ["Ori1", "Ori2", "Ori3"])
        self.assertEqual(link.recv_index, [0, 0, 0])
        self.assertTrue(link.enabled)
        self.assertEqual(link.status, "pending")

    def test_reconnect_keeps_recv_progress(self):
        self.game = FakeApGame()
        netcode.ap_connect(1306, {"host": "old", "port": "1"})
        self.links[1306].recv_index = [5, 2]
        self.links[1306].enabled = False
        netcode.ap_connect(1306, {"host": "new", "port": "2"})
        link = self.links[1306]
        self.assertEqual(link.host, "new")
        self.assertEqual(link.recv_index, [5, 2])  # applied progress is durable
        self.assertTrue(link.enabled)
        self.assertIsNone(link.password)  # no password posted: cleared

    def test_connect_refuses_stale_dlls(self):
        # an old dll against the current bridge dupes self-items, so a
        # known-old version closes the room
        self.game = FakeApGame(roster=[FakeVersionedPlayer(1, "4.2.10"),
                                       FakeVersionedPlayer(2, "4.2.12")])
        status, body = netcode.ap_connect(1310, {"host": "ap.example", "port": "38281"})
        self.assertEqual(status, 409)
        self.assertIn("P1 is on 4.2.10", body)
        self.assertNotIn("P2", body)
        self.assertEqual(self.links, {})

    def test_connect_allows_current_and_unlaunched_dlls(self):
        # no version yet = hasn't launched; refusing would deadlock the flow
        self.game = FakeApGame(roster=[FakeVersionedPlayer(1, "4.2.12"),
                                       FakeVersionedPlayer(2, None),
                                       FakeVersionedPlayer(3, "4.3")])
        self.assertEqual(netcode.ap_connect(1311, {"host": "ap.example", "port": "38281"})[0], 200)

    def test_connect_force_overrides_the_version_gate(self):
        self.game = FakeApGame(roster=[FakeVersionedPlayer(1, "4.2.8")])
        self.assertEqual(netcode.ap_connect(1312, {"host": "ap.example", "port": "38281",
                                                   "force": "1"})[0], 200)

    def test_version_at_least_rows(self):
        from util import version_at_least
        floor = [4, 2, 12]
        for version, expect in [("4.2.12", True), ("4.2.12.1", True), ("4.3", True),
                                ("5.0", True), ("4.2.11", False), ("4.2", False),
                                ("", False), (None, False), ("pineapple", False)]:
            self.assertEqual(version_at_least(version, floor), expect,
                             "%r should be %s" % (version, expect))

    def test_connect_rejects_addresses_only_the_user_can_reach(self):
        self.game = FakeApGame()
        for host in ("localhost", "127.0.0.1", "192.168.1.50", "10.0.0.4", "::1"):
            status, body = netcode.ap_connect(1309, {"host": host, "port": "38281"})
            self.assertEqual(status, 400, "%s should be rejected" % host)
            self.assertIn("archipelago.gg", body)
        self.assertEqual(self.links, {})
        self.assertEqual(netcode.ap_connect(1309, {"host": "archipelago.gg",
                                                   "port": "38281"})[0], 200)

    def test_retrying_same_room_keeps_the_last_error_visible(self):
        self.game = FakeApGame()
        netcode.ap_connect(1310, {"host": "ap.example", "port": "38281"})
        self.links[1310].status = "reconnecting"
        self.links[1310].last_error = "world 1: can't reach ap.example:38281"
        netcode.ap_connect(1310, {"host": "ap.example", "port": "38281"})
        self.assertEqual(self.links[1310].status, "pending")
        self.assertIn("can't reach", self.links[1310].last_error)
        # a different room starts clean
        netcode.ap_connect(1310, {"host": "other.example", "port": "38281"})
        self.assertIsNone(self.links[1310].last_error)

    def test_status_serves_link_json(self):
        import json
        self.game = FakeApGame()
        netcode.ap_connect(1307, {"host": "ap.example", "port": "38281"})
        status, body = netcode.ap_status(1307)
        self.assertEqual(status, 200)
        rep = json.loads(body)
        self.assertEqual(rep["status"], "pending")
        self.assertEqual(rep["host"], "ap.example")
        self.assertEqual(rep["slots"], ["Ori1", "Ori2"])
        self.assertEqual(rep["recv_index"], [0, 0])
        self.assertTrue(rep["enabled"])

    def test_status_without_link_is_404(self):
        self.assertEqual(netcode.ap_status(1308),
                         (404, "No Archipelago link for game 1308"))

    def test_disconnect_disables_and_keeps_link(self):
        self.game = FakeApGame()
        netcode.ap_connect(1309, {"host": "ap.example", "port": "38281"})
        self.assertEqual(netcode.ap_disconnect(1309), (200, "ok"))
        link = self.links[1309]
        self.assertFalse(link.enabled)
        self.assertEqual(link.status, "disconnected")
        self.assertEqual(link.recv_index, [0, 0])  # progress survives disconnect

    def test_disconnect_without_link_is_404(self):
        self.assertEqual(netcode.ap_disconnect(1310)[0], 404)


class TestApStatusCache(SessionTestCase):
    """ap/status memcache behavior: hit path, negative sentinel, hook bust.
    Gids here (1391-1393) are unique to this class: the test cache is
    process-wide and nothing else may see these entries."""

    GIDS = (1391, 1392, 1393)

    def setUp(self):
        super(TestApStatusCache, self).setUp()
        from ap_models import APLink
        self._flag = netcode.ARCHIPELAGO
        netcode.ARCHIPELAGO = True
        self.links = {}

        def fake_put(link, *a, **k):
            self.links[link.key.id()] = link
            return link.key
        APLink.put = fake_put
        APLink.get_by_id = staticmethod(lambda gid: self.links.get(int(gid)))
        self.heals = []
        self._heal = netcode.ap_bridge.heal
        netcode.ap_bridge.heal = lambda gid, active=False: self.heals.append((gid, active))
        for gid in self.GIDS:
            Cache.clear_aplink_report(gid)

    def tearDown(self):
        from ap_models import APLink
        netcode.ARCHIPELAGO = self._flag
        del APLink.put
        del APLink.get_by_id
        netcode.ap_bridge.heal = self._heal
        for gid in self.GIDS:
            Cache.clear_aplink_report(gid)
        super(TestApStatusCache, self).tearDown()

    def test_second_status_is_served_from_cache(self):
        self.game = FakeApGame()
        netcode.ap_connect(1391, {"host": "ap.example", "port": "38281"})
        _, first = netcode.ap_status(1391)
        self.links[1391].status = "connected"  # direct mutation: no put, no bust
        _, second = netcode.ap_status(1391)
        self.assertEqual(second, first)         # stale by design until a bust
        Cache.clear_aplink_report(1391)
        _, third = netcode.ap_status(1391)
        self.assertIn('"connected"', third)

    def test_missing_link_is_negative_cached(self):
        from ap_models import APLink
        calls = []
        real = APLink.get_by_id
        APLink.get_by_id = staticmethod(lambda gid: calls.append(gid) or None)
        try:
            self.assertEqual(netcode.ap_status(1392)[0], 404)
            self.assertEqual(netcode.ap_status(1392)[0], 404)
            self.assertEqual(len(calls), 1)  # the second 404 never hit the store
        finally:
            APLink.get_by_id = staticmethod(real)
        # a bust (what the post-put hook does when connect puts) clears the "-"
        Cache.clear_aplink_report(1392)
        self.game = FakeApGame()
        netcode.ap_connect(1392, {"host": "ap.example", "port": "38281"})
        self.assertEqual(netcode.ap_status(1392)[0], 200)

    def test_post_put_hook_busts_report(self):
        from ap_models import APLink
        Cache.set_aplink_report(1393, "stale")
        APLink(id=1393)._post_put_hook(None)
        self.assertIsNone(Cache.get_aplink_report(1393))

    def test_status_heals_are_passive(self):
        # a poll must never wake an idled bridge -- that was the zombie
        # immortality mechanism
        self.game = FakeApGame()
        netcode.ap_connect(1393, {"host": "ap.example", "port": "38281"})
        self.heals[:] = []
        netcode.ap_status(1393)   # cold path
        netcode.ap_status(1393)   # cached path
        self.assertEqual(self.heals, [(1393, False), (1393, False)])


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
        self._signal_pids = [(int(game_id), int(player_id))]

    update = _update


class TestBingoUpdate(NdbTestCase):
    def setUp(self):
        super(TestBingoUpdate, self).setUp()
        self._with_id = BingoGameData.__dict__["with_id"]
        self.bingo = None
        self.refetched = None  # what get_by_id(use_cache=False) hands back
        BingoGameData.with_id = staticmethod(lambda gid: self.bingo)
        BingoGameData.get_by_id = staticmethod(lambda gid, use_cache=True: self.refetched)

    def tearDown(self):
        BingoGameData.with_id = self._with_id
        del BingoGameData.get_by_id  # restore the inherited ndb classmethod
        super(TestBingoUpdate, self).tearDown()

    def test_no_game_is_404_with_exact_body(self):
        self.assertEqual(netcode.bingo_update(1251, 1, {}),
                         (404, "Bingo game 1251 not found"))

    def test_unknown_player_is_412_with_roster(self):
        self.bingo = FakeBingo(pids=(1, 2))
        self.assertEqual(netcode.bingo_update(1252, 9, {}),
                         (412, "player not in game! [1, 2]"))

    def test_updates_fresh_read_under_lock(self):
        self.bingo = FakeBingo()
        self.refetched = FakeBingo()
        status, body = netcode.bingo_update(1256, 1, {"bingoData": '{"sq": 1}'})
        self.assertEqual((status, body), (200, "200"))
        self.assertEqual(self.bingo.updates, [])          # stale pre-check copy untouched
        self.assertEqual(len(self.refetched.updates), 1)  # locked fresh read did the work
        self.assertEqual(Cache.get_board(1256), {"updated_by": 1})

    def test_failure_is_503(self):
        self.bingo = FakeBingo()
        self.refetched = FakeBingo(fail_times=1)
        self.assertEqual(netcode.bingo_update(1257, 1, {"bingoData": '{"sq": 1}'}),
                         (503, "503"))

    def test_win_rebusts_tick_checksum_after_update(self):
        # regression: a tick that read the winner pre-signal can re-arm the
        # fast path after signal_send's bust; the route must bust again once
        # the update has fully landed (game 133908: 16s win-signal stall)
        self.bingo = FakeBingo()
        self.refetched = FakeBingo()
        Cache.set_seen_checksum((1258, 1), 4242)  # the racing tick's re-arm
        self.assertEqual(netcode.bingo_update(1258, 1, {"bingoData": '{"sq": 1}'}),
                         (200, "200"))
        self.assertIsNone(Cache.get_seen_checksum((1258, 1)))


if __name__ == "__main__":
    unittest.main()
