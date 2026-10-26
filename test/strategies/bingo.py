"""Strategies and harnesses for test/bingo_props.py."""
import hashlib
import json
import logging
import random
import types
from datetime import datetime

from google.cloud import ndb
from hypothesis import strategies as st

from bingo import SPAWN_TELEPORTERS, BingoGenerator
from models import BingoCard, BingoCardProgress, BingoGameData, BingoTeam, Player, pick_discovery_squares

# far above what any finishing board draws, so only a loop that never ends reaches it
DRAW_CAP = 20000
SPAWNS = sorted(SPAWN_TELEPORTERS) + ["Random"]
DIFFICULTIES = ["easy", "normal", "hard"]


class Spinning(Exception):
    """A board drew past its cap."""


class BoundedRandom(random.Random):
    """A Random that raises Spinning past `limit` draws, since get_cards has no iteration guard of its own."""

    def __init__(self, seed=None, limit=DRAW_CAP):
        self.calls, self.limit = 0, limit
        super().__init__(seed)

    def _tick(self):
        self.calls += 1
        if self.calls > self.limit:
            raise Spinning("get_cards drew %d numbers without finishing" % self.calls)

    def random(self):
        self._tick()
        return super().random()

    def getrandbits(self, k):
        self._tick()
        return super().getrandbits(k)


board_seeds = st.one_of(st.integers(-2**40, 2**40), st.text(max_size=10))
discovery_counts = st.one_of(st.just(0), st.integers(1, 25))


def board_options(discovery=discovery_counts):
    """get_cards' keyword options, in any combination."""
    return st.fixed_dictionaries({
        "rando": st.booleans(),
        "difficulty": st.sampled_from(DIFFICULTIES),
        "open_world": st.booleans(),
        "discovery": discovery,
        "meta": st.booleans(),
        "lockout": st.booleans(),
        "keysanity": st.booleans(),
        "spawn": st.sampled_from(SPAWNS),
        "enemy_rando": st.booleans(),
    })


def roll(seed, opts):
    """The board get_cards deals for this seed and these options, on a draw-capped Random."""
    return BingoGenerator.get_cards(BoundedRandom(seed), 25, **opts)


def snapshot(cards):
    """Everything a dealt board carries, in its own order."""
    return [(c.to_json([], True), c.goal_method, c.early, c.meta, sorted(c.needs)) for c in cards]


def quiet_logs(tc):
    """Mutes logging until the test ends: the generator and routes log errors on paths walked on purpose."""
    tc.addCleanup(logging.disable, logging.root.manager.disable)
    logging.disable(logging.CRITICAL)


def hashseed_cases(n):
    """n (seed, options) pairs, the same in every process."""
    r = random.Random(7)
    out = []
    for _ in range(n):
        out.append((r.randint(0, 10**9), {
            "rando": r.random() < .5, "difficulty": r.choice(DIFFICULTIES), "open_world": r.random() < .5,
            "discovery": r.choice([0, 0, r.randint(1, 25)]), "meta": r.random() < .5, "lockout": r.random() < .5,
            "keysanity": r.random() < .5, "spawn": r.choice(SPAWNS), "enemy_rando": r.random() < .5}))
    return out


def board_digests(n):
    """A digest per hashseed case of the dealt board and its discovery picks."""
    out = []
    for seed, opts in hashseed_cases(n):
        cards = roll(seed, opts)
        picks = pick_discovery_squares(cards, str(seed), opts["discovery"] or 2)
        out.append(hashlib.sha1(json.dumps([snapshot(cards), picks]).encode()).hexdigest()[:12])
    return out


UPDATE_GID = 9
# team rosters as pids, captain first
ROSTERS = [[[1]], [[1], [2]], [[1, 2]], [[1, 2], [3]], [[1], [2], [3, 4]]]


