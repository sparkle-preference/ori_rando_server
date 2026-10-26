"""Netcode harness for the property suite: emulator requests, multiworld games, ticks and pause points."""
import itertools
import logging
import random
import threading
import unittest
import warnings
from unittest import mock

from google.cloud import ndb
from hypothesis import strategies as st

import netcode
import util
from cache import Cache
from enums import MultiplayerGameType, ShareType
from models import Game, Player
from seedbuilder.seedparams import MultiplayerOptions, Placement, SeedGenParams, Stuff
from test.ndb_base import EmulatorTestCase

COORDS = util.coords_in_order
VERSION = util.VERSION
ZONE = "Glades"
# spread over all eight seen words, few enough that worlds share coords
LOCATIONS = COORDS[::10]

CATEGORIES = ("Skills", "WorldEvents", "Teleporters", "Upgrades")
SKILLS = ("0", "2", "3", "4", "5", "8", "12", "14", "50", "51")
TELEPORTERS = ("Grove", "Swamp", "Grotto", "Valley", "Forlorn", "Sorrow", "Ginso", "Horu", "Blackroot")
EVENTS = ("0", "1", "2", "3", "4")
STACKERS = ("17", "19", "21", "28", "6")

_client = None
_gids = itertools.count(random.randrange(10**9, 2 * 10**9) * 10)


class QuietCase(unittest.TestCase):
    """Logging and ndb's deprecation warnings off for the class: netcode logs every request it serves."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._log_floor, cls._warning_filters = logging.root.manager.disable, list(warnings.filters)
        logging.disable(logging.CRITICAL)
        warnings.filterwarnings("ignore", category=DeprecationWarning, module=r"google\.cloud\.ndb")

    @classmethod
    def tearDownClass(cls):
        logging.disable(cls._log_floor)
        warnings.filters[:] = cls._warning_filters
        super().tearDownClass()


class EmulatedCase(QuietCase, EmulatorTestCase):
    """EmulatorTestCase's emulator and client, minus the per-test reset and context."""

    @classmethod
    def setUpClass(cls):
        global _client
        super().setUpClass()
        _client = cls.ndb_client
        # util reads the env var once at import and netcode copies it: patch the copy
        cls._archipelago = netcode.ARCHIPELAGO
        netcode.ARCHIPELAGO = False

    @classmethod
    def tearDownClass(cls):
        netcode.ARCHIPELAGO = cls._archipelago
        super().tearDownClass()

    def setUp(self):
        pass

    def tearDown(self):
        pass


def request(fn, *args, **kwargs):
    """One request in its own ndb context, as the wsgi middleware gives each."""
    with _client.context():
        return fn(*args, **kwargs)


def concurrent(fn, *args, **kwargs):
    """A request run to completion on its own thread, from inside another one."""
    box = {}

    def run():
        try:
            box["value"] = request(fn, *args, **kwargs)
        except BaseException as e:
            box["error"] = e
    thread = threading.Thread(target=run)
    thread.start()
    thread.join()
    if "error" in box:
        raise box["error"]
    return box.get("value")


def answer(fn, *args, **kwargs):
    """(status, body) as a client sees it: the handler's, or the adapter's 500 when it raises."""
    try:
        return request(fn, *args, **kwargs)
    except Exception:
        return 500, None


def fresh_gid():
    """A game id no earlier example used, so examples need no emulator reset."""
    return next(_gids)


def fresh_player(gid, pid):
    """The stored Player, past every cache."""
    return ndb.Key(Game, gid, Player, "%s.%s" % (gid, pid)).get(use_cache=False)


def roster(gid):
    """The game's seated player numbers, freshly read."""
    return sorted(Game.get_by_id(gid, use_cache=False).player_nums())


