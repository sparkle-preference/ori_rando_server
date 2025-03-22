import sys
from os import path
from collections import OrderedDict
import pprint

def _parsefatal(line, msg):
    if _VERBOSE:
        print("[FATAL] line %d - %s" % (line, msg))

def _parseerror(line, msg):
    if _VERBOSE:
        print("[ERROR] line %d - %s" % (line, msg))

def _parsewarn(line, msg):
    if _VERBOSE:
        print("[WARN] line %d - %s" % (line, msg))

_VERBOSE = False

def get_path_tags(parts):
    tags = []
    difficulty = parts[0]
    if difficulty in _DIFFICULTIES_IGNORING_TAGS:
        tags.append(difficulty)
        return tags
    
    for part in parts[1:]:
        if part in _TAGS:
            tags.append(difficulty + part)
        if part.startswith("Health="):
            tags.append(difficulty + "DamageBoost")
        if part.startswith("Ability="):
            tags.append(difficulty + "Abilities")

    if len(tags) == 0:
        # If it isn't in any of dboost ability dbash etc. it is a "Core" path.
        tags.append(difficulty + "Core")
            
    return tags


_DIFFICULTIES_IGNORING_TAGS = [
    "glitched",
    "timed-level",
    "insane"
]

_DIFFICULTIES_WITH_TAGS = [
    "casual",
    "standard",
    "expert",
    "master",
]

_DIFFICULTIES = _DIFFICULTIES_WITH_TAGS + _DIFFICULTIES_IGNORING_TAGS

_PATH_TAGS_FROM_PATHSET = {
    "casual-core": ["casualCore", "casualBashGrenade"],
    "casual-dboost": ["casualDamageBoost"],
    "standard-core": ["standardCore", "standardBashGrenade"],
    "standard-dboost": ["standardDamageBoost"],
    "standard-lure": ["standardLure"],
    "standard-abilities": ["standardAbilities", "standardAirDash", "standardRekindle"],
    "expert-core": ["expertCore", "expertBashGrenade"],
    "expert-dboost": ["expertDamageBoost"],
    "expert-lure": ["expertLure"],
    "expert-abilities": ["expertAbilities", "expertChargeDash", "expertRocketJump", "expertAirDash", "expertRekindle"],
    "dbash": ["expertDoubleBash"],
    "master-core": ["masterCore", "masterDoubleBash", "masterBashGrenade"],
    "master-dboost": ["masterDamageBoost"],
    "master-lure": ["masterLure"],
    "master-abilities": ["masterAbilities", "masterChargeFlameBurn", "masterChargeDash", "masterRocketJump", "masterAirDash", "masterTripleJump", "masterUltraDefense", "masterRekindle"],
    "gjump": ["masterGrenadeJump"],
    "glitched": ["glitched"],
    "timed-level": ["timed-level"],
    "insane": ["insane"]
}
PATHSETS_BY_REVERSE_DIFF =     ["insane", "timed-level", "glitched", "gjump", "master-abilities", "master-lure", "master-dboost", "master-core", "dbash", "expert-abilities", "expert-lure", "expert-dboost", "expert-core", "standard-abilities", "standard-lure", "standard-dboost", "standard-core", "casual-dboost", "casual-core"]

def get_path_tags_from_pathsets(pathsets):
    path_tags = []
    for pathset in pathsets:
        for path_tag in _PATH_TAGS_FROM_PATHSET.get(pathset, []):
            if path_tag not in path_tags:
                path_tags.append(path_tag)
    return path_tags
# hacky and bad; fix later
def hardest_pathset_from_tags(tags):
    pathsets = list(set([get_pathset_from_tag(tag) for tag in tags]))
    for pset in PATHSETS_BY_REVERSE_DIFF:
        if pset in pathsets:
            return pset
    return pathsets[0]
def get_pathset_from_tag(tag):
    for pset, tags in _PATH_TAGS_FROM_PATHSET.items():
        if tag in tags:
            return pset
# DamageBoost and Abilities are implicit tags.
_TAGS = [
    "Lure",
    "DoubleBash",
    "GrenadeJump",
    "ChargeFlameBurn",
    "ChargeDash",
    "RocketJump",
    "AirDash",
    "TripleJump",
    "UltraDefense",
    "BashGrenade",
    "Rekindle"
]

