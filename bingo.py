import json
import logging as log
from random import choice, randint, sample
from collections import defaultdict
# constants
DUNGEONS = ["Forlorn Ruins", "Ginso Tree", "Mount Horu"]
AREAS_WITH_TPS = ["Ginso Tree", "Forlorn Ruins", "Moon Grotto", "Hollow Grove", "Sunken Glades",
    "Blackroot Burrows", "Thornfelt Swamp", "Valley of the Wind", "Sorrow Pass", "Lost Grove", "Mount Horu"]
AREAS = AREAS_WITH_TPS + ["Misty Woods"]
AREAS_WITH_MAPSTONES = ["Sunken Glades", "Forlorn Ruins", "Moon Grotto", "Blackroot Burrows", "Thornfelt Swamp", "Valley of the Wind", "Sorrow Pass", "Mount Horu", "Hollow Grove"]
SKILLS = ["Wall Jump", "Charge Flame", "Double Jump", "Bash", "Stomp", "Glide", "Climb", "Charge Jump", "Dash", "Grenade"]
EVENTS = ["Water Vein", "Clean Water", "Gumon Seal", "Wind Restored", "Sunstone", "Warmth Returned"]
BONUS_PICKUPS = ["Extra Double Jump", "Extra Air Dash", "Explosion Power Upgrade", "Charge Dash Efficiency", "Spirit Light Efficiency"]


class Card(object):
    @staticmethod
    def singletons(is_rando):
        tuples = [
            ("StomplessOrCoreSkip", "Fast Stompless or Core Skip"),
            ("Triforce", "Collect the Triforce AC"),
            ("Wilhelm", "Hear Wilhelm's scream"),
            ("CatMouse", "Escape Kuro outside of Forlorn"),
            ("DrownFrog", "Drown an amphibian"),
            ("DrainSwamp", "Drain the swamp"),
            ("BanelingKill", "Kill an enemy with a baneling"),
            ("L4 lava", "Escape the L4 Lava")
        ] + ([
            ("UselessPickup", "Warmth Returned or 1 exp"),
            ("QuadJump", "Quad Jump"),
            ("Regen", "Collect a regen pickup")
        ] if is_rando else [("TripleJump", "Triple Jump")])
        print tuples
        return [{'name': name, 'text': text} for (name, text) in tuples]
    @staticmethod
    def all_cards(is_rando):
        return [{'text': c.get(is_rando), 'name': c.__name__} for c in Card.__subclasses__() if c.valid(is_rando)] + Card.singletons(is_rando)

    @staticmethod
    def get_cards(is_rando, cards=25):
        c = Card.all_cards(is_rando)
        if cards > len(c):
            log.warning("Not enough cards! %s>%s" % (cards, len(c)))
            cards = 25
        return sample(c, cards)
    @staticmethod
    def get_json(is_rando, cards=25):
        return "[%s]" % ",\n".join(['{"name": "%s"}' % card["text"] for card in Card.get_cards(is_rando, cards)])

    @staticmethod
    def valid(rando):
        return True

class Rando():
    @staticmethod
    def valid(rando):
        return rando

class HoruRoomXorY(Card):
    @staticmethod
    def get(rando):
        return "Complete %s or %s" % (choice(["L1", "L2", "L3", "L4"]), choice(["R1", "R2", "R3", "R4"]))

class CollectNMapstones(Card):
    @staticmethod
    def get(rando):
        return "Collect %s mapstones" % (randint(4, 6) + randint(0, 2) + randint(0, 1) + randint(0, 1))

class OpenNDoors(Card):
    @staticmethod
    def get(rando):
        return "Open %s keystone doors" % randint(3, 6)

class BreakNBarriers(Card):
    @staticmethod
    def get(rando):
        return "Break %s breakable walls" % randint(3, 6)

class BreakNVertBarriers(Card):
    @staticmethod
    def get(rando):
        return "Break %s breakable floors/ceilings" % randint(4, 8)


class OpenNrgyDoors(Card):
    @staticmethod
    def get(rando):
        return "Open %s energy doors" % randint(2, 4)

class MaxAbilityTree(Card):
    @staticmethod
    def get(rando):
        return "Get %s abilities in the %s tree" % ("all" if rando else randint(6,10), choice(["Red", "Purple", "Blue"]))

class HaveNKeystones(Card):
    @staticmethod
    def get(rando):
        return "Have %s unspent keystones" % randint(8, 16)

class DieToXorY(Card):
    @staticmethod
    def get(rando):
        return "Die to %s or %s" % tuple(sample(["Kuro (anywhere)", "Forlorn Approach Baneling", "Horu Lava", "Spidersack spikes", "Misty Baneling", "Lightning above Sorrow Pass", "Lasers above far right Forlorn plant", "Lost Grove Bottom Lasers"], 2))

