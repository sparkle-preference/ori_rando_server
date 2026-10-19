"""Bingo square marks: a player's "going for this one" squares, kept in memcache
and handed out on every board fetch.

Same stub style as bingo_reroll_test: the routes are the real ones, the
datastore reads around them are stubbed.

Run from the repo root:  python3 -m unittest test.bingo_marks_test -v
"""
import json
import unittest

import google.auth.credentials
from google.cloud import ndb

import main
import models
from cache import Cache, MemcachedCache
from models import BingoGameData, Game, User
from web import bingo as bingo_routes

from test.bingo_reroll_test import GID, _FakeGame, _FakeKey, _FakeNdbClient, _FakeUser


class _FakePlayer(object):
    def __init__(self, user=None):
        self.user = user


class MarksTestCase(unittest.TestCase):

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
        main.app.secret_key = main.app.secret_key or "marks-test"
        self._game_with_id = Game.__dict__["with_id"]
        self._bingo_with_id = BingoGameData.__dict__["with_id"]
        self._user_get = User.__dict__["get"]
        self.game = _FakeGame()
        self.user = None
        self.owner = ndb.Key("User2", "owner")
        self.bingo = self.make_board({1: None, 2: ndb.Key("User2", "claimed")})
        Game.with_id = staticmethod(lambda gid: self.game)
        BingoGameData.with_id = staticmethod(lambda gid: self.bingo)
        User.get = staticmethod(lambda: self.user)
        self.client = main.app.test_client()
        Cache.clear_marks(GID)
        Cache.set_board(GID, {"cards": [], "teams": {}, "gameId": GID})

    def tearDown(self):
        Cache.clear_marks(GID)
        Game.with_id = self._game_with_id
        BingoGameData.with_id = self._bingo_with_id
        User.get = self._user_get
        main.app.secret_key = self._secret
        models.client = self._ndb_client
        self._ctx.__exit__(None, None, None)

    def make_board(self, seats):
        """seats: {pid: the account that claimed it, or None}."""
        bingo = BingoGameData(id=GID, board=[], game=ndb.Key("Game", GID), creator=self.owner,
                              difficulty="normal", seed="12345", bingo_count=3)
        bingo.players = [ndb.Key("Player", "%s.%s" % (GID, p)) for p in seats]
        bingo.put = lambda: None
        bingo.get_players = lambda: []
        bingo.get_json = lambda initial=False, players=None: {"cards": [], "teams": {}, "gameId": GID}
        bingo.player = lambda pid, *a, **kw: _FakePlayer(seats.get(int(pid)))

        def remove(pid):
            bingo.players = [k for k in bingo.players if not k.id().endswith(".%s" % pid)]
            return _FakeKey(GID, bingo)
        bingo.remove_player = remove
        return bingo

    def mark(self, pid, squares):
        return self.client.get("/bingo/game/%s/marks/%s?squares=%s" % (GID, pid, squares))

    def fetch(self, first=False):
        res = self.client.get("/bingo/game/%s/fetch%s" % (GID, "?first=1" if first else ""))
        self.assertEqual(res.status_code, 200)
        return json.loads(res.get_data(as_text=True))["marks"]

    def test_an_unclaimed_seat_takes_marks_from_anyone(self):
        self.assertEqual(self.mark(1, 5).status_code, 200)
        self.assertEqual(Cache.get_marks(GID), {1: 5})

    def test_a_claimed_seat_takes_marks_from_its_account_only(self):
        self.assertEqual(self.mark(2, 5).status_code, 403)
        self.user = _FakeUser(ndb.Key("User2", "someone-else"))
        self.assertEqual(self.mark(2, 5).status_code, 403)
        self.user = _FakeUser(self.owner)
        self.assertEqual(self.mark(2, 5).status_code, 403)
        self.assertEqual(Cache.get_marks(GID), {})
        self.user = _FakeUser(ndb.Key("User2", "claimed"))
        self.assertEqual(self.mark(2, 5).status_code, 200)
        self.assertEqual(Cache.get_marks(GID), {2: 5})

    def test_only_a_25_bit_mask_and_a_seated_player(self):
        for bad in ["-1", str(1 << 25), ""]:
            self.assertEqual(self.mark(1, bad).status_code, 400, bad)
        self.assertEqual(self.mark(1, "lots").status_code, 400)
        self.assertEqual(self.mark(3, 1).status_code, 404)
        self.assertEqual(self.mark(1, (1 << 25) - 1).status_code, 200)

    def test_zero_drops_the_player(self):
        self.mark(1, 5)
        self.user = _FakeUser(ndb.Key("User2", "claimed"))
        self.mark(2, 6)
        self.mark(1, 0)
        self.assertEqual(Cache.get_marks(GID), {2: 6})

    def test_every_fetch_carries_the_marks(self):
        self.assertEqual(self.fetch(), {})
        self.mark(1, 5)
        self.assertEqual(self.fetch(), {"1": 5})
        self.assertEqual(self.fetch(first=True), {"1": 5})
        Cache.cache.pop("%s.board" % GID, None)  # the dev cache: tests run without memcached
        self.assertEqual(self.fetch(), {"1": 5})

    def test_the_userboard_carries_them(self):
        Cache.set_latest_bingo_game("streamer", GID)
        self.mark(1, 5)
        res = self.client.get("/bingo/userboard/streamer/fetch/%s" % GID)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(json.loads(res.get_data(as_text=True))["marks"], {"1": 5})

    def test_a_reroll_clears_them(self):
        self.bingo.board = bingo_routes.bingo_board_cards(None, "normal", "12345", 0, False, False)
        self.mark(1, 5)
        self.user = _FakeUser(self.owner)
        self.assertEqual(self.client.get("/bingo/game/%s/reroll_board" % GID).status_code, 200)
        self.assertEqual(Cache.get_marks(GID), {})

    def test_removing_a_player_frees_their_marks(self):
        self.mark(1, 5)
        self.user = _FakeUser(ndb.Key("User2", "claimed"))
        self.mark(2, 6)
        self.user = _FakeUser(self.owner)
        self.assertEqual(self.client.get("/bingo/game/%s/remove/1" % GID).status_code, 200)
        self.assertEqual(Cache.get_marks(GID), {2: 6})


