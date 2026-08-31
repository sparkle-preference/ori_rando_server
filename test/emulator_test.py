"""The paths stubs cannot reach: real queries, real transactions, real puts."""
import unittest
from web import bingo as bingo_routes

from flask import g

from test.ndb_base import EmulatorTestCase
from web import presets


class _AppUser(object):
    """The oidc user shape User.get reads."""

    def __init__(self, unique_id, email, name=None):
        self.logged_in = True
        self.unique_id = unique_id
        self.email = email
        self.name = name


class UserPersistenceTestCase(EmulatorTestCase):
    """A user someone can look up by name has to actually be in the datastore."""

    def test_put_then_name_query(self):
        from models import User
        User(id="u-1", email="a@b.c", name="alpha", teamname="alpha's team").put()
        found = User.get_by_name("alpha")
        self.assertIsNotNone(found)
        self.assertEqual(found.key.id(), "u-1")

    def test_a_new_login_is_immediately_queryable(self):
        import main
        from models import User
        with main.app.test_request_context():
            g.oidc_user = _AppUser("31337", "fresh@example.com", "fresh")
            user = User.get()
        self.assertIsNotNone(user)
        self.assertIsNotNone(User.get_by_name("fresh"),
                             "created users must survive a name query, not just a key get")

    def test_a_migrated_login_is_immediately_queryable(self):
        import main
        from models import LegacyUser, User
        LegacyUser(id="old@example.com", email="old@example.com",
                   name="oldtimer", teamname="oldtimer's team").put()
        with main.app.test_request_context():
            g.oidc_user = _AppUser("777", "old@example.com")
            user = User.get()
        self.assertEqual(user.key.id(), "777")
        self.assertEqual(User.get_by_name("oldtimer").key.id(), "777",
                         "the name query must land on the migrated row")


class TransactionalRenameTestCase(EmulatorTestCase):
    """presets._rename_preset through a real transaction, not the unwrapped body."""

    def _user_with(self, *preset_names):
        from models import SavedSeedParams, User
        user = User(id="u-9", email="p@q.r", name="pat", teamname="t")
        user.put()
        for name in preset_names:
            SavedSeedParams(id="u-9:%s" % name, name=name, owner_key=user.key,
                            settings={"keyMode": "Clues"}, description="d").put()
        return user

    def test_rename_moves_the_preset(self):
        import main
        user = self._user_with("warps")
        problem = presets._rename_preset(user, "warps", "warps2", "new desc", True)
        self.assertIsNone(problem)
        self.assertIsNone(user.saved_params("warps"))
        moved = user.saved_params("warps2")
        self.assertEqual(moved.settings, {"keyMode": "Clues"})
        self.assertEqual(moved.description, "new desc")
        self.assertTrue(moved.hidden)

    def test_missing_preset_is_a_problem_string(self):
        import main
        user = self._user_with()
        self.assertEqual(presets._rename_preset(user, "ghost", "x", "", False),
                         "no preset named ghost")

    def test_occupied_target_changes_nothing(self):
        import main
        user = self._user_with("a", "b")
        problem = presets._rename_preset(user, "a", "b", "", False)
        self.assertEqual(problem, "you already have a preset named b")
        self.assertIsNotNone(user.saved_params("a"))
        self.assertEqual(user.saved_params("b").description, "d")


class AdminAndRecreateGateTestCase(EmulatorTestCase):
    """Who may rebuild a live bingo board, and who counts as an admin at all."""

    def _login(self, uid, email, name):
        from models import User
        import main
        with main.app.test_request_context():
            g.oidc_user = _AppUser(uid, email, name)
            return User.get()

    def test_is_admin_reads_the_flag_not_the_method(self):
        import main
        from models import User
        user = self._login("100", "pleb@example.com", "pleb")
        with main.app.test_request_context():
            g.oidc_user = _AppUser("100", "pleb@example.com", "pleb")
            self.assertFalse(User.is_admin(), "a plain user must not pass admin checks")
            user.admin = True
            user.put()
            self.assertTrue(User.is_admin())

    def _game_with_board(self, owner):
        from models import BingoGameData, Game
        game = Game(id=41)
        bingo = BingoGameData(id=41, game=game.key)
        if owner is not None:
            bingo.creator = owner.key
        game.bingo_data = bingo.put()
        game.put()
        return game, bingo

    def test_the_owner_may_recreate(self):
        import main
        owner = self._login("200", "own@example.com", "own")
        game, bingo = self._game_with_board(owner)
        with main.app.test_request_context():
            g.oidc_user = _AppUser("200", "own@example.com", "own")
            self.assertIsNone(bingo_routes._bingo_recreate_problem(game, bingo))

    def test_a_stranger_may_not(self):
        import main
        owner = self._login("200", "own@example.com", "own")
        self._login("300", "other@example.com", "other")
        game, bingo = self._game_with_board(owner)
        with main.app.test_request_context():
            g.oidc_user = _AppUser("300", "other@example.com", "other")
            self.assertIsNotNone(bingo_routes._bingo_recreate_problem(game, bingo))

    def test_an_admin_may(self):
        import main
        owner = self._login("200", "own@example.com", "own")
        boss = self._login("400", "boss@example.com", "boss")
        boss.admin = True
        boss.put()
        game, bingo = self._game_with_board(owner)
        with main.app.test_request_context():
            g.oidc_user = _AppUser("400", "boss@example.com", "boss")
            self.assertIsNone(bingo_routes._bingo_recreate_problem(game, bingo))

    def test_an_anonymous_board_is_admin_only(self):
        import main
        self._login("300", "other@example.com", "other")
        game, bingo = self._game_with_board(None)
        with main.app.test_request_context():
            g.oidc_user = _AppUser("300", "other@example.com", "other")
            self.assertIsNotNone(bingo_routes._bingo_recreate_problem(game, bingo),
                                 "no owner on record means only an admin rebuilds")


if __name__ == "__main__":
    unittest.main()
