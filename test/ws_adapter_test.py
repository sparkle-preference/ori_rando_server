"""Tests for the websocket transport adapter (ws.py).

The session layer itself is pinned by session_golden_test; these tests pin
the adapter contract on top of it: frame parsing, payload parsing identical
to request.form semantics, the reply/close protocol, and the connection
gauge/limit behavior. netcode.tick is stubbed in the save/restore style —
no datastore, no sockets.

Run from the repo root:  python -m unittest test.ws_adapter_test -v
"""
import unittest

import google.auth.credentials
from google.cloud import ndb

import netcode
import ws
from simple_websocket import ConnectionClosed


class StubTick(object):
    """save/restore stub for netcode.tick recording the payload it got."""

    def __init__(self, status=200, body="0,0,0,,,"):
        self.status = status
        self.body = body
        self.calls = []

    def __call__(self, game_id, player_id, payload):
        self.calls.append((game_id, player_id, dict(payload)))
        return self.status, self.body


class HandleFrameTests(unittest.TestCase):
    def setUp(self):
        self._real_tick = netcode.tick

    def tearDown(self):
        netcode.tick = self._real_tick

    def test_tick_frame_replies_with_prefixed_body_verbatim(self):
        # commas, pipes and colons in the body must pass through untouched
        body = "1027,3,512,17x2;100_-70x1,,msg:@hi@|win:done,4|8,1.name;2.other"
        netcode.tick = StubTick(200, body)
        reply, close = ws.handle_frame(1, 2, "tick:x=1&y=2")
        self.assertEqual(reply, "tick:" + body)
        self.assertFalse(close)

    def test_tick_payload_parses_like_request_form(self):
        stub = netcode.tick = StubTick()
        frame = "tick:x=189.5&y=-210.2&version=4.2.2&seen_0=4294967295&have_0=0&have_1="
        ws.handle_frame(3, 4, frame)
        (gid, pid, payload), = stub.calls
        self.assertEqual((gid, pid), (3, 4))
        self.assertEqual(payload, {
            "x": "189.5", "y": "-210.2", "version": "4.2.2",
            "seen_0": "4294967295", "have_0": "0", "have_1": "",  # blanks kept
        })

    def test_failing_tick_errs_and_closes(self):
        netcode.tick = StubTick(412, "412")
        reply, close = ws.handle_frame(1, 2, "tick:x=1&y=2")
        self.assertEqual(reply, "err:tick:412")
        self.assertTrue(close)

    def test_unknown_kind_errs_without_closing(self):
        netcode.tick = StubTick()
        for frame in ("bogus:stuff", "tick", ""):  # prefix-less "tick" is not a tick
            reply, close = ws.handle_frame(1, 2, frame)
            self.assertTrue(reply.startswith("err:"), frame)
            self.assertFalse(close, frame)
        self.assertEqual(netcode.tick.calls, [])

    def test_empty_tick_body_still_dispatches(self):
        stub = netcode.tick = StubTick()
        reply, close = ws.handle_frame(1, 2, "tick:")
        self.assertEqual(stub.calls[0][2], {})
        self.assertFalse(close)


class GoalsFrameTests(unittest.TestCase):
    """goals: asks what this player's board tracks; the 4.3 seed file stopped
    carrying the Goals line, so this channel is the only source."""

    def setUp(self):
        self._goals = netcode.goals
        self.answer = (200, "Goals:DrownFrog,CoreSkip/Journey:COUNT")
        netcode.goals = lambda gid, pid: self.answer

    def tearDown(self):
        netcode.goals = self._goals

    def test_a_board_answers_with_its_line(self):
        reply, close = ws.handle_frame(1, 2, "goals:")
        self.assertEqual(reply, "goals:Goals:DrownFrog,CoreSkip/Journey:COUNT")
        self.assertFalse(close)

    def test_no_board_is_an_err_frame_and_the_socket_lives(self):
        self.answer = (404, "Bingo game 1 not found")
        reply, close = ws.handle_frame(1, 2, "goals:")
        self.assertEqual(reply, "err:goals:404")
        self.assertFalse(close)