@st.composite
def activate_cards(draw):
    """{square: (method, targets)}: up to three Activate Squares cards, each aimed at non-meta squares."""
    squares = draw(st.lists(st.integers(0, 24), unique=True, max_size=3))
    others = [i for i in range(25) if i not in squares]
    return {sq: (draw(st.sampled_from(["or", "and"])),
                 draw(st.lists(st.sampled_from(others), unique=True, min_size=1, max_size=3)))
            for sq in squares}


# (index into the roster's pids, replaces that player's last report, else toggles it, squares)
report = st.tuples(st.integers(0, 3), st.booleans(), st.frozensets(st.integers(0, 24)))


@st.composite
def report_runs(draw, most=40):
    """Up to `most` reports, any length equally likely, so games run long enough to fill lines."""
    n = draw(st.integers(0, most))
    return draw(st.lists(report, min_size=n, max_size=n))


update_scenarios = st.fixed_dictionaries({
    "roster": st.sampled_from(ROSTERS),
    "lockout": st.booleans(),
    "goal": st.one_of(st.tuples(st.just("squares"), st.integers(1, 25)),
                      st.tuples(st.just("bingos"), st.integers(1, 4))),
    "metas": activate_cards(),
    "reports": report_runs(),
})


def stub_player_txns(tc):
    """Points the update's Player transactions at nothing until the test ends."""
    for name in ("signal_send_txn", "save_bingo_txn"):
        tc.addCleanup(setattr, Player, name, Player.__dict__[name])
    Player.signal_send_txn = staticmethod(lambda pkey, signal: True)
    Player.save_bingo_txn = staticmethod(lambda pkey, prog, tp: True)


class UpdateGame(object):
    """A bool board plus Activate Squares cards, teams and players, with datastore writes and the render stubbed."""

    def __init__(self, sc):
        roster = sc["roster"]
        self.pids = [p for team in roster for p in team]
        self.team_of = {p: team[0] for team in roster for p in team}
        self.members = {team[0]: list(team) for team in roster}
        self.metas = sc["metas"]
        self.players = {p: Player(id="%s.%s" % (UPDATE_GID, p),
                                  bingo_prog=[BingoCardProgress(square=i) for i in range(25)]) for p in self.pids}
        for p in self.players.values():
            p.put = lambda *a, **k: None
        bgd = BingoGameData(id=UPDATE_GID)
        bgd.board = [BingoCard(name="S%d" % i, goal_type="bool", square=i) for i in range(25)]
        for sq, (method, targets) in self.metas.items():
            bgd.board[sq] = BingoCard(name="Activate Squares", goal_type="multi", goal_method=method, square=sq,
                                      meta=True, subgoals=[{"name": str(t), "disp_name": str(t)} for t in targets])
        bgd.teams = [BingoTeam(captain=self.players[t[0]].key, teammates=[self.players[p].key for p in t[1:]])
                     for t in roster]
        bgd.players = [self.players[p].key for p in self.pids]
        bgd.lockout = sc["lockout"]
        kind, target = sc["goal"]
        if kind == "squares":
            bgd.square_count = target
        else:
            bgd.bingo_count = target
        bgd.start_time = datetime(2026, 7, 20, 12, 0, 0)
        bgd.game = ndb.Key("Game", UPDATE_GID)
        bgd.get_players = lambda: list(self.players.values())
        bgd.put = lambda *a, **k: None
        bgd.archive_evlog = lambda gid: 0
        bgd.get_json = lambda initial=False, players=None: {}
        self.bgd = bgd

    def report(self, pid, done):
        """pid's game reports exactly these squares done."""
        self.bgd.update({"S%d" % i: {"value": i in done} for i in range(25)}, pid, UPDATE_GID)

    def payload(self):
        """The board json every poll gets, rendered by the real get_json."""
        return BingoGameData.get_json(self.bgd, players=list(self.players.values()))


