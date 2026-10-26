"""Harness for test/ap_props.py: the room's yaml loader, synthetic seeds, scripted rooms and both reach walks."""
import contextlib
import json
import logging
import os
from collections import Counter, defaultdict

import google.auth.credentials
import yaml
from google.cloud import ndb
from hypothesis import strategies as st

from ap_models import APHints
from archipelago import ap_bridge
from archipelago.convert import (DATA_DIR, EXPORTABLE_CATEGORIES, ITEM_BY_CODE_ID, SPAWN_REGIONS,
                                 ap_convert, ap_variations, keystone_tier_list, match_key,
                                 oride_module, tier_map_from_list)
from archipelago.yaml_emit import ITEM_NAMES, LOC_NAMES, make_config
from enums import KeyMode, LogicPath
from models import Player
from reachable import Map, PlayerState
from seedbuilder import enemyroll
from seedbuilder.generator import warp_targets2
from util import is_mw_manifest_loc

shared = oride_module("shared")
rules = oride_module("rules")

with open(os.path.join(DATA_DIR, "items.json")) as _f:
    _ITEMS = json.load(_f)
with open(os.path.join(DATA_DIR, "graph.json")) as _f:
    GRAPH = json.load(_f)["homes"]


# --- the room's yaml loader ---

class RoomLoader(getattr(yaml, "CSafeLoader", yaml.SafeLoader)):
    """Safe loading that refuses a mapping key it has already seen, as the room's Generate does."""


def _unique_keys(loader, node, deep=False):
    seen = set()
    for key_node, _ in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in seen:
            raise yaml.constructor.ConstructorError(
                None, None, "repeated key %r" % (key,), key_node.start_mark)
        seen.add(key)
    return loader.construct_mapping(node, deep=deep)


RoomLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _unique_keys)


def room_yaml(text):
    return yaml.load(text, Loader=RoomLoader)


def normal(value):
    """The value as plain JSON types, which is all a yaml load can hand back."""
    return json.loads(json.dumps(value))


# --- yaml configs ---

ITEM_LIST = sorted(ITEM_NAMES.values())
LOC_LIST = sorted(LOC_NAMES.values())
ROLL_TABLE = enemyroll.table()
PATHSETS = [lp.value for lp in LogicPath]
KEY_MODES = [km.value for km in KeyMode]


@st.composite
def enemy_rolls(draw):
    n = len(ROLL_TABLE["placements"])
    rolls = [None] * n
    for i in draw(st.lists(st.integers(0, n - 1), max_size=12, unique=True)):
        rolls[i] = draw(st.integers(0, len(ROLL_TABLE["variants"]) - 1))
    return rolls


@st.composite
def yaml_configs(draw):
    """make_config over real item and location names, every logic path, key mode and variation."""
    exported = draw(st.dictionaries(st.sampled_from(ITEM_LIST), st.integers(1, 5), max_size=20))
    reserved = draw(st.lists(st.sampled_from(LOC_LIST), unique=True, max_size=30))
    local = draw(st.dictionaries(st.sampled_from(LOC_LIST), st.sampled_from(ITEM_LIST), max_size=20))
    paths = draw(st.lists(st.sampled_from(PATHSETS), min_size=1, unique=True))
    variations = ap_variations(draw(st.lists(st.sampled_from(
        ["ClosedDungeons", "OpenWorld", "Keysanity", "EnemyRando"]), unique=True)))
    tiers = draw(st.none() | st.lists(st.integers(0, 40), min_size=12, max_size=12))
    rolls = draw(st.none() | enemy_rolls()) if variations.get("enemy_rando") else None
    return make_config(exported, reserved, local, paths,
                       key_mode=draw(st.sampled_from(KEY_MODES)),
                       spawn=draw(st.sampled_from(sorted(SPAWN_REGIONS.values()))),
                       variations=variations, params_id=draw(st.integers(0, 2**62)),
                       world=draw(st.integers(1, 8)), death_link=draw(st.booleans()),
                       key_tiers=tiers, enemy_rolls=rolls)


