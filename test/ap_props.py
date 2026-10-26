"""Property tests for Archipelago support: yaml, conversion, the bridge's grants and hint market, and logic parity."""
from test.strategies.base import examples, deep_only, DEEP

import unittest
from collections import Counter

from hypothesis import assume, given, note, settings, strategies as st
from hypothesis.stateful import (RuleBasedStateMachine, initialize, invariant, precondition, rule,
                                 run_state_machine_as_test)

import ap_models
from ap_models import APHints, HINT_OFFERED, HINT_PENDING, HINT_RESOLVED, ap_slot_names
from archipelago import ap_bridge
from archipelago.convert import (ApConversionError, MAX_SLOTS, ap_convert, ap_variations,
                                 build_ap_config, match_key)
from archipelago.yaml_emit import ITEM_NAMES, LOC_NAMES, _emit, emit_yaml, make_config
from test.strategies.ap import (DOORS, FOREIGN, GID, ApLogic, Clock, FakeParams, HintRoom, HintRows,
                                ReachConfig, Reroute, Seat, SlotHolder, Sock, ap_have, data_package,
                                elemental_arena_rolls, emitter_values, fill_room, hello, hint_maps,
                                hint_markets, inventories, item_census, manifest, mw_games, ndb_context,
                                normal, parse, quiet, reach_configs, result_text, room_yaml, server_reach,
                                session_for, slot_name_lists, yaml_configs)
from util import is_mw_manifest_loc


# --- open-bug classes: each property masks one, a repro below carries its expectedFailure ---

def rolled_arena(config):
    return bool(config.get("arena_killers"))


def holds_a_list_in_a_list(value):
    if isinstance(value, dict):
        return any(holds_a_list_in_a_list(v) for v in value.values())
    if isinstance(value, list):
        return any(isinstance(v, list) or holds_a_list_in_a_list(v) for v in value)
    return False


def outrun_by_a_hint_from_elsewhere(say):
    return say["outrun"]


def bought_again_after_a_pending_claim_was_overwritten(say):
    return say["clobbered"]


def starts_in_grotto(config):
    return config.zone == "Grotto"


def run_machine(machine, n, steps=30):
    with quiet():
        run_state_machine_as_test(machine, settings=settings(max_examples=examples(n), stateful_step_count=steps))


# --- the yaml ---

class YamlRoundTrip(unittest.TestCase):
    @settings(max_examples=examples(150))
    @given(yaml_configs(), slot_name_lists, st.data())
    def test_the_room_reads_back_what_make_config_wrote(self, config, names, data):
        slot = ap_slot_names(len(names), names)[data.draw(st.integers(1, len(names))) - 1]
        doc = room_yaml(emit_yaml(config, slot))
        got, want = doc["Ori DE Rando"]["orirando"], normal(config)
        if rolled_arena(config):
            got.pop("arena_killers")
            want.pop("arena_killers")
        self.assertEqual(doc["name"], slot)
        self.assertEqual(doc["Ori DE Rando"]["death_link"], int(config["death_link"]))
        self.assertEqual(got, want)

    @settings(max_examples=examples(200))
    @given(emitter_values())
    def test_every_value_shape_make_config_emits_reads_back(self, value):
        assume(not holds_a_list_in_a_list(value))
        text = "\n".join(_emit({"v": value}, 0)) + "\n"
        note(text)
        self.assertEqual(room_yaml(text), {"v": value})

    @unittest.expectedFailure
    def test_arena_killers_survive_the_yaml(self):
        config = make_config({}, [], {}, ["casual-core"], variations=ap_variations(["EnemyRando"]),
                             enemy_rolls=elemental_arena_rolls())
        parsed = room_yaml(emit_yaml(config, "Ori1"))["Ori DE Rando"]["orirando"]
        self.assertEqual(parsed["arena_killers"], normal(config["arena_killers"]))


# --- conversion and the tables ---

