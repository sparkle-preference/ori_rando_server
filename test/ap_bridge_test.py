"""Unit tests for the Archipelago room bridge.

Self-contained, no mock lib, scripted transport in the ws_adapter_test
style. Three layers:

  session    ApSession against stubbed datastore touchpoints (SessionTestCase)
  golden     ApSession against the REAL _apply_grants/_shadow_slots, running
             on in-memory Player entities so slot bits are checked for real
             (TestGoldenRealTouchpoints, netcode_test-style reroutes)
  loop       _Bridge._run driven synchronously: refusal/loss surface on the
             link row and feed the backoff (TestBridgeLoopBackoff)

Wire shapes follow AP 0.6.7 (MultiServer.py): JSON arrays of {cmd} dicts.

Run from the repo root:  python3 -m unittest test.ap_bridge_test -v
"""
import json
import threading
import unittest

import google.auth.credentials
from google.cloud import ndb
from simple_websocket import ConnectionClosed

import models
from archipelago import ap_bridge
from archipelago.ap_bridge import ApSession, ApRefused, GameMaps
from cache import Cache
from models import Player


class FakeSocket(object):
    """Scripted transport: each script entry is a list of msg dicts (one
    frame) or None (a receive timeout). Exhausted script = connection lost."""

    def __init__(self, frames):
        self.script = list(frames)
        self.sent = []

    def receive(self, timeout=None):
        if not self.script:
            raise ConnectionClosed()
        frame = self.script.pop(0)
        return None if frame is None else json.dumps(frame)

    def send(self, data):
        self.sent.append(json.loads(data))

    def close(self):
        pass


class FakeParams(object):
    def __init__(self, players, seed_data):
        self.players = players
        self.ap_mode = True
        self._seed = seed_data

    def get_seed_data(self, player=1):
        return self._seed[int(player)]


ROOMINFO = [{"cmd": "RoomInfo", "version": {"major": 0, "minor": 6, "build": 7}}]


def roominfo(checksums=None):
    room = dict(ROOMINFO[0])
    if checksums is not None:
        room["datapackage_checksums"] = checksums
    return [room]


def connected(checked=(), missing=(), slot_info=None, players=None, hint_points=None):
    msg = {"cmd": "Connected", "team": 0, "slot": 1,
           "checked_locations": list(checked), "missing_locations": list(missing)}
    if slot_info is not None:
        msg["slot_info"] = slot_info   # json object keys arrive as strings
    if players is not None:
        msg["players"] = players
    if hint_points is not None:
        msg["hint_points"] = hint_points
    return msg


class TestImportHygiene(unittest.TestCase):
    def test_no_bridge_threads_at_import(self):
        self.assertEqual([t for t in threading.enumerate()
                          if t.name.startswith("ap-bridge")], [])

    def test_flag_off_entry_points_noop(self):
        # env flag is off in tests; every request-path hook must be inert
        self.assertEqual(ap_bridge.ensure(9999), 0)
        ap_bridge.heal(9999)
        ap_bridge.notify_goal(9999, 1)
        ap_bridge.stop(9999)
        self.assertEqual(ap_bridge._bridges, {})


class TestMatchKey(unittest.TestCase):
    def test_non_ex_passthrough(self):
        self.assertEqual(ap_bridge._match_key("SK", 0), ("SK", "0"))
        self.assertEqual(ap_bridge._match_key("TP", "Grove"), ("TP", "Grove"))

    def test_ex_is_exact_up_to_the_cap(self):
        for value in (1, 40, 73, 150, 514, 600):
            self.assertEqual(ap_bridge._match_key("EX", str(value)), ("EX", str(value)))

    def test_ex_above_the_cap_rides_a_denomination(self):
        # the fallback keeps working for amounts no shipped seed has rolled
        for value, denom in [(601, "200"), (0, "50"), (-5, "50")]:
            self.assertEqual(ap_bridge._match_key("EX", str(value)), ("EX", denom),
                             "EX %s" % value)

    def test_a_warp_is_named_by_its_destination(self):
        """A TW id keeps the coordinates the client warps to; AP knows the
        item by the leading destination alone."""
        self.assertEqual(
            ap_bridge._match_key("TW", "Warp to Ginso Escape,510,910,GinsoEscape"),
            ("TW", "Warp to Ginso Escape"))

    def test_agrees_with_the_converter(self):
        """The bridge hand-mirrors convert.match_key (import weight: this
        module must stay lazy-start clean). Pin them together."""
        from archipelago.convert import match_key
        self.assertEqual(ap_bridge.EX_EXACT_CAP,
                         __import__("archipelago.export_data", fromlist=["x"]).EX_EXACT_CAP)
        for value in (0, 1, 40, 50, 100, 200, 514, 600, 601, 9999):
            self.assertEqual(ap_bridge._match_key("EX", str(value)),
                             match_key("EX", str(value)), "EX %s" % value)
        for id in ("Warp to Swamp Swim,790,-195,SwampWaterWarp", "Warp to Water Vein"):
            self.assertEqual(ap_bridge._match_key("TW", id), match_key("TW", id), id)
        self.assertEqual(ap_bridge._match_key("SK", 0), match_key("SK", 0))


class TestApfromSignal(unittest.TestCase):
    """The tick signal that says who found each granted slot. Constraints:
    ',' is the tick field separator, '|' joins signals, ';' and '=' are its
    own -- and a signal rides EVERY tick until the client confirms it."""

    def test_shape(self):
        self.assertEqual(ap_bridge._apfrom_signal({0: "P2", 3: "Questy"}, [0, 3]),
                         "apfrom:0=P2;3=Questy")

    def test_an_empty_sender_means_you_found_it_yourself(self):
        self.assertEqual(ap_bridge._apfrom_signal({1: ""}, [1]), "apfrom:1=")

    def test_only_the_slots_actually_granted_are_named(self):
        # a replay marks nothing new, so nothing is announced
        self.assertEqual(ap_bridge._apfrom_signal({0: "P2", 3: "P2"}, [3]), "apfrom:3=P2")
        self.assertIsNone(ap_bridge._apfrom_signal({0: "P2"}, []))
        self.assertIsNone(ap_bridge._apfrom_signal(None, [0]))

    def test_a_release_of_everything_stays_inside_the_cap(self):
        senders = {s: "Somebody%s" % s for s in range(256)}
        signal = ap_bridge._apfrom_signal(senders, list(range(256)))
        self.assertLessEqual(len(signal), ap_bridge.SIGNAL_MAX + len("apfrom:"))
        self.assertTrue(signal.startswith("apfrom:0=Somebody0;"))
        for bad in ",|":
            self.assertNotIn(bad, signal)

    def test_the_payload_carries_no_separator_a_parser_owns(self):
        from ap_models import wire_safe_name
        signal = ap_bridge._apfrom_signal({0: wire_safe_name("Ev,il;Na=me|X")}, [0])
        self.assertEqual(signal, "apfrom:0=Ev il Na me X")


class TestSignalAccumulation(unittest.TestCase):
    """A client that never acks apfrom (any older dll) must not accumulate
    one signal per grant in a field rendered on every tick."""

    class _FakePlayer(object):
        def __init__(self, signals):
            self.signals = list(signals)

        def mark_slot(self, slot, delay_put=False):
            return True

        def put(self, *a, **k):
            pass

    def _run(self, signals, signal, latest_only):
        player = self._FakePlayer(signals)
        key = type("K", (object,), {"get": staticmethod(lambda: player)})()
        Player.mark_slots_txn.__wrapped__(
            key, [5], signal_for=lambda fresh: signal,
            signal_latest_only=latest_only)
        return player.signals

    def test_latest_only_replaces_earlier_apfrom(self):
        self.assertEqual(
            self._run(["msg:hello", "apfrom:0=P2"], "apfrom:5=Questy", True),
            ["msg:hello", "apfrom:5=Questy"])

    def test_other_signal_kinds_still_accumulate(self):
        # msg: signals are separate messages; dropping them would eat text
        self.assertEqual(self._run(["msg:one"], "msg:two", False),
                         ["msg:one", "msg:two"])


class TestGameMaps(unittest.TestCase):
    def test_maps_from_params(self):
        # K=2: shadows are pids 3 and 4. Real coords from locations.json.
        params = FakeParams(2, {
            1: [
                ("2", "SK", "0", "Glades"),                    # plain local line
                ("919908", "MW", "3,0,AP Item #1", "Grove"),   # reserved slot 0
                ("959960", "MW", "3,1,AP Item #2", "Grove"),   # reserved slot 1
                ("5043022", "MW", "2,7,Bash", "Grove"),        # native cross: not ours
                ("-2", "MW", "3,SK,0", "Glades"),              # export slot 0
                ("-3", "MW", "3,EX,40", "Grove"),              # export slot 1
                ("-4", "MW", "3,EX,73", "Grove"),              # export slot 2
                ("-5", "MW", "1,HC,1", "Glades"),              # native manifest: not ours
            ],
            2: [
                ("-10120036", "MW", "4,3,AP Item #1", "Misty"),
                ("-2", "MW", "4,TP,Grove", "Glades"),
            ],
        })
        maps = ap_bridge.maps_from_params(params)
        self.assertEqual(maps.worlds, 2)
        self.assertEqual(maps.outbox[1], {0: 524541, 1: 524542})
        self.assertEqual(maps.outbox[2], {3: 524288})
        # EX slots keep their exact amounts: no two-into-one bucket
        self.assertEqual(maps.grant_slots[1],
                         {("SK", "0"): [0], ("EX", "40"): [1], ("EX", "73"): [2]})
        self.assertEqual(maps.grant_slots[2], {("TP", "Grove"): [0]})
        # the zone an Ori hint names, per reserved slot: what a bought hint
        # about a sibling world has to print
        self.assertEqual(maps.zones[1], {0: "Grove", 1: "Grove"})
        self.assertEqual(maps.zones[2], {3: "Misty"})
        # nothing in this seed is a reveal, so nothing in it is buyable
        self.assertEqual(maps.hint_keys, {1: {}, 2: {}})

    def test_unknown_reserved_coord_is_skipped(self):
        params = FakeParams(1, {1: [("123456789", "MW", "2,0,AP Item #1", "Glades")]})
        maps = ap_bridge.maps_from_params(params)
        self.assertEqual(maps.outbox[1], {})


