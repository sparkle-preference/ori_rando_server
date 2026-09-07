"""Tests for bingo goal generation (2026-07-26).

Focus: JourneyGoal, whose subgoal keys have to match the client's
BingoController.JourneyKey exactly. A typo there is silent -- the card just never
completes -- so the key format and the identifier set are pinned here.

Run from the repo root:  python3 -m unittest test.bingogen_test -v
"""
import random
import unittest

from bingo import (BingoGenerator, DefeatGoal, JourneyGoal, defeat_key, defeat_zones, journey_key,
                   journey_pairs, spawn_early_zones, DEFEAT_ZONES, SPAWN_AREAS, SPAWN_CLUSTER,
                   SPAWN_TELEPORTERS)

# BingoEnemyKinds.Kinds and RandomizerTrackedDataManager.Zones in the client, verbatim:
# a Defeat subgoal named outside these never completes.
CLIENT_KINDS = ["Slimes", "Spitters", "Frogs", "Fronkeys", "Spiders", "Birds", "Fish", "Rhinos", "Swarms",
                "Elementals", "Exploders", "Sharks"]
CLIENT_ZONES = ["Glades", "Grove", "Grotto", "Blackroot", "Swamp", "Ginso", "Valley", "Misty", "Forlorn",
                "Sorrow", "Horu"]

# BingoController.Teleporters in the client, verbatim. If these ever disagree,
# journey cards silently never complete.
CLIENT_TELEPORTERS = [
    "swamp", "sorrowPass", "sunkenGlades", "moonGrotto", "mangroveFalls", "valleyOfTheWind",
    "spiritTree", "mangroveB", "horuFields", "ginsoTree", "forlorn", "mountHoru",
]


def make_goal(easy=False, hard=False, pairs=None, disp=None):
    disp = disp or {t: t.title() for t in CLIENT_TELEPORTERS}
    if pairs is None:
        pairs = journey_pairs(disp, easy, hard)
    return JourneyGoal(pairs, disp)


class TestJourneyKey(unittest.TestCase):
    def test_format_is_origin_dash_destination(self):
        self.assertEqual(journey_key("swamp", "forlorn"), "swamp-forlorn")

    def test_card_subgoal_uses_the_wire_key(self):
        card = make_goal().to_card(random.Random(1))
        self.assertEqual(card.name, "Journey")  # the client's top-level json key
        self.assertEqual(len(card.subgoals), 1)
        frm, _, to = card.subgoals[0]["name"].partition("-")
        self.assertIn(frm, CLIENT_TELEPORTERS)
        self.assertIn(to, CLIENT_TELEPORTERS)


class TestJourneyGeneration(unittest.TestCase):
    def test_card_shape_is_a_single_and_subgoal(self):
        card = make_goal().to_card(random.Random(2))
        self.assertEqual(card.goal_type, "multi")
        self.assertEqual(card.goal_method, "and")  # no counts, no composing
        self.assertEqual(len(card.subgoals), 1)
        self.assertFalse(card.early)
        # the pair lives in the subgoal, not the title -- the board renders both and
        # spelling it out twice made these the longest cards on the board
        self.assertEqual(card.disp_name, "Journey between spirit wells")
        self.assertNotIn(":", card.disp_name)  # Bingo.js appends it
        self.assertIn("→", card.subgoals[0]["disp_name"])

    def test_picking_a_pair_bans_that_origin_and_the_return_trip(self):
        goal = make_goal()
        banned = []
        card = goal.to_card(random.Random(3), banned={"goals": banned})
        frm, _, to = card.subgoals[0]["name"].partition("-")
        self.assertIn(journey_key(to, frm), banned)  # no round trips on one board
        # every *candidate* journey out of that origin (easy-only pairs aren't candidates here)
        self.assertTrue(all(journey_key(f, t) in banned for f, t in goal.pairs if f == frm),
                        "every journey out of %s should be banned" % frm)

    def test_repeated_draws_never_reuse_an_origin(self):
        goal = make_goal()
        rand = random.Random(4)
        banned, origins = [], []
        for _ in range(2):  # max_repeats
            card = goal.to_card(rand, banned={"goals": banned})
            origins.append(card.subgoals[0]["name"].partition("-")[0])
        self.assertEqual(len(set(origins)), len(origins))

    def test_exhausted_pairs_return_none_instead_of_raising(self):
        goal = make_goal(pairs=[("swamp", "forlorn")])
        banned = []
        self.assertIsNotNone(goal.to_card(random.Random(5), banned={"goals": banned}))
        self.assertIsNone(goal.to_card(random.Random(5), banned={"goals": banned}))

    def test_max_repeats_caps_journeys_per_board(self):
        # groupSeen starts at 1, so max_repeats N yields exactly N cards
        self.assertEqual(make_goal().max_repeats, 2)