def elemental_arena_rolls():
    """Enemy rolls that fill every miniboss room with Elementals, which spirit flame can't kill."""
    rolls = [None] * len(ROLL_TABLE["placements"])
    elementals = next(i for i, v in enumerate(ROLL_TABLE["variants"]) if v["kind"] == "Elementals")
    for scene in enemyroll.ARENA_EDGES:
        spot = next((i for i, p in enumerate(ROLL_TABLE["placements"])
                     if p["arena"] and p["scene"] == scene), None)
        if spot is not None:
            rolls[spot] = elementals
    return rolls


slot_name_lists = st.lists(st.text(max_size=24), min_size=1, max_size=6)

_PRINTABLE = st.text(st.characters(min_codepoint=0x20, max_codepoint=0x7e), max_size=12)


def emitter_values():
    """Every value shape make_config hands _emit: scalars, string-keyed dicts, lists of scalars, dicts or lists."""
    scalars = st.booleans() | st.integers(-2**40, 2**40) | _PRINTABLE

    def grow(kids):
        items = (scalars | st.dictionaries(_PRINTABLE, kids, min_size=1, max_size=3)
                 | st.lists(scalars, min_size=1, max_size=3))
        return st.lists(items, max_size=4) | st.dictionaries(_PRINTABLE, kids, max_size=4)
    return st.recursive(scalars, grow, max_leaves=12)


# --- synthetic K-world multiworld seeds, the shape ap_convert reads ---

FLAGS = "Sync0.0,test|mode=Multiworld"
ZONES = ["Glades", "Grove", "Swamp", "Grotto", "Ginso", "Valley", "Misty", "Forlorn", "Sorrow", "Horu"]
COORDS = sorted(LOC_NAMES)
WARPS = ["Warp to %s,%s,%s,%s" % (name, x, y, node)
         for group in warp_targets2 for name, x, y, _area, node, _cost in group]
DP_ITEMS = sorted({(i["code"], i["id"]) for i in _ITEMS if i["code"] not in ("EX", "TW")})
FILLER = [("NO", "1"), ("WT", "#Abandoned Nest#\\nLooks like birds lived here."),
          ("RB", "81"), ("TW", "Warp to Nowhere In Particular,1,2,Node")]
MANY = [("HC", "1"), ("EC", "1"), ("AC", "1"), ("KS", "1"), ("MS", "1"), ("RB", "17"), ("RB", "300"),
        ("EX", "100"), ("EX", "200")]


def pickups():
    return st.one_of(
        st.sampled_from(DP_ITEMS),
        st.sampled_from(MANY),
        st.tuples(st.just("EX"), st.integers(1, 1500).map(str)),
        st.tuples(st.just("TW"), st.sampled_from(WARPS)),
        st.sampled_from(FILLER))


@st.composite
def mw_games(draw, max_worlds=4, max_locs=24):
    """-> (texts, categories, placements); a placement is (host world, loc, owner world, code, id, zone)."""
    k = draw(st.integers(1, max_worlds))
    categories = draw(st.lists(st.sampled_from(EXPORTABLE_CATEGORIES), unique=True, min_size=1))
    stones = "stones" in categories
    placements = []
    for v in range(1, k + 1):
        for loc in draw(st.lists(st.sampled_from(COORDS), unique=True, max_size=max_locs)):
            code, pid = draw(pickups())
            owner = draw(st.integers(1, k)) if k > 1 and draw(st.booleans()) else v
            if owner != v and code == "KS" and not stones:
                owner = v
            placements.append((v, loc, owner, code, pid, draw(st.sampled_from(ZONES))))
    draw(st.randoms()).shuffle(placements)
    lines = {v: [] for v in range(1, k + 1)}
    next_slot = Counter()
    for v, loc, owner, code, pid, zone in placements:
        if owner == v:
            lines[v].append("%s|%s|%s|%s" % (loc, code, pid, zone))
            continue
        slot = next_slot[owner]
        next_slot[owner] += 1
        lines[v].append("%s|MW|%s,%s,%s,%s|%s" % (loc, owner, slot, code, pid, zone))
        lines[owner].append("%s|MW|%s,,%s,%s|%s" % (-(slot + 2), v, code, pid, zone))
    texts = [FLAGS + "\n" + "".join(l + "\n" for l in lines[v]) for v in range(1, k + 1)]
    return texts, categories, placements


