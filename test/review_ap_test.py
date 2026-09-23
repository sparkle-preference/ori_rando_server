"""Regression tests for review findings on the Archipelago bridge.

Each test asserts the correct behavior; @expectedFailure marks a defect still open.

Run from the repo root:  python3 -m unittest test.review_ap_test -v
"""
import socket
import threading
import time
import unittest

import models
from archipelago import ap_bridge
from archipelago.ap_bridge import GameMaps
from test.ap_bridge_test import (FakeSocket, HintTestCase, ROOMINFO,
                                 SessionTestCase, connected)


class TestPendingHintAfterReconnect(HintTestCase):
    """A claim left PENDING by an earlier connection is answered by the room's hint list."""

    def _frames(self):
        room = dict(ROOMINFO[0], hint_cost=10,
                    datapackage_checksums={"Ori DE Rando": "oridesum", "Clique": "cliquesum"})
        held = [self.stored_hint(1, 3, 99, self.WV)]
        # the scout reply precedes the Get reply: the room answers in send order
        return [[room],
                [connected(missing=self.OURS + [524541], slot_info=self.SLOT_INFO,
                           players=self.PLAYERS, hint_points=100)],
                [{"cmd": "LocationInfo", "locations": [
                    {"location": 524541, "item": 42, "player": 3, "flags": 0}]}],
                [self.retrieved(1, held)],
                self.clique_package({"Overworld Chest 12": 99})]

    def test_pending_claim_waits_for_the_room_hint_list(self):
        self.hint_rows[5] = {"s": "p", "t": "", "a": self.WV, "u": int(time.time())}
        self.run_session(self.wanting([5]), self._frames())
        texts = [answers[5] for answers in self.published if 5 in answers]
        self.assertNotIn(ap_bridge.FOREIGN_HINT_TEXT, texts)
        self.assertEqual(texts[-1:], ["Questy Overworld Chest 12"])

    def test_a_claim_in_flight_is_never_put_back_on_sale(self):
        # an unrelated Hint reopens the retry window while the keystone purchase is in flight
        sock = self.run_session(self.buying([6]), self.hello() + [
            [self.hint_msg(1, self.STOMP, 2, 524543)]])
        self.assertEqual(self.says(sock), ["!hint Glades Pool Keystone"])
        self.assertNotIn(6, [slot for slot, state, _ in self.hint_writes if state == "o"])


class _StopAfterWaits(object):
    """threading.Event stand-in that records backoff waits and stops after n."""

    def __init__(self, n):
        self.waits, self.n, self._set = [], n, False

    def is_set(self):
        return self._set

    def set(self):
        self._set = True

    def wait(self, timeout=None):
        self.waits.append(timeout)
        self._set = len(self.waits) >= self.n
        return self._set


class TestPostAuthCrashBackoff(SessionTestCase):
    """A session that authenticates then dies of a non-transport error must back off."""

    def setUp(self):
        super(TestPostAuthCrashBackoff, self).setUp()

        class _Link(object):
            enabled = True
            host, port, password = "ap.example", 38281, "hunter2"
            slot_names = ["Ori1", "Ori2"]
            goal_worlds = []
        link = _Link()
        maps = GameMaps(2, {1: {0: 524541}, 2: {}}, {1: {}, 2: {}})
        bad = [{"cmd": "ReceivedItems", "index": None, "items": []}]
        self._saved = (models.client, ap_bridge.APLink, ap_bridge.game_maps,
                       ap_bridge._open_socket)

        class _FakeNdbClient(object):
            def context(self):
                return ap_bridge._nullctx()
        models.client = _FakeNdbClient()
        ap_bridge.APLink = type("FakeAPLink", (object,),
                                {"with_id": staticmethod(lambda gid: link)})
        ap_bridge.game_maps = lambda gid: maps
        ap_bridge._open_socket = lambda host, port, hint=None: (
            FakeSocket([ROOMINFO, [connected()], bad]), "ws")

    def tearDown(self):
        (models.client, ap_bridge.APLink, ap_bridge.game_maps,
         ap_bridge._open_socket) = self._saved
        ap_bridge._last_active.pop(self.GID, None)
        super(TestPostAuthCrashBackoff, self).tearDown()

    def test_repeated_post_auth_crash_grows_the_backoff(self):
        b = ap_bridge._Bridge(self.GID, self.WORLD)
        b.stop_event = _StopAfterWaits(3)
        b._run()
        self.assertEqual([s for _, s, _ in self.statuses][:2], ["connected", "error"])
        self.assertGreater(b.stop_event.waits[-1], ap_bridge.BACKOFF_MIN)

    def test_a_session_that_stayed_up_retries_fast(self):
        saved, ap_bridge.HEALTHY_SECS = ap_bridge.HEALTHY_SECS, 0.0
        try:
            b = ap_bridge._Bridge(self.GID, self.WORLD)
            b.stop_event = _StopAfterWaits(3)
            b._run()
        finally:
            ap_bridge.HEALTHY_SECS = saved
        self.assertEqual(b.stop_event.waits, [ap_bridge.BACKOFF_MIN] * 3)


