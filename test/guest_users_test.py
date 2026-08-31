"""GUEST_USERS: every beta visitor is their own throwaway account.

The seat rides the session cookie, so distinct browsers must get distinct
users and one browser must keep its user across visits. Flag off, the OIDC
testing profile behaves exactly as before -- local dev and the whole rest of
the suite depend on that.

Run from the repo root:  python -m unittest test.guest_users_test -v
"""
import unittest

from test.ndb_base import EmulatorTestCase


class _GuestHarness(EmulatorTestCase):
    """Stubs only -- no tests. Subclassing a TestCase re-runs its tests."""

    def setUp(self):
        super(_GuestHarness, self).setUp()
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
        super(_GuestHarness, self).tearDown()

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


class GuestUsersTestCase(_GuestHarness):

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

    def test_prod_shape_refuses_even_a_stray_flag(self):
        """K_REVISION not dev-ish = prod. A leaked GUEST_USERS=1 there must
        do nothing; real OIDC is latch two, this pins latch three."""
        self._debug, self.util.is_debug = self.util.is_debug, False
        try:
            c = self.main.app.test_client()
            name = self._whoami(c)
            self.assertFalse((name or "").startswith("Guest-"),
                             "a prod revision minted a guest")
        finally:
            self.util.is_debug = self._debug

    def test_flag_off_keeps_the_testing_profile(self):
        self.util.GUEST_USERS = False
        c = self.main.app.test_client()
        name = self._whoami(c)
        self.assertFalse((name or "").startswith("Guest-"),
                         "flag off must fall back to the OIDC testing profile")


class BetaClaimTestCase(_GuestHarness):
    """The claim route: right secret = this browser is the testing account;
    anything else = 404 and the guest stays a guest."""

    SECRET = "beta-claim-test-secret"

    def setUp(self):
        super(BetaClaimTestCase, self).setUp()
        import os
        self._env = {k: os.environ.get(k) for k in ("GUEST_CLAIM_SECRET", "OIDC_USER_ID")}
        os.environ["GUEST_CLAIM_SECRET"] = self.SECRET
        os.environ["OIDC_USER_ID"] = "claim-target-uid"
        from models import User
        User(id="claim-target-uid", email="t@example.com", name="TheTester",
             teamname="t's team").put()

    def tearDown(self):
        import os
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        super(BetaClaimTestCase, self).tearDown()

    def _claim(self, client, secret):
        self._ctx.__exit__(None, None, None)
        try:
            return client.get("/beta/claim/%s" % secret)
        finally:
            self._ctx = self.ndb_client.context()
            self._ctx.__enter__()

    def test_the_right_secret_takes_the_testing_seat(self):
        c = self.main.app.test_client()
        before = self._whoami(c)
        self.assertTrue(before.startswith("Guest-"))
        res = self._claim(c, self.SECRET)
        self.assertEqual(res.status_code, 302)
        self.assertEqual(self._whoami(c), "TheTester")

    def test_a_wrong_secret_changes_nothing(self):
        c = self.main.app.test_client()
        before = self._whoami(c)
        res = self._claim(c, "nope")
        self.assertEqual(res.status_code, 404)
        self.assertEqual(self._whoami(c), before)

    def test_no_secret_configured_means_no_route(self):
        import os
        os.environ.pop("GUEST_CLAIM_SECRET", None)
        c = self.main.app.test_client()
        res = self._claim(c, "")
        self.assertEqual(res.status_code, 404)

    def test_only_the_claimer_is_affected(self):
        a, b = self.main.app.test_client(), self.main.app.test_client()
        self._claim(a, self.SECRET)
        self.assertEqual(self._whoami(a), "TheTester")
        self.assertTrue(self._whoami(b).startswith("Guest-"),
                        "the claim leaked across sessions")


if __name__ == "__main__":
    unittest.main()
