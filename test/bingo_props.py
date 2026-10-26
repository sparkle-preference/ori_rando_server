"""Bingo properties: dealt boards, discovery, the update machine, marks and the reroll seed bump."""
from test.strategies.base import DEEP, examples

import json
import os
import random
import re
import subprocess
import sys
import unittest
from collections import Counter

from hypothesis import assume, example, given, note, settings, strategies as st

from bingo import (DEFEAT_NEEDS, DEFEAT_ZONES, NEEDS, NEEDS_BUDGET, SPAWN_AREAS, SPAWN_TELEPORTERS, ZONE_NEEDS,
                   BingoGenerator, BoolGoal, DefeatGoal, GoalGroup, IntGoal, JourneyGoal, journey_pairs,
                   with_implied)
from cache import MemcachedCache, _with_marks
from models import BingoCard, BingoGameData, _pid, lines_by_index, pick_discovery_squares
from test.bingo_marks_test import _FakeMemcache
from test.js_bridge import call
from test.ndb_base import NdbTestCase
from test.strategies.bingo import (RerollRoutes, UpdateGame, board_digests, board_options, board_seeds,
                                   hashseed_cases, multiworld_params, quiet_logs, reroll_cases, roll, snapshot,
                                   solo_params, stub_player_txns, update_scenarios)
from web.bingo import RR_SUFFIX, bump_board_seed, mw_bingo_worlds, owner_world

SERVER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COL_C = set(range(2, 23, 5))
ROW_3 = set(range(10, 15))
EDGES = {0, 1, 2, 3, 4, 5, 9, 10, 14, 15, 19, 20, 21, 22, 23, 24}
CENTERS = {6, 7, 8, 11, 12, 13, 16, 17, 18}


def pool_for(opts):
    return BingoGenerator.goal_pool(random.Random(0), **{k: v for k, v in opts.items() if k != "discovery"})


def early_range_outruns_the_roll(group, opts):
    return bool(opts["discovery"] and group.early_max and group.early_max > group.range_func.max)


def triangle_peaks_past_the_top(group):
    """roll_func's triangle peaks at 3/5 of (low + high)."""
    return (group.range_func.min + group.range_func.max) * 3 / 5 > group.range_func.max


