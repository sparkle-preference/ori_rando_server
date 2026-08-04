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


def connected(checked=(), missing=(), slot_info=None, players=None):
    msg = {"cmd": "Connected", "team": 0, "slot": 1,
           "checked_locations": list(checked), "missing_locations": list(missing)}
    if slot_info is not None:
        msg["slot_info"] = slot_info   # json object keys arrive as strings
    if players is not None:
        msg["players"] = players
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

    def test_ex_denominations_ties_round_down(self):
        # mirror of convert.nearest_ex_denom: both sides must bucket alike
        for value, denom in [(1, "50"), (73, "50"), (75, "50"), (76, "100"),
                             (150, "100"), (151, "200"), (999, "200")]:
            self.assertEqual(ap_bridge._match_key("EX", str(value)), ("EX", denom),
                             "EX %s" % value)


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
                ("-3", "MW", "3,EX,40", "Grove"),              # export slot 1 (EX 50)
                ("-4", "MW", "3,EX,73", "Grove"),              # export slot 2 (EX 50)
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
        self.assertEqual(maps.grant_slots[1],
                         {("SK", "0"): [0], ("EX", "50"): [1, 2]})
        self.assertEqual(maps.grant_slots[2], {("TP", "Grove"): [0]})

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
        self.recvs = []          # (gid, world, count)
        self.statuses = []       # (gid, status, error)
        self.names = []          # (gid, world, total, {slot: display name})
        self._orig = (ap_bridge._shadow_slots, ap_bridge._apply_grants,
                      ap_bridge._persist_recv, ap_bridge._persist_status,
                      ap_bridge._goal_worlds, ap_bridge._persist_names)
        ap_bridge._shadow_slots = lambda gid, world, maps: set(self.shadow)
        ap_bridge._apply_grants = lambda gid, world, slots: self.grants.append((gid, world, list(slots))) or len(slots)
        ap_bridge._persist_recv = lambda gid, world, count: self.recvs.append((gid, world, count))
        ap_bridge._persist_status = lambda gid, status, error: self.statuses.append((gid, status, error))
        ap_bridge._goal_worlds = lambda gid: list(self.goals)
        ap_bridge._persist_names = lambda gid, world, total, names: self.names.append((gid, world, total, dict(names)))

    def tearDown(self):
        (ap_bridge._shadow_slots, ap_bridge._apply_grants, ap_bridge._persist_recv,
         ap_bridge._persist_status, ap_bridge._goal_worlds,
         ap_bridge._persist_names) = self._orig

    def make_session(self, **kw):
        # slot 0 and 3 take Bash (524288); slot 1 takes 50 experience (524349)
        maps = GameMaps(2, {1: {0: 524541, 1: 524542}, 2: {}},
                        {1: {("SK", "0"): [0, 3], ("EX", "50"): [1]}, 2: {}})
        return ApSession(self.GID, self.WORLD, maps, "Ori1", "hunter2", **kw)

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
        self.assertEqual(self.grants, [(self.GID, self.WORLD, [0]),
                                       (self.GID, self.WORLD, [0])])
        self.assertEqual(session.recv_count, 1)

    def test_incremental_batch_continues_fill(self):
        session = self.make_session()
        self.run_session(session, [ROOMINFO, [connected()],
                                   [{"cmd": "ReceivedItems", "index": 0,
                                     "items": [{"item": 524288, "location": 10, "player": 2}]}],
                                   [{"cmd": "ReceivedItems", "index": 1,
                                     "items": [{"item": 524288, "location": 12, "player": 2}]}]])
        self.assertEqual(self.grants, [(self.GID, self.WORLD, [0]),
                                       (self.GID, self.WORLD, [3])])
        self.assertEqual(self.recvs[-1], (self.GID, self.WORLD, 2))

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
        self.assertEqual(self.names[-1],
                         (self.GID, self.WORLD, 2,
                          {0: "Bash (Ori2)", 1: "A Click (Questy)"}))
        # nothing extra went out once both packages were in hand
        self.assertEqual(len(self.sent_of(sock, "GetDataPackage")), 1)

    def test_alias_beats_slot_name(self):
        # slot_info calls slot 3 "TestQuest"; the room's players list aliases
        # it to "Questy", which is what everyone in the room sees
        self.run_session(self.make_session(), self.hello() + [
            [self.location_info([(524541, 42, 3, 0)])],
            [{"cmd": "DataPackage", "data": {"games": {
                "Clique": {"checksum": "cliquesum", "item_name_to_id": {"A Click": 42}}}}}]])
        self.assertEqual(self.names[-1][3], {0: "A Click (Questy)"})

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
        self.assertEqual(self.names[-1][3], {0: "Bash (Ori2)"})

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
        label = self.names[-1][3][0]
        for bad in "|/\\?#%$*@\r\n":
            self.assertNotIn(bad, label, "%r survived sanitization in %r" % (bad, label))
        # ',' is the one separator that stays: the name is the LAST field of a
        # maxsplit-bounded value on both sides of the wire
        self.assertEqual(label, "Bow Pipe, Arrows 3 green slash 100 red (Questy)")

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


