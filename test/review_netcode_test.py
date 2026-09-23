"""Netcode edge cases: tick cache races, stale Player puts, signal confirms."""
import unittest
from datetime import datetime

from google.cloud import ndb

import cache as cache_mod
import models
import netcode
from cache import Cache
from enums import MultiplayerGameType
from models import BingoCard, BingoCardProgress, Game, Player
from pickups import Pickup
from test.ndb_base import EmulatorTestCase, NdbTestCase
from test.session_golden_test import FakeGame, make_player


def _tick_payload():
    payload = {"seen_%s" % i: "0" for i in range(8)}
    payload.update({"have_%s" % i: "0" for i in range(8)})
    return payload


class TickCacheRace(NdbTestCase):
    """A grant that busts the checksum mid-tick must not be masked by that tick."""

    def setUp(self):
        super().setUp()
        self._with_id = Game.__dict__["with_id"]
        self.addCleanup(setattr, Game, "with_id", self._with_id)

    def test_grant_between_read_and_arm_reaches_the_next_tick(self):
        gid, pid = 9101, 1
        blank = dict(seen_bflds=8 * [0], have_bflds=8 * [0], signals=[])
        stale = make_player(gid, pid, **blank)
        fresh = make_player(gid, pid, skills=1, **blank)
        game = FakeGame(mode=MultiplayerGameType.SHARED)
        reads = []

        def player(p, *a, **k):
            reads.append(p)
            if len(reads) == 1:
                # the grant commits and busts right after this tick's read
                Cache.clear_seen_checksum((gid, pid))
                return stale
            return fresh
        game.player = player
        Game.with_id = staticmethod(lambda _gid: game)
        Cache.clear_seen_checksum((gid, pid))

        netcode.tick(gid, pid, _tick_payload())
        status, body = netcode.tick(gid, pid, _tick_payload())

        self.assertEqual(status, 200)
        self.assertTrue(body.startswith("1,"), "fast path served the pre-grant body: %r" % body)


class ConfSignals(unittest.TestCase):
    def test_unmatched_msg_confirm_removes_nothing(self):
        signals = ["win:$Finished in 1st place at 10:00!", "msg:@hello@"]
        models._conf_signals(signals, "msg:@hellp@")
        self.assertEqual(signals, ["win:$Finished in 1st place at 10:00!", "msg:@hello@"])


class PlayerIdpts(NdbTestCase):
    def test_malformed_key_falls_back(self):
        self.assertEqual(Player(id="garbage").idpts(), (0, 0))


class TickPayload(NdbTestCase):
    def setUp(self):
        super().setUp()
        self._with_id = Game.__dict__["with_id"]
        self.addCleanup(setattr, Game, "with_id", self._with_id)

    def test_missing_have_field_is_not_a_crash(self):
        game = FakeGame(players={1: make_player(9102, 1, seen_bflds=8 * [0], have_bflds=8 * [0], signals=[])})
        Game.with_id = staticmethod(lambda _gid: game)
        Cache.clear_seen_checksum((9102, 1))
        payload = {"seen_%s" % i: "0" for i in range(8)}
        status, _ = netcode.tick(9102, 1, payload)
        self.assertIn(status, (200, 400))


class BingoAutoStart(NdbTestCase):
    def test_first_report_persists_the_clock(self):
        from models import BingoGameData, BingoTeam
        cards = [BingoCard(name="Goal%s" % i, goal_type="int", target=99, square=i) for i in range(25)]
        p1 = Player(id="58.1", bingo_prog=[BingoCardProgress(square=i) for i in range(25)], signals=[])
        bgd = BingoGameData(id="58")
        bgd.board = cards
        bgd.teams = [BingoTeam(captain=p1.key, teammates=[])]
        bgd.bingo_count = 3
        bgd.auto_start = True
        bgd.game = ndb.Key("Game", 58)
        bgd.get_players = lambda: [p1]
        puts = []
        bgd.put = lambda *a, **k: puts.append(1)
        self.addCleanup(setattr, Player, "save_bingo_txn", Player.__dict__["save_bingo_txn"])
        Player.save_bingo_txn = staticmethod(lambda pkey, prog, tp: True)

        bgd.update({"Goal0": {"value": 1}}, 1, 58)

        self.assertIsNotNone(bgd.start_time)
        self.assertTrue(puts, "the clock start was never written")


