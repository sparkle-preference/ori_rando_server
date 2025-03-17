import random
from collections import defaultdict, Counter
from datetime import datetime, timedelta
from time import sleep
import json
import logging as log

from cache import Cache
from enums import MultiplayerGameType, Variation
from models import Game, User, BingoCard, BingoGameData, BingoEvent, BingoTeam
from util import param_val, param_flag, debug, path, VER, version_check
from seedbuilder.vanilla import seedtext as vanilla_seed

# if debug:
#     from test.data import bingo_data as test_data

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

    def to_card(self, rand, banned = {}):
        return BingoCard(
            name = self.name,
            disp_name = self.disp_name,
            help_lines = [str(l) for l in self.help_lines],
            goal_type = "bool",
            early = "early" in self.tags,
            meta = "meta" in self.tags
        )

class IntGoal(BingoGoal):
    goalType = "int"
    def __init__(self, name, disp_name, help_lines, range_func, early_max = None, tags = []):
        self.name = name
        self.disp_name = disp_name
        self.help_lines = help_lines
        self.range_func = range_func
        self.early_max = early_max
        self.tags = set(tags)
        if early_max and self.range_func.min < early_max:
            self.tags.add("early")
        

    def to_card(self, rand, banned = {}):
        t = self.range_func()
        return BingoCard(
            name = self.name,
            disp_name = self.disp_name,
            help_lines = self.help_lines[:],
            goal_type = "int",
            target = t,
            early = t <= self.early_max if self.early_max else False,
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

    def to_card(self, rand, banned = {}):
        card = BingoCard(
            name = self.name,
            goal_type = "multi",
            meta = "meta" in self.tags
        )
        hls = self.help_lines[:]

        card.goal_method, countFunc = rand.choice([(m, c) for m, c in self.methods if m not in banned["methods"]])
        count = countFunc()
        if card.goal_method.startswith("count"):
            card.disp_name = self.name_func("", count > 1)
            if "always_list_subgoals" in self.tags:
                for subgoal in self.goals:
                    if subgoal.help_lines:
                        hls.append(subgoal.disp_name + ":" + subgoal.help_lines[0])
            card.help_lines = hls[:]
            card.target = count
            card.early = False
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
        subgoals = [subgoal.to_card(rand) for subgoal in rand.sample(subgoals, count)]
        if count == 1:
            infix = "this"
            card.early = subgoals[0].early
        elif card.goal_method.startswith("or"):
            infix = "EITHER" if count == 2 else "ANY"
            card.early = any([s.early for s in subgoals])
        elif card.goal_method.startswith("and"):
            infix = "BOTH" if count == 2 else "EACH"
            plural = count == 2
            card.early = all([s.early for s in subgoals])
        
        card.disp_name = self.name_func(infix, plural)
        for subgoal in subgoals:
            sjson = subgoal.to_json([], True)
            card.subgoals.append(sjson)
            if sjson["help_lines"]:
                hls.append(sjson["disp_name"] + ": " + sjson["help_lines"][0])
        
        card.help_lines = hls[:]
        return card



def namef(verb, noun, plural_form = None):
    if not plural_form:
        plural_form = noun + "s"
    return lambda infix, plural: verb + ((" %s " % infix) if infix else " ") + (plural_form if plural else noun)

class BingoGenerator(object):
    @staticmethod
    def get_cards(rand, count = 25, rando = False, difficulty = "normal", open_world = True, discovery = 0, meta = False, lockout = False):
        easy = difficulty == "easy"
        hard = difficulty == "hard"

        def r(easy_params, params, hard_params, scalar=1, flat=False):
            low, high = easy_params if easy else (hard_params if hard else params)
            func = (lambda: rand.randint(low, high)*scalar) if flat else (lambda: int(round(rand.triangular(low, high, (low+high) * 3.0 / 5.0)))*scalar)
            func.min = low
            return func

        tpGoals = [
            BoolGoal(name = "sunkenGlades", disp_name = "Sunken Glades", tags = ["no_or", "no_singleton", "early"]),
            BoolGoal(name = "moonGrotto", disp_name = "Moon Grotto", tags = [ "early" ]),
            BoolGoal(name = "mangroveFalls", disp_name = "Blackroot Burrows", tags = [ "early" ]),
            BoolGoal(name = "valleyOfTheWind", disp_name = "Sorrow Pass"),
            BoolGoal(name = "sorrowPass", disp_name = "Valley of the Wind"),
            BoolGoal(name = "spiritTree", disp_name = "Hollow Grove", tags = [ "early" ]),
            BoolGoal(name = "mangroveB", disp_name = "Lost Grove"),
            BoolGoal(name = "horuFields", disp_name = "Horu Fields"),
            BoolGoal(name = "ginsoTree", disp_name = "Ginso Tree"),
            BoolGoal(name = "forlorn", disp_name = "Forlorn Ruins"),
            BoolGoal(name = "mountHoru", disp_name = "Mount Horu"),
        ]
        if rando:
            tpGoals += [
                BoolGoal(name = "swamp", disp_name = "Thornfelt Swamp", tags = [ "early" ]),
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
                disp_name = "Make Wilhelm scream",
                help_lines = ["Throw Wilhelm (a green spitter on the top left cliff in the main Valley of the Wind room) off his cliff.", 
                        "Note: Wilhelm does not spawn unless you have the Sunstone."]
            ),
            IntGoal(
                name = "OpenKSDoors",
                disp_name = "Open keystone doors",
                help_lines = [
                    "Keystone doors by zone:", 
                    "Glades: 2 (Spirit Caverns Access, Spirit Tree Access)" if open_world else "Glades: 3 (First Door, Spirit Caverns Access, Spirit Tree Access)", 
                    "Grotto: 1 (Double Jump Access)", 
                    "Ginso: 2 (Bash Access, Ginso TP Access)",
                    "Swamp: 1 (Stomp Access)",
                    "Misty: 1 (Atsu's Torch Access)",
                    "Forlorn: 1 (Right Forlorn Access)"
                    "Sorrow: 3 (Questionable KS Door, Tumbleweed Door, Charge Jump Access)",
                ],
                range_func = r((2, 4), (4, 8), (7, 11)),
                early_max = 3
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
                range_func = r((4, 10), (8, 24), (20, 42))                
            ),
            IntGoal(
                name = "BreakWalls",
                disp_name = "Break walls",
                help_lines = ["A wall is a vertical barrier that can be broken with a skill."],
                range_func = r((4, 10), (8, 20), (16, 28)),
            ),
            IntGoal(
                name = "UnspentKeystones",
                disp_name = "Keystones in inventory",
                help_lines = ["Keyduping is allowed, and you can spend your keys after completing this goal."],
                range_func = r((6, 10), (8, 20), (20, 30)),
                early_max = 10
            ),
            IntGoal(
                name = "BreakPlants",
                disp_name = "Break plants",
                help_lines = ["Plants are the large blue bulbs that can only be broken with Charge Flame, Grenade, or Charge Dash"],
                range_func = r((3, 8), (6, 15), (12, 21)),
                early_max = 9
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
                range_func = r((2, 6), (4, 10), (8, 16)),
                early_max = 5
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
            IntGoal(
                name = "PickupsInGlades",
                disp_name = "Collect Pickups In Glades",
                help_lines = ["You can use the stats feature (alt+5 by default) to see your pickup counts by zone.", "Mapstone turn-ins are not in any zone."],
                range_func = r((8, 15), (10, 22), (16, 27)),
                early_max = 16,
                tags = ["pickups_in_zone"]
            ),
            IntGoal(
                name = "PickupsInGrove",
                disp_name = "Collect Pickups In Grove",
                help_lines = ["You can use the stats feature (alt+5 by default) to see your pickup counts by zone.", "Mapstone turn-ins are not in any zone."],
                range_func = r((7, 14), (10, 19), (16, 26)),
                tags = ["pickups_in_zone"],
                early_max = 9
            ),
            IntGoal(
                name = "PickupsInGrotto",
                disp_name = "Collect Pickups In Grotto",
                help_lines = ["You can use the stats feature (alt+5 by default) to see your pickup counts by zone.", "Mapstone turn-ins are not in any zone."],
                range_func = r((8, 16), (12, 28), (20, 33)),
                tags = ["pickups_in_zone"],
                early_max = 12
            ),
            IntGoal(
                name = "PickupsInBlackroot",
                disp_name = "Collect Pickups In Blackroot",
                help_lines = ["You can use the stats feature (alt+5 by default) to see your pickup counts by zone.", "Mapstone turn-ins are not in any zone."],
                range_func = r((4, 10), (7, 15), (10, 19)),
                tags = ["pickups_in_zone"],
                early_max = 8
            ),
            IntGoal(
                name = "PickupsInSwamp",
                disp_name = "Collect Pickups In Swamp",
                help_lines = ["You can use the stats feature (alt+5 by default) to see your pickup counts by zone.", "Mapstone turn-ins are not in any zone."],
                range_func = r((4, 10), (7, 16), (11, 20)),
                tags = ["pickups_in_zone"]                
            ),
            IntGoal(
                name = "PickupsInGinso",
                disp_name = "Collect Pickups In Ginso",
                help_lines = ["You can use the stats feature (alt+5 by default) to see your pickup counts by zone.", "Mapstone turn-ins are not in any zone."],
                range_func = r((6, 12), (8, 18), (12, 22)),
                tags = ["pickups_in_zone"]
            ),
            IntGoal(
                name = "PickupsInValley",
                disp_name = "Collect Pickups In Valley",
                help_lines = ["You can use the stats feature (alt+5 by default) to see your pickup counts by zone.", "Mapstone turn-ins are not in any zone."],
                range_func = r((4, 9), (7, 14), (11, 18)),
                tags = ["pickups_in_zone"]
            ),
        IntGoal(
                name = "PickupsInMisty",
                disp_name = "Collect Pickups In Misty",
                help_lines = ["You can use the stats feature (alt+5 by default) to see your pickup counts by zone.", "Mapstone turn-ins are not in any zone."],
                range_func = r((4, 8), (6, 13), (10, 16)),
                tags = ["pickups_in_zone"]
            ),
            IntGoal(
                name = "PickupsInForlorn",
                disp_name = "Collect Pickups In Forlorn",
                help_lines = ["You can use the stats feature (alt+5 by default) to see your pickup counts by zone.", "Mapstone turn-ins are not in any zone."],
                range_func = r((3, 6), (5, 9), (8, 10)),
                tags = ["pickups_in_zone"]
            ),
            IntGoal(
                name = "PickupsInSorrow",
                disp_name = "Collect Pickups In Sorrow",
                help_lines = ["You can use the stats feature (alt+5 by default) to see your pickup counts by zone.", "Mapstone turn-ins are not in any zone."],
                range_func = r((7, 14), (8, 19), (16, 26)),
                tags = ["pickups_in_zone"]
            ),
            IntGoal(
                name = "PickupsInHoru",
                disp_name = "Collect Pickups In Horu",
                help_lines = ["You can use the stats feature (alt+5 by default) to see your pickup counts by zone.", "Mapstone turn-ins are not in any zone."],
                range_func = r((4, 10), (7, 15), (10, 19)),
                tags = ["pickups_in_zone"]
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
                    ("or", r((2, 3), (1, 3), (1, 1), flat=True)), 
                    ("and", r((1, 2), (1, 3), (2, 4), flat=True)), 
                    ("count", r((1, 3), (2, 4), (3, 7), flat=True))
                ]
                ),
            GoalGroup(
                name = "ActivateTeleporter", 
                name_func = namef("Activate", "spirit well"),
                help_lines = ["Activate spirit wells by standing on them or unlocking them via pickup"],
                goals = tpGoals, # defined above for reasons
                methods = [
                        ("or", r((1,2), (1,2), (1,1), flat=True)), 
                        ("and", r((1, 2), (2, 3), (3, 4), flat=True)), 
                        ("count", r((4, 7), (5, 9), (8, 11), flat=True))
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
                    ("or", r((2, 3), (2, 2), (1, 1), flat=True)), 
                    ("and", r((1, 1), (1, 2), (2, 3), flat=True))
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
                    BoolGoal(name = "SpiderSacEnergyDoor", disp_name = "Spider Energy Door", help_lines = ["The ability cell behind the energy door in the spidersac area right of the Spirit Tree"], tags = [ "early" ]),
                    BoolGoal(name = "SorrowHealthCell", disp_name = "Sorrow HC", help_lines = ["The health cell in the room above the lowest keystone door in Sorrow"]),
                    BoolGoal(name = "SunstonePlant", disp_name = "Sunstone Plant", help_lines = ["The plant at the top of Sorrow"]),
                    BoolGoal(name = "GladesLaser", disp_name = "Gladzer EC", help_lines = ["The energy cell in the Glades Laser area, reachable via a hidden 4 energy door in Spirit Caverns"],tags = [ "early" ]),
                    BoolGoal(name = "LowerBlackrootLaserAbilityCell", disp_name = "BRB Right Laser AC", help_lines = ["The ability cell to the far right of the lower BRB area, past the very long laser"]),
                    BoolGoal(name = "MistyGrenade", disp_name = "Misty Grenade EX", help_lines = ["The grenade-locked Exp orb near the very end of Misty"]),
                    BoolGoal(name = "LeftSorrowGrenade", disp_name = "Sorrow Grenade EX", help_lines = ["The grenade-locked Exp orb in the far left part of lower Sorrow"]),
                    BoolGoal(name = "DoorWarpExp", disp_name = "Door Warp EX", help_lines = ["The hidden Exp orb in the bottom of Horu, across from the Final Escape access door"]),
                    BoolGoal(name = "HoruR3Plant", disp_name = "R3 Plant", help_lines = ["The plant behind the lava column in R3"]),
                    BoolGoal(name = "RightForlornHealthCell", disp_name = "Right Forlorn HC", help_lines = ["The health cell in the stomp-locked area at the far right of Forlorn"]),
                    BoolGoal(name = "ForlornEscapePlant", disp_name = "Forlorn Escape Plant", help_lines = ["The plant in Forlorn Escape (Missable if you start the escape but don't complete it!)"])
                ],
                methods = [
                    ("or", r((2, 3), (1, 2), (1, 1), flat=True)), 
                    ("and", r((1, 1), (2, 3), (2, 4), flat=True))
                ],
                max_repeats = 2
                ),
            GoalGroup(
                name = "VisitTree",
                name_func = namef("Visit", "tree"),
                help_lines = ["'Tree' refers to a location where a skill is gained in the base game (Kuro's feather counts as a tree). For consistency with the randomizer, Sein / Spirit Flame does not count as a tree."],
                goals = [BoolGoal(name) for name in ["Wall Jump", "Charge Flame", "Double Jump", "Bash", "Stomp", "Glide", "Climb", "Charge Jump", "Grenade", "Dash"]],
                methods = [
                        ("or",    r((1, 3), (1, 2), (1, 1), flat=True)), 
                        ("and",   r((1, 2), (2, 3), (3, 4), flat=True)), 
                        ("count", r((4, 6), (4, 8), (7, 10), flat=True))
                    ],
                max_repeats = 2
                ),
            GoalGroup(
                name = "GetAbility", 
                name_func = namef("Level up", "ability", plural_form = "abilities"),
                goals = [BoolGoal(name, help_lines = ["in the %s ability tree. requires %s ability points" % (color, cost)]) for name, cost, color in [("Ultra Defense", 19, "Blue"), ("Spirit Potency", 10, "Purple"), ("Ultra Stomp", 10, "Red")]],
                methods = [
                    ("or", r((2, 2), (1, 2), (1, 1), flat=True)), 
                    ("and", r((1, 1), (1, 2), (2, 3), flat=True))
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
                    BoolGoal(name = "ForlornLaserPeg", disp_name = "Right Forlorn Access", help_lines = ["The peg in Forlorn, near the moving lasers; opens the door to the right Forlorn HC and plant."]),
                ],
                methods = [
                        ("or",    r((1, 3), (1, 2), (1, 1), flat=True)),
                        ("and",   r((1, 2), (2, 3), (3, 4), flat=True)),
                        ("count", r((3, 6), (4, 8), (6, 10), flat=True))
                    ],
                max_repeats = 2
            ),
            GoalGroup(
                name = "HuntEnemies",
                name_func = namef("Open", "Purple Door", "Purple Doors"),
                help_lines = ["Purple doors are opened by defeating nearby enemies. (R2 has 2 purple doors, but only the second one is counted.)"],
                goals = [
                    BoolGoal(name = "Misty Miniboss", help_lines = ["Kill the 2 jumping purple spitters at the end of Misty"]),
                    BoolGoal(name = "Lost Grove Fight Room", help_lines = ["Kill the 2 birds and 2 slimes above the entrance to Lost Grove"]),
                    BoolGoal(name = "Frog Toss", disp_name = "Lower BRB Frogs", help_lines = ["Kill 2 frogs on either side of the purple door across from the lower lasers."]),
                    BoolGoal(name = "R2", disp_name = "R2 (Upper)", help_lines = ["Kill 8 elementals in R2"]),
                    BoolGoal(name = "Grotto Miniboss", help_lines = ["Kill the jumping purple spitter in lower left Grotto that protects one of the 2 keystones normally used for the Double Jump tree"], tags = ["early"]),
                    BoolGoal(name = "Lower Ginso Miniboss", help_lines = ["Kill the purple spitter enemy below the Bash tree area in Ginso"]),
                    BoolGoal(name = "Upper Ginso Miniboss", help_lines = ["Kill the elemental below the Ginso tree core"]),
                    BoolGoal(name = "Swamp Rhino Miniboss", disp_name = "Stomp Area Rhino", help_lines = ["Kill the rhino miniboss past the Stomp tree in Swamp"]),
                    BoolGoal(name = "Mount Horu Miniboss", disp_name = "Horu Final Miniboss",  help_lines = ["Kill the orange jumping spitter enemy that blocks access to the final escape in Horu"])
                ],
                methods = [
                        ("or",    r((1, 3), (1, 2), (1, 1), flat=True)),
                        ("and",   r((1, 2), (2, 3), (2, 4), flat=True)),
                        ("count", r((2, 4), (3, 6), (5, 9), flat=True))
                    ],
                max_repeats = 2,
                tags = ["always_list_subgoals"]
            ),
            GoalGroup(
                name = "CompleteEscape",
                name_func = namef("Escape", "dungeon"),
                goals = [
                    BoolGoal(name = "Forlorn Ruins", help_lines = ["Completed once you reach the plant at the end of the Forlorn escape"]),
                    BoolGoal(name = "Ginso Tree", help_lines = ["Completed once you recieve the pickup at vanilla clean water" if rando else "Completed once you recieve clean water"]),
                    BoolGoal(name = "Mount Horu", help_lines = ["Completed once you finish the last room of the Horu escape. If this is not your last goal, Alt+R once you regain control of Ori!"]),
                ],
                methods = [
                    ("or",    r((1, 3), (1, 2), (1, 1), flat=True)),
                    ("and",   r((1, 1), (1, 2), (2, 3), flat=True)),
                ]
            ),
            GoalGroup(
                name = "DieTo",
                name_func = namef("Die to", "thing"),
                help_lines = ["Rekindle when you respawn to avoid accidentally losing progress"],
                goals = [
                    BoolGoal(name = "Sunstone Lightning", help_lines = ["The Lightning that strikes if you go too far left or right at the very top of Sorrow Pass"]),
                    BoolGoal(name = "Lost Grove Laser", help_lines = ["The laser in the very bottom right room in Lost Grove"]),
                    BoolGoal(name = "Forlorn Void", help_lines = ["The bottomless pit outside of Forlorn"]),
                    BoolGoal(name = "Stomp Rhino", help_lines = ["The Rhino miniboss past the Stomp tree in Swamp"]),
                    BoolGoal(name = "Horu Fields Acid", help_lines = ["The yellowish liquid in the lower area of the main Horu Fields room"]),
                    BoolGoal(name = "Doorwarp Lava", help_lines = ["The lava at the very bottom of Horu"]),
                    BoolGoal(name = "Ginso Escape Fronkey", disp_name = "Ginso Escape Fronkey", help_lines = ["Any fronkey in the Ginso Escape (you can complete the escape and come back via the teleporter)"]),
                    BoolGoal(name = "Blackroot Teleporter Crushers", disp_name = "BRB TP Crushers", help_lines = ["The crushers below the Blackroot Teleporter"], tags = ["early"]),
                    BoolGoal(name = "NoobSpikes", disp_name = "Sorrow Spike Maze", help_lines = ["The long spike maze room in upper sorrow with 2 keystones on each side"]),
                    BoolGoal(name= "Right Forlorn Laser", help_lines = ["The lasers above the HC and rightmost plant in Forlorn"]),
                    BoolGoal(name= "Misty Vertical Lasers", help_lines = ["The vertical lasers past the 3rd keystone in Misty"])
                ],
                methods = [
                        ("or",    r((1, 2), (1, 2), (1, 1), flat=True)),
                        ("or_",   r((1, 2), (1, 2), (1, 1), flat=True)),
                        ("and",   r((1, 1), (1, 2), (2, 3), flat=True)),
                        ("and_",  r((1, 1), (1, 2), (2, 3), flat=True)),
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
                    range_func = r((4, 7), (4, 9), (8, 11)),
                    early_max = 7
                    ),
                IntGoal(
                    name = "EnergyCellLocs",
                    disp_name = "Get pickups from Energy Cells",
                    help_lines = ["Collect pickups from this many vanilla energy cell locations."],
                    range_func = r((4, 7), (4, 9), (8, 13)),
                    early_max = 6
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
                    range_func = r((3, 5), (3, 7), (5, 9)),
                    early_max = 4
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
                    name_func = namef("Find", "key"),
                    help_lines = ["If you can't find a key and your keymode is clues, consider rushing skill trees",
                                  "If you can't find a key and your keymode is not clues, consider making your next (and all future) bingo seeds with keymode clues."],
                    goals = [BoolGoal(name) for name in ["Water Vein", "Gumon Seal", "Sunstone"]],
                    methods = [
                        ("or",    r((1, 2), (1, 2), (1, 1))), 
                        ("and",   r((1, 1), (1, 2), (2, 3))), 
                    ],
                    max_repeats = 1
                ),
                GoalGroup(
                    name = "TouchMapstone",
                    name_func = namef("Touch", "Map altar"),
                    help_lines = ["To touch a map altar, have Sein enter the slot"],
                    goals = [
                        BoolGoal(name = "sunkenGlades", disp_name = "Glades", tags = ["early"]),
                        BoolGoal(name = "hollowGrove", disp_name = "Grove", tags = ["early"]),
                        BoolGoal(name = "moonGrotto", disp_name = "Grotto", tags = ["early"]),
                        BoolGoal(name = "mangrove", disp_name = "Blackroot", tags = ["early"]),
                        BoolGoal(name = "thornfeltSwamp", disp_name = "Swamp"),
                        BoolGoal(name = "valleyOfTheWind", disp_name = "Valley"),
                        BoolGoal(name = "forlornRuins", disp_name = "Forlorn"),
                        BoolGoal(name = "sorrowPass", disp_name = "Sorrow"),
                        BoolGoal(name = "mountHoru", disp_name = "Horu"),
                    ],
                methods = [
                        ("or",    r((1, 3), (1, 2), (1, 1), flat=True)), 
                        ("and",   r((1, 2), (2, 3), (3, 4), flat=True)), 
                        ("count", r((3, 6), (4, 8), (6, 9), flat=True))
                    ],
                max_repeats = 2
                )
            ]
        else:
            goals += [
                IntGoal( name = "CollectMapstones",
                    disp_name = "Collect mapstones",
                    help_lines = ["You do not need to turn them in."],
                    range_func = r((3, 5), (3, 7), (5, 9))
                ),
                IntGoal(name = "ActivateMaps",
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
                        ("or",    r((1, 3), (1, 2), (1, 1), flat=True)),
                        ("and",   r((1, 1), (1, 2), (2, 3), flat=True)),
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
                help_lines = ["The amphibians native to Nibel are fronkeys, red spitters, and green spitters"],
                tags = ["early"]
            ))
        if meta:
            if not lockout:
                goals += [
                    BoolGoal("VertSym",
                    disp_name= "Vertically symmetric board",
                    help_lines = [
                        "Your bingo board is vertically symmetric if for every completed square in columns A and B, the same squares in columns D and E are completed.", 
                        "You can regain and lose this square based on changes to your bingo board."
                        ],
                    tags=["early", "meta", "symmetry"]
                    ),
                    BoolGoal("HorizSym",
                    disp_name= "Horizontally symmetric board",
                    help_lines = [
                        "Your bingo board is horizontally symmetric if for every completed square in rows 1 and 2, the same squares in row 4 and 5 are completed.", 
                        "You can regain and lose this square based on changes to your bingo board."
                        ],
                    tags=["early", "meta", "symmetry"]
                    ),
                ]
            goals.append(GoalGroup(
                    name = "Activate Squares",
                    name_func = namef("Activate", "square"),
                    help_lines = ["To activate a square, complete the goal specified on that square."],
                    goals = [ BoolGoal("SQUARE_PLACEHOLDER_%s" % i) for i in range(20)],
                    methods = [
                        ("or",    r((1, 3), (2, 2), (1, 1), flat=True)), 
                        ("or_",   r((1, 3), (1, 2), (1, 1), flat=True)), 
                        ("and",   r((1, 2), (2, 2), (2, 3), flat=True)), 
                        ("and_",  r((1, 2), (1, 3), (2, 3), flat=True)), 
                    ],
                    max_repeats = 4,
                    tags = ["meta"]
                ),
            )
        groupSeen = defaultdict(lambda: (1, [], []))
        cards = []
#        goals = [goal for goal in goals]
        pickups_in = rand.randint(2,4)
        patience = 7 * discovery
        meta_count = rand.randint(2,5) if meta else 0
        no_symmetry = False
        is_disc = discovery > 0
        while len(cards) < count:
            goal = None
            if meta_count > 0:
                meta_goals = [goal for goal in goals if "meta" in goal.tags and not (no_symmetry and "symmetry" in goal.tags)]
                log.warning("want %s meta goals, have %s possible" % (meta_count, len(meta_goals)))
                if len(meta_goals):
                    goal = rand.choice(meta_goals)
                    meta_count -= 1
                else:
                    log.error("Not enough meta goals! D:")
                    meta_count = 0
                    continue

            elif discovery > 0:
                early_goals = [goal for goal in goals if "early" in goal.tags]
                if len(early_goals):
                    goal = rand.choice(early_goals)
                    if isinstance(goal, IntGoal):
                        drange = (goal.range_func.min, goal.early_max)
                        goal.range_func = r(drange, drange, drange)
            else:
                goal = rand.choice(goals)
            if "pickups_in_zone" in goal.tags:
                if pickups_in > 0:
                    pickups_in -= 1
                else:
                    continue
            repeats, banned_subgoals, banned_methods = groupSeen[goal.name]
            if repeats == goal.max_repeats:
                goals.remove(goal)
            card = goal.to_card(rand, banned = {"methods": banned_methods, "goals": banned_subgoals})
            if not card:
                continue
            if discovery > 0 and patience > 0:
                if card.early:
                    discovery -= 1
                    patience += 1
                else:
                    patience -= 1
                    continue
            if card.goal_type == "multi":
                banned_methods.append(card.goal_method)
                card.goal_method = card.goal_method.strip('_')
                banned_subgoals += [subgoal["name"] for subgoal in card.subgoals]
            if "symmetry" in goal.tags and not no_symmetry:
                no_symmetry = rand.randint(0,8)<3 # hehe less than 3 
            groupSeen[goal.name] = (repeats+1, banned_subgoals, banned_methods)
            cards.append(card)
        rand.shuffle(cards)
        if is_disc:
            edges = [0,1,2,3,4,5,9,10,14,15,19,20,21,22,23,24]
            centers  = [6,8,16,18, 7,11, 13, 17, 12]
            early_on_edge = [i for i, card in enumerate(cards) if card.early and i in edges]
            late_centers = [i for i, card in enumerate(cards) if not card.early and i in centers]
            rand.shuffle(early_on_edge)
            rand.shuffle(late_centers)
            while late_centers and early_on_edge:
                late = late_centers.pop()
                early = early_on_edge.pop()
                cards[late], cards[early] = cards[early], cards[late]
        if meta:
            # bullshit to put meta cards in places that aren't stupid for them
            metas_by_name = defaultdict(lambda: [])
            for index, card in enumerate(cards):
                if card.meta:
                    metas_by_name[card.name].append(index)
            # vertical symmetry must be in column C
            if "HorizSym" in metas_by_name and "VertSym" in metas_by_name:
                center_guy = random.choice(["HorizSym", "VertSym"])
                center_i = metas_by_name[center_guy][0]
                cards[center_i], cards[12] = cards[12], cards[center_i]
                del metas_by_name[center_guy]
            if "VertSym" in metas_by_name:
                col_c = list(range(2,23,5))
                v_sym = metas_by_name["VertSym"][0]
                if v_sym not in col_c:
                    i = rand.choice(col_c)
                    cards[v_sym], cards[i] = cards[i], cards[v_sym] 
            if "HorizSym" in metas_by_name:
                row_3 = list(range(10,15))
                hor_sym = metas_by_name["HorizSym"][0]
                if hor_sym not in row_3:
                    i = rand.choice(row_3)
                    cards[hor_sym], cards[i] = cards[i], cards[hor_sym]
            if "Activate Squares" in metas_by_name:
                non_metas = set([i for i, card in enumerate(cards) if not card.meta])
                subgoals_json = [BoolGoal(str(5*row+col), col_name+str(row+1)).to_card(rand).to_json([], True) # a subgoal that targets exactly 1 square
                                for row in range(5) for (col,col_name) in enumerate(["A","B","C","D","E"]) # cartesian product - all squares 
                                if 5*row+col in non_metas] # i wanted to just have the non_metas definition here but it'd recalc every time...

                rand.shuffle(subgoals_json)
                cards_to_update = metas_by_name["Activate Squares"]
                while cards_to_update:
                    c = cards[cards_to_update.pop()]
                    c.subgoals = [subgoals_json.pop() for _ in c.subgoals]


        for i, card in enumerate(cards):
            card.square = i
        return cards

