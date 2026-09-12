"""Bingo needs: what a square cannot be done without, and how many such squares a board takes.

The caps and the location tags in bingo.py are pinned against reachable.py: a full
inventory less one need, standard logic, open world, Glades spawn. When areas.ori moves
a number this fails; update the constant and say what moved (prior_notes/BINGO_NEEDS.md
has the tables and the probe that prints them).

Run from the repo root:  python3 -m unittest test.bingoneeds_test -v
"""
import random
import unittest
from collections import Counter

from bingo import (BingoGenerator, BoolGoal, DefeatGoal, GoalGroup, IntGoal, JourneyGoal, defeat_key,
                   defeat_zones, namef, roll_func, with_implied, DEFEAT_NEEDS, IMPLIES, LOC_CAPS, NEED_ITEMS,
                   NEEDS, NEEDS_BUDGET, ZONE_CAPS, ZONE_NEEDS)
from enums import presets
from reachable import Map, full_state
from seedbuilder.oriparse import get_areas

STANDARD = sorted(p.value for p in presets["Standard"]) + ["OPEN_WORLD"]
LOCS = get_areas()["locs"]
ALTARS = {name for name, loc in LOCS.items() if loc["item"] == "MapStone"}


def reachable_locs(without=()):
    areas = set(Map.get_reachable_areas(full_state(without), STANDARD, "Glades", need_reached_with=False))
    return {name for name in LOCS if name in areas}


# need -> the locations a full inventory loses without it
LOST = {need: set(LOCS) - reachable_locs(items) for need, items in NEED_ITEMS.items()}

# GetItemAtLoc subgoals are named after areas.ori locations, bar one
LOC_ALIASES = {"ForlornEscapePlant": "ForlornPlant"}
TREE_LOCS = {"Glide": "GlideSkillFeather"}

# goal -> the areas.ori item code its caps count
LOC_GOALS = {
    "HealthCellLocs": "HC", "EnergyCellLocs": "EC", "AbilityCellLocs": "AC", "MapstoneLocs": "MS",
    "HealthCells": "HC", "EnergyCells": "EC", "AbilityCells": "AC", "CollectMapstones": "MS", "ActivateMaps": "MapStone",
}


def fixed(n):
    func = lambda: n
    func.min = func.max = n
    return func


def pool(**kw):
    kw.setdefault("rando", True)
    return BingoGenerator.goal_pool(random.Random(1), **kw)


def by_name(goals):
    return {goal.name: goal for goal in goals}


def every_pool():
    for rando in (True, False):
        for difficulty in ("easy", "normal", "hard"):
            for meta in (False, True):
                yield pool(rando=rando, difficulty=difficulty, meta=meta)


class TestVocabulary(unittest.TestCase):
    def test_a_full_inventory_reaches_every_location(self):
        self.assertEqual(reachable_locs(), set(LOCS))

    def test_every_need_takes_something_away(self):
        for need in NEEDS:
            self.assertTrue(LOST[need], need)

    def test_every_tag_in_use_is_a_known_need(self):
        used = set()
        for goals in every_pool():
            for goal in goals:
                used |= set(goal.needs)
                for sub in getattr(goal, "goals", []):
                    used |= set(sub.needs)
                used |= set(getattr(goal, "caps", {}))
                for needs in getattr(goal, "well_needs", {}).values():
                    used |= set(needs)
        for needs in list(DEFEAT_NEEDS.values()) + list(IMPLIES.values()):
            used |= set(needs)
        used |= set(ZONE_NEEDS.values()) | set(IMPLIES)
        for caps in list(ZONE_CAPS.values()) + list(LOC_CAPS.values()) + list(NEEDS_BUDGET.values()):
            used |= set(caps)
        self.assertEqual(used - set(NEEDS), set())
        self.assertEqual(used, set(NEEDS))  # and nothing is tagged with a need nobody uses


