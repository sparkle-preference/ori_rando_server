"""Entrance shuffle logic: the shared door rules, the walk through known doors, and the tick's door bits."""
import os
import re
import shutil
import sys
import tempfile
import unittest

import netcode
from cache import Cache
from cli_gen import CLISeedParams
from models import Game, Player
from reachable import Map, full_state
from seedbuilder import generator
from seedbuilder.entrances import (DOORS, DOOR_NAMES, SHARD_TELEPORTERS, door_key, is_door_edge, keys_only_for_doors,
                                   known_edges, parse_entrances)
from seedbuilder.oriparse import get_areas
from test.ndb_base import NdbTestCase
from test.session_golden_test import FakeGame, make_player

STANDARD = ["casual-core", "casual-dboost", "standard-core", "standard-dboost", "standard-lure", "standard-abilities"]
KEYS = ("GinsoKey", "ForlornKey", "HoruKey")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def door(name):
    return next(d for d in DOORS if d[0] == name)


def en_rows(pairs):
    """Seed rows for one-way door lines, [(from door, to door)]."""
    rows = []
    for a, b in pairs:
        _, ax, ay = door(a)
        _, bx, by = door(b)
        rows.append((str(door_key(ax, ay)), "EN", "%s|%s" % (bx, by), None))
    return rows


def bit(name):
    return 1 << [d[0] for d in DOORS].index(name)


def reach(edges, state=None):
    return set(Map.get_reachable_areas(state or full_state(), STANDARD, need_reached_with=False, door_edges=edges))


class DoorTable(unittest.TestCase):
    def test_matches_the_plando_builder(self):
        with open(os.path.join(ROOT, "map", "src", "PlandoBuilder.js"), encoding="utf-8") as f:
            js = f.read()
        block = js[js.index("const DOORS = ["):js.index("]\n", js.index("const DOORS = ["))]
        rows = [(n, int(x), int(y)) for n, x, y in re.findall(r'\["(\w+)", (-?\d+), (-?\d+)\]', block)]
        self.assertEqual(rows, [tuple(d) for d in DOORS])

    def test_generator_shuffles_the_first_22(self):
        self.assertEqual(list(generator.doors_inner) + list(generator.doors_outer), DOORS[:22])

    def test_key_is_the_generators(self):
        for name, x, y in DOORS:
            self.assertEqual(door_key(x, y), generator.Door(name, x, y).get_key())


class KeyRule(unittest.TestCase):
    def test_a_key_stays_on_its_own_outer_door(self):
        path = [("casual",), "GinsoKey", "Bash"]
        self.assertEqual(keys_only_for_doors("OuterSwampUpperArea", "GinsoOuterDoor", path), path)

    def test_a_key_leaves_every_other_edge(self):
        self.assertEqual(keys_only_for_doors("TeleporterNetwork", "HoruTeleporter", [("casual",), "TPHoru", "HoruKey"]),
                         [("casual",), "TPHoru"])
        self.assertEqual(keys_only_for_doors("ForlornInnerDoor", "ForlornEntranceExp", [("casual",), "ForlornKey", "Bash"]),
                         [("casual",), "Bash"])

    def test_from_inside_the_key_leaves_even_its_own_door(self):
        self.assertEqual(keys_only_for_doors("ForlornInnerDoor", "ForlornOuterDoor", [("casual",), "ForlornKey"]),
                         [("casual",)])

    def test_the_entrance_map_keeps_keys_only_at_the_outer_doors(self):
        Map.build(entrance=True)
        gated = {(a.name, c.target) for a in Map.entrance_areas.values() for c in a.conns
                 for reqs in c.reqs.values() for r in reqs if any(k in r.cnt for k in KEYS)}
        self.assertEqual(gated, {("OuterSwampUpperArea", "GinsoOuterDoor"), ("OutsideForlorn", "ForlornOuterDoor"),
                                 ("HorufieldsHoruDoor", "HoruOuterDoor")})

    def test_the_entrance_map_has_no_door_wiring(self):
        Map.build(entrance=True)
        left = [(a.name, c.target) for a in Map.entrance_areas.values() for c in a.conns if is_door_edge(a.name, c.target)]
        self.assertEqual(left, [])
        self.assertTrue(any(is_door_edge(name, t) for name, home in get_areas()["homes"].items() for t in home["conns"]))


