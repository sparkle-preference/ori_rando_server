"""Enemy rando in an AP yaml: no lure pathsets, and a miniboss room's killers past its door."""
import importlib.util
import os
import unittest

from archipelago.convert import ap_variations
from archipelago.yaml_emit import arena_killers, make_config
from enums import Variation
from seedbuilder import enemyroll


def apworld_shared():
    # the apworld package imports Archipelago at its root; shared.py stands alone
    path = os.path.join(os.path.dirname(__file__), "..", "archipelago", "oride_apworld", "oride", "shared.py")
    spec = importlib.util.spec_from_file_location("oride_shared_undertest", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def elemental_roll():
    """A roll with an elemental in one gated miniboss room, vanilla everywhere else."""
    t = enemyroll.table()
    rolls = [None] * len(t["placements"])
    scene = next(s for s in enemyroll.ARENA_EDGES if any(p["arena"] and p["scene"] == s for p in t["placements"]))
    spot = next(i for i, p in enumerate(t["placements"]) if p["arena"] and p["scene"] == scene)
    rolls[spot] = next(i for i, v in enumerate(t["variants"]) if v["kind"] == "Elementals")
    return rolls, scene


class YamlTests(unittest.TestCase):
    def test_lure_paths_leave_the_pathsets(self):
        paths = ["standard-core", "standard-lure"]
        plain = make_config({}, [], {}, paths, variations=ap_variations([]))
        enemy = make_config({}, [], {}, paths, variations=ap_variations([Variation.ENEMY_RANDO]))
        self.assertIn("standardLure", plain["pathsets"])
        self.assertNotIn("standardLure", enemy["pathsets"])
        self.assertIn("standardCore", enemy["pathsets"])
        self.assertTrue(enemy["variations"]["enemy_rando"])
        self.assertNotIn("arena_killers", plain)

    def test_an_elemental_arena_sends_its_killers(self):
        rolls, scene = elemental_roll()
        config = make_config({}, [], {}, ["standard-core"], variations=ap_variations([Variation.ENEMY_RANDO]), enemy_rolls=rolls)
        edges = {(k["home"], k["target"]) for k in config["arena_killers"]}
        self.assertTrue(set(enemyroll.ARENA_EDGES[scene]) <= edges, edges)
        for k in config["arena_killers"]:
            self.assertEqual(k["kills"], [list(enemyroll.KILLERS["Elementals"])])
        # vanilla's own elemental rooms ride along; their paths already carry a killer
        vanilla = {(k["home"], k["target"]) for k in arena_killers([None] * len(rolls))}
        self.assertTrue(vanilla and vanilla < edges, vanilla)


class ApworldTests(unittest.TestCase):
    def test_kill_paths_grow_like_the_generator(self):
        kill_paths = apworld_shared().kill_paths
        paths = [{"tags": ["standardCore"], "reqs": ["Bash"]}, {"tags": [], "reqs": ["Climb", "Dash"]}]
        kills = [["Grenade", "Bash", "Stomp"]]
        grown = kill_paths(paths, kills)
        self.assertEqual(grown[0], {"tags": ["standardCore"], "reqs": ["Bash"]})
        self.assertEqual([p["reqs"] for p in grown[1:]], [["Climb", "Dash", "Grenade"], ["Climb", "Dash", "Bash"], ["Climb", "Dash", "Stomp"]])
        # two kinds: a path grows once per kind it can't already kill
        two = kill_paths([{"tags": [], "reqs": ["Stomp"]}], [["Grenade", "Bash", "Stomp"], ["Stomp", "ChargeFlame", "Grenade"]])
        self.assertEqual([p["reqs"] for p in two], [["Stomp"]])
        self.assertEqual([p["reqs"] for p in kill_paths([], [["Grenade"]])], [["Grenade"]])


if __name__ == "__main__":
    unittest.main()