class SessionTestCase(unittest.TestCase):
    """Stubs every datastore touchpoint the session uses and records calls."""

    GID, WORLD = 1301, 1

    def setUp(self):
        self.shadow = set()      # what _shadow_slots reports
        self.goals = []          # what _goal_worlds reports
        self.grants = []         # (gid, world, slots)
        self.senders = []        # {slot: sender name} per grant
        self.recvs = []          # (gid, world, count)
        self.statuses = []       # (gid, status, error)
        self.names = []          # (gid, world, total, {slot: APScout})
        self.name_slots = []     # each publish's ap_slot
        self.hint_rows = {}      # what _load_hints reports, {slot: entry}
        self.claims = []         # (slot, ap item, stale_ok) actually granted
        self.claim_ok = True     # whether the CAS lets the purchase through
        self.hint_writes = []    # (slot, state, text)
        self.published = []      # {slot: text} handed to the real player
        self.notices = []        # affordability messages sent as signals
        self.scouts_by_world = {}  # what _scout_rows reports
        self._orig = (ap_bridge._shadow_slots, ap_bridge._apply_grants,
                      ap_bridge._persist_recv, ap_bridge._persist_status,
                      ap_bridge._goal_worlds, ap_bridge._persist_names,
                      ap_bridge._load_hints, ap_bridge._claim_hint,
                      ap_bridge._persist_hint, ap_bridge._apply_hint_text,
                      ap_bridge._hint_notice, ap_bridge._scout_rows)
        ap_bridge._load_hints = lambda gid, world: dict(self.hint_rows)
        ap_bridge._claim_hint = self._claim
        ap_bridge._persist_hint = lambda gid, world, slot, state, text="", ap_item=0: (
            self.hint_writes.append((slot, state, text)))
        ap_bridge._apply_hint_text = lambda gid, world, answers, keep=None: self.published.append(dict(answers))
        ap_bridge._hint_notice = lambda gid, world, text: self.notices.append(text)
        ap_bridge._scout_rows = lambda gid, worlds: dict(self.scouts_by_world)
        ap_bridge._shadow_slots = lambda gid, world, maps: set(self.shadow)
        ap_bridge._apply_grants = lambda gid, world, slots, senders=None: (
            self.grants.append((gid, world, list(slots)))
            or self.senders.append(dict(senders or {})) or len(slots))
        ap_bridge._persist_recv = lambda gid, world, count: self.recvs.append((gid, world, count))
        ap_bridge._persist_status = lambda gid, status, error: self.statuses.append((gid, status, error))
        ap_bridge._persist_names = lambda gid, world, total, names, ap_slot=None: (
            self.names.append((gid, world, total, dict(names)))
            or self.name_slots.append(ap_slot))
        ap_bridge._goal_worlds = lambda gid: list(self.goals)

    def _claim(self, gid, world, slot, ap_item, stale_ok=False):
        if not self.claim_ok:
            return False
        self.claims.append((slot, ap_item, stale_ok))
        return True

    def tearDown(self):
        (ap_bridge._shadow_slots, ap_bridge._apply_grants, ap_bridge._persist_recv,
         ap_bridge._persist_status, ap_bridge._goal_worlds,
         ap_bridge._persist_names, ap_bridge._load_hints, ap_bridge._claim_hint,
         ap_bridge._persist_hint, ap_bridge._apply_hint_text,
         ap_bridge._hint_notice, ap_bridge._scout_rows) = self._orig
        ap_bridge._notice_at.clear()

    def make_session(self, **kw):
        # slot 0 and 3 take Bash (524288); slot 1 takes 50 experience (524349)
        maps = GameMaps(2, {1: {0: 524541, 1: 524542}, 2: {}},
                        {1: {("SK", "0"): [0, 3], ("EX", "50"): [1]}, 2: {}})
        kw.setdefault("game_slots", ["Ori1", "Ori2"])
        return ApSession(self.GID, self.WORLD, maps, "Ori1", "hunter2", **kw)

    @staticmethod
    def scouts(entries):
        """{slot: APScout} -> {slot: (comma-field label, field 5 recipient)}."""
        return {slot: (s.label(), s.to) for slot, s in entries.items()}

    def run_session(self, session, frames):
        sock = FakeSocket(frames)
        try:
            session.run(sock)
        except ConnectionClosed:
            pass
        return sock


class TestHandshake(SessionTestCase):
    def test_connect_message_wire_shape(self):
        session = self.make_session()
        sock = self.run_session(session, [ROOMINFO, [connected()]])
        self.assertEqual(sock.sent[0], [{
            "cmd": "Connect", "password": "hunter2", "game": "Ori DE Rando",
            "name": "Ori1", "uuid": "orirando-1301-1",
            "version": {"class": "Version", "major": 0, "minor": 6, "build": 7},
            "items_handling": 3, "tags": [], "slot_data": False,
        }])
        self.assertTrue(session.authed)
        self.assertEqual(self.statuses, [(self.GID, "connected", None)])

    def test_refused_raises(self):
        session = self.make_session()
        sock = FakeSocket([ROOMINFO, [{"cmd": "ConnectionRefused", "errors": ["InvalidSlot"]}]])
        with self.assertRaises(ApRefused):
            session.run(sock)
        self.assertFalse(session.authed)

    def test_noise_before_roominfo_and_connected_is_skipped(self):
        session = self.make_session()
        sock = self.run_session(session, [
            [{"cmd": "PrintJSON", "data": []}], None, ROOMINFO,
            [{"cmd": "PrintJSON", "data": []}], [connected()]])
        self.assertTrue(session.authed)


class DeathLinkTestCase(SessionTestCase):
    """DeathLink rides the tick as a counter out and a signal in. The two
    things that must never happen: an incoming death emitting an outgoing
    one, and a seed without the option changing behaviour at all."""

    def setUp(self):
        SessionTestCase.setUp(self)
        self.deaths_in = []      # (world, token, source) delivered to a client
        self.tokens = {}
        self._dl_orig = (ap_bridge._bump_death_in, ap_bridge._send_death_signal)
        ap_bridge._bump_death_in = self._bump
        ap_bridge._send_death_signal = lambda gid, world, token, source: (
            self.deaths_in.append((world, token, source)))

    def tearDown(self):
        (ap_bridge._bump_death_in, ap_bridge._send_death_signal) = self._dl_orig
        SessionTestCase.tearDown(self)

    def _bump(self, gid, world):
        self.tokens[world] = self.tokens.get(world, 0) + 1
        return self.tokens[world]

    def make_session(self, death_link=True, **kw):
        session = SessionTestCase.make_session(self, **kw)
        session.maps.death_link = death_link
        session.death_box = ap_bridge._DeathBox()
        return session

    @staticmethod
    def bounced(when, source="Zelda", tags=("DeathLink",), cause="drowned"):
        return {"cmd": "Bounced", "tags": list(tags),
                "data": {"time": when, "source": source, "cause": cause}}

    @staticmethod
    def bounces(sock):
        return [m for frame in sock.sent for m in frame
                if m.get("cmd") == "Bounce"]


class TestDeathLinkTag(DeathLinkTestCase):
    def test_the_tag_is_on_connect_only_when_the_seed_opted_in(self):
        on = self.run_session(self.make_session(True), [ROOMINFO, [connected()]])
        self.assertEqual(on.sent[0][0]["tags"], ["DeathLink"])
        off = self.run_session(self.make_session(False), [ROOMINFO, [connected()]])
        self.assertEqual(off.sent[0][0]["tags"], [])


class TestDeathLinkOut(DeathLinkTestCase):
    def _run(self, session, reports):
        """Drive the outbound half: each report is (total, linked) seen on
        one tick, with a session loop between them."""
        sock = FakeSocket([ROOMINFO, [connected()]] + [None] * (len(reports) + 1))
        try:
            session._handshake(sock)
        except ConnectionClosed:
            pass
        for total, linked in reports:
            session.death_box.set(total, linked)
            session._service_deaths(sock)
        return sock

    def test_the_first_report_is_a_baseline_not_a_death(self):
        """Loading a save with 200 deaths owes the room nothing."""
        sock = self._run(self.make_session(), [(200, 0)])
        self.assertEqual(self.bounces(sock), [])
        self.assertEqual(self.make_session().deaths_seen, None)

    def test_an_increase_sends_one_bounce_in_the_ap_shape(self):
        session = self.make_session()
        sock = self._run(session, [(3, 0), (4, 0)])
        bounces = self.bounces(sock)
        self.assertEqual(len(bounces), 1)
        self.assertEqual(bounces[0]["tags"], ["DeathLink"])
        self.assertEqual(bounces[0]["data"]["source"], "Ori1")
        self.assertIn("cause", bounces[0]["data"])
        self.assertIsInstance(bounces[0]["data"]["time"], float)

    def test_an_unchanged_count_says_nothing(self):
        sock = self._run(self.make_session(), [(3, 0), (3, 0), (3, 0), (3, 0)])
        self.assertEqual(self.bounces(sock), [])

    def test_several_deaths_in_one_tick_are_one_bounce(self):
        """Ori players die constantly; the room wants one death, not five."""
        sock = self._run(self.make_session(), [(3, 0), (8, 0)])
        self.assertEqual(len(self.bounces(sock)), 1)

    def test_a_smaller_count_rebaselines_silently(self):
        """A different save file (or a fresh slot) is not a resurrection."""
        session = self.make_session()
        sock = self._run(session, [(40, 0), (41, 0), (2, 0), (3, 0)])
        self.assertEqual(len(self.bounces(sock)), 2)
        self.assertEqual(session.deaths_seen, 3)

    def test_a_deathlink_death_never_bounces_back_out(self):
        """THE loop guard: total and linked rise together, so the net count
        the room hears about does not move."""
        sock = self._run(self.make_session(), [(3, 0), (4, 1), (5, 2), (6, 3)])
        self.assertEqual(self.bounces(sock), [])

    def test_a_real_death_in_the_same_second_still_goes_out(self):
        """Suppression is arithmetic, not a time window: dying yourself right
        after an incoming death is still your death."""
        sock = self._run(self.make_session(), [(3, 0), (5, 1)])
        self.assertEqual(len(self.bounces(sock)), 1)

    def test_a_seed_without_the_option_never_sends(self):
        sock = self._run(self.make_session(death_link=False), [(3, 0), (99, 0)])
        self.assertEqual(self.bounces(sock), [])

    def test_a_client_that_never_reports_sends_nothing(self):
        session = self.make_session()
        sock = FakeSocket([ROOMINFO, [connected()], None])
        try:
            session._handshake(sock)
        except ConnectionClosed:
            pass
        session._service_deaths(sock)
        self.assertEqual(self.bounces(sock), [])


