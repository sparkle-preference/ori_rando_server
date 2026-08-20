"""What a saved seedgen setting keeps, and what it deliberately drops.

An SSP is a SeedGenParams json with the multiplayer half removed, so the same
saved setting can be rolled solo, in co-op, or handed to one world of a
multiworld. The split is a DENY-list on purpose: a new variation is saved
without anyone registering it, where an allow-list would drop it silently and
roll the default instead.

Run from the repo root:  python3 -m unittest test.ssp_test -v
"""
import unittest

from models import SSP_DENY, SavedSeedParams


def request(**over):
    """What MainPage.generateSeed posts, near enough for the split."""
    base = {
        "seed": "123456789",
        "keyMode": "Clues",
        "fillAlg": "Balanced",
        "variations": ["ForceTrees"],
        "paths": ["casual-core", "casual-dboost"],
        "expPool": 10000,
        "cellFreq": 256,
        "selectedPool": "Standard",
        "verboseSpoiler": True,
        "spawn": "Random",
        "spawnWeights": {"Glades": 1},
        "itemPool": {"HC": [12]},
        "players": 4,
        "playerNames": ["a", "b", "c", "d"],
        "tracking": True,
        "coopGameMode": "Multiworld",
        "coopGenMode": "cloned",
        "syncShared": ["Skills"],
        "teams": {1: [1, 2, 3, 4]},
        "apMode": True,
        "apExport": ["Skills"],
        "apDeathLink": True,
        "dedupShared": False,
        "antiBkBias": 3,
    }
    base.update(over)
    return base


class SettingsSplitTests(unittest.TestCase):
    def test_seed_content_is_kept(self):
        s = SavedSeedParams.settings_from(request())
        for key in ("keyMode", "fillAlg", "variations", "paths", "expPool",
                    "cellFreq", "selectedPool", "verboseSpoiler", "itemPool"):
            self.assertIn(key, s, key)

    def test_spawn_is_kept(self):
        s = SavedSeedParams.settings_from(request())
        self.assertEqual(s["spawn"], "Random")
        self.assertEqual(s["spawnWeights"], {"Glades": 1})

    def test_the_multiplayer_half_is_dropped(self):
        s = SavedSeedParams.settings_from(request())
        for key in SSP_DENY:
            self.assertNotIn(key, s, key)

    def test_the_seed_itself_is_dropped(self):
        self.assertNotIn("seed", SavedSeedParams.settings_from(request()))

    def test_tracking_is_kept(self):
        """It is a property of the settings, not of the lobby -- and a bingo
        setting is unrollable without it."""
        self.assertTrue(SavedSeedParams.settings_from(request())["tracking"])
        self.assertFalse(SavedSeedParams.settings_from(request(tracking=False))["tracking"])

    def test_bingo_settings_survive(self):
        s = SavedSeedParams.settings_from(request(variations=["Bingo"], bingoLines=4))
        self.assertEqual(s["variations"], ["Bingo"])
        self.assertEqual(s["bingoLines"], 4)
        self.assertTrue(s["tracking"])

    def test_an_unknown_option_rides_along(self):
        """The deny-list's whole point: a variation added later is saved without
        anyone registering it here."""
        s = SavedSeedParams.settings_from(request(someFutureOption=7))
        self.assertEqual(s["someFutureOption"], 7)

    def test_empty_input_is_empty(self):
        self.assertEqual(SavedSeedParams.settings_from({}), {})
        self.assertEqual(SavedSeedParams.settings_from(None), {})


class ForcedAssignmentTests(unittest.TestCase):
    """fass stays, because Buried placements are how the Starved modes work on
    the web -- dropping them would quietly change what the setting rolls."""

    def test_an_in_world_row_is_kept_without_its_world(self):
        s = SavedSeedParams.settings_from(request(fass=[
            {"loc": "20000050", "item": "TP|Grove", "world": 1, "owner": 1}]))
        self.assertEqual(s["fass"], [{"loc": "20000050", "item": "TP|Grove"}])

    def test_a_cross_world_row_is_dropped(self):
        s = SavedSeedParams.settings_from(request(fass=[
            {"loc": "919772", "item": "SK|0", "world": 1, "owner": 2}]))
        self.assertNotIn("fass", s)

    def test_only_the_saved_world_contributes(self):
        """Keeping every world's rows would apply all of them to whichever
        single world later loaded the setting."""
        rows = [{"loc": "1", "item": "SK|0", "world": 1, "owner": 1},
                {"loc": "2", "item": "HC|1", "world": 2, "owner": 2}]
        self.assertEqual(SavedSeedParams.settings_from(request(fass=rows))["fass"],
                         [{"loc": "1", "item": "SK|0"}])
        self.assertEqual(SavedSeedParams.settings_from(request(fass=rows), world=2)["fass"],
                         [{"loc": "2", "item": "HC|1"}])

    def test_a_cross_world_row_in_the_saved_world_is_still_dropped(self):
        s = SavedSeedParams.settings_from(request(fass=[
            {"loc": "2", "item": "HC|1", "world": 2, "owner": 1}]), world=2)
        self.assertNotIn("fass", s)

    def test_a_row_with_no_world_at_all_is_in_world(self):
        s = SavedSeedParams.settings_from(request(fass=[{"loc": "1", "item": "SK|0"}]))
        self.assertEqual(s["fass"], [{"loc": "1", "item": "SK|0"}])

    def test_no_rows_means_no_key(self):
        self.assertNotIn("fass", SavedSeedParams.settings_from(request(fass=[])))


class NameTests(unittest.TestCase):
    def test_latest_is_reserved(self):
        self.assertIsNotNone(SavedSeedParams.name_problem("latest"))
        self.assertIsNotNone(SavedSeedParams.name_problem("Latest"))

    def test_a_blank_name_is_refused(self):
        self.assertIsNotNone(SavedSeedParams.name_problem(""))
        self.assertIsNotNone(SavedSeedParams.name_problem("   "))

    def test_a_colon_is_refused(self):
        # the entity id is "<owner>:<name>"
        self.assertIsNotNone(SavedSeedParams.name_problem("a:b"))

    def test_an_ordinary_name_is_fine(self):
        self.assertIsNone(SavedSeedParams.name_problem("my usual settings"))


if __name__ == "__main__":
    unittest.main()
