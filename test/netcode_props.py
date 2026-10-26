"""Netcode and multiworld state: the grant ledger, tick cache interleavings, slot bitfields, tick and find parsing."""
from test.strategies.base import DEEP, examples

import contextlib
import unittest
from collections import Counter, defaultdict
from unittest import mock

from google.auth.credentials import AnonymousCredentials
from google.cloud import ndb
from hypothesis import given, note, settings, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, initialize, invariant, precondition, rule

import models
import netcode
import util
import ws
from cache import Cache
from enums import ShareType
from models import Game, Player, stacks
from pickups import Pickup
from test.strategies import netcode as H

WORLD = st.integers(1, 3)
INDEX = st.integers(0, 9)
FOUND_TOKEN = "7"
# None thrice: most requests go through
FAILURES = st.sampled_from([None, None, None, (0, False), (0, True), (1, False), (1, True)])


def grant_committed_then_failed(flaky):
    """A grant txn that commits and then raises."""
    return flaky.fired and flaky.calls[-1][1]


class MultiworldGrants(RuleBasedStateMachine):
    """Clients find, resend, tick, touch wells, reconnect, confirm and complete; worlds hold what the ledger owes."""

    def __init__(self):
        super().__init__()
        self.gid, self.k = H.fresh_gid(), None

    @initialize(layout=H.layouts())
    def roll(self, layout):
        worlds, shared, rows = layout

        def store():
            params = H.make_game(self.gid, worlds, shared, H.placements_of(rows))
            return {w: H.seed_lines(params, w) for w in range(1, worlds + 1)}
        self.lines = H.request(store)
        note("game %s, shared %s, lines %s" % (self.gid, shared, self.lines))
        self.k, self.types = worlds, {ShareType(s) for s in shared}
        self.picked, self.queue, self.delivered = defaultdict(list), defaultdict(list), defaultdict(set)
        self.claimed, self.released, self.unbusted = set(), set(), set()
        self.owed, self.maybe_owed = defaultdict(set), defaultdict(set)
        self.bits, self.events, self.granted, self.items = Counter(), Counter(), defaultdict(set), {}

    # --- the ledger ---
    def _world(self, w):
        return (w - 1) % self.k + 1

    def _kind(self, p):
        if p.code == "MW":
            return "slot"
        if p.code == "TW" or (p.code == "EV" and p.id == 5) or p.share_type not in self.types:
            return "own"
        return "shared"

    def _children(self, w, c):
        code, id = self.lines[w][c]
        pickup = Pickup.n(code, id)
        return [(self._kind(p), p) for p in (pickup.children if code == "MU" else [pickup])]

    def _shared_copies(self, w, c):
        """(key, item) per shared child; the key tells two copies of one item at a location apart."""
        copies, seen = [], Counter()
        for kind, p in self._children(w, c):
            if kind == "shared":
                where = (w, c, p.code, str(p.id))
                seen[where] += 1
                copies.append((where + (seen[where],), p))
        return copies

    def _grant(self, p, key, busts=True):
        if p.code in ("SK", "TP", "EV"):
            self.bits[p.code] |= p.bit
        else:
            self.items[str(p.id)] = p
            self.events[str(p.id)] += 1
            self.granted[str(p.id)].add(key)
        if busts:
            self.unbusted.clear()

    def _committed(self, flaky):
        """The grants an injected failure let through, applied as facts."""
        seen = Counter()
        for n, (grants, committed) in enumerate(flaky.calls):
            for pickup, _, coords, finder in grants:
                where = (int(finder), int(coords), pickup.code, str(pickup.id))
                seen[where] += 1
                if committed:
                    self._grant(pickup, where + (seen[where],), busts=n + 1 < len(flaky.calls))
        if grant_committed_then_failed(flaky):
            self.unbusted = set(range(1, self.k + 1))

    def _found(self, w, c):
        for kind, p in self._children(w, c):
            if kind == "slot":
                self.owed[p.owner].add(p.slot)
        copies = self._shared_copies(w, c)
        if copies and (w, c) not in self.claimed:
            for key, p in copies:
                self._grant(p, key)
            self.claimed.add((w, c))
        self.delivered[w].add(c)

    def _maybe_marked(self, w, locations):
        for c in locations:
            for kind, p in self._children(w, c):
                if kind == "slot":
                    self.maybe_owed[p.owner].add(p.slot)

    def _released(self, w):
        for c in sorted(self.lines[w]):
            for kind, p in self._children(w, c):
                if kind == "slot":
                    self.owed[p.owner].add(p.slot)
            copies = self._shared_copies(w, c)
            if copies and (w, c) not in self.claimed:
                for key, p in copies:
                    self._grant(p, key)
                self.claimed.add((w, c))
        self.released.add(w)

    def _held_range(self, id):
        """A stacker holds one per location granted, to its cap; a failed grant's retry may add one."""
        p = self.items[id]
        if not stacks(p):
            return 1, 1
        cap = p.max or float("inf")
        return min(cap, len(self.granted[id])), min(cap, self.events[id])

    # --- clients ---
    def _send(self, w, c, via_ws):
        code, id = self.lines[w][c]
        if via_ws:
            frame = "found:%s|zone=%s|%s|%s|%s" % (FOUND_TOKEN, H.ZONE, c, code, id)
            reply = H.request(ws.handle_frame, self.gid, w, frame)
            assert reply == ("foundack:%s|200" % FOUND_TOKEN, False), reply
        else:
            reply = H.request(netcode.found_pickup, self.gid, w, str(c), code, id, {"zone": H.ZONE})
            assert reply[0] == 200, reply

    def _pick_up(self, w, count, i=0):
        """The client sets each pickup's seen bit at once and queues its find."""
        for _ in range(count):
            left = [c for c in sorted(self.lines[w]) if c not in self.picked[w]]
            if left:
                c = left[i % len(left)]
                self.picked[w].append(c)
                self.queue[w].append(c)

    @rule(w=WORLD, picks=st.integers(0, 2))
    def tick(self, w, picks):
        w = self._world(w)
        self._pick_up(w, picks)
        status, body = H.request(netcode.tick, self.gid, w, H.tick_payload(self.picked[w]))
        assert status == 200, (status, body)
        if w in self.unbusted:
            return
        want = H.request(H.fresh_render, self.gid, w)
        assert body == want, "stale tick body\n got %r\nwant %r" % (body, want)

    @rule(w=WORLD, j=INDEX, via_ws=st.booleans(), failure=FAILURES)
    def deliver(self, w, j, via_ws, failure):
        w = self._world(w)
        if not self.queue[w]:
            self._pick_up(w, 1, j)
        if not self.queue[w]:
            return
        c = self.queue[w][j % len(self.queue[w])]
        if failure is None:
            self._send(w, c, via_ws)
        else:
            with H.FlakyGrants(*failure) as flaky:
                try:
                    self._send(w, c, via_ws)
                    acked = True
                except H.InjectedFailure:
                    acked = False
            assert acked != flaky.fired, "a failed grant was acked, so its client never resends it"
            if not acked:
                # the find stays queued for a resend, and its claim went back
                self._committed(flaky)
                self._maybe_marked(w, [c])
                return
        self.queue[w].remove(c)
        self._found(w, c)

    @precondition(lambda self: self.k and any(self.delivered.values()))
    @rule(w=WORLD, j=INDEX, via_ws=st.booleans())
    def resend(self, w, j, via_ws):
        worlds = [w for w in range(1, self.k + 1) if self.delivered[w]]
        w = worlds[w % len(worlds)]
        done = sorted(self.delivered[w])
        c = done[j % len(done)]
        self._send(w, c, via_ws)
        self._found(w, c)

    @rule(w=WORLD, action=st.sampled_from(["reconnect", "confirm", "touch"]), j=INDEX)
    def chatter(self, w, action, j):
        """The rest of what a client sends: a reconnect, a signal confirm, a spirit well touch."""
        w = self._world(w)
        if action == "reconnect":
            payload = {"version": H.VERSION, "seed": "Sync%s.%s|Multiworld" % (self.gid, w)}
            assert H.request(netcode.connect, self.gid, w, payload) == (200, "ok")
            self.unbusted.clear()
        elif action == "confirm":
            signals = H.request(lambda: H.fresh_player(self.gid, w).signals)
            if signals:
                reply = H.request(netcode.signal_callback, self.gid, w, signals[j % len(signals)])
                assert reply == (200, "cleared"), reply
        else:
            well = H.TELEPORTERS[j % len(H.TELEPORTERS)]
            reply = H.request(netcode.found_pickup, self.gid, w, "1", "TP", well, {"zone": H.ZONE})
            assert reply[0] == 200, reply
            if ShareType.TELEPORTER in self.types:
                self._grant(Pickup.n("TP", well), None)

    def _complete(self, w, via_ws):
        if via_ws:
            assert H.request(ws.handle_frame, self.gid, w, "complete:") == ("completeack:200", False)
        else:
            assert H.request(netcode.game_complete, self.gid, w) == (200, "ok")

    @precondition(lambda self: self.k and any(self.delivered.values()))
    @rule(w=WORLD, via_ws=st.booleans(), failure=FAILURES)
    def complete(self, w, via_ws, failure):
        """A world that found something rolls the credits; its release hands over whatever is left."""
        worlds = [w for w in range(1, self.k + 1) if self.delivered[w]]
        w = worlds[w % len(worlds)]
        if failure is None:
            self._complete(w, via_ws)
        else:
            with H.FlakyGrants(0, failure[1]) as flaky:
                try:
                    self._complete(w, via_ws)
                    acked = True
                except H.InjectedFailure:
                    acked = False
            assert acked != flaky.fired, "a failed release was acked, so its client never resends it"
            if not acked:
                self._committed(flaky)
                self._maybe_marked(w, self.lines[w])
                return
        self._released(w)

    @invariant()
    def worlds_hold_what_the_ledger_owes(self):
        if self.k is not None:
            H.request(self._check)

    def _check(self):
        seated = H.roster(self.gid)
        assert seated == list(range(1, self.k + 1)), seated
        for pid in range(1, self.k + 1):
            p = H.fresh_player(self.gid, pid)
            slots = H.slots_of(p.slot_bflds)
            owed, maybe = self.owed[pid], self.owed[pid] | self.maybe_owed[pid]
            assert owed <= slots <= maybe, "P%s slots %s, owed %s, at most %s" % (
                pid, sorted(slots), sorted(owed), sorted(maybe))
            held = {"SK": p.skills or 0, "TP": p.teleporters or 0, "EV": p.events or 0}
            owed_bits = {code: self.bits[code] for code in held}
            assert held == owed_bits, "P%s bits %s, owed %s" % (pid, held, owed_bits)
            bonuses = dict(p.bonuses or {})
            assert set(bonuses) == set(self.events), "P%s bonuses %s, owed %s" % (pid, bonuses, sorted(self.events))
            for id, n in bonuses.items():
                lo, hi = self._held_range(id)
                assert lo <= n <= hi, "P%s holds %s of RB|%s, owed %s to %s" % (pid, n, id, lo, hi)
            assert bool(p.released) == (pid in self.released), "P%s released=%s" % (pid, p.released)