class AreasFrameTests(unittest.TestCase):
    """areas:<sha256> asks whether the client's logic file is current: "ok"
    on a match, the whole file otherwise (clients ignore small bodies, so
    the stub serves at production size)."""

    AREAS = "sl: SunkenGladesRunaway\n" * 500

    def setUp(self):
        self._cache = ws.Cache
        test = self

        class _Cache(object):
            def get_areas(self):
                return test.AREAS
        ws.Cache = _Cache()

    def tearDown(self):
        ws.Cache = self._cache

    def _hash(self):
        import hashlib
        return hashlib.sha256(self.AREAS.encode()).hexdigest()

    def test_matching_hash_gets_ok(self):
        reply, close = ws.handle_frame(1, 2, "areas:" + self._hash())
        self.assertEqual(reply, "areas:ok")
        self.assertFalse(close)

    def test_stale_hash_gets_the_whole_file(self):
        reply, close = ws.handle_frame(1, 2, "areas:none")
        self.assertEqual(reply, "areas:" + self.AREAS)
        self.assertFalse(close)

    def test_uppercase_hash_still_matches(self):
        reply, _ = ws.handle_frame(1, 2, "areas:" + self._hash().upper())
        self.assertEqual(reply, "areas:ok")


class RecordingStub(object):
    """save/restore stub for any netcode handler; returns (status, body)."""

    def __init__(self, status=200, body="ok"):
        self.status = status
        self.body = body
        self.calls = []

    def __call__(self, *args):
        self.calls.append(args)
        return self.status, self.body


class ChannelFrameTests(unittest.TestCase):
    """The v2 frame vocabulary (found/bingo/conf/seed/complete). Server-side
    only until the next dll crack; old clients never send these."""

    def setUp(self):
        self._saved = {name: getattr(netcode, name) for name in
                       ("found_pickup", "bingo_update", "signal_callback", "connect", "game_complete")}

    def tearDown(self):
        for name, fn in self._saved.items():
            setattr(netcode, name, fn)

    def test_found_frame_parses_and_acks_with_token(self):
        stub = netcode.found_pickup = RecordingStub(200, "200")
        frame = "found:17|zone=sunkenGlades&remove|919772|RB|12"
        reply, close = ws.handle_frame(3, 4, frame)
        self.assertEqual(reply, "foundack:17|200")
        self.assertFalse(close)
        (gid, pid, coords, kind, id_, payload), = stub.calls
        self.assertEqual((gid, pid, coords, kind, id_), (3, 4, "919772", "RB", "12"))
        self.assertEqual(payload["zone"], "sunkenGlades")
        self.assertIn("remove", payload)  # flag-by-presence survives

    def test_found_id_parses_greedily(self):
        # TW ids carry commas and can carry pipes-adjacent chars; id is last
        stub = netcode.found_pickup = RecordingStub(200, "200")
        ws.handle_frame(3, 4, "found:1||919772|TW|Warp to Stomp Tree Roof,917,-70")
        self.assertEqual(stub.calls[0][4], "Warp to Stomp Tree Roof,917,-70")
        self.assertEqual(stub.calls[0][5], {})

    def test_found_status_rides_the_ack(self):
        netcode.found_pickup = RecordingStub(410, "410")
        reply, close = ws.handle_frame(3, 4, "found:9||1|TP|Glades")
        self.assertEqual(reply, "foundack:9|410")
        self.assertFalse(close)  # per-pickup problems never kill the transport

    def test_found_malformed_errs_without_dispatch(self):
        stub = netcode.found_pickup = RecordingStub()
        reply, close = ws.handle_frame(3, 4, "found:no-pipes-here")
        self.assertEqual(reply, "err:found:malformed")
        self.assertFalse(close)
        self.assertEqual(stub.calls, [])

    def test_bingo_frame_always_acks(self):
        stub = netcode.bingo_update = RecordingStub(200, "200")
        reply, close = ws.handle_frame(3, 4, "bingo:bingoData=%7B%22a%22%3A1%7D&version=4.2.4")
        self.assertEqual(reply, "bingoack:200")
        self.assertEqual(stub.calls[0][2]["bingoData"], '{"a":1}')

    def test_bingo_failure_acks_status(self):
        netcode.bingo_update = RecordingStub(503, "503")
        reply, close = ws.handle_frame(3, 4, "bingo:bingoData=x")
        self.assertEqual(reply, "bingoack:503")
        self.assertFalse(close)

    def test_conf_dispatches_silently(self):
        stub = netcode.signal_callback = RecordingStub(200, "cleared")
        reply, close = ws.handle_frame(3, 4, "conf:win:$Finished in 1st place!")
        self.assertIsNone(reply)
        # the signal keeps its own colons intact
        self.assertEqual(stub.calls[0][2], "win:$Finished in 1st place!")

    def test_seed_dispatches_silently(self):
        stub = netcode.connect = RecordingStub(200, "ok")
        reply, close = ws.handle_frame(3, 4, "seed:seed=Sync3.4%2CStandard%7C123&version=4.2.4")
        self.assertIsNone(reply)
        self.assertEqual(stub.calls[0][2]["seed"], "Sync3.4,Standard|123")

    def test_complete_acks_with_status(self):
        # acked so clients can resend until heard (134478's stranded release)
        stub = netcode.game_complete = RecordingStub(200, "ok")
        reply, close = ws.handle_frame(3, 4, "complete:")
        self.assertEqual(reply, "completeack:200")
        self.assertFalse(close)
        self.assertEqual(stub.calls, [(3, 4)])

    def test_complete_ack_carries_dead_game_status(self):
        netcode.game_complete = RecordingStub(412, "412")
        reply, close = ws.handle_frame(3, 4, "complete:")
        self.assertEqual(reply, "completeack:412")
        self.assertFalse(close)  # any ack stops the client's retries


