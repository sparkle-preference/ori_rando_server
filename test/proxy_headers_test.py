"""Redirect scheme + HSTS behind the TLS-terminating proxy.

Drives the real WSGI stack (ProxyFix > ndb middleware > Flask) via test_client.
Trailing-slash redirects resolve during routing, so no datastore is needed.

Run from the repo root:  python3 -m unittest test.proxy_headers_test -v
"""
import contextlib
import unittest

import main
import models


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
        self._canonical, self._hosts = main.CANONICAL_HOST, main.REDIRECT_HOSTS
        main.CANONICAL_HOST = "bf.orirando.com"
        main.REDIRECT_HOSTS = ["orirando.com"]
        self.client = main.app.test_client()

    def tearDown(self):
        main.CANONICAL_HOST, main.REDIRECT_HOSTS = self._canonical, self._hosts
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
        main.CANONICAL_HOST, main.REDIRECT_HOSTS = "", []
        r = self.client.get("/version/latest", base_url="http://orirando.com")
        self.assertEqual(r.status_code, 200)


if __name__ == "__main__":
    unittest.main()