class TestGoldenRealTouchpoints(unittest.TestCase):
    """ApSession wired to the REAL _apply_grants and _shadow_slots, running
    against in-memory Player entities (netcode_test style: only the txn
    wrapper and entity lookups are rerouted). Pins the whole path both ways:
    AP item id -> datapackage key -> manifest slot -> slot bit on the real
    player, and shadow slot bit -> ap location id on the wire."""

    GID, WORLD = 1301, 1

    # two Bash + one '50 experience'; the EX manifest entry is a true-value
    # EX,40 line, so the grant must ride the denomination bucket
    BATCH = {"cmd": "ReceivedItems", "index": 0, "items": [
        {"item": 524288, "location": 91, "player": 2, "flags": 1},
        {"item": 524349, "location": 92, "player": 2, "flags": 0},
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
        from ap_models import APNames
        self.rows = {}
        APNames.put = lambda row, *a, **k: self.rows.__setitem__(row.key.id(), row) or row.key
        APNames.get_by_id = staticmethod(lambda rid: self.rows.get(rid))

        # K=2 world 1: real player 1301.1, shadow outbox 1301.3. Reserved
        # slot 40 on purpose: the diff must read past the first bfld word.
        self.real = Player(id="1301.1", skills=0, events=0, teleporters=0, bonuses={}, hints={})
        self.shadow = Player(id="1301.3", skills=0, events=0, teleporters=0, bonuses={}, hints={})
        for p in (self.real, self.shadow):
            p.put = lambda *a, **k: None
        by_key = {p.key: p for p in (self.real, self.shadow)}
        by_id = {p.key.id(): p for p in (self.real, self.shadow)}
        self._mtxn = Player.mark_slots_txn
        Player.mark_slots_txn = staticmethod(
            lambda pkey, slots: sum(1 for s in slots if by_key[pkey].mark_slot(s, delay_put=True)))
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
                ("-3", "MW", "3,EX,40", "Grove"),              # export slot 1: EX 40 (denom 50)
                ("-5", "MW", "3,SK,0", "Glades"),              # export slot 3: Bash
            ],
            2: [],
        }))

    def tearDown(self):
        from ap_models import APNames
        (ap_bridge._persist_recv, ap_bridge._persist_status,
         ap_bridge._goal_worlds, ap_bridge._persist_name_counts) = self._orig
        del APNames.put
        del APNames.get_by_id
        ap_bridge._dp_cache.clear()
        Player.mark_slots_txn = staticmethod(self._mtxn)
        models.Game.with_id = staticmethod(self._gwid)
        ndb.Key.get = self._kget
        self._ctx.__exit__(None, None, None)

    def make_session(self):
        return ApSession(self.GID, self.WORLD, self.maps, "Ori1", None)

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
        self.assertTrue(self.real.slot_check(1))  # the EX 40 entry, via denom 50
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
        self.assertEqual(APNames.load(self.GID, self.WORLD), {40: "Bash (Ori2)"})
        self.assertEqual(self.counts, [(self.GID, self.WORLD, 2, 1)])


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