class KnownEdges(unittest.TestCase):
    def test_untouched_doors_add_nothing(self):
        rows = en_rows([("L1OuterDoor", "GinsoInnerDoor"), ("GinsoInnerDoor", "L1OuterDoor")])
        self.assertEqual(known_edges(parse_entrances(rows), 0), {})

    def test_a_touched_door_adds_only_its_own_direction(self):
        rows = en_rows([("L1OuterDoor", "GinsoInnerDoor"), ("GinsoInnerDoor", "L1OuterDoor")])
        self.assertEqual(known_edges(parse_entrances(rows), bit("L1OuterDoor")), {"L1OuterDoor": {"GinsoInnerDoor"}})

    def test_all_known_is_the_whole_map(self):
        rows = en_rows([("L1OuterDoor", "GinsoInnerDoor"), ("GinsoInnerDoor", "L2OuterDoor")])
        self.assertEqual(known_edges(parse_entrances(rows)),
                         {"L1OuterDoor": {"GinsoInnerDoor"}, "GinsoInnerDoor": {"L2OuterDoor"}})

    def test_a_raw_coordinate_target_adds_nothing(self):
        _, x, y = door("L1OuterDoor")
        rows = [(str(door_key(x, y)), "EN", "-200|300", None)]
        self.assertEqual(known_edges(parse_entrances(rows)), {})

    def test_r1_outer_is_known_unused(self):
        rows = en_rows([("R1OuterDoor", "R1InnerDoor"), ("R1InnerDoor", "R1OuterDoor")])
        self.assertEqual(known_edges(parse_entrances(rows), 0), {"R1OuterDoor": {"R1InnerDoor"}})

    def test_other_seed_lines_are_ignored(self):
        self.assertEqual(parse_entrances([("-280256", "SK", "0", "Glades"), ("5, ", "EN", "bad", None)]), {})


class EntranceWalk(unittest.TestCase):
    """A generated Entrance seed, walked with full items."""

    @classmethod
    def setUpClass(cls):
        outdir = tempfile.mkdtemp(prefix="entrancetest_")
        old_argv = sys.argv
        sys.argv = ["cli_gen", "--output-dir", outdir, "--preset", "standard", "--entrance", "--seed", "entrancewalk"]
        try:
            CLISeedParams().from_cli()
            name = next(n for n in os.listdir(outdir) if n.endswith(".bfr"))
            with open(os.path.join(outdir, name)) as f:
                lines = f.read().splitlines()
        finally:
            sys.argv = old_argv
            shutil.rmtree(outdir, ignore_errors=True)
        # params rows carry an EN target as one "x|y" id; the raw seed line splits it in two
        rows = [l.split("|") for l in lines[1:] if l.count("|") >= 3]
        cls.entrances = parse_entrances([(r[0], r[1], "|".join(r[2:4])) for r in rows])

    def test_the_seed_names_every_door(self):
        self.assertEqual(len(self.entrances), 24)
        self.assertEqual(set(self.entrances), {door_key(x, y) for _, x, y in DOORS})

    def test_knowing_every_door_reaches_every_location(self):
        locs = set(get_areas()["locs"])
        vanilla = set(Map.get_reachable_areas(full_state(), STANDARD, need_reached_with=False))
        known = reach(known_edges(self.entrances))
        self.assertEqual((vanilla & locs) - known, set())

    def test_doors_join_the_walk_as_they_are_used(self):
        none = reach(known_edges(self.entrances, 0))
        every = reach(known_edges(self.entrances))
        self.assertLess(len(none), len(every))
        # every door's room is behind some door, so none of the Horu side rooms are in reach yet
        self.assertFalse({"L1", "L2", "L3", "L4"} & none)
        for name, x, y in DOORS:
            target = next(n for n, tx, ty in DOORS if (tx, ty) == self.entrances[door_key(x, y)])
            if name not in none or target in none:
                continue
            after = reach(known_edges(self.entrances, bit(name)))
            self.assertTrue(target in after, "using %s should reach %s" % (name, target))
            break
        else:
            self.fail("no reachable door leads anywhere new")