class TestDeathLinkIn(DeathLinkTestCase):
    def _deliver(self, session, msgs):
        sock = FakeSocket([ROOMINFO, [connected()]] + [[m] for m in msgs])
        try:
            session.run(sock)
        except ConnectionClosed:
            pass
        return sock

    def test_a_bounced_death_reaches_the_client_with_a_fresh_token(self):
        self._deliver(self.make_session(),
                      [self.bounced(100.0), self.bounced(101.0)])
        self.assertEqual(self.deaths_in,
                         [(self.WORLD, 1, "Zelda"), (self.WORLD, 2, "Zelda")])

    def test_a_bounce_without_the_tag_is_not_a_death(self):
        self._deliver(self.make_session(), [self.bounced(100.0, tags=["EnergyLink"])])
        self.assertEqual(self.deaths_in, [])

    def test_our_own_bounce_is_dropped_when_it_comes_back(self):
        """MultiServer fans a Bounce to every tagged client, sender included."""
        session = self.make_session()
        sock = FakeSocket([ROOMINFO, [connected()], None])
        try:
            session._handshake(sock)
        except ConnectionClosed:
            pass
        session.death_box.set(1, 0)
        session._service_deaths(sock)   # baseline
        session.death_box.set(2, 0)
        session._service_deaths(sock)   # our death
        mine = self.bounces(sock)[0]["data"]["time"]
        session._on_bounced({"cmd": "Bounced", "tags": ["DeathLink"],
                             "data": {"time": mine, "source": "Ori1"}})
        self.assertEqual(self.deaths_in, [])

    def test_a_bounce_naming_our_own_slot_is_dropped(self):
        session = self.make_session()
        self._deliver(session, [self.bounced(100.0, source="Ori1")])
        self.assertEqual(self.deaths_in, [])

    def test_a_sibling_ori_world_still_kills_us(self):
        """Two worlds of one Ori game are two AP slots: they deathlink."""
        self._deliver(self.make_session(), [self.bounced(100.0, source="Ori2")])
        self.assertEqual(self.deaths_in, [(self.WORLD, 1, "Ori2")])

    def test_a_seed_without_the_option_ignores_bounces(self):
        self._deliver(self.make_session(death_link=False), [self.bounced(100.0)])
        self.assertEqual(self.deaths_in, [])

    def test_garbage_bounce_data_never_kills_the_session(self):
        session = self.make_session()
        self._deliver(session, [
            {"cmd": "Bounced", "tags": ["DeathLink"], "data": "not a dict"},
            {"cmd": "Bounced", "tags": ["DeathLink"]},
            {"cmd": "Bounced"},
            self.bounced(100.0)])
        self.assertEqual(self.deaths_in, [(self.WORLD, 1, "Zelda")])

    def test_a_hostile_source_name_is_wire_sanitized(self):
        """The name rides a tick signal split on , ; = and |."""
        self._deliver(self.make_session(),
                      [self.bounced(100.0, source="ev;il=name|,x")])
        self.assertEqual(self.deaths_in, [(self.WORLD, 1, "ev il name x")])


class TestDeathCounterParsing(unittest.TestCase):
    def test_shapes(self):
        self.assertEqual(ap_bridge._parse_deaths("7.2"), (7, 2))
        self.assertEqual(ap_bridge._parse_deaths("7"), (7, 0))
        self.assertEqual(ap_bridge._parse_deaths("0.0"), (0, 0))

    def test_junk_is_refused(self):
        for raw in ("", None, "x", "1.x", "-1.0", "1.-2", "1,2"):
            self.assertIsNone(ap_bridge._parse_deaths(raw), repr(raw))

    def test_the_box_holds_a_level(self):
        box = ap_bridge._DeathBox()
        self.assertIsNone(box.read())
        box.set(10, 3)
        box.set(11, 3)
        self.assertEqual(box.read(), 8)

    def test_more_linked_than_total_floors_at_zero(self):
        box = ap_bridge._DeathBox()
        box.set(1, 4)
        self.assertEqual(box.read(), 0)

    def test_note_deaths_is_inert_without_a_bridge(self):
        ap_bridge.note_deaths(4242, 1, "3.0")
        self.assertEqual(ap_bridge._bridges, {})


class TestReconcile(SessionTestCase):
    def test_outbox_diff_vs_room_checked(self):
        self.shadow = {524541, 524542}
        session = self.make_session()
        sock = self.run_session(session, [ROOMINFO, [connected(checked=[524542])]])
        self.assertIn([{"cmd": "LocationChecks", "locations": [524541]}], sock.sent)
        self.assertEqual(session.checked, {524541, 524542})

    def test_nothing_pending_sends_no_checks(self):
        self.shadow = {524542}
        session = self.make_session()
        sock = self.run_session(session, [ROOMINFO, [connected(checked=[524542])]])
        self.assertEqual([m for m in sock.sent if m[0].get("cmd") == "LocationChecks"], [])

    def test_full_replay_in_connected_frame(self):
        # fresh connect auto-resends everything from index 0, same frame
        session = self.make_session()
        self.run_session(session, [ROOMINFO, [connected(), {
            "cmd": "ReceivedItems", "index": 0, "items": [
                {"item": 524288, "location": 10, "player": 2, "flags": 1},
                {"item": 524349, "location": 11, "player": 2, "flags": 0},
                {"item": 524288, "location": 12, "player": 1, "flags": 1},
            ]}]])
        # deterministic fill: lowest matching manifest slot first
        self.assertEqual(self.grants, [(self.GID, self.WORLD, [0, 1, 3])])
        self.assertEqual(self.recvs, [(self.GID, self.WORLD, 3)])

    def test_goal_world_sends_statusupdate_once(self):
        self.goals = [1]
        goal_event = threading.Event()
        goal_event.set()  # even a pre-set event may not double-send
        session = self.make_session(goal_event=goal_event)
        sock = self.run_session(session, [ROOMINFO, [connected()], None])
        goal_msgs = [m for m in sock.sent if m[0].get("cmd") == "StatusUpdate"]
        self.assertEqual(goal_msgs, [[{"cmd": "StatusUpdate", "status": 30}]])

    def test_goal_event_mid_session(self):
        goal_event = threading.Event()
        session = self.make_session(goal_event=goal_event)
        sock = FakeSocket([ROOMINFO, [connected()], None])
        goal_event.set()
        try:
            session.run(sock)
        except ConnectionClosed:
            pass
        self.assertIn([{"cmd": "StatusUpdate", "status": 30}], sock.sent)


class TestSteadyState(SessionTestCase):
    def test_index_mismatch_sends_sync_and_drops_batch(self):
        session = self.make_session()
        sock = self.run_session(session, [ROOMINFO, [connected()], [{
            "cmd": "ReceivedItems", "index": 5,
            "items": [{"item": 524288, "location": 10, "player": 2}]}]])
        self.assertIn([{"cmd": "Sync"}], sock.sent)
        self.assertEqual(self.grants, [])
        self.assertEqual(session.recv_count, 0)

    def test_index_zero_resets_fill_state(self):
        session = self.make_session()
        batch = {"cmd": "ReceivedItems", "index": 0,
                 "items": [{"item": 524288, "location": 10, "player": 2}]}
        self.run_session(session, [ROOMINFO, [connected()], [batch], [dict(batch)]])
        # replayed from scratch: same slot both times (idempotent downstream)
        self.assertEqual(self.grants, [(self.GID, self.WORLD, [0, 0])])
        self.assertEqual(session.recv_count, 1)

    def test_messages_in_one_window_become_one_grant(self):
        """A room's goal handler collects then releases, so the finisher gets
        one ReceivedItems per source world microseconds apart. One
        transaction means one tick means one message in game."""
        session = self.make_session()
        self.run_session(session, [ROOMINFO, [connected()],
                                   [{"cmd": "ReceivedItems", "index": 0,
                                     "items": [{"item": 524288, "location": 10, "player": 2}]}],
                                   [{"cmd": "ReceivedItems", "index": 1,
                                     "items": [{"item": 524288, "location": 12, "player": 2}]}]])
        self.assertEqual(self.grants, [(self.GID, self.WORLD, [0, 3])])
        self.assertEqual(self.recvs, [(self.GID, self.WORLD, 2)])

    def test_a_grant_names_who_found_it(self):
        """The seed cannot carry this: which player found an item is only
        known when Archipelago hands it over."""
        session = self.make_session()
        self.run_session(session, [
            ROOMINFO,
            [connected(slot_info={"1": {"name": "Ori1", "game": "Ori DE Rando"},
                                  "2": {"name": "Ori2", "game": "Ori DE Rando"},
                                  "3": {"name": "TestQuest", "game": "Clique"}},
                       players=[{"slot": 3, "alias": "Questy", "name": "TestQuest"}])],
            [{"cmd": "ReceivedItems", "index": 0, "items": [
                {"item": 524288, "location": 10, "player": 2},   # sibling world
                {"item": 524349, "location": 11, "player": 3},   # foreign game
                {"item": 524288, "location": 12, "player": 1}]}]])  # ourselves
        self.assertEqual(self.grants, [(self.GID, self.WORLD, [0, 1, 3])])
        self.assertEqual(self.senders[-1], {0: "P2", 1: "Questy", 3: ""})

    def test_unknown_item_consumes_index_without_grant(self):
        session = self.make_session()
        self.run_session(session, [ROOMINFO, [connected()], [{
            "cmd": "ReceivedItems", "index": 0, "items": [{"item": 999999}]}]])
        self.assertEqual(self.grants, [])
        self.assertEqual(self.recvs, [(self.GID, self.WORLD, 1)])

    def test_slot_overflow_is_skipped(self):
        session = self.make_session()
        items = [{"item": 524349, "location": n} for n in (1, 2)]  # one EX slot only
        self.run_session(session, [ROOMINFO, [connected()],
                                   [{"cmd": "ReceivedItems", "index": 0, "items": items}]])
        self.assertEqual(self.grants, [(self.GID, self.WORLD, [1])])
        self.assertEqual(session.recv_count, 2)

    def test_roomupdate_extends_checked(self):
        self.shadow = {524541}
        session = self.make_session()
        sock = self.run_session(session, [ROOMINFO, [connected()],
                                          [{"cmd": "RoomUpdate", "checked_locations": [524542]}]])
        self.assertEqual(session.checked, {524541, 524542})
        # a later poll has nothing new to send
        sock2 = FakeSocket([])
        session._poll_outbox(sock2)
        self.assertEqual(sock2.sent, [])

    def test_poll_sends_only_new_bits(self):
        self.shadow = {524541}
        session = self.make_session()
        self.run_session(session, [ROOMINFO, [connected()]])
        self.shadow = {524541, 524542}
        sock2 = FakeSocket([])
        session._poll_outbox(sock2)
        self.assertEqual(sock2.sent, [[{"cmd": "LocationChecks", "locations": [524542]}]])

    def test_stop_event_ends_run_cleanly(self):
        stop = threading.Event()
        session = self.make_session(stop_event=stop)

        class StopAfterHandshake(FakeSocket):
            def receive(s, timeout=None):
                frame = FakeSocket.receive(s, timeout)
                if not s.script:  # handshake consumed: request the stop
                    stop.set()
                return frame

        sock = StopAfterHandshake([ROOMINFO, [connected()]])
        session.run(sock)  # returns instead of raising ConnectionClosed
        self.assertTrue(session.authed)


