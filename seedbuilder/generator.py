import math
import random
import logging as log
import xml.etree.ElementTree as XML
from collections import OrderedDict, defaultdict, Counter
from operator import mul
from enums import KeyMode, PathDifficulty, ShareType, Variation, MultiplayerGameType
from pickups import Pickup
from util import spawn_defaults, choices
from hashlib import sha256
from seedbuilder.oriparse import get_areas, get_path_tags_from_pathsets
from seedbuilder.relics import relics
from functools import reduce

def stable_string_hash(s):
    """fuckin' INFURIATING that this is necessary but so it goes!!!"""
    return int(sha256(s.encode(encoding='UTF-8')).hexdigest(), 16)

longform_to_code = {"Health": ["HC"], "Energy": ["EC"], "Ability": ["AC"], "Keystone": ["KS"], "Mapstone": ["MS"], "Free": []}
key_to_shards = {"GinsoKey": ["WaterVeinShard"] * 5, "ForlornKey": ["GumonSealShard"] * 5, "HoruKey": ["SunstoneShard"] * 5}
keysanity_map = {
    "GladesPoolKeys": ["Glades Pool Keystone"] * 2, "LowerSpiritCavernsKeys": ["Lower Spirit Caverns Keystone"] * 2, "GrottoKeys": ["Grotto Keystone"] * 2, "SwampKeys": ["Swamp Keystone"] * 2,
    "UpperSpiritCavernsKeys": ["Upper Spirit Caverns Keystone"] * 4, "LowerGinsoKeys": ["Lower Ginso Keystone"] * 4, "UpperGinsoKeys": ["Upper Ginso Keystone"] * 4, "MistyKeys": ["Misty Keystone"] * 4,
    "ForlornKeys": ["Forlorn Keystone"] * 4, "LowerSorrowKeys": ["Lower Sorrow Keystone"] * 4, "MidSorrowKeys": ["Mid Sorrow Keystone"] * 4, "UpperSorrowKeys": ["Upper Sorrow Keystone"] * 4
}
warp_targets = [
    [
        # inner swamp
        ("Stomp Miniboss", 915, -115),
        ("Swamp Swim", 790, -195),
        ("Inner Swamp EC", 720, -95),
    ],
    [
        # gumo's hideout
        ("Above Grotto Crushers", 580, -345),
        ("Grotto Energy Vault", 513, -440),
        ("Gumo's Bridge", 480, -244),
    ],
    [
        # blackroot
        ("Lower Blackroot Laser AC", 417, -435),
        ("Dash Plant", 310, -230),
    ],
    [
        # blackrooter 
        ("Grenade Tree", 76, -370),
        ("Lost Grove Laser Lever", 499, -505),
    ],
    [
        # hollow grove
        ("Above Cflame Tree EX", -13, -96),
        ("Spidersack Energy Door", 70, -110),
        ("Death Gauntlet Roof", 328, -176),
        ("Spider Lake Roof Spikes", 194, -100),
    ],
    [
        # hollow grover
        ("Horu Fields Plant", 127, 20),
        ("Horu Fields AC", 170, -35),
        ("Kuro CS AC", 330, -63),
    ],
    [
        # outer swamp
        ("Outer Swamp HC", 585, -68),
        ("Outer Swamp AC", 505, -108),
        ("Spike loop HC", 546, -190),
    ],
    [
        # lower valley / below valley
        ("Valley entry (upper)", -224, -85),
        ("Forlorn entrance", -605, -255),
        ("Spirit Cavern AC", -219, -176),
    ],
    [
        # upper valley
        ("Wilhelm EX", -570, 156),
        ("Stompless AC", -358, 65),
    ],
    [
        # misty ?
        ("Misty First Keystone", -1050, 32),
    ],
    [
        # sorrow
        ("Sunstone Plant", -500, 587),
        ("Sorrow Mapstone", -432, 322),
        ("Tumbleweed Keystone Door", -595, 385),
    ],
    [
        # ginso
        ("Ginso Escape", 510, 910),
    ],
    [
        # horu
        ("Horu Escape Access", 69, 96),
    ],
    [
        # forlorn
        ("Forlorn HC", -610, -312),
    ]
]

# Grouped by subarea to limit 
# (warpName, x, y, area from TP name, logicLocation, logicCost).
warp_targets2 = [
    [
        # inner swamp
        #("Stomp Miniboss", 915, -115, "Swamp", None, None), Swapped out for the CJ pickup because it is less work.
        ("Stomp Tree Roof", 917, -70, "Swamp", "StompAreaRoofExpWarp", 41),
        ("Swamp Swim", 790, -195, "Swamp", "SwampWaterWarp", 41),
        ("Inner Swamp EC", 720, -95, "Swamp", "InnerSwampSkyArea", 41),
    ],
    [
        # gumo's hideout
        ("Above Grotto Crushers", 580, -345, "Grotto", "AboveGrottoCrushersWarp", 41),
        ("Grotto Energy Vault", 513, -440, "Grotto", "GrottoEnergyVaultWarp", 41),
        ("Water Vein", 506, -246, "Grotto", "WaterVeinArea", 41), 
    ],
    [
        # blackroot
        # ("Lower Blackroot Laser AC", 417, -435)
        ("Dash Plant", 310, -230, "Blackroot", "DashPlantAccess", 41),
        ("Right of Grenade Area", 258, -382, "Blackroot", "GrenadeAreaAccess", 41),
        ("Lost Grove Laser Lever", 499, -505, "Blackroot", "LostGroveLaserLeverWarp", 53),
    ],
    [
        # hollow grove
        ("Above Cflame Tree EX", -13, -96, "Grove", "AboveChargeFlameTreeExpWarp", 41),
        ("Spidersack Energy Door", 70, -110, "Grove", "SpiderSacEnergyDoorWarp", 41),
        ("Death Gauntlet Roof", 328, -176, "Grove", "DeathGauntletRoof", 41),
        #("Spider Lake Roof Spikes", 194, -100), # This is a bad idea.
        
    ],
    [
        # hollow grover
        # ("Horu Fields Plant", 127, 20), Replaced with below
        ("Horu Fields Push Block", 77, 11, "Grove", "HoruFieldsPushBlock", 41),
        #("Horu Fields AC", 170, -35)
        ("Kuro CS AC", 330, -63, "Grove", "HollowGroveTreeAbilityCellWarp", 41),
        ("Butter Cell Floor", 380, -143, "Grove", "GroveWaterStompAbilityCellWarp", 41),
    ],
    [
        # outer swamp
        ("Outer Swamp HC", 585, -68, "Swamp", "OuterSwampHealthCellWarp", 41), 
        ("Outer Swamp AC", 505, -108, "Swamp", "OuterSwampMortarAbilityCellLedge", 41),
        #("Spike loop HC", 546, -190, "Grotto"), # FIXME Just do the logic for this.
        ("Triforce AC", 646, -127, "Swamp", "SwampDrainlessArea", 41),
    ],
    [
        # lower valley / below valley
        ("Valley entry (upper)", -224, -85, "Valley", "ValleyEntryTree", 53),
        ("Forlorn entrance", -605, -255, "Valley" ,"OutsideForlorn", 53),
        ("Three Bird AC", -354, -98, "Valley", "VallleyThreeBirdACWarp", 53)
    ],
    [
        # upper valley
        ("Wilhelm EX", -570, 156, "Valley", "WilhelmExpWarp", 53),
        ("Stompless AC", -358, 65, "Valley", "ValleyRightFastStomplessCellWarp", 53),
        # misty ? // Combined because how many misty ones will we get anyway?
        #("Misty First Keystone", -1050, 32),
        ("Misty Entrance", -578, -25, "Misty", "MistyEntrance", 53)
    ],
    [
        # sorrow
        ("Sunstone Plant", -500, 587, "Sorrow", "SunstoneArea", 59),
        ("Sorrow Mapstone", -432, 322, "Sorrow", "SorrowMapstoneWarp", 59),
        ("Tumbleweed Keystone Door", -595, 385, "Sorrow", "LeftSorrowTumbleweedDoorWarp", 59),
    ],
    [
        # ginso - consider keystone door softlocks.
        ("Ginso Escape", 510, 910, "Ginso", "GinsoEscape", 61),
        ("Upper Ginso EC", 539, 434, "Ginso", "UpperGinsoEnergyCellWarp", 61),
        ("Lower Ginso Keystones", 520, 274, "Ginso", "GinsoMiniBossDoor", 61),
    ],
    [
        # horu
        ("Horu Escape Access", 69, 96, "Horu", "HoruBasement", 71),
        ("Horu R1 Mapstone", 155, 362, "Horu", "HoruR1MapstoneSecret", 71),
        ("Horu R4 Cutscene Rock", 254, 188, "Horu", "HoruR4CutsceneTrigger", 71),
    ],
    [
        # forlorn - consider keystone door softlocks.
        ("Forlorn HC", -610, -312, "Forlorn", "RightForlorn", 67),
        ("Forlorn Orb", -747, -407, "Forlorn", "ForlornOrbPossession", 67),
        ("Forlorn Plant", -820, -265, "Forlorn", "ForlornOrbPossession", 67),
    ],
    [
        # glades
        ("Spirit Cavern AC", -219, -176, "Glades", "SpiritCavernsACWarp", 41),
        ("Above Gladeser", -162, -175, "Glades", "GladesLaserArea", 41),
        ("Glades Loop Keystone", -241, -211, "Glades", "UpperLeftGlades", 41),
    ]
]

doors_inner = [
    ("GinsoInnerDoor", 522, 1),
    ("ForlornInnerDoor", -717, -408),
    ("HoruInnerDoor", 68, 169),
    ("L1InnerDoor", -24, 369),
    ("L2InnerDoor", -13, 301),
    ("L3InnerDoor", -28, 244),
    ("L4InnerDoor", -12, 188),
    ("R2InnerDoor", 163, 266),
    ("R3InnerDoor", 171, 218),
    ("R4InnerDoor", 144, 151)
]
doors_outer = [
    ("GinsoOuterDoor", 527, -43),
    ("ForlornOuterDoor", -668, -246),
    ("HoruOuterDoor", -78, 2),
    ("L1OuterDoor", 20, 371),
    ("L2OuterDoor", 13, 293),
    ("L3OuterDoor", 18, 248),
    ("L4OuterDoor", 14, 191),
    ("R2OuterDoor", 128, 288),
    ("R3OuterDoor", 126, 245),
    ("R4OuterDoor", 126, 196)
]

def ordhash(s):
    return reduce(mul, [ord(c) for c in s])

class Area:
    def __init__(self, name):
        self.name = name
        self.connections = []
        self.locations = []
        self.difficulty = 1
        self.has_location = False

    def add_connection(self, connection):
        self.connections.append(connection)

    def get_connections(self):
        return self.connections

    def remove_connection(self, connection):
        self.connections.remove(connection)

    def add_location(self, location):
        self.locations.append(location)
        self.has_location = True

    def get_locations(self):
        return self.locations

    def clear_locations(self):
        self.locations = []

    def remove_location(self, location):
        self.locations.remove(location)


