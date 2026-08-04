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
from enums import MultiplayerGameType
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

    def test_reader_merges_regardless_of_flag(self):
        # CHANGED 2026-07-25 (CHUNKED_LOGS): this used to assert [100] -- the
        # legacy reader returned Game.hls alone and hid Player.history. That
        # made a flag flip lossy: lines written while HIST_ON_PLAYER was on
        # disappeared from the tracker the moment it was turned off. Readers now
        # merge every layout unconditionally; only writes follow the flags.
        models.HIST_ON_PLAYER = False
        g = self._game()
        self.assertEqual([x.coords for x in g.history()], [100, 300, 200])

    def test_duplicate_lines_across_layouts_collapse(self):
        # guards the one unsafe merge shape: the pre-2018 read-time migration
        # copied Player.history into Game.hls without clearing the source
        models.HIST_ON_PLAYER = False
        g = self._game()
        g.hls = list(g.hls) + [HistoryLine(pickup_code="EC", pickup_id="1", coords=300,
                                           player=1, timestamp=datetime(2026, 7, 20, 12, 0, 10))]
        self.assertEqual([x.coords for x in g.history()], [100, 300, 200])


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

    def _game(self, shared=None, extra_pids=()):
        finder = Player(id="77.1", skills=0, events=0, teleporters=0, bonuses={}, hints={})
        owner = Player(id="77.2", skills=0, events=0, teleporters=0, bonuses={}, hints={})
        players = {1: finder, 2: owner}
        for pid in extra_pids:
            players[pid] = Player(id="77.%s" % pid, skills=0, events=0, teleporters=0, bonuses={}, hints={})
        for p in players.values():
            p.put = lambda *a, **k: None
        g = Game(id="77", str_mode="Multiworld", str_shared=shared or [])
        g.get_players = lambda: list(players.values())
        g.player = lambda pid, create=True, delay_put=False: players[pid]
        g.hist = []
        g.append_hl = g.hist.append  # bypass the transactional history write
        by_key = {p.key: p for p in players.values()}
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

    class _FakeApParams(object):
        """AP-mode: finisher's world holds one of P2's items plus two
        AP-reserved slots owned by the world's shadow (K+1 = 3)."""
        players = 2
        ap_mode = True

        def get_seed_data(self, pid):
            assert pid == 1
            return [("100", "MW", "2,3,Keystone", "Glades"),
                    ("400", "MW", "3,0,AP Item #1", "Grove"),
                    ("450", "MW", "3,1,AP Item #2", "Grove"),
                    ("-2", "MW", "4,SK,50", "Grotto"),
                    ("300", "SK", "0", "Glades")]

    def test_release_skips_ap_shadow_slots(self):
        """ori must never force-check AP slots: whether the room releases on
        goal is the AP room's policy. (self.player(3) would KeyError here if
        the shadow-owned lines slipped through.)"""
        g, finder, owner = self._game()
        released = g.mw_release(1, params=self._FakeApParams())
        self.assertEqual(released, 1)  # P2's slot 3 only
        self.assertTrue(owner.slot_check(3))
        self.assertFalse(owner.slot_check(0))
        self.assertFalse(owner.slot_check(1))

    class _FakeParams3(object):
        """Non-AP params (no ap_mode attr) whose finisher world holds an item
        for player 3 -- the shadow skip must be AP-gated, not pid-gated."""
        def get_seed_data(self, pid):
            return [("400", "MW", "3,5,Bash", "Grove")]

    def test_release_shadow_skip_is_ap_gated(self):
        g, finder, owner = self._game(extra_pids=(3,))
        released = g.mw_release(1, params=self._FakeParams3())
        self.assertEqual(released, 1)
        self.assertTrue(g.player(3).slot_check(5))

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


