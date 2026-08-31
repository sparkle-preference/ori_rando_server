"""Redirect scheme + HSTS behind the TLS-terminating proxy.

Drives the real WSGI stack (ProxyFix > ndb middleware > Flask) via test_client.
Trailing-slash redirects resolve during routing, so no datastore is needed.

Run from the repo root:  python3 -m unittest test.proxy_headers_test -v
"""
import contextlib
import unittest
from datetime import timedelta

import main
import models
import util

# unittest imports every named module before it runs anything, so nothing has
# served a request yet: this is the app's import-time value.
LIFETIME_AT_IMPORT = main.app.permanent_session_lifetime


class _FakeNdbClient(object):
    """Stands in for models.client, which is None without credentials."""

    def context(self):
        return contextlib.nullcontext()


class ProxyHeadersTestCase(unittest.TestCase):
    def setUp(self):
        self._client = models.client
        models.client = _FakeNdbClient()
        # flask-oidc's before_request writes to the session
        self._secret = main.app.secret_key
        main.app.secret_key = main.app.secret_key or "proxy-headers-test"
        self.client = main.app.test_client()

    def tearDown(self):
        models.client = self._client
        main.app.secret_key = self._secret

    # defined only with a trailing slash, so this path triggers the redirect
    SLASHED = "/bingo/userboard/eiko"

    def test_forwarded_proto_https_keeps_redirects_on_https(self):
        r = self.client.get(self.SLASHED, headers={"X-Forwarded-Proto": "https"},
                            base_url="http://orirando.com")
        self.assertIn(r.status_code, (301, 308))
        self.assertTrue(r.headers["Location"].startswith("https://"),
                        "downgraded to %s" % r.headers["Location"])
        self.assertEqual(r.headers["Location"], "https://orirando.com/bingo/userboard/eiko/")

    def test_forwarded_host_is_honored(self):
        r = self.client.get(self.SLASHED,
                            headers={"X-Forwarded-Proto": "https", "X-Forwarded-Host": "orirando.com"},
                            base_url="http://internal-cloud-run-host")
        self.assertEqual(r.headers["Location"], "https://orirando.com/bingo/userboard/eiko/")

    def test_plain_http_still_redirects_to_http(self):
        r = self.client.get(self.SLASHED, base_url="http://orirando.com")
        self.assertTrue(r.headers["Location"].startswith("http://"))

    def test_hsts_sent_on_https_without_include_subdomains(self):
        # includeSubDomains would pin bfnc.orirando.com to https, killing the dll
        r = self.client.get("/version/latest", headers={"X-Forwarded-Proto": "https"},
                            base_url="http://orirando.com")
        hsts = r.headers.get("Strict-Transport-Security")
        self.assertIsNotNone(hsts)
        self.assertIn("max-age=", hsts)
        self.assertNotIn("includeSubDomains", hsts)

    def test_no_hsts_on_plaintext_responses(self):
        r = self.client.get("/version/latest", base_url="http://orirando.com")
        self.assertIsNone(r.headers.get("Strict-Transport-Security"))