class TestEasyOnlyPairs(unittest.TestCase):
    """The trivial neighbour hops are a free square on a normal board."""

    EASY_ONLY = [("sunkenGlades", "mangroveFalls"), ("swamp", "moonGrotto")]

    def _pairs(self, **kwargs):
        return set(make_goal(**kwargs).pairs)

    def test_excluded_on_normal_in_both_directions(self):
        pairs = self._pairs()
        for frm, to in self.EASY_ONLY:
            self.assertNotIn((frm, to), pairs)
            self.assertNotIn((to, frm), pairs)

    def test_present_on_easy_in_both_directions(self):
        pairs = self._pairs(easy=True)
        for frm, to in self.EASY_ONLY:
            self.assertIn((frm, to), pairs)
            self.assertIn((to, frm), pairs)

    def test_excluded_on_hard_too(self):
        pairs = self._pairs(hard=True)
        for frm, to in self.EASY_ONLY:
            self.assertNotIn((frm, to), pairs)
            self.assertNotIn((to, frm), pairs)

    def test_other_pairs_survive_on_normal(self):
        pairs = self._pairs()
        self.assertIn(("sunkenGlades", "mountHoru"), pairs)
        self.assertIn(("swamp", "forlorn"), pairs)


class TestHardOnlyPairs(unittest.TestCase):
    """Tedious or dead-end-prone routes: hard boards only, and that means not
    easy ones either."""

    HARD_ONLY = [
        ("mangroveB", "mountHoru"),        # out of Lost Grove, always
        ("mangroveB", "sunkenGlades"),
        ("valleyOfTheWind", "mangroveB"),  # into Lost Grove from a far well
        ("forlorn", "mangroveB"),
        ("mountHoru", "ginsoTree"),        # between two dungeons
        ("forlorn", "mountHoru"),
        ("ginsoTree", "valleyOfTheWind"),  # Sorrow's well, not Valley's
        ("valleyOfTheWind", "ginsoTree"),
        ("spiritTree", "swamp"),           # anything touching Grove
        ("mountHoru", "spiritTree"),
    ]
    NOT_HARD_ONLY = [
        ("sunkenGlades", "mangroveB"),     # a near approach into Lost Grove
        ("moonGrotto", "mangroveB"),
        ("mangroveFalls", "mangroveB"),
        ("swamp", "mangroveB"),
        ("horuFields", "mountHoru"),       # Horu Fields is not a dungeon
        ("sorrowPass", "ginsoTree"),       # Valley's well, not Sorrow's
        ("valleyOfTheWind", "forlorn"),    # Sorrow to a dungeon is fine
    ]

    def test_only_on_hard(self):
        hard = set(make_goal(hard=True).pairs)
        for difficulty in [{}, {"easy": True}]:
            pairs = set(make_goal(**difficulty).pairs)
            for pair in self.HARD_ONLY:
                self.assertIn(pair, hard, "%s should be a hard journey" % (pair,))
                self.assertNotIn(pair, pairs, "%s: %s" % (difficulty, pair))

    def test_pairs_that_stay_available(self):
        pairs = set(make_goal().pairs)
        for pair in self.NOT_HARD_ONLY:
            self.assertIn(pair, pairs)

    def test_lost_grove_is_one_way_below_hard(self):
        # you may walk in from a neighbour, never out
        pairs = set(make_goal().pairs)
        self.assertFalse([p for p in pairs if p[0] == "mangroveB"])
        self.assertTrue([p for p in pairs if p[1] == "mangroveB"])