class _FakeMemcache(object):
    """gets/add/cas with a hook to slip a rival write in before the next cas."""

    def __init__(self):
        self.store, self.version, self.rival = {}, 0, None

    def gets(self, key):
        if key not in self.store:
            return None, None
        return dict(self.store[key]), self.version

    def add(self, key, value, expire=0, noreply=None):
        if key in self.store:
            return False
        self.store[key], self.version = value, self.version + 1
        return True

    def cas(self, key, value, cas, expire=0, noreply=False):
        if self.rival:
            rival, self.rival = self.rival, None
            rival()
        if self.version != cas:
            return False
        self.store[key], self.version = value, self.version + 1
        return True


class MemcachedMarksTestCase(unittest.TestCase):

    def setUp(self):
        self.cache = MemcachedCache.__new__(MemcachedCache)
        self.cache.memcache = _FakeMemcache()

    def test_a_lost_race_retries_on_the_winner(self):
        self.assertTrue(self.cache.set_marks(GID, 1, 5))
        store = self.cache.memcache

        def rival():
            store.store["%s.marks" % GID] = {1: 5, 2: 9}
            store.version += 1
        store.rival = rival
        self.assertTrue(self.cache.set_marks(GID, 3, 7))
        self.assertEqual(store.store["%s.marks" % GID], {1: 5, 2: 9, 3: 7})

    def test_it_gives_up_rather_than_spin(self):
        store = self.cache.memcache
        store.store["%s.marks" % GID] = {}
        store.cas = lambda *a, **kw: False
        self.assertFalse(self.cache.set_marks(GID, 1, 5))


if __name__ == "__main__":
    unittest.main()