class MemcachePool(unittest.TestCase):
    def test_pool_covers_every_gunicorn_thread(self):
        import os
        import re
        with open(os.path.join(os.path.dirname(cache_mod.__file__), "Dockerfile")) as f:
            threads = int(re.search(r"--threads (\d+)", f.read()).group(1))
        pool = cache_mod.MemcachedCache("127.0.0.1", 1).memcache.client_pool
        self.assertGreater(pool.max_size, threads)


class StalePlayerPuts(EmulatorTestCase):
    """Writes on the netcode path must not erase a concurrent grant's slot bits."""

    def _mw_game(self, gid):
        game = Game(id=gid, players=[], str_mode=MultiplayerGameType.MULTIWORLD.value, has_history=False)
        game.put()
        for pid in (1, 2):
            game.player(pid)
        return game

    def test_complete_keeps_a_slot_granted_mid_request(self):
        gid = 9201
        self._mw_game(gid)
        orig_player = Game.player
        orig_release = Game.mw_release
        self.addCleanup(setattr, Game, "player", orig_player)
        self.addCleanup(setattr, Game, "mw_release", orig_release)
        Game.mw_release = lambda self, pid, params=None: 0

        def racing_player(self, pid, *a, **k):
            p = orig_player(self, pid, *a, **k)
            if int(pid) == 1:
                Player.mark_slot_txn(p.key, 7)  # another world finds an item of P1's
            return p
        Game.player = racing_player

        status, _ = netcode.game_complete(gid, 1)

        self.assertEqual(status, 200)
        fresh = ndb.Key(Game, gid, Player, "%s.1" % gid).get()
        self.assertTrue(fresh.released)
        self.assertTrue(fresh.slot_check(7), "the finisher's put erased a concurrent slot grant")

    def test_concurrent_first_joins_keep_both_players(self):
        gid = 9202
        Game(id=gid, players=[], str_mode=MultiplayerGameType.SHARED.value, has_history=False).put()
        # two requests, two copies
        a = Game.get_by_id(gid, use_cache=False)
        b = Game.get_by_id(gid, use_cache=False)
        a.player(1)
        b.player(2)
        self.assertEqual(sorted(Game.get_by_id(gid, use_cache=False).player_nums()), [1, 2])



class FoundPayload(NdbTestCase):
    def setUp(self):
        super().setUp()
        self.addCleanup(setattr, Game, "with_id", Game.__dict__["with_id"])
        Game.with_id = staticmethod(lambda _gid: FakeGame())

    def test_garbage_ids_and_coords_are_refused_not_crashed(self):
        self.assertEqual(netcode.found_pickup(9103, 1, "123", "SK", "abc", {})[0], 406)
        self.assertEqual(netcode.found_pickup(9103, 1, "nope", "SK", "0", {})[0], 406)


class PusherBusySocket(unittest.TestCase):
    def test_a_held_send_lock_skips_the_push(self):
        import threading
        import ws

        class Conn(object):
            sent = []

            def send(self, frame):
                self.sent.append(frame)

        class Ctx(object):
            def context(self):
                import contextlib
                return contextlib.nullcontext()

        gpid, conn, lock = (9104, 1), Conn(), threading.Lock()
        self.addCleanup(ws._socks.pop, gpid, None)
        self.addCleanup(setattr, ws, "PUSH_LOCK_WAIT", ws.PUSH_LOCK_WAIT)
        self.addCleanup(setattr, netcode, "tick_output", netcode.tick_output)
        ws._socks[gpid] = (conn, lock)
        ws.PUSH_LOCK_WAIT = 0.01
        netcode.tick_output = lambda gid, pid: "0,0,0,,"
        with lock:
            ws._push_one(gpid, Ctx())
        self.assertEqual(conn.sent, [])
        ws._push_one(gpid, Ctx())
        self.assertEqual(conn.sent, ["tick:0,0,0,,"])


