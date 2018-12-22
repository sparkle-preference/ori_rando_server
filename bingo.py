import json
import logging as log
from random import choice, randint, sample
from collections import defaultdict


class BingoGoal(object):
    maxRepeats = 1
    tags = []
    def getCard(self, banned_goals=[], banned_methods=[]):
        cardData = {'name': self.name, 'type': self.goalType}
        return cardData
    def isAllowed(self, allowed_tags=[]):
        # if any([tag not in allowed_tags for tag in self.tags]):
        #     print "Excluding %s for tag mismatch: [%s] contains an element not in [%s]" % (self.name, ",".join(self.tags), ",".join(allowed_tags))
        return not any([tag not in allowed_tags for tag in self.tags])

class BoolGoal(BingoGoal):
    goalType = "bool"
    def __init__(self, name, tags=[]):
        self.name = name
        self.tags = tags

class IntGoal(BingoGoal):
    goalType = "int"
    def __init__(self, name, rangeFunc, tags=[]):
        self.name = name
        self.rangeFunc = rangeFunc
        self.tags = tags

    def getCard(self, banned_goals=[], banned_methods=[]):
        cardData = super(IntGoal, self).getCard()
        cardData['target'] = self.rangeFunc()
        return cardData

class GoalGroup(BingoGoal):
    def __init__(self, name, goals, methods, low=1, maxRepeats=1, tags=[]):
        self.name = name
        self.maxRepeats = maxRepeats
        self.goals = goals
        self.low = low
        self.methods = methods
        self.tags = []

    def getCard(self, banned_goals=[], banned_methods=[]):
        method, countFunc = choice([(m,c) for m,c in self.methods if m not in banned_methods])
        count = countFunc()
        if method == "count":
            return {'name': self.name, 'type': "multi", 'method': method, 'target': count}
        subgoals = [goal for goal in self.goals if goal.name not in banned_goals]
        count = min(count, len(subgoals))
        if count > 0:
            goals = sample(subgoals, count)
            return {'name': self.name, 'type': "multi", 'method': method, 'parts': [goal.getCard() for goal in goals]}
        else:
            return None

