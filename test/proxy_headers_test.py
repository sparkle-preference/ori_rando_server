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


if __name__ == "__main__":
    unittest.main()