class Conversion(unittest.TestCase):
    @settings(max_examples=examples(100))
    @given(mw_games(), st.data())
    def test_conversion_keeps_every_item_with_its_owner_and_balances(self, game, data):
        texts, cats, truth = game
        spots = [(v, loc) for v, loc, *_ in truth]
        keep = frozenset(data.draw(st.lists(st.sampled_from(spots), unique=True, max_size=3)) if spots else [])
        try:
            new, info = ap_convert(list(texts), cats, keep_locs=keep)
        except ApConversionError as e:
            self.assertIn("forced cross-world", str(e))
            return
        k = len(texts)
        self.assertEqual(item_census(new), item_census(texts))
        self.assertEqual(sum(map(len, info["reserved"].values())), sum(map(len, info["exported"].values())))
        for p in range(1, k + 1):
            rows = parse(new[p - 1])
            reserved = sorted((int(l), pid) for l, c, pid, _ in rows
                              if c == "MW" and not is_mw_manifest_loc(int(l)) and pid.split(",")[0] == str(k + p))
            self.assertEqual([loc for loc, _ in reserved], [loc for loc, _ in info["reserved"][p]])
            for i, (_, pid) in enumerate(reserved):
                self.assertEqual(pid, "%s,%s,,-1,AP,AP Item #%s" % (k + p, i, i + 1))
            slots = manifest(rows)
            self.assertEqual(sorted(s for s, pid in slots.items() if pid.split(",")[0] == str(k + p)),
                             sorted(info["ap_slots"][p]))
            self.assertTrue(all(0 <= s < MAX_SLOTS for s in slots))
            lines = [l for l, c, *_ in rows if c == "MW" and is_mw_manifest_loc(int(l))]
            self.assertEqual(len(lines), len(set(lines)))
        for v in range(1, k + 1):
            for loc, code, pid, _ in parse(new[v - 1]):
                if code == "MW" and not is_mw_manifest_loc(int(loc)):
                    owner, slot = pid.split(",")[:2]
                    if int(owner) <= k:
                        self.assertIn(int(slot), manifest(parse(new[int(owner) - 1])))
        if any(info["reserved"].values()):
            with self.assertRaises(ApConversionError):
                ap_convert(list(new), cats)

    @settings(max_examples=examples(100))
    @given(mw_games())
    def test_bridge_maps_and_yaml_agree_with_conversion(self, game):
        texts, cats, _ = game
        new, info = ap_convert(list(texts), cats)
        k = len(texts)
        maps = ap_bridge.maps_from_params(FakeParams(new))
        total = 0
        for p in range(1, k + 1):
            self.assertEqual(maps.outbox[p], {i: ap_bridge.AP_LOC_BY_COORD[loc] for loc, i in info["reserved"][p]})
            self.assertEqual(sorted(s for lst in maps.grant_slots[p].values() for s in lst),
                             sorted(info["ap_slots"][p]))
            want = Counter(match_key(c, i) for c, i, _ in info["exported"][p])
            self.assertEqual(Counter({key: len(lst) for key, lst in maps.grant_slots[p].items()}), want)
            for key in want:
                self.assertIn(key, ap_bridge.AP_ID_BY_ITEM_KEY)
            cfg = build_ap_config(parse(new[p - 1]), k, p, ["casual-core"], "Clues", "Glades", {"open": True})
            self.assertEqual(sorted(cfg["reserved_locations"]),
                             sorted(LOC_NAMES[loc] for loc, _ in info["reserved"][p]))
            self.assertEqual(Counter(cfg["exported_items"]), Counter({ITEM_NAMES[key]: n for key, n in want.items()}))
            total += sum(cfg["exported_items"].values())
        self.assertEqual(total, sum(len(info["reserved"][p]) for p in range(1, k + 1)))


class Datapackage(unittest.TestCase):
    def test_item_and_location_ids_are_bijections(self):
        self.assertEqual(len(ap_bridge.ITEM_KEY_BY_AP_ID), len(ap_bridge.AP_ID_BY_ITEM_KEY))
        for ap_id, (code, pid) in ap_bridge.ITEM_KEY_BY_AP_ID.items():
            self.assertEqual(ap_bridge.AP_ID_BY_ITEM_KEY[(code, str(pid))], ap_id)
        self.assertEqual(len(set(ap_bridge.AP_LOC_BY_COORD.values())), len(ap_bridge.AP_LOC_BY_COORD))

    @settings(max_examples=examples(200))
    @given(st.sampled_from(["EX", "TW", "SK", "RB", "XX"]),
           st.one_of(st.integers(-10**6, 10**6).map(str), st.text(max_size=12), st.integers(-5, 5)))
    def test_the_bridge_names_an_item_the_way_conversion_does(self, code, pid):
        self.assertEqual(ap_bridge._match_key(code, pid), match_key(code, pid))

    @settings(max_examples=examples(200))
    @given(st.lists(st.text(max_size=24), max_size=10), st.integers(1, 12))
    def test_slot_names_survive_the_rooms_name_handling(self, names, worlds):
        out = ap_slot_names(worlds, names)
        self.assertEqual(out, ap_slot_names(worlds, names))
        self.assertEqual(len(out), worlds)
        self.assertEqual(len({n.lower() for n in out}), worlds)
        for name in out:
            self.assertTrue(0 < len(name) <= 16 and name != "Archipelago")
            self.assertEqual(name, name.strip()[:16].strip())
            self.assertFalse(set(name) & set("{}%"))


# --- the bridge's grants ---