class ShardTeleporters(unittest.TestCase):
    TPS = set(SHARD_TELEPORTERS)

    def walk(self, modes, **shards):
        state = full_state()
        for shard, n in shards.items():
            state.has[shard] = n
        return set(Map.get_reachable_areas(state, modes, need_reached_with=False, door_edges={})) & self.TPS

    def test_a_shards_walk_wants_two_of_the_dungeons_shards(self):
        self.assertEqual(self.walk(STANDARD + ["SHARDS"]), set())
        self.assertEqual(self.walk(STANDARD + ["SHARDS"], RB17=1, RB19=2, RB21=5), {"ForlornTeleporter", "HoruTeleporter"})

    def test_any_other_key_mode_takes_the_teleporter_alone(self):
        self.assertEqual(self.walk(STANDARD), self.TPS)

    def test_the_table_is_the_generators(self):
        with open(os.path.join(ROOT, "seedbuilder", "generator.py")) as f:
            found = re.findall(r'Connection\("TeleporterNetwork", "(\w+)", self, p\)\s+connection.add_requirements\(\[([^\]]+)\]', f.read())
        rb = {"WaterVeinShard": "RB17", "GumonSealShard": "RB19", "SunstoneShard": "RB21"}
        want = {}
        for target, reqs in found:
            names = [r.strip().strip('"') for r in reqs.split(",")]
            shards = [n for n in names if n in rb]
            self.assertEqual(len(shards), 2, (target, names))
            want[target] = rb[shards[0]]
        self.assertEqual({t: shard for t, (_, shard) in SHARD_TELEPORTERS.items()}, want)

class TickDoorBits(NdbTestCase):
    def setUp(self):
        super().setUp()
        self._with_id = Game.__dict__["with_id"]
        self.addCleanup(setattr, Game, "with_id", self._with_id)
        self._txn = Player.__dict__["tick_update_txn"]
        self.addCleanup(setattr, Player, "tick_update_txn", self._txn)
        self._clear = Cache.clear_reach
        self.addCleanup(setattr, Cache, "clear_reach", self._clear)

    def _rig(self, gid, stored):
        player = make_player(gid, 1, seen_bflds=8 * [0], have_bflds=8 * [0], signals=[], entrance_doors=stored)
        game = FakeGame(players={1: player})
        Game.with_id = staticmethod(lambda _gid: game)
        writes, clears = [], []

        def txn(pkey, vers, seen, have, doors=None):
            writes.append(doors)
            if doors is not None:
                player.entrance_doors = doors
            return player
        Player.tick_update_txn = staticmethod(txn)
        Cache.clear_reach = lambda g, p: clears.append((g, p))
        Cache.clear_seen_checksum((gid, 1))
        return writes, clears

    def _payload(self, ent=None):
        payload = {"seen_%s" % i: "0" for i in range(8)}
        payload.update({"have_%s" % i: "0" for i in range(8)})
        if ent is not None:
            payload["ent"] = str(ent)
        return payload

    def test_a_new_door_is_stored_and_drops_the_tracker_reach(self):
        writes, clears = self._rig(9201, 0)
        netcode.tick(9201, 1, self._payload(0))
        netcode.tick(9201, 1, self._payload(5))
        self.assertEqual(writes, [5])
        self.assertEqual(clears, [(9201, 1)])

    def test_a_door_busts_the_fast_path(self):
        writes, _ = self._rig(9202, 0)
        netcode.tick(9202, 1, self._payload(0))
        netcode.tick(9202, 1, self._payload(0))
        netcode.tick(9202, 1, self._payload(2))
        self.assertEqual(writes, [2])

    def test_no_field_leaves_the_bits_alone(self):
        writes, clears = self._rig(9203, 7)
        netcode.tick(9203, 1, self._payload())
        self.assertEqual((writes, clears), ([], []))


if __name__ == "__main__":
    unittest.main()
