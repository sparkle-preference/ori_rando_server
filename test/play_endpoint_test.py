"""Play links name the server that rolled the seed, so a launcher that knows
several servers hands the game to the right one.

Run from the repo root:  python3 -m unittest test.play_endpoint_test -v
"""
import unittest

import util


class PlayEndpointTestCase(unittest.TestCase):
    def setUp(self):
        self._host = util.CANONICAL_HOST

    def tearDown(self):
        util.CANONICAL_HOST = self._host

    def _endpoint_for(self, host):
        util.CANONICAL_HOST = host
        return util.play_endpoint()

    def test_prod_links_carry_no_endpoint(self):
        self.assertEqual(self._endpoint_for(""), "")
        self.assertEqual(self._endpoint_for("bf.orirando.com"), "")

    def test_the_beta_and_dev_boxes_name_themselves(self):
        self.assertEqual(self._endpoint_for("bfbeta.eiko.blue"), "beta")
        self.assertEqual(self._endpoint_for("bfdev.eiko.blue"), "dev")


if __name__ == "__main__":
    unittest.main()