class TestSpawnTeleporter(unittest.TestCase):
    """Spawn hands you its own well, so that one can't carry a card alone."""

    BOARDS = 150

    def _free_squares(self, spawn):
        """Wells that rolled as the whole card, or inside an 'either'."""
        seen = set()
        for seed in range(self.BOARDS):
            rand = random.Random()
            rand.seed(str(seed))
            for card in BingoGenerator.get_cards(rand, 25, rando=True, spawn=spawn):
                if card.name != "ActivateTeleporter":
                    continue
                if len(card.subgoals) == 1 or card.goal_method.startswith("or"):
                    seen |= {sg["name"] for sg in card.subgoals}
        return seen

    def test_the_spawn_well_is_excluded(self):
        for spawn, well in [("Glades", "sunkenGlades"), ("Sorrow", "valleyOfTheWind"), ("Horu", "mountHoru")]:
            free = self._free_squares(spawn)
            self.assertNotIn(well, free, "%s spawn" % spawn)
            self.assertTrue(free, "%s spawn: no wells rolled free at all" % spawn)

    def test_other_wells_are_not(self):
        # the tags used to be pinned to Glades; a non-Glades spawn frees it up
        self.assertIn("sunkenGlades", self._free_squares("Sorrow"))
        self.assertIn("valleyOfTheWind", self._free_squares("Glades"))

    def test_an_unresolved_spawn_excludes_nothing(self):
        # multiworld + random spawn leaves params.spawn == "Random"
        free = self._free_squares("Random")
        self.assertIn("sunkenGlades", free)
        self.assertIn("valleyOfTheWind", free)

    def test_every_spawn_zone_maps_to_a_client_teleporter(self):
        for well in SPAWN_TELEPORTERS.values():
            self.assertIn(well, CLIENT_TELEPORTERS)


def roll_boards(spawn, difficulty="normal", boards=60):
    for seed in range(boards):
        rand = random.Random()
        rand.seed("%s%s%s" % (spawn, difficulty, seed))
        for card in BingoGenerator.get_cards(rand, 25, rando=True, difficulty=difficulty, spawn=spawn):
            yield card


class TestSpawnArea(unittest.TestCase):
    """Spawning inside an area means entering it is free, same as its well."""

    def _free_squares(self, spawn):
        seen = set()
        for card in roll_boards(spawn):
            if card.name == "EnterArea" and (len(card.subgoals) == 1 or card.goal_method.startswith("or")):
                seen |= {sg["name"] for sg in card.subgoals}
        return seen

    def test_the_spawn_area_is_excluded(self):
        for spawn, area in SPAWN_AREAS.items():
            free = self._free_squares(spawn)
            self.assertNotIn(area, free, "%s spawn" % spawn)
            self.assertTrue(free, "%s spawn: no areas rolled free at all" % spawn)

    def test_areas_you_did_not_spawn_in_are_not(self):
        free = self._free_squares("Glades")
        for area in SPAWN_AREAS.values():
            if area != "Ginso Tree":  # already no_singleton on its own
                self.assertIn(area, free)


