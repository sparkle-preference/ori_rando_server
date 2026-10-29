"""The Twitch extension reads two bingo routes cross-origin, and only those two.

Run from the repo root:  python -m unittest test.bingo_twitch_cors_test -v
"""
import unittest

from test.ndb_base import EmulatorTestCase

TWITCH = "https://abc123.ext-twitch.tv"


class TwitchCorsTestCase(EmulatorTestCase):

    def setUp(self):
        super(TwitchCorsTestCase, self).setUp()
        import main
        import models
        self.main, self.models = main, models
        # requests ride the wsgi middleware, which opens models.client's context
        self._models_client, models.client = models.client, self.ndb_client
        self._secret = main.app.secret_key
        main.app.secret_key = main.app.secret_key or "cors-test"

    def tearDown(self):
        self.models.client = self._models_client
        self.main.app.secret_key = self._secret
        super(TwitchCorsTestCase, self).tearDown()

    def _get(self, path, origin):
        self._ctx.__exit__(None, None, None)
        try:
            return self.main.app.test_client().get(path, headers={"Origin": origin})
        finally:
            self._ctx = self.ndb_client.context()
            self._ctx.__enter__()

    def test_the_board_routes_answer_twitch(self):
        for path in ("/bingo/game/7/fetch", "/bingo/userboard/nobody/fetch/-1"):
            res = self._get(path, TWITCH)
            self.assertEqual(res.headers.get("Access-Control-Allow-Origin"), TWITCH, path)
            self.assertIn("Origin", res.headers.get("Vary", ""), path)

    def test_local_test_serves_from_https_localhost(self):
        res = self._get("/bingo/game/7/fetch", "https://localhost:8443")
        self.assertEqual(res.headers.get("Access-Control-Allow-Origin"), "https://localhost:8443")
        res = self._get("/bingo/game/7/fetch", "http://localhost:8443")
        self.assertIsNone(res.headers.get("Access-Control-Allow-Origin"))

    def test_other_origins_and_routes_get_nothing(self):
        for path, origin in (("/bingo/game/7/fetch", "https://evil.example"),
                             ("/bingo/game/7/fetch", "https://x.ext-twitch.tv.evil.example"),
                             ("/bingo/game/7/seed/1", TWITCH),
                             ("/bingo/game/7/marks/1?squares=1", TWITCH)):
            res = self._get(path, origin)
            self.assertIsNone(res.headers.get("Access-Control-Allow-Origin"), (path, origin))

    def test_a_refusal_still_varies_on_origin(self):
        res = self._get("/bingo/game/7/fetch", "https://evil.example")
        self.assertIn("Origin", res.headers.get("Vary", ""))


if __name__ == "__main__":
    unittest.main()
