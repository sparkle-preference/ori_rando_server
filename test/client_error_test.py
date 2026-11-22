"""The page's crash reports land in the log on every box, within a budget.

Run from the repo root:  python3 -m unittest test.client_error_test -v
"""
import contextlib
import io
import json
import unittest
from unittest import mock

import main
import models
import util
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
        with self.assertLogs(level="WARNING") as logs:
            resp = self._post({"kind": "render", "message": "Cannot read properties of null", "stack": "at dE.paramsJson",
                               "app": "MainPage", "version": "4.9.2", "url": "https://bfbeta.eiko.blue/"})
        self.assertEqual(resp.status_code, 204)
        line = "\n".join(logs.output)
        self.assertIn("CLIENTERR app=MainPage ver=4.9.2 kind=render", line)
        self.assertIn("Cannot read properties of null", line)
        self.assertIn("at dE.paramsJson", line)
        # a browser's crash is no server fault: prod's ERROR entries stay the server's own
        self.assertEqual([r.levelname for r in logs.records], ["WARNING"])

    def test_an_oversized_report_is_refused(self):
        resp = self.client.post("/client_error", data="x" * (meta.CLIENT_ERROR_MAX_BYTES + 1), content_type="application/json")
        self.assertEqual(resp.status_code, 413)

    def test_the_budget_holds(self):
        meta.CLIENT_ERROR_BUDGET = (2, 600)
        with self.assertLogs(level="WARNING"):
            self.assertEqual(self._post({"message": "one"}).status_code, 204)
            self.assertEqual(self._post({"message": "two"}).status_code, 204)
        self.assertEqual(self._post({"message": "three"}).status_code, 429)

    def test_a_release_build_on_prod_logs_them_too(self):
        with mock.patch.object(util, "BETA_OF", None), mock.patch.object(util, "is_debug", False):
            with self.assertLogs(level="WARNING") as logs:
                self.assertEqual(self._post({"kind": "window", "message": "prod broke"}).status_code, 204)
        self.assertIn("prod broke", "\n".join(logs.output))

    def test_a_body_that_is_no_report_is_dropped_without_a_line_or_a_slot(self):
        meta.CLIENT_ERROR_BUDGET = (1, 600)
        with self.assertNoLogs(level="WARNING"):
            for junk in ("[1, 2]", '"text"', "{}", '{"kind": "mine"}', "not json", "[" * 5000, "\xff\xfe"):
                resp = self.client.post("/client_error", data=junk.encode("latin-1"), content_type="application/json")
                self.assertEqual(resp.status_code, 204, junk[:20])
            # the page posts json; a cross-site form post is not one
            resp = self.client.post("/client_error", data='{"message": "forged"}', content_type="text/plain")
            self.assertEqual(resp.status_code, 204)
        with self.assertLogs(level="WARNING"):
            self.assertEqual(self._post({"stack": "at x"}).status_code, 204)

    def test_a_rejection_with_no_reason_still_counts(self):
        with self.assertLogs(level="WARNING") as logs:
            self.assertEqual(self._post({"kind": "promise", "message": "", "stack": "", "app": "MainPage"}).status_code, 204)
        self.assertIn("CLIENTERR app=MainPage ver= kind=promise", "\n".join(logs.output))

    def test_half_an_emoji_cannot_break_the_log_write(self):
        # the page cuts by UTF-16 unit, so a slice can end on a lone surrogate
        raw = b'{"kind": "window", "message": "boom \\ud83d", "stack": "at \\udc00 x"}'
        with self.assertLogs(level="WARNING") as logs:
            self.assertEqual(self.client.post("/client_error", data=raw, content_type="application/json").status_code, 204)
        line = logs.records[0].getMessage()
        self.assertEqual(line.encode("utf-8").decode("utf-8"), line)
        self.assertIn("boom", line)

    def test_a_chunked_body_past_the_cap_is_refused(self):
        # no content length to refuse up front: the read itself has to stop
        resp = self.client.post("/client_error", input_stream=io.BytesIO(b"x" * (meta.CLIENT_ERROR_MAX_BYTES + 1)),
                                content_type="application/json",
                                environ_overrides={"wsgi.input_terminated": True, "CONTENT_LENGTH": ""})
        self.assertEqual(resp.status_code, 413)


if __name__ == "__main__":
    unittest.main()