class MultiworldGrantsMatchTheLedger(H.EmulatedCase, MultiworldGrants.TestCase):
    settings = settings(max_examples=examples(40), stateful_step_count=40 if DEEP else 30)


# --- a tick paused at each point while other requests finish ---

# the paused tick holds a Player read from here until its cache write
HOLDS_A_READ = ("after_txn", "before_cache_write")
SAME_PLAYER_TICKS = ("tick_same", "tick_moved")
OPS = ("mw_grant", "shared_grant", "stale_seed", "conf", "tick_same", "tick_moved", "push", "tracker_players",
       "complete_other", "complete_self", "reconnect")


def renders_the_legacy_tick(op):
    return op == "tracker_players"


def second_tick_under_a_held_read(point, ops):
    """A same-player tick finishing while a paused one holds its read."""
    return point in HOLDS_A_READ and any(op in SAME_PLAYER_TICKS for op in ops)


INTERLEAVED_OPS = st.sampled_from(OPS).filter(lambda op: not renders_the_legacy_tick(op))
PAUSES = st.tuples(st.sampled_from(H.PausePoint.POINTS), st.lists(INTERLEAVED_OPS, max_size=3)).filter(
    lambda pause: not second_tick_under_a_held_read(*pause))


def interleaving_game(gid):
    """P2's world holds twelve of P1's items and the shared skills; returns P2's lines."""
    rows = [(c, 2, "EC", "1", 1) for c in H.LOCATIONS[:12]]
    rows += [(c, 2, "SK", s, None) for c, s in zip(H.LOCATIONS[12:], H.SKILLS)]
    return H.seed_lines(H.make_game(gid, 2, ["Skills"], H.placements_of(rows)), 2)