class TestSpawnEarlyZones(unittest.TestCase):
    def test_the_spawn_zone_opens_itself(self):
        for zone in ["Sorrow", "Valley", "Forlorn", "Horu", "Ginso", "Blackroot"]:
            self.assertIn(zone, spawn_early_zones(zone))

    def test_the_opening_cluster_shares_its_zones(self):
        for spawn in SPAWN_CLUSTER:
            self.assertLessEqual({"Glades", "Grove", "Grotto"}, spawn_early_zones(spawn))

    def test_sorrow_reaches_valley_and_misty(self):
        self.assertEqual(spawn_early_zones("Sorrow"), {"Sorrow", "Valley", "Misty"})

    def test_swamp_is_never_early(self):
        # the Swamp well doesn't reach most of the zone, spawn or not
        for spawn in list(SPAWN_TELEPORTERS) + ["Random"]:
            self.assertNotIn("Swamp", spawn_early_zones(spawn))

    def test_an_unresolved_spawn_opens_nothing(self):
        self.assertFalse(spawn_early_zones("Random") & set(SPAWN_TELEPORTERS))

    def test_the_early_cap_is_a_slice_of_the_roll_range(self):
        # Glades rolls (8,15) easy / (10,22) normal / (16,27) hard
        for difficulty, cap in [("easy", 9), ("normal", 13), ("hard", 20)]:
            hi, lo = 0, 99
            for card in roll_boards("Glades", difficulty, boards=300):
                if card.name != "PickupsInGlades":
                    continue
                if card.early:
                    hi = max(hi, card.target)
                else:
                    lo = min(lo, card.target)
            self.assertEqual(hi, cap, difficulty)
            self.assertEqual(lo, cap + 1, difficulty)

    def test_a_zone_spawn_does_not_open_the_others(self):
        early = {c.name for c in roll_boards("Forlorn", boards=200) if c.early and c.name.startswith("PickupsIn")}
        self.assertEqual(early, {"PickupsInForlorn"})


class TestClusterEarlyGoals(unittest.TestCase):
    """Spidersack and Blackroot-crusher goals assume the opening cluster."""

    def _early_names(self, spawn, group):
        return {sg["name"] for card in roll_boards(spawn, boards=120)
                if card.name == group and card.early for sg in card.subgoals}

    def test_pickup_locations_are_early_only_in_the_cluster(self):
        self.assertTrue({"SpiderSacEnergyDoor", "GladesLaser"} & self._early_names("Grotto", "GetItemAtLoc"))
        self.assertFalse(self._early_names("Sorrow", "GetItemAtLoc"))

    def test_deaths_are_early_only_in_the_cluster(self):
        cluster = self._early_names("Blackroot", "DieTo")
        for name in ["Spidersack Spikes", "Blackroot Teleporter Crushers", "Grotto Vault Lasers"]:
            self.assertIn(name, cluster)
        self.assertFalse(self._early_names("Horu", "DieTo"))


class TestJourneyInProgress(unittest.TestCase):
    """A journey card is 'live' when the player is standing at its origin well.
    Driven by LastTouchedTeleporter, which no card is named for."""

    class FakeProgress(object):
        def __init__(self, completed=False):
            self.completed = completed

        def to_json(self):
            return {"completed": self.completed, "count": 0, "subgoals": []}

    class FakePlayer(object):
        def __init__(self, last_tp, completed=False):
            self.bingo_last_tp = last_tp
            self.bingo_prog = [TestJourneyInProgress.FakeProgress(completed)]

    def _card(self):
        from models import BingoCard
        card = BingoCard(name="Journey", square=0)
        card.subgoals = [{"name": journey_key("swamp", "forlorn"), "disp_name": "Thornfelt Swamp → Forlorn Ruins"}]
        return card

    def test_live_at_the_origin(self):
        self.assertTrue(self._card().prog_json(self.FakePlayer("swamp"))["in_progress"])

    def test_not_live_elsewhere_or_nowhere(self):
        card = self._card()
        self.assertFalse(card.prog_json(self.FakePlayer("moonGrotto"))["in_progress"])
        self.assertFalse(card.prog_json(self.FakePlayer(""))["in_progress"])
        self.assertFalse(card.prog_json(self.FakePlayer(None))["in_progress"])

    def test_not_live_at_the_destination(self):
        # arriving completes the card; it should not read as still in progress
        self.assertFalse(self._card().prog_json(self.FakePlayer("forlorn"))["in_progress"])

    def test_completed_cards_are_never_in_progress(self):
        # re-touching the origin after finishing must not un-finish the display
        self.assertFalse(self._card().prog_json(self.FakePlayer("swamp", completed=True))["in_progress"])

    def test_non_journey_cards_omit_the_flag(self):
        from models import BingoCard
        card = BingoCard(name="ActivateTeleporter", square=0)
        self.assertNotIn("in_progress", card.prog_json(self.FakePlayer("swamp")))


