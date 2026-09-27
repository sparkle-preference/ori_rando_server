"""EV 6/7, RB 260-267 and RB 5: they build and name like any pickup, never share,
never fan out across worlds and never reach the item tracker, and roll in pools
and preplacements like any other unshared bonus item.

Run from the repo root:  python3 -m unittest test.plando_pickups_test -v
"""
import os
import shutil
import sys
import tempfile
import unittest
from collections import Counter

import main
from cache import Cache
from cli_gen import CLISeedParams
from enums import MultiplayerGameType, ShareType
from models import Game, Player
from pickups import Pickup
from seedbuilder.generator import SeedGenerator
from test.ndb_base import NdbTestCase
from test.seedgen_test import check_mw_invariants, generate_ap, parse_ap_seed, parse_seed
from web import tracker

NEW_PICKUPS = [
    ("EV", "6", "Darkness Lifted"), ("EV", "7", "Forlorn Energy Restored"),
    ("RB", "260", "Remove Water Vein"), ("RB", "261", "Remove Clean Water"),
    ("RB", "262", "Remove Gumon Seal"), ("RB", "263", "Remove Wind Restored"),
    ("RB", "264", "Remove Sunstone"), ("RB", "265", "Remove Warmth Returned"),
    ("RB", "266", "Remove Darkness Lifted"), ("RB", "267", "Remove Forlorn Energy Restored"),
    ("RB", "5", "Save Game"),
]
NEW_KEYS = {(code, pid) for code, pid, _ in NEW_PICKUPS}
EVERY_SHARE = [s for s in ShareType if s != ShareType.NOT_SHARED]


class NewPickupBuildTests(unittest.TestCase):
    def test_each_builds_under_its_name(self):
        for code, pid, name in NEW_PICKUPS:
            p = Pickup.n(code, pid)
            self.assertIsNotNone(p, pid)
            self.assertEqual(p.name, name)
            self.assertEqual(Pickup.name(code, pid), name)

    def test_none_is_shareable(self):
        for code, pid, _ in NEW_PICKUPS:
            p = Pickup.n(code, pid)
            self.assertEqual(p.share_type, ShareType.NOT_SHARED, pid)
            self.assertFalse(p.is_shared(EVERY_SHARE), pid)

    def test_each_removal_names_its_event(self):
        for ev in range(8):
            self.assertEqual(Pickup.n("RB", str(260 + ev)).name, "Remove " + Pickup.n("EV", str(ev)).name)

    def test_the_story_events_are_unchanged(self):
        for ev, name in enumerate(["Water Vein", "Clean Water", "Gumon Seal", "Wind Restored",
                                   "Sunstone", "Warmth Returned"]):
            p = Pickup.n("EV", str(ev))
            self.assertEqual((p.name, p.bit, p.share_type), (name, 1 << ev, ShareType.EVENT))

    def test_the_new_events_take_the_next_bits(self):
        self.assertEqual((Pickup.n("EV", "6").bit, Pickup.n("EV", "7").bit), (64, 128))
        self.assertIsNone(Pickup.n("EV", "8"))

    def test_268_is_not_an_upgrade(self):
        self.assertIsNone(Pickup.n("RB", "268"))


class NewPickupSharingTests(NdbTestCase):
    def setUp(self):
        super(NewPickupSharingTests, self).setUp()
        self._saved = {n: getattr(Player, n) for n in ("append_hl_chunked_txn", "transaction_pickup_batch")}
        self._mark_history = Game.mark_history_txn
        Game.mark_history_txn = staticmethod(lambda key: None)

    def tearDown(self):
        for name, fn in self._saved.items():
            setattr(Player, name, fn)
        Game.mark_history_txn = self._mark_history
        super(NewPickupSharingTests, self).tearDown()

    def game(self, mode):
        players = {pid: Player(id="93.%s" % pid, skills=0, events=0, teleporters=0,
                               bonuses={}, hints={}) for pid in (1, 2)}
        for p in players.values():
            p.put = lambda *a, **k: None
        g = Game(id="93", str_mode=mode.value, str_shared=[s.value for s in EVERY_SHARE])
        g.get_players = lambda: list(players.values())
        g.player = lambda pid, create=True, delay_put=False: players[pid]
        g.hist, g.grants = [], []
        Player.append_hl_chunked_txn = staticmethod(lambda pkey, hl: g.hist.append(hl) or True)
        Player.transaction_pickup_batch = staticmethod(lambda pkeys, grants: g.grants.append(grants))
        return g, players

    def test_multiworld_never_fans_them_out(self):
        g, _ = self.game(MultiplayerGameType.MULTIWORLD)
        for code, pid, _ in NEW_PICKUPS:
            self.assertEqual(g.mw_shareable(Pickup.n(code, pid)), [], pid)

    def test_a_shared_game_records_them_and_grants_nothing(self):
        g, players = self.game(MultiplayerGameType.SHARED)
        for code, pid, _ in NEW_PICKUPS:
            self.assertEqual(g.found_pickup(1, Pickup.n(code, pid), 999, False, False, "Glades"), 406, pid)
        self.assertEqual(g.grants, [])
        self.assertEqual(len(g.hist), len(NEW_PICKUPS))
        self.assertEqual([p.events for p in players.values()], [0, 0])


class _TrackerKey(object):
    def id(self):
        return 93093


