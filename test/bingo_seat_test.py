"""Seating on a per-world bingo board.

A multiworld board's roster comes out of the seed, so /bingo/game/<id>/add/<pid>
has no slot to claim -- except one the owner removed, which it can put back.

The fakes come from bingo_reroll_test: same shape of stub, same reasons, and one
copy is worth more than a matching pair. Only the datastore reads are stubbed;
the route and its guards are the ones prod runs.

Run from the repo root:  python3 -m unittest test.bingo_seat_test -v
"""
import json
import unittest

import google.auth.credentials
from google.cloud import ndb

import main
from web import generator
import models
from models import BingoGameData, BingoWorldBoard, Game, User

from test.bingo_reroll_test import GID, _FakeGame, _FakeNdbClient, _FakeUser


class _SeatHarness(unittest.TestCase):
    """Stubs only -- no tests. A TestCase subclass inherits its parent's
    tests, so the classes below share this instead of each other."""

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
        main.app.secret_key = main.app.secret_key or "seat-test"
        self._game_with_id = Game.__dict__["with_id"]
        self._bingo_with_id = BingoGameData.__dict__["with_id"]
        self._user_get = User.__dict__["get"]
        self._is_admin = User.__dict__["is_admin"]
        self.game = _FakeGame()
        self.bingo = None
        self.user = None
        self.admin = False
        Game.with_id = staticmethod(lambda gid: self.game)
        BingoGameData.with_id = staticmethod(lambda gid: self.bingo)
        User.get = staticmethod(lambda: self.user)
        User.is_admin = staticmethod(lambda: self.admin)
        self.client = main.app.test_client()

    def tearDown(self):
        Game.with_id = self._game_with_id
        BingoGameData.with_id = self._bingo_with_id
        User.get = self._user_get
        User.is_admin = self._is_admin
        main.app.secret_key = self._secret
        models.client = self._ndb_client
        self._ctx.__exit__(None, None, None)

    def make_board(self, worlds=(1, 2), seated=(2,), owner="owner"):
        """A per-world board with `seated` still holding seats. init_player is
        stubbed: putting a Player back is a datastore write, not a guard."""
        bingo = BingoGameData(id=GID, board=[], game=ndb.Key("Game", GID),
                              creator=ndb.Key("User2", owner), difficulty="normal",
                              boards=[BingoWorldBoard(world=w, board=[]) for w in worlds])
        bingo.players = [ndb.Key("Player", "%s.%s" % (GID, w)) for w in seated]
        bingo.puts = 0
        bingo.seated = []

        def fake_put():
            bingo.puts += 1
        bingo.put = fake_put
        bingo.get_players = lambda: []
        bingo.get_json = lambda initial=False, players=None: {"worlds": bingo.player_nums()}

        def fake_init_player(pid):
            key = ndb.Key("Player", "%s.%s" % (GID, pid))
            bingo.seated.append(pid)
            bingo.players.append(key)
            return type("_P", (), {"key": key})()
        bingo.init_player = fake_init_player
        self.bingo = bingo
        self.user = _FakeUser(bingo.creator)
        return bingo

    def add(self, pid):
        return self.client.get("/bingo/game/%s/add/%s" % (GID, pid))


class PerWorldSeatTestCase(_SeatHarness):

    def test_the_owner_puts_a_removed_world_back(self):
        bingo = self.make_board(worlds=(1, 2), seated=(2,))
        res = self.add(1)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(bingo.seated, [1])
        self.assertEqual([t.pids() for t in bingo.teams], [[1]], "back as its own team")
        self.assertEqual(json.loads(res.get_data(as_text=True))["worlds"], [2, 1])
        self.assertEqual(bingo.puts, 1)

    def test_a_stranger_still_gets_the_go_ask_the_host_message(self):
        bingo = self.make_board()
        self.user = _FakeUser(ndb.Key("User2", "someone-else"))
        res = self.add(1)
        self.assertEqual(res.status_code, 412)
        self.assertIn("whoever rolled it", res.get_data(as_text=True))
        self.assertEqual(bingo.seated, [])
        self.user = None
        self.assertEqual(self.add(1).status_code, 412)
        self.assertEqual(bingo.puts, 0)

    def test_an_admin_can_reseat_too(self):
        bingo = self.make_board()
        self.user = _FakeUser(ndb.Key("User2", "someone-else"))
        self.admin = True
        self.assertEqual(self.add(1).status_code, 200)
        self.assertEqual(bingo.seated, [1])

    def test_a_world_with_no_board_is_not_a_seat(self):
        bingo = self.make_board(worlds=(1, 2), seated=(2,))
        res = self.add(3)
        self.assertEqual(res.status_code, 412)
        self.assertIn("no board", res.get_data(as_text=True))
        self.assertEqual(bingo.seated, [])

    def test_a_world_that_never_left_is_not_re_seated(self):
        bingo = self.make_board(worlds=(1, 2), seated=(1, 2))
        res = self.add(2)
        self.assertEqual(res.status_code, 409)
        self.assertEqual(bingo.seated, [])
        self.assertEqual(bingo.puts, 0)

    def test_the_event_log_says_the_squares_are_gone(self):
        """Removal deletes the Player, so a re-seat is a clear board. Say so
        where the players will read it rather than letting them discover it."""
        bingo = self.make_board()
        self.add(1)
        self.assertEqual(len(bingo.event_log), 1)
        self.assertIn("clear board", bingo.event_log[0].event_type)


class ApBingoSeedGateTestCase(_SeatHarness):
    """The board's seed handout obeys the same not-ready gate as the seed
    page. An AP seed is a snapshot; the bingo route was the way around it."""

    def setUp(self):
        super(ApBingoSeedGateTestCase, self).setUp()
        self._gate = generator.ap_seed_not_ready
        self.gate_calls = []
        self.gate_answer = None
        def gate(params, gid):
            self.gate_calls.append((params, gid))
            return self.gate_answer
        generator.ap_seed_not_ready = gate
        # the default harness game is paramless; the gate needs one to consult
        self.ap_params = object()
        self.game._params = self.ap_params

    def tearDown(self):
        generator.ap_seed_not_ready = self._gate
        super(ApBingoSeedGateTestCase, self).tearDown()

    def download(self, pid=2):
        bingo = self.make_board()
        bingo.get_seed = lambda p: "Sync%s.%s,flags\n" % (GID, p)
        return self.client.get("/bingo/game/%s/seed/%s" % (GID, pid))

    def test_a_not_ready_ap_game_refuses_the_download(self):
        self.gate_answer = "names are not ready"
        res = self.download()
        self.assertEqual(res.status_code, 409)
        self.assertIn(b"names are not ready", res.data)
        self.assertEqual(self.gate_calls, [(self.ap_params, GID)])

    def test_a_ready_ap_game_hands_the_seed_out(self):
        res = self.download()
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"flags", res.data)

    def test_force_is_the_same_escape_hatch_the_seed_page_has(self):
        self.gate_answer = "names are not ready"
        bingo = self.make_board()
        bingo.get_seed = lambda p: "Sync%s.%s,flags\n" % (GID, p)
        res = self.client.get("/bingo/game/%s/seed/2?force=1" % GID)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self.gate_calls, [], "force must skip the gate, not ask it")

    def test_a_paramless_board_skips_the_gate(self):
        # vanilla+ boards have a game and no params; there is nothing to bake
        self.game._params = None
        res = self.download()
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self.gate_calls, [])


if __name__ == "__main__":
    unittest.main()