class FakeConn(object):
    """Scripted socket: receive() pops frames, then simulates a client close."""

    def __init__(self, frames):
        self.frames = list(frames)
        self.sent = []
        self.closed = None

    def receive(self, timeout=None):
        if not self.frames:
            raise ConnectionClosed(1000, "client gone")
        return self.frames.pop(0)

    def send(self, data):
        self.sent.append(data)

    def close(self, reason=None, message=None):
        self.closed = (reason, message)


class RunConnectionTests(unittest.TestCase):
    """Runs inside a real ndb context, like prod: the connection loop clears
    the ambient context's cache per frame (contexts can't nest per thread)."""

    @classmethod
    def setUpClass(cls):
        creds = google.auth.credentials.AnonymousCredentials()
        cls.ndb_client = ndb.Client(project="unit-test", credentials=creds)

    def setUp(self):
        self._ctx = self.ndb_client.context()
        self._ctx.__enter__()
        self._real_tick = netcode.tick
        self._real_limit = ws.WS_CONN_LIMIT
        self.assertEqual(ws._conns, 0)  # tests must leave the gauge clean

    def tearDown(self):
        netcode.tick = self._real_tick
        ws.WS_CONN_LIMIT = self._real_limit
        self._ctx.__exit__(None, None, None)

    def test_frames_replied_and_gauge_restored(self):
        netcode.tick = StubTick(200, "ok")
        conn = FakeConn(["tick:x=1&y=2", "tick:x=3&y=4"])
        ws.run_connection(conn, 1, 2)
        self.assertEqual(conn.sent, ["tick:ok", "tick:ok"])
        self.assertEqual(ws._conns, 0)

    def test_bytes_frames_are_decoded(self):
        netcode.tick = StubTick(200, "ok")
        conn = FakeConn([b"tick:x=1&y=2"])
        ws.run_connection(conn, 1, 2)
        self.assertEqual(conn.sent, ["tick:ok"])

    def test_dead_game_sends_err_and_stops(self):
        netcode.tick = StubTick(412, "412")
        conn = FakeConn(["tick:x=1&y=2", "tick:never=processed"])
        ws.run_connection(conn, 1, 2)
        self.assertEqual(conn.sent, ["err:tick:412"])
        self.assertEqual(len(netcode.tick.calls), 1)
        self.assertEqual(ws._conns, 0)

    def test_at_limit_rejects_with_1013_and_leaves_gauge(self):
        ws.WS_CONN_LIMIT = 0
        conn = FakeConn(["tick:x=1&y=2"])
        ws.run_connection(conn, 1, 2)
        self.assertEqual(conn.closed[0], 1013)
        self.assertEqual(conn.sent, [])
        self.assertEqual(ws._conns, 0)

    def test_handler_exception_drops_frame_but_keeps_connection(self):
        # parity with http: a failed tick is one 500, not transport death
        calls = []

        def flaky(gid, pid, payload):
            calls.append(payload)
            if len(calls) == 1:
                raise RuntimeError("kaboom")
            return 200, "recovered"
        netcode.tick = flaky
        conn = FakeConn(["tick:x=1&y=2", "tick:x=3&y=4"])
        ws.run_connection(conn, 1, 2)
        self.assertEqual(conn.sent, ["tick:recovered"])
        self.assertEqual(len(calls), 2)
        self.assertEqual(ws._conns, 0)


if __name__ == "__main__":
    unittest.main()