class TickInterleavings(RuleBasedStateMachine):
    """A tick paused at any point while other requests finish; the next tick serves what a fresh read renders."""

    def __init__(self):
        super().__init__()
        self.gid = H.fresh_gid()
        lines = H.request(interleaving_game, self.gid)
        self.finds = {code: [(c, id) for c, (k, id) in sorted(lines.items()) if k == code] for code in ("MW", "SK")}
        self.seen, self.stale = [], 0

    def _move(self):
        self.seen = self.seen + [H.COORDS[len(self.seen)]]

    def _find(self, code):
        if self.finds[code]:
            c, id = self.finds[code].pop(0)
            netcode.found_pickup(self.gid, 2, str(c), code, id, {"zone": H.ZONE})

    def _op(self, op):
        gid = self.gid
        if op == "mw_grant":
            self._find("MW")
        elif op == "shared_grant":
            self._find("SK")
        elif op == "stale_seed":
            self.stale += 1
            netcode.connect(gid, 1, {"version": H.VERSION, "seed": "Sync%s.1|Multiworld" % (gid + self.stale)})
        elif op == "conf":
            signals = H.fresh_player(gid, 1).signals
            if signals:
                netcode.signal_callback(gid, 1, signals[0])
        elif op in SAME_PLAYER_TICKS:
            if op == "tick_moved":
                self._move()
            netcode.tick(gid, 1, H.tick_payload(self.seen))
        elif op == "push":
            netcode.tick_output(gid, 1)
        elif op == "tracker_players":
            for p in Game.with_id(gid).visible_players():
                p.output()
        elif op == "complete_other":
            netcode.game_complete(gid, 2)
        elif op == "complete_self":
            netcode.game_complete(gid, 1)
        elif op == "reconnect":
            netcode.connect(gid, 1, {"version": H.VERSION})

    @rule(pause=PAUSES, move=st.booleans())
    def paused_tick(self, pause, move):
        point, ops = pause
        if move:
            self._move()

        def fire():
            for op in ops:
                H.concurrent(self._op, op)
        with H.PausePoint(point, fire):
            status, _ = H.request(netcode.tick, self.gid, 1, H.tick_payload(self.seen))
        assert status == 200
        status, body = H.request(netcode.tick, self.gid, 1, H.tick_payload(self.seen))
        want = H.request(H.fresh_render, self.gid, 1)
        assert body == want, "stale tick body\n got %r\nwant %r" % (body, want)

    @rule(op=INTERLEAVED_OPS)
    def solo(self, op):
        H.request(self._op, op)