_TAGS_SKILLS = {
    "Lure": [],
    "DoubleBash": ["Bash"],
    "GrenadeJump": ["Climb", "ChargeJump", "Grenade"],
    "ChargeFlameBurn": ["ChargeFlame"],
    "ChargeDash": ["Dash"],
    "RocketJump": ["Dash"],
    "AirDash": ["Dash"],
    "TripleJump": ["DoubleJump"],
    "UltraDefense": [],
    "BashGrenade": ["Bash", "Grenade"],
    "Rekindle": []
}

_TAGS_ABILITY = {
    "Lure": 0,
    "DoubleBash": 0,
    "GrenadeJump": 0,
    "ChargeFlameBurn": 3,
    "ChargeDash": 6,
    "RocketJump": 6,
    "AirDash": 3,
    "TripleJump": 12,
    "UltraDefense": 12,
    "BashGrenade": 0,
    "Rekindle": 0
}

_REQS = [
    "WallJump",
    "ChargeFlame",
    "DoubleJump",
    "Bash",
    "Stomp",
    "Glide",
    "Climb",
    "ChargeJump",
    "Grenade",
    "Dash",
    "GinsoKey",
    "ForlornKey",
    "HoruKey",
    "Water",
    "Wind",
    "TPGlades",
    "TPGrove",
    "TPSwamp",
    "TPGrotto",
    "TPGinso",
    "TPValley",
    "TPForlorn",
    "TPSorrow",
    "TPHoru",
    "TPBlackroot",
    "Health",
    "Energy",
    "Ability",
    "Keystone",
    "Mapstone",
    "Free",
    "Open",
    "OpenWorld",
    "Keysanity",
    "GladesPoolKeys",
    "LowerSpiritCavernsKeys",
    "GrottoKeys",
    "SwampKeys",
    "UpperSpiritCavernsKeys",
    "LowerGinsoKeys",
    "UpperGinsoKeys",
    "MistyKeys",
    "ForlornKeys",
    "LowerSorrowKeys",
    "MidSorrowKeys",
    "UpperSorrowKeys"
]

def get_areas(areas_ori_path="", verbose=False):
    if areas_ori_path == "":
        dir_path = path.dirname(path.realpath(__file__))
        return ori_load_file("%s/areas.ori" % dir_path, verbose)
    else:
        return ori_load_file(areas_ori_path, verbose)

def ori_load_file(fn, verbose=False):
    with open(fn, 'r') as f:
        lines = f.readlines()

    return ori_load(lines, verbose)

def ori_load_url(url, verbose=False):
    try:
        # use urlfetch if we have it to avoid webgen warning spam
        from google.appengine.api import urlfetch
        result = urlfetch.fetch(url)
        lines = result.content.split("\n")
    except ImportError:
        # cli_gen uses urllib2 instead
        import urllib2
        response = urllib2.urlopen(url)
        lines = response.read().split("\n")

    return ori_load(lines, verbose)