class TestBoardGeneration(unittest.TestCase):
    """Journey cards have to survive a real board roll."""

    def _board(self, seed, difficulty="normal"):
        rand = random.Random()
        rand.seed(seed)
        return BingoGenerator.get_cards(rand, 25, rando=True, difficulty=difficulty)

    def test_boards_roll_and_respect_the_journey_cap(self):
        seen_any = False
        for seed in range(25):
            cards = self._board(str(seed))
            self.assertEqual(len(cards), 25)
            journeys = [c for c in cards if c.name == "Journey"]
            self.assertLessEqual(len(journeys), 3)
            if journeys:
                seen_any = True
                origins = [c.subgoals[0]["name"].partition("-")[0] for c in journeys]
                self.assertEqual(len(set(origins)), len(origins))
        self.assertTrue(seen_any, "no journey cards rolled in 25 boards")

    def test_zone_pickup_cards_are_capped(self):
        counts = set()
        for seed in range(40):
            cards = self._board(str(seed))
            counts.add(len([c for c in cards if c.disp_name.startswith("Collect Pickups In")]))
        # a flat budget of 2 is a ceiling: a board can draw the family once and stop
        self.assertLessEqual(max(counts), 2)
        self.assertIn(2, counts)

    def test_generation_is_deterministic(self):
        first = [c.disp_name for c in self._board("determinism")]
        second = [c.disp_name for c in self._board("determinism")]
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()


class TestDefeatData(unittest.TestCase):
    def test_every_kind_and_zone_is_one_the_client_tracks(self):
        for kind, zones in defeat_zones(hard=True).items():
            self.assertIn(kind, CLIENT_KINDS)
            for zone in zones:
                self.assertIn(zone, CLIENT_ZONES)

    def test_hard_only_zones_join_on_hard(self):
        self.assertNotIn("Forlorn", defeat_zones()["Spitters"])
        self.assertIn("Forlorn", defeat_zones(hard=True)["Spitters"])
        self.assertEqual(defeat_zones()["Rhinos"], defeat_zones(hard=True)["Rhinos"])

    def test_sharks_are_a_kind_but_never_a_target(self):
        self.assertIn("Sharks", CLIENT_KINDS)
        self.assertNotIn("Sharks", DEFEAT_ZONES)

    def test_key_is_kind_dash_zone(self):
        self.assertEqual(defeat_key("Slimes", "Glades"), "Slimes-Glades")