class TestApShadowPlayers(NdbTestCase):
    """AP-mode game creation (Game.from_params): shadow players K+1..2K exist
    from birth as the bridge's durable outbox, and the tick names field
    renders them '<K+w>.Archipelago'. Datastore ops are stubbed at
    Player.get_by_id / put (an in-memory store), session-test style."""

    class _ApParams(object):
        players = 2
        ap_mode = True
        key = None
        variations = []

        class sync(object):
            shared = []
            mode = MultiplayerGameType.MULTIWORLD
            dedup = False
            teams = None

    def setUp(self):
        super(TestApShadowPlayers, self).setUp()
        self._pput = Player.put
        self._gput = Game.put
        self._uget = models.User.__dict__["get"]
        self._rebuild = Game.rebuild_hist
        self.store = {}

        def fake_get_by_id(pid, parent=None):
            return self.store.get(pid)

        def fake_put(p, *a, **k):
            self.store[p.key.id()] = p
            return p.key
        Player.get_by_id = staticmethod(fake_get_by_id)
        Player.put = fake_put
        Game.put = lambda g, *a, **k: g.key
        models.User.get = staticmethod(lambda: None)
        Game.rebuild_hist = lambda g: None

    def tearDown(self):
        del Player.get_by_id  # restore the inherited ndb classmethod
        Player.put = self._pput
        Game.put = self._gput
        models.User.get = self._uget
        Game.rebuild_hist = self._rebuild
        super(TestApShadowPlayers, self).tearDown()

    def _patch_key_get(self, game):
        """Route ndb.Key.get through the in-memory store (mw_names_field
        resolves the parent game and its player keys)."""
        orig = ndb.Key.get

        def fake_key_get(k, *a, **kw):
            if k == game.key:
                return game
            return self.store.get(k.id())
        ndb.Key.get = fake_key_get
        self.addCleanup(lambda: setattr(ndb.Key, "get", orig))

    def test_from_params_creates_shadows(self):
        game = Game.from_params(self._ApParams(), gid=70)
        self.assertEqual(game.player_nums(), [1, 2, 3, 4])
        for w in (3, 4):
            self.assertEqual(self.store["70.%s" % w].nickname, "Archipelago")
        for w in (1, 2):
            self.assertIsNone(self.store["70.%s" % w].nickname)

    def test_names_field_renders_shadow_pairs(self):
        from cache import Cache
        game = Game.from_params(self._ApParams(), gid=71)
        self._patch_key_get(game)
        shadow = self.store["71.3"]
        names = shadow.mw_names_field()
        self.assertEqual(names, "1.Player 1;2.Player 2;3.Archipelago;4.Archipelago")
        # the tick output serves the same field at index 7
        fields = self.store["71.1"].output(include_slots=True).split(",")
        self.assertEqual(fields[7], names)
        self.assertEqual(Cache.get_names(71), names)

    def test_creation_invalidates_stale_names(self):
        from cache import Cache
        Cache.set_names(72, "stale")
        Game.from_params(self._ApParams(), gid=72)
        self.assertIsNone(Cache.get_names(72))

    def test_shadow_creation_is_idempotent(self):
        game = Game.from_params(self._ApParams(), gid=73)
        n = len(self.store)
        game.create_ap_shadows(self._ApParams())
        self.assertEqual(len(self.store), n)
        self.assertEqual(game.player_nums(), [1, 2, 3, 4])

    def test_non_ap_games_get_no_shadows(self):
        params = self._ApParams()
        params.ap_mode = False
        game = Game.from_params(params, gid=74)
        self.assertEqual(game.player_nums(), [1, 2])


