"""A first-time user has to be stored, not just built.

User.get() builds an entity for an unseen user; until it is stored, every lookup
by name misses -- and share links resolve their owner by name.
"""
import unittest


import models
from models import User
from test.ndb_base import NdbTestCase


class _AppUser(object):
    def __init__(self, uid="9999", email="second@example.com", name=None, logged_in=True):
        self.unique_id = uid
        self.email = email
        self.name = name
        self.logged_in = logged_in


class _G(object):
    """flask's g, as far as User.get() cares."""
    def __init__(self, app_user):
        self.oidc_user = app_user


class UserCreateTestCase(NdbTestCase):
    def setUp(self):
        self._ctx = self.ndb_client.context()
        self._ctx.__enter__()
        self.put_calls = []
        self.by_id = None
        self.legacy = []
        self._g, self._get_by_id, self._put = models.g, User.get_by_id, User.put
        self._legacy_query = models.LegacyUser.query
        User.get_by_id = staticmethod(lambda uid: self.by_id)
        User.put = lambda user: self.put_calls.append(user)
        models.LegacyUser.query = staticmethod(lambda *a, **kw: _FakeQuery(self.legacy))

    def tearDown(self):
        models.g, User.get_by_id, User.put = self._g, self._get_by_id, self._put
        models.LegacyUser.query = self._legacy_query
        self._ctx.__exit__(None, None, None)

    def get(self, app_user):
        models.g = _G(app_user)
        return User.get()

    def test_a_first_time_user_is_stored(self):
        user = self.get(_AppUser())
        self.assertIsNotNone(user)
        self.assertEqual(user.name, "second", "the email prefix names them")
        self.assertEqual(self.put_calls, [user], "an unstored owner cannot be found by name")

    def test_a_known_user_is_not_rewritten(self):
        self.by_id = User(id="9999")
        self.by_id.name = "second"
        user = self.get(_AppUser())
        self.assertIs(user, self.by_id)
        self.assertEqual(self.put_calls, [], "an existing user needs no write on every request")

    def test_a_logged_out_visitor_creates_nothing(self):
        self.assertIsNone(self.get(_AppUser(logged_in=False)))
        self.assertEqual(self.put_calls, [])

    def test_an_ambiguous_legacy_email_stores_nothing(self):
        """Two legacy rows on one email is a refusal, not a new user."""
        self.legacy = [_Legacy("a"), _Legacy("b")]
        self.assertIsNone(self.get(_AppUser()))
        self.assertEqual(self.put_calls, [])


class _FakeQuery(object):
    def __init__(self, rows):
        self.rows = rows

    def fetch(self):
        return self.rows


class _Legacy(object):
    def __init__(self, uid):
        self.id = uid
        self.name = uid
        self.teamname = "%s's team" % uid
        self.games, self.theme, self.dark_theme = [], None, False


if __name__ == "__main__":
    unittest.main()