class ApLinkRouteWrites(EmulatorTestCase):
    def test_connect_and_disconnect_keep_the_bridges_fields(self):
        from ap_models import APLink
        link = APLink.make(9301, 2)
        link.goal_worlds, link.dl_in = [2], [0, 3]
        link.put()
        netcode._connect_link_txn(9301, 2, None, "ap.example", 38281, None)
        fresh = APLink.get_by_id(9301, use_cache=False)
        self.assertEqual((fresh.host, fresh.enabled, fresh.status), ("ap.example", True, "pending"))
        self.assertEqual((fresh.goal_worlds, fresh.dl_in), ([2], [0, 3]))
        self.assertTrue(netcode._disconnect_link_txn(9301))
        fresh = APLink.get_by_id(9301, use_cache=False)
        self.assertEqual((fresh.enabled, fresh.goal_worlds), (False, [2]))
        self.assertIsNone(netcode._disconnect_link_txn(9399))



class SanityCheckAddOnly(EmulatorTestCase):
    """Co-op sanity repairs only ever add, on a fresh read per player."""

    def _game(self, gid, inventory, after_snapshot=None):
        game = Game(id=gid, players=[], str_mode=MultiplayerGameType.SHARED.value,
                    str_shared=["Skills", "Upgrades"], has_history=False)
        game.put()
        p1, p2 = game.player(1), game.player(2)

        def get_inventories(self_, players, *a, **k):
            if after_snapshot:
                after_snapshot(p1, p2)
            return {(1, 2): inventory}
        self.addCleanup(setattr, Game, "get_inventories", Game.get_inventories)
        Game.get_inventories = get_inventories
        return Game.get_by_id(gid, use_cache=False), p1, p2

    def _fresh(self, p):
        return p.key.get(use_cache=False)

    def test_missing_items_are_added_and_extras_are_left_alone(self):
        game, p1, p2 = self._game(9401, {("SK", 0): 1, ("RB", 6): 1})
        attack = Pickup.n("RB", 6)
        Player.transaction_pickup_batch([p1.key], [(attack, False, None, None), (attack, False, None, None)])
        with self.assertLogs(level="WARNING") as logs:
            self.assertTrue(Game.get_by_id(9401, use_cache=False).sanity_check())
        self.assertTrue(self._fresh(p2).has_pickup(Pickup.n("SK", 0)))
        self.assertEqual(self._fresh(p1).has_pickup(attack), 2, "a surplus upgrade was taken away")
        self.assertTrue(any("leaving it" in line for line in logs.output))

    def test_bitfields_merge_as_a_union(self):
        game, p1, p2 = self._game(9402, {})
        Player.transaction_pickup_batch([p1.key], [(Pickup.n("SK", 0), False, None, None),
                                                   (Pickup.n("SK", 3), False, None, None)])
        Player.transaction_pickup_batch([p2.key], [(Pickup.n("SK", 2), False, None, None)])
        Game.get_by_id(9402, use_cache=False).sanity_check()
        for p in (p1, p2):
            fresh = self._fresh(p)
            for sk in (0, 2, 3):
                self.assertTrue(fresh.has_pickup(Pickup.n("SK", sk)), "P%s lost or never got SK%s" % (p.pid(), sk))

    def test_a_grant_landing_mid_check_survives(self):
        def grant(p1, p2):
            Player.transaction_pickup_batch([p2.key], [(Pickup.n("RB", 12), False, None, None)])
        game, p1, p2 = self._game(9403, {("SK", 0): 1}, after_snapshot=grant)
        Game.get_by_id(9403, use_cache=False).sanity_check()
        self.assertEqual(self._fresh(p2).has_pickup(Pickup.n("RB", 12)), 1, "the repair put erased a grant")


if __name__ == "__main__":
    unittest.main()