def parse(text):
    """Seed text -> [(loc, code, id, zone)], flag line skipped."""
    return [tuple(line.split("|")) for line in text.split("\n")[1:] if line]


def manifest(rows):
    """{manifest slot: MW id} of one world's rows."""
    return {-int(loc) - 2: pid for loc, code, pid, _ in rows
            if code == "MW" and is_mw_manifest_loc(int(loc))}


def item_census(texts):
    """{(owner, match_key)} multiset over a game's texts, shadow exports counted for their owner."""
    k = len(texts)
    seeds = [parse(t) for t in texts]
    manifests = [manifest(rows) for rows in seeds]
    out = Counter()
    for v, rows in enumerate(seeds, start=1):
        for loc, code, pid, _ in rows:
            if code != "MW":
                out[(v, match_key(code, pid))] += 1
            elif is_mw_manifest_loc(int(loc)):
                finder, _h, icode, iid = pid.split(",", 3)
                if int(finder) > k:
                    out[(v, match_key(icode, iid))] += 1
            else:
                owner, slot, _ = pid.split(",", 2)
                if int(owner) <= k:
                    _f, _h, icode, iid = manifests[int(owner) - 1][int(slot)].split(",", 3)
                    out[(int(owner), match_key(icode, iid))] += 1
    return out


class FakeParams(object):
    """The two params reads maps_from_params makes, over converted seed texts."""

    def __init__(self, texts):
        self.players = len(texts)
        self.ap_mode = True
        self._seed = {w: parse(t) for w, t in enumerate(texts, start=1)}

    def get_seed_data(self, player=1):
        return self._seed[int(player)]


# --- a scripted room socket and the bridge's datastore touchpoints ---

GID = 1301
GAME = ap_bridge.AP_GAME_NAME
FOREIGN = "Clique"


class Sock(object):
    """Scripted transport: receive() pops frames, send() keeps every message; an empty script is a dead socket."""

    def __init__(self, frames=(), on_send=None):
        self.script = list(frames)
        self.sent = []
        self.on_send = on_send
        self.dead = False

    def receive(self, timeout=None):
        if not self.script:
            raise ConnectionError("script done")
        return json.dumps(self.script.pop(0))

    def send(self, data):
        if self.dead:
            raise ConnectionError("socket died")
        msgs = json.loads(data)
        if self.on_send is not None:
            self.on_send(msgs)
        self.sent.extend(msgs)

    def take(self):
        out, self.sent = self.sent, []
        return out


class SlotHolder(object):
    """Just the slot and extra-item state of a real Player, driven by Player's own methods."""

    def __init__(self):
        self.slot_bflds = None
        self.extra_items = None

    def slot_check(self, slot):
        return Player.slot_check(self, slot)

    def mark(self, slot):
        return Player.mark_slot(self, slot, delay_put=True)

    def add_extras(self, entries):
        return Player.add_extra_items(self, entries)

    def put(self):
        pass

    def marked(self):
        return {32 * i + b for i, word in enumerate(self.slot_bflds or []) for b in range(32) if word >> b & 1}

    def extra_keys(self):
        """Datapackage keys of the slotless items held, a warp named by its destination."""
        return Counter((e[1], e[2].split(",")[0] if e[1] == "TW" else e[2]) for e in self.extra_items or [])


TOUCHPOINTS = ("_shadow_slots", "_apply_grants", "_apply_extras", "_persist_recv", "_persist_status",
               "_goal_worlds", "_persist_names", "_load_hints", "_persist_drop", "_notify_drop",
               "_persist_promises", "_load_scout_row", "_scout_rows", "_claim_hint", "_persist_hint",
               "_apply_hint_text", "_hint_notice", "_persist_price", "_persist_name_counts")

_MISSING = object()


@contextlib.contextmanager
def quiet():
    """No bridge log lines: a machine run makes thousands of deliberate degraded fills and refusals."""
    before = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        yield
    finally:
        logging.disable(before)