class ATickServesWhatAFreshReadRenders(H.EmulatedCase, TickInterleavings.TestCase):
    settings = settings(max_examples=examples(30), stateful_step_count=12 if DEEP else 8)


# --- open bugs the machines mask; a fix makes its repro an unexpected success ---

class _OuterContext(object):
    """Hands the request middleware the context the test is already inside."""

    def context(self):
        return contextlib.nullcontext()


class TheTickCacheServesFreshBodies(H.EmulatedCase):
    def setUp(self):
        self.gid = H.fresh_gid()
        lines = H.request(interleaving_game, self.gid)
        self.c, self.id = next((c, id) for c, (code, id) in sorted(lines.items()) if code == "MW")

    @unittest.expectedFailure
    def test_a_tick_finishing_under_a_paused_one_leaves_no_stale_body(self):
        def fire():
            H.concurrent(netcode.found_pickup, self.gid, 2, str(self.c), "MW", self.id, {})
            H.concurrent(netcode.tick, self.gid, 1, H.tick_payload([]))
        with H.PausePoint("after_txn", fire):
            H.request(netcode.tick, self.gid, 1, H.tick_payload([]))
        body = H.request(netcode.tick, self.gid, 1, H.tick_payload([]))[1]
        self.assertEqual(body, H.request(H.fresh_render, self.gid, 1))


class TheTrackerLeavesTheTickCacheAlone(H.EmulatedCase):
    def setUp(self):
        import main
        self.gid = H.fresh_gid()
        H.request(interleaving_game, self.gid)
        assert H.request(netcode.tick, self.gid, 1, H.tick_payload([]))[0] == 200
        self.addCleanup(setattr, main.app, "secret_key", main.app.secret_key)
        main.app.secret_key = main.app.secret_key or "props"
        with mock.patch.object(models, "client", _OuterContext()):
            page = H.request(main.app.test_client().get, "/game/%s/players/" % self.gid)
        assert page.status_code == 200, page.status_code

    @unittest.expectedFailure
    def test_the_players_page_leaves_a_multiworld_tick_alone(self):
        body = H.request(netcode.tick, self.gid, 1, H.tick_payload([]))[1]
        self.assertEqual(body, H.request(H.fresh_render, self.gid, 1))