class TestPropagation(unittest.TestCase):
    """Lapis's rules: and/single/or take the union, count only what it cannot avoid."""

    def setUp(self):
        self.rand = random.Random(7)
        self.subs = [BoolGoal("a", needs=["Horu"]), BoolGoal("b", needs=["Stomp"]), BoolGoal("c"), BoolGoal("d")]

    def group(self, method, count, needs=()):
        return GoalGroup("G", self.subs, [(method, fixed(count))], namef("Do", "thing"), needs=needs)

    def test_a_plain_goal_carries_its_own(self):
        self.assertEqual(BoolGoal("x", needs=["Horu"]).to_card(self.rand).needs, {"Horu"})
        self.assertEqual(BoolGoal("x").to_card(self.rand).needs, set())

    def test_an_int_goal_needs_above_its_cap(self):
        goal = IntGoal("n", "N", [], fixed(10), caps={"Horu": 9, "Stomp": 10})
        self.assertEqual(goal.to_card(self.rand).needs, {"Horu"})

    def test_a_grenade_square_is_a_blue_breakage_square(self):
        self.assertEqual(with_implied({"Grenade"}), {"Grenade", "Blue"})
        self.assertEqual(BoolGoal("x", needs=["Grenade"]).to_card(self.rand).needs, {"Grenade", "Blue"})
        self.assertEqual(IntGoal("n", "N", [], fixed(10), caps={"Grenade": 9}).to_card(self.rand).needs, {"Grenade", "Blue"})
        # through a count too: the implied need rides along with the one that implies it
        group = GoalGroup("G", [BoolGoal("a", needs=["Grenade"]), BoolGoal("b")], [("count", fixed(2))], namef("Do", "thing"))
        self.assertEqual(group.to_card(self.rand, banned={"methods": [], "goals": []}).needs, {"Grenade", "Blue"})

    def test_and_is_the_union(self):
        for _ in range(20):
            card = self.group("and", 4).to_card(self.rand, banned={"methods": [], "goals": []})
            self.assertEqual(card.needs, {"Horu", "Stomp"})

    def test_a_single_subgoal_is_its_own(self):
        seen = set()
        for _ in range(40):
            card = self.group("and", 1).to_card(self.rand, banned={"methods": [], "goals": []})
            name = card.subgoals[0]["name"]
            seen.add(name)
            self.assertEqual(card.needs, {"a": {"Horu"}, "b": {"Stomp"}}.get(name, set()))
        self.assertEqual(seen, {"a", "b", "c", "d"})

    def test_or_counts_as_both(self):
        for _ in range(40):
            card = self.group("or", 2).to_card(self.rand, banned={"methods": [], "goals": []})
            names = {s["name"] for s in card.subgoals}
            expected = ({"Horu"} if "a" in names else set()) | ({"Stomp"} if "b" in names else set())
            self.assertEqual(card.needs, expected)

    def test_count_needs_only_what_it_cannot_avoid(self):
        banned = {"methods": [], "goals": []}
        # two untagged subgoals: a count of 2 avoids both needs; 3 must touch a tagged square,
        # and which one is the player's choice, so it is charged as both
        self.assertEqual(self.group("count", 2).to_card(self.rand, banned=banned).needs, set())
        self.assertEqual(self.group("count", 3).to_card(self.rand, banned=banned).needs, {"Horu", "Stomp"})

    def test_a_count_ignores_bans(self):
        # a count card counts any completion, banned or not
        banned = {"methods": [], "goals": ["c", "d"]}
        self.assertEqual(self.group("count", 2).to_card(self.rand, banned=banned).needs, set())

    def test_group_needs_land_on_every_card(self):
        banned = {"methods": [], "goals": []}
        self.assertEqual(self.group("count", 1, needs=["Horu"]).to_card(self.rand, banned=banned).needs, {"Horu"})
        card = self.group("and", 1, needs=["Horu"]).to_card(self.rand, banned=banned)
        self.assertIn("Horu", card.needs)

    def test_a_journey_needs_both_wells(self):
        wells = {"a": {"Stomp"}, "b": {"Horu"}, "c": set()}
        goal = JourneyGoal([("a", "b"), ("b", "c"), ("c", "a")], {w: w for w in wells}, well_needs=wells)
        seen = {}
        for _ in range(60):
            card = goal.to_card(self.rand, banned={"methods": [], "goals": []})
            seen[card.subgoals[0]["name"]] = card.needs
        self.assertEqual(seen, {"a-b": {"Stomp", "Horu"}, "b-c": {"Horu"}, "c-a": {"Stomp"}})

    def test_a_defeat_in_a_dungeon_needs_it(self):
        zones = {"Slimes": ["Horu", "Glades"], "Spitters": ["Horu", "Blackroot"]}
        by_zone = DefeatGoal(zones, fixed(2), by_zone=True)
        by_kind = DefeatGoal(zones, fixed(2))
        for _ in range(40):
            card = by_zone.to_card(self.rand, banned={"methods": [], "goals": []})
            zone = card.subgoals[0]["name"].partition("-")[2]
            self.assertEqual("Horu" in card.needs, zone == "Horu", card.subgoals)
            self.assertEqual("Grenade" in card.needs, zone == "Blackroot" and "Spitters-Blackroot" in [s["name"] for s in card.subgoals])
            card = by_kind.to_card(self.rand, banned={"methods": [], "goals": []})
            names = [s["name"] for s in card.subgoals]
            self.assertEqual("Horu" in card.needs, any(n.endswith("-Horu") for n in names))
            self.assertEqual("Grenade" in card.needs, "Spitters-Blackroot" in names)