class Reroute(object):
    """Replaces attributes on modules and classes, and puts every one back."""

    def __init__(self):
        self.saved = []

    def set(self, owner, name, value):
        self.saved.append((owner, name, vars(owner).get(name, _MISSING)))
        setattr(owner, name, value)

    def bridge(self, **fns):
        """Every datastore touchpoint of ap_bridge inert, then the named ones replaced."""
        inert = {"_shadow_slots": lambda gid, world, maps: set(),
                 "_apply_grants": lambda gid, world, slots, senders=None: 0,
                 "_apply_extras": lambda gid, world, entries: [],
                 "_persist_recv": lambda gid, world, count: None,
                 "_persist_status": lambda gid, status, error: None,
                 "_goal_worlds": lambda gid: [],
                 "_persist_names": lambda gid, world, total, names, ap_slot=None: None,
                 "_load_hints": lambda gid, world: {},
                 "_persist_drop": lambda gid, world, entry: True,
                 "_notify_drop": lambda gid, world, text: None,
                 "_persist_promises": lambda gid, world, blob: None,
                 "_load_scout_row": lambda gid, world: ({}, None),
                 "_scout_rows": lambda gid, worlds: {},
                 "_claim_hint": lambda *a, **kw: False,
                 "_persist_hint": lambda *a, **kw: None,
                 "_apply_hint_text": lambda *a, **kw: None,
                 "_hint_notice": lambda *a, **kw: None,
                 "_persist_price": lambda *a, **kw: None,
                 "_persist_name_counts": lambda *a, **kw: None}
        inert.update(fns)
        for name in TOUCHPOINTS:
            self.set(ap_bridge, name, inert[name])

    def restore(self):
        while self.saved:
            owner, name, value = self.saved.pop()
            if value is _MISSING:
                delattr(owner, name)
            else:
                setattr(owner, name, value)


def slot_info(k):
    """Connected.slot_info for K Ori worlds on slots 1..K and one foreign game on K+1."""
    info = {str(w): {"name": "Ori%s" % w, "game": GAME} for w in range(1, k + 1)}
    info[str(k + 1)] = {"name": "Questy", "game": FOREIGN}
    return info


def data_package():
    ori = {n: i for i, n in ap_bridge.ITEM_NAME_BY_AP_ID.items()}
    return {"cmd": "DataPackage", "data": {"games": {
        GAME: {"checksum": "orisum", "item_name_to_id": ori, "location_name_to_id": {}},
        FOREIGN: {"checksum": "clsum", "item_name_to_id": {"Shield %s" % j: 990000 + j for j in range(9)},
                  "location_name_to_id": {"Chest %s" % j: 880000 + j for j in range(64)}}}}}


def session_for(k, w, maps, **kw):
    return ap_bridge.ApSession(GID, w, maps, "Ori%s" % w, None,
                               game_slots=["Ori%s" % v for v in range(1, k + 1)], **kw)


def hello(w, k, checked=(), missing=(), items=None, hint_cost=0, hint_points=None):
    """RoomInfo, then Connected (plus the connect backlog when items is given), as two frames."""
    connected = {"cmd": "Connected", "team": 0, "slot": w, "checked_locations": list(checked),
                 "missing_locations": list(missing), "slot_info": slot_info(k)}
    if hint_points is not None:
        connected["hint_points"] = hint_points
    second = [connected]
    if items is not None:
        second.append({"cmd": "ReceivedItems", "index": 0, "items": items})
    return [[{"cmd": "RoomInfo", "hint_cost": hint_cost,
              "datapackage_checksums": {GAME: "orisum", FOREIGN: "clsum"}}], second]


# --- a room that fills a converted game ---

EX100 = ap_bridge.AP_ID_BY_ITEM_KEY[("EX", "100")]