class TestAPLink(NdbTestCase):
    """The bridge's durable connection record (ap_models.APLink)."""

    def test_make_defaults(self):
        from ap_models import APLink
        link = APLink.make(44, 3)
        self.assertEqual(link.key.id(), 44)
        self.assertEqual(link.slot_names, ["Ori1", "Ori2", "Ori3"])
        self.assertEqual(link.recv_index, [0, 0, 0])
        self.assertFalse(link.enabled)
        self.assertEqual(link.status, "disconnected")

    def test_slot_names_follow_the_yaml_convention(self):
        # to_ap_yaml and APLink.make both go through ap_slot_name: the name in
        # the emitted yaml and the name the bridge connects with must agree
        from ap_models import ap_slot_name
        self.assertEqual(ap_slot_name(1), "Ori1")
        self.assertEqual(ap_slot_name("3"), "Ori3")

    def test_report_shape(self):
        from ap_models import APLink
        link = APLink.make(45, 1)
        link.host, link.port = "ap.example", 38281
        link.enabled, link.status = True, "pending"
        rep = link.report()
        self.assertEqual(rep["host"], "ap.example")
        self.assertEqual(rep["port"], 38281)
        self.assertEqual(rep["slots"], ["Ori1"])
        self.assertEqual(rep["recv_index"], [0])
        self.assertTrue(rep["enabled"])
        self.assertEqual(rep["status"], "pending")
        self.assertIsNone(rep["last_error"])
        self.assertIsNone(rep["last_activity"])  # auto_now lands at put
        # scout progress: empty until the bridge has been in the room
        self.assertEqual(rep["names_total"], [])
        self.assertEqual(rep["names_resolved"], [])

    def test_report_carries_name_counts(self):
        from ap_models import APLink
        link = APLink.make(46, 2)
        link.name_totals, link.name_counts = [111, 108], [111, 0]
        rep = link.report()
        self.assertEqual(rep["names_total"], [111, 108])
        self.assertEqual(rep["names_resolved"], [111, 0])


class TestDisplayNames(unittest.TestCase):
    """Sanitizing what the Archipelago room tells us an item is called.

    The label ends up in '<loc>|MW|<owner>,<slot>,<label>|<zone>', which the
    client splits on '|' and then on ',' with maxsplit 3, and also pastes
    unescaped into /found/<coords>/<kind>/<id>."""

    def test_pipe_is_fatal_and_goes(self):
        from ap_models import sanitize_display_name
        self.assertEqual(sanitize_display_name("a|b"), "a b")

    def test_comma_survives(self):
        # last field of a maxsplit-bounded value on both sides of the wire
        from ap_models import sanitize_display_name
        self.assertEqual(sanitize_display_name("Bow, Silver Arrows"), "Bow, Silver Arrows")

    def test_url_and_message_hazards_go(self):
        from ap_models import sanitize_display_name
        for hazard in "/\\?#%$*@\"<>;{}[]^~`\r\n\t":
            self.assertNotIn(hazard, sanitize_display_name("x%sy" % hazard),
                             "%r survived" % hazard)

    def test_harmless_punctuation_stays(self):
        from ap_models import sanitize_display_name
        self.assertEqual(sanitize_display_name("Zelda's Bow (Progressive) 2: A+B & C!"),
                         "Zelda's Bow (Progressive) 2: A+B & C!")

    def test_non_ascii_goes(self):
        from ap_models import sanitize_display_name
        self.assertEqual(sanitize_display_name("Pokeball ★ café"), "Pokeball caf")

    def test_lengths_are_capped(self):
        from ap_models import ap_display_name, ITEM_NAME_MAX, PLAYER_NAME_MAX
        label = ap_display_name("i" * 200, "p" * 200)
        self.assertEqual(label, "%s (%s)" % ("i" * ITEM_NAME_MAX, "p" * PLAYER_NAME_MAX))

    def test_unnameable_item_yields_nothing(self):
        # the caller reads "" as "keep the AP Item #n placeholder"
        from ap_models import ap_display_name
        self.assertEqual(ap_display_name(None, "Ori2"), "")
        self.assertEqual(ap_display_name("|||", "Ori2"), "")

    def test_nameless_player_still_names_the_item(self):
        from ap_models import ap_display_name
        self.assertEqual(ap_display_name("Bash", None), "Bash")