def assert_board(tc, cards, opts):
    """Caps, needs budget and soundness, journeys, spawn squares, meta placement and discovery layout."""
    pool = pool_for(opts)
    tops = {}
    for g in pool:
        tops.setdefault(g.name, []).append(g)
    subs = {(g.name, s.name): s for g in pool for s in getattr(g, "goals", [])}
    hard, easy = opts["difficulty"] == "hard", opts["difficulty"] == "easy"

    tc.assertEqual([c.square for c in cards], list(range(25)))
    names = Counter(c.name for c in cards)
    for name, n in names.items():
        tc.assertIn(name, tops)
        tc.assertLessEqual(n, 2 if name == "Defeat" else max(g.max_repeats for g in tops[name]), name)
    tc.assertLessEqual(sum(n for name, n in names.items() if name.startswith("PickupsIn")), 2)
    need_counts = Counter(n for c in cards for n in c.needs)
    for need, most in NEEDS_BUDGET[opts["difficulty"]].items():
        tc.assertLessEqual(need_counts[need], most, need)

    seen_subgoals = {}
    for c in cards:
        tc.assertTrue(c.disp_name, c.name)
        tc.assertTrue(c.needs <= set(NEEDS), c.needs)
        tc.assertEqual(c.needs, with_implied(c.needs))
        if c.goal_type == "multi":
            tc.assertIn(c.goal_method, ("and", "or", "count"), c.name)
            if c.goal_method != "count":
                tc.assertTrue(c.subgoals, c.name)
            keys = [s["name"] for s in c.subgoals]
            tc.assertEqual(len(keys), len(set(keys)), (c.name, keys))
            seen = seen_subgoals.setdefault(c.name, set())
            tc.assertFalse(seen & set(keys), (c.name, keys, seen))
            seen |= set(keys)
        group = tops[c.name][0]
        # a need a card is not charged for must be avoidable on it
        if isinstance(group, GoalGroup) and c.name != "Activate Squares":
            tc.assertTrue(with_implied(group.needs) <= c.needs, c.name)
            if c.goal_method == "count":
                for need in set(NEEDS) - c.needs:
                    free = [s for s in group.goals if need not in with_implied(s.needs)]
                    tc.assertGreaterEqual(len(free), c.target, (c.name, need, c.target))
            else:
                for s in c.subgoals:
                    tc.assertTrue(with_implied(subs[(c.name, s["name"])].needs) <= c.needs, (c.name, s["name"]))
        elif isinstance(group, IntGoal):
            scalar = 250 if c.name == "GainExperience" else 1
            tc.assertEqual(c.target % scalar, 0)
            t = c.target // scalar
            tc.assertGreaterEqual(t, group.range_func.min, c.name)
            if not (early_range_outruns_the_roll(group, opts) or triangle_peaks_past_the_top(group)):
                tc.assertLessEqual(t, group.range_func.max, c.name)
            owed = with_implied(set(group.needs) | {n for n, cap in group.caps.items() if c.target > cap})
            tc.assertTrue(owed <= c.needs, (c.name, c.target, owed, c.needs))
            if c.early:
                tc.assertTrue(group.early_max and c.target <= group.early_max, (c.name, c.target, group.early_max))
        elif isinstance(group, BoolGoal):
            tc.assertTrue(with_implied(group.needs) <= c.needs, c.name)
            tc.assertEqual(bool(c.early), "early" in group.tags, c.name)
        elif isinstance(group, JourneyGoal):
            frm, _, to = c.subgoals[0]["name"].partition("-")
            tc.assertIn((frm, to), journey_pairs(group.disp_names, easy, hard))
            owed = with_implied(set(group.well_needs.get(frm, ())) | set(group.well_needs.get(to, ())))
            tc.assertTrue(owed <= c.needs, (frm, to, owed, c.needs))
        elif isinstance(group, DefeatGoal):
            for s in c.subgoals:
                kind, _, zone = s["name"].partition("-")
                spec = DEFEAT_ZONES[kind]
                tc.assertIn(zone, spec["default"] + (spec.get("hard", []) if hard else []))
                owed = with_implied(([ZONE_NEEDS[zone]] if zone in ZONE_NEEDS else []) + DEFEAT_NEEDS.get(s["name"], []))
                tc.assertTrue(owed <= c.needs, (s["name"], owed, c.needs))

    journeys = [c.subgoals[0]["name"].partition("-") for c in cards if c.name == "Journey"]
    origins = [j[0] for j in journeys]
    tc.assertEqual(len(origins), len(set(origins)))
    pairs = {(j[0], j[2]) for j in journeys}
    tc.assertFalse({(b, a) for a, b in pairs} & pairs)
    if opts["enemy_rando"]:
        tc.assertNotIn("Defeat", names)
    if opts["keysanity"]:
        tc.assertNotIn("UnspentKeystones", names)

    well, area = SPAWN_TELEPORTERS.get(opts["spawn"]), SPAWN_AREAS.get(opts["spawn"])
    for c in cards:
        if len(c.subgoals) == 1 or c.goal_method == "or":
            if c.name == "ActivateTeleporter":
                tc.assertNotIn(well, [s["name"] for s in c.subgoals])
            if c.name == "EnterArea":
                tc.assertNotIn(area, [s["name"] for s in c.subgoals])

    metas = [c for c in cards if c.meta]
    if not opts["meta"]:
        tc.assertFalse(metas)
    tc.assertLessEqual(len(metas), 5)
    for c in cards:
        if c.name == "VertSym":
            tc.assertIn(c.square, COL_C)
        if c.name == "HorizSym":
            tc.assertIn(c.square, ROW_3)
        if c.name in ("VertSym", "HorizSym"):
            tc.assertFalse(opts["lockout"])
    targets = [int(s["name"]) for c in cards if c.name == "Activate Squares" for s in c.subgoals]
    tc.assertEqual(len(targets), len(set(targets)), targets)
    for t in targets:
        tc.assertFalse(cards[t].meta, t)

    if opts["discovery"] and not opts["meta"]:
        late_centers = [c.square for c in cards if not c.early and c.square in CENTERS]
        early_edges = [c.square for c in cards if c.early and c.square in EDGES]
        tc.assertFalse(late_centers and early_edges, (late_centers, early_edges))