class FilledRoom(object):
    """Every exported item on one reserved location, plus a foreign game's pairs; checks happen in `order`."""

    def __init__(self, k, maps, placed, start, order):
        self.k, self.maps, self.placed, self.start, self.order = k, maps, placed, start, order
        self.checked = []
        self.export_key = {(p, s): key for p in range(1, k + 1)
                           for key, slots in maps.grant_slots[p].items() for s in slots}

    def stream(self, w, everything=False):
        """World w's ReceivedItems: its start inventory, then its items at checked (or all) locations."""
        out = list(self.start[w])
        for finder, loc in (self.order if everything else self.checked):
            owner, ap_item = self.placed[(finder, loc)]
            if owner == w:
                out.append({"item": ap_item, "location": loc, "player": finder, "flags": 0})
        return out

    @staticmethod
    def keys(items):
        return Counter(ap_bridge.ITEM_KEY_BY_AP_ID.get(i["item"]) for i in items)

    def own_locs(self, w):
        return sorted(loc for (v, loc) in self.placed if v == w)

    def location_info(self, w, locs):
        return {"cmd": "LocationInfo", "locations": [
            {"item": self.placed[(w, loc)][1], "location": loc, "player": self.placed[(w, loc)][0], "flags": 0}
            for loc in locs]}

    def hello(self, w):
        own = self.own_locs(w)
        checked = [l for (v, l) in self.checked if v == w]
        return hello(w, self.k, checked=checked, missing=[l for l in own if l not in checked],
                     items=self.stream(w))


def fill_room(game, data, filler=False):
    """Converts and fills a synthetic game; filler moves up to two items to start, 100 experience in their place."""
    texts, cats, _ = game
    new, info = ap_convert(list(texts), cats)
    k = len(texts)
    maps = ap_bridge.maps_from_params(FakeParams(new))
    items = [(p, ap_bridge.AP_ID_BY_ITEM_KEY[match_key(c, i)])
             for p in range(1, k + 1) for c, i, _ in info["exported"][p]]
    locs = [(v, ap_bridge.AP_LOC_BY_COORD[loc]) for v in range(1, k + 1) for loc, _ in info["reserved"][v]]
    n_foreign = data.draw(st.integers(0, min(len(items), len(locs), 4)))
    items += [(k + 1, 990000 + j) for j in range(n_foreign)]
    locs += [(k + 1, 880000 + j) for j in range(n_foreign)]
    rnd = data.draw(st.randoms(use_true_random=False))
    rnd.shuffle(items)
    placed = dict(zip(locs, items))
    start = {w: [] for w in range(1, k + 1)}
    if filler and locs:
        for loc in data.draw(st.lists(st.sampled_from(locs), unique=True, max_size=2)):
            owner, ap_item = placed[loc]
            if owner <= k:
                start[owner].append({"item": ap_item, "location": -2, "player": 0, "flags": 0})
                placed[loc] = (owner, EX100)
    order = list(locs)
    rnd.shuffle(order)
    return FilledRoom(k, maps, placed, start, order)


# --- the clock the hint market reads ---

class Clock(object):
    """One fake time for ap_bridge.monotonic, ap_bridge.time and ap_models.time."""

    def __init__(self, start=1.8e9):
        self.now = float(start)

    def monotonic(self):
        return self.now

    def time(self):
        return self.now


class HintRows(object):
    """APHints rows in a dict, so the real compare-and-set and persist code runs without a datastore."""

    def __init__(self):
        self.rows = {}

    def install(self, reroute):
        reroute.set(APHints, "put", lambda row, *a, **k: self.rows.__setitem__(row.key.id(), row) or row.key)
        reroute.set(APHints, "get_by_id", staticmethod(lambda rid: self.rows.get(rid)))

    def entries(self, gid, world):
        return APHints.unpack(self.rows.get(APHints.key_id(gid, world)))


_ndb = []


def ndb_context():
    """A local ndb context: enough to build entities, never a datastore call."""
    if not _ndb:
        _ndb.append(ndb.Client(project="unit-test", credentials=google.auth.credentials.AnonymousCredentials()))
    return _ndb[0].context()


# --- a room's hint market ---

HINT_KEYS = sorted(ap_bridge.HINTABLE_KEYS)
ITEM_ID_BY_NAME = {name: ap_id for ap_id, name in ap_bridge.ITEM_NAME_BY_AP_ID.items()}