class CanonicalRedirectTestCase(unittest.TestCase):
    """The orirando.com -> bf.orirando.com move: browser traffic on the old
    host 301s to the canonical one; the dll fleet's /netcode/ surface and every
    unlisted host (bfnc!) must never see a redirect."""

    def setUp(self):
        self._client = models.client
        models.client = _FakeNdbClient()
        self._secret = main.app.secret_key
        main.app.secret_key = main.app.secret_key or "proxy-headers-test"
        self._canonical, self._hosts = util.CANONICAL_HOST, util.REDIRECT_HOSTS
        util.CANONICAL_HOST = "bf.orirando.com"
        util.REDIRECT_HOSTS = ["orirando.com"]
        self.client = main.app.test_client()

    def tearDown(self):
        util.CANONICAL_HOST, util.REDIRECT_HOSTS = self._canonical, self._hosts
        models.client = self._client
        main.app.secret_key = self._secret

    def test_old_host_page_redirects_with_path_and_query(self):
        r = self.client.get("/faq?g=install", headers={"X-Forwarded-Proto": "https"},
                            base_url="http://orirando.com")
        self.assertEqual(r.status_code, 301)
        self.assertEqual(r.headers["Location"], "https://bf.orirando.com/faq?g=install")

    def test_bare_path_has_no_stray_question_mark(self):
        r = self.client.get("/version/latest", base_url="http://orirando.com")
        self.assertEqual(r.status_code, 301)
        self.assertEqual(r.headers["Location"], "https://bf.orirando.com/version/latest")

    def test_unlisted_host_is_untouched(self):
        # bfnc.orirando.com (the dll's plain-http host) must never redirect
        r = self.client.get("/version/latest", base_url="http://bfnc.orirando.com")
        self.assertEqual(r.status_code, 200)

    def test_netcode_paths_never_redirect_even_on_old_host(self):
        # the pre-move wss fleet connects to orirando.com/netcode/...
        r = self.client.get("/netcode/areas", base_url="http://orirando.com")
        self.assertNotEqual(r.status_code, 301)

    def test_posts_never_redirect(self):
        # 405 (GET-only route), never a 301 that would swallow the body
        r = self.client.post("/version/latest", base_url="http://orirando.com")
        self.assertNotEqual(r.status_code, 301)

    def test_unset_is_inert(self):
        util.CANONICAL_HOST, util.REDIRECT_HOSTS = "", []
        r = self.client.get("/version/latest", base_url="http://orirando.com")
        self.assertEqual(r.status_code, 200)


class SessionCookieTestCase(unittest.TestCase):
    """The login cookie survives a browser restart, and nothing else gets one.

    Flask-OIDC's OIDC_ENABLED=False path plants a token in the session on every
    request whenever OIDC_TESTING_PROFILE is non-empty, which is how these tests
    switch between a logged-in and an anonymous visitor.
    """

    def setUp(self):
        self._client = models.client
        models.client = _FakeNdbClient()
        self._secret = main.app.secret_key
        main.app.secret_key = main.app.secret_key or "session-cookie-test"
        self._enabled = main.app.config["OIDC_ENABLED"]
        self._profile = main.app.config.get("OIDC_TESTING_PROFILE")
        main.app.config["OIDC_ENABLED"] = False

    def tearDown(self):
        models.client = self._client
        main.app.secret_key = self._secret
        main.app.config["OIDC_ENABLED"] = self._enabled
        main.app.config["OIDC_TESTING_PROFILE"] = self._profile

    def _logged_in(self):
        main.app.config["OIDC_TESTING_PROFILE"] = {"email": "t@example.com", "sub": "1"}
        return main.app.test_client()

    def _anonymous(self):
        main.app.config["OIDC_TESTING_PROFILE"] = {}
        return main.app.test_client()

    def test_lifetime_is_set_before_the_first_request(self):
        # open_session reads it during context push, so a before_request hook is
        # too late: the first request each worker serves would fall back to
        # Flask's 31-day default and reject older cookies.
        self.assertEqual(LIFETIME_AT_IMPORT, timedelta(days=365))

    def test_login_cookie_outlives_the_browser(self):
        r = self._logged_in().get("/version/latest")
        self.assertIn("Expires=", r.headers.get("Set-Cookie", ""))

    def test_cookie_is_reissued_on_every_response(self):
        # what makes the year-long window roll rather than expire from the login
        client = self._logged_in()
        first = client.get("/version/latest").headers["Set-Cookie"]
        second = client.get("/version/latest").headers["Set-Cookie"]
        self.assertIn("Expires=", first)
        self.assertIn("Expires=", second)
        self.assertEqual(first.split(".")[0], second.split(".")[0])  # same session

    def test_anonymous_visitors_get_no_cookie(self):
        r = self._anonymous().get("/version/latest")
        self.assertIsNone(r.headers.get("Set-Cookie"))

    def test_netcode_surface_gets_no_cookie(self):
        # the dll fleet has no cookie jar; every byte here is dead weight
        r = self._anonymous().get("/netcode/areas")
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.headers.get("Set-Cookie"))

    def test_logout_deletes_the_cookie(self):
        client = self._logged_in()
        client.get("/version/latest")
        r = client.get("/logout")
        # flask-oidc only pops its own keys; an emptied session is what makes
        # Flask send the deletion
        self.assertIn("Expires=Thu, 01 Jan 1970", r.headers.get("Set-Cookie", ""))


if __name__ == "__main__":
    unittest.main()
