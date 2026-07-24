"""Unit tests for the netcode/cache rework (2026-07).

Self-contained: no datastore emulator, no memcached, no Flask app. Model logic
runs in an in-memory ndb context (anonymous credentials, no RPCs) and the
memcached client is replaced with a faithful stub.

Run from the repo root:  python3 -m unittest test.netcode_test -v
"""
import json
import time as time_mod
import unittest
from datetime import datetime, timedelta

import google.auth.credentials
from google.cloud import ndb
from google.cloud.ndb.model import _BaseValue

import cache as cache_mod
import models
import util
from models import BingoCard, BingoCardProgress, Game, HistoryLine, Player
from pickups import Pickup


class FakeMemcache(object):
    """In-memory stand-in for a pymemcache client.

    Faithful where it matters: add() can only report an existing-key failure
    when called with noreply=False. This mirrors real pymemcache, where the
    default noreply makes add() return True unconditionally -- the bug that
    silently disabled san_check's rate limiting for years. If someone removes
    noreply=False from the gate calls, the gate tests below fail.
    """

    def __init__(self):
        self.d = {}

    def get(self, key):
        return self.d.get(key)

    def set(self, key, value, expire=0, noreply=None):
        self.d[key] = value
        return True

    def add(self, key, value, expire=0, noreply=None):
        exists = key in self.d
        if not exists:
            self.d[key] = value
        if noreply is False:
            return not exists
        return True  # with noreply, pymemcache cannot report failure

    def delete(self, key, noreply=None):
        self.d.pop(key, None)

    def get_many(self, keys):
        return {k: self.d[k] for k in keys if k in self.d}

    def delete_multi(self, keys, key_prefix="", noreply=None):
        for k in keys:
            self.d.pop(key_prefix + k, None)


def fake_memcached_cache():
    mc = cache_mod.MemcachedCache.__new__(cache_mod.MemcachedCache)
    mc.memcache = FakeMemcache()
    return mc


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


class TestBfieldChecksum(unittest.TestCase):
    def test_stable_and_type_agnostic(self):
        a = util.bfield_checksum(str(x) for x in [1, 2, 3])
        b = util.bfield_checksum([1, 2, 3])
        self.assertEqual(a, b)
        self.assertEqual(util.bfield_checksum([0] * 8), util.bfield_checksum(["0"] * 8))

    def test_sensitive(self):
        base = util.bfield_checksum([1, 2, 3])
        self.assertNotEqual(base, util.bfield_checksum([1, 2, 4]))
        self.assertNotEqual(base, util.bfield_checksum([3, 2, 1]))


class TestJsonDefault(unittest.TestCase):
    def test_unwraps_base_values(self):
        board = {"progress": {"1": {"completed": _BaseValue(False),
                                    "count": _BaseValue(3),
                                    "subgoals": [_BaseValue("a")]}}}
        out = json.loads(json.dumps(board, default=util.json_default))
        self.assertEqual(out["progress"]["1"],
                         {"completed": False, "count": 3, "subgoals": ["a"]})

    def test_coerces_unknown_to_str(self):
        class Weird(object):
            def __str__(self):
                return "weird"
        self.assertEqual(json.dumps({"x": Weird()}, default=util.json_default),
                         '{"x": "weird"}')


