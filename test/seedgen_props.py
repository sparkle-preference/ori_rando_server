"""Seed generation properties: rolls are well formed, beatable, conserved, counted right and served back as rolled."""
from test.strategies.base import DEEP, deep_only, examples

import logging
import unittest
from collections import Counter

from hypothesis import Phase, event, given, note, settings, strategies as st

from reachable import PlayerState
from seedbuilder import enemyopts, enemyroll
from seedbuilder.enemyroll import LASER, RANGED, RANGED_EXTRA, same_family, table
from seedbuilder.generator import SeedGenerator
from test.strategies import seedgen as S

# outside deep the noted argv and seed are the repro, so shrinking is skipped
PHASES = tuple(Phase) if DEEP else (Phase.explicit, Phase.reuse, Phase.generate)


class EnemyRollProps(unittest.TestCase):

    @settings(max_examples=examples(150), phases=PHASES)
    @given(S.seed_strings, st.integers(1, 4), S.enemy_opts())
    def test_every_roll_obeys_its_placement(self, seed, world, opts):
        note("enemyroll.roll(%r, %r, %r)" % (seed, world, opts))
        t = table()
        rolls = enemyroll.roll(seed, world, opts)
        self.assertEqual(rolls, enemyroll.roll(seed, world, opts))
        self.assertEqual(len(rolls), len(t["placements"]))
        self.assertEqual(enemyroll.rolls_of(enemyroll.meta_line(rolls)), rolls)
        o = dict(enemyopts.DEFAULTS)
        o.update(enemyopts.normalize(opts) or {})
        pool, keep = set(o["pool"]), set(o["keep"])
        kinds = {k["name"]: k for k in t["kinds"]}
        ranged = Counter()
        for p, r in zip(t["placements"], rolls):
            kind = p["kind"] if r is None else t["variants"][r]["kind"]
            if kind in RANGED:
                ranged[p["scene"]] += 1
            if r is None:
                continue
            v = t["variants"][r]
            where = (p["guid"], kind)
            self.assertFalse(p["pinned"] or p["kind"] in keep or p["kind"] is None, where)
            self.assertFalse(o["arena"] == "kind" and p["arena"], where)
            self.assertTrue(kind == p["kind"] or kind in pool, where)
            self.assertFalse(p["wet"] and "drowns" in kinds[kind]["flags"], where)
            self.assertFalse(o["flyingfish"] == "off" and kind == "Fish" and p["spot"] != "water", where)
            self.assertFalse(o["pools"] == "off" and p["spot"] == "water" and kind != "Fish", where)
            role = p["role"] or ""
            if not (o["logic"] == "on" or role.endswith("!")):
                continue
            role = role.rstrip("!")
            if role == "keep":
                self.assertTrue(same_family(kind, p["kind"]), where)
                if p["prefab"] != LASER:
                    self.assertNotEqual(v["prefab"], LASER, where)
            elif role == "bashable":
                self.assertIn("bash", kinds[kind]["flags"], where)
            elif role.startswith("prefab:"):
                self.assertEqual(v["prefab"], role[len("prefab:"):], where)
            elif role.startswith("kinds:"):
                self.assertIn(kind, role[len("kinds:"):].split("+"), where)
        if o["shootercap"] == "on":
            vanilla = Counter(p["scene"] for p in t["placements"] if p["kind"] in RANGED)
            for scene, n in ranged.items():
                self.assertLessEqual(n, vanilla[scene] + RANGED_EXTRA, scene)


class NoLeakProps(unittest.TestCase):

    @settings(max_examples=examples(5), phases=PHASES)
    @given(S.solo_settings(), S.seed_strings, st.one_of(S.solo_settings(), S.mw_settings()), S.seed_strings)
    def test_a_roll_ignores_what_the_process_rolled_before(self, a, seed_a, b, seed_b):
        a, b = a + ["--seed", seed_a], b + ["--seed", seed_b]
        note("A: " + S.repro(a))
        note("B: " + S.repro(b))
        try:
            first = S.cli(a, attempts=S.ATTEMPTS).files
        except S.RollTooLong:
            event("a roll ran out of placement attempts")
            return
        try:
            S.cli(b, attempts=S.ATTEMPTS)
        except S.RollTooLong:
            event("a roll ran out of placement attempts")
        self.assertEqual(S.cli(a).files, first)