class TestBudget(unittest.TestCase):
    def _boards(self, difficulty, rando, n=40):
        for seed in range(n):
            yield BingoGenerator.get_cards(random.Random("%s-%s-%s" % (difficulty, rando, seed)), 25,
                                           rando=rando, difficulty=difficulty)

    def test_no_board_exceeds_its_budget_and_every_board_fills(self):
        for difficulty, budget in NEEDS_BUDGET.items():
            for rando in (True, False):
                for cards in self._boards(difficulty, rando):
                    self.assertEqual(len(cards), 25)
                    counts = Counter(need for card in cards for need in card.needs)
                    for need, most in budget.items():
                        self.assertLessEqual(counts[need], most, (difficulty, rando, need))

    def test_the_budget_binds(self):
        # the cap is a ceiling boards actually hit, or it is doing nothing
        for difficulty, budget in NEEDS_BUDGET.items():
            hit = {need: max(Counter(n for card in cards for n in card.needs)[need] for cards in self._boards(difficulty, True))
                   for need in budget}
            self.assertTrue(any(hit[need] == most for need, most in budget.items()), (difficulty, hit))

    def test_blue_is_never_capped(self):
        # the grenade cap already does most of that work (Lapis)
        for budget in NEEDS_BUDGET.values():
            self.assertNotIn("Blue", budget)

    def test_unlisted_needs_are_unlimited(self):
        saved = dict(NEEDS_BUDGET["hard"])
        try:
            NEEDS_BUDGET["hard"].clear()
            most = max(Counter(n for card in cards for n in card.needs)["Horu"] for cards in self._boards("hard", True, 80))
            self.assertGreater(most, saved["Horu"])
        finally:
            NEEDS_BUDGET["hard"].update(saved)

    def test_a_refused_card_leaves_no_bans(self):
        # a journey out of the Lost Grove well needs Grenade; refusing it must not ban the well's
        # other journeys, which JourneyGoal.to_card writes into the banned list as it draws
        saved = dict(NEEDS_BUDGET["normal"])
        try:
            NEEDS_BUDGET["normal"]["Grenade"] = 0
            origins = Counter()
            for cards in self._boards("normal", True, 80):
                for card in cards:
                    if card.name == "Journey":
                        origins[card.subgoals[0]["name"].partition("-")[0]] += 1
                    self.assertNotIn("Grenade", card.needs)
            self.assertNotIn("mangroveB", origins)
            self.assertGreater(len(origins), 5)
        finally:
            NEEDS_BUDGET["normal"].update(saved)