class TestSplitCache(unittest.TestCase):
    def setUp(self):
        self._orig = cache_mod.SPLIT_CACHE
        self.mc = fake_memcached_cache()

    def tearDown(self):
        cache_mod.SPLIT_CACHE = self._orig

    def test_split_layout_round_trips(self):
        cache_mod.SPLIT_CACHE = True
        mc = self.mc
        mc.set_pos(7, 1, 10, 20)
        mc.set_pos(7, 2, 30, 40)
        self.assertEqual(mc.get_pos(7), {1: (10, 20), 2: (30, 40)})
        self.assertIn("7.1.pos", mc.memcache.d)
        # merge semantics: subset writes don't clobber other players
        mc.set_have(7, {1: [100, 2]})
        mc.set_have(7, {2: [200, 2]})
        self.assertEqual(mc.get_have(7), {1: [100, 2], 2: [200, 2]})
        mc.set_reachable(7, {1: {"m": ["a"]}})
        mc.set_reachable(7, {2: {"m": ["b"]}})
        self.assertEqual(mc.get_reachable(7), {1: {"m": ["a"]}, 2: {"m": ["b"]}})
        mc.clear_reach(7, 1)
        self.assertEqual(mc.get_reachable(7)[1], {})
        mc.set_hist(7, 1, ["h1"])
        mc.append_hl(7, 1, "h2")
        mc.append_hl(7, 2, "h3")
        self.assertEqual(mc.get_hist(7), {1: ["h1", "h2"], 2: ["h3"]})
        self.assertEqual(sorted(mc._pids(7)), [1, 2])

    def test_split_remove_game_cleans_per_player_keys(self):
        cache_mod.SPLIT_CACHE = True
        mc = self.mc
        mc.set_pos(7, 1, 10, 20)
        mc.set_hist(7, 1, ["h"])
        mc.remove_game(7)
        self.assertEqual(mc.get_pos(7), {})
        self.assertEqual(mc.get_hist(7), {})
        self.assertEqual(mc._pids(7), [])
        leftovers = [k for k in mc.memcache.d if k.startswith("7.")]
        self.assertEqual(leftovers, [])

    def test_legacy_layout_and_merge(self):
        cache_mod.SPLIT_CACHE = False
        mc = self.mc
        mc.set_pos(7, 1, 10, 20)
        mc.set_pos(7, 2, 30, 40)
        self.assertEqual(mc.get_pos(7), {1: (10, 20), 2: (30, 40)})
        self.assertIn("7.pos", mc.memcache.d)
        self.assertNotIn("7.1.pos", mc.memcache.d)
        # merge semantics hold in legacy mode too (callers pass subsets now)
        mc.set_have(7, {1: [100]})
        mc.set_have(7, {2: [200]})
        self.assertEqual(mc.get_have(7), {1: [100], 2: [200]})

    def test_gates_require_noreply_false(self):
        # if san_check/second_strike stop passing noreply=False, FakeMemcache
        # reverts to pymemcache's lying default and these assertions fail
        mc = self.mc
        self.assertTrue(mc.san_check(99))
        self.assertFalse(mc.san_check(99))
        self.assertFalse(mc.second_strike(99))
        self.assertTrue(mc.second_strike(99))


class TestDevCache(unittest.TestCase):
    def test_ttl_and_add(self):
        c = cache_mod.TLRUCacheWithCustomExpiry(64, timer=time_mod.monotonic)
        c.set("k", "v", time=0.05)
        self.assertEqual(c.get("k"), "v")
        self.assertTrue(c.add("other", 1, time=10))
        self.assertFalse(c.add("other", 2, time=10))
        time_mod.sleep(0.08)
        self.assertIsNone(c.get("k"))

    def test_python_cache_merge_and_gates(self):
        pc = cache_mod.PythonCache()
        pc.set_have(7, {1: [100]})
        pc.set_have(7, {2: [200]})
        self.assertEqual(pc.get_have(7), {1: [100], 2: [200]})
        pc.set_reachable(7, {1: {"m": ["a"]}})
        pc.set_reachable(7, {2: {"m": ["b"]}})
        self.assertEqual(pc.get_reachable(7), {1: {"m": ["a"]}, 2: {"m": ["b"]}})
        self.assertTrue(pc.san_check(98))
        self.assertFalse(pc.san_check(98))
        self.assertFalse(pc.second_strike(98))
        self.assertTrue(pc.second_strike(98))


class TestGivePickup(NdbTestCase):
    def test_delay_put_semantics(self):
        p = Player(id="9.1", skills=0, events=0, teleporters=0, bonuses={}, hints={})
        sk = Pickup.n("SK", "50")
        ev = Pickup.n("EV", "0")
        rb = Pickup.n("RB", "17")  # stacking bonus
        for pk in [sk, ev, rb, rb]:
            p.give_pickup(pk, delay_put=True)
        self.assertTrue(p.has_pickup(sk))
        self.assertTrue(p.has_pickup(ev))
        self.assertEqual(p.bonuses["17"], 2)
        p.give_pickup(rb, remove=True, delay_put=True)
        self.assertEqual(p.bonuses["17"], 1)
        p.give_pickup(sk, coords=555, finder=2, delay_put=True)
        self.assertEqual(p.hints["555"], 2)