class BoardProps(unittest.TestCase):
    def setUp(self):
        quiet_logs(self)

    @settings(max_examples=examples(300))
    @given(board_seeds, board_options(discovery=st.integers(1, 25)))
    @example(0, dict(rando=False, difficulty="easy", open_world=False, discovery=9, meta=False, lockout=False,
                     keysanity=False, spawn="Blackroot", enemy_rando=False))
    def test_every_board_finishes(self, seed, opts):
        self.assertEqual(len(roll(seed, opts)), 25)

    @settings(max_examples=examples(200))
    @given(board_seeds, board_options())
    def test_every_board_keeps_its_caps_budgets_and_layout(self, seed, opts):
        assert_board(self, roll(seed, opts), opts)

    @settings(max_examples=examples(60))
    @given(board_seeds, board_options(), board_seeds, board_options())
    def test_a_seed_deals_the_same_board_whatever_was_dealt_before(self, seed, opts, other_seed, other_opts):
        first = snapshot(roll(seed, opts))
        roll(other_seed, other_opts)
        self.assertEqual(snapshot(roll(seed, opts)), first)

    def target_and_top(self, seed, opts, name):
        top = next(g.range_func.max for g in pool_for(opts) if g.name == name)
        return [c.target for c in roll(seed, opts) if c.name == name], top

    @unittest.expectedFailure
    def test_a_discovery_reroll_keeps_an_early_card_inside_its_range(self):
        (plants,), top = self.target_and_top(395, {"difficulty": "easy", "discovery": 2}, "BreakPlants")
        self.assertLessEqual(plants, top)

    @unittest.expectedFailure
    def test_a_rolled_target_stays_inside_its_range(self):
        (points,), top = self.target_and_top(117, {"difficulty": "easy"}, "SpendPoints")
        self.assertLessEqual(points, top)


HASHSEED_CASES = examples(60)
CHILD = ("import json, logging, sys; logging.disable(logging.CRITICAL); "
         "from test.strategies.bingo import board_digests; print(json.dumps(board_digests(int(sys.argv[1]))))")
children = {}


def setUpModule():
    """Starts the hash seed children first, so their interpreter startup overlaps the other tests."""
    # children skip google-auth's metadata-server probe, a multi-second stall at import
    env = dict(os.environ, NO_GCE_CHECK="true")
    for hs in [s for s in ("0", "1", "12345") if s != os.environ.get("PYTHONHASHSEED")][:3 if DEEP else 2]:
        children[hs] = subprocess.Popen([sys.executable, "-c", CHILD, str(HASHSEED_CASES)], cwd=SERVER, text=True,
                                        env=dict(env, PYTHONHASHSEED=hs), stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE)


def tearDownModule():
    for child in children.values():
        if child.returncode is None:
            child.kill()
            child.communicate()


class HashSeedProps(unittest.TestCase):
    def setUp(self):
        quiet_logs(self)

    def test_boards_do_not_depend_on_the_hash_seed(self):
        mine = board_digests(HASHSEED_CASES)
        for hs, child in children.items():
            out, err = child.communicate(timeout=600)
            self.assertEqual(child.returncode, 0, err[-3000:])
            theirs = json.loads(out.strip().splitlines()[-1])
            diff = [i for i, (a, b) in enumerate(zip(theirs, mine)) if a != b]
            self.assertEqual((len(theirs), diff), (len(mine), []), "PYTHONHASHSEED=%s deals other boards for %s"
                             % (hs, [hashseed_cases(HASHSEED_CASES)[i] for i in diff[:3]]))