@st.composite
def hint_markets(draw):
    """-> ({world: [(manifest slot, key)]}, {world: (hint cost percent, location count, points)})."""
    k = draw(st.integers(1, 2))
    exports, prices = {}, {}
    for w in range(1, k + 1):
        slots = [(0, ("EX", "50"))]
        for key in draw(st.lists(st.sampled_from(HINT_KEYS), min_size=1, max_size=3, unique=True)):
            for _ in range(draw(st.integers(1, 2))):
                slots.append((len(slots), key))
        exports[w] = slots
        pct, n = draw(st.sampled_from([0, 10, 25])), draw(st.sampled_from([4, 10, 40]))
        cost = max(1, int(pct * 0.01 * n)) if pct else 0
        prices[w] = (pct, n, draw(st.integers(0, 3 * cost + 1)))
    return exports, prices


def hint_maps(exports):
    grants = {w: {} for w in exports}
    reveals = {w: {} for w in exports}
    for w, slots in exports.items():
        for slot, key in slots:
            grants[w].setdefault(key, []).append(slot)
            if key in ap_bridge.HINTABLE_KEYS:
                reveals[w][slot] = key
    return ap_bridge.GameMaps(len(exports), {w: {} for w in exports}, grants,
                              zones={w: {} for w in exports}, hint_keys=reveals)


def command_result(text):
    return {"cmd": "PrintJSON", "type": "CommandResult", "data": [{"text": text}]}


