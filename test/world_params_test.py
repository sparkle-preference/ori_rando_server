"""World-settings storage and the per-world view of a seed's params."""
import unittest

import google.auth.credentials
from google.cloud import ndb

from enums import KeyMode, LogicPath, PathDifficulty, Variation
from seedbuilder.seedparams import MultiplayerOptions, SeedGenParams, WorldParams


def base_params(**kw):
    """A params entity that never reaches the datastore."""
    p = SeedGenParams(seed="worldparams")
    p.sync = MultiplayerOptions()
    p.spoilers = [""]
    p.logic_paths = [LogicPath.CASUAL_CORE]
    p.key_mode = KeyMode.CLUES
    p.path_diff = PathDifficulty.NORMAL
    p.variations = [Variation.FORCE_TREES]
    for k, v in kw.items():
        setattr(p, k, v)
    return p


class WorldParamsTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        creds = google.auth.credentials.AnonymousCredentials()
        cls.ndb_client = ndb.Client(project="unit-test", credentials=creds)

    def setUp(self):
        self._ctx = self.ndb_client.context()
        self._ctx.__enter__()

    def tearDown(self):
        self._ctx.__exit__(None, None, None)

    def test_no_overrides_returns_the_entity_itself(self):
        """Not merely equivalent: the same object, so the path a seed without
        per-world settings takes is unchanged."""
        p = base_params()
        self.assertIs(p.world_params(1), p)
        self.assertIs(p.world_params(2), p)

    def test_an_empty_blob_is_not_an_override(self):
        p = base_params(world_settings=[{}, {}])
        self.assertIs(p.world_params(1), p)
        self.assertIs(p.world_params(2), p)

    def test_a_world_past_the_end_falls_back_to_the_seed(self):
        p = base_params(world_settings=[{"keyMode": "Shards"}])
        self.assertIs(p.world_params(2), p)
        self.assertIs(p.world_params(9), p)

    def test_an_override_wins_and_the_rest_is_inherited(self):
        p = base_params(exp_pool=10000, world_settings=[{}, {"keyMode": "Shards"}])
        w2 = p.world_params(2)
        self.assertEqual(w2.key_mode, KeyMode.SHARDS)
        self.assertEqual(p.key_mode, KeyMode.CLUES, "the base must not be touched")
        self.assertEqual(w2.exp_pool, 10000, "unmentioned fields come from the seed")
        self.assertEqual(w2.seed, "worldparams")

    def test_every_stored_field_converts_to_its_typed_value(self):
        blob = {"paths": ["expert-core"], "pathDiff": "Hard", "keyMode": "Shards",
                "variations": ["OpenWorld"], "expPool": 7777, "cellFreq": 12,
                "fragCount": 31, "fragReq": 21, "relicCount": 9, "bingoLines": 4,
                "itemPool": {"EX*": [1, 1]}, "selectedPool": "Competitive",
                "spawn": "Valley", "spawnECs": 5, "spawnHCs": 6, "spawnSKs": 2,
                "spawnWeights": [1.0], "senseData": "sense", "verboseSpoiler": True}
        w = base_params(world_settings=[blob]).world_params(1)
        self.assertEqual(w.logic_paths, [LogicPath.EXPERT_CORE])
        self.assertEqual(w.path_diff, PathDifficulty.HARD)
        self.assertEqual(w.key_mode, KeyMode.SHARDS)
        self.assertEqual(w.variations, [Variation.OPEN_WORLD])
        self.assertEqual((w.exp_pool, w.cell_freq, w.frag_count, w.frag_req), (7777, 12, 31, 21))
        self.assertEqual((w.relic_count, w.bingo_lines), (9, 4))
        self.assertEqual(w.item_pool, {"EX*": [1, 1]})
        self.assertEqual(w.pool_preset, "Competitive")
        self.assertEqual((w.start, w.starting_energy, w.starting_health, w.starting_skills),
                         ("Valley", 5, 6, 2))
        self.assertEqual((w.spawn_weights, w.sense, w.verbose_spoiler), ([1.0], "sense", True))

    def test_a_view_reads_the_base_live(self):
        """The retry path bumps starting_skills on the entity mid-generation;
        a view that snapshotted would miss it."""
        p = base_params(starting_skills=0, world_settings=[{"keyMode": "Shards"}])
        w = p.world_params(1)
        p.starting_skills += 1
        self.assertEqual(w.starting_skills, 1)

    def test_flag_line_on_a_view_is_that_worlds_flag_line(self):
        """flag_line is a method on the entity, so a view that only forwarded
        attributes would hand back the seed's flags for every world."""
        p = base_params(world_settings=[{}, {"keyMode": "Shards", "variations": ["OpenWorld"]}])
        self.assertIn("Clues", p.flag_line())
        w2 = p.world_params(2)
        self.assertIsInstance(w2, WorldParams)
        self.assertIn("Shards", w2.flag_line())
        self.assertNotIn("Clues", w2.flag_line())
        self.assertIn("OpenWorld", w2.flag_line())

    def test_ndbs_own_methods_stay_on_the_entity(self):
        """Rebinding put/key to the view would break the write path. Holds even
        when a caller has patched put onto the subclass, which leaves the
        inherited function sitting in SeedGenParams.__dict__."""
        p = base_params(world_settings=[{"keyMode": "Shards"}])
        self.assertEqual(p.world_params(1).put.__self__, p)
        patched = SeedGenParams.__dict__.get("put")
        SeedGenParams.put = SeedGenParams.put
        try:
            self.assertEqual(p.world_params(1).put.__self__, p)
        finally:
            if patched is None:
                del SeedGenParams.put
            else:
                SeedGenParams.put = patched

    def test_settings_survive_the_json_round_trip(self):
        p = base_params(world_settings=[{}, {"keyMode": "Shards"}])
        self.assertEqual(p.to_json()["worldSettings"], [{}, {"keyMode": "Shards"}])


if __name__ == "__main__":
    unittest.main()
