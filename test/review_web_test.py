"""Web-layer and helper regressions: auth, input validation, and helper edge cases."""
import contextlib
import random
import unittest
from urllib.parse import quote, urlsplit

import main
import models
import util
from models import Game, Seed, User
from test.ndb_base import EmulatorTestCase, NdbTestCase


class _OuterContext(object):
    """Hands the request middleware the context the test is already inside."""

    def context(self):
        return contextlib.nullcontext()


class _Routes(EmulatorTestCase):
    def setUp(self):
        super(_Routes, self).setUp()
        self._user_get = User.__dict__["get"]
        self.user = None
        User.get = staticmethod(lambda: self.user)
        self.addCleanup(setattr, User, "get", self._user_get)
        self._ndb_client = models.client
        models.client = _OuterContext()
        self.addCleanup(setattr, models, "client", self._ndb_client)
        self._secret = main.app.secret_key
        main.app.secret_key = main.app.secret_key or "review-test"
        self.addCleanup(setattr, main.app, "secret_key", self._secret)
        self.client = main.app.test_client()

    def game(self, gid, **kw):
        g = Game(id=gid, players=[], str_shared=[], str_mode="None", has_history=True, **kw)
        g.put()
        return g

    def author(self, uid="rv-1", name="pat"):
        user = User(id=uid, email="%s@example.com" % name, name=name, teamname="team")
        user.put()
        self.user = user
        return user


class GameRoutesTestCase(_Routes):
    def admin(self):
        user = self.author("rv-admin", "boss")
        user.admin = True
        user.put()
        return user

    def test_a_stranger_cannot_delete_a_game(self):
        self.game(123456)
        r = self.client.get("/game/123456/delete/")
        self.assertIn(r.status_code, (401, 403))
        self.assertIsNotNone(Game.get_by_id(123456))

    def test_the_creator_can_delete_their_game(self):
        owner = self.author()
        self.game(123460, creator=owner.key)
        self.assertEqual(self.client.get("/game/123460/delete/").status_code, 200)
        self.assertIsNone(Game.get_by_id(123460))

    def test_old_games_need_override_even_for_admins(self):
        self.admin()
        self.game(9999)
        self.assertEqual(self.client.get("/game/9999/delete/").status_code, 403)
        self.assertEqual(self.client.get("/game/9999/delete/?override=1").status_code, 200)

    def test_remove_player_answers_without_a_500(self):
        self.game(123457)
        r = self.client.get("/game/123457/player/1/remove/")
        self.assertNotEqual(r.status_code, 500)

    def test_a_stranger_cannot_remove_a_player(self):
        g = self.game(123461)
        g.player(1)
        self.assertEqual(self.client.get("/game/123461/player/1/remove/").status_code, 403)
        self.assertEqual(Game.get_by_id(123461).player_nums(), [1])

    def test_generator_json_does_not_replace_a_live_game(self):
        owner = self.author()
        self.game(123458, creator=owner.key)
        self.user = None
        r = self.client.get("/generator/json?seed=review&logic_mode=standard&game_id=123458")
        self.assertEqual(r.status_code, 409)
        g = Game.get_by_id(123458)
        self.assertIsNone(g.params, "a stranger's seed was attached to an existing game")
        self.assertEqual(g.creator, owner.key)

    def test_generator_json_takes_a_free_game_id(self):
        r = self.client.get("/generator/json?seed=review&logic_mode=standard&game_id=123459")
        self.assertEqual(r.status_code, 200)
        self.assertIsNotNone(Game.get_by_id(123459).params)

    def test_cache_clear_needs_credentials(self):
        self.assertIn(self.client.get("/cache/clear").status_code, (401, 403))
        self.assertIn(self.client.get("/clean/").status_code, (401, 403))

    def test_admins_may_clear(self):
        self.admin()
        self.assertEqual(self.client.get("/cache/clear").status_code, 200)


