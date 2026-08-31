"""The game-list pages (/activeGames, /myGames).

Rendering a row used to inflate the whole SeedGenParams entity -- placements,
spoilers and all -- for two small values, and /activeGames additionally ran a
history walk per game behind an unlimited query. This pins the cheap shapes.

Stubs in the save/restore style (no mock lib). Params ids here are unique to
this module: the test PythonCache is process-wide.

Run from the repo root:  python3 -m unittest test.gamelist_test -v
"""
import unittest

import google.auth.credentials
from google.cloud import ndb

import main
import models
import util
from cache import Cache
from enums import MultiplayerGameType, Variation
from util import utcnow
from seedbuilder.seedparams import SeedGenParams


class _FakeKey(object):
    def __init__(self, kid, entity=None, counter=None):
        self._id, self._entity, self._counter = kid, entity, counter

    def id(self):
        return self._id

    def get(self):
        if self._counter is not None:
            self._counter[0] += 1
        return self._entity


class _FakeParams(object):
    """Stands in for the ~250KB entity; the two cheap values are all a list
    row ever reads off it."""

    def __init__(self, line="standard,balanced|seedname", race=False):
        self.line, self.variations = line, [Variation.RACE] if race else []

    def flag_line(self, verbose_paths=False):
        return self.line


class GameFlagsTestCase(unittest.TestCase):
    PID = 77001

    @classmethod
    def setUpClass(cls):
        creds = google.auth.credentials.AnonymousCredentials()
        cls.ndb_client = ndb.Client(project="unit-test", credentials=creds)

    def setUp(self):
        # the hook tests build real entities/keys, which needs a context
        self._ctx = self.ndb_client.context()
        self._ctx.__enter__()
        self.gets = [0]
        self.params = _FakeParams()
        Cache.clear_game_flags(self.PID)

    def tearDown(self):
        Cache.clear_game_flags(self.PID)
        self._ctx.__exit__(None, None, None)

    def _key(self):
        return _FakeKey(self.PID, self.params, self.gets)

    def test_the_entity_is_read_once_and_then_never_again(self):
        self.assertEqual(util.game_flags(self._key()),
                         ("standard,balanced|seedname", False))
        self.assertEqual(self.gets[0], 1)
        for _ in range(20):
            util.game_flags(self._key())
        self.assertEqual(self.gets[0], 1)   # twenty more rows, no inflation

    def test_a_race_seed_reports_itself(self):
        self.params = _FakeParams(race=True)
        line, is_race = util.game_flags(self._key())
        self.assertTrue(is_race)
        self.assertEqual(line, "standard,balanced|seedname")

    def test_a_deleted_seed_is_not_cached_as_an_answer(self):
        self.params = None
        self.assertEqual(util.game_flags(self._key()), (None, False))
        self.assertIsNone(Cache.get_game_flags(self.PID))

    def test_a_params_put_busts_the_pair(self):
        # the one mutate-and-put site (bingo's variation append) must not
        # leave a stale flag line behind. Drives the REAL hook, so deleting
        # its bust fails here rather than passing quietly.
        util.game_flags(self._key())
        self.assertIsNotNone(Cache.get_game_flags(self.PID))
        planted = SeedGenParams(id=self.PID, seed="x")
        planted._post_put_hook(None)         # what ndb fires after any put
        self.assertIsNone(Cache.get_game_flags(self.PID))
        self.params = _FakeParams(line="standard,balanced,bingo|seedname")
        self.assertEqual(util.game_flags(self._key())[0],
                         "standard,balanced,bingo|seedname")

    def test_a_params_delete_busts_the_pair(self):
        # clean_up deletes params that another live game may still point at:
        # that row has to go back to "(Seed not found)", not a dead link
        util.game_flags(self._key())
        self.assertIsNotNone(Cache.get_game_flags(self.PID))
        SeedGenParams._post_delete_hook(ndb.Key("SeedGenParams", self.PID), None)
        self.assertIsNone(Cache.get_game_flags(self.PID))


class _FakeGame(object):
    def __init__(self, gid, params_key=None, has_history=None):
        self.key = _FakeKey(gid)
        self.params = params_key
        self.has_history = has_history
        self.last_update = utcnow()
        self.bingo_data = None


class GameListHtmlTestCase(unittest.TestCase):
    PID = 77002

    def setUp(self):
        self.gets = [0]
        self._url_for, self._whitelist = util.url_for, util.whitelist_ok
        util.url_for = lambda route, **kw: "/%s/%s" % (route, kw.get("game_id", ""))
        util.whitelist_ok = lambda: False
        Cache.clear_game_flags(self.PID)

    def tearDown(self):
        util.url_for, util.whitelist_ok = self._url_for, self._whitelist
        Cache.clear_game_flags(self.PID)

    def test_the_seed_link_costs_no_fetch_when_flags_are_cached(self):
        Cache.set_game_flags(self.PID, "standard|seed", False)
        games = [_FakeGame(500 + i, _FakeKey(self.PID, _FakeParams(), self.gets))
                 for i in range(5)]
        body = util.game_list_html(games)
        self.assertEqual(self.gets[0], 0)         # five rows, zero inflations
        self.assertEqual(body.count("Seed</a>"), 5)
        self.assertIn("standard|seed", body)

    def test_race_games_are_hidden_from_the_unwhitelisted(self):
        Cache.set_game_flags(self.PID, "standard|seed", True)
        body = util.game_list_html([_FakeGame(501, _FakeKey(self.PID, _FakeParams(race=True)))])
        self.assertEqual(body, "")
        util.whitelist_ok = lambda: True
        body = util.game_list_html([_FakeGame(501, _FakeKey(self.PID, _FakeParams(race=True)))])
        self.assertIn("Game #501", body)

    def test_a_missing_seed_says_so(self):
        body = util.game_list_html([_FakeGame(502, _FakeKey(77003, None))])
        self.assertIn("Seed not found", body)

    def test_a_game_without_params_still_renders(self):
        body = util.game_list_html([_FakeGame(503)])
        self.assertIn("Game #503", body)