class TestScouting(SessionTestCase):
    """Display names: LocationScouts -> LocationInfo -> GetDataPackage ->
    {shadow slot: label}. make_session's world 1 reserves ap locations
    524541 (slot 0) and 524542 (slot 1)."""

    LOCS = [524541, 524542]
    # the room's own view: slot 1 is us, 2 is the other Ori world, 3 is a
    # different game entirely (so its item ids live in ITS datapackage)
    SLOT_INFO = {"1": {"class": "NetworkSlot", "name": "Ori1", "game": "Ori DE Rando", "type": 1},
                 "2": {"class": "NetworkSlot", "name": "Ori2", "game": "Ori DE Rando", "type": 1},
                 "3": {"class": "NetworkSlot", "name": "TestQuest", "game": "Clique", "type": 1}}
    PLAYERS = [{"class": "NetworkPlayer", "team": 0, "slot": 1, "alias": "Ori1", "name": "Ori1"},
               {"class": "NetworkPlayer", "team": 0, "slot": 2, "alias": "Ori2", "name": "Ori2"},
               {"class": "NetworkPlayer", "team": 0, "slot": 3, "alias": "Questy", "name": "TestQuest"}]
    CHECKSUMS = {"Ori DE Rando": "oridesum", "Clique": "cliquesum"}

    def setUp(self):
        SessionTestCase.setUp(self)
        ap_bridge._dp_cache.clear()

    def tearDown(self):
        ap_bridge._dp_cache.clear()
        SessionTestCase.tearDown(self)

    def hello(self, missing=None):
        return [roominfo(self.CHECKSUMS),
                [connected(missing=self.LOCS if missing is None else missing,
                           slot_info=self.SLOT_INFO, players=self.PLAYERS)]]

    @staticmethod
    def sent_of(sock, cmd):
        return [m[0] for m in sock.sent if m[0].get("cmd") == cmd]

    @staticmethod
    def location_info(entries):
        # NetworkItem serializes as a dict (NetUtils._scan_for_TypedTuples);
        # in LocationInfo 'player' is the RECEIVING slot
        return {"cmd": "LocationInfo", "locations": [
            {"class": "NetworkItem", "item": item, "location": loc, "player": owner, "flags": flags}
            for (loc, item, owner, flags) in entries]}

    def test_scout_request_shape(self):
        sock = self.run_session(self.make_session(), self.hello())
        self.assertEqual(self.sent_of(sock, "LocationScouts"),
                         [{"cmd": "LocationScouts", "locations": [524541, 524542],
                           "create_as_hint": 0}])

    def test_scout_only_asks_about_locations_the_room_says_are_ours(self):
        # a mismatched room (different seed) would otherwise KeyError inside
        # its own LocationScouts handler
        sock = self.run_session(self.make_session(), self.hello(missing=[524542]))
        self.assertEqual(self.sent_of(sock, "LocationScouts")[0]["locations"], [524542])

    def test_no_reserved_locations_sends_no_scout(self):
        sock = self.run_session(self.make_session(), self.hello(missing=[]))
        self.assertEqual(self.sent_of(sock, "LocationScouts"), [])

    def test_no_reserved_locations_publishes_a_complete_result(self):
        # otherwise the panel waits forever for names this world will never have
        self.run_session(self.make_session(), self.hello(missing=[]))
        self.assertEqual(self.names, [(self.GID, self.WORLD, 0, {})])

    def test_scout_chunks_a_large_world(self):
        maps = GameMaps(2, {1: {i: 900000 + i for i in range(250)}, 2: {}},
                        {1: {}, 2: {}})
        session = ApSession(self.GID, self.WORLD, maps, "Ori1", None)
        sock = self.run_session(session, [
            roominfo(self.CHECKSUMS),
            [connected(missing=[900000 + i for i in range(250)],
                       slot_info=self.SLOT_INFO, players=self.PLAYERS)]])
        scouts = self.sent_of(sock, "LocationScouts")
        self.assertEqual([len(s["locations"]) for s in scouts], [100, 100, 50])
        self.assertEqual(sorted(l for s in scouts for l in s["locations"]),
                         [900000 + i for i in range(250)])

    def test_datapackage_requested_for_exactly_the_owning_games(self):
        sock = self.run_session(self.make_session(), self.hello() + [
            [self.location_info([(524541, 77, 2, 1), (524542, 42, 3, 0)])]])
        self.assertEqual(self.sent_of(sock, "GetDataPackage"),
                         [{"cmd": "GetDataPackage", "games": ["Clique", "Ori DE Rando"]}])

    def test_names_resolve_across_games(self):
        sock = self.run_session(self.make_session(), self.hello() + [
            [self.location_info([(524541, 77, 2, 1), (524542, 42, 3, 0)])],
            [{"cmd": "DataPackage", "data": {"games": {
                "Ori DE Rando": {"checksum": "oridesum", "item_name_to_id": {"Bash": 77}},
                "Clique": {"checksum": "cliquesum", "item_name_to_id": {"A Click": 42}}}}}]])
        # a sibling Ori world becomes 'P<world>', which the client turns into
        # that player's own name; a foreign game keeps its room name
        self.assertEqual(self.scouts(self.names[-1][3]),
                         {0: ("Bash (Ori2)", "P2"),
                          1: ("A Click (Questy)", "Questy")})
        self.assertEqual(self.names[-1][:3], (self.GID, self.WORLD, 2))
        self.assertEqual(self.name_slots[-1], 1)  # our own room slot, for the join
        # nothing extra went out once both packages were in hand
        self.assertEqual(len(self.sent_of(sock, "GetDataPackage")), 1)

    def test_our_own_items_name_our_own_world(self):
        # items_handling 0b011 means the room hands our own finds back to us
        self.run_session(self.make_session(), self.hello() + [
            [self.location_info([(524541, 77, 1, 1)])],
            [{"cmd": "DataPackage", "data": {"games": {
                "Ori DE Rando": {"checksum": "oridesum", "item_name_to_id": {"Bash": 77}}}}}]])
        self.assertEqual(self.scouts(self.names[-1][3]), {0: ("Bash (Ori1)", "P1")})

    def test_a_second_ori_game_in_the_room_is_not_a_sibling(self):
        """Slot names, not the game name, decide who belongs to this game:
        another orirando game's world must not be printed as one of ours."""
        session = self.make_session(game_slots=["Ori1", "Ori2"])
        self.run_session(session, [
            roominfo(self.CHECKSUMS),
            [connected(missing=self.LOCS,
                       slot_info={"1": {"name": "Ori1", "game": "Ori DE Rando"},
                                  "2": {"name": "Stranger", "game": "Ori DE Rando"}},
                       players=[{"slot": 2, "alias": "Stranger", "name": "Stranger"}])],
            [self.location_info([(524541, 77, 2, 1)])],
            [{"cmd": "DataPackage", "data": {"games": {
                "Ori DE Rando": {"checksum": "oridesum", "item_name_to_id": {"Bash": 77}}}}}]])
        self.assertEqual(self.scouts(self.names[-1][3]), {0: ("Bash (Stranger)", "Stranger")})

    def test_an_alias_that_mimics_a_slot_name_is_not_a_sibling(self):
        """Aliases are player-editable, so the join reads slot_info's raw
        name; otherwise anyone could rename themselves into our game."""
        self.run_session(self.make_session(), [
            roominfo(self.CHECKSUMS),
            [connected(missing=self.LOCS,
                       slot_info={"1": {"name": "Ori1", "game": "Ori DE Rando"},
                                  "3": {"name": "TestQuest", "game": "Clique"}},
                       players=[{"slot": 3, "alias": "Ori2", "name": "TestQuest"}])],
            [self.location_info([(524541, 42, 3, 0)])],
            [{"cmd": "DataPackage", "data": {"games": {
                "Clique": {"checksum": "cliquesum", "item_name_to_id": {"A Click": 42}}}}}]])
        self.assertEqual(self.scouts(self.names[-1][3]), {0: ("A Click (Ori2)", "Ori2")})

    def test_alias_beats_slot_name(self):
        # slot_info calls slot 3 "TestQuest"; the room's players list aliases
        # it to "Questy", which is what everyone in the room sees
        self.run_session(self.make_session(), self.hello() + [
            [self.location_info([(524541, 42, 3, 0)])],
            [{"cmd": "DataPackage", "data": {"games": {
                "Clique": {"checksum": "cliquesum", "item_name_to_id": {"A Click": 42}}}}}]])
        self.assertEqual(self.scouts(self.names[-1][3]), {0: ("A Click (Questy)", "Questy")})

    def test_unknown_item_or_owner_keeps_its_placeholder(self):
        self.run_session(self.make_session(), self.hello() + [
            # 999 isn't in Clique's package; slot 8 isn't in the room at all
            [self.location_info([(524541, 999, 3, 0), (524542, 42, 8, 0)])],
            [{"cmd": "DataPackage", "data": {"games": {
                "Clique": {"checksum": "cliquesum", "item_name_to_id": {"A Click": 42}}}}}]])
        self.assertEqual(self.names[-1], (self.GID, self.WORLD, 2, {}))

    def test_room_that_never_answers_the_scout_is_harmless(self):
        session = self.make_session()
        self.run_session(session, self.hello() + [None, None])
        self.assertTrue(session.authed)
        self.assertEqual(self.names, [])
        self.assertIsNone(session.named)

    def test_room_that_ignores_getdatapackage_publishes_nothing(self):
        # a blank must never overwrite an earlier connection's good names
        session = self.make_session()
        self.run_session(session, self.hello() + [
            [self.location_info([(524541, 77, 2, 1)])], None, None])
        self.assertEqual(self.names, [])
        self.assertEqual(session.dp_pending, {"Ori DE Rando"})

    def test_datapackage_cached_by_checksum_across_reconnects(self):
        frames = self.hello() + [
            [self.location_info([(524541, 77, 2, 1)])],
            [{"cmd": "DataPackage", "data": {"games": {
                "Ori DE Rando": {"checksum": "oridesum", "item_name_to_id": {"Bash": 77}}}}}]]
        self.run_session(self.make_session(), list(frames))
        sock2 = self.run_session(self.make_session(), list(frames[:3]))
        self.assertEqual(self.sent_of(sock2, "GetDataPackage"), [])
        self.assertEqual(self.scouts(self.names[-1][3]), {0: ("Bash (Ori2)", "P2")})

    def test_new_checksum_refetches(self):
        self.run_session(self.make_session(), self.hello() + [
            [self.location_info([(524541, 77, 2, 1)])],
            [{"cmd": "DataPackage", "data": {"games": {
                "Ori DE Rando": {"checksum": "oridesum", "item_name_to_id": {"Bash": 77}}}}}]])
        sock2 = self.run_session(self.make_session(), [
            roominfo({"Ori DE Rando": "REGENERATED"}),
            [connected(missing=self.LOCS, slot_info=self.SLOT_INFO, players=self.PLAYERS)],
            [self.location_info([(524541, 77, 2, 1)])]])
        self.assertEqual(self.sent_of(sock2, "GetDataPackage"),
                         [{"cmd": "GetDataPackage", "games": ["Ori DE Rando"]}])

    def test_hostile_name_is_sanitized_but_keeps_its_commas(self):
        hostile = "Bow|Pipe, Arrows #3 $green$ /slash/ 100% @red@"
        self.run_session(self.make_session(), self.hello() + [
            [self.location_info([(524541, 77, 3, 0)])],
            [{"cmd": "DataPackage", "data": {"games": {
                "Clique": {"checksum": "cliquesum", "item_name_to_id": {hostile: 77}}}}}]])
        label = self.names[-1][3][0].label()
        for bad in "|/\\?#%$*@\r\n":
            self.assertNotIn(bad, label, "%r survived sanitization in %r" % (bad, label))
        # ',' is the one separator that stays: the name is the LAST field of a
        # maxsplit-bounded value on both sides of the wire
        self.assertEqual(label, "Bow Pipe, Arrows 3 green slash 100 red (Questy)")

    def test_field_five_drops_the_commas_the_label_keeps(self):
        """Field 5 is ';'-split and rides the apfrom signal's charset too, so
        the recipient loses separators the comma-bounded label may keep."""
        self.run_session(self.make_session(), [
            roominfo(self.CHECKSUMS),
            [connected(missing=self.LOCS,
                       slot_info={"1": {"name": "Ori1", "game": "Ori DE Rando"},
                                  "3": {"name": "TestQuest", "game": "Clique"}},
                       players=[{"slot": 3, "alias": "Ev,il;Na=me|X", "name": "TestQuest"}])],
            [self.location_info([(524541, 42, 3, 0)])],
            [{"cmd": "DataPackage", "data": {"games": {
                "Clique": {"checksum": "cliquesum", "item_name_to_id": {"A Click": 42}}}}}]])
        scout = self.names[-1][3][0]
        self.assertEqual(scout.to, "Ev il Na me X")
        for bad in ",;=|":
            self.assertNotIn(bad, scout.to)

    def test_hostile_name_still_renders_a_four_field_seed_line(self):
        # the whole point: '|' would push the zone out of line.Split('|')
        from ap_models import ap_display_name
        label = ap_display_name("Evil|Name, Mk|II", "Bad|Guy")
        line = "919908|MW|%s,%s,%s|%s" % (3, 7, label, "Grove")
        self.assertEqual(len(line.split("|")), 4)
        loc, code, value, zone = line.split("|")
        owner, slot, name = value.split(",", 2)
        self.assertEqual((loc, code, owner, slot, zone),
                         ("919908", "MW", "3", "7", "Grove"))
        self.assertEqual(name, "Evil Name, Mk II (Bad Guy)")

    def test_garbage_room_data_never_kills_the_session(self):
        # names are cosmetic: nothing the room says about them may stop items
        session = self.make_session()
        sock = self.run_session(session, [
            roominfo("not a dict at all"),
            [connected(missing=self.LOCS, slot_info={"x": 5, "2": None, "3": []},
                       players=["nope", {"slot": "?"}])],
            [{"cmd": "LocationInfo", "locations": ["junk", {"item": "x"}, None]}],
            [{"cmd": "DataPackage", "data": {"games": {"Clique": None}}}],
            [{"cmd": "ReceivedItems", "index": 0,
              "items": [{"item": 524288, "location": 10, "player": 2}]}]])
        self.assertTrue(session.authed)
        # the item still landed
        self.assertEqual(self.grants, [(self.GID, self.WORLD, [0])])
        # every scouted entry was unusable, so it reports an honest 0 of 2
        self.assertEqual(self.names, [(self.GID, self.WORLD, 2, {})])
        self.assertIn([{"cmd": "LocationScouts", "locations": [524541, 524542],
                        "create_as_hint": 0}], sock.sent)

    def test_transport_failure_inside_the_name_path_still_propagates(self):
        # a dead socket is the reconnect loop's business, not something the
        # cosmetic guard may swallow
        class DeadOnScout(FakeSocket):
            def send(s, data):
                if "LocationScouts" in data:
                    raise ConnectionClosed()
                FakeSocket.send(s, data)

        sock = DeadOnScout(self.hello())
        with self.assertRaises(ConnectionClosed):
            self.make_session().run(sock)

    def test_every_connection_rescouts(self):
        # the loop builds a fresh ApSession per attempt; each must re-ask, so
        # a room swap or a re-fill can never leave stale names behind
        for _ in range(2):
            sock = self.run_session(self.make_session(), self.hello())
            self.assertEqual(len(self.sent_of(sock, "LocationScouts")), 1)