class Connection:

    def __init__(self, home, target, sg):
        self.home = home
        self.target = target
        self.keys = 0
        self.mapstone = False
        self.requirements = []
        self.difficulties = []
        self.sg = sg

    def add_requirements(self, req, difficulty):
        def translate(req_part):
            """Helper function. Turns a req from areas.ori into
            the list of the things that req indicates are required"""
            if req_part in longform_to_code:
                return longform_to_code[req_part]
            if self.sg.params.key_mode == KeyMode.SHARDS and req_part in key_to_shards:
                return key_to_shards[req_part]
            if req_part in keysanity_map:
                return keysanity_map[req_part]
            if '=' not in req_part:
                return [req_part]
            item, _, count = req_part.partition("=")
            count = int(count)
            if item in longform_to_code:
                return count * longform_to_code[item]
            return count * [item]
        translated_req = []

        for part in req:
            translated_req += translate(part)

        self.requirements.append(translated_req)
        self.difficulties.append(difficulty)
        if not self.keys:
            self.keys = translated_req.count("KS")
        self.mapstone = "MS" in translated_req

    def get_requirements(self):
        return self.requirements

    def cost(self):
        minReqScore = 7777
        minDiff = 7777
        minReq = []
        for i in range(0, len(self.requirements)):
            score = 0
            items = {"EC": 0, "HC": 0, "AC": 0, "SunstoneShard": 0, "WaterVeinShard": 0, "GumonSealShard": 0}
            for req_part in self.requirements[i]:
                if req_part in items:
                    items[req_part] += 1
                    if self.sg.inventory[req_part] < items[req_part]:
                        score += self.sg.costs[req_part]
                elif req_part == "MS":
                    if self.sg.inventory["MS"] < self.sg.mapstonesSeen:
                        score += self.sg.costs["MS"]
                else:
                    score += self.sg.costs.get(req_part, 0)
            if score < minReqScore:
                minReqScore = score
                minReq = self.requirements[i]
                minDiff = self.difficulties[i]
        return (minReqScore, minReq, minDiff)


all_locations = {}
repeatable_locs = set()
forbidden_repeatable_locs = set([-7680144, -9120036, -10440008, -10759968, -1560272])

class Location:
    factor = 4.0

    def __init__(self, x, y, area, orig, difficulty, zone):
        self.x = int(math.floor((x) / self.factor) * self.factor)
        self.y = int(math.floor((y) / self.factor) * self.factor)
        self.orig = orig
        self.area = area
        self.difficulty = difficulty
        self.zone = zone
        key = self.get_key()
        if key not in all_locations:
            all_locations[key] = self
            if orig[0:2] in ["EX", "EC", "HC", "AC", "MS", "KS"]:
                if key not in forbidden_repeatable_locs:
                    repeatable_locs.add(key)

    def get_key(self):
        return self.x * 10000 + self.y

    def __str__(self): return self.to_string()

    def to_string(self):
        return self.area + " " + self.orig + " (" + str(self.x) + " " + str(self.y) + ")"


class Door:
    factor = 4.0

    def __init__(self, name, x, y):
        self.x = x
        self.y = y
        self.name = name

    def get_key(self):
        return int(math.floor(self.x / self.factor) * self.factor) * 10000 + int(
            math.floor(self.y / self.factor) * self.factor)


class SeedGenerator:
    seedDifficultyMap = OrderedDict({"Dash": 2, "Bash": 2, "Glide": 3, "DoubleJump": 2, "ChargeJump": 1})

    difficultyMap = OrderedDict({
        "casual": 1, "standard": 2, "expert": 3, "master": 4, "glitched": 5, "timed-level": 5, "insane": 7
    })

    def get_difficulty(self, path_tags):
        for difficulty in ["insane", "glitched", "timed-level", "master", "expert", "standard"]:
            for path_tag in path_tags:
                if path_tag.startswith(difficulty):
                    return self.difficultyMap[difficulty]
        return self.difficultyMap["casual"]

    def choice(self, things, weights):
        return self.choices(things, weights, 1)[0]

    def choices(self, things, weights, N):
        return self.choices_rec(list(things), list(weights), N)

    def choices_rec(self, things, weights, N):
        if len(things) != len(weights):
            return []
        if N >= len(things):
            return things
        if N == 0:
            return [] 
        stop = self.random.random() * sum(weights)
        curr = 0
        i = -1
        while curr < stop:
            i += 1
            curr += weights[i]
        weights.pop(i)
        choice = things.pop(i)
        return [choice] + self.choices_rec(things, weights, N-1)

    # in order: 10 skills, then WV, Water, GS, Wind, Sunstone    
    skillsOutput = OrderedDict({
        "WallJump": "SK3", "ChargeFlame": "SK2", "Dash": "SK50", "Stomp": "SK4", "DoubleJump": "SK5",
        "Glide": "SK14", "Bash": "SK0", "Climb": "SK12", "Grenade": "SK51", "ChargeJump": "SK8", "SpiritFlame": "SK15"
    })
    eventsOutput = OrderedDict({
        "GinsoKey": "EV0", "Water": "EV1", "ForlornKey": "EV2", "Wind": "EV3", "HoruKey": "EV4", "Warmth": "EV5",
        "WaterVeinShard": "RB17", "GumonSealShard": "RB19", "SunstoneShard": "RB21"
    })
    keysanityOutput = OrderedDict({
        "Glades Pool Keystone": "RB300",
        "Lower Spirit Caverns Keystone": "RB301",
        "Grotto Keystone": "RB302",
        "Swamp Keystone": "RB303",
        "Upper Spirit Caverns Keystone": "RB304",
        "Lower Ginso Keystone": "RB305",
        "Upper Ginso Keystone": "RB306",
        "Misty Keystone": "RB307",
        "Forlorn Keystone": "RB308",
        "Lower Sorrow Keystone": "RB309",
        "Mid Sorrow Keystone": "RB310",
        "Upper Sorrow Keystone": "RB311",
    })


    def toOutput(self, item, asMultiPart=False):
        if asMultiPart:
            raw = self.toOutput(item)
            return "%s/%s" % (raw[0:2], raw[2:])
        if item in self.skillsOutput:
            return self.skillsOutput[item]
        if item in self.eventsOutput:
            return self.eventsOutput[item]
        if item in self.keysanityOutput:
            return self.keysanityOutput[item]
        return item

    def var(self, v):
        return v in self.params.variations

    def init_fields(self):
        """Part one of a reset. All initialization that doesn't
        require reading from params goes here."""
        self.limitKeysPool = [-3160308, -560160, 2919744, 719620, 7839588, 5320328, 8599904, -4600020, -6959592, -11880100, 5480952, 4999752, -7320236, -7200024, -5599400]

        self.costs = OrderedDict({
            "Free": 0, "MS": 0, "KS": 2, "AC": 12, "EC": 6, "HC": 12, "WallJump": 13,
            "ChargeFlame": 13, "DoubleJump": 13, "Bash": 28, "Stomp": 13,
            "Glide": 13, "Climb": 13, "ChargeJump": 28, "Dash": 13,
            "Grenade": 13, "GinsoKey": 12, "ForlornKey": 12, "HoruKey": 12,
            "Water": 31, "Wind": 31, "WaterVeinShard": 5, "GumonSealShard": 5,
            "SunstoneShard": 5, "TPForlorn": 67, "TPGrotto": 41,
            "TPSorrow": 59, "TPGrove": 41, "TPSwamp": 41, "TPValley": 53,
            "TPGinso": 61, "TPHoru": 71, "Open": 0, "OpenWorld": 1, "Relic": 1,
            "TPGlades": 90, "TPBlackroot": 53, "Keysanity": 1,
            "Glades Pool Keystone": 0, "Lower Spirit Caverns Keystone": 0,
            "Grotto Keystone": 0, "Swamp Keystone": 0,
            "Upper Spirit Caverns Keystone": 0, "Lower Ginso Keystone": 0,
            "Upper Ginso Keystone": 0, "Misty Keystone": 0,
            "Forlorn Keystone": 0, "Lower Sorrow Keystone": 0,
            "Mid Sorrow Keystone": 0, "Upper Sorrow Keystone": 0,
        })
        self.inventory = OrderedDict([
            ("EX1", 0), ("EX*", 0), ("KS", 0), ("MS", 0), ("AC", 0), ("EC", 0),
            ("HC", 3), ("WallJump", 0), ("ChargeFlame", 0), ("Dash", 0),
            ("Stomp", 0), ("DoubleJump", 0), ("Glide", 0), ("Bash", 0),
            ("Climb", 0), ("Grenade", 0), ("ChargeJump", 0), ("GinsoKey", 0),
            ("ForlornKey", 0), ("HoruKey", 0), ("Water", 0), ("Wind", 0),
            ("Warmth", 0), ("RB0", 0), ("RB1", 0), ("RB6", 0), ("RB8", 0),
            ("RB9", 0), ("RB10", 0), ("RB11", 0), ("RB12", 0), ("RB13", 0),
            ("RB15", 0), ("WaterVeinShard", 0), ("GumonSealShard", 0),
            ("SunstoneShard", 0), ("TPForlorn", 0), ("TPGrotto", 0),
            ("TPSorrow", 0), ("TPGrove", 0), ("TPSwamp", 0), ("TPValley", 0),
            ("TPGinso", 0), ("TPHoru", 0), ("Open", 0), ("OpenWorld", 0), ("Relic", 0),
            ("TPGlades", 0), ("Keysanity", 0)
        ])

        self.mapstonesSeen = 1
        self.balanceLevel = 0
        self.balanceList = []
        self.balanceListLeftovers = []
        self.seedDifficulty = 0
        self.outputStr = ""
        self.eventList = []

        self.areas = OrderedDict()

        self.areasReached = OrderedDict([])
        self.currentAreas = []
        self.areasRemaining = []
        self.connectionQueue = []
        self.assignQueue = []
        self.sharedAssignQueue = []
        self.spoiler = []
        self.entrance_spoiler = ""
        self.warps = {}
        self.padding = 0
        self.starting_health = 3
        self.starting_energy = 1

    def reset(self, worried=False):
        """A full reset. Resets internal state completely (besides pRNG
        advancement), then sets initial values according to params."""
        self.init_fields()
        self.expRemaining = self.params.exp_pool
        self.forcedAssignments = self.preplaced.copy()
        self.forceAssignedLocs = set()
        self.itemPool = OrderedDict([
            ("EX1", 1), ("KS", 40), ("MS", 11), ("WallJump", 1), ("ChargeFlame", 1),
            ("Dash", 1), ("Stomp", 1), ("DoubleJump", 1), ("Glide", 1),
            ("Bash", 1), ("Climb", 1), ("Grenade", 1), ("ChargeJump", 1),
            ("GinsoKey", 1), ("ForlornKey", 1), ("HoruKey", 1), ("Water", 1),
            ("Wind", 1), ("Warmth", 1), ("WaterVeinShard", 0), ("EC", 0), ("HC", 0), ("AC", 0),
            ("GumonSealShard", 0), ("SunstoneShard", 0), ("Open", 0), ("OpenWorld", 0), ("Relic", 0)
        ])

        if self.params.keysanity:
            self.itemPool.update(OrderedDict([
                ("KS", 0),
                ("Glades Pool Keystone", 2), ("Lower Spirit Caverns Keystone", 2),
                ("Grotto Keystone", 2), ("Swamp Keystone", 2),
                ("Upper Spirit Caverns Keystone", 4), ("Lower Ginso Keystone", 4),
                ("Upper Ginso Keystone", 4), ("Misty Keystone", 4),
                ("Forlorn Keystone", 4), ("Lower Sorrow Keystone", 4),
                ("Mid Sorrow Keystone", 4), ("Upper Sorrow Keystone", 4)
            ]))
            self.inventory.update(OrderedDict([
                ("Keysanity", 1),
                ("Glades Pool Keystone", 0), ("Lower Spirit Caverns Keystone", 0),
                ("Grotto Keystone", 0), ("Swamp Keystone", 0),
                ("Upper Spirit Caverns Keystone", 0), ("Lower Ginso Keystone", 0),
                ("Upper Ginso Keystone", 0), ("Misty Keystone", 0),
                ("Forlorn Keystone", 0), ("Lower Sorrow Keystone", 0),
                ("Mid Sorrow Keystone", 0), ("Upper Sorrow Keystone", 0)
            ]))
            self.costs.update(OrderedDict([
                ("Keysanity", 0),
                ("Glades Pool Keystone", 2), ("Lower Spirit Caverns Keystone", 2),
                ("Grotto Keystone", 2), ("Swamp Keystone", 2),
                ("Upper Spirit Caverns Keystone", 4), ("Lower Ginso Keystone", 4),
                ("Upper Ginso Keystone", 4), ("Misty Keystone", 4),
                ("Forlorn Keystone", 4), ("Lower Sorrow Keystone", 4),
                ("Mid Sorrow Keystone", 4), ("Upper Sorrow Keystone", 4)
            ]))

        if not self.params.item_pool:
            self.itemPool.update(OrderedDict([
                ("RB0", 3), ("RB1", 3), ("RB6", 3), ("RB8", 0), ("RB9", 1), ("RB10", 1),
                ("RB11", 1), ("RB12", 1), ("RB13", 3), ("RB15", 3), ("TPForlorn", 1),
                ("TPGrotto", 1), ("TPSorrow", 1), ("TPGrove", 1), ("TPSwamp", 1),
                ("TPValley", 1), ("TPGinso", 1), ("TPHoru", 1),
            ]))
        else:
            for item, counts in sorted(list(self.params.item_pool.items()), key=lambda x: x[0]):
                item = item.replace("|", "")
                if item in ["HC1", "AC1", "EC1", "KS1", "MS1"]:
                    item = item[0:2]
                fixed_item = self.codeToName.get(item, item)
                count = self.random.randint(*counts) if len(counts) == 2 else counts[0]
                self.itemPool[fixed_item] = self.itemPool.get(fixed_item, 0) + count

        if self.var(Variation.DOUBLE_SKILL):
            self.itemPool["DoubleJump"] += 1
            self.itemPool["Bash"] += 1
            self.itemPool["Stomp"] += 1
            self.itemPool["Glide"] += 1
            self.itemPool["ChargeJump"] += 1
            self.itemPool["Dash"] += 1
            self.itemPool["Grenade"] += 1
            self.itemPool["Water"] += 1
            self.itemPool["Wind"] += 1
        if "BS*" in self.itemPool:
            drain_skills = ["RB102", "RB103", "RB109", "RB110"]
            for bonus_skill in self.random.sample(["RB101", "DrainSkill", "DrainSkill", "DrainSkill", "WarpSkill", "RB106", "RB107"], min(self.itemPool["BS*"], 7)):
                if bonus_skill == "DrainSkill":
                    if len(drain_skills) == 2 and self.random.random() < .5:  # third drain skill, if chosen, has a 50/50 chance to be wither or bash/stomp damage
                        bonus_skill = self.random.choice(["RB111", "RB113"])
                    else:
                        bonus_skill = self.random.choice(drain_skills)
                        if bonus_skill in ["RB110", "RB109"] and self.random.random() < .25:  # reroll timewarp and invincibility once 1/4 times
                            bonus_skill = self.random.choice(drain_skills)
                        drain_skills.remove(bonus_skill)
                if bonus_skill == "WarpSkill":
                    bonus_skill = self.random.choice(["RB104", "RB105"])
                self.itemPool[bonus_skill] = 1
            del self.itemPool["BS*"]

        if not self.var(Variation.STRICT_MAPSTONES):
            self.costs["MS"] = 11

        if self.var(Variation.OPEN_WORLD):
            self.inventory["OpenWorld"] = 1
            self.costs["OpenWorld"] = 0
            self.itemPool["KS"] -= 2

        if self.var(Variation.CLOSED_DUNGEONS):
            self.inventory["Open"] = 0
            self.costs["Open"] = 1
            self.itemPool["TPGinso"] = 0
            self.itemPool["TPHoru"] = 0

        # FIXME When we don't start in glades, add glades tp and remove other tp if applicable, before we process warps.
        # FIXME If Variation is closed dungeons, umm, check that we don't start in them, maybe? Can't start at the tp anyway.

        logic_paths = [lp.value for lp in self.params.logic_paths]
        logic_path_tags = get_path_tags_from_pathsets(logic_paths)
        difficulty = self.get_difficulty(logic_path_tags)

        if self.playerID == 1:
            self.start = "Glades"
            # FIXME On repeats after failed generation this will tend bias towards places that generate easier.
            start_weights = OrderedDict([
                ("Random", 0),
                ("Glades", 1.0),
                ("Grove", 2.0),
                ("Swamp", 2.0),
                ("Grotto", 2.0),
                ("Forlorn", 1.5),
                ("Valley", 2),
                ("Horu", 0.1),
                ("Ginso", 0.1),
                ("Sorrow", 0.25),
                ("Blackroot", 0.5)
            ])
            if len(self.params.spawn_weights) > 9:
                for i,k in enumerate(list(start_weights.keys())[1:]):
                    start_weights[k] = self.params.spawn_weights[i]