class TestHistoryMerge(NdbTestCase):
    def setUp(self):
        super(TestHistoryMerge, self).setUp()
        self._orig = models.HIST_ON_PLAYER

    def tearDown(self):
        models.HIST_ON_PLAYER = self._orig
        super(TestHistoryMerge, self).tearDown()

    def _game(self):
        t0 = datetime(2026, 7, 20, 12, 0, 0)
        legacy = HistoryLine(pickup_code="SK", pickup_id="5", coords=100, player=2, timestamp=t0)
        p1 = Player(id="9.1", history=[
            HistoryLine(pickup_code="EX", pickup_id="4", coords=200, player=None,
                        timestamp=t0 + timedelta(seconds=30)),
            HistoryLine(pickup_code="EC", pickup_id="1", coords=300, player=1,
                        timestamp=t0 + timedelta(seconds=10)),
        ])
        g = Game(id="9")
        g.hls = [legacy]
        g.get_players = lambda: [p1]
        return g

    def test_merged_ordering_backfill_filtering(self):
        models.HIST_ON_PLAYER = True
        g = self._game()
        h = g.history()
        self.assertEqual([x.coords for x in h], [100, 300, 200])  # timestamp order
        self.assertEqual(h[2].player, 1)  # backfilled from owning player
        self.assertEqual(len(g.history([1])), 2)
        self.assertEqual([x.coords for x in g.history([2])], [100])

    def test_legacy_path_unchanged_when_hls_present(self):
        models.HIST_ON_PLAYER = False
        g = self._game()
        self.assertEqual([x.coords for x in g.history()], [100])


class TestBingoDebounce(NdbTestCase):
    """BingoCard.update: gains instant; losses staged then confirmed by the
    same player; teammates can't fast-track; meta squares bypass everything."""

    def _setup(self, goal_type="int", target=3, completed_by=None, meta=False,
               goal_method=None, subgoals=None):
        card = BingoCard(name="TestGoal", goal_type=goal_type, target=target,
                         square=0, meta=meta, goal_method=goal_method,
                         subgoals=subgoals or [])
        card.completed_by = completed_by if completed_by is not None else []
        p1 = Player(id="9.1", bingo_prog=[BingoCardProgress(square=0)])
        p2 = Player(id="9.2", bingo_prog=[BingoCardProgress(square=0)])
        return card, p1, p2

    def test_gain_is_immediate(self):
        card, p1, p2 = self._setup()
        ev = card.update({"value": 5}, p1, [], p1.key)
        self.assertIsNotNone(ev)
        self.assertFalse(ev.loss)

    def test_loss_staged_then_confirmed_by_same_player(self):
        card, p1, p2 = self._setup(completed_by=[1])
        p1.bingo_prog[0].completed = True
        p1.bingo_prog[0].count = 3
        # regression arrives: staged, not applied
        ev = card.update({"value": 1}, p1, [], p1.key)
        self.assertIsNone(ev)
        self.assertTrue(p1.bingo_prog[0].pending_loss)
        # second consecutive regressed update: loss applies
        ev = card.update({"value": 1}, p1, [], p1.key)
        self.assertIsNotNone(ev)
        self.assertTrue(ev.loss)
        self.assertFalse(p1.bingo_prog[0].pending_loss)

    def test_restore_before_confirm_self_heals_silently(self):
        card, p1, p2 = self._setup(completed_by=[1])
        p1.bingo_prog[0].completed = True
        p1.bingo_prog[0].count = 3
        self.assertIsNone(card.update({"value": 1}, p1, [], p1.key))  # staged
        ev = card.update({"value": 4}, p1, [], p1.key)  # stale post superseded
        self.assertIsNone(ev)  # no gain event: square never visibly lost
        self.assertFalse(p1.bingo_prog[0].pending_loss)

    def test_teammate_cannot_stage_someone_elses_loss(self):
        card, p1, p2 = self._setup(completed_by=[1])
        # p1 completed it once, but p1's stored progress has already regressed
        p1.bingo_prog[0].completed = False
        p1.bingo_prog[0].count = 1
        # p2 (never completed it) posts: sees team regression but must not stage
        ev = card.update({"value": 1}, p2, [p1], p1.key)
        self.assertIsNone(ev)
        self.assertFalse(p2.bingo_prog[0].pending_loss)

    def test_teammate_progress_keeps_square_completed(self):
        card, p1, p2 = self._setup(completed_by=[1])
        p1.bingo_prog[0].completed = True
        p1.bingo_prog[0].count = 3
        # p2 posts an incomplete state; team stays complete via p1 -> no event
        ev = card.update({"value": 0}, p2, [p1], p1.key)
        self.assertIsNone(ev)

    def test_meta_bypasses_debounce_both_directions(self):
        card, p1, p2 = self._setup(goal_type="bool", target=None,
                                   completed_by=[1], meta=True)
        p1.bingo_prog[0].completed = True
        ev = card.update({"value": False}, p1, [p2], p1.key)
        self.assertIsNotNone(ev)  # immediate loss, no staging
        self.assertTrue(ev.loss)
        card.completed_by = []
        ev = card.update({"value": True}, p1, [p2], p1.key)
        self.assertIsNotNone(ev)
        self.assertFalse(ev.loss)

    def test_multi_and_union_across_team(self):
        subgoals = [{"name": "A"}, {"name": "B"}]
        card, p1, p2 = self._setup(goal_type="multi", goal_method="and",
                                   target=None, subgoals=subgoals)
        p2.bingo_prog[0].completed_subgoals = ["B"]
        ev = card.update({"total": 1, "value": {"A": {"value": True},
                                                "B": {"value": False}}},
                         p1, [p2], p1.key)
        self.assertIsNotNone(ev)  # union {A} | {B} completes the "and"
        self.assertFalse(ev.loss)


