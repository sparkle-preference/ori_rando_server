"""Username -> game resolution on the two polling routes.

The tracker's usermap lookup rides the 1Hz update poll, and the userboard's
bingo lookup rides a 1/min poll -- a name query plus a get per game the user
has ever played, which used to run on every single one of them.

Stubs in the save/restore style (no mock lib). The process-wide PythonCache
means gids/names here must be unique to this module.

Run from the repo root:  python3 -m unittest test.userlookup_test -v
"""
import json
import unittest

import main
from web import bingo as bingo_routes
from web import tracker
from cache import Cache
from models import User


class _FakeGame(object):
    def __init__(self, gid, bingo=False):
        self.key = _FakeKey(gid, self)
        self.bingo_data = "bingo!" if bingo else None


class _FakeKey(object):
    def __init__(self, gid, game=None, counter=None):
        self._id, self._game, self._counter = gid, game, counter

    def id(self):
        return self._id

    def get(self):
        if self._counter is not None:
            self._counter[0] += 1   # the walk's per-game datastore get
        return self._game


class _FakeUser(object):
    def __init__(self, games):
        self.games = games


class LatestBingoGameTestCase(unittest.TestCase):
    NAME = "lookuptester"

    def setUp(self):
        self.queries = 0
        self.gets = [0]
        self._by_name = User.get_by_name

        def counting_get_by_name(name):
            self.queries += 1
            return self.user
        User.get_by_name = staticmethod(counting_get_by_name)
        # newest last: the walk reverses, so the bingo game is visited first
        self.user = _FakeUser([_FakeKey(9002, _FakeGame(9002), self.gets),
                               _FakeKey(9001, _FakeGame(9001, bingo=True), self.gets)])
        Cache.clear_latest_bingo(self.NAME)
        Cache.clear_latest(self.NAME)

    def tearDown(self):
        User.get_by_name = staticmethod(self._by_name)
        Cache.clear_latest_bingo(self.NAME)
        Cache.clear_latest(self.NAME)

    def test_the_walk_runs_once_then_the_answer_is_cached(self):
        gid, err = bingo_routes.latest_bingo_game(self.NAME)
        self.assertEqual((gid, err), (9001, None))
        self.assertEqual(self.queries, 1)
        walk_gets = self.gets[0]
        self.assertGreater(walk_gets, 0)
        for _ in range(10):
            gid, err = bingo_routes.latest_bingo_game(self.NAME)
            self.assertEqual((gid, err), (9001, None))
        # ten more polls: no more name queries AND no more per-game gets
        self.assertEqual(self.queries, 1)
        self.assertEqual(self.gets[0], walk_gets)

    def test_the_derived_answer_never_claims_to_be_the_latest_game(self):
        # an OLD bingo game found by walking must not clobber the key the
        # tracker's usermap redirect reads
        Cache.set_latest_game(self.NAME, 9999)
        bingo_routes.latest_bingo_game(self.NAME)
        self.assertEqual(Cache.get_latest_game(self.NAME), 9999)
        self.assertEqual(Cache.get_latest_game(self.NAME, bingo=True), 9001)

    def test_unknown_user_is_an_error_and_is_not_cached(self):
        self.user = None
        gid, err = bingo_routes.latest_bingo_game(self.NAME)
        self.assertIsNone(gid)
        self.assertIn("not found", err)
        bingo_routes.latest_bingo_game(self.NAME)
        self.assertEqual(self.queries, 2)   # nothing to cache, so it re-asks

    def test_no_bingo_games_is_a_distinct_error(self):
        self.user = _FakeUser([_FakeKey(9003, _FakeGame(9003))])
        gid, err = bingo_routes.latest_bingo_game(self.NAME)
        self.assertIsNone(gid)
        self.assertIn("Could not find any bingo games", err)

    def test_a_cleaned_up_game_key_does_not_crash_the_walk(self):
        # Game.clean_old deletes games but leaves their keys on the user.
        # Order matters: the walk reverses, so the dangling key must be LAST
        # here to be the first one visited.
        self.user = _FakeUser([_FakeKey(9005, _FakeGame(9005, bingo=True)),
                               _FakeKey(9004, None)])
        gid, err = bingo_routes.latest_bingo_game(self.NAME)
        self.assertEqual((gid, err), (9005, None))

    def test_every_key_dangling_falls_through_to_the_error(self):
        self.user = _FakeUser([_FakeKey(9006, None), _FakeKey(9007, None)])
        gid, err = bingo_routes.latest_bingo_game(self.NAME)
        self.assertIsNone(gid)
        self.assertIn("Could not find any bingo games", err)


