"""GUEST_USERS: every beta visitor is their own throwaway account.

The seat rides the session cookie, so distinct browsers must get distinct
users and one browser must keep its user across visits. Flag off, the OIDC
testing profile behaves exactly as before -- local dev and the whole rest of
the suite depend on that.

Run from the repo root:  python -m unittest test.guest_users_test -v
"""
import unittest

from test.ndb_base import EmulatorTestCase


class GuestUsersTestCase(EmulatorTestCase):

    def setUp(self):
        super(GuestUsersTestCase, self).setUp()
        import main
        import models
        import util
        self.main, self.util = main, util
        # requests ride the wsgi middleware, which opens models.client's context
        self._models_client, models.client = models.client, self.ndb_client
        self.models = models
        self._flag = util.GUEST_USERS
        self._secret = main.app.secret_key
        main.app.secret_key = main.app.secret_key or "guest-test"
        util.GUEST_USERS = True

    def tearDown(self):
        self.models.client = self._models_client
        self.util.GUEST_USERS = self._flag
        self.main.app.secret_key = self._secret
        super(GuestUsersTestCase, self).tearDown()

    def _whoami(self, client):
        # the middleware opens its own context; the harness's outer one has to
        # step aside for the duration of the request
        self._ctx.__exit__(None, None, None)
        try:
            res = client.get("/user/settings")
        finally:
            self._ctx = self.ndb_client.context()
            self._ctx.__enter__()
        self.assertEqual(res.status_code, 200, res.data)
        return res.get_json().get("name")

    def test_two_browsers_are_two_users(self):
        a = self.main.app.test_client()
        b = self.main.app.test_client()
        name_a, name_b = self._whoami(a), self._whoami(b)
        self.assertTrue(name_a.startswith("Guest-"), name_a)
        self.assertTrue(name_b.startswith("Guest-"), name_b)
        self.assertNotEqual(name_a, name_b, "two cookie jars shared a user")

    def test_one_browser_keeps_its_user(self):
        c = self.main.app.test_client()
        self.assertEqual(self._whoami(c), self._whoami(c),
                         "the cookie did not bring the same user back")

    def test_the_guest_is_a_real_stored_user(self):
        from models import User
        c = self.main.app.test_client()
        name = self._whoami(c)
        found = User.get_by_name(name)
        self.assertIsNotNone(found, "guests must survive a name query")
        self.assertTrue(found.key.id().startswith("guest-"))
        self.assertTrue(found.email.endswith("@guests.invalid"))

    def test_flag_off_keeps_the_testing_profile(self):
        self.util.GUEST_USERS = False
        c = self.main.app.test_client()
        name = self._whoami(c)
        self.assertFalse((name or "").startswith("Guest-"),
                         "flag off must fall back to the OIDC testing profile")


if __name__ == "__main__":
    unittest.main()
