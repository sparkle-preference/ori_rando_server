from random import choice, randint, sample
from collections import defaultdict, Counter
from datetime import datetime
import json
import logging as log

from webapp2 import RequestHandler, redirect, uri_for
from webapp2_extras.routes import RedirectRoute as Route
from google.appengine.ext.webapp import template

from enums import MultiplayerGameType
from models import Game, User, BingoCard, BingoGameData
from pickups import Pickup, Skill, AbilityCell, HealthCell, EnergyCell, Multiple
from util import param_val, param_flag, resp_error, debug, path
from seedbuilder.vanilla import seedtext as vanilla_seed

if debug:
    from test.data import bingo_data as test_data

BINGO_LATEST = [0,1,4]
def version_check(version):
    nums = [int(num) for num in version.split(".")]
    for latest,test in zip(BINGO_LATEST, nums):
        if latest > test:
            return False
        if test > latest:
            return True
    return True

class BingoGoal(object):
    max_repeats = 1
    tags = []
    def isAllowed(self, allowed_tags = []):
        # if any([tag not in allowed_tags for tag in self.tags]):
        #     print "Excluding %s for tag mismatch: [%s] contains an element not in [%s]" % (self.name, ",".join(self.tags), ",".join(allowed_tags))
        return not any([tag not in allowed_tags for tag in self.tags])

class BoolGoal(BingoGoal):
    goalType = "bool"
    def __init__(self, name, disp_name = None, help_lines = [], tags = []):
        self.name = name
        self.disp_name = disp_name or self.name
        self.help_lines = help_lines
        self.tags = set(tags)

    def to_card(self, banned = {}):
        return BingoCard(
            name = self.name,
            disp_name = self.disp_name,
            help_lines = self.help_lines[:],
            goal_type = "bool",
        )

class IntGoal(BingoGoal):
    goalType = "int"
    def __init__(self, name, disp_name, help_lines, range_func, tags = []):
        self.name = name
        self.disp_name = disp_name
        self.help_lines = help_lines
        self.range_func = range_func
        self.tags = set(tags)

    def to_card(self, banned = {}):
        return BingoCard(
            name = self.name,
            disp_name = self.disp_name,
            help_lines = self.help_lines[:],
            goal_type = "int",
            target = self.range_func()
        )


class GoalGroup(BingoGoal):
    def __init__(self, name, goals, methods, name_func, help_lines = [],  max_repeats = 1, tags = []):
        self.name = name
        self.methods = methods
        self.name_func = name_func
        self.help_lines = help_lines
        self.max_repeats = max_repeats
        self.goals = goals
        self.tags = set(tags)

    def to_card(self, banned = {}):
        card = BingoCard(
            name = self.name,
            goal_type = "multi",
        )
        hls = self.help_lines[:]

        card.goal_method, countFunc = choice([(m, c) for m, c in self.methods if m not in banned["methods"]])
        count = countFunc()
        if card.goal_method.startswith("count"):
            card.disp_name = self.name_func("", count > 1)
            if "always_list_subgoals" in self.tags:
                for subgoal in self.goals:
                    if subgoal.help_lines:
                        hls.append(subgoal.disp_name + ":" + subgoal.help_lines[0])
            card.help_lines = hls[:]
            card.target = count
            return card
        banned_tags = set()
        if count == 1:
            banned_tags.add("no_singleton")
        if card.goal_method.startswith("or"):
            banned_tags.add("no_or")
        subgoals = [goal for goal in self.goals if goal.name not in banned["goals"] and not (banned_tags & goal.tags)]
        count = min(count, len(subgoals))
        if count == 0:
            return None
        infix = ""
        plural = False
        if count == 1:
            infix = "this"
        elif card.goal_method.startswith("or"):
            infix = "EITHER" if count == 2 else "ANY"
        elif card.goal_method.startswith("and"):
            infix = "BOTH" if count == 2 else "EACH"
            plural = count == 2

        card.disp_name = self.name_func(infix, plural)
        subgoals = [subgoal.to_card().to_json() for subgoal in sample(subgoals, count)]
        for subgoal in subgoals:
            card.subgoals.append(subgoal)
            if(subgoal["help_lines"]):
                hls.append(subgoal["disp_name"] + ": " + subgoal["help_lines"][0])
        card.help_lines = hls[:]
        return card



def namef(verb, noun, plural_form = None):
    if not plural_form:
        plural_form = noun + "s"
    return lambda infix, plural: verb + ((" %s " % infix) if infix else " ") + (plural_form if plural else noun)