class _TrackerGame(object):
    mode = MultiplayerGameType.SIMUSOLO
    is_race = False
    key = _TrackerKey()

    def relics_for(self, player):
        return []

    def visible_players(self):
        return []

    def get_inventories(self, players, include_unshared_prog=False, use_have=False):
        return {(1,): {}, "unshared": {1: {("EV", 0): 1, ("EV", 6): 1, ("EV", 7): 1}}}


class NewPickupTrackerTests(unittest.TestCase):
    def tearDown(self):
        Cache.clear_items(_TrackerKey().id())

    def test_the_tracker_shows_only_the_story_events(self):
        data, _ = tracker._get_item_tracker_items([], _TrackerGame(), 1)
        self.assertEqual(data["events"], ["Water Vein"])


POOL = {"%s|%s" % key: [1] for key in NEW_KEYS}
BASE_ARGS = ["--preset", "standard", "--open-world", "--force-trees", "--balanced"]


def roll(args, players, pool=POOL):
    """cli_gen with the new pickups added to every world's pool -> {player: seed lines}."""
    out = tempfile.mkdtemp(prefix="seedgentest_newpickups_")
    orig = SeedGenerator.setSeedAndPlaceItems
    def patched(sg, params, **kwargs):
        params.item_pool = dict(params.item_pool)
        params.item_pool.update(pool)
        return orig(sg, params, **kwargs)
    old_argv = sys.argv
    sys.argv = ["cli_gen", "--output-dir", out] + BASE_ARGS + args
    SeedGenerator.setSeedAndPlaceItems = patched
    try:
        CLISeedParams().from_cli()
        seeds = {}
        for p in range(1, players + 1):
            with open(os.path.join(out, "randomizer_%s.bfr" % p if players > 1 else "randomizer0.bfr")) as f:
                seeds[p] = f.read().splitlines()
        return seeds
    finally:
        SeedGenerator.setSeedAndPlaceItems = orig
        sys.argv = old_argv
        shutil.rmtree(out, ignore_errors=True)


def owned(seeds, owner):
    """The new pickups owner holds: plain lines in its own seed plus its manifest."""
    placements, manifest = parse_seed(seeds[owner])
    held = Counter((c, i) for (c, i, z) in placements.values() if (c, i) in NEW_KEYS)
    held.update((c, i) for (f, c, i, z) in manifest.values() if (c, i) in NEW_KEYS)
    return held


class NewPickupSeedgenTests(unittest.TestCase):
    ONE_EACH = Counter({key: 1 for key in NEW_KEYS})

    def test_solo_pool_and_preplacements(self):
        seeds = roll(["--seed", "newpickups1", "--fass", "919772:EV6|-280256:RB5|5280264:RB263"], 1)
        placements, _ = parse_seed(seeds[1])
        self.assertEqual([placements[loc][:2] for loc in (919772, -280256, 5280264)],
                         [("EV", "6"), ("RB", "5"), ("RB", "263")])
        # a preplacement takes its pool copy
        self.assertEqual(owned(seeds, 1), self.ONE_EACH)

    def test_cloned_coop_gives_every_world_its_own(self):
        seeds = roll(["--seed", "newpickups2", "--players", "2", "--share-mode", "shared", "--cloned",
                      "--shared-items", "skills,teleporters,worldevents,upgrades,misc"], 2)
        self.assertEqual(seeds[1], seeds[2])
        self.assertEqual(owned(seeds, 1), self.ONE_EACH)

    def test_multiworld_keeps_one_per_world_and_ships_the_rest(self):
        seeds = roll(["--seed", "newpickups3", "--players", "3", "--share-mode", "multiworld",
                      "--shared-items", "skills,teleporters,worldevents,upgrades",
                      "--fass", "919772:EV7|2.-280256:RB266@3"], 3)
        check_mw_invariants(self, seeds)
        for p in seeds:
            self.assertEqual(owned(seeds, p), self.ONE_EACH, "world %s" % p)
        placements, _ = parse_seed(seeds[2])
        self.assertEqual(placements[-280256][0], "MW")
        self.assertTrue(placements[-280256][1].startswith("3,"))

    def test_archipelago_leaves_them_on_the_native_fabric(self):
        out = tempfile.mkdtemp(prefix="seedgentest_newpickups_ap_")
        self.addCleanup(shutil.rmtree, out, ignore_errors=True)
        orig = SeedGenerator.setSeedAndPlaceItems
        def patched(sg, params, **kwargs):
            params.item_pool = dict(params.item_pool)
            params.item_pool.update({"EV|6": [3], "EV|7": [3], "RB|5": [3]})
            return orig(sg, params, **kwargs)
        SeedGenerator.setSeedAndPlaceItems = patched
        try:
            seeds, _ = generate_ap(out, 2, "skills,teleporters,events,upgrades", seed="newpickupsap")
        finally:
            SeedGenerator.setSeedAndPlaceItems = orig
        found = Counter()
        for p, lines in seeds.items():
            plain, _, _, native_manifest, ap_manifest = parse_ap_seed(lines, 2)
            self.assertEqual([e for e in ap_manifest.values() if (e[1], e[2]) in NEW_KEYS], [])
            found.update((c, i) for (c, i, z) in plain.values() if (c, i) in NEW_KEYS)
            found.update((e[1], e[2]) for e in native_manifest.values() if (e[1], e[2]) in NEW_KEYS)
        self.assertEqual(found, Counter({("EV", "6"): 6, ("EV", "7"): 6, ("RB", "5"): 6}))


if __name__ == "__main__":
    unittest.main()