class Delivery(RuleBasedStateMachine):
    """A converted game's grants: a room that fills it, sessions that come and go, the client's contact grants."""
    FILLER = False
    DEGRADED = False

    @initialize(game=mw_games(max_worlds=3, max_locs=14), data=st.data())
    def setup(self, game, data):
        self.reroute = Reroute()
        self.room = fill_room(game, data, self.FILLER)
        worlds = range(1, self.room.k + 1)
        self.sessions, self.room_sent, self.scouts_now = {}, {}, {}
        self.pending_scouts = {w: [] for w in worlds}
        self.holders = {w: SlotHolder() for w in worlds}
        self.contact = {w: set() for w in worlds}
        self.blob = {w: None for w in worlds}
        self.blobs_seen = {w: set() for w in worlds}
        self.stored = {w: ({}, None) for w in worlds}
        self.hide_stored = {w: False for w in worlds}
        self.degraded = {w: False for w in worlds}
        self.recv = {w: 0 for w in worlds}
        self.drops = []
        self.reroute.bridge(
            _apply_grants=lambda gid, w, slots, senders=None: sum(1 for s in slots if self.holders[w].mark(s)),
            _apply_extras=lambda gid, w, entries: self.holders[w].add_extras(entries)[1],
            _persist_recv=self.persist_recv,
            _persist_names=self.persist_names,
            _persist_drop=lambda gid, w, entry: self.drops.append((w, entry)) or True,
            _persist_promises=self.persist_promises,
            _load_scout_row=lambda gid, w: ({}, None) if self.hide_stored[w] else self.stored[w])
        note("k=%s placed=%s start=%s order=%s" % (self.room.k, self.room.placed, self.room.start, self.room.order))

    def teardown(self):
        if hasattr(self, "reroute"):
            self.reroute.restore()
        ap_bridge._dp_cache.clear()

    def persist_recv(self, gid, w, count):
        assert count >= 0
        self.recv[w] = max(self.recv[w], count)

    def persist_names(self, gid, w, total, names, ap_slot=None):
        self.stored[w] = (dict(names), ap_slot)

    def persist_promises(self, gid, w, blob):
        self.blob[w] = dict(blob)
        self.blobs_seen[w].add(tuple(sorted(blob.items())))

    def pump(self, w):
        """Answers whatever the session asked the room, until it asks nothing new."""
        s = self.sessions.get(w)
        for _ in range(20):
            sent = s.sock.take()
            if not sent:
                break
            for msg in sent:
                if msg.get("cmd") == "Sync":
                    stream = self.room.stream(w)
                    self.room_sent[w] = len(stream)
                    s._dispatch({"cmd": "ReceivedItems", "index": 0, "items": stream}, s.sock)
                elif msg.get("cmd") == "LocationScouts":
                    locs = msg["locations"]
                    now = len(locs) if self.scouts_now[w] == "now" else len(locs) // 2 if self.scouts_now[w] else 0
                    if now:
                        s._dispatch(self.room.location_info(w, locs[:now]), s.sock)
                    if locs[now:]:
                        self.pending_scouts[w].append(locs[now:])
                elif msg.get("cmd") == "GetDataPackage":
                    s._dispatch(data_package(), s.sock)
            s._service_promises(s.sock)

    def open_session(self, w, mode):
        if w in self.sessions:
            self.close_session(w)
        session = session_for(self.room.k, w, self.room.maps)
        session.sock = Sock(self.room.hello(w))
        self.scouts_now[w] = mode if mode in ("now", "split") else None
        self.pending_scouts[w] = []
        self.hide_stored[w] = mode == "degraded"
        self.sessions[w] = session
        self.room_sent[w] = len(self.room.stream(w))
        session._handshake(session.sock)
        if mode in ("stored", "degraded"):
            session.promises_deadline = ap_bridge.monotonic() - 1
        self.pump(w)
        if (session.promised is not None and len(session.scouted) < session.scout_total
                and session._stored_scouts() is None):
            self.degraded[w] = True

    def close_session(self, w):
        self.sessions.pop(w)._flush_grants()

    def held(self, w):
        h = self.holders[w]
        return Counter(self.room.export_key[(w, s)] for s in h.marked() | self.contact[w]) + h.extra_keys()

    def check_holdings(self, w, settled=False):
        held, sent = self.held(w), self.room.keys(self.room.stream(w))
        owed = self.room.keys(self.room.stream(w, everything=True))
        for key in set(held) | set(sent):
            if self.degraded[w]:
                assert held[key] <= owed[key], "world %s holds %s x%s, owed %s" % (w, key, held[key], owed[key])
                assert not settled or held[key] >= sent[key], "world %s lost %s" % (w, key)
            elif settled:
                assert held[key] == sent[key], "world %s holds %s x%s, sent %s" % (w, key, held[key], sent[key])
            else:
                assert held[key] <= sent[key], "world %s holds %s x%s, sent %s" % (w, key, held[key], sent[key])

    @rule(n=st.integers(1, 6))
    def room_checks(self, n):
        self.room.checked += [loc for loc in self.room.order if loc not in self.room.checked][:n]

    @rule(data=st.data())
    def connect(self, data):
        modes = ["now", "split", "late", "stored"] + (["degraded"] if self.DEGRADED else [])
        self.open_session(data.draw(st.integers(1, self.room.k)), data.draw(st.sampled_from(modes)))

    @precondition(lambda self: self.sessions)
    @rule(data=st.data())
    def answer_scouts(self, data):
        w = data.draw(st.sampled_from(sorted(self.sessions)))
        s = self.sessions[w]
        for locs in self.pending_scouts[w]:
            s._dispatch(self.room.location_info(w, locs), s.sock)
        self.pending_scouts[w] = []
        s._service_promises(s.sock)
        self.pump(w)

    def push(self, w, index, items):
        s = self.sessions[w]
        s._dispatch({"cmd": "ReceivedItems", "index": index, "items": items}, s.sock)
        s._service_promises(s.sock)
        self.pump(w)

    @precondition(lambda self: self.sessions)
    @rule(data=st.data())
    def room_sends_the_next_items(self, data):
        w = data.draw(st.sampled_from(sorted(self.sessions)))
        stream, sent = self.room.stream(w), self.room_sent[w]
        self.room_sent[w] = len(stream)
        self.push(w, sent, stream[sent:])

    @precondition(lambda self: self.sessions)
    @rule(data=st.data())
    def room_resends_old_items(self, data):
        w = data.draw(st.sampled_from(sorted(self.sessions)))
        sent = self.room_sent[w]
        back = data.draw(st.integers(0, sent))
        if back < sent:
            self.push(w, back, self.room.stream(w)[back:sent])

    @precondition(lambda self: self.sessions)
    @rule(data=st.data())
    def a_batch_is_lost_on_the_way(self, data):
        w = data.draw(st.sampled_from(sorted(self.sessions)))
        stream, sent = self.room.stream(w), self.room_sent[w]
        if len(stream) > sent + 1:
            self.push(w, sent + 1, stream[sent + 1:])

    @precondition(lambda self: self.sessions)
    @rule(data=st.data())
    def flush(self, data):
        self.sessions[data.draw(st.sampled_from(sorted(self.sessions)))]._flush_grants()

    @precondition(lambda self: self.sessions)
    @rule(data=st.data())
    def disconnect(self, data):
        self.close_session(data.draw(st.sampled_from(sorted(self.sessions))))

    @rule(data=st.data())
    def client_touches_own_location(self, data):
        w = data.draw(st.integers(1, self.room.k))
        own = self.room.own_locs(w)
        if not own:
            return
        loc = data.draw(st.sampled_from(own))
        shadow = {ap: s for s, ap in self.room.maps.outbox[w].items()}[loc]
        mine = (self.blob[w] or {}).get(shadow)
        if mine is not None:
            self.contact[w].add(mine)
        if (w, loc) not in self.room.checked:
            self.room.checked.append((w, loc))

    @rule(data=st.data())
    def settle_world(self, data):
        w = data.draw(st.integers(1, self.room.k))
        self.open_session(w, "now")
        self.close_session(w)
        self.check_holdings(w, settled=True)
        assert self.recv[w] == len(self.room.stream(w))

    @invariant()
    def only_export_slots_are_marked(self):
        for w, h in getattr(self, "holders", {}).items():
            for s in h.marked() | self.contact[w]:
                assert (w, s) in self.room.export_key, "world %s slot %s isn't an export" % (w, s)

    @invariant()
    def nothing_is_held_past_what_the_room_sent_or_owes(self):
        for w in getattr(self, "holders", {}):
            self.check_holdings(w)

    @invariant()
    def the_recv_index_never_runs_ahead_of_the_grants(self):
        for w in getattr(self, "holders", {}):
            behind = self.room.keys(self.room.stream(w)[:self.recv[w]]) - self.held(w)
            assert not behind, "world %s recv index %s claims %s" % (w, self.recv[w], dict(behind))
            s = self.sessions.get(w)
            assert s is None or s.recv_count <= self.room_sent[w], "world %s applied past what the room sent" % w

    @invariant()
    def a_promise_names_an_own_item_on_one_of_its_own_slots(self):
        for w, blob in getattr(self, "blob", {}).items():
            for shadow, slot in (blob or {}).items():
                owner, ap_item = self.room.placed[(w, self.room.maps.outbox[w][shadow])]
                assert owner == w, "world %s promised slot %s for slot %s's item" % (w, slot, owner)
                assert self.room.export_key.get((w, slot)) == ap_bridge.ITEM_KEY_BY_AP_ID.get(ap_item)

    @invariant()
    def nothing_is_dropped(self):
        assert not getattr(self, "drops", []), self.drops

    @invariant()
    def one_promise_map_per_world(self):
        for w, seen in getattr(self, "blobs_seen", {}).items():
            assert len(seen) <= 1, "world %s published %s promise maps" % (w, len(seen))