def ori_load(lines, verbose=False):
    global _VERBOSE
    _VERBOSE = verbose

    contents = OrderedDict([
        ('locs', OrderedDict()),
        ('homes', OrderedDict())
    ])
    context_home = None
    context_conn = None
    i = 0

    while i < len(lines):
        # Tokenize the line by whitespace
        tokens = lines[i].split()
        i += 1

        # Skip empty lines and full comment lines
        if len(tokens) == 0:
            continue
        if tokens[0][:2] == "--":
            continue

        # Drop any tokens after a comment marker
        for j in range(len(tokens)):
            if tokens[j][:2] == "--":
                tokens = tokens[:j]
                break

        # Find a type marker and perform contextual parsing
        if tokens[0][-1:] == ":":
            type_marker = tokens[0][:-1]

            if type_marker == "loc":
                context_home = None
                context_conn = None

                if len(tokens) < 7:
                    _parseerror(i, "ignoring loc definition with too few fields (name, X, Y, original item, difficulty, zone)")
                    continue

                name = tokens[1]
                if name in contents["homes"]:
                    _parsefatal(i, "cannot use the same name `%s` for both a pickup location and a home!" % name)
                    return None

                if name in contents["locs"]:
                    _parseerror(i, "ignoring duplicate loc definition for `%s`" % name)
                    continue

                if len(tokens) > 7:
                    _parsewarn(i, "ignoring extra fields in loc definition for `%s`" % name)

                x = tokens[2]
                y = tokens[3]
                item = tokens[4]
                difficulty = tokens[5]
                zone = tokens[6]

                contents["locs"][name] = OrderedDict([
                    ('x', x),
                    ('y', y),
                    ('item', item),
                    ('difficulty', difficulty),
                    ('zone', zone)
                ])
            elif type_marker == "home":
                context_home = None
                context_conn = None

                if len(tokens) < 2:
                    _parseerror(i, "ignoring home definition with too few fields (name)")
                    continue

                name = tokens[1]
                if name in contents["locs"]:
                    _parsefatal(i, "cannot use the same name `%s` for both a pickup location and a home!" % name)
                    return None

                if name in contents["homes"]:
                    _parseerror(i, "ignoring duplicate home definition for `%s`" % name)
                    continue
                else:
                    contents["homes"][name] = OrderedDict([
                        ('conns', OrderedDict())
                    ])

                if len(tokens) > 2:
                    _parsewarn(i, "ignoring extra fields in home definition for `%s`" % name)

                context_home = name
            elif type_marker == "pickup" or type_marker == "conn":
                if not context_home:
                    _parseerror(i, "ignoring %s connection with no active home" % type_marker)
                    continue

                context_conn = None

                if len(tokens) < 2:
                    _parseerror(i, "ignoring %s connection in home `%s` with too few fields (name)" % (type_marker, context_home))
                    continue

                name = tokens[1]
                if name in contents["homes"][context_home]["conns"]:
                    _parsewarn(i, "combining duplicate %s connection for `%s` in same home `%s`" % (type_marker, name, context_home))
                else:
                    contents["homes"][context_home]["conns"][name] = OrderedDict([
                        ("type", type_marker),
                        ("paths", [])
                    ])

                if len(tokens) > 2:
                    _parsewarn(i, "ignoring extra fields in %s connection for `%s` in home `%s`" % (type_marker, name, context_home))

                context_conn = name
        else:
            # If there's no type marker, it's a logic path
            valid = True

            if tokens[0] not in _DIFFICULTIES:
                _parseerror(i, "ignoring logic path with unknown difficulty %s" % tokens[0])
                valid = False

            if valid and not context_home:
                _parseerror(i, "ignoring logic path with no active home")
                valid = False

            if valid and not context_conn:
                _parseerror(i, "ignoring logic path with no active connection")
                valid = False

            has_health = False
            has_ability = False
            has_mapstone = False
            tags = []
            health = 0
            ability = 0

            if valid:
                output_tokens = []
                for j in range(1, len(tokens)):
                    req = tokens[j]
                    if "=" in req:
                        (req, count) = req.split("=")

                        if int(count) == 0:
                            _parseerror(i, "ignoring logic path with invalid count requirement %s" % tokens[j])
                            valid = False
                            break
                    if (req not in _REQS) and (req not in _TAGS):
                        _parseerror(i, "ignoring logic path with unknown requirement %s" % tokens[j])
                        valid = False
                        break

                    if req == "Health":
                        has_health = True
                        health = int(count);
                    elif req == "Ability":
                        has_ability = True
                        if int(count) > ability:
                            ability = int(count);
                    elif req == "Mapstone":
                        has_mapstone = True
                        output_tokens.append("Mapstone")
                    elif req in _TAGS:
                        bundled_skills = _TAGS_SKILLS[req]
                        for bundled_skill in bundled_skills:
                            if bundled_skill not in output_tokens:
                                output_tokens.append(bundled_skill)
                        bundled_ability = _TAGS_ABILITY[req]
                        if bundled_ability > 0:
                            has_ability = True
                            if bundled_ability > ability:
                                ability = bundled_ability
                    else: #if req not in _TAGS:
                        if tokens[j] not in output_tokens:
                            output_tokens.append(tokens[j])

                if has_ability:
                    output_tokens.append("Ability=" + str(ability))
                if has_health:
                    output_tokens.append("Health=" + str(health))

            if not valid:
                # As far as I can tell the line of code below was useless.
                #contents["homes"][context_home]["conns"][name]["paths"].append(tuple(["invalid"] + tokens))
                continue

            path_tags = get_path_tags(tokens)
            
            if (tokens[0] == "casual") and (has_ability == True):
                _parsewarn(i, "`%s` logic path (from: `%s` to: `%s`) has an ability point count but is in casual" % (tokens[0], context_home, context_conn))
            if (tokens[0] == "standard") and (has_ability == True) and (ability > 3):
                _parsewarn(i, "`%s` logic path (from: `%s` to: `%s`) has an ability > 3 but is in standard" % (tokens[0], context_home, context_conn))
            if (tokens[0] == "expert") and (has_ability == True) and (ability > 6):
                _parsewarn(i, "`%s` logic path (from: `%s` to: `%s`) has an ability > 6 but is in expert" % (tokens[0], context_home, context_conn))
            
            if (tokens[0] == "casual") and (has_health == True) and (health > 3):
                _parsewarn(i, "`%s` logic path (from: `%s` to: `%s`) has a health > 3 but is in casual" % (tokens[0], context_home, context_conn))
            if (tokens[0] == "standard") and (has_health == True) and (health > 4):
                _parsewarn(i, "`%s` logic path (from: `%s` to: `%s`) has a health > 4 but is in standard" % (tokens[0], context_home, context_conn))
            if (tokens[0] == "expert") and (has_health == True) and (health > 7):
                _parsewarn(i, "`%s` logic path (from: `%s` to: `%s`) has a health > 7 but is in expert" % (tokens[0], context_home, context_conn))
            
            if (tokens[0] == "casual") and ("Lure" in tokens):
                _parsewarn(i, "`%s` logic path (from: `%s` to: `%s`) has Lure." % (tokens[0], context_home, context_conn))
            if (tokens[0] in ["casual", "standard"]) and ("DoubleBash" in tokens):
                _parsewarn(i, "`%s` logic path (from: `%s` to: `%s`) has DoubleBash." % (tokens[0], context_home, context_conn))
            if (tokens[0] in ["casual", "standard"]) and ("GrenadeJump" in tokens):
                _parsewarn(i, "`%s` logic path (from: `%s` to: `%s`) has GrenadeJump." % (tokens[0], context_home, context_conn))
            if (tokens[0] in ["casual", "standard", "expert"]) and ("ChargeFlameBurn" in tokens):
                _parsewarn(i, "`%s` logic path (from: `%s` to: `%s`) has ChargeFlameBurn." % (tokens[0], context_home, context_conn))
            if (tokens[0] in ["casual", "standard"]) and ("ChargeDash" in tokens):
                _parsewarn(i, "`%s` logic path (from: `%s` to: `%s`) has ChargeDash." % (tokens[0], context_home, context_conn))
            if (tokens[0] in ["casual", "standard"]) and ("RocketJump" in tokens):
                _parsewarn(i, "`%s` logic path (from: `%s` to: `%s`) has RocketJump." % (tokens[0], context_home, context_conn))
            if (tokens[0] in ["casual"]) and ("AirDash" in tokens):
                _parsewarn(i, "`%s` logic path (from: `%s` to: `%s`) has GrenadeJump." % (tokens[0], context_home, context_conn))
            if (tokens[0] in ["casual", "standard", "expert"]) and ("TripleJump" in tokens):
                _parsewarn(i, "`%s` logic path (from: `%s` to: `%s`) has TripleJump." % (tokens[0], context_home, context_conn))
            if (tokens[0] in ["casual", "standard", "expert"]) and ("UltraDefense" in tokens):
                _parsewarn(i, "`%s` logic path (from: `%s` to: `%s`) has UltraDefense." % (tokens[0], context_home, context_conn))

            # FIXME Do we want warnings for cases where Abilities with energy cost are listed but don't have energy values?
            
            # Deals with, for example, having both GrenadeJump and Grenade listed.
            for tag in _TAGS_SKILLS.keys():
                if tag in tokens:
                    for skill in _TAGS_SKILLS[tag]:
                        if skill in tokens:
                            _parsewarn(i, "`%s` logic path (from: `%s` to: `%s`) has both %s and %s" % (tokens[0], context_home, context_conn, tag, skill))

            if context_conn[-3:] == "Map" and not has_mapstone:
                _parsewarn(i, "`%s` logic path (from: `%s` to: `%s`) is missing a mapstone requirement" % (tokens[0], context_home, context_conn))
            elif context_conn[-3:] != "Map" and has_mapstone:
                _parsewarn(i, "`%s` logic path (from: `%s` to: `%s`) incorrectly has a mapstone requirement" % (tokens[0], context_home, context_conn))

            contents["homes"][context_home]["conns"][name]["paths"].append((path_tags, ) + tuple(output_tokens))
            
            #print(tokens)
            #print("&&& - " + str((path_tags, ) + tuple(output_tokens)))
            #print()

    connected = {
        "SunkenGladesRunaway": True
    }

    for area in contents["homes"].keys():
        for target in contents["homes"][area]["conns"].keys():
            connected[target] = True
            conn_type = contents["homes"][area]["conns"][target]["type"]
            if conn_type == "pickup" and target in contents["homes"]:
                _parsewarn(0, "home `%s` is connected from home `%s` with type `pickup` (should be `conn`)" % (target, area))
            elif conn_type == "conn" and target in contents["locs"]:
                _parsewarn(0, "pickup location `%s` is connected from `%s` with type `conn` (should be `pickup`)" % (target, area))

    for loc in contents["locs"].keys():
        if loc not in connected:
            _parsewarn(0, "pickup location `%s` is not connected from any home" % loc)

    for home in contents["homes"].keys():
        if home not in connected:
            if not home.endswith("Warp"):
                _parsewarn(0, "home `%s` is not connected from any home!" % home)

    # The existence of paths to homes that don't otherwise exist.
    for area in contents["homes"].keys():
        for target in contents["homes"][area]["conns"].keys():
            conn_type = contents["homes"][area]["conns"][target]["type"]
            if conn_type == "conn":
                if target not in contents["homes"].keys():
                    _parsewarn(0, "Area {} has connection to target {} but that area doesn't exist." % (target, area))


    return contents