class TestAPNames(NdbTestCase):
    """APNames: one world's scouted labels, stored as JSON (put/get_by_id
    stubbed in-memory, session_golden_test style)."""

    def setUp(self):
        super(TestAPNames, self).setUp()
        from ap_models import APNames
        self.rows = {}

        def fake_put(row, *a, **k):
            self.rows[row.key.id()] = row
            return row.key
        APNames.put = fake_put
        APNames.get_by_id = staticmethod(lambda rid: self.rows.get(rid))

    def tearDown(self):
        from ap_models import APNames
        del APNames.put
        del APNames.get_by_id
        super(TestAPNames, self).tearDown()

    def test_round_trip_int_keys(self):
        from ap_models import APNames
        APNames.store(88, 2, {0: "Bash (Ori2)", 40: "A Click (Questy)"})
        self.assertEqual(list(self.rows), ["88.2"])
        self.assertEqual(self.rows["88.2"].scouted, 2)
        self.assertEqual(APNames.load(88, 2), {0: "Bash (Ori2)", 40: "A Click (Questy)"})

    def test_worlds_do_not_share_a_row(self):
        # K threads scout concurrently; per-world keys keep them apart
        from ap_models import APNames
        APNames.store(88, 1, {0: "one"})
        APNames.store(88, 2, {0: "two"})
        self.assertEqual(APNames.load(88, 1), {0: "one"})
        self.assertEqual(APNames.load(88, 2), {0: "two"})

    def test_missing_or_corrupt_row_is_empty_not_fatal(self):
        from ap_models import APNames
        self.assertEqual(APNames.load(88, 9), {})
        APNames.store(88, 1, {})
        self.assertEqual(APNames.load(88, 1), {})
        self.rows["88.1"].names = "not json at all"
        self.assertEqual(APNames.load(88, 1), {})


class TestNameCountVector(unittest.TestCase):
    def test_pads_and_sets(self):
        # -1 padding, so a padded world never reads as a complete "0 of 0"
        from archipelago.ap_bridge import _at_world
        self.assertEqual(_at_world([], 3, 7), [-1, -1, 7])
        self.assertEqual(_at_world(None, 1, 4), [4])
        self.assertEqual(_at_world([1, 2, 3], 2, 9), [1, 9, 3])

    def test_does_not_mutate_the_input(self):
        from archipelago.ap_bridge import _at_world
        vals = [1, 2]
        self.assertEqual(_at_world(vals, 1, 5), [5, 2])
        self.assertEqual(vals, [1, 2])


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

    def test_winning_update_signals_and_stashes_rebust_pids(self):
        """A win must (a) queue the win signal, (b) stash _signal_pids so the
        route can re-bust the tick checksum after the update lands -- the
        signal_send-time bust alone can be re-armed by an in-flight tick that
        read the winner pre-signal (game 133908: 16s wait for 2nd place)."""
        from models import BingoGameData, BingoTeam
        card = BingoCard(name="TestGoal", goal_type="int", target=3, square=0)
        filler = [BingoCard(name="Filler%s" % i, goal_type="int", target=99, square=i)
                  for i in range(1, 25)]
        p1 = Player(id="56.1", bingo_prog=[BingoCardProgress(square=i) for i in range(25)])
        bgd = BingoGameData(id="56")
        bgd.board = [card] + filler
        bgd.teams = [BingoTeam(captain=p1.key, teammates=[])]
        bgd.square_count = 1
        bgd.start_time = datetime(2026, 7, 20, 12, 0, 0)
        bgd.game = ndb.Key("Game", 56)
        bgd.get_players = lambda: [p1]
        self._stub_puts(p1, bgd)

        bgd.update_v2({"TestGoal": {"value": 5}}, 1, 56)

        self.assertEqual(bgd.teams[0].place, 1)
        self.assertEqual(len([e for e in bgd.event_log if e.event_type == "win"]), 1)
        self.assertEqual(len(p1.signals), 1)
        self.assertTrue(p1.signals[0].startswith("win:$Finished in 1st place"))
        self.assertEqual(bgd._signal_pids, [(56, 1)])