class TestMultiworldFoundPickup(NdbTestCase):
    """Game.found_pickup in MULTIWORLD mode: an MW find flips the owner's
    slot bit and busts their tick cache; own-world finds are server-passive.
    Shared categories (mw shared singletons, 2026-07-23) fan out to every
    player; MW pickups, TW warps and EV5 never do."""

    def setUp(self):
        super(TestMultiworldFoundPickup, self).setUp()
        self._txn = Player.mark_slot_txn
        self._btxn = Player.mark_slots_txn
        self._ptxn = Player.transaction_pickup
        self._pbtxn = Player.transaction_pickup_batch
        self._hop = models.HIST_ON_PLAYER
        models.HIST_ON_PLAYER = False

    def tearDown(self):
        Player.mark_slot_txn = self._txn
        Player.mark_slots_txn = self._btxn
        Player.transaction_pickup = self._ptxn
        Player.transaction_pickup_batch = self._pbtxn
        models.HIST_ON_PLAYER = self._hop
        super(TestMultiworldFoundPickup, self).tearDown()

    def _game(self, shared=None):
        finder = Player(id="77.1", skills=0, events=0, teleporters=0, bonuses={}, hints={})
        owner = Player(id="77.2", skills=0, events=0, teleporters=0, bonuses={}, hints={})
        for p in (finder, owner):
            p.put = lambda *a, **k: None
        g = Game(id="77", str_mode="Multiworld", str_shared=shared or [])
        g.get_players = lambda: [finder, owner]
        g.player = lambda pid, create=True, delay_put=False: {1: finder, 2: owner}[pid]
        g.hist = []
        g.append_hl = g.hist.append  # bypass the transactional history write
        by_key = {p.key: p for p in (finder, owner)}
        Player.mark_slot_txn = staticmethod(lambda pkey, slot: by_key[pkey].mark_slot(slot))
        Player.mark_slots_txn = staticmethod(
            lambda pkey, slots: sum(1 for s in slots if by_key[pkey].mark_slot(s)))
        Player.transaction_pickup = staticmethod(
            lambda pkey, pickup, remove=False, delay_put=False, coords=None, finder=None:
                by_key[pkey].give_pickup(pickup, remove, delay_put=True))
        Player.transaction_pickup_batch = staticmethod(
            lambda pkeys, grants: [by_key[k].give_pickup(g_[0], g_[1], delay_put=True)
                                   for k in pkeys for g_ in grants])
        return g, finder, owner

    def test_mw_find_flips_owner_slot_and_busts_cache(self):
        from cache import Cache
        g, finder, owner = self._game()
        Cache.set_seen_checksum(owner.idpts(), 999)
        pickup = Pickup.n("MW", "2,17,Bash")
        status = g.found_pickup(1, pickup, 555, False, False, "Glades")
        self.assertEqual(status, 200)
        self.assertTrue(owner.slot_check(17))
        self.assertIsNone(Cache.get_seen_checksum(owner.idpts()))
        self.assertEqual(finder.skills, 0)  # the finder gets nothing granted
        self.assertEqual(owner.skills, 0)   # ...and neither does the owner (client-side grant)
        self.assertEqual(len(g.hist), 1)    # but history remembers
        self.assertEqual(g.hist[0].pickup_code, "MW")

    def test_repeat_find_is_idempotent(self):
        from cache import Cache
        g, finder, owner = self._game()
        pickup = Pickup.n("MW", "2,17,Bash")
        g.found_pickup(1, pickup, 555, False, False, "Glades")
        Cache.set_seen_checksum(owner.idpts(), 123)  # owner ticked since
        g.found_pickup(1, pickup, 555, False, False, "Glades")
        self.assertTrue(owner.slot_check(17))
        # no re-flip: the owner's rearmed cache survives the duplicate
        self.assertEqual(Cache.get_seen_checksum(owner.idpts()), 123)

    def test_own_world_find_is_server_passive(self):
        g, finder, owner = self._game()
        status = g.found_pickup(1, Pickup.n("SK", "0"), 999, False, False, "Glades")
        self.assertEqual(status, 200)
        self.assertEqual(finder.skills, 0)  # no server-side grant in MW
        self.assertEqual(owner.skills, 0)
        self.assertEqual(len(g.hist), 1)

    class _FakeParams(object):
        """Finisher's world holds two of P2's items, one manifest line (P1's
        own slot, must be ignored), and an own-world pickup."""
        def get_seed_data(self, pid):
            assert pid == 1
            return [("100", "MW", "2,3,Keystone", "Glades"),
                    ("200", "MW", "2,7,Bash", "Grove"),
                    ("-2", "MW", "2,SK,50", "Grotto"),
                    ("300", "SK", "0", "Glades")]

    def test_release_grants_unfound_items_to_owners(self):
        from cache import Cache
        g, finder, owner = self._game()
        owner.mark_slot(3)  # already found earlier: not re-released
        Cache.set_seen_checksum(owner.idpts(), 55)
        released = g.mw_release(1, params=self._FakeParams())
        self.assertEqual(released, 1)  # only slot 7 was new
        self.assertTrue(owner.slot_check(7))
        self.assertIsNone(Cache.get_seen_checksum(owner.idpts()))
        self.assertTrue(any(s.startswith("msg:") for s in owner.signals))
        # releasing again: nothing new, no duplicate signal spam
        again = g.mw_release(1, params=self._FakeParams())
        self.assertEqual(again, 0)
        self.assertEqual(len([s for s in owner.signals if s.startswith("msg:")]), 1)

    def test_mw_find_processes_even_when_coords_already_seen(self):
        """Regression (game 133746, player 3's missing release): the finder's
        1Hz tick can deliver the seen bit for a location BEFORE its found POST
        arrives, and the seen-coords dedup was silently dropping the whole MW
        branch -- slot flips included. MW skips that dedup (idempotent)."""
        g, finder, owner = self._game()
        finder.seen_coords = lambda: [555, 2]  # tick got there first
        pickup = Pickup.n("MW", "2,17,Bash")
        status = g.found_pickup(1, pickup, 555, False, False, "Glades")
        self.assertEqual(status, 200)
        self.assertTrue(owner.slot_check(17), "slot flip must survive the seen-race")

    def test_shared_singleton_fans_out(self):
        g, finder, owner = self._game(shared=["Skills", "WorldEvents"])
        status = g.found_pickup(1, Pickup.n("SK", "0"), 999, False, False, "Glades")
        self.assertEqual(status, 200)
        self.assertNotEqual(finder.skills, 0)  # finder's server entity converges
        self.assertEqual(owner.skills, finder.skills)
        status = g.found_pickup(2, Pickup.n("EV", "0"), 888, False, False, "Ginso")
        self.assertEqual(status, 200)
        self.assertEqual(owner.events, finder.events)
        self.assertNotEqual(finder.events, 0)

    def test_unshared_category_stays_local(self):
        g, finder, owner = self._game(shared=["Skills"])
        g.found_pickup(1, Pickup.n("EV", "0"), 888, False, False, "Ginso")
        self.assertEqual(finder.events, 0)  # WorldEvents not shared: server-passive
        self.assertEqual(owner.events, 0)

    def test_shared_never_touches_warmth_warps_or_mw(self):
        g, finder, owner = self._game(shared=["Skills", "WorldEvents", "Teleporters"])
        g.found_pickup(1, Pickup.n("EV", "5"), 777, False, False, "Horu")
        self.assertEqual(finder.events, 0)  # each world's finale stays its own
        self.assertEqual(owner.events, 0)
        g.found_pickup(1, Pickup.n("TW", "Warp to Sorrow,-600,400,SorrowWarp"), 666, False, False, "Sorrow")
        self.assertEqual(owner.bonuses, {})  # warps are world-local
        g.found_pickup(1, Pickup.n("MW", "2,17,Bash"), 555, False, False, "Glades")
        self.assertTrue(owner.slot_check(17))
        self.assertEqual(owner.skills, 0)  # slot flip, not a grant