class GrantsThatFailLateStillBustTheTickCache(H.EmulatedCase):
    def setUp(self):
        self.gid, self.c = H.fresh_gid(), H.LOCATIONS[0]
        H.request(H.make_game, self.gid, 2, ["Skills"], H.placements_of([(self.c, 1, "SK", "0", None)]))
        assert H.request(netcode.tick, self.gid, 2, H.tick_payload([]))[0] == 200

    def _commits_then_fails(self, fn, *args):
        with H.FlakyGrants(0, True):
            try:
                H.request(fn, *args)
            except H.InjectedFailure:
                pass

    def _tick_is_fresh(self):
        self.assertEqual(H.request(netcode.tick, self.gid, 2, H.tick_payload([]))[1],
                         H.request(H.fresh_render, self.gid, 2))

    @unittest.expectedFailure
    def test_a_find_whose_grant_commits_then_fails_leaves_no_stale_tick(self):
        self._commits_then_fails(netcode.found_pickup, self.gid, 1, str(self.c), "SK", "0", {"zone": H.ZONE})
        self._tick_is_fresh()

    @unittest.expectedFailure
    def test_a_release_whose_grant_commits_then_fails_leaves_no_stale_tick(self):
        self._commits_then_fails(netcode.game_complete, self.gid, 1)
        self._tick_is_fresh()


# --- slot bitfields ---

