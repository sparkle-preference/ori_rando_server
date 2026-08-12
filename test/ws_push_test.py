"""Tests for the websocket push layer: the push.py hub, the
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
    def setUp(self):
        # keep the real pusher thread out of unit tests: it would race the
        # queue assertions (and hit real ndb). _notify must still ASK for it.
        self._real_ensure = ws._ensure_pusher
        self.ensure_calls = []
        ws._ensure_pusher = lambda: self.ensure_calls.append(1)

    def tearDown(self):
        ws._ensure_pusher = self._real_ensure
        with ws._socks_lock:
            ws._socks.clear()
        while not ws._push_queue.empty():
            ws._push_queue.get_nowait()

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

    def test_notify_lazily_ensures_the_pusher_thread(self):
        # the preload-fork lesson (game 134236): the thread must be started
        # by the process that notifies, not the gunicorn master at import
        ws._register((1, 2), FakeConn())
        ws._notify((1, 2))
        self.assertEqual(self.ensure_calls, [1])

    def test_notify_without_socket_skips_thread_start(self):
        ws._notify((1, 2))
        self.assertEqual(self.ensure_calls, [])

    def test_ensure_pusher_starts_and_reuses(self):
        import threading
        stop = threading.Event()
        real_pusher, real_thread = ws._pusher, ws._push_thread
        ws._pusher = stop.wait
        ws._ensure_pusher = self._real_ensure  # use the real one here
        try:
            ws._push_thread = None
            ws._ensure_pusher()
            t1 = ws._push_thread
            self.assertTrue(t1.is_alive())
            ws._ensure_pusher()
            self.assertIs(ws._push_thread, t1)  # alive thread is reused
        finally:
            stop.set()
            ws._pusher = real_pusher
            ws._push_thread = real_thread


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
        # bitfields match the payload and no version is sent, so the slow
        # path has nothing to write and never reaches tick_update_txn
        p = Player(id="9.1", skills=1027, events=3, teleporters=512,
                   bonuses={"17": 2}, hints={}, signals=["msg:@hi@"],
                   seen_bflds=8 * [0], have_bflds=8 * [0])
        p.put = lambda *a, **k: None
        game = FakeGame(p)
        Game.with_id = staticmethod(lambda gid: game)

        payload = {"x": "1", "y": "2"}
        for i in range(8):
            payload["seen_%s" % i] = "0"
            payload["have_%s" % i] = "0"
        tick_status, tick_body = netcode.tick(9, 1, payload)
        self.assertEqual(tick_status, 200)
        self.assertEqual(netcode.tick_output(9, 1), tick_body)

    def test_dead_game_returns_none(self):
        Game.with_id = staticmethod(lambda gid: None)
        self.assertIsNone(netcode.tick_output(9, 1))


if __name__ == "__main__":
    unittest.main()