class TestBingoV2(NdbTestCase):
    def test_lock_identity(self):
        self.assertIs(models.bingo_lock(5), models.bingo_lock(5))
        self.assertIsNot(models.bingo_lock(5), models.bingo_lock(6))
        with models.bingo_lock(5):
            pass  # acquirable and releasable

    def _stub_puts(self, *entities):
        for e in entities:
            e.put = lambda *a, **k: None

    def test_event_log_cap_preserves_misc_markers(self):
        from models import BingoEvent, BingoGameData
        bgd = BingoGameData(id="55")
        markers = [BingoEvent(event_type="miscBingo Game 55 created!"),
                   BingoEvent(event_type="miscBingo Game 55 started!")]
        bgd.event_log = markers + [BingoEvent(event_type="square") for _ in range(600)]
        bgd._update_inner = lambda *a, **k: None
        bgd.update_v2({}, 1, 55)
        self.assertEqual(len(bgd.event_log), 402)
        self.assertTrue(bgd.event_log[0].event_type.startswith("misc"))
        self.assertTrue(bgd.event_log[1].event_type.startswith("misc"))
        # under the cap: untouched
        bgd.event_log = markers + [BingoEvent(event_type="square") for _ in range(10)]
        bgd.update_v2({}, 1, 55)
        self.assertEqual(len(bgd.event_log), 12)

    def test_update_v2_full_flow_in_memory(self):
        """The whole non-transactional update path: a posted goal completion
        lands as an event, completed_by membership, score, and a board stash."""
        from models import BingoGameData, BingoTeam
        card = BingoCard(name="TestGoal", goal_type="int", target=3, square=0)
        filler = [BingoCard(name="Filler%s" % i, goal_type="int", target=99, square=i)
                  for i in range(1, 25)]
        p1 = Player(id="55.1", bingo_prog=[BingoCardProgress(square=i) for i in range(25)])
        bgd = BingoGameData(id="55")
        bgd.board = [card] + filler
        bgd.teams = [BingoTeam(captain=p1.key, teammates=[])]
        bgd.bingo_count = 99  # out of reach: no win/signal path in this test
        bgd.start_time = datetime(2026, 7, 20, 12, 0, 0)
        bgd.game = ndb.Key("Game", 55)
        bgd.get_players = lambda: [p1]
        self._stub_puts(p1, bgd)

        bgd.update_v2({"TestGoal": {"value": 5}}, 1, 55)

        self.assertIn(1, card.completed_by)
        square_events = [e for e in bgd.event_log if e.event_type == "square"]
        self.assertEqual(len(square_events), 1)
        self.assertFalse(square_events[0].loss)
        self.assertEqual(bgd.teams[0].score, 1)
        board = getattr(bgd, "_board_json", None)
        self.assertIsNotNone(board)
        self.assertEqual(board["cards"][0]["completed_by"], [1])
        # idempotent re-post: no duplicate events, state stable
        bgd.update_v2({"TestGoal": {"value": 5}}, 1, 55)
        self.assertEqual(len([e for e in bgd.event_log if e.event_type == "square"]), 1)


if __name__ == "__main__":
    unittest.main()
