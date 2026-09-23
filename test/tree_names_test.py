"""A tree grant is named after the tree whose coordinate grants it.

Run from the repo root:  python3 -m unittest test.tree_names_test -v
"""
import io
import json
import os
import re
import unittest

from models import trees_by_coords

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCATIONS = os.path.join(HERE, "archipelago", "oride_apworld", "oride", "data", "locations.json")


class TreeNameTests(unittest.TestCase):
    def test_each_tree_grant_names_its_own_tree(self):
        with io.open(LOCATIONS, encoding="utf-8") as f:
            names = {loc["coord"]: loc["name"] for loc in json.load(f)}
        for coord, pickup in trees_by_coords.items():
            skill = re.match(r"(\w+)Skill(Tree|Feather)$", names[coord]).group(1)
            self.assertEqual(pickup.name.replace(" ", ""), skill + "Tree", coord)

    def test_grenade_and_dash(self):
        self.assertEqual(trees_by_coords[719620].name, "Grenade Tree")
        self.assertEqual(trees_by_coords[2919744].name, "Dash Tree")


if __name__ == "__main__":
    unittest.main()