class NTotalPickups(Card):
    @staticmethod
    def get(rando):
        return "Collect %s pickups" % (randint(60, 140) if rando else randint(50, 90))

class GrenadeLocked(Card):
    @staticmethod
    def get(rando):
        return "Light %s grenade-lanterns" % randint(3, 6)

class CollectNPlants(Card):
    @staticmethod
    def get(rando):
        return "Break %s Plants" % randint(3, 6)

class CollectNUnderwater(Card):
    @staticmethod
    def get(rando):
        return "Collect %s pickups underwater" % randint(2, 5)

class NHealth(Card):
    @staticmethod
    def get(rando):
        return "Collect %s Health Cells" % randint(4, 8)

class NPoints(Card):
    @staticmethod
    def get(rando):
        return "Level up %s abilities in any tree" % randint(12, 24)

# disabled until integration
# class ReachLevelN(Card):
#	@staticmethod
#	def get(rando):
#		return "Reach level %s" % randint(8,16)

class Nrgy(Card):
    @staticmethod
    def get(rando):
        return "Collect %s Energy Cells" % randint(4, 8)

class CollectNUnderwater(Card):
    @staticmethod
    def get(rando):
        return "Collect %s pickups underwater" % randint(2, 5)

class EnterArea(Card):
    @staticmethod
    def get(rando):
        return "Enter %s" % choice(["Lost Grove", "Sorrow Pass", "Misty Woods"] + DUNGEONS)

class EnterAreaXorY(Card):
    @staticmethod
    def get(rando):
        return "Enter %s or %s" % tuple(sample(["Lost Grove", "Sorrow Pass", "Misty Woods"] + DUNGEONS, 2))

class DungeonEscape(Card):
    @staticmethod
    def get(rando):
        return "Complete the %s escape" % choice(DUNGEONS)

class NEscapeS(Card):
    @staticmethod
    def get(rando):
        return "Complete %s dungeon escape(s)" % randint(1, 3)

class ActivateNTPs(Card):
    @staticmethod
    def get(rando):
        return "Activate %s Spirit Wells" % randint(2, 5)

class StompPegXorY(Card):
    @staticmethod
    def get(rando):
        return "Stomp the peg(s) at %s or %s" % tuple(sample(["Hollow Groves Spider Lake", "Kuro CS Tree", "Sorrow Tumbleweed Area", "Swamp Post-Stomp", "Above Death Gauntlet"], 2))
    
class ActivateNTrees(Card):
    @staticmethod
    def get(rando):
        return "Activate %s Trees" % (randint(2, 5) + randint(1, 3) + randint(0, 2))


class KillByLevelup(Card):
    @staticmethod
    def get(rando):
        return "Kill %s enemies by leveling up" % randint(2, 6)

class MapstoneN(Card):
    @staticmethod
    def get(rando):
        return "Turn in Mapstone %s" % randint(2, 9)

class XorYTp(Rando, Card):
    @staticmethod
    def get(rando):
        return "Find or Activate the %s, %s, or %s TP" % tuple(sample(AREAS_WITH_TPS, 3))

class XorYFullClear(Card):
    @staticmethod
    def get(rando):
        return "Get every pickup in %s, %s, or %s" % tuple(sample(AREAS_WITH_TPS, 3))

class FindXInY(Card):
    @staticmethod
    def get(rando):
        return "Get %s pickups from %s" % (randint(2, 10), choice(AREAS_WITH_TPS))

class XorYEvent(Card):
    @staticmethod
    def get(rando):
        return "%s or %s" % tuple(sample(EVENTS, 2))

class XandYMapstoneTurnins(Card):
    @staticmethod
    def get(rando):
        return "Activate the %s and %s Mapstones" % tuple(sample(AREAS_WITH_MAPSTONES, 2))

class GarbagePickupXorY(Card):
    @staticmethod
    def get(rando):
        return "Get the pickup at %s or %s" % tuple(sample(["Lost Grove Underwater AC", "Sunstone", "Forlorn Escape Plant", "Validation Exp", "Gladezer EC", "Forlorn HC", "R3 Plant", "Misty Grenade Pickup", "Valley Enterance Long Swim EC"], 2))

class EventLocationXorY(Card):
    @staticmethod
    def get(rando):
        return "Collect the pickup at vanilla %s or %s" % tuple(sample(["Water Vein", "Clean Water", "Gumon Seal", "Wind Restored", "Sunstone"], 2))