def check_for_reverse_connections(contents):
    #            X has a connection to these Y that can be ignored, i.e. we don't need a path back.
    areas_to_skip = {}
    areas_to_skip["GladesFirstDoor"] = ["GladesFirstDoorOpened"]
    areas_to_skip["SunkenGladesRunaway"] = ["DeathGauntletDoor", "GladesFirstDoor", "LowerChargeFlameArea"]
    areas_to_skip["GladesFirstDoorOpened"] = ["SunkenGladesRunaway", "GladesMain"]
    areas_to_skip["DeathGauntletDoor"] = ["DeathGauntletDoorOpened"]
    areas_to_skip["DeathGauntletDoorOpened"] = ["DeathGauntlet", "DeathGauntletMoat", "SunkenGladesRunaway"]
    areas_to_skip["DeathGauntlet"] = ["DeathGauntletDoor", "DeathGauntletMoat"]
    areas_to_skip["GladesMain"] = ["GladesFirstDoor", "SpiritCavernsDoor"]
    areas_to_skip["SpiritCavernsDoor"] = ["SpiritCavernsDoorOpened"]
    areas_to_skip["SpiritCavernsDoorOpened"] = ["LowerSpiritCaverns", "GladesMain"]
    areas_to_skip["LowerSpiritCaverns"] = ["SpiritCavernsDoor"]
    areas_to_skip["UpperSpiritCaverns"] = ["SpiritTreeDoor"]
    areas_to_skip["SpiritTreeDoor"] = ["SpiritTreeDoorOpened"]
    areas_to_skip["SpiritTreeDoorOpened"] = ["SpiritTreeRefined", "UpperSpiritCaverns", ""]
    areas_to_skip["SpiritTreeRefined"] = ["SpiritTreeDoor", "", ""]
    areas_to_skip["SpiderWaterArea"] = ["DeathGauntletRoof", "", ""]
    areas_to_skip["LowerGinsoTree"] = ["R4InnerDoor", "GinsoMiniBossDoor", ""]
    areas_to_skip["GinsoMiniBossDoor"] = ["BashTreeDoorClosed", "", ""]
    areas_to_skip["BashTreeDoorClosed"] = ["BashTreeDoorOpened", "", ""]
    areas_to_skip["BashTreeDoorOpened"] = ["GinsoMiniBossDoor", "BashTree", ""]
    areas_to_skip["BashTree"] = ["BashTreeDoorClosed", "", ""]
    areas_to_skip["UpperGinsoTree"] = ["UpperGinsoDoorClosed", "", ""]
    areas_to_skip["UpperGinsoDoorClosed"] = ["UpperGinsoDoorOpened", "", ""]
    areas_to_skip["UpperGinsoDoorOpened"] = ["GinsoTeleporter", "UpperGinsoTree", ""]
    areas_to_skip["GinsoTeleporter"] = ["UpperGinsoDoorClosed", "", ""]
    areas_to_skip["TopGinsoTree"] = ["GinsoEscape", "", ""]
    areas_to_skip["GinsoEscape"] = ["GinsoEscapeComplete", "", ""]
    areas_to_skip["GinsoEscapeComplete"] = ["Swamp", "SwampKeyDoorPlatform", ""]
    areas_to_skip["GumoHideout"] = ["DoubleJumpKeyDoor", "", ""]
    areas_to_skip["DoubleJumpKeyDoor"] = ["DoubleJumpKeyDoorOpened", "", ""]
    areas_to_skip["SwampKeyDoorPlatform"] = ["SwampKeyDoorOpened", "", ""]
    areas_to_skip["SwampKeyDoorOpened"] = ["RightSwamp", "", ""]
    areas_to_skip["ForlornOrbPossession"] = ["ForlornKeyDoor", "", ""]
    areas_to_skip["ForlornMapArea"] = ["ForlornKeyDoor", "", ""]
    areas_to_skip["ForlornLaserRoom"] = ["ForlornStompDoor", "", ""]
    areas_to_skip["ForlornStompDoor"] = ["RightForlorn", "", ""]
    areas_to_skip["LowerSorrow"] = ["LeftSorrowLowerDoor", "", ""]
    areas_to_skip["SorrowMapstoneArea"] = ["HoruInnerDoor", "", ""]
    areas_to_skip["LeftSorrowLowerDoor"] = ["LeftSorrow", "", ""]
    areas_to_skip["MistyPreClimb"] = ["ForlornTeleporter", "RightForlorn", ""]
    areas_to_skip["GladesMainAttic"] = ["LowerChargeFlameArea", "", ""]
    areas_to_skip["RazielNoArea"] = ["GumoHideout", "", ""]
    areas_to_skip["SwampTeleporter"] = ["OuterSwampMortarAbilityCellLedge", "", ""]
    areas_to_skip["OuterSwampAbilityCellNook"] = ["InnerSwampSkyArea", "", ""]
    areas_to_skip["LowerLeftGumoHideout"] = ["LowerBlackroot", "", ""]
    areas_to_skip["HoruR1CutsceneTrigger"] = ["LowerGinsoTree", "", ""]
    areas_to_skip["MistyPreMortarCorridor"] = ["RightForlorn", "", ""]
    areas_to_skip[""] = ["", "", ""]
       
    for area in contents["homes"].keys():
        for target in contents["homes"][area]["conns"].keys():
            conn_type = contents["homes"][area]["conns"][target]["type"]
            if conn_type == "conn":
                if area not in contents["homes"][target]["conns"].keys():
                    if target not in areas_to_skip.get(area, []):
                        print("Area {} has connection to target {} that doesn't have a connection back.".format(area, target)) 



if __name__ == "__main__":
    import sys
    fn = sys.argv[1]
    ori_load_file(fn, True)
    #contents = ori_load_file(fn, True)
    #check_for_reverse_connections(contents)
    pp = pprint.PrettyPrinter(indent=4)
    #pp.pprint(contents)