class HintRoom(object):
    """AP 0.6.7's hint bookkeeping for K Ori worlds whose copies all sit in one foreign game."""

    def __init__(self, exports, prices):
        self.k = len(exports)
        self.prices = prices
        self.points = {w: prices[w][2] for w in exports}
        self.copies = defaultdict(list)
        loc = 880000
        for w, slots in sorted(exports.items()):
            for _, key in slots:
                self.copies[(w, ap_bridge.AP_ID_BY_ITEM_KEY[key])].append(loc)
                loc += 1
        self.hints = {w: [] for w in exports}

    def cost(self, w):
        pct, n, _ = self.prices[w]
        return max(1, int(pct * 0.01 * n)) if pct else 0

    def locations(self, w):
        return list(range(600000 + 1000 * w, 600000 + 1000 * w + self.prices[w][1]))

    def key(self, w):
        return "_read_hints_0_%s" % w

    def hint(self, w, item, loc):
        return {"receiving_player": w, "finding_player": self.k + 1, "location": loc, "item": item,
                "found": False}

    @staticmethod
    def print_json(h):
        return {"cmd": "PrintJSON", "type": "Hint", "receiving": h["receiving_player"], "found": False,
                "item": {"item": h["item"], "location": h["location"], "player": h["finding_player"],
                         "flags": 1}}

    def unhinted(self, w, item):
        held = {h["location"] for h in self.hints[w] if h["item"] == item}
        return [loc for loc in self.copies[(w, item)] if loc not in held]

    def news(self, w, fresh):
        """What a new hint for world w sends every session on its slot: SetReply, RoomUpdate, then the hints."""
        return [{"cmd": "SetReply", "key": self.key(w), "value": list(self.hints[w])},
                {"cmd": "RoomUpdate", "hint_points": self.points[w]}] + [self.print_json(h) for h in fresh]

    def say(self, w, text, pick):
        """'!hint <name>' from world w -> (messages to every session on the slot, messages to the sayer)."""
        item = ITEM_ID_BY_NAME[text[len("!hint "):]]
        old = [h for h in self.hints[w] if h["item"] == item]
        new = self.unhinted(w, item)
        if not new:
            used = command_result("Hint was previously used, no points deducted.")
            return [self.print_json(h) for h in old], [used]
        cost = self.cost(w)
        can_pay = int(self.points[w] // cost > 0) if cost else 1000
        fresh = []
        while can_pay > 0 and new:
            fresh.append(self.hint(w, item, new.pop(pick(len(new)))))
            can_pay -= 1
            self.points[w] -= cost
        self.hints[w] += fresh
        to_all = (self.news(w, []) if fresh else []) + [self.print_json(h) for h in old + fresh]
        to_me = []
        if new and (old or fresh) and cost and self.points[w] // cost == 0:
            to_me.append(command_result("There may be more hintables, however, you cannot afford to pay for "
                                        "any more.  You have %s and need at least %s." % (self.points[w], cost)))
        elif new and (old or fresh):
            to_me.append(command_result("There may be more hintables, you can rerun the command to find more."))
        elif new:
            to_me.append(command_result("You can't afford the hint. You have %s points and need at least %s."
                                        % (self.points[w], cost)))
        return to_all, to_me

    def hint_from_elsewhere(self, w, item, loc):
        """Another client or the finder's game hints one of world w's copies."""
        h = self.hint(w, item, loc)
        self.hints[w].append(h)
        return self.news(w, [h])


class Seat(object):
    """One bridge session on a world's slot as the room sees it: an inbox, and the points it was last told."""

    def __init__(self, n, world, session, sock, points):
        self.n, self.world, self.session, self.sock, self.points = n, world, session, sock, points
        self.inbox = []
        self.says = []
        self.subscribed = False
        self.gone = False

    def __repr__(self):
        return "Seat(%s, world=%s)" % (self.n, self.world)


def result_text(msg):
    return "".join(p.get("text") or "" for p in msg.get("data") or []) if msg.get("type") == "CommandResult" else ""


# --- the reach walks ---

DOORS = [(h, t) for h, t, _ in shared.KEYSTONE_DOORS]
SKILLS = [("SK", s) for s in ("0", "2", "3", "4", "5", "8", "12", "14", "50", "51")]
EVENTS = [("EV", e) for e in ("0", "1", "2", "3", "4")]
TELEPORTERS = [("TP", t) for t in ("Grove", "Swamp", "Grotto", "Valley", "Forlorn", "Sorrow",
                                   "Ginso", "Horu", "Blackroot", "Glades")]
COUNTED = {"HC": 12, "EC": 15, "AC": 33, "KS": 40, "MS": 11}
SHARDS = [("RB", "17"), ("RB", "19"), ("RB", "21")]
BASE_HEALTH = 3
MS_BUMPS = {8: 9, 9: 11}


class ReachConfig(object):
    """One world's logic as both sides see it: the apworld's yaml blob and the tracker's modes."""

    def __init__(self, zone, paths, variations, key_mode, door_order):
        self.zone, self.paths, self.key_mode = zone, list(paths), key_mode
        self.variations = list(variations)
        vals = set(self.variations)
        self.tiers = keystone_tier_list(type("P", (), {
            "variations": self.variations, "ks_door_order": {"1": list(door_order)}})(), 1)
        self.cfg = make_config({}, [], {}, self.paths, key_mode=key_mode, spawn=SPAWN_REGIONS[zone],
                               variations=ap_variations(vals), key_tiers=self.tiers)
        self.modes = self.paths + (["CLOSED_DUNGEON"] if "ClosedDungeons" in vals else []) + (
            ["OPEN_WORLD"] if "OpenWorld" in vals else [])

    def __repr__(self):
        return "ReachConfig(%r, %r, %r, %r, tiers=%r)" % (
            self.zone, self.paths, self.variations, self.key_mode, self.tiers)

    def spawn_line(self):
        """The spawn-line grants the room never sees: the start's teleporter, and free key mode's dungeon keys."""
        out = Counter()
        if self.zone != "Glades":
            out[("TP", self.zone)] += 1
        if self.cfg["key_mode"] == "free":
            out.update({("EV", "0"): 1, ("EV", "2"): 1, ("EV", "4"): 1})
        return out


@st.composite
def reach_configs(draw):
    """Non-keysanity worlds with tiers, casual-core always on: the seeds the tracker models."""
    variations = draw(st.lists(st.sampled_from(["ClosedDungeons", "OpenWorld"]), unique=True))
    zones = [z for z in sorted(SPAWN_REGIONS)
             if not ("ClosedDungeons" in variations and z in ("Ginso", "Horu"))]
    zone = draw(st.sampled_from(zones))
    paths = ["casual-core"] + draw(st.lists(st.sampled_from(PATHSETS[1:]), unique=True, max_size=6))
    key_mode = draw(st.sampled_from(KEY_MODES))
    order = draw(st.permutations(DOORS))
    return ReachConfig(zone, paths, variations, key_mode, order)


@st.composite
def inventories(draw, config):
    """An item multiset the world could hold: shards at most five, no dungeon teleporter behind closed dungeons."""
    singles = [k for k in SKILLS + EVENTS + TELEPORTERS
               if not ("ClosedDungeons" in config.variations and k in (("TP", "Ginso"), ("TP", "Horu")))]
    picked = draw(st.sets(st.sampled_from(singles)))
    if draw(st.booleans()):
        picked = set(singles) - picked
    have = Counter({key: 1 for key in picked})
    for code, top in COUNTED.items():
        have[(code, "1")] = draw(st.integers(0, top))
    for key in SHARDS:
        have[key] = draw(st.integers(0, 5))
    return +have


def ap_have(inventory):
    """{AP item name: count} for a seed-line inventory, plus the cells every run starts with."""
    out = Counter()
    for key, n in inventory.items():
        out[ITEM_BY_CODE_ID[key]["name"]] += n
    out["Health Cell"] += BASE_HEALTH
    return out


def apworld_tiers(cfg):
    """The keystone tiers generate_early hands the rule compiler, or None under keysanity."""
    if cfg.get("variations", {}).get("keysanity"):
        return None
    kt = cfg.get("key_tiers")
    if kt:
        return {(h, t): v for (h, t, _), v in zip(shared.KEYSTONE_DOORS, kt) if v}
    return shared.keystone_door_tiers(cfg.get("variations", {}))


class ApLogic(object):
    """The apworld's compiled rules for one yaml blob, walked without Archipelago."""

    def __init__(self, cfg):
        compiler = rules.RuleCompiler(cfg, lambda msg: None, ks_tiers=apworld_tiers(cfg))
        killers = {(k["home"], k["target"]): k["kills"] for k in cfg.get("arena_killers", [])}
        self.spawn = cfg.get("spawn", "SunkenGladesRunaway")
        self.edges = defaultdict(list)
        self.pickups = defaultdict(list)
        self.pedestals = defaultdict(list)
        for home, conns in GRAPH.items():
            for target, conn in conns.items():
                paths = conn["paths"]
                if (home, target) in killers:
                    paths = shared.kill_paths(paths, killers[(home, target)])
                needs = [dict(n) for n in compiler.compile_paths(paths, edge=(home, target))]
                if conn["type"] == "conn":
                    if needs:
                        self.edges[home].append((target, needs))
                elif conn.get("item") == "MapStone":
                    self.pedestals[target].append((home, needs))
                else:
                    self.pickups[target].append((home, needs))

    @staticmethod
    def passes(needs, have):
        return any(all(have[item] >= n for item, n in need.items()) for need in needs)

    def reach(self, have):
        """Every region, pickup, usable pedestal and mapstone turn-in a CollectionState holding `have` reaches."""
        regions, todo = {self.spawn}, [self.spawn]
        while todo:
            for target, needs in self.edges[todo.pop()]:
                if target not in regions and self.passes(needs, have):
                    regions.add(target)
                    todo.append(target)

        def got(accesses):
            return any(home in regions and self.passes(needs, have) for home, needs in accesses)
        locations = {t for t, acc in self.pickups.items() if got(acc)}
        pedestals = {t for t, acc in self.pedestals.items() if got(acc)}
        turnins = {"MS%s" % n for n in range(1, 10)
                   if have["Mapstone"] >= MS_BUMPS.get(n, n) and len(pedestals) >= n}
        return regions | locations | pedestals | turnins


def server_reach(config, inventory):
    """Everything the tracker's engine reaches for this inventory plus the spawn line, as one name set."""
    held = inventory + config.spawn_line()
    state = PlayerState([(code, pid, n, False) for (code, pid), n in sorted(held.items())])
    return set(Map.get_reachable_areas(state, list(config.modes), config.zone, need_reached_with=False,
                                       ks_tiers=tier_map_from_list(config.tiers)))

