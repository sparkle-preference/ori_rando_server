"""What the netcode paths read from the datastore and clear from the cache."""
import json
import threading
import unittest
from contextlib import contextmanager
from time import monotonic

from google.cloud import ndb
from google.cloud.ndb import _datastore_api
from simple_websocket import ConnectionClosed

import netcode
import ws
from archipelago import ap_bridge
from cache import Cache
from enums import MultiplayerGameType
from models import (BingoCard, BingoCardProgress, BingoEventChunk, BingoGameData, BingoTeam, Game,
                    HistoryChunk, Player)
from pickups import Pickup
from test.ndb_base import EmulatorTestCase
from util import utcnow

COORDS = "919772"


@contextmanager
def lookups():
    """Collects one entry per datastore Lookup RPC made inside the block."""
    seen = []
    real = _datastore_api.make_call

    def counting(rpc_name, *args, **kwargs):
        if rpc_name == "lookup":
            seen.append(rpc_name)
        return real(rpc_name, *args, **kwargs)
    _datastore_api.make_call = counting
    try:
        yield seen
    finally:
        _datastore_api.make_call = real


def make_game(gid, mode, players, **fields):
    game = Game(id=gid, players=[], str_mode=mode.value, has_history=False, **fields)
    game.put()
    for pid in range(1, players + 1):
        game.player(pid)
    ws._begin_frame()
    return game


class PlayerLoads(EmulatorTestCase):
    def _find_lookups(self, gid, mode, players, kind, id):
        make_game(gid, mode, players)
        with lookups() as seen:
            status, _ = netcode.found_pickup(gid, 1, COORDS, kind, id, {})
        self.assertEqual(status, 200)
        return len(seen)

    def test_players_load_in_one_batch(self):
        make_game(9601, MultiplayerGameType.SIMUSOLO, 5)
        game = Game.with_id(9601)
        with lookups() as seen:
            players = game.get_players()
        self.assertEqual(len(seen), 1)
        self.assertEqual([p.pid() for p in players], [1, 2, 3, 4, 5])

    def test_a_solo_find_reads_the_same_whatever_the_lobby_size(self):
        solo = MultiplayerGameType.SIMUSOLO
        self.assertEqual(self._find_lookups(9602, solo, 2, "HC", "1"),
                         self._find_lookups(9603, solo, 6, "HC", "1"))

    def test_a_slot_find_reads_the_same_whatever_the_lobby_size(self):
        mw = MultiplayerGameType.MULTIWORLD
        self.assertEqual(self._find_lookups(9604, mw, 2, "MW", "2,5,SK,0"),
                         self._find_lookups(9605, mw, 6, "MW", "2,5,SK,0"))
        owner = ndb.Key(Game, 9605, Player, "9605.2").get(use_cache=False)
        self.assertTrue(owner.slot_check(5))

    def test_a_shared_multiworld_find_reaches_every_world(self):
        make_game(9606, MultiplayerGameType.MULTIWORLD, 3, str_shared=["Skills"])
        status, _ = netcode.found_pickup(9606, 1, COORDS, "SK", "0", {})
        self.assertEqual(status, 200)
        for pid in (1, 2, 3):
            world = ndb.Key(Game, 9606, Player, "9606.%s" % pid).get(use_cache=False)
            self.assertEqual(world.skills, 1, "world %s missed the shared skill" % pid)