class SoloProps(unittest.TestCase):

    @settings(max_examples=examples(16), phases=PHASES)
    @given(S.solo_settings(), S.seed_strings)
    def test_a_solo_roll_holds_every_location_once_and_reaches_them_all(self, argv, seed):
        run = S.roll(argv, seed)
        if run is None:
            return
        lines = run.seed()
        self.assertEqual(S.structure_problems(lines, entrance="--entrance" in argv), [])
        self.assertEqual(S.header_problems(run, 1, 1), [])
        if not S.walkable(argv):
            return
        placements = S.Seed(lines).placements
        modes, spawn = S.modes_for(run.params), S.spawn_zone(S.Seed(lines).spawn()[1])
        missed = S.unreachable(placements, modes, spawn)
        if missed:
            event("the reach walk needed the keystone cushion")
            missed = S.unreachable(placements, modes, spawn, cushion=S.CUSHION)
        self.assertEqual(missed, [], "locations reachable.py never gets to")

    @settings(max_examples=examples(6), phases=PHASES)
    @given(S.solo_settings(random_parts=False), S.seed_strings, S.seed_strings)
    def test_the_seed_string_moves_items_but_never_changes_the_pool(self, argv, seed_a, seed_b):
        a, b = S.roll(argv, seed_a), S.roll(argv, seed_b)
        if a is None or b is None:
            return
        self.assertEqual(S.pool(S.Seed(a.seed()).placements), S.pool(S.Seed(b.seed()).placements))


class HeldProps(unittest.TestCase):

    @settings(max_examples=examples(8), phases=PHASES)
    @given(S.held_settings(), S.seed_strings)
    def test_buried_and_early_items_keep_their_timing_and_mint_nothing(self, held, seed):
        argv, fass, (base, depth, items) = held
        control = S.roll(argv, seed)
        if control is None:
            return
        records = []
        run = S.roll(argv + ["--fass", fass], control.params.seed, spies=S.records_spy(records))
        if run is None:
            event("the held roll failed")
            return
        lines = run.seed()
        self.assertEqual(S.structure_problems(lines), [])
        self.assertEqual(S.totals(S.Seed(lines).placements), S.totals(S.Seed(control.seed()).placements))
        records = S.kept_records(records)
        cap = min(depth, run.gen.total_locs())
        for code in items:
            mine = [r for r in records if r[0] == S.HELD[code] + "|1"]
            self.assertTrue(mine, "%s was never assigned" % code)
            if base == S.BURIED:
                last = max if code in ("HC1", "EC1", "KS1") else min
                self.assertGreaterEqual(last(r[1] for r in mine), cap, code)
            elif not [w for w in run.gen.gen_warnings if S.HELD[code] in w]:
                self.assertLess(min(r[3] for r in mine), cap, code)