class TestLogicCanaries(unittest.TestCase):
    """The hand-entered numbers and location tags agree with areas.ori."""

    def _zone_goals(self, difficulty):
        goals = by_name(pool(difficulty=difficulty))
        return {name[len("PickupsIn"):]: goal for name, goal in goals.items() if name.startswith("PickupsIn")}

    def test_zone_caps_match_logic(self):
        # a cap is listed exactly when the top hard roll can exceed it; a zone with nothing left is a need
        goals = self._zone_goals("hard")
        for difficulty in ("easy", "normal"):
            for zone, goal in self._zone_goals(difficulty).items():
                self.assertLessEqual(goal.range_func.max, goals[zone].range_func.max, zone)
        for zone, goal in goals.items():
            zone_locs = {name for name, loc in LOCS.items() if loc["zone"] == zone} - ALTARS
            for need in NEEDS:
                cap = len(zone_locs - LOST[need])
                if cap == 0:
                    self.assertEqual(ZONE_NEEDS.get(zone), need)
                    self.assertEqual(goal.needs, {need})
                elif cap < goal.range_func.max:
                    self.assertEqual(ZONE_CAPS.get(zone, {}).get(need), cap, (zone, need))
                else:
                    self.assertNotIn(need, ZONE_CAPS.get(zone, {}), (zone, need, cap))
            self.assertEqual(goal.caps, ZONE_CAPS.get(zone, {}))
        self.assertLessEqual(set(ZONE_CAPS) | set(ZONE_NEEDS), set(goals))

    def test_location_goal_caps_match_logic(self):
        seen = set()
        for rando in (True, False):
            goals = by_name(pool(rando=rando, difficulty="hard"))
            for name, code in LOC_GOALS.items():
                if name not in goals:
                    continue
                seen.add(name)
                goal = goals[name]
                locs = {loc for loc, spec in LOCS.items() if spec["item"] == code}
                for need in NEEDS:
                    cap = len(locs - LOST[need])
                    if cap < goal.range_func.max:
                        self.assertEqual(goal.caps.get(need), cap, (name, need))
                    else:
                        self.assertNotIn(need, goal.caps, (name, need, cap))
                self.assertEqual(goal.caps, LOC_CAPS[code])
        self.assertEqual(seen, set(LOC_GOALS))

    def test_the_big_counters_never_need_anything(self):
        # every roll of these stays below what any single need takes away
        goals = by_name(pool(difficulty="hard"))
        worst = max(len(lost) for lost in LOST.values())
        self.assertLess(goals["TotalPickups"].range_func.max, len(LOCS) - worst)
        self.assertEqual(goals["TotalPickups"].caps, {})
        self.assertEqual(goals["TotalPickups"].needs, set())

    def test_plants_are_blue_and_nothing_else(self):
        goals = by_name(pool(difficulty="hard"))
        plants = {name for name, loc in LOCS.items() if loc["item"] == "Plant"}
        self.assertEqual(plants - LOST["Blue"], set())
        self.assertEqual(goals["BreakPlants"].needs, {"Blue"})
        others = [len(plants - lost) for need, lost in LOST.items() if need != "Blue"]
        self.assertLessEqual(goals["BreakPlants"].range_func.max, min(others))
        self.assertEqual(goals["BreakPlants"].caps, {})

    def _assert_tagged_as_logic_says(self, subgoal, loc, group_needs=frozenset()):
        self.assertIn(loc, LOCS, subgoal.name)
        needs = with_implied(subgoal.needs | group_needs)
        for need in NEEDS:
            self.assertEqual(need in needs, loc in LOST[need], (subgoal.name, need))

    def test_pickup_location_subgoals(self):
        for sub in by_name(pool())["GetItemAtLoc"].goals:
            self._assert_tagged_as_logic_says(sub, LOC_ALIASES.get(sub.name, sub.name))

    def test_tree_subgoals(self):
        for sub in by_name(pool())["VisitTree"].goals:
            self._assert_tagged_as_logic_says(sub, TREE_LOCS.get(sub.name, sub.name.replace(" ", "") + "SkillTree"))

    def test_horu_room_subgoals(self):
        group = by_name(pool())["CompleteHoruRoom"]
        for sub in group.goals:
            self._assert_tagged_as_logic_says(sub, "Horu" + sub.name, group.needs)

    def test_wells_in_dungeons_need_them(self):
        wells = by_name(by_name(pool())["ActivateTeleporter"].goals)
        self.assertEqual(wells["ginsoTree"].needs, {"Ginso"})
        self.assertEqual(wells["forlorn"].needs, {"Forlorn"})
        self.assertEqual(wells["mountHoru"].needs, {"Horu"})
        self.assertEqual(wells["mangroveB"].needs, {"Grenade"})  # its teleporter location is behind the door
        self.assertIn("LostGroveTeleporter", LOST["Grenade"])
        self.assertEqual(wells["horuFields"].needs, {"Stomp"})  # a Grove well, behind a peg

    def test_journeys_read_the_wells(self):
        goals = by_name(pool())
        wells = by_name(goals["ActivateTeleporter"].goals)
        self.assertEqual(goals["Journey"].well_needs, {name: well.needs for name, well in wells.items()})

    def test_defeat_zones_cover_every_dungeon(self):
        dungeons = {zone for zones in defeat_zones(hard=True).values() for zone in zones} & {"Ginso", "Forlorn", "Horu"}
        self.assertEqual(dungeons, set(ZONE_NEEDS))
        for key in DEFEAT_NEEDS:
            kind, _, zone = key.partition("-")
            self.assertIn(zone, defeat_zones(hard=True)[kind], key)


if __name__ == "__main__":
    unittest.main()