class HintTestCase(SessionTestCase):
    """Progressive hints. World 1 exports one Water Vein (slot 5), two Glades
    Pool keystones (slots 6 and 7) and one Stomp (slot 8); slot 1 is a plain
    experience export, i.e. something no reveal may ever buy."""

    WV, KS, STOMP = 524299, 524324, 524291     # EV|0, RB|300, SK|4 ap ids
    HINT_KEYS = {5: ("EV", "0"), 6: ("RB", "300"), 7: ("RB", "300"), 8: ("SK", "4")}
    GRANTS = {("EX", "50"): [1], ("EV", "0"): [5], ("RB", "300"): [6, 7], ("SK", "4"): [8]}
    SLOT_INFO = {"1": {"name": "Ori1", "game": "Ori DE Rando"},
                 "2": {"name": "Ori2", "game": "Ori DE Rando"},
                 "3": {"name": "TestQuest", "game": "Clique"}}
    PLAYERS = [{"slot": 3, "alias": "Questy", "name": "TestQuest"}]
    # 100 locations x 10% -> a hint costs 10 points
    OURS = list(range(600000, 600100))

    def setUp(self):
        SessionTestCase.setUp(self)
        ap_bridge._dp_cache.clear()

    def tearDown(self):
        ap_bridge._dp_cache.clear()
        SessionTestCase.tearDown(self)

    def make_session(self, **kw):
        maps = GameMaps(2, {1: {0: 524541, 1: 524542}, 2: {3: 524543}},
                        {1: self.GRANTS, 2: {}},
                        zones={1: {0: "Glades", 1: "Grove"}, 2: {3: "Valley"}},
                        hint_keys={1: dict(self.HINT_KEYS), 2: {}})
        kw.setdefault("game_slots", ["Ori1", "Ori2"])
        kw.setdefault("hint_box", ap_bridge._HintBox())
        return ApSession(self.GID, self.WORLD, maps, "Ori1", None, **kw)

    def hello(self, hint_points=100, hint_cost=10, held=()):
        """Handshake + the room's answer about the hints it already holds.
        Nothing is ever bought before that answer lands."""
        room = dict(ROOMINFO[0])
        room["hint_cost"] = hint_cost
        room["datapackage_checksums"] = {"Ori DE Rando": "oridesum", "Clique": "cliquesum"}
        return [[room], [connected(missing=self.OURS, slot_info=self.SLOT_INFO,
                                   players=self.PLAYERS, hint_points=hint_points)],
                [self.retrieved(1, list(held))]]

    def wanting(self, slots, **kw):
        session = self.make_session(**kw)
        session.hint_box.add(slots)
        return session

    @staticmethod
    def says(sock):
        return [m["text"] for f in sock.sent for m in f if m.get("cmd") == "Say"]

    @staticmethod
    def sent_of(sock, cmd):
        return [m for f in sock.sent for m in f if m.get("cmd") == cmd]

    @staticmethod
    def hint_msg(receiving, item, finder, location):
        return {"cmd": "PrintJSON", "type": "Hint", "receiving": receiving, "found": False,
                "item": {"class": "NetworkItem", "item": item, "location": location,
                         "player": finder, "flags": 1}}

    @staticmethod
    def retrieved(slot, hints):
        return {"cmd": "Retrieved", "keys": {"_read_hints_0_%s" % slot: hints}}

    @staticmethod
    def stored_hint(receiving, finder, location, item):
        return {"class": "Hint", "receiving_player": receiving, "finding_player": finder,
                "location": location, "item": item, "found": False,
                "entrance": "", "item_flags": 1, "status": 0}

    def clique_package(self, locations):
        return [{"cmd": "DataPackage", "data": {"games": {"Clique": {
            "checksum": "cliquesum", "item_name_to_id": {"A Click": 42},
            "location_name_to_id": locations}}}}]


class TestHintGates(HintTestCase):
    """Nothing reaches the room until every free answer is exhausted and the
    slot can actually pay -- a '!hint' is broadcast to the whole room and
    spends points the player can never earn back."""

    def test_the_room_is_asked_for_its_own_hint_list_on_connect(self):
        sock = self.run_session(self.make_session(), self.hello())
        self.assertEqual(self.sent_of(sock, "Get"),
                         [{"cmd": "Get", "keys": ["_read_hints_0_1"]}])
        self.assertEqual(self.sent_of(sock, "SetNotify"),
                         [{"cmd": "SetNotify", "keys": ["_read_hints_0_1"]}])

    def test_a_slot_outside_the_three_reveals_never_reaches_the_room(self):
        # slot 1 is an experience export: the client may ask, the server may
        # not buy, and a modified client gets exactly the same answer
        session = self.wanting([1])
        sock = self.run_session(session, self.hello())
        self.assertEqual(self.says(sock), [])
        self.assertEqual(self.claims, [])
        self.assertEqual(session.hint_wanted, set())

    def test_an_unaffordable_hint_is_deferred_without_a_word(self):
        session = self.wanting([5])
        sock = self.run_session(session, self.hello(hint_points=9))
        self.assertEqual(self.says(sock), [])
        self.assertEqual(self.hint_writes, [(5, "d", "")])
        self.assertEqual(self.published, [])
        # no live point count in the text: signal_send dedups on an exact
        # match, so a balance that ticks up would stack a line per deferral
        self.assertEqual(self.notices, ["Find more Archipelago checks to afford this hint"])

    def test_hint_cost_mirrors_the_rooms_own_formula(self):
        session = self.make_session()
        self.run_session(session, self.hello(hint_cost=10))
        self.assertEqual(session._hint_cost(), 10)     # 10% of 100 locations
        session.hint_cost_pct = 0
        self.assertEqual(session._hint_cost(), 0)      # free hints
        session.hint_cost_pct = 1
        self.assertEqual(session._hint_cost(), 1)      # the max(1, ...) floor

    def test_free_hints_are_affordable_at_zero_points(self):
        session = self.wanting([5])
        sock = self.run_session(session, self.hello(hint_points=0, hint_cost=0))
        self.assertEqual(self.says(sock), ["!hint Water Vein"])

    def test_the_affordability_notice_is_rate_limited_per_world(self):
        self.run_session(self.wanting([5, 8]), self.hello(hint_points=0))
        self.assertEqual(len(self.notices), 1)
        self.assertEqual(sorted(w[0] for w in self.hint_writes), [5, 8])

    def test_one_purchase_is_in_flight_at_a_time(self):
        # a CommandResult carries no correlation id, so two open purchases
        # would make an affordability refusal ambiguous
        sock = self.run_session(self.wanting([5, 8]), self.hello())
        self.assertEqual(self.says(sock), ["!hint Water Vein"])

    def test_a_record_that_refuses_the_claim_stops_the_purchase(self):
        self.claim_ok = False
        sock = self.run_session(self.wanting([5]), self.hello())
        self.assertEqual(self.says(sock), [])

    def test_the_claim_is_written_before_the_room_is_asked(self):
        session = self.wanting([5])
        order = []
        self._claim_inner = self._claim
        ap_bridge._claim_hint = lambda *a, **k: (order.append("claim")
                                                 or self._claim_inner(*a, **k))
        real_send = ap_bridge._send
        ap_bridge._send = lambda sock, msgs: (
            order.append("say") if msgs[0].get("cmd") == "Say" else None) or real_send(sock, msgs)
        try:
            self.run_session(session, self.hello())
        finally:
            ap_bridge._send = real_send
        self.assertEqual(order, ["claim", "say"])

    def test_a_multi_copy_item_may_never_reclaim_a_stale_purchase(self):
        # a repeat '!hint' for a 2-key door buys the NEXT copy and charges
        # again, so an ambiguous outcome must never be retried
        self.run_session(self.wanting([6]), self.hello())
        self.assertEqual(self.claims, [(6, self.KS, False)])
        self.claims = []
        self.run_session(self.wanting([5]), self.hello())
        self.assertEqual(self.claims, [(5, self.WV, True)])   # singleton: safe

    def test_a_resolved_slot_is_answered_from_storage(self):
        self.hint_rows = {5: {"s": "r", "t": "Questy Chest 4", "a": self.WV}}
        sock = self.run_session(self.wanting([5]), self.hello())
        self.assertEqual(self.says(sock), [])
        self.assertEqual(self.claims, [])
        self.assertEqual(self.published, [{5: "Questy Chest 4"}])

    def test_a_deferred_slot_retries_when_the_room_pushes_more_points(self):
        session = self.wanting([5])
        sock = self.run_session(session, self.hello(hint_points=0) + [
            [{"cmd": "RoomUpdate", "hint_points": 40}],
            [{"cmd": "PrintJSON", "type": "Hint", "receiving": 1, "found": False,
              "item": {"item": self.WV, "location": 524543, "player": 2, "flags": 1}}]])
        self.assertEqual(session.hint_points, 40)
        # the retry rides the next Hint-driven service pass, not a new Say:
        # the room answered while we were still deferred
        self.assertEqual(self.published, [{5: "P2 Valley"}])