class BingoGenerator(object):
    @staticmethod
    def get_cards(count = 25, rando = False, difficulty = "normal"):
        easy = difficulty == "easy"
        hard = difficulty == "hard"

        def r(easy_params, params, hard_params, scalar=1):
            if easy:
                params = easy_params
            if hard:
                params = hard_params
            low, high = params
            return lambda: randint(low, high)*scalar
        tpGoals = [
            BoolGoal(name = "sunkenGlades", disp_name = "Sunken Glades", tags = ["no_or", "no_singleton"]),
            BoolGoal(name = "moonGrotto", disp_name = "Moon Grotto"),
            BoolGoal(name = "mangroveFalls", disp_name = "Blackroot Burrows"),
            BoolGoal(name = "valleyOfTheWind", disp_name = "Sorrow Pass"),
            BoolGoal(name = "spiritTree", disp_name = "Hollow Grove"),
            BoolGoal(name = "mangroveB", disp_name = "Lost Grove"),
            BoolGoal(name = "horuFields", disp_name = "Horu Fields"),
            BoolGoal(name = "ginsoTree", disp_name = "Ginso Tree"),
            BoolGoal(name = "forlorn", disp_name = "Forlorn Ruins"),
            BoolGoal(name = "mountHoru", disp_name = "Mount Horu"),
        ]
        if rando:
            tpGoals += [
                BoolGoal(name = "swamp", disp_name = "Thornfelt Swamp"),
                BoolGoal(name = "sorrowPass", disp_name = "Valley of the Wind")
            ]   
        goals = [
            BoolGoal(
                name = "DrainSwamp",
                disp_name = "Drain the Swamp",
                help_lines = ["Drain the pool in the area above and to the right of the Grotto Teleporter by breaking the blue barrier there."],
                ),
            BoolGoal(
                name = "WilhelmScream",
                disp_name = "Make Wilhelm Scream",
                help_lines = ["Throw Wilhelm (a green spitter on the top left cliff in the main Valley of the Wind room) off his cliff.", 
                        "Note: Wilhelm does not spawn unless you have the Sunstone."]
            ),
            IntGoal(
                name = "OpenKSDoors",
                disp_name = "Open keystone doors",
                help_lines = [
                    "Keystone doors by zone:", 
                    "Glades: 3 (First Door, Spirit Caverns Access, Spirit Tree Access)", 
                    "Grotto: 1 (Double Jump Access)", 
                    "Ginso: 2 (Bash Access, Ginso TP Access)",
                    "Swamp: 1 (Stomp Access)",
                    "Misty: 1 (Atsu's Torch Access)",
                    "Forlorn: 1 (Right Forlorn Access)"
                    "Sorrow: 3 (Questionable KS Door, Tumbleweed Door, Charge Jump Access)",
                    
                ] + (["NOTE: In Open Mode, First Door is already open and will not count."] if rando else []),
                range_func = r((2, 4), (4, 8), (7, 11))
            ),
            IntGoal(
                name = "OpenEnergyDoors", 
                disp_name = "Open energy doors",
                help_lines = [
                    "Energy doors by zone: ",
                    "Grotto: 2 (Glide Vault, Redirect Puzzle)",
                    "Glades: 3 (Gladezer, Death Gauntlet, Death Gauntlet Water)",
                    "Grove: 1 (Spidersack Energy Door)",
                    "Sorrow: 1 (Questionable Energy Door)"
                ],
                range_func  = r((2, 4), (3, 6), (4, 7)),
            ),
            IntGoal(
                name = "BreakFloors",
                disp_name = "Break floors or ceilings",
                help_lines = ["A floor or ceiling is a horizontal barrier that can be broken with a skill or enemy attack.",
                             "Almost half of the game's horizontal barriers are in either Sorrow or Swamp"],
                range_func = r((4, 10), (8, 24), (20, 42)),
            ),
            IntGoal(
                name = "BreakWalls",
                disp_name = "Break walls",
                help_lines = ["A wall is a vertical barrier that can be broken with a skill."],
                range_func = r((4, 10), (8, 20), (16, 28))
            ),
            IntGoal(
                name = "UnspentKeystones",
                disp_name = "Keystones in inventory",
                help_lines = ["Keyduping is allowed, and you can spend your keys after completing this goal."],
                range_func = r((6, 10), (8, 20), (20, 30))
            ),
            IntGoal(
                name = "BreakPlants",
                disp_name = "Break plants",
                help_lines = ["Plants are the large blue bulbs that can only be broken with Charge Flame, Grenade, or Charge Dash"],
                range_func = r((3, 8), (6, 15), (12, 21))
            ),
            IntGoal(
                name = "TotalPickups",
                disp_name = "Collect pickups",
                help_lines = ["This includes petrified plants, mapstone turnins, world events, and horu rooms."],
                range_func = (r((40, 80), (60, 140), (100, 180)) if rando else r((30, 60), (40, 120), (100, 140)))
            ),
            IntGoal(
                name = "UnderwaterPickups",
                disp_name = "Collect underwater pickups",
                help_lines = ["Pickups are considered underwater if they are submerged or in an area only reachable by swimming."],
                range_func = r((2, 6), (4, 10), (8, 16))
            ),
            IntGoal(
                name = "LightLanterns",
                disp_name = "Light Lanterns",
                help_lines = ["The lanterns in the pre-dash area of Blackroot Burrows do not count."],
                range_func = r((4, 6), (4, 10), (8, 14))
            ), 
            IntGoal(
                name = "SpendPoints",
                disp_name = "Spend Ability Points",
                help_lines = ["What you spend them on is up to you."],
                range_func = r((12, 15), (15, 30), (25, 35))
            ),
            IntGoal(
                name = "GainExperience",
                disp_name = "Gain spirit light",
                help_lines = ["bonus experience gained from Spirit Light Efficiency counts."],
                range_func = r((12, 20), (14, 28), (20, 40), scalar = 250)
            ),
            IntGoal(
                name = "KillEnemies",
                disp_name = "Kill enemies",
                help_lines = ["Large swarms count as 3 enemies (the initial swarm and the first split)"],
                range_func = r((25, 75), (50, 125), (75, 175))
            ),
            GoalGroup(
                name = "CompleteHoruRoom", 
                name_func = namef("Complete", "Horu room"),
                help_lines = ["A room is completed when the 'lava drain' animation plays"],
                goals = [
                    BoolGoal("L1", help_lines = ["Laser/Platform puzzle. Requires Stomp"]),
                    BoolGoal("L2", help_lines = ["Spinning Laser Block Push. Requires Stomp"]),
                    BoolGoal("L3", help_lines = ["Dangerous Path"]),
                    BoolGoal("L4", help_lines = ["Lava Escape/Spinning Laser. Requires Stomp"]),
                    BoolGoal("R1", help_lines = ["Spiked Elevators"]),
                    BoolGoal("R2", help_lines = ["Kill Elementals. Requires Stomp"]),
                    BoolGoal("R3", help_lines = ["Elevator of Death"]),
                    BoolGoal("R4", help_lines = ["Laser Tumbleweed Puzzle"]),
                ],
                methods = [
                    ("or", r((2, 3), (1, 3), (1, 1))), 
                    ("and", r((1, 2), (1, 3), (2, 4))), 
                    ("count", r((1, 3), (2, 4), (3, 7)))
                ]
                ),
            GoalGroup(
                name = "ActivateTeleporter", 
                name_func = namef("Activate", "spirit well"),
                help_lines = ["Activate spirit wells by standing on them or unlocking them via pickup"],
                goals = tpGoals, # defined above for reasons
                methods = [
                        ("or", r((1,2), (1,2), (1,1))), 
                        ("and", r((1, 2), (2, 3), (3, 4))), 
                        ("count", r((4, 7), (5, 9), (8, 11)))
                    ],
                max_repeats = 3
                ),
            GoalGroup(
                name = "EnterArea",
                name_func = namef("Enter", "area"),
                help_lines = ["Enter these areas (either manually or by teleporting into them)"],
                goals = [
                    BoolGoal("Lost Grove", help_lines = ["The upper boundary is the grenade door after the fight room, where the music changes"]),
                    BoolGoal("Misty Woods", help_lines = ["The first green frog is far enough"]),
                    BoolGoal("Sorrow Pass", help_lines = ["The lower boundary is where the always-on wind begins"]),
                    BoolGoal("Forlorn Ruins", help_lines = ["Requires the Gumon Seal or Forlorn TP. The Forlorn approach is in Valley, not Forlorn"]),
                    BoolGoal("Mount Horu", help_lines = ["Requires the Sunstone or Horu TP. Horu Fields is in Grove, not Horu"]),
                    BoolGoal("Ginso Tree", help_lines = ["Requires the Water Vein or Ginso TP"], tags = ["no_singleton"])
                ],
                methods = [
                    ("or", r((2, 3), (2, 2), (1, 1))), 
                    ("and", r((1, 1), (1, 2), (2, 3)))
                ],
                max_repeats = 2
                ),
            GoalGroup(
                name = "GetItemAtLoc", 
                name_func = namef("Get", "pickup"),
                help_lines = ["Collect the pickups in these locations"],
                goals = [
                    BoolGoal(name = "LostGroveLongSwim", disp_name = "Lost Grove Swim AC", help_lines = ["The ability cell behind the hidden underwater crushers in Lost Grove"]),
                    BoolGoal(name = "ValleyEntryGrenadeLongSwim", disp_name = "Valley Long Swim", help_lines = ["The energy cell at the end of the grenade-locked swim in Valley entry"]),
                    BoolGoal(name = "SpiderSacEnergyDoor", disp_name = "Spider Energy Door", help_lines = ["The ability cell behind the energy door in the spidersac area right of the Spirit Tree"]),
                    BoolGoal(name = "SorrowHealthCell", disp_name = "Sorrow HC", help_lines = ["The health cell in the room above the lowest keystone door in Sorrow"]),
                    BoolGoal(name = "SunstonePlant", disp_name = "Sunstone Plant", help_lines = ["The plant at the top of Sorrow"]),
                    BoolGoal(name = "GladesLaser", disp_name = "Gladzer EC", help_lines = ["The energy cell in the Glades Laser area, reachable via a hidden 4 energy door in Spirit Caverns"]),
                    BoolGoal(name = "LowerBlackrootLaserAbilityCell", disp_name = "BRB Right Laser AC", help_lines = ["The ability cell to the far right of the lower BRB area, past the very long laser"]),
                    BoolGoal(name = "MistyGrenade", disp_name = "Misty Grenade EX", help_lines = ["The grenade-locked Exp orb near the very end of Misty"]),
                    BoolGoal(name = "LeftSorrowGrenade", disp_name = "Sorrow Grenade EX", help_lines = ["The grenade-locked Exp orb in the far left part of lower Sorrow"]),
                    BoolGoal(name = "DoorWarpExp", disp_name = "Door Warp EX", help_lines = ["The hidden Exp orb in the bottom of Horu, across from the Final Escape access door"]),
                    BoolGoal(name = "HoruR3Plant", disp_name = "R3 Plant", help_lines = ["The plant behind the lava column in R3"]),
                    BoolGoal(name = "RightForlornHealthCell", disp_name = "Right Forlorn HC", help_lines = ["The health cell in the stomp-locked area at the far right of Forlorn"]),
                    BoolGoal(name = "ForlornEscapePlant", disp_name = "Forlorn Escape Plant", help_lines = ["The plant in Forlorn Escape (Missable if you start the escape but don't complete it!)"])
                ],
                methods = [
                    ("or", r((2, 3), (1, 2), (1, 1))), 
                    ("and", r((1, 1), (2, 3), (2, 4)))
                ],
                max_repeats = 2
                ),
            GoalGroup(
                name = "VisitTree",
                name_func = namef("Visit", "tree"),
                help_lines = ["'Tree' refers to a location where a skill is gained in the base game (Kuro's feather counts as a tree). For consistency with the randomizer, Sein / Spirit Flame does not count as a tree."],
                goals = [BoolGoal(name) for name in ["Wall Jump", "Charge Flame", "Double Jump", "Bash", "Stomp", "Glide", "Climb", "Charge Jump", "Grenade", "Dash"]],
                methods = [
                        ("or",    r((1, 3), (1, 2), (1, 1))), 
                        ("and",   r((1, 2), (2, 3), (3, 4))), 
                        ("count", r((4, 6), (4, 8), (7, 10)))
                    ],
                max_repeats = 2
                ),
            GoalGroup(
                name = "GetAbility", 
                name_func = namef("Level up", "ability", plural_form = "abilities"),
                goals = [BoolGoal(name, help_lines = ["requires %s ability points" % cost]) for name, cost in [("Ultra Defense", 19), ("Spirit Light Efficiency", 10), ("Ultra Stomp", 10)]],
                methods = [
                    ("or", r((2, 2), (1, 2), (1, 1))), 
                    ("and", r((1, 1), (1, 2), (2, 3)))
                ],
                max_repeats = 1
                ),
            GoalGroup(
                name = "StompPeg", 
                name_func = namef("Stomp", "peg"),
                help_lines = ["Pegs must be fully stomped to count; Using a Fronkey to stomp a peg is permitted"],
                goals = [
                    BoolGoal(name = "BlackrootTeleporter", disp_name = "BRB/Grotto", help_lines = ["The peg to the right of the blackroot TP; opens the shortcut between Blackroot and Grotto"]),
                    BoolGoal(name = "SwampPostStomp", disp_name = "Stomp Miniboss", help_lines = ["The peg to the right of the stomp tree; opens door to the Swamp Rhino miniboss"]),
                    BoolGoal(name = "GroveMapstoneTree", disp_name = "Buttercell", help_lines = ["The peg hidden in the tree near the Grove mapstone; opens the door to the underwater AC below"]),
                    BoolGoal(name = "HoruFieldsTPAccess", disp_name = "Horu Fields TP", help_lines = ["The peg behind the wall in Horu Fields; opens the door to the Horu Fields TP"]),
                    BoolGoal(name = "L1", disp_name = "L1", help_lines = ["The peg in L1; drains the lava"]),
                    BoolGoal(name = "R2", disp_name = "R2", help_lines = ["The peg in R2; drains the lava"]),
                    BoolGoal(name = "L2", disp_name = "L2", help_lines = ["The peg in L2; activates the spinning laser"]),
                    BoolGoal(name = "L4Fire", disp_name = "L4 (Upper)", help_lines = ["The upper peg in L4; activates the lava chase"]),
                    BoolGoal(name = "L4Drain", disp_name = "L4 (Lower)", help_lines = ["The lower peg in L4; drains the lava"]),
                    BoolGoal(name = "SorrowLasersArea", disp_name = "Sorrow Laser Area", help_lines = ["The peg in the laser / tumbleweed puzzle room in the middle of Sorrow; blocks a laser"]),
                    BoolGoal(name = "SpiderLake", disp_name = "Spider Lake", help_lines = ["The center post in the Spider Lake area of Grove; opens the underwater path between Grove and Grotto"]),
                    BoolGoal(name = "GroveGrottoUpper", disp_name = "DG Roof (Upper)", help_lines = ["The upper peg in the room connecting the Spider Lake area of Grove to the passageway between Glades and Grotto (Death Gauntlet); blocks a laser."]),
                    BoolGoal(name = "GroveGrottoLower", disp_name = "DG Roof (Lower)", help_lines = ["The lower peg in the room connecting the Spider Lake area of Grove to the passageway between Glades and Grotto (Death Gauntlet); blocks a laser."]),
                ],
                methods = [
                        ("or",    r((1, 3), (1, 2), (1, 1))), 
                        ("and",   r((1, 2), (2, 3), (3, 4))), 
                        ("count", r((3, 6), (4, 8), (6, 10)))
                    ],
                max_repeats = 2
            ),
            GoalGroup(
                name = "HuntEnemies",
                name_func = namef("Kill", "Miniboss"),
                help_lines = ["If there are multiple enemies, defeating all of them is required"],
                goals = [
                    BoolGoal(name = "Misty Miniboss", help_lines = ["The 2 jumping purple spitters at the end of Misty"]),
                    BoolGoal(name = "Lost Grove Fight Room", help_lines = ["The room with 2 birds and 2 slimes above the entrance to Lost Grove"]),
                    BoolGoal(name = "Grotto Miniboss", help_lines = ["The jumping purple spitter in lower left Grotto that protects one of the 2 keystones normally used for the Double Jump tree"]),
                    BoolGoal(name = "Lower Ginso Miniboss", help_lines = ["The purple spitter enemy below the Bash tree area in Ginso"]),
                    BoolGoal(name = "Upper Ginso Miniboss", help_lines = ["The elemental below the Ginso tree core"]),
                    BoolGoal(name = "Swamp Rhino Miniboss", disp_name = "Stomp Area Rhino", help_lines = ["The Rhino miniboss past the Stomp tree in Swamp"]),
                    BoolGoal(name = "Mount Horu Miniboss", disp_name = "Horu Final Miniboss",  help_lines = ["The orange jumping spitter enemy that blocks access to the final escape in Horu"])
                ] + ([
                    BoolGoal(name = "Fronkey Fight", help_lines = ["The 3 fronkeys fought after collecting Sein (don't alt+R!)"])
                ] if hard else []),
                methods = [
                        ("or",    r((1, 3), (1, 2), (1, 1))), 
                        ("and",   r((1, 2), (2, 3), (2, 4))), 
                        ("count", r((2, 4), (3, 5), (4, 7)))
                    ],
                max_repeats = 2,
                tags = ["always_list_subgoals"]
            ),
            GoalGroup(
                name = "CompleteEscape",
                name_func = namef("Escape", "dungeon"),
                goals = [
                    BoolGoal(name = "Forlorn Ruins", help_lines = ["Completed once you reach the plant at the end of the escape"]),
                    BoolGoal(name = "Ginso Tree", help_lines = ["Completed once you recieve the pickup at vanilla clean water" if rando else "Completed once you recieve clean water"]),
                    BoolGoal(name = "Mount Horu", help_lines = ["Completed once you finish the last room of the final escape"]),
                ],
                methods = [
                        ("or",    r((1, 3), (1, 2), (1, 1))), 
                        ("and",   r((1, 1), (1, 2), (2, 3))), 
                ]
            ),
            GoalGroup(
                name = "DieTo",
                name_func = namef("Die to", "thing"),
                help_lines = ["Saving to avoid losing your pickups is recommended"],
                goals = [
                    BoolGoal(name = "Sunstone Lightning", help_lines = ["The Lightning that strikes if you go too far left or right at the very top of Sorrow Pass"]),
                    BoolGoal(name = "Lost Grove Laser", help_lines = ["The laser in the very bottom right room in Lost Grove"]),
                    BoolGoal(name = "Forlorn Void", help_lines = ["The bottomless pit outside of Forlorn"]),
                    BoolGoal(name = "Stomp Rhino", help_lines = ["The Rhino miniboss past the Stomp tree in Swamp"]),
                    BoolGoal(name = "Horu Fields Acid", help_lines = ["The yellowish liquid in the lower area of the main Horu Fields room"]),
                    BoolGoal(name = "Doorwarp Lava", help_lines = ["The lava at the very bottom of Horu"]),
                    BoolGoal(name = "Ginso Escape Fronkey", disp_name = "Top Ginso Fronkey", help_lines = ["The fronkey in the second-to-last room of the Ginso Escape"]),
                    BoolGoal(name = "Blackroot Teleporter Crushers", disp_name = "BRB TP Crushers", help_lines = ["The crushers below the Blackroot Teleporter"]),
                    BoolGoal(name = "NoobSpikes", disp_name = "Sorrow Spike Maze", help_lines = ["The long spike maze room in upper sorrow with 2 keystones on each side."]),
                ],
                methods = [
                        ("or",    r((1, 2), (1, 2), (1, 1))), 
                        ("and",   r((1, 1), (1, 2), (2, 3))), 
                        ("and_",  r((1, 1), (1, 2), (2, 3))), 
                ],
                max_repeats = 3
            )
        ]
        if rando:
            goals += [
                IntGoal(
                    name = "HealthCellLocs",
                    disp_name = "Get pickups from Health Cells",
                    help_lines = ["Collect pickups from this many vanilla health cell locations."],                    
                    range_func = r((4, 7), (4, 9), (8, 11))
                    ),
                IntGoal(
                    name = "EnergyCellLocs",
                    disp_name = "Get pickups from Energy Cells",
                    help_lines = ["Collect pickups from this many vanilla energy cell locations."],
                    range_func = r((4, 7), (4, 9), (8, 13))
                ),
                IntGoal(
                    name = "AbilityCellLocs",
                    disp_name = "Get pickups from Ability Cells",
                    help_lines = ["Collect pickups from this many vanilla ability cell locations."],
                    range_func = r((6, 10), (8, 21), (15, 30))
                ),
                IntGoal(
                    name = "MapstoneLocs",
                    disp_name = "Get pickups from Mapstone Fragments",
                    help_lines = ["Collect pickups from this many vanilla mapstone fragment locations.", "(Mapstone fragments are the small pickups tracked in the top left of the screen)"],
                    range_func = r((3, 5), (3, 7), (5, 9))
                ),
                GoalGroup(
                    name = "VanillaEventLocs",
                    name_func = namef("Visit", "event location"),
                    help_lines = ["The event locations are where the 3 dungeon keys and Clean Water, Wind Restored, and Warmth Returned are obtained in the base game.", 
                                 "Visiting an event location requires getting (and keeping) the pickup at that location."],
                    goals = [BoolGoal(name) for name in ["Water Vein", "Gumon Seal", "Sunstone", "Clean Water", "Wind Restored", "Warmth Returned"]],
                    methods = [
                        ("or",    r((1, 2), (1, 2), (1, 1))), 
                        ("and",   r((1, 1), (1, 2), (2, 3))), 
                    ],
                    max_repeats = 2
                    ),
                GoalGroup(
                    name = "GetEvent",
                    name_func = namef("Find", "event"),
                    goals = [BoolGoal(name) for name in ["Water Vein", "Gumon Seal", "Sunstone"]],
                    methods = [
                        ("or",    r((1, 2), (1, 2), (1, 1))), 
                        ("and",   r((1, 1), (1, 2), (2, 3))), 
                    ],
                    max_repeats = 1
                ),
            ]
        else:
            goals += [
                IntGoal( name = "CollectMapstones",
                    disp_name = "Collect mapstones",
                    help_lines = ["You do not need to turn them in."],
                    range_func = r((3, 5), (3, 7), (5, 9))
                ),
                IntGoal( name = "ActivateMaps",
                    disp_name = "Activate map altars",
                    help_lines = ["There are map altars in every zone besides Misty and Ginso"],
                    range_func = r((3, 5), (3, 7), (5, 9))
                ),
                IntGoal( name = "HealthCells",
                    disp_name = "Collect Health Cells",
                    help_lines = ["Any bonus health cells you spawn with will not count."],
                    range_func = r((4, 7), (4, 9), (8, 11))
                ),
                IntGoal( name = "EnergyCells",
                    disp_name = "Collect Energy Cells",
                    help_lines = ["Any bonus energy cells you spawn with will not count."],
                    range_func = r((4, 7), (4, 9), (8, 13))
                ),
                IntGoal( name = "AbilityCells",
                    disp_name = "Collect Ability Cells",
                    help_lines = ["Any bonus ability cells you spawn with will not count."],
                    range_func = r((6, 10), (8, 21), (15, 30))
                ),
                GoalGroup(
                    name = "GetEvent",
                    name_func = namef("Get", "event"),
                    help_lines = ["Remember that half the events require one of the other events as a pre-requisite"],
                    goals = [BoolGoal(name) for name in ["Water Vein", "Gumon Seal", "Sunstone", "Clean Water", "Wind Restored", "Warmth Returned"]],
                    methods = [
                        ("or",    r((1, 3), (1, 2), (1, 1))),
                        ("and",   r((1, 1), (1, 2), (2, 3))),
                    ],
                    max_repeats = 2
                ),
            ]
        if hard:
            goals += [
                BoolGoal(
                    name = "CoreSkip",
                    disp_name = "Core Skip",
                    help_lines = ["Skip one of the Ginso core rooms by destroying both sets of brambles with a well-timed level-up."]
                ),
                BoolGoal(
                    name = "FastStompless",
                    disp_name = "Fast Stompless",
                    help_lines = ["Break the rocks above Kuro's head in the Valley of the Wind with a long-distance spider shot"]
                ),
            ]
        else:
            goals.append(BoolGoal(
                name = "DrownFrog",
                disp_name = "Drown an amphibian",
                help_lines = ["The amphibians native to Nibel are fronkeys, red spitters, and green spitters"]
            ))





        groupSeen = defaultdict(lambda: (1, [], []))
        cards = []
        goals = [goal for goal in goals]
        while len(cards) < count:
            goal = choice(goals)
            repeats, banned_subgoals, banned_methods = groupSeen[goal.name]
            if repeats == goal.max_repeats:
                goals.remove(goal)
            elif repeats > goal:
                assert "help?" and False
            card = goal.to_card(banned = {"methods": banned_methods, "goals": banned_subgoals})
            if not card:
                continue
            if card.goal_type == "multi":
                banned_methods.append(card.goal_method)
                card.goal_method = card.goal_method.strip('_')
                banned_subgoals += [subgoal["name"] for subgoal in card.subgoals] 
            groupSeen[goal.name] = (repeats+1, banned_subgoals, banned_methods)
            card.square = len(cards)
            cards.append(card)
        return cards