class WatchXorY(Card):
    @staticmethod
    def get(rando):
        return "Watch (don't skip) %s or %s" % tuple(sample(["Racist Dad 3", "Spirit Tree Cutscene", "Post-Forlorn Escape Cutscene", "Racist Dad 2", "Sunstone cutscene", "Post-Ginso Escape cutscene"], 2))

class XorYTree(Card):
    @staticmethod
    def get(rando):
        return "Get the %s or %s Tree" % tuple(sample(SKILLS, 2))

class KillEnemyXorY(Card):
    @staticmethod
    def get(rando):
        return "Kill %s or %s" % tuple(sample(["Stomp Tree Rhino", "Grotto Miniboss", "Lower Ginso Miniboss", "Lost Grove Fight Room", "Upper Ginso Miniboss", "Misty Minibosses", "Horu Final Miniboss"], 2))

class AltRAfter(Rando, Card):
    @staticmethod
    def get(rando):
        return "Alt-r immediately after you Find %s" % choice(["1 Experience"] + SKILLS + EVENTS)

class CollectNSkills(Rando, Card):
    @staticmethod
    def get(rando):
        return "Collect %s Skills" % (randint(2, 6) + randint(1, 3) + randint(0, 1))

class XorYSkill(Rando, Card):
    @staticmethod
    def get(rando):
        return "%s or %s" % tuple(sample(SKILLS, 2))

class XandYSkill(Rando, Card):
    @staticmethod
    def get(rando):
        return "%s and %s" % tuple(sample(SKILLS, 2))

class XorYBonus(Rando, Card):
    @staticmethod
    def get(rando):
        return "%s or %s" % tuple(sample(BONUS_PICKUPS, 2))







def r(low, high):
    return lambda: randint(low, high)



class BingoGoal(object):
    maxRepeats = 1
    def getCard(self, banned_goals=[], banned_methods=[]):
        cardData = {'name': self.name, 'type': self.goalType}
        return cardData

class BoolGoal(BingoGoal):
    goalType = "bool"
    def __init__(self, name):
        self.name = name

class IntGoal(BingoGoal):
    goalType = "int"
    def __init__(self, name, rangeFunc):
        self.name = name
        self.rangeFunc = rangeFunc
    def getCard(self, banned_goals=[], banned_methods=[]):
        cardData = super(IntGoal, self).getCard()
        cardData['target'] = self.rangeFunc()
        return cardData

class GoalGroup(BingoGoal):
    def __init__(self, name, goals, low=1, methods=[("or", r(1, 3)), ("and", r(1, 2))], maxRepeats=1):
        self.name = name
        self.maxRepeats = maxRepeats
        self.goals = goals
        self.low = low
        self.methods = methods
        assert len(methods) > 0
    def getCard(self, banned_goals=[], banned_methods=[]):
        method, countFunc = choice([(m,c) for m,c in self.methods if m not in banned_methods])
        count = countFunc()
        if method == "count":
            return {'name': self.name, 'type': "multi", 'method': method, 'target': count}
        subgoals = [goal for goal in self.goals if goal.name not in banned_goals]
        count = min(count, len(subgoals))
        if count > 0:
            goals = sample(self.goals, count)
            return {'name': self.name, 'type': "multi", 'method': method, 'parts': [goal.getCard() for goal in goals]}
        else:
            return None

