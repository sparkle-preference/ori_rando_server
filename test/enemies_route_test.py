"""The game's box editor page reads the enemy table from 127.0.0.1, across origins."""
import json
import unittest

import main
from web import plando


class EnemiesJsonTestCase(unittest.TestCase):

    def test_any_origin_reads_the_table(self):
        with main.app.test_request_context("/enemies.json"):
            res = plando.enemies_json()
        self.assertEqual(res.headers["Access-Control-Allow-Origin"], "*")
        self.assertEqual(res.mimetype, "application/json")
        table = json.loads(res.get_data())
        self.assertTrue(table["version"] and table["variants"] and table["kinds"])
        self.assertTrue(all("x" in p and "y" in p and "scene" in p for p in table["placements"]))