class TestRetargetRedials(SessionTestCase):
    """A room retargeted under a live session is dialed by the same thread."""

    def setUp(self):
        super(TestRetargetRedials, self).setUp()

        class _Link(object):
            enabled = True
            host, port, password = "ap.example", 38281, "hunter2"
            slot_names = ["Ori1", "Ori2"]
            goal_worlds = []
        self.link = _Link()
        self.dialed = []
        maps = GameMaps(2, {1: {0: 524541}, 2: {}}, {1: {}, 2: {}})
        self._saved = (models.client, ap_bridge.APLink, ap_bridge.game_maps,
                       ap_bridge._open_socket, ap_bridge.LINK_RECHECK_SECS)

        class _FakeNdbClient(object):
            def context(self):
                return ap_bridge._nullctx()

        def dial(host, port, hint=None):
            self.dialed.append(host)
            self.link.host = "new.example"    # retargeted while the first session runs
            return FakeSocket([ROOMINFO, [connected()], None, None]), "ws"
        models.client = _FakeNdbClient()
        ap_bridge.APLink = type("FakeAPLink", (object,),
                                {"with_id": staticmethod(lambda gid: self.link)})
        ap_bridge.game_maps = lambda gid: maps
        ap_bridge._open_socket = dial
        ap_bridge.LINK_RECHECK_SECS = 0.0

    def tearDown(self):
        (models.client, ap_bridge.APLink, ap_bridge.game_maps,
         ap_bridge._open_socket, ap_bridge.LINK_RECHECK_SECS) = self._saved
        ap_bridge._last_active.pop(self.GID, None)
        super(TestRetargetRedials, self).tearDown()

    def test_the_bridge_loop_dials_the_new_room(self):
        b = ap_bridge._Bridge(self.GID, self.WORLD)
        b.stop_event = _StopAfterWaits(1)
        b._run()
        self.assertEqual(self.dialed, ["ap.example", "new.example"])