class BingoGenerator(object):
    def __init__(self, hard = False, is_rando = False):
        self.is_rando = is_rando
        self.goals = []
        for name in ["DrownFrog", "DrainSwamp", "WilhelmScream"] + (["FastStompless", "CoreSkip"] if hard else []):
            self.goals.append(BoolGoal(name))
        self.goals += [
            IntGoal("CollectMapstones", r(3, 7)),
            IntGoal("ActivateMaps", r(2, 7)),
            IntGoal("OpenKSDoors", r(3, 8)),
            IntGoal("OpenEnergyDoors", r(3, 6)),
            IntGoal("BreakFloors", r(4, 10)),
            IntGoal("BreakWalls", r(4, 10)),
            IntGoal("UnspentKeystones", r(4, 18)),
            IntGoal("BreakPlants", r(5, 12)),
            IntGoal("TotalPickups", r(50, 90)),
            IntGoal("UnderwaterPickups", r(2, 6)),
            IntGoal("HealthCells", r(4, 8)),
            IntGoal("EnergyCells", r(5, 9)),
            IntGoal("AbilityCells", r(6, 15)),
            IntGoal("LightLanterns", r(4, 10)),
            IntGoal("SpendPoints", r(20, 30)),
            IntGoal("GainExperience", lambda: 500*randint(8, 16)),
            IntGoal("KillEnemies", lambda: 5*randint(5, 25)),
        ]
        self.goals += [
            GoalGroup(
                name="CompleteHoruRoom", 
                goals=[BoolGoal(name) for name in ["L1", "L2", "L3", "L4", "R1", "R2", "R3", "R4"]], 
                methods=[("or", lambda: 2), ("and", r(1, 3)), ("count", r(2, 5))]
                ),
            GoalGroup(
                name="ActivateTeleporter", 
                goals=[BoolGoal(name) for name in ["sunkenGlades", "moonGrotto", "mangroveFalls", "valleyOfTheWind", "spiritTree", "mangroveB", "horuFields", "ginsoTree", "forlorn", "mountHoru"]],  # "swamp", "sorrowPass" if rando
                methods=[("or", lambda: 2), ("and", r(1, 3)), ("count", r(4, 7))],
                maxRepeats=3
                ),
            GoalGroup(
                name="EnterArea", 
                goals=[BoolGoal(name) for name in ["Lost Grove", "Misty Woods", "Sorrow Pass", "Forlorn Ruins", "Mount Horu", "Ginso Tree"]],
                methods=[("or", lambda: 2), ("and", r(1, 2))],
                maxRepeats=2
                ),
            GoalGroup(
                name="GetEvent",
                goals=[BoolGoal(name) for name in ["Water Vein", "Gumon Seal", "Sunstone", "Clean Water", "Wind Restored", "Warmth Returned"]],
                methods=[("or", r(2, 3)), ("and", r(1, 2))],
                maxRepeats=2
                ),
            GoalGroup(
                name="GetItemAtLoc", 
                goals=[BoolGoal(name) for name in ["LostGroveLongSwim", "ValleyEntryGrenadeLongSwim", "SpiderSacEnergyDoor", "SorrowHealthCell", "SunstonePlant", "GladesLaser", "LowerBlackrootLaserAbilityCell", 
                                                "MistyGrenade", "LeftSorrowGrenade", "DoorWarpExp", "HoruR3Plant", "RightForlornHealthCell", "ForlornEscapePlant"]],
                methods=[("or", r(2,3)), ("and", r(1, 2))],
                maxRepeats=2
                ),
            GoalGroup(
                name="VisitTree", 
                goals=[BoolGoal(name) for name in ["Wall Jump", "Charge Flame", "Double Jump", "Bash", "Stomp", "Glide", "Climb", "Charge Jump", "Grenade", "Dash"]],
                methods=[("or", lambda: 2), ("and", r(2, 3)), ("count", r(4, 9))],
                maxRepeats=2
                ),
            GoalGroup(
                name="GetAbility", 
                goals=[BoolGoal(name) for name in ["Ultra Defense", "Spirit Light Efficiency", "Ultra Stomp"]],
                methods=[("or", r(1, 3)), ("and", r(1, 2))],
                ),
            GoalGroup(
                name="StompPeg", 
                goals=[BoolGoal(name) for name in ["BlackrootTeleporter", "SwampPostStomp", "GroveMapstoneTree", "HoruFieldsTPAccess", "L1", "R2", 
                                                "L2", "L4Fire", "L4Drain", "SpiderLake", "GroveGrottoUpper", "GroveGrottoLower"]],
                methods=[("count", r(4,6)), ("and", r(2, 3))],
                maxRepeats=2
                ),
            GoalGroup(
                name="HuntEnemies", 
                goals=[BoolGoal(name) for name in ["Fronkey Fight", "Misty Miniboss", "Lost Grove Fight Room", "Grotto Miniboss", 
                                                "Lower Ginso Miniboss", "Upper Ginso Miniboss", "Swamp Rhino Miniboss", "Mount Horu Miniboss"]],
                methods=[("count", r(3, 5)), ("and", r(1, 3)), ("or", r(2, 3))],
                maxRepeats=3
                ),
        ]
    
    def get_cards(self, cards=25):
        print len(self.goals)
        groupSeen = defaultdict(lambda: (1, [], []))
        output = []
        goals = self.goals[:]
        while(len(output) < cards):
            print len(output), len(goals)
            goal = choice(goals)
            repeats, banned_subgoals, banned_methods = groupSeen[goal.name]
            if repeats == goal.maxRepeats:
                print "removing %s after %s repeats" % (goal.name, goal.maxRepeats)
                goals.remove(goal)
            elif repeats > goal:
                assert "help?" and False
            cardData = goal.getCard(banned_subgoals, banned_methods)
            if not cardData:
                print "Failed %s" % goal.name 
                continue
            if "method" in cardData:
                banned_methods.append(cardData["method"])
            if "parts" in cardData:
                banned_subgoals += [part["name"] for part in cardData["parts"]]
            output.append(cardData)
            groupSeen[goal.name] = (repeats+1, banned_subgoals, banned_methods) 
        return output