class PageRoutesTestCase(_Routes):
    def redirects_home(self, url):
        r = self.client.get(url)
        self.assertEqual(r.status_code, 302)
        return urlsplit(r.headers["Location"])

    def test_theme_toggle_without_redir(self):
        self.assertEqual(self.redirects_home("/theme/toggle").path, "/")

    def test_theme_toggle_only_follows_same_site_paths(self):
        for evil in ("https://evil.example/", "//evil.example/", "/\\evil.example/", "/\t/evil.example/"):
            loc = self.redirects_home("/theme/toggle?redir=" + quote(evil, safe=""))
            self.assertIn(loc.netloc, ("", "localhost"), evil)
            self.assertEqual(loc.path, "/", evil)
        loc = self.redirects_home("/theme/toggle?redir=" + quote("/plando/pat?x=1", safe=""))
        self.assertEqual((loc.path, loc.query), ("/plando/pat", "x=1"))

    def test_bingo_new_with_too_many_skills_is_not_a_500(self):
        self.assertEqual(self.client.get("/bingo/new?skills=11&cells=0&seed=x").status_code, 200)

    def test_bingo_new_caps_the_cell_count(self):
        self.assertEqual(self.client.get("/bingo/new?skills=0&cells=100000000&seed=x").status_code, 200)

    def test_malformed_numbers_are_400s(self):
        for url in ("/bingo/new?cells=lots", "/bingo/new?discCount=x", "/activeGames/soon/",
                    "/bingo/userboard/pat/fetch/abc", "/tracker/game/1/fetch/update"):
            self.assertEqual(self.client.get(url).status_code, 400, url)

    def test_items_for_a_gone_game_with_cached_coords(self):
        from cache import Cache
        Cache.set_have(777001, {1: [2]})
        self.assertEqual(self.client.get("/tracker/game/777001/fetch/items/1").status_code, 404)

    def test_transfer_to_a_missing_player_creates_nobody(self):
        owner = self.author()
        g = self.game(123470, creator=owner.key)
        self.assertEqual(self.client.get("/transfer/123470/5").status_code, 404)
        self.assertIsNone(models.Player.get_by_id("123470.5", parent=g.key))

    def test_race_guard_tolerates_a_game_without_params(self):
        import os
        if not os.path.exists(os.path.join(util.template_root, util.INDEX_TEMPLATE)):
            self.skipTest("no built page")
        self.game(123471)
        self.assertEqual(self.client.get("/tracker/game/123471/").status_code, 200)

    def test_an_unknown_author_name_is_escaped(self):
        body = self.client.get("/plando/%3Cscript%3Ex%3C%2Fscript%3E").get_data(as_text=True)
        self.assertNotIn("<script>x</script>", body)

    # the owner view shares the line with the public one
    def test_author_index_escapes_descriptions(self):
        user = self.author()
        Seed(id="%s:alpha" % user.key.id(), name="alpha", author=user.name, author_key=user.key,
             description="<script>alert(1)</script>", flags=["ForceTrees"], players=1).put()
        body = self.client.get("/plando/pat").get_data(as_text=True)
        self.assertIn("alpha", body)
        self.assertNotIn("<script>alert(1)</script>", body)

    def test_upload_rename_onto_an_existing_plando_changes_nothing(self):
        import json
        user = self.author()
        for name, desc in (("alpha", "the one being renamed"), ("beta", "already here")):
            Seed(id="%s:%s" % (user.key.id(), name), name=name, author=user.name,
                 author_key=user.key, description=desc, flags=["ForceTrees"], players=1).put()
        body = {"oldName": "alpha", "name": "beta", "desc": "the one being renamed",
                "flags": ["ForceTrees"], "placements": []}
        r = self.client.post("/plando/beta/upload", data={"seed": json.dumps(body)})
        self.assertEqual(r.status_code, 409)
        self.assertEqual(Seed.get_by_id("%s:beta" % user.key.id()).description, "already here")
        self.assertIsNotNone(Seed.get_by_id("%s:alpha" % user.key.id()))

    def test_unreadable_plando_bodies_are_400s(self):
        self.author()
        self.assertEqual(self.client.post("/plando/x/upload", data={"seed": "{"}).status_code, 400)
        self.assertEqual(self.client.post("/plando/reachable", data={"modes": "[]"}).status_code, 400)


