"""Rerolling a bingo game: a new seed on the same settings
(/bingo/game/<id>/reroll) and a new board on the same seed
(/bingo/game/<id>/reroll_board).

Stubs in the save/restore style (no mock lib), driving the real routes via
test_client. The BingoGameData is a real entity, so the cards, the discovery
draw and the RR seed bump are the ones prod runs; only the datastore reads
around it are stubbed.

Run from the repo root:  python3 -m unittest test.bingo_reroll_test -v
"""
import contextlib
import json
import unittest

import google.auth.credentials
from google.cloud import ndb

import main
from web import bingo as bingo_routes
import models
from enums import MultiplayerGameType
from models import BingoGameData, Game, User
from util import utcnow
from seedbuilder.seedparams import SeedGenParams

GID = 91001


class _FakeNdbClient(object):
    def context(self):
        return contextlib.nullcontext()


class _FakeKey(object):
    def __init__(self, kid, entity=None):
        self._id, self._entity = kid, entity

    def id(self):
        return self._id

    def get(self):
        return self._entity


class _FakeUser(object):
    def __init__(self, key):
        self.key = key


class _FakeSync(object):
    def __init__(self, enabled=False, mode=MultiplayerGameType.SHARED):
        self.enabled, self.mode, self.cloned = enabled, mode, True


class _FakeParams(object):
    """Enough of a SeedGenParams for the reroll path: it round-trips through
    to_json, answers seed_mode_problem, and claims to generate."""

    def __init__(self, ap_mode=False, shared=False, players=1):
        self.ap_mode = ap_mode
        self.seed = "rolled"
        self.bingo_lines = 4
        # the board url carries every bingo setting, so the double owes them all
        self.bingo_goal = "bingos"
        self.bingo_squares = 13
        self.bingo_diff = "normal"
        self.bingo_meta = False
        self.bingo_disc = 0
        self.players = players
        self.sync = _FakeSync(enabled=shared, mode=MultiplayerGameType.SHARED)
        self.generated = False

    def to_json(self):
        return {"seed": "old"}

    def generate(self):
        self.generated = True
        return True


class _FakeGame(object):
    def __init__(self, params=None, bingo=None):
        self._params = params
        self.params = _FakeKey(1, params) if params else None
        self.bingo_data = _FakeKey(GID, bingo) if bingo else None

    def fetch_params(self):
        return self._params