class TestChunkedHistory(NdbTestCase):
    """CHUNKED_LOGS: history lines append into fixed-size child entities while
    constant-size dedup state rides on the Player. The dedup decision must stay
    bit-identical to the legacy scan of `history[:-20]` -- that scan is what
    stops a client replaying old pickups from duplicating the game's history."""

    def _line(self, coords, code="EX", pid=1, id="100"):
        return HistoryLine(player=pid, pickup_code=code, pickup_id=id, coords=coords,
                           timestamp=datetime(2026, 7, 25, 12, 0, 0))

    def _chunked_append(self, p, chunks, hl):
        """Drive the append exactly as append_hl_chunked_txn does, minus the RPCs."""
        n = p.hist_chunk or 0
        while len(chunks) <= n:
            chunks.append(models.HistoryChunk())
        return Player.hl_chunk_append(p, chunks[n], hl)

    def _legacy_append(self, hls, hl):
        if any([h for h in hls[:-models.HIST_TAIL] if h.equals(hl)]):
            return False
        hls.append(hl)
        return True

    def test_chunks_fill_and_seal_at_size(self):
        p, chunks = Player(id="80.1"), []
        for i in range(models.HIST_CHUNK_SIZE * 2 + 5):
            self.assertTrue(self._chunked_append(p, chunks, self._line(1000 + i)))
        self.assertEqual(len(chunks), 3)
        self.assertEqual(len(chunks[0].lines), models.HIST_CHUNK_SIZE)
        self.assertEqual(len(chunks[1].lines), models.HIST_CHUNK_SIZE)
        self.assertEqual(len(chunks[2].lines), 5)
        self.assertEqual(p.hist_chunk, 2)

    def test_dedup_state_stays_constant_size(self):
        """The whole point: what rides on the hot Player entity must not grow
        with the game. hist_tail is capped; hist_seen is bounded by the number
        of distinct pickups, not by how many lines were logged."""
        p, chunks = Player(id="81.1"), []
        for i in range(300):
            self._chunked_append(p, chunks, self._line(1000 + (i % 40)))
        self.assertEqual(len(p.hist_tail), models.HIST_TAIL)
        self.assertLessEqual(len(p.hist_seen), 40)

    def test_dedup_matches_legacy_decision_for_decision(self):
        # a nasty sequence: fresh finds, immediate repeats (inside the tail
        # window, legal), and an alt+L-style replay of the whole run so far
        coords = [1000 + i for i in range(40)]
        seq = [self._line(c) for c in coords]
        seq += [self._line(coords[-1])]                      # immediate repeat
        seq += [self._line(c) for c in coords]               # full replay
        seq += [self._line(c) for c in coords[:5]]           # partial replay
        seq += [self._line(9999, code="SK", id="0")]         # something new

        p, chunks, legacy = Player(id="82.1"), [], []
        for hl in seq:
            self.assertEqual(self._chunked_append(p, chunks, hl),
                             self._legacy_append(legacy, hl),
                             "divergence at coords=%s" % hl.coords)
        stored = [hl for c in chunks for hl in c.lines]
        self.assertEqual([h.coords for h in stored], [h.coords for h in legacy])

    def test_replay_of_old_pickup_is_skipped(self):
        p, chunks = Player(id="83.1"), []
        first = self._line(1234)
        self.assertTrue(self._chunked_append(p, chunks, first))
        for i in range(models.HIST_TAIL + 5):  # push it out of the tail window
            self._chunked_append(p, chunks, self._line(2000 + i))
        self.assertFalse(self._chunked_append(p, chunks, self._line(1234)))

    def test_repeat_inside_tail_window_is_kept(self):
        # matches legacy: a duplicate whose original is still within the last 20
        # lines is appended (rollback re-collection shows up in history)
        p, chunks = Player(id="84.1"), []
        self._chunked_append(p, chunks, self._line(1234))
        self._chunked_append(p, chunks, self._line(1235))
        self.assertTrue(self._chunked_append(p, chunks, self._line(1234)))

    def test_distinct_pickups_at_same_coords_are_distinct(self):
        p, chunks = Player(id="85.1"), []
        self.assertTrue(self._chunked_append(p, chunks, self._line(1234, code="EX", id="100")))
        for i in range(models.HIST_TAIL + 2):
            self._chunked_append(p, chunks, self._line(3000 + i))
        self.assertTrue(self._chunked_append(p, chunks, self._line(1234, code="SK", id="0")))