def a_count_a_bare_read_loses(count):
    return count != 2


def check_picks(tc, board, count, picks):
    """count distinct picks on the board, early squares first."""
    early = {c.square for c in board if c.early}
    tc.assertEqual(len(picks), count, picks)
    tc.assertTrue(set(picks) <= set(range(25)), picks)
    tc.assertTrue(set(picks) <= early if len(early) >= count else early <= set(picks), (picks, early))
    tc.assertEqual(len(set(picks)), count, picks)


board_cells = st.lists(st.tuples(st.booleans(), st.sampled_from(["Goal"] * 6 + ["VertSym", "HorizSym"])),
                       min_size=25, max_size=25)


class DiscoveryProps(unittest.TestCase):
    def setUp(self):
        quiet_logs(self)

    @settings(max_examples=examples(500))
    @given(board_cells, st.text(max_size=8), st.integers(1, 25))
    def test_discovery_reveals_the_count_asked_for(self, cells, seed, count):
        board = [BingoCard(name=name, square=i, early=early) for i, (early, name) in enumerate(cells)]
        picks = pick_discovery_squares(board, seed, count)
        check_picks(self, board, count, picks)
        self.assertEqual(pick_discovery_squares(board, seed, count), picks)

    @settings(max_examples=examples(200))
    @given(board_seeds, board_options(discovery=st.integers(1, 25)))
    def test_a_dealt_board_reveals_its_discovery_count(self, seed, opts):
        cards = roll(seed, opts)
        check_picks(self, cards, opts["discovery"], pick_discovery_squares(cards, str(seed), opts["discovery"]))

    @settings(max_examples=examples(100))
    @given(board_seeds, st.integers(1, 25), st.booleans())
    def test_reading_the_discovery_squares_changes_nothing(self, seed, count, drawn):
        bingo = BingoGameData(board=roll(seed, {"discovery": count}), seed=str(seed))
        if drawn:
            squares = bingo.discovery_squares(count)
        else:
            bingo.discovery = count
        read = bingo.discovery_squares()
        if drawn:
            self.assertEqual(read, squares)
        if not a_count_a_bare_read_loses(count):
            self.assertEqual((bingo.discovery, len(read)), (count, count))
        self.assertEqual(bingo.discovery_squares(), read)

    def test_a_board_short_of_early_squares_still_reveals_distinct_ones(self):
        board = [BingoCard(name="G%d" % i, square=i, early=i == 0) for i in range(25)]
        self.assertEqual(len(set(pick_discovery_squares(board, "25", 2))), 2)

    @unittest.expectedFailure
    def test_a_bare_read_keeps_the_discovery_count(self):
        bingo = BingoGameData(board=[BingoCard(name="G%d" % i, square=i, early=True) for i in range(25)], seed="s")
        bingo.discovery_squares(5)
        bingo.discovery_squares()
        self.assertEqual(bingo.discovery, 5)


def per_world_reroll_with_discovery(bingo, disc):
    return bool(bingo.boards) and disc > 0