class TestDefeatCards(unittest.TestCase):
    def kind_goal(self, count=2, zones=None, hard=False):
        return DefeatGoal(zones or defeat_zones(hard), lambda: count)

    def zone_goal(self, count=2, zones=None, hard=False):
        return DefeatGoal(zones or defeat_zones(hard), lambda: count, by_zone=True)

    def test_kind_card_is_one_kind_in_n_zones(self):
        card = self.kind_goal(count=3).to_card(random.Random(1))
        self.assertEqual(card.name, "Defeat")  # the client's top-level json key
        self.assertEqual(card.goal_type, "multi")
        self.assertEqual(card.goal_method, "and")
        self.assertEqual(len(card.subgoals), 3)
        kinds = {sg["name"].partition("-")[0] for sg in card.subgoals}
        self.assertEqual(len(kinds), 1)
        for sg in card.subgoals:
            kind, _, zone = sg["name"].partition("-")
            self.assertIn(zone, defeat_zones()[kind])
            self.assertEqual(sg["disp_name"], zone)
        self.assertEqual(card.disp_name, "Defeat a %s in zones" % {"Slimes": "Slime", "Spitters": "Spitter", "Frogs": "Frog",
                         "Fronkeys": "Fronkey", "Spiders": "Spider", "Birds": "Bird", "Fish": "Fish", "Rhinos": "Rhino", "Swarms": "Swarm"}[kinds.pop()])
        self.assertNotIn(":", card.disp_name)  # Bingo.js appends it

    def test_zone_card_is_n_kinds_in_one_zone(self):
        card = self.zone_goal(count=3).to_card(random.Random(2))
        zones = {sg["name"].partition("-")[2] for sg in card.subgoals}
        self.assertEqual(len(zones), 1)
        zone = zones.pop()
        for sg in card.subgoals:
            kind, _, _ = sg["name"].partition("-")
            self.assertIn(zone, defeat_zones()[kind])
            self.assertEqual(sg["disp_name"], "a " + kind[:-1] if kind != "Fish" else "a Fish")
        self.assertEqual(card.disp_name, "Defeat in %s" % zone)

    def test_wording_follows_the_count(self):
        self.assertTrue(self.kind_goal(count=1).to_card(random.Random(3)).disp_name.endswith(" in zone"))
        self.assertTrue(self.kind_goal(count=2).to_card(random.Random(3)).disp_name.endswith(" in zones"))
        self.assertTrue(self.zone_goal(count=1).to_card(random.Random(3)).disp_name.startswith("Defeat in "))

    def test_count_is_capped_by_what_is_there(self):
        card = self.kind_goal(count=9, zones={"Rhinos": defeat_zones()["Rhinos"]}).to_card(random.Random(4))
        self.assertEqual(len(card.subgoals), len(defeat_zones()["Rhinos"]))

    def test_banned_pairs_are_skipped_and_exhaustion_returns_none(self):
        zones = {"Rhinos": ["Swamp", "Valley"]}
        card = self.kind_goal(count=2, zones=zones).to_card(random.Random(5), banned={"goals": ["Rhinos-Swamp"]})
        self.assertEqual([sg["name"] for sg in card.subgoals], ["Rhinos-Valley"])
        self.assertIsNone(self.kind_goal(zones=zones).to_card(random.Random(5), banned={"goals": ["Rhinos-Swamp", "Rhinos-Valley"]}))

    def test_no_hard_only_zone_below_hard(self):
        hard_only = {defeat_key(k, z) for k, spec in DEFEAT_ZONES.items() for z in spec.get("hard", [])}
        for seed in range(30):
            for goal in (self.kind_goal(count=5), self.zone_goal(count=5)):
                card = goal.to_card(random.Random(seed))
                self.assertFalse(hard_only & {sg["name"] for sg in card.subgoals})

    def test_hard_reaches_the_hard_only_zones(self):
        seen = set()
        for seed in range(200):
            card = self.kind_goal(count=5, hard=True).to_card(random.Random(seed))
            seen |= {sg["name"] for sg in card.subgoals}
        self.assertIn("Spitters-Forlorn", seen)


class TestDefeatBudget(unittest.TestCase):
    def test_at_most_two_defeat_cards_per_board(self):
        for seed in range(40):
            for difficulty in ("easy", "normal", "hard"):
                cards = BingoGenerator.get_cards(random.Random(seed), difficulty=difficulty)
                self.assertLessEqual(sum(1 for card in cards if card.name == "Defeat"), 2)

    def test_boards_do_get_defeat_cards(self):
        self.assertTrue(any(card.name == "Defeat" for seed in range(20)
                            for card in BingoGenerator.get_cards(random.Random(seed))))

    def test_two_defeat_cards_never_share_a_pair(self):
        for seed in range(60):
            cards = [card for card in BingoGenerator.get_cards(random.Random(seed)) if card.name == "Defeat"]
            keys = [sg["name"] for card in cards for sg in card.subgoals]
            self.assertEqual(len(keys), len(set(keys)))