class TestHistoryWriteDispatch(NdbTestCase):
    """Which of the three history layouts a pickup writes to is flag-driven:
    CHUNKED_LOGS > HIST_ON_PLAYER > legacy Game.hls."""

    def setUp(self):
        super(TestHistoryWriteDispatch, self).setUp()
        self._flags = (models.CHUNKED_LOGS, models.HIST_ON_PLAYER)
        self._chunked, self._on_player = Player.append_hl_chunked_txn, Player.append_hl_txn
        self.calls = []
        Player.append_hl_chunked_txn = staticmethod(
            lambda pkey, hl: self.calls.append(("chunked", hl.coords)) or True)
        Player.append_hl_txn = staticmethod(
            lambda pkey, hl: self.calls.append(("on_player", hl.coords)) or True)

    def tearDown(self):
        models.CHUNKED_LOGS, models.HIST_ON_PLAYER = self._flags
        Player.append_hl_chunked_txn, Player.append_hl_txn = self._chunked, self._on_player
        super(TestHistoryWriteDispatch, self).tearDown()

    def _game(self):
        p = Player(id="88.1", skills=0, events=0, teleporters=0, bonuses={}, hints={})
        p.put = lambda *a, **k: None
        g = Game(id="88", str_mode="Bingo")
        g.get_players = lambda: [p]
        g.player = lambda pid, create=True, delay_put=False: p
        g.hls = []
        return g

    def _find(self, g):
        g.found_pickup(1, Pickup.n("EX", "100"), 3000, False, False, "Glades")

    def test_chunked_wins_when_both_flags_set(self):
        models.CHUNKED_LOGS, models.HIST_ON_PLAYER = True, True
        g = self._game()
        self._find(g)
        self.assertEqual(self.calls, [("chunked", 3000)])
        self.assertEqual(g.hls, [])

    def test_falls_back_to_player_history(self):
        models.CHUNKED_LOGS, models.HIST_ON_PLAYER = False, True
        g = self._game()
        self._find(g)
        self.assertEqual(self.calls, [("on_player", 3000)])

    def test_falls_back_to_game_hls(self):
        models.CHUNKED_LOGS, models.HIST_ON_PLAYER = False, False
        g = self._game()
        g.append_hl = g.hls.append  # bypass the transactional write
        self._find(g)
        self.assertEqual(self.calls, [])
        self.assertEqual([hl.coords for hl in g.hls], [3000])