class RerollTestCase(unittest.TestCase):
    """Real ndb context for the entities; the middleware's own context would
    nest inside it, which ndb forbids, so client.context() is a no-op here."""

    @classmethod
    def setUpClass(cls):
        creds = google.auth.credentials.AnonymousCredentials()
        cls.ndb_client = ndb.Client(project="unit-test", credentials=creds)

    def setUp(self):
        self._ctx = self.ndb_client.context()
        self._ctx.__enter__()
        self._ndb_client = models.client
        models.client = _FakeNdbClient()
        self._secret = main.app.secret_key
        main.app.secret_key = main.app.secret_key or "reroll-test"
        self._game_with_id = Game.__dict__["with_id"]
        self._bingo_with_id = BingoGameData.__dict__["with_id"]
        self._user_get = User.__dict__["get"]
        self.game = _FakeGame()
        self.bingo = None
        self.user = None
        Game.with_id = staticmethod(lambda gid: self.game)
        BingoGameData.with_id = staticmethod(lambda gid: self.bingo)
        User.get = staticmethod(lambda: self.user)
        self.client = main.app.test_client()

    def tearDown(self):
        Game.with_id = self._game_with_id
        BingoGameData.with_id = self._bingo_with_id
        User.get = self._user_get
        main.app.secret_key = self._secret
        models.client = self._ndb_client
        self._ctx.__exit__(None, None, None)

    def make_board(self, seed="12345", owner="owner", **kw):
        """A real board entity with the datastore-touching bits stubbed out."""
        fields = dict(difficulty="normal", seed=seed, bingo_count=3, teams_allowed=False)
        fields.update(kw)
        bingo = BingoGameData(id=GID, board=bingo_routes.bingo_board_cards(None, fields["difficulty"], seed, 0, False, False),
                              game=ndb.Key("Game", GID), creator=ndb.Key("User2", owner), **fields)
        bingo.puts = 0

        def fake_put():
            bingo.puts += 1
        bingo.put = fake_put
        bingo.get_players = lambda: []
        # the real one inflates the creator; the cards are what these tests read
        bingo.get_json = lambda initial=False, players=None: {"cards": [c.name for c in bingo.board],
                                                             "initial": bool(initial)}
        self.bingo = bingo
        self.user = _FakeUser(bingo.creator)
        return bingo

    def reroll(self, **params):
        query = "&".join("%s=%s" % kv for kv in params.items())
        return self.client.get("/bingo/game/%s/reroll_board?%s" % (GID, query))

    def names(self, bingo):
        return [c.name for c in bingo.board]

    def test_bump_board_seed(self):
        for before, after in [("12345", "12345RR1"), ("12345RR1", "12345RR2"),
                              ("12345RR9", "12345RR10"), ("", "RR1"), ("RRRR2", "RRRR3")]:
            self.assertEqual(bingo_routes.bump_board_seed(before), after)

    def test_a_stranger_cannot_reroll(self):
        self.make_board()
        self.user = _FakeUser(ndb.Key("User2", "someone-else"))
        self.assertEqual(self.reroll().status_code, 401)
        self.user = None
        self.assertEqual(self.reroll().status_code, 401)
        self.assertEqual(self.bingo.puts, 0)

    def test_a_started_board_keeps_its_board(self):
        bingo = self.make_board(start_time=utcnow())
        before = self.names(bingo)
        self.assertEqual(self.reroll().status_code, 412)
        self.assertEqual(self.names(bingo), before)
        self.assertEqual(bingo.puts, 0)

    def test_a_joined_but_unstarted_board_rerolls(self):
        # goals travel by channel, so holding a seed no longer pins the board
        bingo = self.make_board()
        bingo.players = [ndb.Key("Player", "%s.1" % GID)]
        before = self.names(bingo)
        self.assertEqual(self.reroll().status_code, 200)
        self.assertNotEqual(self.names(bingo), before)

    def test_reroll_bumps_the_seed_and_moves_the_board(self):
        bingo = self.make_board(seed="12345")
        before = self.names(bingo)
        res = self.reroll(difficulty="normal", lines=3, seed="12345")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(bingo.seed, "12345RR1")
        self.assertNotEqual(self.names(bingo), before)
        self.assertEqual(bingo.puts, 1)
        # what the roller gets back is the board it just rolled
        self.assertEqual(json.loads(res.get_data(as_text=True))["cards"], self.names(bingo))

    def test_rerolls_keep_counting_up(self):
        bingo = self.make_board(seed="12345")
        for expected in ["12345RR1", "12345RR2", "12345RR3"]:
            self.assertEqual(self.reroll(seed=bingo.seed).status_code, 200)
            self.assertEqual(bingo.seed, expected)

    def test_an_edited_seed_is_taken_as_typed(self):
        bingo = self.make_board(seed="12345")
        self.assertEqual(self.reroll(seed="banana").status_code, 200)
        self.assertEqual(bingo.seed, "banana")

    def test_the_board_is_updated_not_replaced(self):
        bingo = self.make_board()
        creator, log_len = bingo.creator, len(bingo.event_log)
        self.assertEqual(self.reroll().status_code, 200)
        self.assertEqual(bingo.key.id(), GID)
        self.assertEqual(bingo.creator, creator)
        self.assertEqual(len(bingo.event_log), log_len + 1)
        self.assertTrue(bingo.event_log[-1].event_type.startswith("misc"))

    def test_switching_goal_mode_drops_the_old_goal(self):
        bingo = self.make_board(square_count=13)
        self.assertEqual(self.reroll(lines=5).status_code, 200)
        self.assertEqual(bingo.bingo_count, 5)
        self.assertIsNone(bingo.square_count)
        self.assertEqual(self.reroll(squares=11, lockout=1).status_code, 200)
        self.assertEqual(bingo.square_count, 11)
        self.assertTrue(bingo.lockout)

    def test_discovery_squares_are_redrawn(self):
        bingo = self.make_board(discovery=2, disc_squares=[7, 11])
        self.assertEqual(self.reroll(discCount=3).status_code, 200)
        self.assertEqual(bingo.discovery, 3)
        self.assertEqual(len(bingo.disc_squares), 3)
        # dropping discovery has to drop the squares with it
        self.assertEqual(self.reroll().status_code, 200)
        self.assertIsNone(bingo.discovery)
        self.assertEqual(bingo.disc_squares, [])

    def test_a_vanilla_board_has_no_seed_to_reroll(self):
        self.game = _FakeGame()
        res = self.client.get("/bingo/game/%s/reroll" % GID)
        self.assertEqual(res.status_code, 412)

    def test_an_archipelago_seed_refuses(self):
        params = _FakeParams(ap_mode=True)
        self.game = _FakeGame(params=params)
        res = self.client.get("/bingo/game/%s/reroll" % GID)
        self.assertEqual(res.status_code, 412)
        self.assertFalse(params.generated)

    def test_reroll_lands_in_the_board_builder(self):
        rolled = _FakeParams(shared=True, players=3)
        old = _FakeParams()
        self.make_board(discovery=4)
        self.game = _FakeGame(params=old, bingo=self.bingo)
        from_json, from_params = SeedGenParams.__dict__["from_json"], Game.__dict__["from_params"]
        SeedGenParams.from_json = staticmethod(lambda j: _FakeKey(1, rolled))
        Game.from_params = staticmethod(lambda p, gid=None: _FakeGame_with_key(99))
        try:
            res = self.client.get("/bingo/game/%s/reroll" % GID)
        finally:
            SeedGenParams.from_json = from_json
            Game.from_params = from_params
        self.assertEqual(res.status_code, 302)
        self.assertTrue(rolled.generated)
        self.assertIn("/bingo/board?game_id=99&fromGen=1&seed=rolled&bingoLines=4", res.headers["Location"])
        self.assertIn("disc=4", res.headers["Location"])
        self.assertIn("teamMax=3", res.headers["Location"])


class _FakeGame_with_key(object):
    def __init__(self, gid):
        self.key = _FakeKey(gid)


if __name__ == "__main__":
    unittest.main()