def multiworld_params(worlds, seed="bingoprops"):
    """An in-memory multiworld SeedGenParams, one settings blob per world."""
    from enums import KeyMode, LogicPath, MultiplayerGameType, PathDifficulty
    from seedbuilder.seedparams import MultiplayerOptions, SeedGenParams
    p = SeedGenParams(seed=seed)
    p.sync = MultiplayerOptions()
    p.sync.enabled = True
    p.sync.mode = MultiplayerGameType.MULTIWORLD
    p.spoilers, p.placements = [""], []
    p.logic_paths = [LogicPath.CASUAL_CORE]
    p.key_mode = KeyMode.CLUES
    p.path_diff = PathDifficulty.NORMAL
    p.players = len(worlds)
    p.variations = []
    p.world_settings = worlds
    return p


def solo_params(seed="bingoprops"):
    """An in-memory single-world SeedGenParams."""
    from seedbuilder.seedparams import MultiplayerOptions
    p = multiworld_params([{}], seed)
    p.sync = MultiplayerOptions()
    return p


world_blobs = st.fixed_dictionaries({
    "variations": st.sampled_from([["Bingo"], [], ["Bingo", "OpenWorld"]]),
    "bingoDiff": st.sampled_from(DIFFICULTIES),
    "bingoDisc": discovery_counts,
    "bingoMeta": st.booleans(),
})

reroll_cases = st.fixed_dictionaries({
    "shape": st.sampled_from(["vanilla", "solo", "multiworld"]),
    "worlds": st.lists(world_blobs, min_size=1, max_size=3),
    "seed": st.text(max_size=6),
    "difficulty": st.sampled_from(DIFFICULTIES),
    "disc": discovery_counts,
    "meta": st.booleans(),
    "lockout": st.booleans(),
    "world": st.integers(1, 3),
})


class RerollRoutes(object):
    """reroll_board on one in-memory board with its datastore reads stubbed; mix in ahead of a TestCase."""

    GID = 91002

    def setUp(self):
        super().setUp()
        import main
        import models
        from models import Game, User
        from test.bingo_reroll_test import _FakeNdbClient
        from web import bingo as bingo_routes
        self.routes = bingo_routes
        self.bingo = self.game = self.user = None
        for owner, name in ((models, "client"), (main.app, "secret_key"), (bingo_routes, "random")):
            self.addCleanup(setattr, owner, name, getattr(owner, name))
        for cls, name in ((Game, "with_id"), (BingoGameData, "with_id"), (User, "get")):
            self.addCleanup(setattr, cls, name, cls.__dict__[name])
        models.client = _FakeNdbClient()
        main.app.secret_key = main.app.secret_key or "bingo-props"
        bingo_routes.random = types.SimpleNamespace(Random=BoundedRandom)
        Game.with_id = staticmethod(lambda gid: self.game)
        BingoGameData.with_id = staticmethod(lambda gid: self.bingo)
        User.get = staticmethod(lambda: self.user)
        self.client = main.app.test_client()

    def seat(self, params, seed, boards=()):
        """A board for these params (None for vanilla+), served to the route with its owner signed in."""
        from test.bingo_reroll_test import _FakeGame, _FakeUser
        board = [] if boards else self.routes.bingo_board_cards(params, "normal", seed, 0, False, False)
        bingo = BingoGameData(id=self.GID, board=board, boards=list(boards), game=ndb.Key("Game", self.GID),
                              creator=ndb.Key("User2", "owner"), difficulty="normal", seed=seed, bingo_count=3)
        bingo.put = lambda *a, **k: None
        bingo.get_players = lambda: []
        bingo.get_json = lambda initial=False, players=None: {}
        self.bingo, self.game, self.user = bingo, _FakeGame(params=params), _FakeUser(bingo.creator)
        return bingo

    def reroll(self, **query):
        args = "&".join("%s=%s" % kv for kv in query.items())
        return self.client.get("/bingo/game/%s/reroll_board?%s" % (self.GID, args))