class TestEvlogArchive(NdbTestCase):
    """CHUNKED_LOGS: the bingo event log's overflow is archived into child
    entities instead of being dropped at the 400 cap. The entity keeps the feed
    tail -- get_json renders it on every update, so it must stay small."""

    class _RecordingChunk(object):
        made = []

        def __init__(self, key=None, events=None):
            self.key, self.events, self.put_count = key, events, 0
            TestEvlogArchive._RecordingChunk.made.append(self)

        def put(self):
            self.put_count += 1

        @staticmethod
        def key_for(bingo_key, gid, n):
            return ("chunk", gid, n)

    def setUp(self):
        super(TestEvlogArchive, self).setUp()
        self._chunk_cls = models.BingoEventChunk
        self._flag = models.CHUNKED_LOGS
        TestEvlogArchive._RecordingChunk.made = []
        models.BingoEventChunk = TestEvlogArchive._RecordingChunk
        models.CHUNKED_LOGS = True

    def tearDown(self):
        models.BingoEventChunk = self._chunk_cls
        models.CHUNKED_LOGS = self._flag
        super(TestEvlogArchive, self).tearDown()

    def _game(self, squares, markers=2):
        from models import BingoEvent, BingoGameData
        bgd = BingoGameData(id="60")
        bgd.event_log = ([BingoEvent(event_type="miscBingo Game 60 created!")] * markers +
                         [BingoEvent(event_type="square", square=i) for i in range(squares)])
        bgd.put = lambda *a, **k: None
        return bgd

    def test_under_threshold_is_a_noop(self):
        bgd = self._game(models.EVLOG_KEEP + models.EVLOG_ARCHIVE - 5)
        before = len(bgd.event_log)
        self.assertEqual(bgd.archive_evlog(60), 0)
        self.assertEqual(len(bgd.event_log), before)
        self.assertEqual(bgd.ev_chunk, 0)
        self.assertEqual(TestEvlogArchive._RecordingChunk.made, [])

    def test_overflow_archives_and_keeps_feed_tail(self):
        bgd = self._game(300)
        archived = bgd.archive_evlog(60)
        self.assertEqual(archived, 300 - models.EVLOG_KEEP)
        # the entity keeps exactly the feed tail plus the framing markers
        self.assertEqual(len(bgd.event_log), models.EVLOG_KEEP + 2)
        self.assertTrue(all(e.event_type.startswith("misc") for e in bgd.event_log[:2]))
        chunk = TestEvlogArchive._RecordingChunk.made[0]
        self.assertEqual(len(chunk.events), 300 - models.EVLOG_KEEP)
        self.assertEqual(chunk.put_count, 1)
        self.assertEqual(bgd.ev_chunk, 1)  # advanced, so the next archive can't clobber

    def test_nothing_is_lost_across_repeated_archives(self):
        from models import BingoEvent
        bgd = self._game(0, markers=0)
        seen = 0
        for batch in range(6):
            bgd.event_log += [BingoEvent(event_type="square", square=seen + i) for i in range(60)]
            seen += 60
            bgd.archive_evlog(60)
        archived = [e for c in TestEvlogArchive._RecordingChunk.made for e in c.events]
        self.assertEqual(len(archived) + len(bgd.event_log), seen)
        self.assertEqual([e.square for e in archived + list(bgd.event_log)], list(range(seen)))
        self.assertLessEqual(len(bgd.event_log), models.EVLOG_KEEP + models.EVLOG_ARCHIVE)

    def test_update_v2_archives_instead_of_pruning_when_flagged(self):
        bgd = self._game(600)
        bgd._update_inner = lambda *a, **k: None
        bgd.update_v2({}, 1, 60)
        self.assertEqual(len(bgd.event_log), models.EVLOG_KEEP + 2)
        self.assertTrue(TestEvlogArchive._RecordingChunk.made)


class TestVersionTracking(NdbTestCase):
    """The client sends its dll version on every tick (>= 4.1.10). Recording it
    is the capability-negotiation hook for the websocket migration."""

    def test_first_report_records_and_asks_for_a_put(self):
        p = Player(id="90.1")
        self.assertTrue(p.note_version("4.1.10", 90))
        self.assertEqual(p.dll_version, "4.1.10")

    def test_unchanged_version_is_free(self):
        p = Player(id="91.1", dll_version="4.1.10")
        self.assertFalse(p.note_version("4.1.10", 91))

    def test_missing_version_is_ignored(self):
        p = Player(id="92.1", dll_version="4.1.10")
        self.assertFalse(p.note_version(None, 92))
        self.assertFalse(p.note_version("", 92))
        self.assertEqual(p.dll_version, "4.1.10")

    def test_upgrade_is_recorded(self):
        p = Player(id="93.1", dll_version="4.1.9")
        self.assertTrue(p.note_version("4.1.10", 93))
        self.assertEqual(p.dll_version, "4.1.10")


if __name__ == "__main__":
    unittest.main()
