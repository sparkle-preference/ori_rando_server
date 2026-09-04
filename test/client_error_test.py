"""The page's crash reports land in the log on beta and dev boxes, within a budget.

Run from the repo root:  python3 -m unittest test.client_error_test -v
"""
import contextlib
import json
import unittest

import main
import models
from web import meta


class _FakeNdbClient(object):
    def context(self):
        return contextlib.nullcontext()


class ClientErrorTestCase(unittest.TestCase):
    def setUp(self):
        self._client = models.client
        models.client = _FakeNdbClient()
        self._secret = main.app.secret_key
        main.app.secret_key = main.app.secret_key or "client-error-test"
        self._budget = meta.CLIENT_ERROR_BUDGET
        meta._client_errors.clear()
        self.client = main.app.test_client()

    def tearDown(self):
        models.client = self._client
        main.app.secret_key = self._secret
        meta.CLIENT_ERROR_BUDGET = self._budget
        meta._client_errors.clear()

    def _post(self, body):
        return self.client.post("/client_error", data=json.dumps(body), content_type="application/json")

    def test_a_report_is_logged_with_its_pieces(self):
        with self.assertLogs(level="ERROR") as logs:
            resp = self._post({"kind": "render", "message": "Cannot read properties of null", "stack": "at dE.paramsJson",
                               "app": "MainPage", "version": "4.9.2", "url": "https://bfbeta.eiko.blue/"})
        self.assertEqual(resp.status_code, 204)
        line = "\n".join(logs.output)
        self.assertIn("CLIENTERR app=MainPage ver=4.9.2 kind=render", line)
        self.assertIn("Cannot read properties of null", line)
        self.assertIn("at dE.paramsJson", line)

    def test_an_oversized_report_is_refused(self):
        resp = self.client.post("/client_error", data="x" * (meta.CLIENT_ERROR_MAX_BYTES + 1), content_type="application/json")
        self.assertEqual(resp.status_code, 413)

    def test_the_budget_holds(self):
        meta.CLIENT_ERROR_BUDGET = (2, 600)
        with self.assertLogs(level="ERROR"):
            self.assertEqual(self._post({"message": "one"}).status_code, 204)
            self.assertEqual(self._post({"message": "two"}).status_code, 204)
        self.assertEqual(self._post({"message": "three"}).status_code, 429)


if __name__ == "__main__":
    unittest.main()