class RerollProps(RerollRoutes, NdbTestCase):
    def setUp(self):
        super().setUp()
        quiet_logs(self)

    @settings(max_examples=examples(100))
    @given(reroll_cases)
    def test_a_reroll_redraws_the_discovery_it_was_asked_for(self, case):
        shape, seed, disc = case["shape"], case["seed"], case["disc"]
        params = {"vanilla": lambda: None, "solo": solo_params,
                  "multiworld": lambda: multiworld_params(case["worlds"])}[shape]()
        boards = self.routes.bingo_boards_for(params, seed, False) if shape == "multiworld" else ()
        bingo = self.seat(params, seed, boards)
        assume(not per_world_reroll_with_discovery(bingo, disc))
        kept = {wb.world: (wb.difficulty, wb.discovery, wb.meta) for wb in bingo.boards}
        query = {"difficulty": case["difficulty"], "discCount": disc, "lockout": int(case["lockout"]),
                 "world": case["world"]}
        if case["meta"]:
            query["meta"] = 1
        self.assertEqual(self.reroll(**query).status_code, 200)
        if not bingo.boards:
            self.assertEqual((bingo.lockout, bingo.meta), (case["lockout"], case["meta"] and not case["lockout"]))
            self.assertFalse(bingo.lockout and any(c.meta for c in bingo.board))
            self.assertEqual((len(bingo.board), bingo.discovery), (25, disc or None))
            check_picks(self, bingo.board, disc, bingo.disc_squares)
            return
        worlds = mw_bingo_worlds(params)
        self.assertEqual((bingo.board, [wb.world for wb in bingo.boards]), ([], worlds))
        owner = owner_world(worlds, case["world"])
        for wb in bingo.boards:
            want = (case["difficulty"], disc, case["meta"]) if wb.world == owner else kept[wb.world]
            self.assertEqual((wb.difficulty, wb.discovery, wb.meta), want, wb.world)
            check_picks(self, wb.board, wb.discovery, wb.disc_squares)

    @unittest.expectedFailure
    def test_a_per_world_board_rerolls_with_discovery(self):
        params = multiworld_params([{"variations": ["Bingo"]}, {"variations": ["Bingo"]}])
        self.seat(params, "s", self.routes.bingo_boards_for(params, "s", False))
        self.assertEqual(self.reroll(discCount=3, world=1).status_code, 200)


ROW_FILLED_AROUND_A_LOSS = {"roster": [[1]], "lockout": False, "goal": ("bingos", 1), "metas": {}, "reports": [
    (0, True, frozenset({24})), (0, True, frozenset()), (0, True, frozenset({20, 21, 22, 23}))]}


def full_lines(held, team):
    return {name for name, line in lines_by_index.items() if all(team in held[sq] for sq in line)}


