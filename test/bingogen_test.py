"""Tests for bingo goal generation (2026-07-26).

Focus: JourneyGoal, whose subgoal keys have to match the client's
BingoController.JourneyKey exactly. A typo there is silent -- the card just never
completes -- so the key format and the identifier set are pinned here.

Run from the repo root:  python3 -m unittest test.bingogen_test -v
"""
import random
import unittest

from bingo import BingoGenerator, JourneyGoal, journey_key

# BingoController.Teleporters in the client, verbatim. If these ever disagree,
# journey cards silently never complete.
CLIENT_TELEPORTERS = [
    "swamp", "sorrowPass", "sunkenGlades", "moonGrotto", "mangroveFalls", "valleyOfTheWind",
    "spiritTree", "mangroveB", "horuFields", "ginsoTree", "forlorn", "mountHoru",
]


def make_goal(easy=False, pairs=None, disp=None):
    disp = disp or {t: t.title() for t in CLIENT_TELEPORTERS}
    if pairs is None:
        easy_only = [{"sunkenGlades", "mangroveFalls"}, {"sunkenGlades", "spiritTree"}, {"swamp", "moonGrotto"}]
        pairs = [(f, t) for f in disp for t in disp
                 if f != t and (easy or {f, t} not in easy_only)]
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
        for _ in range(3):  # max_repeats
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
        self.assertEqual(make_goal().max_repeats, 3)


class TestEasyOnlyPairs(unittest.TestCase):
    """The trivial neighbour hops are a free square on a normal board."""

    EASY_ONLY = [("sunkenGlades", "mangroveFalls"), ("sunkenGlades", "spiritTree"), ("swamp", "moonGrotto")]

    def _pairs(self, easy):
        return set(make_goal(easy=easy).pairs)

    def test_excluded_on_normal_in_both_directions(self):
        pairs = self._pairs(easy=False)
        for frm, to in self.EASY_ONLY:
            self.assertNotIn((frm, to), pairs)
            self.assertNotIn((to, frm), pairs)

    def test_present_on_easy_in_both_directions(self):
        pairs = self._pairs(easy=True)
        for frm, to in self.EASY_ONLY:
            self.assertIn((frm, to), pairs)
            self.assertIn((to, frm), pairs)

    def test_other_pairs_survive_on_normal(self):
        pairs = self._pairs(easy=False)
        self.assertIn(("sunkenGlades", "mountHoru"), pairs)
        self.assertIn(("swamp", "forlorn"), pairs)


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

    def test_generation_is_deterministic(self):
        first = [c.disp_name for c in self._board("determinism")]
        second = [c.disp_name for c in self._board("determinism")]
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