class TestHintFreeAnswers(HintTestCase):
    """A hint we can derive costs nothing and must never be bought."""

    def test_a_key_the_room_left_in_an_ori_world_comes_from_our_own_scouts(self):
        from ap_models import APScout
        # world 2's reserved slot 3 holds OUR Water Vein: every world scouts
        # its own locations, so the K rows together already place it
        self.scouts_by_world = {1: ({}, 1),
                                2: ({3: APScout("Water Vein", "Ori1", "P1", self.WV, 1)}, 2)}
        sock = self.run_session(self.wanting([5]), self.hello())
        self.assertEqual(self.says(sock), [])
        self.assertEqual(self.published, [{5: "P2 Valley"}])
        self.assertEqual(self.hint_writes, [(5, "r", "P2 Valley")])

    def test_a_hint_the_room_already_holds_is_never_bought(self):
        sock = self.run_session(self.wanting([5]),
                                self.hello(held=[self.stored_hint(1, 2, 524543, self.WV)]))
        self.assertEqual(self.says(sock), [])
        self.assertEqual(self.published, [{5: "P2 Valley"}])

    def test_a_hint_for_someone_else_is_not_ours(self):
        sock = self.run_session(self.wanting([5]),
                                self.hello(held=[self.stored_hint(2, 2, 524543, self.WV)]))
        self.assertEqual(self.says(sock), ["!hint Water Vein"])

    def test_two_copies_are_answered_in_slot_order(self):
        from ap_models import APScout
        self.scouts_by_world = {
            1: ({0: APScout("Glades Pool Keystone", "Ori1", "P1", self.KS, 1)}, 1),
            2: ({3: APScout("Glades Pool Keystone", "Ori1", "P1", self.KS, 1)}, 2)}
        sock = self.run_session(self.wanting([6, 7]), self.hello())
        self.assertEqual(self.says(sock), [])
        self.assertEqual(self.published, [{6: "P1 Glades"}, {7: "P2 Valley"}])

    def test_a_scouted_copy_and_a_hinted_copy_are_one_copy(self):
        from ap_models import APScout
        self.scouts_by_world = {1: ({}, 1),
                                2: ({3: APScout("Water Vein", "Ori1", "P1", self.WV, 1)}, 2)}
        sock = self.run_session(self.wanting([5]),
                                self.hello(held=[self.stored_hint(1, 2, 524543, self.WV)]))
        self.assertEqual(self.says(sock), [])
        self.assertEqual(self.published, [{5: "P2 Valley"}])


class TestHintPurchase(HintTestCase):
    def test_a_purchase_says_hint_once_and_publishes_the_answer(self):
        sock = self.run_session(self.wanting([5]), self.hello() + [
            [self.hint_msg(1, self.WV, 3, 99)],
            self.clique_package({"Overworld Chest 12": 99})])
        self.assertEqual(self.says(sock), ["!hint Water Vein"])
        self.assertEqual(self.published, [{5: "Questy Overworld Chest 12"}])
        self.assertEqual(self.hint_writes[-1], (5, "r", "Questy Overworld Chest 12"))

    def test_a_sibling_world_reads_exactly_like_a_baked_clue(self):
        # 'P2 Valley' is what annotate would have written at download time,
        # and the client turns P2 into that player's own name
        sock = self.run_session(self.wanting([5]), self.hello() + [
            [self.hint_msg(1, self.WV, 2, 524543)]])
        self.assertEqual(self.published, [{5: "P2 Valley"}])
        self.assertEqual(self.sent_of(sock, "GetDataPackage"), [])

    def test_the_location_name_is_fetched_before_anything_is_published(self):
        sock = self.run_session(self.wanting([5]), self.hello() + [
            [self.hint_msg(1, self.WV, 3, 99)]])
        self.assertEqual(self.sent_of(sock, "GetDataPackage"),
                         [{"cmd": "GetDataPackage", "games": ["Clique"]}])
        self.assertEqual(self.published, [])       # a half-formed hint is not an answer

    def test_a_hint_about_another_item_is_not_our_answer(self):
        self.run_session(self.wanting([5]), self.hello() + [
            [self.hint_msg(1, self.STOMP, 2, 524543)]])
        self.assertEqual(self.published, [])

    def test_cannot_afford_defers_the_slot_that_was_in_flight(self):
        sock = self.run_session(self.wanting([5]), self.hello() + [
            [{"cmd": "PrintJSON", "type": "CommandResult", "data": [
                {"text": "You can't afford the hint. You have 4 points and need at least 10."}]}]])
        self.assertEqual(self.says(sock), ["!hint Water Vein"])
        self.assertEqual([w[1] for w in self.hint_writes], ["d"])
        self.assertEqual(self.published, [])

    def test_a_hostile_room_cannot_corrupt_the_tick_line(self):
        sock = self.run_session(self.wanting([5]), [
            [dict(ROOMINFO[0], hint_cost=10,
                  datapackage_checksums={"Clique": "cliquesum"})],
            [connected(missing=self.OURS, hint_points=100,
                       slot_info={"1": {"name": "Ori1", "game": "Ori DE Rando"},
                                  "3": {"name": "TestQuest", "game": "Clique"}},
                       players=[{"slot": 3, "alias": "Ev,il;Na=me|X", "name": "TestQuest"}])],
            [self.retrieved(1, [])],
            [self.hint_msg(1, self.WV, 3, 99)],
            self.clique_package({"Chest, in the |wall| = here": 99})])
        text = self.published[-1][5]
        for bad in ",;=|":
            self.assertNotIn(bad, text)
        self.assertLessEqual(len(text), ap_bridge.HINT_TEXT_MAX)
        self.assertEqual(text, "Ev il Na me X Chest in the wall here")
        self.assertEqual(self.says(sock), ["!hint Water Vein"])

    def test_a_room_that_never_answers_leaves_the_claim_standing(self):
        session = self.wanting([5])
        sock = self.run_session(session, self.hello() + [None, None])
        self.assertEqual(self.says(sock), ["!hint Water Vein"])
        self.assertEqual(self.published, [])
        # PENDING is deliberately not released: the purchase may have gone
        # through, and buying it again would charge twice
        self.assertEqual([w for w in self.hint_writes if w[1] != "p"], [])


class TestHintRequestChannel(unittest.TestCase):
    """The tick's 'aph' field. Every guard here also has to make the field
    free for the games that never send it."""

    def test_slots_parse_from_the_dot_separated_form(self):
        self.assertEqual(ap_bridge._parse_hint_slots("5.6.204"), {5, 6, 204})

    def test_junk_and_out_of_range_slots_are_dropped(self):
        self.assertEqual(ap_bridge._parse_hint_slots("5..x.-1.256.7"), {5, 7})

    def test_a_flood_cannot_grow_the_queue(self):
        raw = ".".join(str(i) for i in range(200))
        self.assertLessEqual(len(ap_bridge._parse_hint_slots(raw)), ap_bridge.HINT_QUEUE_MAX)
        box = ap_bridge._HintBox()
        box.add(range(200))
        self.assertEqual(len(box.slots), ap_bridge.HINT_QUEUE_MAX)
        self.assertEqual(len(box.drain()), ap_bridge.HINT_QUEUE_MAX)
        self.assertEqual(box.drain(), set())     # draining empties it

    def test_no_bridge_for_the_world_costs_nothing(self):
        # plain multiworld and solo games land here: refused, silently, with
        # no datastore read and no room traffic
        ap_bridge.request_hints(4242, 1, "5.6")
        self.assertEqual(ap_bridge._bridges, {})

    def test_flag_off_ignores_the_field_entirely(self):
        self.assertFalse(ap_bridge.ARCHIPELAGO)   # env flag is off in tests
        ap_bridge.request_hints(4242, 1, "5")

    def test_every_buyable_key_has_an_ap_item_and_a_name(self):
        for key in ap_bridge.HINTABLE_KEYS:
            ap_id = ap_bridge.AP_ID_BY_ITEM_KEY.get(key)
            self.assertIsNotNone(ap_id, "%s is not in the datapackage" % (key,))
            self.assertTrue(ap_bridge.ITEM_NAME_BY_AP_ID.get(ap_id))

    def test_the_allowlist_is_exactly_the_three_reveals(self):
        self.assertEqual(len(ap_bridge.HINTABLE_KEYS), 17)
        for key in [("EV", "1"), ("SK", "0"), ("RB", "17"), ("EX", "50"), ("TP", "Grove")]:
            self.assertNotIn(key, ap_bridge.HINTABLE_KEYS)