class BingoReports(EmulatorTestCase):
    def _bingo(self, gid):
        game = Game(id=gid, players=[], str_mode=MultiplayerGameType.SIMUSOLO.value, has_history=False)
        game.put()
        player = game.player(1)
        player.bingo_prog = [BingoCardProgress(square=i) for i in range(25)]
        player.put()
        cards = [BingoCard(name="Goal%s" % i, goal_type="int", target=99, square=i) for i in range(25)]
        BingoGameData(id=gid, game=game.key, players=[player.key], board=cards, bingo_count=3,
                      teams=[BingoTeam(captain=player.key, teammates=[])], start_time=utcnow()).put()

    def _report(self, gid, first_goal):
        ws._begin_frame()
        data = {"Goal%s" % i: {"value": first_goal if i == 0 else 0} for i in range(25)}
        return netcode.bingo_update(gid, 1, {"bingoData": json.dumps(data)})[0]

    def test_a_repeated_snapshot_reads_twice_and_writes_nothing(self):
        self._bingo(9611)
        writes = []
        real = Player.__dict__["save_bingo_txn"]
        self.addCleanup(setattr, Player, "save_bingo_txn", real)
        Player.save_bingo_txn = staticmethod(lambda *args: writes.append(args) or real.__func__(*args))

        self.assertEqual(self._report(9611, 3), 200)
        with lookups() as seen:
            self.assertEqual(self._report(9611, 3), 200)
        self.assertEqual(len(writes), 1)
        self.assertEqual(len(seen), 2, "the board and its players, once each")

        self.assertEqual(self._report(9611, 4), 200)
        self.assertEqual(len(writes), 2)
        stored = ndb.Key(Game, 9611, Player, "9611.1").get(use_cache=False)
        self.assertEqual(stored.bingo_prog[0].count, 4)


class ReloadScope(EmulatorTestCase):
    """A seed load (connect) refreshes the player loading, and a co-op team."""

    def _reload(self, gid, mode, players, **fields):
        make_game(gid, mode, players, **fields)
        for pid in range(1, players + 1):
            Cache.set_seen_checksum((gid, pid), 7)
        with lookups() as seen:
            netcode.connect(gid, 1, {})
        return len(seen), [Cache.get_seen_checksum((gid, pid)) for pid in range(1, players + 1)]

    def test_a_solo_reload_leaves_the_rest_of_the_lobby_alone(self):
        solo = MultiplayerGameType.SIMUSOLO
        small, armed = self._reload(9631, solo, 3)
        self.assertEqual(armed, [None, 7, 7])
        large, _ = self._reload(9632, solo, 7)
        self.assertEqual(small, large, "a reload read more for a bigger lobby")

    def test_a_coop_reload_still_refreshes_the_team(self):
        self.addCleanup(setattr, Game, "get_inventories", Game.get_inventories)
        Game.get_inventories = lambda self_, players, *a, **k: {(1, 2): {}}
        _, armed = self._reload(9633, MultiplayerGameType.SHARED, 2, str_shared=["Skills"])
        self.assertEqual(armed, [None, None])


class ItemCache(EmulatorTestCase):
    STALE = {"skills": ["stale"]}

    def _find(self, gid, mode, **fields):
        make_game(gid, mode, 2, **fields)
        for pid in (1, 2):
            Cache.set_items(gid, pid, (self.STALE, {}))
        self.assertEqual(netcode.found_pickup(gid, 2, COORDS, "SK", "0", {})[0], 200)
        return [Cache.get_items(gid, pid)[0] for pid in (1, 2)]

    def test_a_find_clears_the_finders_items(self):
        self.assertEqual(self._find(9641, MultiplayerGameType.SIMUSOLO), [self.STALE, {}])

    def test_a_coop_grant_clears_the_teams_items(self):
        self.assertEqual(self._find(9642, MultiplayerGameType.SHARED, str_shared=["Skills"]), [{}, {}])


class HealMemo(EmulatorTestCase):
    def test_a_game_with_no_link_row_is_remembered_longer(self):
        gid = 9651
        self.addCleanup(ap_bridge._heal_memo.pop, gid, None)
        ap_bridge.heal(gid, active=True)
        expiry, state, _ = ap_bridge._heal_memo[gid]
        self.assertFalse(state)
        self.assertGreater(expiry - monotonic(), ap_bridge.HEAL_TTL)