def words(coords):
    """The eight seen bitfields a client sends for these locations."""
    out = [0] * 8
    for c in coords:
        i = COORDS.index(c)
        out[i // 32] |= 1 << (i % 32)
    return out


def tick_payload(seen, version=VERSION):
    """A client's tick form with these locations both seen and held."""
    payload = {"version": version, "x": "1.0", "y": "2.0"}
    for i, word in enumerate(words(seen)):
        payload["seen_%s" % i] = payload["have_%s" % i] = str(word)
    return payload


def slots_of(field_words):
    """Slot numbers set in eight 32-bit words, read the way the client reads tick field 6."""
    return {w * 32 + b for w, word in enumerate(field_words or []) for b in range(32) if (int(word) >> b) & 1}


def pure_render(p, include_slots=True):
    """Player.output from the entity alone: no cached names read, nothing cached."""
    with mock.patch.object(Cache, "set_output", lambda *a: None), \
            mock.patch.object(Cache, "get_names", lambda *a: None), \
            mock.patch.object(Cache, "set_names", lambda *a: None):
        return p.output(include_slots=include_slots)


def fresh_render(gid, pid):
    """The tick body a fresh read of the player renders."""
    return pure_render(fresh_player(gid, pid))


def make_game(gid, worlds, shared, placements=None):
    """Store a multiworld game, every world seated, rolled as these placements if given; returns its params."""
    params = None
    if placements is not None:
        # the emulator's own ids restart on reset, and SeedGenParams caches by id process-wide
        params = SeedGenParams(id=gid, seed="props", players=worlds, placements=list(placements))
        params.sync = MultiplayerOptions(enabled=True, cloned=False)
        params.sync.mode = MultiplayerGameType.MULTIWORLD
        params.sync.shared = [ShareType(s) for s in shared]
    game = Game(id=gid, params=params.put() if params else None, players=[],
                str_mode=MultiplayerGameType.MULTIWORLD.value, str_shared=list(shared), has_history=False)
    for pid in range(1, worlds + 1):
        game.player(pid, delay_put=True)
    game.put()
    return params


def placements_of(rows):
    """Placements from (coords, world, code, id, owner) rows, in coords order."""
    by_coords = {}
    for coords, world, code, id, owner in rows:
        stuff = Stuff(code=code, id=id, player=str(world), owner=str(owner) if owner else None)
        by_coords.setdefault(coords, []).append(stuff)
    return [Placement(location=str(c), zone=ZONE, stuff=s) for c, s in sorted(by_coords.items())]


def seed_lines(params, world):
    """A world's location lines as its client holds them, manifests left out."""
    return {int(loc): (code, id) for loc, code, id, _ in params.get_seed_data(world)
            if not util.is_mw_manifest_loc(loc)}


@st.composite
def layouts(draw, multipickups=True):
    """(worlds, shared categories, rows) for a small multiworld seed; rows feed placements_of."""
    worlds = draw(st.integers(2, 3))
    shared = sorted(draw(st.lists(st.sampled_from(CATEGORIES), unique=True)))
    kinds = ["own", "mw", "skill", "teleporter", "event", "stacker", "bonus"]

    def piece(world, kind):
        other = st.sampled_from([o for o in range(1, worlds + 1) if o != world])
        if kind == "mw":
            return "EC", "1", draw(other)
        if kind == "skill":
            return "SK", draw(st.sampled_from(SKILLS)), None
        if kind == "teleporter":
            return "TP", draw(st.sampled_from(TELEPORTERS)), None
        if kind == "event":
            return "EV", draw(st.sampled_from(EVENTS)), None
        if kind == "stacker":
            return "RB", draw(st.sampled_from(STACKERS)), None
        if kind == "bonus":
            return "RB", "8", None
        return draw(st.sampled_from([("EC", "1"), ("EV", "5")])) + (None,)

    rows = []
    for world in range(1, worlds + 1):
        for coords in draw(st.lists(st.sampled_from(LOCATIONS), min_size=2, max_size=5, unique=True)):
            kind = draw(st.sampled_from(kinds + (["multi"] if multipickups else [])))
            if kind != "multi":
                rows.append((coords, world) + piece(world, kind))
                continue
            parts = []
            for part in draw(st.lists(st.sampled_from(["own", "mw", "skill", "stacker"]), min_size=2, max_size=3)):
                code, id, owner = piece(world, part)
                parts.append((code, "%s@%s" % (id, owner) if owner else id))
            rows.append((coords, world, "MU", util.compose_multi_value(parts), None))
    return worlds, shared, rows


class PausePoint(object):
    """Runs `fire` once, on the arming thread, when that thread's tick reaches `point`."""

    POINTS = ("before_arm", "after_arm", "after_game_read", "after_txn", "before_cache_write", "after_cache_write")

    def __init__(self, point, fire):
        self.point, self.fire, self.owner, self.fired = point, fire, threading.get_ident(), False

    def _hit(self, point):
        if point == self.point and not self.fired and threading.get_ident() == self.owner:
            self.fired = True
            self.fire()

    def __enter__(self):
        cache_cls = type(Cache)
        arm, write = cache_cls.__dict__["set_seen_checksum"], cache_cls.__dict__["set_output"]
        with_id, txn = Game.__dict__["with_id"], Player.__dict__["tick_update_txn"]
        hit = self._hit

        def set_seen_checksum(cache, gpid, value):
            hit("before_arm")
            arm(cache, gpid, value)
            hit("after_arm")

        def set_output(cache, gpid, out):
            hit("before_cache_write")
            write(cache, gpid, out)
            hit("after_cache_write")

        def game_read(gid):
            game = with_id.__func__(gid)
            hit("after_game_read")
            return game

        def tick_update_txn(*args):
            p = txn.__func__(*args)
            hit("after_txn")
            return p

        self._saved = [(cache_cls, "set_seen_checksum", arm), (cache_cls, "set_output", write),
                       (Game, "with_id", with_id), (Player, "tick_update_txn", txn)]
        cache_cls.set_seen_checksum, cache_cls.set_output = set_seen_checksum, set_output
        Game.with_id, Player.tick_update_txn = staticmethod(game_read), staticmethod(tick_update_txn)
        return self

    def __exit__(self, *exc):
        for owner, name, value in self._saved:
            setattr(owner, name, value)


class InjectedFailure(Exception):
    """The grant txn failure FlakyGrants raises."""


class FlakyGrants(object):
    """Fails the nth grant txn inside it, before its commit or just after; `calls` records each."""

    def __init__(self, nth, after_commit):
        self.nth, self.after_commit, self.calls, self.fired = nth, after_commit, [], False

    def __enter__(self):
        self._real = Player.__dict__["transaction_pickup_batch"]
        real, flaky = self._real.__func__, self

        def batch(pkeys, grants):
            if len(flaky.calls) != flaky.nth:
                flaky.calls.append((list(grants), True))
                return real(pkeys, grants)
            flaky.fired = True
            if flaky.after_commit:
                real(pkeys, grants)
            flaky.calls.append((list(grants), flaky.after_commit))
            raise InjectedFailure("grant txn %s failed %s its commit" % (
                flaky.nth, "after" if flaky.after_commit else "before"))
        Player.transaction_pickup_batch = staticmethod(batch)
        return self

    def __exit__(self, *exc):
        Player.transaction_pickup_batch = self._real