class MultiworldProps(unittest.TestCase):

    @settings(max_examples=examples(8), phases=PHASES)
    @given(S.mw_settings(), S.seed_strings)
    def test_every_multiworld_roll_is_consistent_and_jointly_beatable(self, argv, seed):
        run = S.roll(argv, seed)
        if run is None:
            return
        worlds = run.worlds()
        players = int(S.flag_value(argv, "--players"))
        self.assertEqual(sorted(worlds), list(range(1, players + 1)))
        self.assertEqual(S.mw_problems(worlds), [])
        for p in worlds:
            self.assertEqual(S.header_problems(run, p, players), [], "world %s" % p)
        split = S.share_disagreements(run)
        if S.misc_keysanity_split(argv):
            split = {s for s in split if s[:2] not in S.KEYSANITY_KEYS}
        self.assertEqual(split, set(), "the generator and the netcode disagree on what is shared")
        if not S.walkable(argv) or S.spawn_shards_pile_up(argv):
            return
        modes = {p: S.modes_for(run.params, p) for p in worlds}
        spawns = {p: S.spawn_zone(S.Seed(worlds[p]).spawn()[1]) for p in worlds}
        shared = run.params.sync.shared
        missed = S.joint_unreachable(worlds, modes, spawns, shared)
        if missed:
            event("the joint walk needed the keystone cushion")
            missed = S.joint_unreachable(worlds, modes, spawns, shared, cushion=S.CUSHION)
        self.assertEqual(missed, {}, "locations no world's walk gets to")