class CleanUp(EmulatorTestCase):
    def test_a_cleaned_game_takes_its_history_chunks_with_it(self):
        gid = 9661
        make_game(gid, MultiplayerGameType.SIMUSOLO, 1)
        netcode.found_pickup(gid, 1, COORDS, "HC", "1", {})
        key = ndb.Key(Game, gid)
        self.assertEqual(HistoryChunk.query(ancestor=key).count(), 1)

        Game.with_id(gid).clean_up()

        self.assertEqual(HistoryChunk.query(ancestor=key).count(), 0)
        self.assertIsNone(key.get(use_cache=False))
        self.assertIsNone(ndb.Key(Game, gid, Player, "%s.1" % gid).get(use_cache=False))

    def test_a_cleaned_bingo_game_takes_its_event_chunks_with_it(self):
        gid = 9662
        make_game(gid, MultiplayerGameType.SIMUSOLO, 1)
        game = Game.with_id(gid)
        game.bingo_data = BingoGameData(id=gid, game=game.key).put()
        game.put()
        BingoEventChunk(key=BingoEventChunk.key_for(game.bingo_data, gid, 0), events=[]).put()

        game.clean_up()

        self.assertEqual(BingoEventChunk.query(ancestor=game.bingo_data).count(), 0)
        self.assertIsNone(game.bingo_data.get(use_cache=False))


class ScriptedConn(object):
    """A socket whose script mixes frames with things that happen between them."""

    def __init__(self, script):
        self.script = list(script)
        self.sent = []

    def receive(self, timeout=None):
        while self.script and callable(self.script[0]):
            self.script.pop(0)()
        if not self.script:
            raise ConnectionClosed(1000, "client gone")
        return self.script.pop(0)

    def send(self, data):
        self.sent.append(data)


def tick_frame(**fields):
    payload = {"seen_%s" % i: "0" for i in range(8)}
    payload.update({"have_%s" % i: "0" for i in range(8)})
    payload.update(fields)
    return "tick:" + "&".join("%s=%s" % kv for kv in sorted(payload.items()))


class SocketContext(EmulatorTestCase):
    """A socket reuses one ndb context for every frame."""

    def setUp(self):
        super().setUp()
        # no pusher thread: it has no datastore here
        self.addCleanup(setattr, ws, "_ensure_pusher", ws._ensure_pusher)
        ws._ensure_pusher = lambda: None
        self.addCleanup(lambda: [ws._push_queue.get_nowait() for _ in range(ws._push_queue.qsize())])

    def _elsewhere(self, work):
        def run():
            with self.ndb_client.context():
                work()
        thread = threading.Thread(target=run)
        thread.start()
        thread.join()

    def test_a_push_batch_reads_each_game_once(self):
        gid = 9622
        make_game(gid, MultiplayerGameType.SIMUSOLO, 3)
        conns = {pid: ScriptedConn([]) for pid in (1, 2, 3)}
        for pid, conn in conns.items():
            self.addCleanup(ws._unregister, (gid, pid), conn)
            ws._register((gid, pid), conn)
        with lookups() as seen:
            self._elsewhere(lambda: ws._push_one((gid, 1)))
            alone = len(seen)
        with lookups() as seen:
            # the pusher's own thread: contexts cannot nest
            thread = threading.Thread(target=ws._push_batch, args=([(gid, pid) for pid in conns], self.ndb_client))
            thread.start()
            thread.join()
        self.assertEqual(len(seen), alone + 2, "one more read per extra player, none per extra Game")
        self.assertEqual([len(conn.sent) for conn in conns.values()], [2, 1, 1])

    def test_a_tick_sees_a_grant_made_after_its_own_last_write(self):
        gid = 9621
        make_game(gid, MultiplayerGameType.SHARED, 2, str_shared=["Skills", "Upgrades"])
        team = [ndb.Key(Game, gid, Player, "%s.%s" % (gid, pid)) for pid in (1, 2)]

        def teammate_finds_an_upgrade():
            Player.transaction_pickup_batch(team, [(Pickup.n("RB", 6), False, None, None)])
            Cache.clear_seen_checksum((gid, 1))

        conn = ScriptedConn([
            tick_frame(seen_0="1"),      # writes this player through a txn
            tick_frame(seen_0="1"),      # fast path: no datastore call
            lambda: self._elsewhere(teammate_finds_an_upgrade),
            tick_frame(seen_0="1"),
        ])
        ws.run_connection(conn, gid, 1)

        self.assertEqual(len(conn.sent), 3)
        self.assertIn("6x1", conn.sent[-1], "the tick after a teammate's grant was read from the socket's own cache")


if __name__ == "__main__":
    unittest.main()