class UpdateProps(NdbTestCase):
    def setUp(self):
        super().setUp()
        quiet_logs(self)
        stub_player_txns(self)

    @settings(max_examples=examples(150))
    @given(update_scenarios)
    @example(ROW_FILLED_AROUND_A_LOSS)
    def test_the_board_follows_its_reports(self, sc):
        game = UpdateGame(sc)
        history = {p: [] for p in game.pids}
        places, blackouts = {}, {}
        held = [set() for _ in range(25)]
        for step, (who, fresh, squares) in enumerate(sc["reports"]):
            pid = game.pids[who % len(game.pids)]
            cap = game.team_of[pid]
            done = squares if fresh or not history[pid] else history[pid][-1] ^ squares
            before = held
            game.report(pid, done)
            history[pid].append(done)
            note((step, pid, sorted(done)))
            held = [set(c.completed_by) for c in game.bgd.board]
            owners = [c.owner for c in game.bgd.board]
            self.check_squares(game, sc, history, pid, cap, before, held, owners)
            self.check_teams(game, sc, cap, held, owners, places, blackouts)
        self.check_feed(game)
        self.check_payload(game)

    def check_squares(self, game, sc, history, pid, cap, before, held, owners):
        """Holdings move only for the reporter's team, and only as its reports allow."""
        lockout = sc["lockout"]
        firsts = [c.completed_by[0] if c.completed_by else 0 for c in game.bgd.board]
        for sq in range(25):
            now, was = held[sq], before[sq]
            self.assertTrue(now <= set(game.members) and now ^ was <= {cap}, (sq, was, now))
            self.assertEqual(owners[sq], firsts[sq] if lockout else 0, sq)
            if sq in game.metas:
                continue
            for team, members in game.members.items():
                if any(history[m] and sq in history[m][-1] for m in members):
                    self.assertIn(team, now, (sq, team))
            if cap in now - was:
                self.assertTrue(any(history[m] and sq in history[m][-1] for m in game.members[cap]), sq)
            if cap in was - now:
                # a loss lands on its player's second down report after an up one
                self.assertEqual([sq in r for r in history[pid][-3:]], [True, False, False], sq)
        for sq, (method, targets) in game.metas.items():
            for team in [cap] if lockout else game.members:
                holds = [(owners[t] == team) if lockout else (team in held[t]) for t in targets]
                want = any(holds) if method == "or" else all(holds)
                self.assertEqual(team in held[sq], want, (sq, team, method, targets))

    def check_teams(self, game, sc, cap, held, owners, places, blackouts):
        """Scores, lines and places follow from what each team holds."""
        lockout = sc["lockout"]
        kind, target = sc["goal"]
        teams = {_pid(t.captain): t for t in game.bgd.teams}
        for team in [cap] if lockout else game.members:
            mine = [sq for sq in range(25) if (owners[sq] == team if lockout else team in held[sq])]
            self.assertEqual(teams[team].score, len(mine), team)
        for team, t in teams.items():
            self.assertEqual(len(t.bingos), len(set(t.bingos)), t.bingos)
            self.assertEqual(set(t.bingos), full_lines(held, team) if kind == "bingos" else set(), team)
        reporter = teams[cap]
        if (reporter.score if kind == "squares" else len(reporter.bingos)) >= target:
            places.setdefault(cap, len(places) + 1)
        if reporter.score == 25:
            blackouts.setdefault(cap, len(blackouts) + 1)
        for team, t in teams.items():
            self.assertEqual((t.place, t.blackout_place), (places.get(team), blackouts.get(team)), team)

    def check_feed(self, game):
        """Replaying the event feed lands on the board and teams it describes."""
        bgd = game.bgd
        held, owner, lines, wins = {}, {}, {}, Counter()
        for ev in bgd.event_log:
            team = _pid(ev.player)
            if ev.event_type == "square":
                self.assertNotEqual(held.get((team, ev.square), False), not ev.loss, (team, ev.square))
                held[(team, ev.square)] = not ev.loss
            elif ev.event_type == "owner":
                owner[ev.square] = 0 if ev.loss else team
            elif ev.event_type == "bingo" and ev.loss:
                lines.setdefault(team, []).remove(ev.bingo)
            elif ev.event_type == "bingo":
                lines.setdefault(team, []).append(ev.bingo)
            elif ev.event_type == "win":
                wins[team] += 1
        for sq, card in enumerate(bgd.board):
            self.assertEqual(sorted(card.completed_by), sorted(t for (t, s), h in held.items() if s == sq and h), sq)
            self.assertEqual(card.owner, owner.get(sq, 0), sq)
        for t in bgd.teams:
            self.assertEqual(lines.get(_pid(t.captain), []), t.bingos)
        self.assertEqual(wins, Counter(_pid(t.captain) for t in bgd.teams if t.place))

    def check_payload(self, game):
        """The json a poll gets shows the board and teams as they stand."""
        res, bgd = game.payload(), game.bgd
        self.assertEqual([(c["completed_by"], c["owner"]) for c in res["cards"]],
                         [(c.completed_by, c.owner) for c in bgd.board])
        self.assertEqual({cap: (t["score"], t["bingos"], t.get("place")) for cap, t in res["teams"].items()},
                         {_pid(t.captain): (t.score, t.bingos, t.place) for t in bgd.teams})

    def test_a_win_needs_its_lines_held_at_once(self):
        game = UpdateGame({"roster": [[1]], "lockout": False, "goal": ("bingos", 2), "metas": {}})
        col_b, row_1 = {1, 6, 11, 16, 21}, {0, 1, 2, 3, 4}
        for done in (col_b, col_b - {6}, (col_b - {6}) | row_1):
            game.report(1, done)
        self.assertEqual(game.bgd.teams[0].bingos, ["Row 1"])
        self.assertIsNone(game.bgd.teams[0].place)