class BingoGenerator(object):
    @staticmethod
    def get_cards(cards=25, rando=False, difficulty="normal"):
        def r(low, easy_high, high, hard_high, scalar=1):
            if difficulty == "easy":
                return lambda: randint(low, easy_high)*scalar
            if difficulty == "hard":
                return lambda: randint(easy_high, hard_high)*scalar
            return lambda: randint(low, high)*scalar
        teleporterNames = ["sunkenGlades", "moonGrotto", "mangroveFalls", "valleyOfTheWind", "spiritTree", "mangroveB", "horuFields", "ginsoTree", "forlorn", "mountHoru"] + (["swamp", "sorrowPass"] if rando else [])
        goals = [
            BoolGoal("DrainSwamp"),
            BoolGoal("WilhelmScream"),
            IntGoal("CollectMapstones", r(3, 5, 7, 9)),
            IntGoal("ActivateMaps", r(3, 5, 7, 9)) if rando else IntGoal("ActivateMaps", r(2, 4, 6, 9)),
            IntGoal("OpenKSDoors", r(3, 4, 8, 11)),
            IntGoal("OpenEnergyDoors", r(3, 4, 5, 6)),
            IntGoal("BreakFloors", r(4, 10, 25, 42)),
            IntGoal("BreakWalls", r(4, 10, 20, 28)),
            IntGoal("UnspentKeystones", r(4, 10, 18, 24)),
            IntGoal("BreakPlants", r(5, 10, 15, 21)),
            IntGoal("TotalPickups", r(60, 100, 140, 180)) if rando else IntGoal("TotalPickups", r(50, 70, 120, 180)),
            IntGoal("UnderwaterPickups", r(2, 6, 10, 16)),
            IntGoal("HealthCells", r(4, 6, 9, 11)),
            IntGoal("EnergyCells", r(4, 6, 9, 13)),
            IntGoal("AbilityCells", r(6, 15, 20, 30)),
            IntGoal("LightLanterns", r(4, 6, 10, 14)), 
            IntGoal("SpendPoints", r(15, 25, 30, 35)),
            IntGoal("GainExperience", r(8, 10, 16, 20, scalar=500)),  # todo: see if these suck or not
            IntGoal("KillEnemies", r(5, 15, 25, 40, scalar=5)),
            GoalGroup(
                name="CompleteHoruRoom", 
                goals=[BoolGoal(name) for name in ["L1", "L2", "L3", "L4", "R1", "R2", "R3", "R4"]], 
                methods=[("or", lambda: 2), ("and", r(1, 2, 3, 4)), ("count", r(2, 4, 5, 7))]
                ),
            GoalGroup(
                name="ActivateTeleporter", 
                goals=[BoolGoal(name) for name in teleporterNames],   
                methods=[("or", lambda: 2), ("and", r(1, 3, 3, 4)), ("count", r(4, 7, 9, 11) if rando else r(4, 6, 8, 10))],
                maxRepeats=3
                ),
            GoalGroup(
                name="EnterArea", 
                goals=[BoolGoal(name) for name in ["Lost Grove", "Misty Woods", "Sorrow Pass", "Forlorn Ruins", "Mount Horu", "Ginso Tree"]],
                methods=[("or", (lambda: 3) if difficulty == "easy" else (lambda: 2)), ("and", r(1, 2, 2, 3))],
                maxRepeats=2
                ),
            GoalGroup(
                name="GetEvent",
                goals=[BoolGoal(name) for name in ["Water Vein", "Gumon Seal", "Sunstone", "Clean Water", "Wind Restored", "Warmth Returned"]],
                methods=[("or", (lambda: 3) if difficulty == "easy" else (lambda: 2)), ("and", r(1, 2, 2, 3))],
                maxRepeats=2
                ),
            GoalGroup(
                name="GetItemAtLoc", 
                goals=[BoolGoal(name) for name in ["LostGroveLongSwim", "ValleyEntryGrenadeLongSwim", "SpiderSacEnergyDoor", "SorrowHealthCell", "SunstonePlant", "GladesLaser", "LowerBlackrootLaserAbilityCell", 
                                                "MistyGrenade", "LeftSorrowGrenade", "DoorWarpExp", "HoruR3Plant", "RightForlornHealthCell", "ForlornEscapePlant"]],
                methods=[("or", (lambda: 3) if difficulty == "easy" else (lambda: 2)), ("and", r(1, 2, 3, 4))],
                maxRepeats=2
                ),
            GoalGroup(
                name="VisitTree", 
                goals=[BoolGoal(name) for name in ["Wall Jump", "Charge Flame", "Double Jump", "Bash", "Stomp", "Glide", "Climb", "Charge Jump", "Grenade", "Dash"]],
                methods=[("or", (lambda: 3) if difficulty == "easy" else (lambda: 2)), ("and", r(2, 2, 3, 4)), ("count", r(4, 6, 8, 10))],
                maxRepeats=2
                ),
            GoalGroup(
                name="GetAbility", 
                goals=[BoolGoal(name) for name in ["Ultra Defense", "Spirit Light Efficiency", "Ultra Stomp"]],
                methods=[("or", (lambda: 2) if difficulty == "easy" else (lambda: 1)), ("and", r(1, 2, 2, 3))],
                ),
            GoalGroup(
                name="StompPeg", 
                goals=[BoolGoal(name) for name in ["BlackrootTeleporter", "SwampPostStomp", "GroveMapstoneTree", "HoruFieldsTPAccess", "L1", "R2", 
                                                "L2", "L4Fire", "L4Drain", "SpiderLake", "GroveGrottoUpper", "GroveGrottoLower"]],
                methods=[("count", r(3, 5, 7, 10)), ("or", (lambda: 3) if difficulty == "easy" else (lambda: 2)), ("and", r(2, 3, 3, 4 ))],
                maxRepeats=2
                ),
            GoalGroup(
                name="HuntEnemies", 
                goals=[BoolGoal(name) for name in ["Fronkey Fight", "Misty Miniboss", "Lost Grove Fight Room", "Grotto Miniboss", 
                                                "Lower Ginso Miniboss", "Upper Ginso Miniboss", "Swamp Rhino Miniboss", "Mount Horu Miniboss"]],
                methods=[("count", r(3, 4, 6, 7)), ("and", r(1, 2, 3, 4)), ("or", (lambda: 3) if difficulty == "easy" else (lambda: 2))],
                maxRepeats=3
                ),
        ]
        if rando:
            goals += [
                IntGoal("HealthCellLocs", r(4, 6, 9, 11)),
                IntGoal("EnergyCellLocs", r(4, 6, 9, 13)),
                IntGoal("AbilityCellLocs", r(6, 15, 20, 30)),
                IntGoal("CollectMapstones", r(3, 5, 7, 9))
            ]

        if difficulty == "hard":
            goals += [
                BoolGoal("CoreSkip"),
                BoolGoal("FastStompless"),
            ]
        else:
            goals.append(BoolGoal("DrownFrog"))
        groupSeen = defaultdict(lambda: (1, [], []))
        output = []
        goals = [goal for goal in goals]
        while len(output) < cards:
            goal = choice(goals)
            repeats, banned_subgoals, banned_methods = groupSeen[goal.name]
            if repeats == goal.maxRepeats:
                goals.remove(goal)
            elif repeats > goal:
                assert "help?" and False
            cardData = goal.getCard(banned_subgoals, banned_methods)
            if not cardData:
                continue
            if "method" in cardData:
                banned_methods.append(cardData["method"])
            if "parts" in cardData:
                banned_subgoals += [part["name"] for part in cardData["parts"]]
            output.append(cardData)
            groupSeen[goal.name] = (repeats+1, banned_subgoals, banned_methods) 
        return output