#                   print(k, start_weights[k])
            if not self.params.start or self.params.start not in start_weights:
                log.warning("Unknown start location. Switching to Glades")
                self.start = "Glades"
            elif self.params.start in ["Horu", "Ginso"] and self.var(Variation.CLOSED_DUNGEONS):
                log.error("can't start in dungeons with closed dungeons.")
                exit(1)
            elif self.params.start == "Random":
                if not self.var(Variation.OPEN_WORLD):
                    start_weights["Valley"] /= 10.0
                if self.var(Variation.CLOSED_DUNGEONS):
                    start_weights["Horu"] = 0
                    start_weights["Ginso"] = 0
                self.start = self.choice(start_weights.keys(), start_weights.values())
            else:
                self.start = self.params.start
        

            self.starting_skills = []


            possible_skills = ["WallJump", "ChargeFlame", "Dash", "Stomp", "DoubleJump", "Glide", "Bash", "Climb", "Grenade", "ChargeJump", "Water"]#, "Wind", "Warmth"]
            # possible_skills_forced = ["WallJump", "ChargeFlame", "Dash", "Stomp", "DoubleJump", "Glide", "Bash", "Climb", "Grenade", "ChargeJump", "Water", "Wind", "Warmth"]
            try_force = {
                "Glades": ["WallJump", "Bash", "Climb", "ChargeJump", "Water"],
                "Grove": ["ChargeFlame", "Stomp", "Grenade", "ChargeJump"],
                "Swamp": ["WallJump", "ChargeFlame", "Dash", "Bash", "Climb", "Grenade", "ChargeJump", "Water"],
                "Grotto": ["WallJump", "ChargeFlame", "Dash", "DoubleJump", "Glide", "Climb", "Grenade", "ChargeJump", "Water"],
                "Forlorn": ["ChargeFlame", "Bash", "Grenade", "ChargeJump"],
                "Valley": ["WallJump", "ChargeFlame", "DoubleJump", "Glide", "Bash", "Climb", "Grenade", "ChargeJump"],
                "Horu": ["WallJump", "Climb", "Bash"],
                "Ginso": ["Stomp", "DoubleJump", "Bash", "ChargeJump"],
                "Sorrow": ["ChargeJump", "Bash", "Glide", "Climb", "Stomp"],
                "Blackroot": ["WallJump", "ChargeFlame", "Dash", "Stomp", "DoubleJump", "Glide", "Bash", "Climb", "Grenade", "ChargeJump", "Water"],
            }
            start_skills = 0
            # FIXME Check if starved exists, then just set the defaults to 3/1?
            if self.params.start == "Random":
                self.starting_health, self.starting_energy, start_skills = spawn_defaults[self.start][difficulty]
            elif self.start != "Glades":
                    self.starting_health = max(self.params.starting_health, self.starting_health)
                    self.starting_energy = max(self.params.starting_energy, self.starting_energy)
                    start_skills = int(self.params.starting_skills)
            if start_skills > 0:
                if start_skills > 1:
                    possible_skills.append("Wind")
                    possible_skills.append("Warmth")
                # Weigh skills. FIXME: it would be good to have weights
                weights = []
                for skill in possible_skills:
                    if skill == "Warmth":
                        cost = 75
                    else:
                        cost = self.costs[skill]
                    if skill in ["Wind", "Water"]:
                        cost *= 1.5
                    if skill in ["WallJump", "Climb"] and self.var(Variation.FUCK_WALLS): 
                        cost *= 5
                    if skill == "Grenade" and self.var(Variation.FUCK_GRENADE):
                        cost *= 5
                    if worried and self.start in try_force and skill in try_force[self.start]: 
                        # if we're worried, overweight useful skills
                        cost = 1
                    weight = 1.0 / cost
                    weights.append(weight)
                
                if start_skills > 0:
                    self.starting_skills = self.choices(possible_skills, weights, start_skills)
            
            self.spawn_things = []
            #print(self.starting_skills, self.starting_health, self.starting_energy)
            if self.starting_health > 3:
                for _ in range(self.starting_health - 3):
                    self.spawn_things.append("HC/1")
            energy_cells = self.starting_energy
            if self.start == "Glades":
                # FIXME this will change if we randomise the first EC.
                energy_cells -= 1
                self.inventory["EC"] = 1
            for _ in range(energy_cells):
                self.spawn_things.append("EC/1")
            if (self.start == "Ginso"):
                for _ in range(4):
                    self.spawn_things.append("KS/1")
                if (not self.var(Variation.KEYS_ONLY_FOR_DOORS)) and (self.params.key_mode != KeyMode.FREE):
                    if self.params.key_mode == KeyMode.SHARDS:
                        for _ in range(5):
                            self.spawn_things.append("RB/17")
                    else:
                        self.spawn_things.append("EV/0")
            if (self.start == "Forlorn"):
                if (not self.var(Variation.KEYS_ONLY_FOR_DOORS)) and (self.params.key_mode != KeyMode.FREE):
                    if self.params.key_mode == KeyMode.SHARDS:
                        for _ in range(5):
                            self.spawn_things.append("RB/19")
                    else:
                        self.spawn_things.append("EV/2")
                self.spawn_things.append("NB/-914,-298")
            if (self.start == "Horu"):
                if (not self.var(Variation.KEYS_ONLY_FOR_DOORS)) and (self.params.key_mode != KeyMode.FREE):
                    if self.params.key_mode == KeyMode.SHARDS:
                        for _ in range(5):
                            self.spawn_things.append("RB/21")
                    else:
                        self.spawn_things.append("EV/4")
            if (self.start != "Glades"):
                self.spawn_things.append(self.toOutput("SpiritFlame", True))
            for skill in self.starting_skills:
                self.spawn_things.append(self.toOutput(skill, True))
            if self.params.key_mode == KeyMode.FREE:
                self.spawn_things.append("EV/0/EV/2/EV/4")
            
            spawn_spots = {
                "Grove": (-159, -114),
                "Swamp": (491, -73),
                "Grotto": (519, -174), 
                "Forlorn": (-914, -298),
                "Valley": (-430, 0), 
                "Horu": (88, 142),  
                "Ginso": (570, 539),
                "Sorrow": (-594, 496), 
                "Blackroot": (381, -297), 
            }
            self.spawn_logic_areas = {
                "Glades": "SunkenGladesRunaway",
                "Grove": "SpiritTreeRefined", 
                "Swamp": "SwampTeleporter", 
                "Grotto": "MoonGrotto", 
                "Forlorn": "ForlornTeleporter", 
                "Valley": "ValleyTeleporter", 
                "Horu": "HoruTeleporter", 
                "Ginso": "GinsoTeleporter", 
                "Sorrow": "SorrowTeleporter", 
                "Blackroot": "BlackrootGrottoConnection", 
            }

        if self.start != "Glades":
            self.itemPool["TPGlades"] = 1
            if self.playerID == 1:
                self.spawn_things.append("TP/" + self.start)
                # The Warp Save should be last in the line because of the *save*
                self.spawn_things.append("WS/" + str(spawn_spots[self.start][0]) + "," + str(spawn_spots[self.start][1]) + ",force")
        
        if len(self.spawn_things) > 0:
            if 2 in self.forcedAssignments:
                current_assignment = self.forcedAssignments[2]
                if current_assignment[0:2] not in ["MU", "RP"]:
                    self.forcedAssignments[2] = "MU" + self.toOutput(current_assignment, True)
                self.forcedAssignments[2] += "/" + "/".join(self.spawn_things) 
            else:
                self.forcedAssignments[2] = "MU" + "/".join(self.spawn_things)


        # FIXME Are we giving the correct number of ECs for non-glades starts?
        # FIXME Test altering preplaced things at spawn, but can't add things at spawn currently anyway.

        # Make it so we only give up to 1 warp in each subarea.
        self.unused_warps = []
        for warp_group in warp_targets2:
            self.unused_warps.append(self.random.choice(warp_group))
            
        # Warps. format (warpName, x, y, area from TP name, logicLocation, logicCost).
        if self.var(Variation.WARPS_INSTEAD_OF_TPS):
            tps = []
            for item in self.itemPool:
                if item.startswith("TP"):
                    tps.append(item)
            # Calculate number of warps to add.
            possible_warps_to_add = self.params.warps_instead_of_tps
            if len(tps) < possible_warps_to_add:
                possible_warps_to_add = len(tps)
            if self.var(Variation.WARP_COUNT):
                if self.params.warp_count > possible_warps_to_add:
                    possible_warps_to_add = self.params.warp_count
            for tp in self.random.sample(tps, possible_warps_to_add):
                #log.debug("Removing tp: " + tp)
                tp_name = tp[2:]
                warps_in_area = []
                for warp in self.unused_warps:
                    if warp[3] == tp_name:
                        warps_in_area.append(warp)
                if len(warps_in_area) > 0:
                    warp = self.random.choice(warps_in_area)
                    self.itemPool[tp] -= 1
                    self.add_warp(warp)

        # So we've currently added len(self.warps) warps.
        if self.var(Variation.WARP_COUNT):
            remaining_warps = self.params.warp_count - len(self.warps)
            if remaining_warps > 0:
                self.itemPool["WP*"] = remaining_warps
            else:
                if "WP*" in self.itemPool:
                    del self.itemPool["WP*"]
        if self.itemPool.get("WP*", 0) > 0:
            for warp in self.random.sample(self.unused_warps, min(len(self.unused_warps), self.itemPool.get("WP*", 0))):
                #log.debug("Adding warp.")
                self.add_warp(warp)
            self.itemPool.pop("WP*")

        if self.var(Variation.NO_TPS):
            for item in self.itemPool:
                if item.startswith("TP"):
                    self.itemPool[item] = 0

        if self.params.key_mode == KeyMode.SHARDS:
            shard_count = 5
            if self.params.sync.mode == MultiplayerGameType.SPLITSHARDS:
                shard_count = 2 + 3 * self.params.players
            for shard in ["WaterVeinShard", "GumonSealShard", "SunstoneShard"]:
                self.itemPool[shard] = shard_count
                self.costs[shard] = shard_count
            for key in ["GinsoKey", "HoruKey", "ForlornKey"]:
                self.itemPool[key] = 0

        if self.var(Variation.WARMTH_FRAGMENTS):
            self.costs["RB28"] = 3 * self.params.frag_count
            self.inventory["RB28"] = 0
            self.itemPool["RB28"] = self.params.frag_count
            self.itemPool["Warmth"] = 0

        if self.params.key_mode == KeyMode.LIMITKEYS:
            dungeonLocs = {"GinsoKey": {5480952, 5320328}, "ForlornKey": {-7320236}, "HoruKey": set()}
            names = {-3160308: "SKWallJump", -560160: "SKChargeFlame", 2919744: "SKDash", 719620: "SKGrenade", 7839588: "SKDoubleJump", 5320328: "SKBash", 8599904: "SKStomp", -4600020: "SKGlide",
                    -6959592: "SKChargeJump", -11880100: "SKClimb", 5480952: "EVWater", 4999752: "EVGinsoKey", -7320236: "EVWind", -7200024: "EVForlornKey", -5599400: "EVHoruKey"}
            for key in self.random.sample(list(dungeonLocs.keys()), 3):
                loc = self.random.choice([l for l in self.limitKeysPool if l not in dungeonLocs[key]])
                self.limitKeysPool.remove(loc)
                for key_to_update in ["GinsoKey", "ForlornKey"]:
                    if loc in dungeonLocs[key_to_update]:
                        dungeonLocs[key_to_update] |= dungeonLocs[key]
                self.forcedAssignments[loc] = key

        # paired setup for subsequent players
        self.unplaced_shared = 0
        if self.playerID > 1:
            for item in self.sharedList:
                self.itemPool[item] = 0
            self.unplaced_shared = self.sharedCounts[self.playerID]

    def __init__(self):
        self.init_fields()
        self.codeToName = OrderedDict([(v, k) for k, v in list(self.skillsOutput.items()) + list(self.eventsOutput.items()) + list(self.keysanityOutput.items()) + [("RB17", "WaterVeinShard"), ("RB19", "GumonSealShard"), ("RB21", "SunstoneShard")]])

    def add_warp(self, warp):
        name, x, y, area, logic_location, logic_cost = warp
        self.unused_warps.remove(warp)
        warp_id = "Warp" + str(len(self.warps))
        self.warps[warp_id] = warp
        self.itemPool[warp_id] = 1
        self.costs[warp_id] = logic_cost
        if self.do_multi and ShareType.TELEPORTER in self.params.sync.shared:
            self.sharedList += [warp_id]
        self.inventory[warp_id] = 0
        #if self.var(Variation.IN_LOGIC_WARPS):
            #connection = Connection("TeleporterNetwork", logic_location, self)
            #connection.add_requirements([warp_id], 0)
            #self.areas["TeleporterNetwork"].add_connection(connection)
            #log.debug("Added connect to {}".format(logic_location))

    def create_warp_paths(self):
        if self.var(Variation.IN_LOGIC_WARPS):
            for warp_id in self.warps:
                name, x, y, area, logic_location, logic_cost = self.warps[warp_id]
                connection = Connection("TeleporterNetwork", logic_location, self)
                requirements = [warp_id]
                if not self.var(Variation.KEYS_ONLY_FOR_DOORS):
                    # Consider keystone softlocks.
                    #if area == "Ginso":
                    #    requirements.append("GinsoKey")
                    if area == "Horu":
                        requirements.append("HoruKey")
                    #if area == "Forlorn":
                    #    requirements.append("ForlornKey")
                connection.add_requirements(requirements, 0)
                self.areas["TeleporterNetwork"].add_connection(connection)
                #log.debug("Added connect to {}".format(logic_location))

    def shared_item_split(self, target):
        for item, player in self.sharedMap.get(target, []):
            if player == self.playerID:
                self.assignQueue.append(item)
                self.unplaced_shared -= 1

            # If the item is intended for player with higher ID, we can just assign the item.
            # Otherwise, we want to assign it after the paths are generated for this round
            elif player > self.playerID:
                self.assign(item)
                self.append_spoiler(self.adjust_item(item, None), "Player %s" % player)
            else:
                self.sharedAssignQueue.append(item)
                self.append_spoiler(self.adjust_item(item, None), "Player %s" % player)

    def reach_area(self, target):
        if self.playerID > 1 and target in self.sharedMap:
            self.shared_item_split(target)
        if self.areas[target].has_location:
            self.currentAreas.append(target)
        self.areasReached[target] = True

    def open_free_connections(self):
        found = False
        keystoneCount = 0
        mapstoneCount = 0
        # python 3 wont allow concurrent changes
        # list(areasReached.keys()) is a copy of the original list
        for area in list(self.areasReached.keys()):
            for connection in self.areas[area].get_connections():
                cost = connection.cost()
                reached = connection.target in self.areasReached
                if cost[0] <= 0:
                    if not reached:
                        self.areas[connection.target].difficulty = cost[2]
                        if len(self.areas[connection.target].locations) > 0:
                            self.areas[connection.target].difficulty += self.areas[area].difficulty
                    if connection.keys > 0:
                        if area not in self.doorQueue.keys():                            
                            self.doorQueue[area] = connection
                            keystoneCount += connection.keys
                    elif connection.mapstone and self.var(Variation.STRICT_MAPSTONES):
                        if not reached:
                            visitMap = True
                            for mp in self.mapQueue.keys():
                                if mp == area or self.mapQueue[mp].target == connection.target:
                                    visitMap = False
                            if visitMap:
                                self.mapQueue[area] = connection
                                mapstoneCount += 1
                    else:
                        if not reached:
                            self.seedDifficulty += cost[2] * cost[2]
                            self.reach_area(connection.target)
                            if connection.mapstone and not self.var(Variation.STRICT_MAPSTONES):
                                self.mapstonesSeen += 1
                                if self.mapstonesSeen >= 9:
                                    self.mapstonesSeen = 11
                                if self.mapstonesSeen == 8:
                                    self.mapstonesSeen = 9
                        if connection.target in self.areasRemaining:
                            self.areasRemaining.remove(connection.target)
                        self.connectionQueue.append((area, connection))
                        found = True
        return (found, keystoneCount, mapstoneCount)

    def choose_relic_for_zone(self, zone):
        self.random.shuffle(relics[zone])
        return relics[zone][0]

    def get_all_accessible_locations(self):
        locations = []
        forced_placement = False
        for area in self.areasReached.keys():
            currentLocations = self.areas[area].get_locations()
            for location in currentLocations:
                location.difficulty += self.areas[area].difficulty
            if self.forcedAssignments:
                reachable_forced_ass_locs = [l for l in currentLocations if l.get_key() in self.forcedAssignments]
                for loc in reachable_forced_ass_locs:
                    currentLocations.remove(loc)
                    key = loc.get_key()
                    if key in self.forceAssignedLocs:
                        continue
                    self.forceAssignedLocs.add(key)
                    self.force_assign(self.forcedAssignments[key], loc)
                    forced_placement = True
            locations.extend(currentLocations)
            self.areas[area].clear_locations()
        if self.reservedLocations:
            locations.append(self.reservedLocations.pop(0))
            locations.append(self.reservedLocations.pop(0))
        if self.locations() > 2 and len(locations) >= 2:
            self.reservedLocations.append(locations.pop(self.random.randrange(len(locations))))
            self.reservedLocations.append(locations.pop(self.random.randrange(len(locations))))
        return locations, forced_placement

    def prepare_path(self, free_space):
        abilities_to_open = OrderedDict()
        totalCost = 0.0
        free_space += len(self.balanceList)
        # find the sets of abilities we need to get somewhere
        for area in self.areasReached.keys():
            for connection in self.areas[area].get_connections():
                if connection.target in self.areasReached:
                    continue
                req_sets = connection.get_requirements()
                for req_set in req_sets:
                    requirements = []
                    cost = 0
                    cnts = defaultdict(lambda: 0)
                    for req in req_set:
                        if not req:
                            log.warning(req, req_set, str(connection), connection.target)
                            continue
                        if self.costs[req] > 0:
                            # if the item isn't in your itemPool (due to co-op or an unprocessed forced assignment), skip it
                            if self.itemPool.get(req, 0) == 0:
                                requirements = []
                                continue
                            if req in ["HC", "EC", "WaterVeinShard", "GumonSealShard", "SunstoneShard",
                                "Glades Pool Keystone", "Lower Spirit Caverns Keystone",
                                "Grotto Keystone", "Swamp Keystone",
                                "Upper Spirit Caverns Keystone", "Lower Ginso Keystone",
                                "Upper Ginso Keystone", "Misty Keystone",
                                "Forlorn Keystone", "Lower Sorrow Keystone",
                                "Mid Sorrow Keystone", "Upper Sorrow Keystone"]:
                                cnts[req] += 1
                                if cnts[req] > self.inventory[req]:
                                    requirements.append(req)
                                    cost += self.costs[req]
                            else:
                                requirements.append(req)
                                cost += self.costs[req]
                                if self.var(Variation.TPSTARVED) and (req.startswith("TP") or req.startswith("Warp")):
                                    cost += self.costs[req]
                                if self.var(Variation.FUCK_GRENADE) and req == "Grenade":
                                    cost += self.costs[req] * 5
                                if self.var(Variation.FUCK_WALLS) and req in ["WallJump", "Climb"]:
                                    cost += self.costs[req] * 7
                    # don't decrease the rate of multi-ability paths, bc we're already pruning them
                    # cost *= max(1, len(requirements) - 1)
                    if len(requirements) <= free_space:
                        for req in requirements:
                            if req not in abilities_to_open:
                                abilities_to_open[req] = (cost, requirements)
                            elif abilities_to_open[req][0] > cost:
                                abilities_to_open[req] = (cost, requirements)
        # pick a random path weighted by cost
        for path in abilities_to_open:
            totalCost += 1.0 / abilities_to_open[path][0]
        position = 0
        target = self.random.random() * totalCost
        path_selected = None
        for path in abilities_to_open:
            position += 1.0 / abilities_to_open[path][0]
            if target <= position:
                path_selected = abilities_to_open[path]
                break
        # if a connection will open with a subset of skills in the selected path, use that instead
        subsetCheck = list(abilities_to_open.keys())
        self.random.shuffle(subsetCheck)
        for path in subsetCheck:
            isSubset = abilities_to_open[path][0] < path_selected[0]
            if isSubset:
                for req in abilities_to_open[path][1]:
                    if req not in path_selected[1]:
                        isSubset = False
                        break
                if isSubset:
                    path_selected = abilities_to_open[path]
        if path_selected:
            for req in path_selected[1]:
                if self.itemPool.get(req, 0) > 0:
                    self.assignQueue.append(req)
            return path_selected[1]
        return None

    def get_location_from_balance_list(self):
        target = int(pow(self.random.random(), 1.0 / self.balanceLevel) * len(self.balanceList))
        location = self.balanceList.pop(target)
        self.balanceListLeftovers.append(location[0])
        return location[1]

    def cloned_item(self, item, player):
        name = self.codeToName.get(item, item)  # TODO: get upgrade names lol
        item = self.toOutput(item)
        if not self.params.sync.hints:
            return "EV5"
        hint_text = {"SK": "Skill", "TP": "Teleporter", "RB": "Upgrade", "EV": "World Event"}.get(item[:2], "?Unknown?")
        if item in ["RB17", "RB19", "RB21"]:
            name = "a " + name  # grammar
            hint_text = "Shard"
        elif item == "RB28":
            name = "a Warmth Fragment"
            hint_text = "Warmth Fragment"
        elif item == "Relic":
            name = "a Relic"
            hint_text = "Relic"

        owner = ("Team " if self.params.sync.teams else "Player ") + str(player)
        msg = "HN%s-%s-%s" % (name, hint_text, owner)
        return msg

    def assign_random(self, locs, recurseCount=0):
        value = self.random.random()
        position = 0.0
        denom = float(sum(self.itemPool.values()))
        if denom == 0.0:
            log.warning("%s: itemPool was empty! locations: %s, balanced items: %s", self.params.flag_line(), self.locations(), self.items() - self.items(False))
            return self.assign("EX*")
        for key in self.itemPool.keys():
            position += self.itemPool[key] / denom
            if value <= position:
                if self.var(Variation.STARVED):
                    if key in self.skillsOutput and recurseCount < 3:
                        return self.assign_random(locs, recurseCount=recurseCount + 1)
                if self.var(Variation.FUCK_WALLS):
                    if key in ["WallJump", "Climb"] and recurseCount < 3 and 252 - locs < 40:
                        return self.assign_random(locs, recurseCount=recurseCount + 1)
                if self.var(Variation.FUCK_GRENADE):
                    if key == "Grenade" and recurseCount < 3 and 252 - locs < 60:
                        return self.assign_random(locs, recurseCount=recurseCount + 1)
                if self.var(Variation.TPSTARVED):
                    if key.startswith("TP") and recurseCount < 3 and 252 - locs < self.costs.get(key, 0):
                        return self.assign_random(locs, recurseCount=recurseCount + 1)
                return self.assign(key)

    def assign(self, item, preplaced=False):
        if item[0:2] in ["MU", "RP"] and item not in self.itemPool:
            for multi_item in self.get_multi_items(item):
                self.assign(multi_item, preplaced)
        else:
            if not preplaced:
                self.itemPool[item] = max(self.itemPool.get(item, 0) - 1, 0)
            if item in ["KS", "EC", "HC", "AC", "WaterVeinShard", "GumonSealShard", "SunstoneShard", 
                "RB300", "RB301", "RB302", "RB303",
                "RB304", "RB305", "RB306", "RB307"
                "RB308", "RB309", "RB310", "RB311"]:
                if self.costs[item] > 0:
                    self.costs[item] -= 1
            elif item == "RB28":
                if self.costs[item] > 0:
                    self.costs[item] -= min(3, self.costs[item])
            elif item in self.costs and self.itemPool.get(item, 0) == 0:
                self.costs[item] = 0
            self.inventory[item] = 1 + self.inventory.get(item, 0)
        return item

    # for use in limitkeys mode
    def force_assign(self, item, location):
        self.assign(item, True)
        self.assign_to_location(item, location)

    # for use in world tour mode
    # TODO: replace this with generalized preplacement
    def relic_assign(self, location):
        self.force_assign("Relic", location)
        self.areas[location.area].remove_location(location)

    def assign_to_location(self, item, location):
        zone = location.zone
        hist_written = False
        at_mapstone = not self.var(Variation.DISCRETE_MAPSTONES) and location.orig == "MapStone"
        has_cost = item in self.costs.keys()

        loc = location.get_key()

        if at_mapstone:
            self.mapstonesAssigned += 1
            loc = 20 + self.mapstonesAssigned * 4
            zone = "Mapstone"

        # if this is the first player of a paired seed, construct the map
        if self.playerCount > 1 and self.playerID == 1 and item in self.sharedList:
            player = self.random.randint(1, self.playerCount)
            if self.params.sync.cloned:
                # handle cloned seed placement
                adjusted_item = self.adjust_item(item, zone)
                self.split_locs[loc] = (player, adjusted_item)
                self.spoilerGroup[item].append("%s from Player %s at %s\n" % (item, player, location.to_string()))
                hist_written = True
                if player != self.playerID:
                    item = self.cloned_item(item, player=player)
            else:
                if location.area not in self.sharedMap:
                    self.sharedMap[location.area] = []
                self.sharedMap[location.area].append((item, player))
                if player != self.playerID:
                    self.sharedCounts[player] += 1
                    self.append_spoiler(self.adjust_item(item, zone), "Player %s" % player)
                    item = "EX*"
                    self.expSlots += 1
        # if mapstones are progressive, set a special location


        fixed_item = self.adjust_item(item, zone)
        if (has_cost or self.params.verbose_spoiler) and not hist_written:
            self.append_spoiler(fixed_item, "Mapstone %s" % self.mapstonesAssigned if at_mapstone else location.to_string())
        assignment = self.get_assignment(loc, fixed_item, zone)

        if item in self.eventsOutput:
            self.eventList.append(assignment)
        elif self.params.balanced and not has_cost and location.orig != "MapStone" and loc not in self.forceAssignedLocs:
            self.balanceList.append((fixed_item, location, assignment))
        else:
            self.outputStr += assignment

        if self.params.do_loc_analysis:
            key = location.to_string()
            if location.orig == "MapStone":
                key = "MapStone " + str(self.mapstonesAssigned)
            if item in self.params.locationAnalysisCopy[key]:
                self.params.locationAnalysisCopy[key][item] += 1
                self.params.locationAnalysisCopy[location.zone][item] += 1

    def append_spoiler(self, fixed_item, location_name):
        pname = "Warp to " + self.warps[fixed_item][0] if fixed_item in self.warps else Pickup.name(fixed_item[:2], fixed_item[2:] or "1")
        self.padding = max(self.padding, len(pname))
        self.spoilerGroup[fixed_item].append(pname + "!PDPLC!-from " + location_name + "\n")


    def adjust_item(self, item, zone):
        if item in self.skillsOutput:
            item = self.skillsOutput[item]
        elif item in self.eventsOutput:
            item = self.eventsOutput[item]
        elif item in self.keysanityOutput:
            item = self.keysanityOutput[item]
        elif item == "Relic":
            relic = self.choose_relic_for_zone(zone)
            item = "WT#" + relic[0] + "#\\n" + relic[1]
        elif item == "EX*":
            value = self.get_random_exp_value()
            self.expRemaining -= value
            self.expSlots -= 1
            item = "EX%s" % value
        return item

    def get_assignment(self, loc, item, zone):
        pickup = ""
        if item.startswith("Warp"):
            name, x, y, area, logic_location, logic_cost = self.warps[item]
            pickup = "TW|Warp to " + name + "," + str(x) + ',' + str(y) + ',' + logic_location
        elif item[2:]:
            pickup = "%s|%s" % (item[:2], item[2:])
        else:
            pickup = "%s|1" % item[:2]
        return "%s|%s|%s\n" % (loc, pickup, zone)

    def get_random_exp_value(self):
        minExp = self.random.randint(2, 9)
        if self.expSlots <= 1:
            return max(self.expRemaining, minExp)
        return int(max(self.expRemaining * (self.inventory["EX*"] + self.expSlots / 4) * self.random.uniform(0.0, 2.0) / (self.expSlots * (self.expSlots + self.inventory["EX*"])), minExp))

    def preferred_difficulty_assign(self, item, locationsToAssign):
        total = 0.0
        for loc in locationsToAssign:
            if self.params.path_diff == PathDifficulty.EASY:
                total += (20 - loc.difficulty) * (20 - loc.difficulty)
            else:
                total += (loc.difficulty * loc.difficulty)
        value = self.random.random()
        position = 0.0
        for i in range(0, len(locationsToAssign)):
            if self.params.path_diff == PathDifficulty.EASY:
                position += (20 - locationsToAssign[i].difficulty) * (20 - locationsToAssign[i].difficulty) / total
            else:
                position += locationsToAssign[i].difficulty * locationsToAssign[i].difficulty / total
            if value <= position:
                self.assign_to_location(item, locationsToAssign[i])
                break
        del locationsToAssign[i]

    def form_areas(self, keysOnlyForDoors=False):
        if self.params.do_loc_analysis:
            self.params.locationAnalysis["FinalEscape EVWarmth (-240 512)"] = self.params.itemsToAnalyze.copy()
            self.params.locationAnalysis["FinalEscape EVWarmth (-240 512)"]["Zone"] = "Horu"

        # sorry for this - only intended to last as long as 3.0 beta lasts
        meta = get_areas(self.params.areas_ori_path)
        logic_paths = [lp.value for lp in self.params.logic_paths]
        logic_path_tags = get_path_tags_from_pathsets(logic_paths)
        for loc_name, loc_info in meta["locs"].items():
            area = Area(loc_name)
            self.areasRemaining.append(loc_name)
            self.areas[loc_name] = area

            loc = Location(
                int(loc_info["x"]),
                int(loc_info["y"]),
                loc_name,
                loc_info["item"],
                int(loc_info["difficulty"]),
                loc_info["zone"]
            )
            area.add_location(loc)

            if self.params.do_loc_analysis:
                key = loc.to_string()
                if key not in self.params.locationAnalysis:
                    self.params.locationAnalysis[key] = self.params.itemsToAnalyze.copy()
                    self.params.locationAnalysis[key]["Zone"] = loc.zone
                zoneKey = loc.zone
                if zoneKey not in self.params.locationAnalysis:
                    self.params.locationAnalysis[zoneKey] = self.params.itemsToAnalyze.copy()
                    self.params.locationAnalysis[zoneKey]["Zone"] = loc.zone

        for home_name, home_info in meta["homes"].items():
            area = Area(home_name)
            self.areasRemaining.append(home_name)
            self.areas[home_name] = area

            for conn_target_name, conn_info in home_info["conns"].items():
                connection = Connection(home_name, conn_target_name, self)

                # can't actually be used yet but this is roughly how this will be implemented
                # entranceConnection = True if "entrance" in conn_info else False
                # if self.var(Variation.ENTRANCE_SHUFFLE) and entranceConnection:
                #   continue

                if not conn_info["paths"]:
                    connection.add_requirements(["Free"], 1)
                for path in conn_info["paths"]:
                    valid = True
                    path_tags = path[0]
                    for path_tag in path_tags:
                        if path_tag not in logic_path_tags:
                            valid = False
                            break
                    if valid:
                        if keysOnlyForDoors:
                            # Okay, this is essentially Free keymode but with requirements
                            # for the keys to be placed in their doors, but aren't given freely.
                            altered_path = list(path)
                            if "GinsoKey" in path:
                                if (conn_target_name != "GinsoOuterDoor") or ("InnerDoor" in home_name):
                                    altered_path.remove("GinsoKey")
                            if "ForlornKey" in path:
                                if conn_target_name != "ForlornOuterDoor" or ("InnerDoor" in home_name):
                                    altered_path.remove("ForlornKey")
                            if "HoruKey" in path:
                                if conn_target_name != "HoruOuterDoor" or ("InnerDoor" in home_name):
                                    altered_path.remove("HoruKey")
                            connection.add_requirements(list(altered_path[1:]), self.get_difficulty(path_tags))
                        else:
                            connection.add_requirements(list(path[1:]), self.get_difficulty(path_tags))

                if connection.get_requirements():
                    area.add_connection(connection)

                if self.params.keysanity:
                    connection.keys = 0

    def connect_doors(self, door1, door2, requirements=["Free"]):
        connection1 = Connection(door1.name, door2.name, self)
        connection1.add_requirements(requirements, 1)
        self.areas[door1.name].add_connection(connection1)
        connection2 = Connection(door2.name, door1.name, self)
        connection2.add_requirements(requirements, 1)
        self.areas[door2.name].add_connection(connection2)
        dat_string = str(door1.get_key()) + "|EN|" + str(door2.x) + "|" + str(door2.y) + "\n" + str(door2.get_key()) + "|EN|" + str(door1.x) + "|" + str(door1.y) + "\n"
        spoiler_string = str("    {} <-> {}\n".format(door1.name, door2.name))
        return dat_string, spoiler_string

    def randomize_entrances(self):
        doors = doors_inner + doors_outer

        # Remove all previous connections
        for door_name, x, y in doors:
            area = self.areas[door_name]
            connections = area.get_connections()[:]
            for connection in connections:
                if ("OuterDoor" in connection.target) or ("InnerDoor" in connection.target):
                    area.remove_connection(connection)
                    #log.debug("Removed connection to {} from area {}".format(connection.target, door_name))
        
        # Okay, according to old XML, door groups are...
        outerDoors = [[], [], [], [], [], [], [], [], [], [], [], [], []]
        innerDoors = [[], [], [], [], [], [], [], [], [], [], [], [], []]
        innerDoors[1] = [Door("HoruInnerDoor", 68, 169)]
        innerDoors[3] = [Door("L1InnerDoor", -24, 369)]
        innerDoors[4] = [Door("L2InnerDoor", -13, 301)]
        innerDoors[5] = [Door("L3InnerDoor", -28, 244)]
        innerDoors[6] = [Door("L4InnerDoor", -12, 188)]
        innerDoors[7] = [Door("R1InnerDoor", 153, 413)]
        innerDoors[8] = [Door("R2InnerDoor", 163, 266)]
        innerDoors[9] = [Door("R3InnerDoor", 171, 218)]
        innerDoors[10] = [Door("R4InnerDoor", 144, 151)]
        innerDoors[12] = [Door("GinsoInnerDoor", 522, 1), Door("ForlornInnerDoor", -717, -408), Door("HoruEscapeInnerDoor", -242, 489)]
        outerDoors[0] = [Door("GinsoOuterDoor", 527, -43), Door("ForlornOuterDoor", -668, -246), Door("HoruOuterDoor", -78, 2)]
        outerDoors[1] = [Door("L1OuterDoor", 20, 371)]
        outerDoors[2] = [Door("R1OuterDoor", 125, 382)]
        outerDoors[4] = [Door("L2OuterDoor", 13, 293)]
        outerDoors[5] = [Door("L3OuterDoor", 18, 248)]
        outerDoors[6] = [Door("L4OuterDoor", 14, 191)]
        outerDoors[8] = [Door("R2OuterDoor", 128, 288)]
        outerDoors[9] = [Door("R3OuterDoor", 126, 245)]
        outerDoors[10] = [Door("R4OuterDoor", 126, 196)]
        outerDoors[12] = [Door("HoruEscapeOuterDoor", 18, 100)]

        # So we shuffle the 3 in world outer doors, and the ginso/forlorn/escape doors.
        self.random.shuffle(outerDoors[0])
        self.random.shuffle(innerDoors[12])

        firstDoors = []
        lastDoors = []

        firstDoors.append(outerDoors[0].pop(0))
        firstDoors.append(outerDoors[0].pop(0))

        lastDoors.append(innerDoors[12].pop(0))
        lastDoors.append(innerDoors[12].pop(0))

        self.entrance_spoiler = "Entrances: {\n"
        doorStr = ""

        # activeGroups = [0, 1, 2]
        # targets = [3, 4, 5, 6, 7, 8, 9, 10, 12]
        # for now, make R1 vanilla

        dat_s, spoiler_s = self.connect_doors(outerDoors[2].pop(0), innerDoors[7].pop(0))
        doorStr += dat_s
        self.entrance_spoiler += spoiler_s

        activeGroups = [0, 1, 8]
        targets = [3, 4, 5, 6, 8, 9, 10, 12]

        self.random.shuffle(targets)
        # Below comes... 4 5 6 9 10 1 (11 becomes 1).
        # So we select an horu outer door for entry into horu.
        horuEntryGroup = self.random.randint(4, 9)
        if horuEntryGroup >= 7:
            horuEntryGroup += 2
        if horuEntryGroup == 11:
            horuEntryGroup = 1
            if self.random.random() > 0.5:
                # We connect one of our first doors to HoruInner
                dat_s, spoiler_s = self.connect_doors(firstDoors[0], innerDoors[1].pop(0))
                doorStr += dat_s
                self.entrance_spoiler += spoiler_s
                # We add the other first door back to outer doors[0]
                outerDoors[0].append(firstDoors[1])
            else:
                # We connect one of our first doors to L1Outer
                dat_s, spoiler_s = self.connect_doors(firstDoors[0], outerDoors[1].pop(0))
                doorStr += dat_s
                self.entrance_spoiler += spoiler_s
                # We add the other first door back, and also add in HoruInner
                outerDoors[0].append(firstDoors[1])
                outerDoors[0].append(innerDoors[1].pop(0))
        else:
            # We connect one of our first doors to an outer door inside horu.
            dat_s, spoiler_s = self.connect_doors(
                firstDoors[0], outerDoors[horuEntryGroup].pop(0))
            doorStr += dat_s
            self.entrance_spoiler += spoiler_s
            # We connect our other first door to a horu inner door.
            dat_s, spoiler_s = self.connect_doors(firstDoors[1], innerDoors[horuEntryGroup - 1].pop(0))
            doorStr += dat_s
            self.entrance_spoiler += spoiler_s
            targets.remove(horuEntryGroup - 1)

        # While we still have targets...
        while len(targets) > 0:
            index = self.random.randrange(len(activeGroups))
            group = activeGroups[index]
            if not outerDoors[group]:
                del activeGroups[index]
                continue

            target = targets[0]
            if not innerDoors[target]:
                del targets[0]
                continue

            if target < 12:
                activeGroups.append(target + 1)

            if (target == 6 and 10 not in targets) or (target == 10 and 6 not in targets):
                activeGroups.append(12)

            dat_s, spoiler_s = self.connect_doors(outerDoors[group].pop(0), innerDoors[target].pop(0))
            doorStr += dat_s
            self.entrance_spoiler += spoiler_s

        lastDoorIndex = 0

        for group in range(13):
            if innerDoors[group]:
                dat_s, spoiler_s = self.connect_doors(innerDoors[group].pop(0), lastDoors[lastDoorIndex])
                doorStr += dat_s
                self.entrance_spoiler += spoiler_s
                lastDoorIndex += 1
            if outerDoors[group]:
                dat_s, spoiler_s = self.connect_doors(outerDoors[group].pop(0), lastDoors[lastDoorIndex])
                doorStr += dat_s
                self.entrance_spoiler += spoiler_s
                lastDoorIndex += 1

        self.entrance_spoiler += "}\n"
        return doorStr

    def setSeedAndPlaceItems(self, params, preplaced={}, retries=10, verbose_paths=False):
        self.verbose_paths = verbose_paths
        self.params = params

        self.sharedList = []
        self.random = random.Random()
        self.random.seed(stable_string_hash(self.params.seed))
        self.preplaced = {k: self.codeToName.get(v, v) for k, v in preplaced.items()}
        self.do_multi = self.params.sync.enabled and self.params.sync.mode == MultiplayerGameType.SHARED

        if self.var(Variation.WORLD_TOUR):
            self.relicZones = self.random.sample(["Glades", "Grove", "Grotto", "Blackroot", "Swamp", "Ginso", "Valley", "Misty", "Forlorn", "Sorrow", "Horu"], self.params.relic_count)

        self.playerCount = 1
        if self.do_multi:
            if self.params.sync.cloned and self.params.sync.teams:
                self.playerCount = len(self.params.sync.teams)
            else:
                self.playerCount = self.params.players
            shared = self.params.sync.shared
            if ShareType.SKILL in shared:
                self.sharedList += ["WallJump", "ChargeFlame", "Dash", "Stomp", "DoubleJump", "Glide", "Bash", "Climb", "Grenade", "ChargeJump"]
            if ShareType.EVENT in shared:
                if self.params.key_mode == KeyMode.SHARDS:
                    self.sharedList += ["WaterVeinShard", "GumonSealShard", "SunstoneShard"]
                else:
                    self.sharedList += ["GinsoKey", "ForlornKey", "HoruKey"]
                self.sharedList += ["Water", "Wind", "Warmth"]
            if ShareType.TELEPORTER in shared:
                self.sharedList += ["TPForlorn", "TPGrotto", "TPSorrow", "TPGrove", "TPSwamp", "TPValley", "TPGinso", "TPHoru", "TPBlackroot", "TPGlades"]
            if ShareType.UPGRADE in self.params.sync.shared:
                self.sharedList += ["RB6", "RB8", "RB9", "RB10", "RB11", "RB12", "RB13", "RB15"]
                if self.var(Variation.EXTRA_BONUS_PICKUPS):
                    self.sharedList += ["RB31", "RB32", "RB33", "RB101", "RB102", "RB103", "RB104", "RB105", "RB106", "RB107", "RB36"]
            if ShareType.MISC in shared:
                if self.var(Variation.WARMTH_FRAGMENTS):
                    self.sharedList.append("RB28")
                # TODO: figure out relic sharing
                # if self.var(Variation.WORLD_TOUR):
                #      self.sharedList.append("Relic")
        return self.placeItemsMulti(retries)

    def placeItemsMulti(self, retries):
        placements = []
        self.sharedMap = {}
        self.sharedCounts = Counter()
        self.split_locs = {}
        self.playerID = 1

        placement = self.placeItems(0, retries < 7)
        if not placement:
            if retries > 0:
                if self.params.start != "Glades" and retries < 4:
                    log.info("Failed to generate with %s spawn and %s starting skills, adding another" % (self.params.start, self.params.starting_skills))
                    self.params.starting_skills += 1
                retries -= 1
            else:
                log.error("""Seed not completeable with these params and placements.
                            ItemCount: %s
                            Items remaining: %s,
                            Areas reached: %s,
                            AreasRemaining: %s,
                            Inventory: %s,
                            Forced Assignments: %s,
                            Nonzero Costs:%s,
                            Partial Seed: %s""",
                            self.locations(),
                            {k: v for k, v in self.itemPool.items() if v > 0},
                            [x for x in self.areasReached],
                            [x for x in self.areasRemaining],
                            {k: v for k, v in self.inventory.items() if v != 0},
                            self.forcedAssignments,
                            {k: v for k, v in self.costs.items() if v != 0},
                            self.outputStr)
                return None
            return self.placeItemsMulti(retries)
        placements.append(placement)
        if self.params.sync.cloned:
            lines = placement[0].split("\n")
            spoiler = placement[1]
        while self.playerID < self.playerCount:
            self.playerID += 1
            if self.params.sync.cloned:
                outlines = [lines[0]]
                for line in lines[1:-1]:
                    loc, _, _, zone = tuple(line.split("|"))
                    if int(loc) in self.split_locs:
                        player, split_item = self.split_locs[int(loc)]
                        if self.playerID != player:  # theirs
                            hint = self.cloned_item(split_item, player)
                            outlines.append("|".join([loc, hint[:2], hint[2:], zone]))
                        else:  # ours
                            outlines.append("|".join([loc, split_item[:2], split_item[2:], zone]))
                    else:
                        outlines.append(line)
                placements.append(("\n".join(outlines) + "\n", spoiler))
            else:
                placement = self.placeItems(0, retries < 5)
                if not placement:
                    if retries > 0:
                        retries -= 1
                    else:
                        log.error("Coop seed not completeable with these params and placements")
                        return None
                    return self.placeItemsMulti(retries)
                placements.append(placement)
        if self.params.spawn != self.start:
            self.params.spawn = self.start
            self.params.put()
        return placements

    def locations(self):
        """Number of remaining locations that can have items in them"""
        remaining_fass = len(self.forcedAssignments) - len(self.forceAssignedLocs)
        return sum([len(area.locations) for area in self.areas.values()]) - remaining_fass + len(self.reservedLocations)

    def items(self, include_balanced=True):
        """Number of items left to place"""
        balanced = len(self.balanceListLeftovers) if include_balanced else 0
        return sum([v for v in self.itemPool.values()]) + balanced + self.unplaced_shared

    def place_repeatables(self):
        repeatables = []
        for item, count in [(i,c)  for (i,c) in self.itemPool.items()]:
            if item.startswith("RP"):
                repeatables += count * [item]
                del self.itemPool[item]
        if self.itemPool.get("WP*", 0) > 0:
            warps = min(self.itemPool["WP*"], 14)
            del self.itemPool["WP*"]
            for warp_group in self.random.sample(warp_targets, warps):
                repeatables.append("RPSH/Press AltR to Warp to %s/WP/%s,%s" % self.random.choice(warp_group))
        if repeatables:
            true_rep_locs = list(set(repeatable_locs) - set(self.forcedAssignments.keys()))
            for loc, pickup in zip(self.random.sample(true_rep_locs, len(repeatables)), repeatables):
                self.forcedAssignments[loc] = pickup

    def placeItems(self, depth=0, worried=False):
        self.reset(worried)
        keystoneCount = 0
        mapstoneCount = 0

        self.form_areas(self.var(Variation.KEYS_ONLY_FOR_DOORS))
        self.create_warp_paths()
        if self.params.do_loc_analysis:
            self.params.locationAnalysisCopy = {}
            for location in self.params.locationAnalysis:
                self.params.locationAnalysisCopy[location] = {}
                for item in self.params.locationAnalysis[location]:
                    self.params.locationAnalysisCopy[location][item] = self.params.locationAnalysis[location][item]

        # flags line
        self.outputStr += (self.params.flag_line(self.verbose_paths) + "\n")

        self.spoilerGroup = defaultdict(list)

        if self.var(Variation.ENTRANCE_SHUFFLE):
            self.outputStr += self.randomize_entrances()

        if self.var(Variation.WORLD_TOUR):
            locations_by_zone = OrderedDict({zone: [] for zone in self.relicZones})
            for area in self.areas.values():
                for location in area.locations:
                    if location.zone in locations_by_zone:
                        locations_by_zone[location.zone].append(location)

            for locations in locations_by_zone.values():
                self.random.shuffle(locations)

                relic_loc = None

                while not relic_loc and len(locations):
                    next_loc = locations.pop()
                    # Can't put a relic on a map turn-in
                    if next_loc.orig == "MapStone":
                        continue
                    # Can't put a relic on a reserved preplacement location
                    # TODO: re-impl relics via preplacement
                    if next_loc.get_key() in self.forcedAssignments:
                        continue
                    relic_loc = next_loc
                self.relic_assign(relic_loc)
            # Capture relic spoilers before the spoiler group is overwritten
            relicSpoiler = self.spoilerGroup["Relic"]

        self.place_repeatables()
        # handle the fixed pickups: first energy cell, the glitchy 100 orb at spirit tree, and the forlorn escape plant
        # FIXME Make the EC1 do something.
        for loc, item, zone in [(-280256, "EC1", "Glades"), (-12320248, "RB81", "Forlorn")]:
            if loc in self.forcedAssignments:
                item = self.forcedAssignments[loc]
                del self.forcedAssignments[loc]  # don't count these ones
            if item not in ["EX100", "EC1", "RB81"] and item not in self.itemPool:
                log.warning("Preplaced item %s was not in pool. Translation may be necessary." % item)
            ass = self.get_assignment(loc, self.adjust_item(item, zone), zone)
            self.outputStr += ass

        if 2 in self.forcedAssignments:
            item = self.forcedAssignments[2]
            self.assign(item)
            if item[0:2] in ["MU", "RP"] and item not in self.itemPool:                
                for multi_item in self.get_multi_items(item):
                    # below should not be needed as get_multi_items() already does it, and repeating
                    # it breaks shards names.
                    #name = self.codeToName.get(multi_item, multi_item)
                    #self.spoilerGroup[name].append(name + " preplaced at Spawn\n")
                    if not multi_item.startswith("WS"): # avoid dumb padding thing
                        self.append_spoiler(self.adjust_item(multi_item, "Glades"), "Spawn")
            else:
                name = self.codeToName.get(item, item)
                self.append_spoiler(self.adjust_item(name, "Glades"), "Spawn")
            del self.forcedAssignments[2]
            ass = self.get_assignment(2, self.adjust_item(item, "Glades"), "Glades")
            self.outputStr += ass 

        if len(self.spoilerGroup):
            self.spoiler.append((["Spawn"], [], self.spoilerGroup))
            self.spoilerGroup = defaultdict(list)

        for loc, v in self.forcedAssignments.items():
            if v[0:2] in ["MU", "RP"]:
                for item in self.get_multi_items(v):
                    if item in self.itemPool:
                        self.itemPool[item] -= 1
                    self.spoilerGroup[item].append(item + " preplaced at %s \n" % all_locations[loc].to_string() if loc in all_locations else loc)
            if v in self.itemPool:
                self.itemPool[v] -= 1
        
        locationsToAssign = []
        self.connectionQueue = []
        self.reservedLocations = []

        self.skillCount = 10
        self.mapstonesAssigned = 0

        self.doorQueue = OrderedDict()
        self.mapQueue = OrderedDict()
        spoilerPath = []

        #if self.start == "Glades":
        #    self.reach_area("SunkenGladesRunaway")
        #    if self.var(Variation.OPEN_WORLD):
        #        self.reach_area("GladesMain")
        #else:
        #    self.reach_area(self.spawn_logic_areas[self.start])
        
        if self.var(Variation.OPEN_WORLD):
            #for connection in list(self.areas["SunkenGladesRunaway"].connections):
            #    if connection.target == "GladesMain":
            #        self.areas["SunkenGladesRunaway"].remove_connection(connection)
            # We remove the keystone connection, and create a new connection that is free.
            for connection in list(self.areas["GladesFirstKeyDoor"].connections):
                if connection.target == "GladesFirstKeyDoorOpened":
                    self.areas["GladesFirstKeyDoor"].remove_connection(connection)
            connection = Connection("GladesFirstKeyDoor", "GladesFirstKeyDoorOpened", self)
            connection.add_requirements([], 0)
            self.areas["GladesFirstKeyDoor"].add_connection(connection)

        if self.var(Variation.KEYS_ONLY_FOR_DOORS) and self.params.key_mode == KeyMode.SHARDS:
            for connection in list(self.areas["TeleporterNetwork"].connections):
                if connection.target in ["HoruTeleporter", "GinsoTeleporter", "ForlornTeleporter"]:
                    self.areas["TeleporterNetwork"].remove_connection(connection)
            connection = Connection("TeleporterNetwork", "HoruTeleporter", self)
            connection.add_requirements(["TPHoru", "SunstoneShard", "SunstoneShard"], 0)
            self.areas["TeleporterNetwork"].add_connection(connection)
            connection = Connection("TeleporterNetwork", "GinsoTeleporter", self)
            connection.add_requirements(["TPGinso", "WaterVeinShard", "WaterVeinShard"], 0)
            self.areas["TeleporterNetwork"].add_connection(connection)
            connection = Connection("TeleporterNetwork", "ForlornTeleporter", self)
            connection.add_requirements(["TPForlorn", "GumonSealShard", "GumonSealShard"], 0)
            self.areas["TeleporterNetwork"].add_connection(connection)

        self.reach_area(self.spawn_logic_areas[self.start])

        self.itemPool["EX*"] = self.locations() - sum([v for v in self.itemPool.values()]) - self.unplaced_shared + 1  # add 1 for warmth returned (:
        self.expSlots = self.itemPool["EX*"]
        locs = self.locations()
        while locs > 0:
            if locs != self.items() - 1:
                log.warning("Item (%s) /Location (%s) desync!", self.items(), self.locations())
            self.balanceLevel += 1
            # open all paths that we can already access
            opening = True
            while opening:
                (opening, keys, mapstones) = self.open_free_connections()
                keystoneCount += keys
                mapstoneCount += mapstones
                if mapstoneCount >= 9:
                    mapstoneCount = 11
                if mapstoneCount == 8:
                    mapstoneCount = 9
                for connection in self.connectionQueue:
                    self.areas[connection[0]].remove_connection(connection[1])
                self.connectionQueue = []
            reset_loop = False
            locationsToAssign, reset_loop = self.get_all_accessible_locations()

            # if there aren't any doors to open, it's time to get a new skill
            # consider -- work on stronger anti-key-lock logic so that we don't
            # have to give keys out right away (this opens up the potential of
            # using keys in the wrong place, will need to be careful)
            if not (self.doorQueue and self.inventory["KS"] >= keystoneCount) and not (self.mapQueue and self.inventory["MS"] >= mapstoneCount) and not reset_loop and len(locationsToAssign) == 0:
                if self.reservedLocations:
                    locationsToAssign.append(self.reservedLocations.pop(0))
                    locationsToAssign.append(self.reservedLocations.pop(0))
                spoilerPath = self.prepare_path(len(locationsToAssign) + len(self.balanceList))
                if self.params.balanced:
                    for item in self.assignQueue:
                        if len(self.balanceList) == 0:
                            break
                        locationsToAssign.append(self.get_location_from_balance_list())
                if not self.assignQueue:
                    # we've painted ourselves into a corner, try again
                    if self.playerID == 1:
                        self.split_locs = {}
                        self.sharedMap = {}
                        self.sharedCounts = Counter()
                    if depth > self.playerCount * self.playerCount + self.params.keysanity * 10:
                        return
                    return self.placeItems(depth + 1, worried)

            # pick what we're going to put in our accessible space
            itemsToAssign = []
            if len(locationsToAssign) < len(self.assignQueue) + max(keystoneCount - self.inventory["KS"], 0) + max(mapstoneCount - self.inventory["MS"], 0):
                # we've painted ourselves into a corner, try again
                if not self.reservedLocations:
                    if self.playerID == 1:
                        self.split_locs = {}
                        self.sharedMap = {}
                        self.sharedCounts = Counter()
                    if depth > self.playerCount * self.playerCount + self.params.keysanity * 10:
                        return
                    return self.placeItems(depth + 1, worried)
                locationsToAssign.append(self.reservedLocations.pop(0))
                locationsToAssign.append(self.reservedLocations.pop(0))
            for i in range(0, len(locationsToAssign)):
                locs = self.locations()
                if self.assignQueue:
                    itemsToAssign.append(self.assign(self.assignQueue.pop(0)))
                elif self.inventory["KS"] < keystoneCount:
                    itemsToAssign.append(self.assign("KS"))
                elif self.inventory["MS"] < mapstoneCount:
                    itemsToAssign.append(self.assign("MS"))
                elif self.inventory["HC"] * self.params.cell_freq < (252 - locs) and self.itemPool["HC"] > 0:
                    itemsToAssign.append(self.assign("HC"))
                elif self.inventory["EC"] * self.params.cell_freq < (252 - locs) and self.itemPool["EC"] > 0:
                    itemsToAssign.append(self.assign("EC"))
                elif self.itemPool.get("RB28", 0) > 0 and self.itemPool["RB28"] >= locs:
                    itemsToAssign.append(self.assign("RB28"))
                elif self.balanceListLeftovers and self.items(include_balanced=False) < 2:
                    itemsToAssign.append(self.balanceListLeftovers.pop(0))
                else:
                    itemsToAssign.append(self.assign_random(locs))

            for _ in range(len(self.sharedAssignQueue)):
                self.assign(self.sharedAssignQueue.pop(0))

            # force assign things if using --prefer-path-difficulty
            if self.params.path_diff != PathDifficulty.NORMAL:
                for item in list(itemsToAssign):
                    if item in self.skillsOutput or item in self.eventsOutput:
                        self.preferred_difficulty_assign(item, locationsToAssign)
                        itemsToAssign.remove(item)

            # shuffle the items around and put them somewhere
            self.random.shuffle(itemsToAssign)
            for i in range(0, len(locationsToAssign)):
                self.assign_to_location(itemsToAssign[i], locationsToAssign[i])

            self.spoiler.append((self.currentAreas, spoilerPath, self.spoilerGroup))

            # open all reachable doors (for the next iteration)
            if self.inventory["KS"] >= keystoneCount:
                for area in self.doorQueue.keys():
                    if self.doorQueue[area].target not in self.areasReached:
                        difficulty = self.doorQueue[area].cost()[2]
                        self.seedDifficulty += difficulty * difficulty
                    self.reach_area(self.doorQueue[area].target)
                    if self.doorQueue[area].target in self.areasRemaining:
                        self.areasRemaining.remove(self.doorQueue[area].target)
                    self.areas[area].remove_connection(self.doorQueue[area])

            if self.inventory["MS"] >= mapstoneCount:
                for area in self.mapQueue.keys():
                    if self.mapQueue[area].target not in self.areasReached:
                        difficulty = self.mapQueue[area].cost()[2]
                        self.seedDifficulty += difficulty * difficulty
                    self.reach_area(self.mapQueue[area].target)
                    if self.mapQueue[area].target in self.areasRemaining:
                        self.areasRemaining.remove(self.mapQueue[area].target)
                    self.areas[area].remove_connection(self.mapQueue[area])

            locationsToAssign = []
            self.spoilerGroup = defaultdict(list)
            self.currentAreas = []

            self.doorQueue = OrderedDict()
            self.mapQueue = OrderedDict()
            spoilerPath = []

        if self.params.balanced:
            for item in self.balanceList:
                self.outputStr += item[2]

        # place the last item on the final escape
        balanced = self.params.balanced
        self.params.balanced = False
        for item in self.itemPool:
            if self.itemPool[item] > 0:
                self.assign_to_location(item, Location(-240, 512, 'FinalEscape', 'EVWarmth', 0, 'Horu'))
                break
        else:  # In python, the else clause of a for loop triggers if the loop completed without breaking, e.g. we found nothing in the item pool
            if len(self.balanceListLeftovers) > 0:
                item = self.balanceListLeftovers.pop(0)
                log.info("Empty item pool: placing %s from balanceListLeftovers onto warmth returned.", item)
                self.assign_to_location(item, Location(-240, 512, 'FinalEscape', 'EVWarmth', 0, 'Horu'))
            else:
                log.warning("%s: No item found for warmth returned! Placing EXP", self.params.flag_line())
                self.assign_to_location("EX*", Location(-240, 512, 'FinalEscape', 'EVWarmth', 0, 'Horu'))
        self.params.balanced = balanced

        self.random.shuffle(self.eventList)
        for event in self.eventList:
            self.outputStr += event

        if len(self.balanceListLeftovers) > 0:
            log.warning("%s: Balance list was not empty! %s", self.params.flag_line(), self.balanceListLeftovers)

        if len(self.spoilerGroup):
            self.spoiler.append((self.currentAreas, spoilerPath, self.spoilerGroup))

        spoilerStr = self.form_spoiler()
        spoilerStr = self.params.flag_line(self.verbose_paths) + "\n" + "Difficulty Rating: " + str(self.seedDifficulty) + "\n" + spoilerStr

        if self.var(Variation.WORLD_TOUR):
            spoilerStr += "Relics: {\n"
            for instance in relicSpoiler:
                spoilerStr += "    " + instance
            spoilerStr += "}\n"

        if self.params.do_loc_analysis:
            self.params.locationAnalysis = self.params.locationAnalysisCopy

        return (self.outputStr, spoilerStr)

    def get_multi_items(self, multi_item):
        multi_parts = multi_item[2:].split("/")
        multi_items = []
        while len(multi_parts) > 1:
            item = multi_parts.pop(0) + multi_parts.pop(0)
            if item[0:2] in ["AC", "EC", "KS", "MS", "HC"]:
                item = item[0:2]
            multi_items.append(self.codeToName.get(item, item))
        return multi_items

    def form_spoiler(self):
        def pad(instance):
          name, _, loc = instance.partition("!PDPLC!-")
          return name + (2+self.padding - len(name))*" " + loc
        i = 0
        groupDepth = -1 if 2 in self.preplaced else 0
        spoilerStr = ""

        while i < len(self.spoiler):
            sets_forced = 1 if self.spoiler[i][1] else 0
            groupDepth += 1
            self.currentAreas = self.spoiler[i][0]
            spoilerPath = self.spoiler[i][1]
            self.spoilerGroup = self.spoiler[i][2]
            while i + 1 < len(self.spoiler) and len(self.spoiler[i + 1][0]) == 0:
                spoilerPath += self.spoiler[i + 1][1]
                sets_forced += 1 if self.spoiler[i + 1][1] else 0
                for item in self.spoiler[i + 1][2]:
                    self.spoilerGroup[item] += self.spoiler[i + 1][2][item]
                i += 1
            i += 1
            currentGroupSpoiler = ""

            if spoilerPath:
                currentGroupSpoiler += ("    " + str(sets_forced) + " forced pickup set" + ("" if sets_forced == 1 else "s") + ": " + str(spoilerPath) + "\n")
            for skill in self.skillsOutput:
                code = self.skillsOutput[skill]
                if code in self.spoilerGroup:
                    for instance in self.spoilerGroup[code]:
                        currentGroupSpoiler += "    " + pad(instance)
                    if skill in self.seedDifficultyMap:
                        self.seedDifficulty += groupDepth * self.seedDifficultyMap[skill]

            for event in self.eventsOutput:
                code = self.eventsOutput[event]
                if code in self.spoilerGroup:
                    for instance in self.spoilerGroup[code]:
                        currentGroupSpoiler += "    " + pad(instance)

            '''
            for keystone in self.keysanityOutput:
                code = self.keysanityOutput[keystone]
                if code in self.spoilerGroup:
                    for instance in self.spoilerGroup[code]:
                        currentGroupSpoiler += "    " + pad(instance)
            '''

            for key in self.spoilerGroup:
                if key[:2] == "TP":
                    for instance in self.spoilerGroup[key]:
                        currentGroupSpoiler += "    " + pad(instance)

            for warp_id in self.warps.keys():
                if warp_id in self.spoilerGroup:
                    for instance in self.spoilerGroup[warp_id]:
                        currentGroupSpoiler += "    " + pad(instance)

            for pickup_type in ["RB", "MS", "KS", "HC", "EC", "AC", "EX"]:
                for key in self.spoilerGroup:
                    if key[:2] == pickup_type:
                        for instance in self.spoilerGroup[key]:
                            currentGroupSpoiler += "    " + pad(instance)
            self.currentAreas.sort()

            spoilerStr += str(groupDepth) + ": " + str(self.currentAreas) + " {\n"

            spoilerStr += currentGroupSpoiler

            spoilerStr += "}\n"

        spoilerStr += self.entrance_spoiler

        return spoilerStr

    def do_reachability_analysis(self, params):
        self.params = params
        self.preplaced = {}
        self.playerID = 1
        self.mapQueue = {}
        self.reservedLocations = []
        self.doorQueue = {}
        self.random = random.Random()
        #items = ["WallJump", "Dash", "ChargeFlame", "DoubleJump", "Bash", "Stomp", "Grenade", "Glide", "Climb", "ChargeJump"]
        items = ["Glide", "Stomp", "DoubleJump", "ChargeFlame", "WallJump"]
        #items = ["Climb", "WallJump"]
        #items = ["Grenade", "ChargeFlame"]
        #items = ["Bash", "ChargeJump", "Glide", "DoubleJump"]
        #items = ["ChargeJump", "Stomp"]
        #items = ["TPHoru"]
        fill_items = ["WallJump", "Dash", "TPGrove", "ChargeFlame", "TPSwamp", "TPGrotto", "DoubleJump", "GinsoKey", "Bash", "TPGinso", "Water", "Stomp", "Grenade", "Glide", "TPValley", "Climb", "ForlornKey", "TPForlorn", "Wind", "ChargeJump", "TPSorrow", "HoruKey", "TPHoru"]
        overlap_items = []
        for item in overlap_items:
            fill_items.remove(item)
        #fill_items = ["TPGrove", "TPSwamp", "TPGrotto", "GinsoKey", "TPGinso", "Water", "TPValley", "ForlornKey", "TPForlorn", "Wind", "TPSorrow", "HoruKey", "TPHoru"]
        #fill_items = ["ForlornKey"]
        scores = []
        for item in items:
            self.reset()
            for item2 in fill_items:
                if item2 not in items:
                    self.inventory[item2] = 1
                    self.costs[item2] = 0
            score = 0
            for item2 in items:
                print(item + " " + item2)
                self.inventory["KS"] = 40
                self.inventory["MS"] = 11
                self.inventory["AC"] = 33
                self.inventory["EC"] = 15
                self.inventory["HC"] = 15
                self.costs["KS"] = 0
                self.costs["MS"] = 0
                self.costs["AC"] = 0
                self.costs["EC"] = 0
                self.costs["HC"] = 0
                self.form_areas()
                self.reservedLocations = []
                self.inventory[item2] = 1
                self.costs[item2] = 0
                self.inventory[item] = 0
                self.costs[item] = 1
                self.reach_area("SunkenGladesRunaway")
                if self.var(Variation.OPEN_WORLD):
                    self.reach_area("GladesMain")
                    for connection in list(self.areas["SunkenGladesRunaway"].connections):
                        if connection.target == "GladesMain":
                            self.areas["SunkenGladesRunaway"].remove_connection(connection)
                locations = 1
                while locations > 0:
                    opening = True
                    while opening:
                        (opening, keys, mapstones) = self.open_free_connections()
                        for connection in self.connectionQueue:
                            self.areas[connection[0]].remove_connection(connection[1])
                        self.connectionQueue = []
                    locationsToAssign, reset_loop = self.get_all_accessible_locations()
                    locations = len(locationsToAssign)
                self.inventory[item] = 1
                self.costs[item] = 0
                locations = 1
                while locations > 0:
                    opening = True
                    while opening:
                        (opening, keys, mapstones) = self.open_free_connections()
                        for connection in self.connectionQueue:
                            self.areas[connection[0]].remove_connection(connection[1])
                        self.connectionQueue = []
                    locationsToAssign, reset_loop = self.get_all_accessible_locations()
                    string = ""
                    for loc in locationsToAssign:
                        string += loc.to_string() + " "
                    print(string)
                    locations = len(locationsToAssign)
                    score += locations
            scores.append(score)
        for item, score in zip(items, scores):
            print("%s %d" % (item, score))