class StorageProps(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import google.auth.credentials
        from google.cloud import ndb
        cls.client = ndb.Client(project="unit-test", credentials=google.auth.credentials.AnonymousCredentials())

    @deep_only
    @settings(max_examples=examples(8), phases=PHASES)
    @given(S.web_json())
    def test_stored_placements_serve_back_the_generated_lines(self, j):
        from enums import MultiplayerGameType
        from seedbuilder.seedparams import SeedGenParams
        note("SeedGenParams.from_json(%r)" % j)
        raw = []
        inner = SeedGenerator.setSeedAndPlaceItems

        def keep(sg, params, **kw):
            out = inner(sg, params, **kw)
            raw.append(out)
            return out
        old_disable = logging.root.manager.disable
        logging.disable(logging.CRITICAL)
        with self.client.context():
            params = SeedGenParams.from_json(j, store=False)
            SeedGenerator.setSeedAndPlaceItems = keep
            try:
                ok = params.generate(store=False)
            finally:
                SeedGenerator.setSeedAndPlaceItems = inner
                logging.disable(old_disable)
            if not ok:
                event("generation failed")
                return
            multi = params.sync.mode == MultiplayerGameType.MULTIWORLD
            suffix = params.players > 1 and (multi or params.sync.mode == MultiplayerGameType.SHARED)
            for p in range(1, params.players + 1):
                rolled = raw[-1][p - 1 if multi else 0][0].split("\n")
                served = params.get_seed(p, include_sync=False).split("\n")
                self.assertEqual(served[0], rolled[0] + ("/%s" % p if suffix else ""), "world %s" % p)
                self.assertEqual(Counter(S.body(served)), Counter(S.body(rolled)), "world %s" % p)
                self.assertEqual(meta_lines(served), meta_lines(rolled), "world %s" % p)


def meta_lines(lines):
    return sorted(l for l in lines if l.startswith("//") and not l.startswith(("// SEED_FORMAT", "// PLAYERS")))


def keymode_problems(worlds, shared, argv):
    """What a world is handed that its keymode doesn't call for; a shared spawn draw repeats once per drawing world."""
    out = []
    keysanity, open_world = "--keysanity" in argv, "--open-world" in argv
    shards = S.flag_value(argv, "--keymode") == "Shards"
    spawned, placed = S.received(worlds, shared, True), S.received(worlds, shared, False)
    for p in worlds:
        got = spawned[p] + placed[p]
        for key, shard in (("0", "17"), ("2", "19"), ("4", "21")):
            item, other, n = (("RB", shard), ("EV", key), 5) if shards else (("EV", key), ("RB", shard), 1)
            if got[other] or got[item] < n:
                out.append("w%s holds %s x%s and %s x%s" % (p, item, got[item], other, got[other]))
            if placed[p][item] != (0 if spawned[p][item] else n):
                out.append("w%s finds %s x%s, its spawn holds %s" % (p, item, placed[p][item], spawned[p][item]))
        want = {("KS", "1"): 0 if keysanity else 40 - 2 * open_world}
        if keysanity and not S.misc_keysanity_split(argv):
            for name, copies in Counter(n for names in S.keysanity_map.values() for n in names).items():
                code = SeedGenerator.keysanityOutput[name]
                want[(code[:2], code[2:])] = 0 if open_world and name == "Glades Pool Keystone" else copies
        out += ["w%s holds %s x%s, wants %s" % (p, k, got[k], n) for k, n in sorted(want.items()) if got[k] != n]
    return out


LIMITKEY_DUNGEONS = {"0": {5480952, 5320328}, "2": {-7320236}, "4": set()}


def key_spot_problems(worlds, argv):
    """Free keys ride only spawns; a LimitKeys key sits on a limitkey spot outside its dungeon (every dungeon, in MW)."""
    km = S.flag_value(argv, "--keymode")
    solo = len(worlds) == 1
    homes = {}
    out = []
    pool = set(SeedGenerator().limitKeysPool)
    for p, lines in worlds.items():
        for loc, (code, id, zone) in S.Seed(lines).placements.items():
            for pc, pid in S.parts(code, id) if code != "MW" else [tuple(id.split(",")[2:4])]:
                if pc != "EV" or pid not in LIMITKEY_DUNGEONS or loc == S.SPAWN_LOC:
                    continue
                if km == "Free":
                    out.append("w%s free key EV%s at %s" % (p, pid, loc))
                elif km == "LimitKeys":
                    locked = LIMITKEY_DUNGEONS[pid] if solo else set().union(*LIMITKEY_DUNGEONS.values())
                    if loc not in pool or loc in locked:
                        out.append("w%s EV%s at %s" % (p, pid, loc))
                    homes[pid] = loc
    if solo and homes.get("0") in LIMITKEY_DUNGEONS["2"] and homes.get("2") in LIMITKEY_DUNGEONS["0"]:
        out.append("Ginso and Forlorn lock each other's keys in")
    return out


class CountProps(unittest.TestCase):

    @settings(max_examples=examples(8), phases=PHASES)
    @given(S.cloned_settings(), S.seed_strings)
    def test_cloned_coop_worlds_are_byte_identical(self, cloned, seed):
        argv, copies = cloned
        run = S.roll(argv, seed)
        if run is None:
            return
        names = run.seed_names()
        self.assertEqual(names, ["randomizer_%s.bfr" % p for p in range(1, copies + 1)])
        self.assertEqual({run.files[n] for n in names}, {run.files[names[0]]})
        self.assertEqual({run.files["spoiler_%s.txt" % p] for p in range(1, copies + 1)}, {run.files["spoiler_1.txt"]})
        self.assertNotIn("|MW|", run.files[names[0]])

    @settings(max_examples=examples(6), phases=PHASES)
    @given(S.warp_settings(), S.seed_strings)
    def test_warp_count_hands_every_world_exactly_that_many_warps(self, warps, seed):
        argv, count = warps
        run = S.roll(argv, seed)
        if run is None:
            return
        for p, lines in run.worlds().items():
            seed_ = S.Seed(lines)
            own = sum(1 for code, id, zone in seed_.placements.values() if code == "TW")
            sent = sum(1 for f, code, id, zone in seed_.manifest.values() if code == "TW")
            self.assertEqual(own + sent, count, "world %s" % p)

    @settings(max_examples=examples(8), phases=PHASES)
    @given(S.tour_settings(), S.seed_strings)
    def test_world_tour_puts_one_relic_in_each_of_its_zones(self, tour, seed):
        argv, count = tour
        run = S.roll(argv, seed)
        if run is None:
            return
        zones = S.loc_zones()
        for p, lines in run.worlds().items():
            seed_ = S.Seed(lines)
            found = [(loc, id, zone) for loc, (code, id, zone) in seed_.placements.items() if code == "WT"]
            self.assertEqual(len(found), count, "world %s" % p)
            self.assertEqual(len({zone for _, _, zone in found}), count, "world %s relic zones" % p)
            for loc, id, zone in found:
                self.assertEqual(zones.get(loc), zone, "world %s relic at %s" % (p, loc))
                self.assertIn(id, ["#%s#\\n%s" % pair for pair in S.relics[zone]], "world %s" % p)
            crossed = [1 for f, code, id, zone in seed_.manifest.values() if code == "WT"]
            crossed += [1 for code, id, zone in seed_.placements.values() if code == "MW" and ",WT," in id]
            self.assertEqual(crossed, [], "relics never cross worlds")

    @settings(max_examples=examples(8), phases=PHASES)
    @given(S.keymode_settings(), S.seed_strings)
    def test_each_keymode_hands_out_its_keys_and_keystones(self, argv, seed):
        run = S.roll(argv, seed)
        if run is None:
            return
        worlds = run.worlds()
        self.assertEqual(keymode_problems(worlds, run.params.sync.shared, argv), [])
        self.assertEqual(key_spot_problems(worlds, argv), [])


class OpenBugRepros(unittest.TestCase):

    @unittest.expectedFailure
    def test_the_tracker_reach_engine_finds_every_location_of_a_beatable_seed(self):
        # a generator change can un-strand these seeds; check them before reading a pass as a fix
        missed = {}
        for argv in (["--preset", "casual", "--start", "Sorrow", "--seed", "s12"], ["--preset", "expert", "--seed", "b"]):
            run = S.cli(argv)
            seed = S.Seed(run.seed())
            spawn = S.spawn_zone(seed.spawn()[1])
            missed[S.repro(argv)] = S.unreachable(seed.placements, S.modes_for(run.params), spawn)
        self.assertEqual({k: v for k, v in missed.items() if v}, {})

    @unittest.expectedFailure
    def test_a_forced_spot_is_filled_even_when_its_area_opens_last(self):
        # a generator change can un-strand this seed; check it before reading a pass as a fix
        run = S.cli(["--preset", "casual", "--players", "2", "--share-mode", "multiworld", "--shared-items", "",
                     "--keymode", "LimitKeys", "--entrance", "--start", "Grove", "--anti-bk-bias", "0.5",
                     "--seed", "688"])
        self.assertEqual((bool(run.worlds()), S.stranded_forced_spots(run)), (True, {}))

    @unittest.expectedFailure
    def test_misc_sharing_agrees_with_the_netcode_on_keysanity_keys(self):
        run = S.cli(["--preset", "standard", "--players", "2", "--share-mode", "multiworld",
                     "--shared-items", "misc", "--keysanity", "--seed", "misc"])
        self.assertEqual((bool(run.worlds()), S.share_disagreements(run)), (True, set()))

    @unittest.expectedFailure
    def test_double_skills_rolls_from_a_start_that_hands_out_skills(self):
        self.assertTrue(S.cli(["--preset", "standard", "--easy", "--start", "Sorrow", "--seed", "e0"]).worlds())

    @unittest.expectedFailure
    def test_the_tracker_reach_engine_grants_a_dungeon_key_past_five_shards(self):
        self.assertEqual(PlayerState([("RB", "17", 6, False)]).has["GinsoKey"], 1)

    @unittest.expectedFailure
    def test_closed_dungeons_warps_instead_of_tps_places_every_warp(self):
        run = S.cli(["--preset", "standard", "--closed-dungeons", "--warps-instead-of-tps", "8", "--seed", "a"])
        warps = sum(1 for code, id, zone in S.Seed(run.seed()).placements.values() if code == "TW")
        self.assertEqual(warps, len(run.gen.warps))

    @unittest.expectedFailure
    def test_warps_instead_of_tps_rolls_with_a_warp_count_above_the_teleporters(self):
        run = S.cli(["--preset", "standard", "--warps-instead-of-tps", "1", "--warp-count", "9", "--seed", "a"])
        self.assertTrue(run.worlds())


if __name__ == "__main__":
    unittest.main()