class _StopRoute(Exception):
    """Cut the route off right after the resolve block."""


class TrackerUsermapTestCase(unittest.TestCase):
    """The usermap redirect on /tracker/game/<id>/fetch/update. The route's
    next statement is Cache.get_pos(game_id), so capturing that argument is
    how we see which game id the resolve block settled on."""
    NAME = "usermaptester"

    def setUp(self):
        self.calls = 0
        self.resolved = []
        self.latest = 8001
        self._latest, self._get_pos = User.latest_game, Cache.get_pos

        def counting_latest(name):
            self.calls += 1
            return self.latest

        def capture_pos(gid):
            self.resolved.append(gid)
            raise _StopRoute()
        User.latest_game = staticmethod(counting_latest)
        # Cache is a module-level instance: a plain reassignment would leave
        # the bound method shadowing the class attribute forever, so remember
        # whether the instance had one of its own
        self._had_own_get_pos = "get_pos" in Cache.__dict__
        Cache.get_pos = capture_pos

    def tearDown(self):
        User.latest_game = staticmethod(self._latest)
        if self._had_own_get_pos:
            Cache.get_pos = self._get_pos
        else:
            del Cache.get_pos

    def _resolve(self, game_id):
        with main.app.test_request_context(
                "/tracker/game/%s/fetch/update?usermap=%s" % (game_id, self.NAME)):
            self.assertRaises(_StopRoute, tracker.tracker_update_map, game_id)
        return self.resolved[-1]

    def test_the_lookup_runs_once_per_poll(self):
        self._resolve(8001)
        self.assertEqual(self.calls, 1)

    def test_a_newer_game_redirects_the_poll_with_one_lookup(self):
        # the redirect branch is the one that used to call latest_game twice
        # (once for the != test, once for the assignment)
        self.latest = 8002
        self.assertEqual(self._resolve(8001), 8002)
        self.assertEqual(self.calls, 1)

    def test_an_unknown_user_does_not_become_the_game_id(self):
        # latest_game returns False for an unknown name; that used to be
        # assigned straight into game_id, turning the poll into a 404
        self.latest = False
        self.assertEqual(self._resolve(8001), 8001)


class TrackerRedirectResponseTestCase(unittest.TestCase):
    """The redirect has to reach the client: without newGid in the body a
    tracker (or an OBS source) keeps polling the stale game id forever."""
    NAME = "redirecttester"
    MODES = "casual-core"

    def setUp(self):
        self._saved = (User.latest_game, Cache.get_pos, Cache.get_have,
                       Cache.get_reachable)
        User.latest_game = staticmethod(lambda name: 8102)
        Cache.get_pos = lambda gid: {1: (3, 4)}
        Cache.get_have = lambda gid: {1: [-280256]}
        # pre-seeded so the route never needs a game entity to compute reach
        Cache.get_reachable = lambda gid: {1: {(self.MODES,): ["glades"]}}

    def tearDown(self):
        (User.latest_game, Cache.get_pos, Cache.get_have,
         Cache.get_reachable) = self._saved

    def _body(self, game_id):
        with main.app.test_request_context(
                "/tracker/game/%s/fetch/update?modes=%s&usermap=%s"
                % (game_id, self.MODES, self.NAME)):
            resp = tracker.tracker_update_map(game_id)
        return json.loads(resp.get_data(as_text=True))

    def test_a_moved_game_tells_the_client_its_new_id(self):
        body = self._body(8101)
        self.assertEqual(body.get("newGid"), 8102)

    def test_the_same_game_says_nothing(self):
        body = self._body(8102)
        self.assertNotIn("newGid", body)
        self.assertIn("players", body)


if __name__ == "__main__":
    unittest.main()