class TestGoldenRealTouchpoints(unittest.TestCase):
    """ApSession wired to the REAL _apply_grants and _shadow_slots, running
    against in-memory Player entities (netcode_test style: only the txn
    wrapper and entity lookups are rerouted). Pins the whole path both ways:
    AP item id -> datapackage key -> manifest slot -> slot bit on the real
    player, and shadow slot bit -> ap location id on the wire."""

    GID, WORLD = 1301, 1

    # two Bash + one '40 experience', matching the EX,40 manifest entry
    # exactly (524396, not the old 50-denomination 524349)
    BATCH = {"cmd": "ReceivedItems", "index": 0, "items": [
        {"item": 524288, "location": 91, "player": 2, "flags": 1},
        {"item": 524396, "location": 92, "player": 2, "flags": 0},
        {"item": 524288, "location": 93, "player": 1, "flags": 1},
    ]}

    @classmethod
    def setUpClass(cls):
        creds = google.auth.credentials.AnonymousCredentials()
        cls.ndb_client = ndb.Client(project="unit-test", credentials=creds)

    def setUp(self):
        self._ctx = self.ndb_client.context()
        self._ctx.__enter__()
        self.recvs, self.goals, self.counts = [], [], []
        self._orig = (ap_bridge._persist_recv, ap_bridge._persist_status,
                      ap_bridge._goal_worlds, ap_bridge._persist_name_counts)
        ap_bridge._persist_recv = lambda gid, world, count: self.recvs.append((gid, world, count))
        ap_bridge._persist_status = lambda gid, status, error: None
        ap_bridge._goal_worlds = lambda gid: list(self.goals)
        # the counter half of _persist_names is @ndb.transactional, which
        # wants a real backend; _persist_names itself and APNames are real
        ap_bridge._persist_name_counts = lambda gid, world, total, resolved: self.counts.append(
            (gid, world, total, resolved))
        from ap_models import APHints, APNames
        self.rows = {}
        APNames.put = lambda row, *a, **k: self.rows.__setitem__(row.key.id(), row) or row.key
        APNames.get_by_id = staticmethod(lambda rid: self.rows.get(rid))
        # hint purchases run for REAL here, minus the transaction wrapper the
        # emulator would need: the compare-and-set is the whole point
        self.hint_rows = {}
        APHints.put = lambda row, *a, **k: self.hint_rows.__setitem__(row.key.id(), row) or row.key
        APHints.get_by_id = staticmethod(lambda rid: self.hint_rows.get(rid))
        self._hintfns = (ap_bridge._claim_hint, ap_bridge._persist_hint,
                         Player.set_ap_hints_txn)
        ap_bridge._claim_hint = ap_bridge._claim_hint.__wrapped__
        ap_bridge._persist_hint = ap_bridge._persist_hint.__wrapped__
        set_hints = Player.set_ap_hints_txn.__wrapped__
        Player.set_ap_hints_txn = staticmethod(
            lambda pkey, answers, keep=None, limit=16: set_hints(pkey, answers, keep, limit))

        # K=2 world 1: real player 1301.1, shadow outbox 1301.3. Reserved
        # slot 40 on purpose: the diff must read past the first bfld word.
        self.real = Player(id="1301.1", skills=0, events=0, teleporters=0, bonuses={}, hints={})
        self.shadow = Player(id="1301.3", skills=0, events=0, teleporters=0, bonuses={}, hints={})
        for p in (self.real, self.shadow):
            p.put = lambda *a, **k: None
        by_key = {p.key: p for p in (self.real, self.shadow)}
        by_id = {p.key.id(): p for p in (self.real, self.shadow)}
        self._mtxn = Player.mark_slots_txn
        self.signals = []

        def _mark(pkey, slots, signal_for=None, signal_latest_only=False):
            fresh = [s for s in slots if by_key[pkey].mark_slot(s, delay_put=True)]
            if fresh and signal_for:
                self.signals.append(signal_for(fresh))
            return len(fresh)
        Player.mark_slots_txn = staticmethod(_mark)
        self._gwid = models.Game.with_id
        real = self.real

        class _FakeGame(object):
            def player(self, pid, create=True, delay_put=False):
                assert int(pid) == 1
                return real
        models.Game.with_id = staticmethod(lambda gid: _FakeGame())
        self._kget = ndb.Key.get
        ndb.Key.get = lambda k, *a, **kw: by_id.get(k.id())

        self.maps = ap_bridge.maps_from_params(FakeParams(2, {
            1: [
                ("919908", "MW", "3,0,AP Item #1", "Grove"),   # reserved slot 0 -> 524541
                ("959960", "MW", "3,40,AP Item #2", "Grove"),  # reserved slot 40 -> 524542
                ("-2", "MW", "3,SK,0", "Glades"),              # export slot 0: Bash
                ("-3", "MW", "3,EX,40", "Grove"),              # export slot 1: EX 40
                ("-5", "MW", "3,SK,0", "Glades"),              # export slot 3: Bash
                ("-6", "MW", "3,EV,0", "Swamp"),               # export slot 4: Water Vein
            ],
            2: [],
        }))

    def tearDown(self):
        from ap_models import APHints, APNames
        (ap_bridge._persist_recv, ap_bridge._persist_status,
         ap_bridge._goal_worlds, ap_bridge._persist_name_counts) = self._orig
        (ap_bridge._claim_hint, ap_bridge._persist_hint,
         Player.set_ap_hints_txn) = self._hintfns
        del APNames.put
        del APNames.get_by_id
        del APHints.put
        del APHints.get_by_id
        ap_bridge._notice_at.clear()
        ap_bridge._dp_cache.clear()
        Player.mark_slots_txn = staticmethod(self._mtxn)
        models.Game.with_id = staticmethod(self._gwid)
        ndb.Key.get = self._kget
        self._ctx.__exit__(None, None, None)

    def make_session(self):
        return ApSession(self.GID, self.WORLD, self.maps, "Ori1", None,
                         game_slots=["Ori1", "Ori2"])

    def run_session(self, session, frames):
        sock = FakeSocket(frames)
        try:
            session.run(sock)
        except ConnectionClosed:
            pass
        return sock

    def test_index_zero_batch_marks_real_player(self):
        Cache.set_seen_checksum((self.GID, self.WORLD), 111)
        self.run_session(self.make_session(), [ROOMINFO, [connected(), dict(self.BATCH)]])
        self.assertEqual(self.real.slot_bflds, [0b1011] + [0] * 7)  # slots 0, 1, 3
        self.assertTrue(self.real.slot_check(1))  # the EX 40 entry, named exactly
        self.assertIsNone(Cache.get_seen_checksum((self.GID, self.WORLD)))  # tick rearmed
        self.assertEqual(self.recvs[-1], (self.GID, self.WORLD, 3))

    def test_full_replay_grants_nothing_twice(self):
        # a fresh connection replays the whole stream; the rebuilt fill
        # lands on the same slots, so the player is untouched
        self.run_session(self.make_session(), [ROOMINFO, [connected(), dict(self.BATCH)]])
        Cache.set_seen_checksum((self.GID, self.WORLD), 222)  # owner ticked since
        self.run_session(self.make_session(), [ROOMINFO, [connected(), dict(self.BATCH)]])
        self.assertEqual(self.real.slot_bflds, [0b1011] + [0] * 7)
        self.assertEqual(Cache.get_seen_checksum((self.GID, self.WORLD)), 222)  # no re-bust
        self.assertEqual(self.recvs[-1], (self.GID, self.WORLD, 3))

    def test_reconnect_reconcile(self):
        # bits set during an outage + the room's own checked list reconcile
        # to exactly one LocationChecks; the replayed grants stay put
        self.run_session(self.make_session(), [ROOMINFO, [connected(), dict(self.BATCH)]])
        self.shadow.mark_slot(0, delay_put=True)    # already known to the room
        self.shadow.mark_slot(40, delay_put=True)   # found during the outage
        sock = self.run_session(self.make_session(),
                                [ROOMINFO, [connected(checked=[524541]), dict(self.BATCH)]])
        checks = [m for m in sock.sent if m[0].get("cmd") == "LocationChecks"]
        self.assertEqual(checks, [[{"cmd": "LocationChecks", "locations": [524542]}]])
        self.assertEqual(self.real.slot_bflds, [0b1011] + [0] * 7)  # replay-stable

    def test_a_deathlink_death_leaves_ap_bookkeeping_alone(self):
        """Ori's death rollback wipes the client's granted-slot items (940-947,
        outside the 1500-1599 range deaths preserve) and the next tick re-grants
        from the diff. The server side of that has to be untouched by a death:
        the slot bits, the ReceivedItems index and the signal are all durable
        here, so the re-grant delivers exactly the same items."""
        self.run_session(self.make_session(), [ROOMINFO, [connected(), dict(self.BATCH)]])
        before = (list(self.real.slot_bflds), self.recvs[-1])

        # a DeathLink arrives and the client dies of it
        session = self.make_session()
        session.maps.death_link = True
        deliveries = []
        orig = (ap_bridge._bump_death_in, ap_bridge._send_death_signal)
        ap_bridge._bump_death_in = lambda gid, world: 1
        ap_bridge._send_death_signal = lambda gid, world, token, source: deliveries.append(source)
        try:
            self.run_session(session, [ROOMINFO, [connected()], [
                {"cmd": "Bounced", "tags": ["DeathLink"],
                 "data": {"time": 1.0, "source": "Zelda"}}]])
        finally:
            (ap_bridge._bump_death_in, ap_bridge._send_death_signal) = orig
        self.assertEqual(deliveries, ["Zelda"])
        self.assertEqual(list(self.real.slot_bflds), before[0])

        # the client comes back with its local grant bits cleared: the tick
        # still reports the same slots, so nothing was lost to the rollback
        self.run_session(self.make_session(), [ROOMINFO, [connected(), dict(self.BATCH)]])
        self.assertEqual((list(self.real.slot_bflds), self.recvs[-1]), before)

    def test_shadow_bit_flip_polls_correct_ap_id(self):
        session = self.make_session()
        sock = self.run_session(session, [ROOMINFO, [connected()]])
        self.assertEqual([m for m in sock.sent if m[0].get("cmd") == "LocationChecks"], [])
        self.shadow.mark_slot(40, delay_put=True)  # second bitfield word
        sock2 = FakeSocket([])
        session._poll_outbox(sock2)
        self.assertEqual(sock2.sent, [[{"cmd": "LocationChecks", "locations": [524542]}]])
        sock3 = FakeSocket([])
        session._poll_outbox(sock3)
        self.assertEqual(sock3.sent, [])  # nothing new: silent

    def test_scouted_names_land_in_a_readable_apnames_row(self):
        # the real _persist_names -> APNames -> the dict get_seed reads back.
        # Reserved slots here are 0 (ap loc 524541) and 40 (ap loc 524542).
        from ap_models import APNames
        self.run_session(self.make_session(), [
            roominfo({"Ori DE Rando": "oridesum"}),
            [connected(missing=[524541, 524542],
                       slot_info={"1": {"name": "Ori1", "game": "Ori DE Rando"},
                                  "2": {"name": "Ori2", "game": "Ori DE Rando"}},
                       players=[{"slot": 2, "alias": "Ori2", "name": "Ori2"}])],
            [{"cmd": "LocationInfo", "locations": [
                {"item": 524288, "location": 524542, "player": 2, "flags": 1}]}],
            [{"cmd": "DataPackage", "data": {"games": {"Ori DE Rando": {
                "checksum": "oridesum", "item_name_to_id": {"Bash": 524288}}}}}]])
        entries, ap_slot = APNames.load(self.GID, self.WORLD)
        self.assertEqual({s: (e.label(), e.to, e.ap_item, e.ap_owner)
                          for s, e in entries.items()},
                         {40: ("Bash (Ori2)", "P2", 524288, 2)})
        self.assertEqual(ap_slot, 1)  # what the annotate join keys off
        self.assertEqual(self.counts, [(self.GID, self.WORLD, 2, 1)])

    def test_a_grant_carries_its_sender_on_the_same_write(self):
        """The apfrom signal has to ride the slot marks: the client reads
        signals before the slot field, so one tick delivers both."""
        self.run_session(self.make_session(), [
            ROOMINFO,
            [connected(slot_info={"1": {"name": "Ori1", "game": "Ori DE Rando"},
                                  "2": {"name": "Ori2", "game": "Ori DE Rando"}}),
             dict(self.BATCH)]])
        self.assertEqual(self.signals, ["apfrom:0=P2;1=P2;3="])

    def test_a_replay_grants_nothing_so_it_announces_nothing(self):
        frames = [ROOMINFO, [connected(slot_info={"2": {"name": "Ori2", "game": "Ori DE Rando"}}),
                             dict(self.BATCH)]]
        self.run_session(self.make_session(), list(frames))
        self.run_session(self.make_session(), list(frames))
        self.assertEqual(len(self.signals), 1)

    # --- hint purchases against the real APHints record ---
    # world 1's manifest slot 4 is a Water Vein (ap id 524299), so this is the
    # clues-mode reveal end to end: request -> claim -> Say -> answer -> tick.

    WV = 524299

    def hint_session(self, slots):
        session = ApSession(self.GID, self.WORLD, self.maps, "Ori1", None,
                            game_slots=["Ori1", "Ori2"], hint_box=ap_bridge._HintBox())
        session.hint_box.add(slots)
        return session

    @staticmethod
    def hint_frames(hints=()):
        return [ROOMINFO,
                [connected(slot_info={"1": {"name": "Ori1", "game": "Ori DE Rando"},
                                      "2": {"name": "Ori2", "game": "Ori DE Rando"}})],
                [{"cmd": "Retrieved", "keys": {"_read_hints_0_1": list(hints)}}]]

    @staticmethod
    def says(sock):
        return [m["text"] for f in sock.sent for m in f if m.get("cmd") == "Say"]

    def test_the_buyable_slots_come_out_of_the_real_manifest(self):
        # only the three reveals; the Bash and experience exports next to it
        # have no purchase path at all
        self.assertEqual(self.maps.hint_keys[1], {4: ("EV", "0")})

    def test_a_purchase_is_claimed_before_the_room_hears_about_it(self):
        from ap_models import APHints
        sock = self.run_session(self.hint_session([4]), self.hint_frames())
        self.assertEqual(self.says(sock), ["!hint Water Vein"])
        self.assertEqual(APHints.load(self.GID, self.WORLD)[4]["s"], "p")

    def test_only_one_session_can_buy_a_slot(self):
        """The threat model is several gunicorn processes each running this
        world's session, all seeing the same 1 Hz request."""
        first = self.run_session(self.hint_session([4]), self.hint_frames())
        second = self.run_session(self.hint_session([4]), self.hint_frames())
        self.assertEqual(self.says(first) + self.says(second), ["!hint Water Vein"])

    def test_a_repeat_request_is_answered_from_storage(self):
        hint = {"receiving_player": 1, "finding_player": 1, "location": 524542,
                "item": self.WV, "found": False}
        self.run_session(self.hint_session([4]),
                         self.hint_frames() + [[{"cmd": "PrintJSON", "type": "Hint",
                                                 "receiving": 1, "found": False,
                                                 "item": {"item": self.WV, "location": 524542,
                                                          "player": 1, "flags": 1}}]])
        self.assertEqual(self.real.ap_hints, {"4": "P1 Grove"})
        # a later session -- reconnect, seed reload, another process -- answers
        # the same request without a word to the room
        again = self.run_session(self.hint_session([4]), self.hint_frames([hint]))
        self.assertEqual(self.says(again), [])
        self.assertEqual(self.real.ap_hints, {"4": "P1 Grove"})

    def test_the_answer_reaches_the_client_on_tick_field_8(self):
        Cache.set_seen_checksum((self.GID, self.WORLD), 333)
        self.run_session(self.hint_session([4]),
                         self.hint_frames() + [[{"cmd": "PrintJSON", "type": "Hint",
                                                 "receiving": 1, "found": False,
                                                 "item": {"item": self.WV, "location": 524542,
                                                          "player": 1, "flags": 1}}]])
        self.assertIsNone(Cache.get_seen_checksum((self.GID, self.WORLD)))  # pushed
        self.assertEqual(self.real.output(include_slots=True).split(",")[8], "4=P1 Grove")