class FillerDelivery(Delivery):
    FILLER = True


class DegradedDelivery(Delivery):
    FILLER = True
    DEGRADED = True


class DeliveryMachine(unittest.TestCase):
    def test_every_sent_item_is_held_exactly_once(self):
        run_machine(Delivery, 80)

    def test_start_inventory_filler_is_held_exactly_once(self):
        run_machine(FillerDelivery, 80)

    def test_a_degraded_fill_loses_nothing_and_grants_nothing_unowed(self):
        run_machine(DegradedDelivery, 100)

    @deep_only
    def test_a_degraded_fill_loses_nothing_over_long_histories(self):
        run_machine(DegradedDelivery, 100, steps=80)


# --- the hint market ---

class HintMarket(RuleBasedStateMachine):
    """Hint purchases across twin sessions, a seed page that presses buy, and a room that answers at its own pace."""

    @initialize(market=hint_markets(), data=st.data())
    def setup(self, market, data):
        self.exports, prices = market
        self.wanted = {w: data.draw(st.sets(st.sampled_from([s for s, _ in slots])))
                       for w, slots in self.exports.items()}
        self.ctx = ndb_context()
        self.ctx.__enter__()
        self.reroute = Reroute()
        self.clock = Clock()
        self.rows = HintRows()
        self.rows.install(self.reroute)
        real = {n: getattr(ap_bridge, n) for n in ("_load_hints", "_claim_hint", "_persist_hint", "_persist_price")}
        self.real_claim = real["_claim_hint"].__wrapped__
        self.real_persist = real["_persist_hint"].__wrapped__
        self.reroute.bridge(_load_hints=real["_load_hints"], _claim_hint=self.claim, _persist_hint=self.persist,
                            _persist_price=real["_persist_price"].__wrapped__)
        self.reroute.set(ap_bridge, "monotonic", self.clock.monotonic)
        self.reroute.set(ap_bridge, "time", self.clock)
        self.reroute.set(ap_models, "time", self.clock)
        ap_bridge._notice_at.clear()
        ap_bridge._dp_put(FOREIGN, "clsum", {}, {"Chest %s" % j: 880000 + j for j in range(64)})
        self.maps = hint_maps(self.exports)
        self.room = HintRoom(self.exports, prices)
        self.seats, self.says, self.queue = [], [], []
        self.buys = Counter()
        self.resolved = set()
        self.last_claim = None
        self.acting = None
        self.claimant = {}
        self.clobbered = set()
        note("exports=%s prices=%s wanted=%s" % (self.exports, prices, self.wanted))
        for w in self.exports:
            self.connect(w)

    def teardown(self):
        if hasattr(self, "reroute"):
            self.reroute.restore()
        if hasattr(self, "ctx"):
            self.ctx.__exit__(None, None, None)
        ap_bridge._dp_cache.clear()
        ap_bridge._notice_at.clear()

    def connect(self, w):
        session = session_for(self.room.k, w, self.maps, hint_box=ap_bridge._HintBox())
        seat = Seat(len(self.seats), w, session, None, self.room.points[w])
        seat.sock = Sock(hello(w, self.room.k, missing=self.room.locations(w), hint_cost=self.room.prices[w][0],
                               hint_points=self.room.points[w]), on_send=lambda msgs: self.on_send(seat, msgs))
        self.seats.append(seat)
        self.guard(seat, session._handshake, seat.sock)

    def claim(self, gid, world, slot, ap_item, stale_ok=False):
        before = self.rows.entries(gid, world).get(int(slot)) or {}
        ok = self.real_claim(gid, world, slot, ap_item, stale_ok=stale_ok)
        if ok:
            self.last_claim = (before.get("s"), before.get("u", 0), stale_ok)
            self.claimant[(world, int(slot))] = self.acting
        return ok

    def persist(self, gid, world, slot, state, text="", ap_item=0, key=""):
        before = (self.rows.entries(gid, world).get(int(slot)) or {}).get("s")
        if (before == HINT_PENDING and state not in (HINT_PENDING, HINT_RESOLVED)
                and self.claimant.get((world, int(slot))) is not self.acting):
            self.clobbered.add((world, int(slot)))
        return self.real_persist(gid, world, slot, state, text=text, ap_item=ap_item, key=key)

    def on_send(self, seat, msgs):
        for msg in msgs:
            if msg.get("cmd") != "Say":
                continue
            slot, item, _ = seat.session.hint_inflight
            now = self.clock.now
            busy = [s for s in seat.says if not s["answered"] and now - s["t"] <= ap_bridge.HINT_ACK_SECS
                    and not outrun_by_a_hint_from_elsewhere(s)]
            say = dict(seat=seat.n, world=seat.world, slot=slot, item=item, text=msg["text"], t=now,
                       points=seat.points, cost=self.room.cost(seat.world), busy=len(busy),
                       claim=self.last_claim, answered=False, outrun=False, refused=False,
                       clobbered=(seat.world, slot) in self.clobbered)
            self.last_claim = None
            seat.says.append(say)
            self.says.append(say)
            self.queue.append((seat, say))

    def live(self):
        return [s for s in self.seats if not s.gone]

    def pick(self, data, seats=None):
        seats = seats or self.live()
        return seats[data.draw(st.integers(0, len(seats) - 1))]

    def guard(self, seat, fn, *args):
        """Runs a session call; a dead socket ends the session, as the bridge loop would."""
        self.acting = seat
        try:
            fn(*args)
        except ConnectionError:
            seat.gone = True
            self.last_claim = None
            return
        finally:
            self.acting = None
        for msg in seat.sock.take():
            if msg.get("cmd") == "Get":
                seat.inbox.append([{"cmd": "Retrieved", "keys": {
                    k: list(self.room.hints[seat.world]) for k in msg["keys"]}}, None])
            elif msg.get("cmd") == "SetNotify":
                seat.subscribed = True

    def tell(self, w, msgs, skip=None):
        for seat in self.live():
            if seat.world == w and seat is not skip:
                seat.inbox += [[m, None] for m in msgs if m["cmd"] != "SetReply" or seat.subscribed]

    def buy(self, w, slot):
        if APHints.request.__wrapped__(GID, w, slot):
            self.buys[(w, slot)] += 1

    def service(self, seat):
        """One bridge loop second for one session."""
        self.clock.now += ap_bridge.HINT_SERVICE_SECS
        self.guard(seat, seat.session._service_hints, seat.sock)

    def deliver(self, seat, n):
        while n and seat.inbox and not seat.gone:
            n -= 1
            msg, answers = seat.inbox.pop(0)
            if msg.get("cmd") == "RoomUpdate" and "hint_points" in msg:
                seat.points = msg["hint_points"]
            if answers is not None:
                answers["answered"] = True
            if msg.get("type") == "Hint":
                for say in seat.says:
                    if say is not answers and not say["answered"] and say["item"] == msg["item"]["item"]:
                        say["outrun"] = True
            self.guard(seat, seat.session._dispatch, msg, seat.sock)

    def answer(self, data):
        seat, say = self.queue.pop(0)
        held = len(self.room.hints[seat.world])
        to_all, to_me = self.room.say(seat.world, say["text"], lambda n: data.draw(st.integers(0, n - 1)))
        say["refused"] = len(self.room.hints[seat.world]) == held and any(
            "afford" in result_text(m).lower() for m in to_me)
        self.tell(seat.world, to_all, skip=seat)
        if seat.gone:
            return
        batch = [[m, None] for m in to_all if m["cmd"] != "SetReply" or seat.subscribed] + [[m, None] for m in to_me]
        answer = next((b for b in batch if b[0].get("type") == "Hint" and b[0]["item"]["item"] == say["item"]), None)
        answer = answer or next((b for b in batch if "afford" in result_text(b[0]).lower()), None)
        if answer is not None:
            answer[1] = say
        seat.inbox += batch

    @precondition(lambda self: len(self.live()) < 3)
    @rule(data=st.data())
    def a_session_connects(self, data):
        w = data.draw(st.integers(1, self.room.k))
        if sum(1 for s in self.live() if s.world == w) < 2:
            self.connect(w)

    @rule(data=st.data())
    def the_client_unlocks_hints(self, data):
        w = data.draw(st.integers(1, self.room.k))
        self.wanted[w] |= data.draw(st.sets(st.sampled_from([s for s, _ in self.exports[w]]), min_size=1))

    @precondition(lambda self: self.live())
    @rule(data=st.data())
    def a_client_tick_reaches_a_session(self, data):
        seat = self.pick(data)
        seat.session.hint_box.add(self.wanted[seat.world])

    @rule(data=st.data())
    def someone_presses_buy(self, data):
        offered = sorted((w, slot) for w in self.exports for slot, e in self.rows.entries(GID, w).items()
                         if e.get("s") == HINT_OFFERED)
        if offered:
            self.buy(*data.draw(st.sampled_from(offered)))

    @rule(data=st.data())
    def a_stale_page_presses_buy(self, data):
        w = data.draw(st.integers(1, self.room.k))
        self.buy(w, data.draw(st.sampled_from(sorted(self.maps.hint_keys[w]))))

    @precondition(lambda self: self.live())
    @rule(data=st.data())
    def a_session_services_its_hints(self, data):
        self.service(self.pick(data))

    @precondition(lambda self: any(s.inbox for s in self.live()))
    @rule(data=st.data(), n=st.integers(1, 4))
    def the_room_reaches_a_session(self, data, n):
        self.deliver(self.pick(data, [s for s in self.live() if s.inbox]), n)

    @precondition(lambda self: self.queue)
    @rule(data=st.data())
    def the_room_answers_a_say(self, data):
        self.answer(data)

    @precondition(lambda self: self.live())
    @rule(data=st.data(), seconds=st.sampled_from([1, 3, 6, 15, 40]))
    def everything_runs_for_a_while(self, data, seconds):
        for _ in range(seconds):
            while self.queue:
                self.answer(data)
            for seat in self.live():
                self.deliver(seat, len(seat.inbox))
            self.clock.now += ap_bridge.HINT_SERVICE_SECS
            for seat in self.live():
                seat.session.hint_box.add(self.wanted[seat.world])
                self.guard(seat, seat.session._service_hints, seat.sock)

    @rule(data=st.data())
    def someone_else_hints_an_item(self, data):
        w = data.draw(st.integers(1, self.room.k))
        open_copies = sorted((item, loc) for (v, item) in list(self.room.copies) if v == w
                             for loc in self.room.unhinted(w, item))
        if open_copies:
            self.tell(w, self.room.hint_from_elsewhere(w, *data.draw(st.sampled_from(open_copies))))

    @rule(data=st.data(), n=st.integers(1, 5))
    def the_player_checks_locations(self, data, n):
        w = data.draw(st.integers(1, self.room.k))
        self.room.points[w] += n
        self.tell(w, [{"cmd": "RoomUpdate", "hint_points": self.room.points[w]}])

    @rule(dt=st.sampled_from([0.5, 1.5, 6.0, 21.0, 31.0, 300.0, ap_bridge.HINT_CLAIM_TTL + 1]))
    def time_passes(self, dt):
        self.clock.now += dt

    @precondition(lambda self: self.live())
    @rule(data=st.data())
    def a_session_dies_at_its_next_send(self, data):
        self.pick(data).sock.dead = True

    @precondition(lambda self: self.live())
    @rule(data=st.data())
    def a_session_goes_away(self, data):
        self.pick(data).gone = True

    def stale(self, say):
        state, stamp, stale_ok = say["claim"] or (None, 0, False)
        return state == HINT_PENDING and stale_ok and say["t"] - stamp > ap_bridge.HINT_CLAIM_TTL

    @invariant()
    def a_slot_is_bought_once_but_for_the_stale_reclaim(self):
        bought = set()
        for say in getattr(self, "says", []):
            key = (say["world"], say["slot"])
            assert (key not in bought or self.stale(say) or bought_again_after_a_pending_claim_was_overwritten(say)), \
                "a second !hint for world %s slot %s: %s" % (key + (say,))
            if not say["refused"]:
                bought.add(key)

    @invariant()
    def no_say_while_points_fall_short_of_the_cost(self):
        for say in getattr(self, "says", []):
            assert say["points"] >= say["cost"], say

    @invariant()
    def no_say_while_another_is_in_flight(self):
        for say in getattr(self, "says", []):
            assert not say["busy"], say

    @invariant()
    def every_say_follows_a_buy(self):
        says = Counter((s["world"], s["slot"]) for s in getattr(self, "says", []) if not self.stale(s))
        for key, n in says.items():
            assert n <= self.buys[key], "world %s slot %s: %s says, %s buys" % (key + (n, self.buys[key]))

    @invariant()
    def only_reveals_are_ever_bought(self):
        for say in getattr(self, "says", []):
            assert say["slot"] in self.maps.hint_keys[say["world"]], say

    @invariant()
    def a_resolved_hint_stays_resolved(self):
        if not hasattr(self, "rows"):
            return
        now = {(w, slot) for w in self.exports for slot, e in self.rows.entries(GID, w).items()
               if e.get("s") == HINT_RESOLVED}
        assert self.resolved <= now, self.resolved - now
        self.resolved |= now