MARKS_GID = 91003
masks = st.integers(0, (1 << 25) - 1)
mark_writes = st.tuples(st.integers(1, 4), masks)


def replay_marks(writes):
    out = {}
    for pid, bits in writes:
        if bits:
            out[pid] = bits
        else:
            out.pop(pid, None)
    return out


class MarksProps(unittest.TestCase):
    @settings(max_examples=examples(100))
    @given(st.dictionaries(st.integers(1, 4), masks.filter(bool)), mark_writes)
    def test_a_mark_write_touches_only_its_player(self, marks, write):
        got = _with_marks(marks, *write)
        self.assertEqual({k: v for k, v in got.items() if k != write[0]},
                         {k: v for k, v in marks.items() if k != write[0]})
        self.assertEqual(got.get(write[0]), write[1] or None)

    @settings(max_examples=examples(300))
    @given(st.lists(st.tuples(mark_writes, st.lists(mark_writes, max_size=6)), max_size=12))
    def test_racing_mark_writers_lose_nothing(self, steps):
        key = "%s.marks" % MARKS_GID
        cache = MemcachedCache.__new__(MemcachedCache)
        store = cache.memcache = _FakeMemcache()
        applied = []
        for (pid, bits), rivals in steps:
            pending = list(rivals)

            def rival():
                # a rival's whole read-modify-write lands between our gets and our cas
                w = pending.pop(0)
                store.store[key], store.version = _with_marks(store.store.get(key), *w), store.version + 1
                applied.append(w)
                store.rival = rival if pending else None
            store.rival = rival if pending else None
            ok = cache.set_marks(MARKS_GID, pid, bits)
            store.rival = None
            self.assertTrue(ok or rivals, "a write with no rival gave up")
            if ok:
                applied.append((pid, bits))
        self.assertEqual(store.store.get(key, {}), replay_marks(applied))


def eats_a_trailing_newline(seed):
    return re.search(r"RR\d+\n\Z", seed) is not None


def has_unicode_rr_digits(seed):
    match = RR_SUFFIX.search(seed)
    return bool(match) and not match.group(1).isascii()


def past_js_integers(seed):
    match = RR_SUFFIX.search(seed)
    return bool(match) and int(match.group(1)) + 1 > 2 ** 53


bump_seeds = st.one_of(st.text(max_size=8), st.builds(
    lambda head, digits, tail: head + "RR" + digits + tail, st.text(max_size=4),
    st.one_of(st.text("0123456789", min_size=1, max_size=20),
              st.text("0123456789\N{ARABIC-INDIC DIGIT THREE}\N{DEVANAGARI DIGIT ONE}", min_size=1, max_size=3)),
    st.sampled_from(["", "", "", "\n", "x", "RR"])))


class SeedBumpProps(unittest.TestCase):
    def bumps(self, seed):
        return call("Bingo.js", "bumpBoardSeed", seed), bump_board_seed(seed)

    @settings(max_examples=examples(300))
    @given(bump_seeds)
    def test_the_modal_shows_the_seed_a_reroll_bumps_to(self, seed):
        assume(not eats_a_trailing_newline(seed))
        assume(not has_unicode_rr_digits(seed))
        assume(not past_js_integers(seed))
        js, py = self.bumps(seed)
        self.assertEqual(js, py)

    @unittest.expectedFailure
    def test_the_modal_bumps_a_seed_ending_in_a_newline_like_a_reroll(self):
        js, py = self.bumps("aRR1\n")
        self.assertEqual(js, py)

    @unittest.expectedFailure
    def test_the_modal_bumps_unicode_digits_like_a_reroll(self):
        js, py = self.bumps("aRR\N{ARABIC-INDIC DIGIT THREE}")
        self.assertEqual(js, py)

    @unittest.expectedFailure
    def test_the_modal_bumps_numbers_past_2_53_like_a_reroll(self):
        js, py = self.bumps("RR" + "9" * 22)
        self.assertEqual(js, py)


if __name__ == "__main__":
    unittest.main()