class _StopOnFirstWait(object):
    """threading.Event stand-in: the loop must sleep out its backoff there
    (not spin), and the recorded timeout is the backoff under test."""

    def __init__(self):
        self.waits = []
        self._set = False

    def is_set(self):
        return self._set

    def set(self):
        self._set = True

    def wait(self, timeout=None):
        self.waits.append(timeout)
        self._set = True
        return True


class TestBridgeLoopBackoff(SessionTestCase):
    """_Bridge._run driven synchronously (the thread object never starts):
    connection outcomes surface on the link row and feed the backoff."""

    def setUp(self):
        super(TestBridgeLoopBackoff, self).setUp()
        class _Link(object):
            enabled = True
            host, port, password = "ap.example", 38281, "hunter2"
            slot_names = ["Ori1", "Ori2"]
            goal_worlds = []
        self.link = _Link()
        self.sockets = []
        maps = GameMaps(2, {1: {0: 524541}, 2: {}}, {1: {}, 2: {}})
        self._saved = (models.client, ap_bridge.APLink, ap_bridge.game_maps,
                       ap_bridge._open_socket)

        class _FakeNdbClient(object):
            def context(self):
                return ap_bridge._nullctx()
        models.client = _FakeNdbClient()
        ap_bridge.APLink = type("FakeAPLink", (object,),
                                {"with_id": staticmethod(lambda gid: self.link)})
        ap_bridge.game_maps = lambda gid: maps
        ap_bridge._open_socket = lambda host, port, hint=None: (self.sockets.pop(0), "ws")

    def tearDown(self):
        (models.client, ap_bridge.APLink, ap_bridge.game_maps,
         ap_bridge._open_socket) = self._saved
        super(TestBridgeLoopBackoff, self).tearDown()

    def _run_bridge(self, frames):
        b = ap_bridge._Bridge(self.GID, self.WORLD)
        b.stop_event = _StopOnFirstWait()
        self.sockets.append(FakeSocket(frames))
        b._run()
        # the loop unwound: no thread ever ran, no registry residue
        self.assertEqual(ap_bridge._bridges, {})
        self.assertEqual([t for t in threading.enumerate()
                          if t.name.startswith("ap-bridge")], [])
        return b

    def test_refused_surfaces_status_and_pins_backoff(self):
        b = self._run_bridge([ROOMINFO, [{"cmd": "ConnectionRefused",
                                          "errors": ["InvalidSlot"]}]])
        self.assertEqual(b.stop_event.waits, [ap_bridge.BACKOFF_MAX])
        (gid, status, error), = self.statuses
        self.assertEqual((gid, status), (self.GID, "refused"))
        self.assertIn("InvalidSlot", error)

    def test_connection_lost_after_auth_resets_backoff(self):
        b = self._run_bridge([ROOMINFO, [connected()]])
        self.assertEqual(b.stop_event.waits, [ap_bridge.BACKOFF_MIN])
        self.assertEqual([s for _, s, _ in self.statuses],
                         ["connected", "reconnecting"])


class TestDeflateHandshake(unittest.TestCase):
    """AP warns clients that connect uncompressed and plans to require it;
    simple_websocket only offers permessage-deflate server-side."""

    def _handshake_headers(self, client_class):
        import socket as socket_mod
        srv = socket_mod.socket()
        srv.setsockopt(socket_mod.SOL_SOCKET, socket_mod.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        port = srv.getsockname()[1]
        seen = {}

        def accept():
            conn, _ = srv.accept()
            seen["data"] = conn.recv(4096).decode("latin-1")
            conn.close()
        thread = threading.Thread(target=accept, daemon=True)
        thread.start()
        try:
            client_class.connect("ws://127.0.0.1:%s/" % port)
        except Exception:
            pass       # the request is all we need; no server response follows
        thread.join(timeout=5)
        srv.close()
        return seen.get("data", "")

    def test_client_offers_permessage_deflate(self):
        headers = self._handshake_headers(ap_bridge.DeflateClient)
        self.assertIn("permessage-deflate", headers.lower())

    def test_upstream_client_does_not(self):
        # pins WHY the subclass exists: drop it when simple_websocket offers it
        from simple_websocket import Client
        self.assertNotIn("permessage-deflate", self._handshake_headers(Client).lower())


class TestPreflight(unittest.TestCase):
    """An unroutable room must fail in seconds with an address in the message,
    not hold the thread for the OS SYN ladder."""

    def test_unreachable_port_fails_fast_and_names_the_room(self):
        import socket as socket_mod
        from time import monotonic
        # a closed port on loopback refuses immediately; the point is that the
        # error carries host:port and arrives via OSError
        free = socket_mod.socket()
        free.bind(("127.0.0.1", 0))
        port = free.getsockname()[1]
        free.close()
        start = monotonic()
        with self.assertRaises(OSError) as caught:
            ap_bridge._preflight("127.0.0.1", port)
        self.assertLess(monotonic() - start, ap_bridge.CONNECT_TIMEOUT + 5)
        self.assertIn("127.0.0.1:%s" % port, str(caught.exception))
        self.assertIn("orirando", str(caught.exception))

    def test_open_socket_preflights_before_dialing(self):
        calls = []
        saved = ap_bridge._preflight
        ap_bridge._preflight = lambda host, port: calls.append((host, port))
        try:
            # preflight passes, then the ws dial fails: both schemes attempted
            with self.assertRaises(Exception):
                ap_bridge._open_socket("127.0.0.1", 1, None)
        finally:
            ap_bridge._preflight = saved
        self.assertEqual(calls, [("127.0.0.1", 1)])


class TestLinkRetarget(unittest.TestCase):
    """ap/connect with new room coordinates must cycle live sessions: the
    15s link recheck compares (host, port, password) and ends the session."""

    def setUp(self):
        self._saved = ap_bridge.APLink
        self.link = type("L", (object,), {})()
        self.link.enabled = True
        self.link.host, self.link.port, self.link.password = "room.test", 38281, None
        self.link.goal_worlds = []
        ap_bridge.APLink = type("FakeAPLink", (object,),
                                {"with_id": staticmethod(lambda gid: self.link)})

    def tearDown(self):
        ap_bridge.APLink = self._saved

    def _session(self):
        maps = GameMaps(1, {1: {}}, {1: {}})
        return ApSession(942, 1, maps, "Ori1", None, host="room.test", port=38281)

    def test_same_room_continues(self):
        self.assertTrue(self._session()._recheck_link(sock=None))

    def test_port_change_cycles(self):
        self.link.port = 12345
        self.assertFalse(self._session()._recheck_link(sock=None))

    def test_password_change_cycles(self):
        self.link.password = "hunter2"
        self.assertFalse(self._session()._recheck_link(sock=None))

    def test_disabled_stops(self):
        self.link.enabled = False
        self.assertFalse(self._session()._recheck_link(sock=None))


if __name__ == "__main__":
    unittest.main()
