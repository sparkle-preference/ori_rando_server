"""/dll hands out whichever branch's committed dll the deployment is configured
for, so a beta box can serve its own branch while prod keeps serving master.

Run from the repo root:  python3 -m unittest test.dll_redirect_test -v
"""
import contextlib
import unittest

import main
import models
import util


class _FakeNdbClient(object):
    """Stands in for models.client, which is None without credentials."""

    def context(self):
        return contextlib.nullcontext()


class DllRedirectTestCase(unittest.TestCase):
    def setUp(self):
        self._client = models.client
        models.client = _FakeNdbClient()
        self._secret = main.app.secret_key
        main.app.secret_key = main.app.secret_key or "dll-redirect-test"
        self.client = main.app.test_client()
        self._branches = util.DLL_BRANCH, util.DLL_BETA_BRANCH

    def tearDown(self):
        models.client = self._client
        main.app.secret_key = self._secret
        util.DLL_BRANCH, util.DLL_BETA_BRANCH = self._branches

    def _target(self, path):
        r = self.client.get(path)
        self.assertEqual(r.status_code, 302, path)
        return r.headers["Location"]

    def test_the_default_is_master(self):
        util.DLL_BRANCH = util.DLL_BETA_BRANCH = "master"
        self.assertEqual(self._target("/dll"), util.DLL_URL % "master")
        self.assertEqual(self._target("/dll/beta"), util.DLL_URL % "master")

    def test_a_beta_box_serves_its_own_branch(self):
        util.DLL_BRANCH = util.DLL_BETA_BRANCH = "4.3"
        self.assertEqual(self._target("/dll"), util.DLL_URL % "4.3")
        self.assertEqual(self._target("/dll/beta"), util.DLL_URL % "4.3")

    def test_prod_can_point_only_the_beta_route_elsewhere(self):
        util.DLL_BRANCH, util.DLL_BETA_BRANCH = "master", "4.3"
        self.assertEqual(self._target("/dll"), util.DLL_URL % "master")
        self.assertEqual(self._target("/dll/beta"), util.DLL_URL % "4.3")

    def test_the_display_version_names_the_beta(self):
        # 4.9.x is the 5.0 beta on the page; anything else is itself
        if util.BETA_OF:
            self.assertEqual(util.DISPLAY_VERSION, "5.0 beta v%d" % util.VER[2])
        else:
            self.assertEqual(util.DISPLAY_VERSION, util.VERSION)


if __name__ == "__main__":
    unittest.main()