class SlotBitfields(H.QuietCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ndb_client = ndb.Client(project="unit-test", credentials=AnonymousCredentials())

    @settings(max_examples=examples(500))
    @given(marks=st.lists(st.integers(-5, 300)))
    def test_marked_slots_read_back_from_tick_field_six(self, marks):
        gid, held = H.fresh_gid(), set()
        with self.ndb_client.context():
            p = Player(id="%s.1" % gid, parent=ndb.Key(Game, gid), skills=0, events=0, teleporters=0,
                       bonuses={}, hints={}, signals=[])
            for slot in marks:
                fresh = 0 <= slot <= 255 and slot not in held
                self.assertEqual(p.mark_slot(slot, delay_put=True), fresh, slot)
                if fresh:
                    held.add(slot)
            Cache.set_names(gid, "1.Player 1")
            field = p.output(include_slots=True).split(",")[6].split(";")
        self.assertEqual(len(field), 8, field)
        self.assertTrue(all(word.isascii() and word.isdigit() and int(word) < 2**32 for word in field), field)
        self.assertEqual(H.slots_of(field), held)
        self.assertEqual({s for s in range(256) if p.slot_check(s)}, held)


# --- tick and find parsing ---

def word_breaks_the_tick(text):
    """A seen or have word int() refuses, or one past ndb's 64-bit ints."""
    try:
        return not -2**63 <= int(text) < 2**63
    except ValueError:
        return True


def word_outside_32_bits(text):
    """A seen or have word int() reads outside 32 bits."""
    return not word_breaks_the_tick(text) and not 0 <= int(text) < 2**32


def version_breaks_the_tick(version):
    return len(version.encode("utf-8")) > 1500


ODD_WORDS = st.one_of(
    st.integers(0, 2**32 - 1).map(str),
    st.tuples(st.sampled_from([" %s", "+%s", "%s ", "0%s"]), st.integers(0, 2**32 - 1)).map(lambda t: t[0] % t[1]),
    st.sampled_from(["-0", "1_0", "\u0661\u0662", "\uff17", str(2**32 - 1)]),
    st.sampled_from(["", "abc", "7.0", "0x10", "1e3", "\u00b2", "-1", str(2**32), str(2**63), "9" * 5000]),
    st.integers(-2**64, 2**65).map(str),
    st.text(max_size=6),
).filter(lambda text: not word_breaks_the_tick(text) and not word_outside_32_bits(text))
VERSIONS = st.one_of(
    st.just(H.VERSION), st.just(""), st.text(max_size=24),
    st.integers(1490, 1510).map(lambda n: "v" * n), st.integers(740, 760).map(lambda n: "\u00e9" * n),
).filter(lambda version: not version_breaks_the_tick(version))
FORM_KEYS = ["%s_%s" % (kind, i) for kind in ("seen", "have") for i in range(8)]


@st.composite
def tick_forms(draw):
    """A tick form: client words, a few odd ones, any number missing, any version and position."""
    form = H.tick_payload(draw(st.lists(st.sampled_from(H.COORDS), max_size=12, unique=True)))
    for key in draw(st.lists(st.sampled_from(FORM_KEYS), max_size=3, unique=True)):
        form[key] = draw(ODD_WORDS)
    for key in draw(st.lists(st.sampled_from(FORM_KEYS + ["version", "x", "y"]), max_size=19, unique=True)):
        form.pop(key)
    if "version" in form:
        form["version"] = draw(VERSIONS)
    for key in ("x", "y"):
        if key in form:
            form[key] = draw(st.text(max_size=12))
    return form


def coords_of(sent):
    return {H.COORDS[w * 32 + b] for w, word in enumerate(sent) for b in range(32) if (word >> b) & 1}


class TickParsing(H.EmulatedCase):
    @settings(max_examples=examples(100))
    @given(form=tick_forms())
    def test_a_tick_form_is_answered_and_never_corrupts_the_stored_player(self, form):
        gid = H.fresh_gid()
        H.request(H.make_game, gid, 2, [])
        before = H.request(H.fresh_player, gid, 1)
        status, body = H.answer(netcode.tick, gid, 1, form)
        self.assertTrue(status == 200 or 400 <= status < 500, status)
        after = H.request(H.fresh_player, gid, 1)
        if status != 200:
            self.assertEqual((after.seen_bflds, after.have_bflds, after.dll_version),
                             (before.seen_bflds, before.have_bflds, before.dll_version))
            return
        self.assertEqual(body, H.request(H.fresh_render, gid, 1))
        for kind, stored, coords in (("seen", after.seen_bflds, after.seen_coords()),
                                     ("have", after.have_bflds, after.have_coords())):
            self.assertTrue(len(stored) == 8 and all(0 <= word < 2**32 for word in stored), (kind, stored))
            sent = [int(form.get("%s_%s" % (kind, i), 0)) for i in range(8)]
            if all(0 <= word < 2**32 for word in sent):
                self.assertEqual(set(coords) - {2}, coords_of(sent), kind)
        if form.get("version"):
            self.assertEqual(after.dll_version, form["version"])


class OddTickAndConnectFields(H.EmulatedCase):
    def setUp(self):
        self.gid = H.fresh_gid()
        H.request(H.make_game, self.gid, 2, [])
        assert H.answer(netcode.tick, self.gid, 1, H.tick_payload([]))[0] == 200

    def _status(self, **fields):
        # new seen words, or the fast path answers before anything is parsed
        form = H.tick_payload([H.COORDS[0]])
        form.update(fields)
        return H.answer(netcode.tick, self.gid, 1, form)[0]

    def _stored_words(self):
        p = H.request(H.fresh_player, self.gid, 1)
        return p.seen_bflds + p.have_bflds

    @unittest.expectedFailure
    def test_a_non_numeric_seen_word_is_answered_not_a_500(self):
        self.assertNotEqual(self._status(seen_0="abc"), 500)

    @unittest.expectedFailure
    def test_a_seen_word_past_64_bits_is_answered_not_a_500(self):
        self.assertNotEqual(self._status(seen_0=str(2**64)), 500)

    @unittest.expectedFailure
    def test_a_negative_seen_word_never_reaches_the_stored_player(self):
        self._status(seen_0="-1")
        self.assertTrue(all(0 <= word < 2**32 for word in self._stored_words()), self._stored_words())

    @unittest.expectedFailure
    def test_a_seen_word_past_32_bits_never_reaches_the_stored_player(self):
        self._status(seen_0=str(2**32))
        self.assertTrue(all(0 <= word < 2**32 for word in self._stored_words()), self._stored_words())

    @unittest.expectedFailure
    def test_a_tick_with_an_overlong_version_is_answered_not_a_500(self):
        self.assertNotEqual(self._status(version="v" * 1501), 500)

    @unittest.expectedFailure
    def test_a_connect_with_an_overlong_version_is_answered_not_a_500(self):
        self.assertNotEqual(H.answer(netcode.connect, self.gid, 1, {"version": "v" * 1501})[0], 500)


def mw_item(mwid):
    """The MW item a find's id parses to, or None where netcode refuses it."""
    try:
        return Pickup.n("MW", mwid)
    except (TypeError, ValueError):
        return None


def owner_outside_the_game(mwid, worlds):
    """An MW find naming an owner the game doesn't seat."""
    item = mw_item(mwid)
    return item is not None and not 1 <= item.owner <= worlds


def named_slot(mwid):
    """(owner, slot) an MW find marks, or None when it marks nothing."""
    item = mw_item(mwid)
    return (item.owner, item.slot) if item is not None and 0 <= item.slot <= 255 else None


OWNERS = st.one_of(st.integers(0, 12).map(str),
                   st.sampled_from(["01", "", "x", "-1", "1.0", " 1", "\u00b2", "\u0661", str(2**64)]))
SLOTS = st.one_of(st.integers(0, 300).map(str), st.sampled_from(["", "x", "-1", "007", str(2**70), "\u00b2"]))
RESTS = st.sampled_from(["EC,1", "SK,4", "", "AP,Some Item", "RB,17,extra", ",,,"])


@st.composite
def finds(draw):
    """(worlds, finder, MW id) for one find, owners outside the game masked."""
    worlds = draw(st.integers(2, 3))
    mwid = draw(st.one_of(st.tuples(OWNERS, SLOTS, RESTS).map(",".join), st.text(max_size=10)).filter(
        lambda mwid: not owner_outside_the_game(mwid, worlds)))
    return worlds, draw(st.integers(1, worlds)), mwid


class FindParsing(H.EmulatedCase):
    @settings(max_examples=examples(100))
    @given(find=finds())
    def test_a_find_marks_only_the_slot_it_names_and_seats_no_one(self, find):
        worlds, finder, mwid = find
        gid = H.fresh_gid()
        H.request(H.make_game, gid, worlds, [])
        status = H.answer(netcode.found_pickup, gid, finder, str(H.LOCATIONS[0]), "MW", mwid, {})[0]
        self.assertIn(status, (200, 406))

        def state():
            return H.roster(gid), {pid: H.slots_of(H.fresh_player(gid, pid).slot_bflds) for pid in range(1, worlds + 1)}
        seated, slots = H.request(state)
        self.assertEqual(seated, list(range(1, worlds + 1)))
        want = {pid: set() for pid in range(1, worlds + 1)}
        if named_slot(mwid):
            owner, slot = named_slot(mwid)
            want[owner].add(slot)
        self.assertEqual(slots, want)


class FindsSeatNoOne(H.EmulatedCase):
    @unittest.expectedFailure
    def test_a_find_naming_an_owner_outside_the_game_seats_no_one(self):
        gid = H.fresh_gid()
        H.request(H.make_game, gid, 2, [])
        H.answer(netcode.found_pickup, gid, 1, str(H.LOCATIONS[0]), "MW", "9,0,EC,1", {})
        self.assertEqual(H.request(H.roster, gid), [1, 2])


# --- multipickups in multiworld ---

class MultipickupsGrantLikeSingles(H.EmulatedCase):
    def setUp(self):
        self.gid, self.c = H.fresh_gid(), H.LOCATIONS[0]
        piece = [("SK", "4"), ("EC", "1@2")]
        params = H.request(H.make_game, self.gid, 2, ["Skills"],
                           H.placements_of([(self.c, 1, "MU", util.compose_multi_value(piece), None)]))
        self.code, self.id = H.request(H.seed_lines, params, 1)[self.c]

    def _p2(self):
        p = H.request(H.fresh_player, self.gid, 2)
        return p.skills or 0, H.slots_of(p.slot_bflds)

    def test_a_multipickup_seen_before_its_find_still_grants(self):
        H.request(netcode.tick, self.gid, 1, H.tick_payload([self.c]))
        H.request(netcode.found_pickup, self.gid, 1, str(self.c), self.code, self.id, {"zone": H.ZONE})
        self.assertEqual(self._p2(), (Pickup.n("SK", "4").bit, {0}))

    def test_a_release_hands_over_an_unfound_multipickups_slots(self):
        H.request(netcode.game_complete, self.gid, 1)
        self.assertEqual(self._p2(), (Pickup.n("SK", "4").bit, {0}))


if __name__ == "__main__":
    unittest.main()