class _FakeSync(object):
    shared, dedup, teams = [], False, None
    mode = MultiplayerGameType.SIMUSOLO


class _FakeGenParams(object):
    """Only the attributes Game.from_params reads."""
    player_names, variations, players, ap_mode = [], [], 1, False

    def __init__(self):
        self.key = ndb.Key("SeedGenParams", 70002)
        self.sync = _FakeSync()


class GameBirthTestCase(unittest.TestCase):
    """What a REAL Game is born with. Every assertion elsewhere in this module
    supplies has_history itself, which is exactly how a creation path that
    never set it stayed invisible: from_params (the seed-generation path, five
    callers) is the one that matters, not Game.new (bingo only)."""

    @classmethod
    def setUpClass(cls):
        creds = google.auth.credentials.AnonymousCredentials()
        cls.ndb_client = ndb.Client(project="unit-test", credentials=creds)

    def setUp(self):
        self._ctx = self.ndb_client.context()
        self._ctx.__enter__()
        self._gid, self._user = models.Game.get_open_gid, models.User.get
        models.Game.get_open_gid = staticmethod(lambda: 70001)
        models.User.get = staticmethod(lambda: None)

    def tearDown(self):
        models.Game.get_open_gid = self._gid
        models.User.get = self._user
        self._ctx.__exit__(None, None, None)

    def test_a_generated_game_starts_empty_not_unknown(self):
        # from_params is the seed-generation path; a game born without the
        # field reads None, and None is not False, so /activeGames would show
        # every generated-but-never-played game
        params = _FakeGenParams()
        saved = (models.Game.put, models.Game.rebuild_hist, models.Game.player)
        try:
            models.Game.put = lambda g, *a, **k: g.key
            models.Game.rebuild_hist = lambda g: None
            models.Game.player = lambda g, pid, **k: None
            game = models.Game.from_params(params, gid=70001)
        finally:
            (models.Game.put, models.Game.rebuild_hist, models.Game.player) = saved
        self.assertIs(game.has_history, False)

    def test_a_bingo_game_starts_empty(self):
        created = []
        saved = models.Game.put
        try:
            models.Game.put = lambda g, *a, **k: created.append(g) or g.key
            models.Game.new(gid=70003)
        finally:
            models.Game.put = saved
        self.assertIs(created[0].has_history, False)


class ActiveGamesRouteTestCase(unittest.TestCase):
    """The real route: one bounded query, no history walk, and empty games
    filtered on the field. False = known empty, None = written before the
    field existed, so unknown and shown."""

    def setUp(self):
        self.queries = 0
        self.limits = []
        self.orders = []
        self.rendered = []
        self.games = []
        self._query, self._html = main.Game.query, main.game_list_html
        outer = self

        class _Query(object):
            def order(self, *props):
                outer.orders.append(props)
                return self

            def fetch(self, limit=None):
                outer.limits.append(limit)
                return outer.games

        def counting_query(*a, **kw):
            outer.queries += 1
            return _Query()
        main.Game.query = staticmethod(counting_query)
        main.game_list_html = lambda games: (outer.rendered.append(list(games))
                                             or "<li>rendered</li>")

    def tearDown(self):
        main.Game.query, main.game_list_html = self._query, self._html

    def _run(self):
        with main.app.test_request_context("/activeGames/"):
            main.active_games()
        return self.rendered[-1]

    def test_the_query_is_bounded_and_runs_once(self):
        self.games = [_FakeGame(1, has_history=True)]
        self._run()
        self.assertEqual(self.queries, 1)
        # over-fetches so the has_history filter has slack, then slices
        self.assertEqual(self.limits, [main.GAME_LIST_LIMIT * 4])

    def test_the_rendered_list_is_capped_after_filtering(self):
        self.games = ([_FakeGame(i, has_history=False) for i in range(60)]
                      + [_FakeGame(900 + i, has_history=True) for i in range(60)])
        shown = self._run()
        self.assertEqual(len(shown), main.GAME_LIST_LIMIT)
        # the empty ones were dropped BEFORE the cap, so real games survive
        self.assertTrue(all(g.key.id() >= 900 for g in shown))

    def test_the_cap_keeps_the_newest_games(self):
        # an inequality query defaults to ascending on that property, so
        # without an explicit descending order the limit would keep the
        # OLDEST games in the window
        self.games = [_FakeGame(1, has_history=True)]
        self._run()
        self.assertEqual(len(self.orders), 1)
        order, = self.orders[0]
        self.assertEqual(order.name, "last_update")
        self.assertTrue(order.reverse)

    def test_empty_games_are_filtered_but_unknown_ones_survive(self):
        self.games = [_FakeGame(1, has_history=True),
                      _FakeGame(2, has_history=False),
                      _FakeGame(3, has_history=None)]
        shown = [g.key.id() for g in self._run()]
        self.assertEqual(shown, [1, 3])

    def test_no_active_games_does_not_fall_back_to_every_game(self):
        # the old fallback re-queried with no filter at all, pulling the
        # entire Game corpus into one request
        self.games = []
        with main.app.test_request_context("/activeGames/"):
            resp = main.active_games()
        self.assertEqual(self.queries, 1)
        self.assertIn("No active games", resp.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
