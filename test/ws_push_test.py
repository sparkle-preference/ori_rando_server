"""Tests for the websocket push layer (WS_PUSH): the push.py hub, the
cache-bust trigger, the socket registry, and the pusher's send path.

Same conventions as ws_adapter_test: save/restore stubs, fake sockets, no
real networking. The tick_output-vs-tick parity test runs a real Player
entity through both public entry points inside an in-memory ndb context.

Run from the repo root:  python -m unittest test.ws_push_test -v
"""
import unittest

import google.auth.credentials
from google.cloud import ndb

import cache
import netcode
import push
import ws
from enums import MultiplayerGameType
from models import Game, Player
from simple_websocket import ConnectionClosed


class RecordingHandler(object):
    def __init__(self, boom=False):
        self.calls = []
        self.boom = boom

    def __call__(self, gpid):
        self.calls.append(gpid)
        if self.boom:
            raise RuntimeError("handler kaboom")


class PushHubTests(unittest.TestCase):
    def tearDown(self):
        push.set_handler(None)

    def test_no_handler_is_a_noop(self):
        push.notify((1, 2))  # must not raise

    def test_handler_receives_gpid(self):
        h = RecordingHandler()
        push.set_handler(h)
        push.notify((7, 3))
        self.assertEqual(h.calls, [(7, 3)])

    def test_handler_exception_is_swallowed(self):
        push.set_handler(RecordingHandler(boom=True))
        push.notify((1, 2))  # must not raise

    def test_python_cache_bust_notifies(self):
        h = RecordingHandler()
        push.set_handler(h)
        pc = cache.PythonCache()
        pc.clear_seen_checksum((5, 9))
        self.assertEqual(h.calls, [(5, 9)])


class FakeConn(object):
    def __init__(self):
        self.sent = []
        self.closed_on_send = False

    def send(self, data):
        if self.closed_on_send:
            raise ConnectionClosed(1000, "gone")
        self.sent.append(data)


class FakeNdbClient(object):
    class _Ctx(object):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def context(self):
        return self._Ctx()


class RegistryTests(unittest.TestCase):
    def tearDown(self):
        with ws._socks_lock:
            ws._socks.clear()

    def test_register_unregister(self):
        conn = FakeConn()
        ws._register((1, 2), conn)
        self.assertIn((1, 2), ws._socks)
        ws._unregister((1, 2), conn)
        self.assertNotIn((1, 2), ws._socks)

    def test_stale_unregister_leaves_replacement(self):
        old, new = FakeConn(), FakeConn()
        ws._register((1, 2), old)
        ws._register((1, 2), new)  # reconnect replaced the entry
        ws._unregister((1, 2), old)  # old conn's finally must not evict new
        self.assertIs(ws._socks[(1, 2)][0], new)

    def test_notify_without_socket_skips_queue(self):
        ws._notify((1, 2))
        self.assertTrue(ws._push_queue.empty())

    def test_notify_with_socket_enqueues(self):
        ws._register((1, 2), FakeConn())
        ws._notify((1, 2))
        self.assertEqual(ws._push_queue.get_nowait(), (1, 2))


class StubTickOutput(object):
    def __init__(self, body="1,2,3,,,"):
        self.body = body
        self.calls = []

    def __call__(self, game_id, player_id):
        self.calls.append((game_id, player_id))
        return self.body


class PushOneTests(unittest.TestCase):
    def setUp(self):
        self._real = netcode.tick_output

    def tearDown(self):
        netcode.tick_output = self._real
        with ws._socks_lock:
            ws._socks.clear()

    def test_pushes_tick_frame(self):
        stub = netcode.tick_output = StubTickOutput("42,0,0,,,win:gg")
        conn = FakeConn()
        ws._register((3, 4), conn)
        ws._push_one((3, 4), FakeNdbClient())
        self.assertEqual(conn.sent, ["tick:42,0,0,,,win:gg"])
        self.assertEqual(stub.calls, [(3, 4)])

    def test_no_socket_skips_render(self):
        stub = netcode.tick_output = StubTickOutput()
        ws._push_one((3, 4), FakeNdbClient())
        self.assertEqual(stub.calls, [])

    def test_dead_game_sends_nothing(self):
        netcode.tick_output = lambda g, p: None
        conn = FakeConn()
        ws._register((3, 4), conn)
        ws._push_one((3, 4), FakeNdbClient())
        self.assertEqual(conn.sent, [])

    def test_closed_socket_is_swallowed(self):
        netcode.tick_output = StubTickOutput()
        conn = FakeConn()
        conn.closed_on_send = True
        ws._register((3, 4), conn)
        ws._push_one((3, 4), FakeNdbClient())  # must not raise

    def test_render_exception_is_swallowed(self):
        def boom(g, p):
            raise RuntimeError("kaboom")
        netcode.tick_output = boom
        ws._register((3, 4), FakeConn())
        ws._push_one((3, 4), FakeNdbClient())  # must not raise


class FakeGame(object):
    def __init__(self, player, mode=MultiplayerGameType.SHARED):
        self.mode = mode
        self._player = player

    def player(self, pid, *a, **k):
        return self._player


class TickOutputParityTests(unittest.TestCase):
    """A pushed frame's body must be byte-identical to the /tick/ response
    the same player state would produce (the client can't tell them apart)."""

    @classmethod
    def setUpClass(cls):
        creds = google.auth.credentials.AnonymousCredentials()
        cls.ndb_client = ndb.Client(project="unit-test", credentials=creds)

    def setUp(self):
        self._ctx = self.ndb_client.context()
        self._ctx.__enter__()
        self._real_with_id = Game.with_id

    def tearDown(self):
        Game.with_id = self._real_with_id
        self._ctx.__exit__(None, None, None)

    def test_matches_tick_slow_path_body(self):
        p = Player(id="9.1", skills=1027, events=3, teleporters=512,
                   bonuses={"17": 2}, hints={}, signals=["msg:@hi@"])
        p.put = lambda *a, **k: None
        p.bitfield_updates = lambda payload, gid: None
        p.note_version = lambda *a, **k: False
        game = FakeGame(p)
        Game.with_id = staticmethod(lambda gid: game)

        tick_status, tick_body = netcode.tick(9, 1, {"x": "1", "y": "2"})
        self.assertEqual(tick_status, 200)
        self.assertEqual(netcode.tick_output(9, 1), tick_body)

    def test_dead_game_returns_none(self):
        Game.with_id = staticmethod(lambda gid: None)
        self.assertIsNone(netcode.tick_output(9, 1))


if __name__ == "__main__":
    unittest.main()