class BitfieldTestCase(unittest.TestCase):
    def test_removing_an_unheld_bit_below_the_value_changes_nothing(self):
        self.assertEqual(util.add_single(0, 4, remove=True), 0)

    def test_removing_an_unheld_bit_leaves_other_bits_alone(self):
        self.assertEqual(util.add_single(4, 1, remove=True), 4)

    def test_removing_a_held_bit(self):
        self.assertEqual(util.add_single(5, 4, remove=True), 1)


class VersionCheckTestCase(unittest.TestCase):
    def test_a_short_version_is_not_current(self):
        self.assertFalse(util.version_check("4"))
        self.assertTrue(util.version_check("%s.%s.%s" % tuple(util.MIN_VER)))

    def test_version_at_least_pads(self):
        self.assertFalse(util.version_at_least("4", [4, 9, 8]))


class WhitelistTestCase(unittest.TestCase):
    def whitelisted(self, secret, url):
        saved = util.whitelist_secret
        util.whitelist_secret = secret
        try:
            with main.app.test_request_context(url):
                return util.whitelist_ok()
        finally:
            util.whitelist_secret = saved

    def test_no_secret_whitelists_nobody(self):
        self.assertFalse(self.whitelisted(None, "/"))
        self.assertFalse(self.whitelisted("", "/?sec="))

    def test_the_secret_whitelists(self):
        self.assertTrue(self.whitelisted("s3", "/?sec=s3"))
        self.assertFalse(self.whitelisted("s3", "/?sec=s4"))
        self.assertFalse(self.whitelisted("s3", "/?sec=%C3%A9"))


class ParamIntTestCase(unittest.TestCase):
    def test_absent_empty_clamped_and_malformed(self):
        from werkzeug.exceptions import BadRequest
        with main.app.test_request_context("/?a=&b=7&c=x"):
            self.assertEqual(util.param_int("a", 3), 3)
            self.assertEqual(util.param_int("missing", 3), 3)
            self.assertEqual(util.param_int("b", 0, 0, 5), 5)
            self.assertEqual(util.param_int("b", 0, 9), 9)
            with self.assertRaises(BadRequest):
                util.param_int("c")


class BoardDeterminismTestCase(NdbTestCase):
    def test_a_board_seed_reproduces_its_board(self):
        from bingo import BingoGenerator

        def board(seed):
            rand = random.Random()
            rand.seed(seed)
            return [c.name for c in BingoGenerator.get_cards(rand, 25, False, "normal", True, 0, True)]

        for i in range(300):
            names = board("sym%d" % i)
            if "HorizSym" in names and "VertSym" in names:
                for _ in range(8):
                    self.assertEqual(board("sym%d" % i), names)
                return
        self.skipTest("no seed rolled both symmetry squares")



class SockOptionsTestCase(unittest.TestCase):
    def test_pings_only_when_configured(self):
        from web.extensions import sock_server_options
        self.assertNotIn("ping_interval", sock_server_options(0))
        self.assertEqual(sock_server_options(25)["ping_interval"], 25)
        self.assertEqual(sock_server_options(25)["max_message_size"], 1 << 20)



class GeneratorInputTestCase(_Routes):
    def test_no_logic_paths_is_a_422_with_a_reason(self):
        import json
        r = self.client.post("/generator/build", data={"params": json.dumps({"seed": "x", "paths": []})})
        self.assertEqual(r.status_code, 422)
        self.assertIn("logic path", r.get_data(as_text=True))

    def test_blank_spawn_weights_read_as_zero(self):
        from seedbuilder.seedparams import SeedGenParams, spawn_weights
        self.assertEqual(spawn_weights([1, None, 2.5, "x"]), [1.0, 0.0, 2.5, 0.0])
        self.assertEqual(spawn_weights(None), [])
        key = SeedGenParams.from_json({"seed": "x", "paths": ["casual-core"], "spawnWeights": [1, None]})
        self.assertEqual(key.get().spawn_weights, [1.0, 0.0])


if __name__ == "__main__":
    unittest.main()