class HintMarketMachine(unittest.TestCase):
    def test_a_hint_is_bought_once_only_when_affordable_and_one_at_a_time(self):
        run_machine(HintMarket, 150, steps=50)

    @deep_only
    def test_a_hint_is_bought_once_over_long_histories(self):
        run_machine(HintMarket, 200, steps=120)


class HintAnswers(unittest.TestCase):
    def setUp(self):
        for cm in (quiet(), ndb_context()):
            cm.__enter__()
            self.addCleanup(cm.__exit__, None, None, None)
        self.addCleanup(ap_bridge._notice_at.clear)
        self.addCleanup(ap_bridge._dp_cache.clear)
        self.reroute = Reroute()
        self.addCleanup(self.reroute.restore)
        self.clock = Clock()
        HintRows().install(self.reroute)
        self.reroute.bridge(_load_hints=ap_bridge._load_hints, _claim_hint=ap_bridge._claim_hint.__wrapped__,
                            _persist_hint=ap_bridge._persist_hint.__wrapped__,
                            _persist_price=ap_bridge._persist_price.__wrapped__)
        for owner, name in ((ap_bridge, "monotonic"), (ap_bridge, "time"), (ap_models, "time")):
            self.reroute.set(owner, name, self.clock.monotonic if name == "monotonic" else self.clock)
        ap_bridge._dp_put(FOREIGN, "clsum", {}, {"Chest %s" % j: 880000 + j for j in range(4)})

    def connected(self, room, exports):
        """A session on world 1 that has its room's hint list; nothing asked yet."""
        session = session_for(1, 1, hint_maps(exports), hint_box=ap_bridge._HintBox())
        sock = Sock(hello(1, 1, missing=room.locations(1), hint_cost=room.prices[1][0], hint_points=room.points[1]))
        session._handshake(sock)
        session._dispatch({"cmd": "Retrieved", "keys": {room.key(1): []}}, sock)
        return session, sock

    def test_a_purchase_lost_in_a_crash_is_bought_again_only_after_the_claim_ttl(self):
        exports = {1: [(1, ("EV", "0")), (2, ("SK", "4"))]}
        room = HintRoom(exports, {1: (10, 40, 20)})
        (twin, twin_sock), (crashing, crashing_sock) = self.connected(room, exports), self.connected(room, exports)

        def service(session, sock, buy=None):
            if buy is not None:
                APHints.request.__wrapped__(GID, 1, buy)
                self.clock.now += ap_bridge.HINT_POLL_SECS + 1
            session.hint_box.add({1, 2})
            session._service_hints(sock)
        service(twin, twin_sock)
        service(crashing, crashing_sock)
        service(twin, twin_sock, buy=2)
        service(twin, twin_sock, buy=1)
        crashing_sock.dead = True
        with self.assertRaises(ConnectionError):
            service(crashing, crashing_sock)
        self.assertEqual(APHints.load(GID, 1)[1]["s"], HINT_PENDING)
        for msg in room.say(1, "!hint Stomp", lambda n: 0)[0]:
            twin._dispatch(msg, twin_sock)
        says = lambda: [m["text"] for m in twin_sock.sent if m.get("cmd") == "Say"]
        self.clock.now += ap_bridge.HINT_RETRY_SECS + 1
        service(twin, twin_sock)
        self.assertEqual(says(), ["!hint Stomp"])
        self.clock.now += ap_bridge.HINT_CLAIM_TTL
        service(twin, twin_sock)
        self.assertEqual(says(), ["!hint Stomp", "!hint Water Vein"])

    @unittest.expectedFailure
    def test_a_session_waits_for_its_own_answer_before_buying_again(self):
        exports = {1: [(1, ("EV", "0")), (2, ("SK", "4"))]}
        room = HintRoom(exports, {1: (10, 40, 100)})
        APHints.store(GID, 1, {1: APHints.entry("q"), 2: APHints.entry("q")})
        session, sock = self.connected(room, exports)
        session.hint_box.add({1, 2})
        session._service_hints(sock)
        water_vein = ap_bridge.AP_ID_BY_ITEM_KEY[("EV", "0")]
        for msg in room.hint_from_elsewhere(1, water_vein, room.copies[(1, water_vein)][0]):
            session._dispatch(msg, sock)
        says = [m["text"] for m in sock.sent if m.get("cmd") == "Say"]
        self.assertEqual(says, ["!hint Water Vein"])

    @unittest.expectedFailure
    def test_a_twin_never_puts_a_pending_purchase_back_on_sale(self):
        exports = {1: [(1, ("EV", "0"))]}
        room = HintRoom(exports, {1: (10, 40, 20)})
        (first, first_sock), (twin, twin_sock) = self.connected(room, exports), self.connected(room, exports)
        first.hint_box.add({1})
        first._service_hints(first_sock)
        APHints.request.__wrapped__(GID, 1, 1)
        self.clock.now += ap_bridge.HINT_POLL_SECS + 1
        first._service_hints(first_sock)
        self.assertEqual(APHints.load(GID, 1)[1]["s"], HINT_PENDING)
        twin.hint_box.add({1})
        twin._service_hints(twin_sock)
        self.assertEqual(APHints.load(GID, 1)[1]["s"], HINT_PENDING)


# --- logic parity with the tracker ---

class LogicParity(unittest.TestCase):
    @settings(max_examples=examples(100))
    @given(reach_configs(), st.data())
    def test_the_room_never_reaches_what_the_tracker_cannot(self, config, data):
        assume(not starts_in_grotto(config))
        logic = ApLogic(config.cfg)
        for _ in range(3):
            inventory = data.draw(inventories(config))
            ap_only = logic.reach(ap_have(inventory)) - server_reach(config, inventory)
            self.assertEqual(ap_only, set(), "%r holding %s" % (config, dict(inventory)))

    @unittest.expectedFailure
    def test_a_grotto_run_starts_on_the_teleporter(self):
        config = ReachConfig("Grotto", ["casual-core"], [], "Clues", DOORS)
        inventory = Counter({("SK", "5"): 1})
        self.assertEqual(ApLogic(config.cfg).reach(ap_have(inventory)) - server_reach(config, inventory), set())


if __name__ == "__main__":
    unittest.main()