# handlers

class BingoBoard(RequestHandler):
    def get(self):
        template_values = {'app': "Bingo", 'title': "OriDE Bingo"}
        user = User.get()
        if user:
            template_values['user'] = user.name
            template_values['dark'] = user.dark_theme
        self.response.write(template.render(path, template_values))

class BingoCreate(RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'application/json'
        difficulty = param_val(self, "difficulty") or "normal"
        skills = param_val(self, "skills")
        cells = param_val(self, "cells")
        skills = int(skills) if skills and skills != "NaN" else 3
        cells = int(cells) if cells and cells != "NaN" else 3
        show_info = param_flag(self, "showInfo")
        misc_raw = param_val(self, "misc")
        misc_pickup = Pickup.from_str(misc_raw) if misc_raw and misc_raw != "NO|1" else None
        skill_pool = [Skill(x) for x in [0, 2, 3, 4, 5, 8, 12, 14, 50, 51]]
        cell_pool  = [Multiple.with_pickups([AbilityCell(1), AbilityCell(1)]), HealthCell(1), EnergyCell(1)]

        start_pickups = sample(skill_pool, skills)
        for _ in range(cells):
            start_pickups.append(choice(cell_pool))
        if misc_pickup:
            start_pickups.append(misc_pickup)
        start_with = Multiple.with_pickups(start_pickups)
        key = Game.new(_mode = "Bingo", _shared = [])
        if show_info and start_with:
            tps = []
            skills = []
            misc = []
            cells = Counter()
            for pick in start_with.children:
                if pick.code == "TP":
                    tps.append(pick.name[:-11])
                elif pick.code == "SK":
                    skills.append(pick.name)
                elif pick.code in ["HC", "EC", "AC"]:
                    cells[pick.code]+=1
                else:
                    misc.append(pick.name)
            sw_parts = []
            if skills:
                sw_parts.append("Skills: " + ", ".join(skills))
            if tps:
                sw_parts.append("TPs: " + ", ".join(tps))
            if cells:
                sw_parts.append("Cells: " + ", ".join([cell if amount == 1 else "%s %ss" % (amount, cell) for cell,amount in cells.items()]))
            if misc:
                sw_parts.append(", ".join(misc))
        base = vanilla_seed.split("\n")
        base[0] = "OpenWorld,Bingo|Bingo Game %s" % key.id()
        if start_with:
            mu_line = "2|MU|%s|Glades" % start_with.id
            base.insert(1, mu_line)
        
        game = key.get()
        game.bingo = BingoGameData(
            board      = BingoGenerator.get_cards(25, False, difficulty),
            difficulty = difficulty,
            start_time = datetime.now(),
            seed       = "\n".join(base),
        )
        user = User.get()
        if user:
            game.bingo.creator = user.key
        if show_info:
            game.bingo.subtitle = " | ".join(sw_parts)
        
        
        res = game.bingo_json(True)
        # {
        #     'gameId':     key.id(),
        #     'seed':       "\n".join(base),
        #     'cards':      BingoGenerator.get_cards(25, False, difficulty),
        #     'difficulty': difficulty,
        #     'playerData': {},
        #     'teams':      {},
        # }
        self.response.write(json.dumps(res))
        game.put()
 
class AddBingoToGame(RequestHandler):
    def get(self, game_id):
        self.response.headers['Content-Type'] = 'application/json'

        game_id = int(game_id)
        difficulty = param_val(self, "difficulty") or "normal"
        if not game_id or int(game_id) < 1:
            return resp_error(self, 404, "please provide a valid game id", 'plain/text')
        game = Game.with_id(game_id)
        if not game:
            return resp_error(self, 404, "game not found", 'plain/text')
        if not game.params:
            return resp_error(self, 412, "game did not have required seed data", 'plain/text')
        if game.mode in [MultiplayerGameType.SHARED, MultiplayerGameType.SPLITSHARDS]:
            return resp_error(self, 412, "Co-op / splitshards bingo are not currently supported", 'plain/text')
        params = game.params.get()
        params.tracking = False
        game.bingo = BingoGameData(
            board      = BingoGenerator.get_cards(25, True, difficulty),
            difficulty = difficulty,
            start_time = datetime.now(),
            seed       = "Bingo," + params.get_seed(),
            subtitle   = params.flag_line(),
        )
        res = game.bingo_json(True)
        # res = {
        #     'gameId':     game_id,
        #     'seed':       "Bingo," + params.get_seed(),
        #     'cards':      BingoGenerator.get_cards(25, True, difficulty),
        #     'difficulty': difficulty,
        #     'subtitle':   params.flag_line(),
        #     'playerData': {},
        #     'teams':      {},
        # }
        # game.bingo = res
        self.response.write(json.dumps(res))
        for p in game.get_players():
            game.remove_player(p.key.id())
        game.put()

class BingoAddPlayer(RequestHandler):
    def get(self, game_id, player_id):
        player_id = int(player_id)
        res = {}
        game = Game.with_id(game_id)
        if not game:
            return resp_error(self, 404, "Game not found", "text/plain")
        if player_id in game.player_nums():
            return resp_error(self, 409, "Player id already in use!", "text/plain")
        p = game.player(player_id)
        user = User.get()
        pkey = None
        if user:
            p.user = user.key
            p.put()
            user.games.append(game.key)
            user.put()
        cap_id = int(param_val(self, "joinTeam") or player_id)
        team = game.bingo_team(cap_id)
        if not team:
            team = {'bingos': [], 'cap': cap_id, 'teammates': []}
            game.bingo.teams += [team]
        elif pkey != team["cap"] and pkey not in team["teammates"]:
            team["teammates"].append(pkey)
        else:
            log.error("In bingo game %s, team %s already had player %s!", game.key.id(), team, player_id)
        game = game.put().get()

        res = game.bingo_json()
        
        # res["playerData"] = {}
        # for player in game.get_players():
        #     pid = player.pid()
        #     res["playerData"][pid] = {'name': player.name(), 'teamname': player.teamname(), 'bingoData': player.bingo_data}

        self.response.headers['Content-Type'] = 'application/json'
        self.response.write(json.dumps(res))

class BingoGetGame(RequestHandler):
    def get(self, game_id):
        res = {}
        game = Game.with_id(game_id)
        if not game:
            return resp_error(self, 404, "Game not found", "text/plain")
            
        if not game.bingo:
            return resp_error(self, 404, "Game found but had no bingo data...", "text/plain")
        res = game.bingo_json(param_flag(self, "first"))

        self.response.headers['Content-Type'] = 'application/json'
        self.response.write(json.dumps(res))

class HandleBingoUpdate(RequestHandler):
    def get(self, game_id, player_id):
        if debug:
            self.post(game_id, player_id)
    def post(self, game_id, player_id):
        game = Game.with_id(game_id)
        if not game:
            return resp_error(self, 404)
        p = game.player(player_id)
        bingo_data = json.loads(self.request.POST["bingoData"]) if "bingoData" in self.request.POST  else None
        need_update = version_check(self.request.POST["version"]) if "version" in self.request.POST else False
        if debug and player_id in test_data:
            bingo_data = test_data[player_id]['bingoData']
        game.bingo_update(bingo_data, player_id, need_update)

routes = [
    Route('/bingo/board', handler = BingoBoard, name = "bingo-board", strict_slash = True),
    Route('/bingo/spectate', handler = BingoBoard, name = "bingo-board-spectate", strict_slash = True),
    Route('/bingo/game/<game_id>/fetch', handler = BingoGetGame, name = "bingo-get-game", strict_slash = True),
    Route('/bingo/game/<game_id>/add/<player_id>', handler = BingoAddPlayer, name = "bingo-add-player", strict_slash = True),
    Route('/bingo/new', handler = BingoCreate, name = "bingo-create-game", strict_slash = True),
    Route('/bingo/from_game/<game_id>', handler = AddBingoToGame, name = "add-bingo-to-game", strict_slash = True),
    Route('/netcode/game/<game_id:\d+>/player/<player_id:\d+>/bingo', handler = HandleBingoUpdate,  name = "netcode-player-bingo-tick"),
]