class TestSilentRoomHandshake(unittest.TestCase):
    """A host that accepts TCP and never speaks must not hold a bridge thread forever."""

    def setUp(self):
        self._saved = (ap_bridge.CONNECT_TIMEOUT, ap_bridge.HANDSHAKE_TIMEOUT)
        ap_bridge.CONNECT_TIMEOUT = ap_bridge.HANDSHAKE_TIMEOUT = 0.5
        self.server = socket.socket()
        self.server.bind(("127.0.0.1", 0))
        self.server.listen(4)
        self.held = []

        def accept():
            while True:
                try:
                    conn, _ = self.server.accept()
                except OSError:
                    return
                self.held.append(conn)
        threading.Thread(target=accept, daemon=True).start()

    def tearDown(self):
        ap_bridge.CONNECT_TIMEOUT, ap_bridge.HANDSHAKE_TIMEOUT = self._saved
        self.server.close()
        for conn in self.held:
            conn.close()

    def test_open_socket_gives_up_on_a_silent_host(self):
        port = self.server.getsockname()[1]
        worker = threading.Thread(
            target=lambda: self._swallow(ap_bridge._open_socket, "127.0.0.1", port),
            daemon=True)
        worker.start()
        worker.join(3.0)
        self.assertFalse(worker.is_alive(), "_open_socket still blocked after 3 s")

    def test_an_idle_connection_outlives_the_handshake_timeout(self):
        from wsproto import ConnectionType, WSConnection
        from wsproto.events import AcceptConnection, Request, TextMessage
        from wsproto.extensions import PerMessageDeflate
        self.server.close()
        srv = socket.socket()
        srv.bind(("127.0.0.1", 0))
        srv.listen(4)
        self.held.append(srv)

        def room():
            while True:
                conn, _ = srv.accept()
                self.held.append(conn)
                data = conn.recv(4096)
                if not data:
                    continue            # the preflight probe
                ws = WSConnection(ConnectionType.SERVER)
                ws.receive_data(data)
                for event in ws.events():
                    if isinstance(event, Request):
                        conn.send(ws.send(AcceptConnection(extensions=[PerMessageDeflate()])))
                time.sleep(1.0)
                conn.send(ws.send(TextMessage(data="hello")))
                return
        threading.Thread(target=room, daemon=True).start()
        client, scheme = ap_bridge._open_socket("127.0.0.1", srv.getsockname()[1], "ws")
        try:
            self.assertEqual(scheme, "ws")
            self.assertEqual(client.receive(timeout=3), "hello")
        finally:
            client.close()

    @staticmethod
    def _swallow(fn, *args):
        try:
            fn(*args)
        except Exception:
            pass


def _slot_names_before_the_cut(worlds, names):
    """ap_slot_names as seeds were generated with before the 16-char rule."""
    from ap_models import PLAYER_NAME_MAX, ap_slot_name, sanitize_display_name
    out, seen = [], set()
    for w in range(1, int(worlds) + 1):
        raw = names[w - 1] if names and w <= len(names) else ""
        name = sanitize_display_name(raw, PLAYER_NAME_MAX) or ap_slot_name(w)
        if name.lower() in seen:
            suffix = str(w)
            name = name[:PLAYER_NAME_MAX - len(suffix)] + suffix
        seen.add(name.lower())
        out.append(name)
    return out


def _ap_accepts(out):
    return (all(n == n.strip()[:16].strip() and n != "Archipelago" for n in out)
            and len({n.lower() for n in out}) == len(out))


class TestSlotNamesFitArchipelago(unittest.TestCase):
    """AP's Generate.handle_name keeps 16 chars and rejects case-insensitive duplicates."""

    def test_slot_names_survive_ap_name_handling(self):
        from ap_models import ap_slot_names
        for names in (["ABCDEFGHIJKLMNOPQRST", "x"], ["Bob3", "Bob", "Bob"],
                      ["ABCDEFGHIJKLMNOPQ1", "ABCDEFGHIJKLMNOPQ2"], ["Archipelago", "Ori1"],
                      ["ABCDEFGHIJKLMNOP", "abcdefghijklmnop", "ABCDEFGHIJKLMNO2"]):
            out = ap_slot_names(len(names), names)
            self.assertTrue(_ap_accepts(out), (names, out))

    def test_names_ap_already_accepted_are_unchanged(self):
        import random
        from ap_models import ap_slot_names
        rng = random.Random(7)
        pool = ["Ana", "ana", "Bob", "Bob2", "Bob3", "Ori1", "Ori2", "", "x" * 15,
                "Sixteen Chars Ok", "Seventeen chars!!", "Al|ice", "  spaced  out "]
        checked = 0
        for _ in range(3000):
            names = [rng.choice(pool) for _ in range(rng.randint(1, 5))]
            self.assertTrue(_ap_accepts(ap_slot_names(len(names), names)), names)
            before = _slot_names_before_the_cut(len(names), names)
            if _ap_accepts(before):
                checked += 1
                self.assertEqual(ap_slot_names(len(names), names), before, names)
        self.assertGreater(checked, 500)


if __name__ == "__main__":
    unittest.main()
