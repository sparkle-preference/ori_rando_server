#!/usr/bin/env python
import argparse, time
import logging as log
import re
import pickle
from collections import OrderedDict, defaultdict, Counter

from util import enums_from_strlist, get_preset_from_paths
from enums import MultiplayerGameType, ShareType, Variation, LogicPath, KeyMode, PathDifficulty, presets
from seedbuilder.generator import SeedGenerator

FLAGLESS_VARS = [Variation.WARMTH_FRAGMENTS, Variation.WORLD_TOUR]
first_line_pattern = re.compile(r"(\d+): (\[[^]]+\])")
forced_pickup_pattern = re.compile(r".*forced pickup.*\[([^]]+)\]")
normal_line_pattern = re.compile(r" *(\w+) from (\w+)")

def vals(enumType):
    return [v.value for v in list(enumType.__members__.values())]

def defaultgroup():
    return {"items": Counter(), "forced": Counter(), "locs": 0, "seeds": 0, "force": 0}

class CLIMultiOptions(object):
    def __init__(self, mode=MultiplayerGameType.SIMUSOLO, shared=[], enabled=False, cloned=False, hints=False, teams={}):
        self.mode = mode
        self.shared = shared
        self.enabled = enabled
        self.cloned = cloned
        self.hints = hints
        self.teams = teams

class CLISeedParams(object):
    def __init__(self):
        pass

    def put(self):
        pass # this is stupid as fuck but it does work.

    def from_cli(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--output-dir", help="directory to put the seeds in", type=str, default=".")
        parser.add_argument("--output-number", help="number to be placed in randomizer0.dat", type=str, default="0")
        parser.add_argument("--preset", help="Choose a preset group of paths for the generator to use")
        parser.add_argument("--custom-logic", help="Customize paths that the generator will use, comma-separated: %s" % ", ".join(vals(LogicPath)))
        parser.add_argument("--seed", help="Seed value (default 'test')", type=str, default="test")
        parser.add_argument("--keymode", help="""Changes how the dungeon keys (The Water Vein, Gumon Seal, and Sunstone) are handled:
        Default: The dungeon keys are placed without any special consideration.
        Clues: For each 3 trees visited, the zone of a random dungeon key will be revealed
        Shards: The dungeon keys will be awarded after 3/5 shards are found
        LimitKeys: The Water Vein, Gumon Seal, and Sunstone will only appear at skill trees or event sources
        Free: The dungeon keys are given to the player upon picking up the first Energy Cell.
        """, type=str)
        # variations
        parser.add_argument("--ohko", help="Enable one-hit-ko mode", action="store_true")
        parser.add_argument("--zeroxp", help="Enable 0xp mode", action="store_true")       
        parser.add_argument("--starved", help="Reduces the rate at which skills will appear when not required to advance", action="store_true")
        parser.add_argument("--tp-starved", help="Reduces the rate at which teleporters will appear early game when not required to advance", action="store_true")
        parser.add_argument("--wall-starved", help="Reduces the rate at which WallJump and Climb will appear early game when not required to advance", action="store_true")
        parser.add_argument("--grenade-starved", help="Reduces the rate at which Grenade will appear early and when not required to advance", action="store_true")
        parser.add_argument("--strict-mapstones", help="Require a mapstone to be placed when a map monument becomes accessible", action="store_true")
        parser.add_argument("--non-progressive-mapstones", help="Map Stones will retain their behaviour from before v1.2, having their own unique drops", action="store_true")
        # goal modes
        parser.add_argument("--force-trees", help="Prevent Ori from entering the final escape room until all skill trees have been visited", action="store_true")
        parser.add_argument("--force-mapstones", help="Prevent Ori from entering the final escape room until all mapstone altars have been activated", action="store_true")
        parser.add_argument("--world-tour", help="Prevent Ori from entering the final escape until collecting one relic from each of the zones in the world. Recommended default: 8", type=int)
        parser.add_argument("--warmth-frags", help="Prevent Ori from entering the final escape until collecting some number of warmth fragments. Recommended default: 40", type=int)
        parser.add_argument("--entrance", help="Randomize entrances", action="store_true")
        parser.add_argument("--closed-dungeons", help="deactivate open mode within dungeons", action="store_true")
        parser.add_argument("--open-world", help="Activate open mode on the world map", action="store_true")
        parser.add_argument("--easy", help="Add an extra copy of double jump, bash, stomp, glide, charge jump, dash, grenade, water, and wind", action="store_true")
        parser.add_argument("--warps-instead-of-tps", help="Replace up to X teleporters with warps to those areas.", type=int)
        parser.add_argument("--in-logic-warps", help="Warps will be in logic, so going to the warp's target is expected.", action="store_true")
        parser.add_argument("--warp-count", help="Ensure you get X random warps.", type=int)
        parser.add_argument("--start", help="Sets start location, e.g. random or glades.", type=str, default="Glades")
        parser.add_argument("--starting-health", help="Sets starting health to X, note: X=5 would give you 2 HC at spawn.", type=int)
        parser.add_argument("--starting-energy", help="Sets starting energy to X, note: X=5 would give you 4-5 EC at spawn.", type=int)
        parser.add_argument("--starting-skills", help="Sets how many skills we start with.", type=str)
        parser.add_argument("--spawn-weights", help="For random spawn, set custom weights for starting teleporters. Format: Glades=.5,Swamp=1.0,Sorrow=2.0")

        parser.add_argument("--goal-mode-finish", help="Skips the final escape when goal modes are done.", action="store_true")
        parser.add_argument("--no-tps", help="Removes teleporters from the item pool.", action="store_true")      
        # item pools.
        parser.add_argument("--competitive", help="Competitive item pool, which is standard without Ginso and Horu teleporters.", action="store_true")
        parser.add_argument("--bonus-lite", help='Bonus Lite item pool, which is extra bonus without bonus skills.', action="store_true")
        parser.add_argument("--bonus-pickups", help="Adds some extra bonus pickups not balanced for competitive play", action="store_true")
        parser.add_argument("--hard", help="Enable hard mode", action="store_true")
        # misc
        parser.add_argument("--verbose-paths", help="print every logic path in the flagline for debug purposes", action="store_true")
        parser.add_argument("--exp-pool", help="Size of the experience pool (default 10000)", type=int, default=10000)
        parser.add_argument("--extra-frags", help="""Sets the number of extra warmth fragments. Total frag number is still the value passed to --warmth-frags;
        --warmth-frags 40 --extra-frags 10 will place 40 total frags, 30 of which will be required to finish""", type=int, default=10)
        parser.add_argument("--prefer-path-difficulty", help="Increase the chances of putting items in more convenient (easy) or less convenient (hard) locations", choices=["easy", "hard"])
        parser.add_argument("--balanced", help="Reduce the value of newly discovered locations for progression placements", action="store_true")
        parser.add_argument("--force-cells", help="Force health and energy cells to appear every N pickups, if they don't randomly", type=int, default=256)
        parser.add_argument("--verbose-spoiler", help="show everything in the spoiler", action="store_true")
        # anal TODO: IMPL
        parser.add_argument("--analysis", help="Report stats on the skill order for all seeds generated", action="store_true")
        parser.add_argument("--loc-analysis", help="Report stats on where skills are placed over multiple seeds", action="store_true")
        parser.add_argument("--count", help="Number of seeds to generate (default 1)", type=int, default=1)
        # sync
        parser.add_argument("--players", help="Player count for paired randomizer", type=int, default=1)
        parser.add_argument("--tracking", help="Place a sync ID in a seed for tracking purposes", action="store_true")
        parser.add_argument("--sync-id", help="Team identifier number for paired randomizer", type=int)
        parser.add_argument("--shared-items", help="What will be shared by sync, comma-separated: skills,worldevents,misc,teleporters,upgrades", default="skills,worldevents")
        parser.add_argument("--share-mode", help="How the server will handle shared pickups, one of: shared,swap,split,none", default="shared")
        parser.add_argument("--cloned", help="Make a split cloned seed instead of seperate seeds", action="store_true")
        parser.add_argument("--teams", help="Cloned seeds only: define teams. Format: 1|2,3,4|5,6. Each player must appear once", type=str)
        parser.add_argument("--hints", help="Cloned seeds only: display a hint with the item category on a shared location instead of 'Warmth Returned'", action="store_true")
        parser.add_argument("--do-reachability-analysis", help="Analyze how many locations are opened by various progression items in various inventory states", action="store_true")
        parser.add_argument("--areas-ori-path", help="Path to areas.ori. Will search next to generator if omitted.", type=str)
        parser.add_argument("--keysanity", help="Keysanity mode: keys only belong to one door", action="store_true")
        args = parser.parse_args()

        """
        path_diff = property(get_pathdiff, set_pathdiff)
        exp_pool = ndb.IntegerProperty(default=10000)
        balanced = ndb.BooleanProperty(default=True)
        tracking = ndb.BooleanProperty(default=True)
        players = ndb.IntegerProperty(default=1)
        sync = ndb.LocalStructuredProperty(MultiplayerOptions)
        frag_count = ndb.IntegerProperty(default=40)
        frag_extra = ndb.IntegerProperty(default=10)
        cell_freq = ndb.IntegerProperty(default=256)
        """
        self.seed = args.seed
        self.areas_ori_path = args.areas_ori_path or ""
        if args.preset:
            self.logic_paths = presets[args.preset.capitalize()]
        elif args.custom_logic:
            self.logic_paths = enums_from_strlist(LogicPath, args.custom_logic.split(","))
        else:
            self.logic_paths = presets["Standard"]
        self.key_mode = KeyMode.mk(args.keymode) or KeyMode.NONE
        # variations (help)
        varMap = {
            "zeroxp": "0XP", "non_progressive_mapstones": "NonProgressMapStones", "ohko": "OHKO", "force_trees": "ForceTrees", "starved": "Starved", "keysanity": "Keysanity",
            "force_mapstones": "ForceMaps", "entrance": "Entrance", "open_world": "OpenWorld", "easy": "DoubleSkills", "strict_mapstones": "StrictMapstones",
            "warmth_frags": "WarmthFrags", "world_tour": "WorldTour", "closed_dungeons": "ClosedDungeons", "tp_starved": "TPStarved", "wall_starved": "WallStarved",
            "warps_instead_of_tps": "WarpsInsteadOfTPs", "in_logic_warps": "InLogicWarps", "warp_count": "WarpCount", "starting_health": "StartingHealth",
            "starting_energy": "StartingEnergy", "starting_skills": "StartingSkills", "grenade_starved": "GrenadeStarved", "goal_mode_finish": "GoalModeFinish",
            "no_tps": "NoTPs", "competitive": "Competitive", "bonus_lite": "BonusLite", "hard": "Hard", "bonus_pickups": "BonusPickups"
        }
        self.variations = []
        for argName, flagStr in varMap.items():
            if getattr(args, argName, False):
                v = Variation.mk(flagStr)
                if v:
                    self.variations.append(v)
                else:
                    log.warning("Failed to make a Variation from %s" % flagStr)
        if Variation.WORLD_TOUR in self.variations:
            self.relic_count = args.world_tour
        if Variation.WARMTH_FRAGMENTS in self.variations:
            self.frag_count = args.warmth_frags
            self.frag_extra = args.extra_frags
        if Variation.WARPS_INSTEAD_OF_TPS in self.variations:
            self.warps_instead_of_tps = args.warps_instead_of_tps
        if Variation.WARP_COUNT in self.variations:
            self.warp_count = args.warp_count
        self.start = args.start
        self.spawn = self.start if self.start != "Random" else ""

        if Variation.STARTING_HEALTH in self.variations:
            self.starting_health = args.starting_health
        if Variation.STARTING_ENERGY in self.variations:
            self.starting_energy = args.starting_energy
        if Variation.STARTING_SKILLS in self.variations:
            self.starting_skills = args.starting_skills
        #misc
        self.exp_pool = args.exp_pool
        if args.prefer_path_difficulty:
            if args.prefer_path_difficulty == "easy":
                self.path_diff = PathDifficulty.EASY
            else:
                self.path_diff = PathDifficulty.HARD
        else:
            self.path_diff = PathDifficulty.NORMAL
        if args.spawn_weights:
            spawn_weights = OrderedDict([
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
            for pair in args.spawn_weights.split(","):
                try:
                    zone, _, rawWeight = pair.partition("=")
                    spawn_weights[zone] = float(rawWeight)
                except Exception as e:
                    print("Bad spawn weight argument '%s' will be ignored" % pair)
            self.spawn_weights = list(spawn_weights.values())
            print (self.spawn_weights)
        else:
            self.spawn_weights = []
        self.balanced = args.balanced or False
        self.cell_freq = args.force_cells
        self.players = args.players
        self.tracking = args.tracking or False
        self.sync = CLIMultiOptions()
        
        if Variation.EXTRA_BONUS_PICKUPS in self.variations:
            self.pool_preset = "Extra Bonus"
            self.item_pool = {
                "TP|Grove": [1],
                "TP|Swamp": [1],
                "TP|Grotto": [1],
                "TP|Valley": [1],
                "TP|Sorrow": [1],
                "TP|Ginso": [1],
                "TP|Horu": [1],
                "TP|Forlorn": [1],
                "TP|Blackroot": [1],
                "HC|1": [12],
                "EC|1": [15],
                "AC|1": [33],
                "RB|0": [3],
                "RB|1": [3],
                "RB|6": [5],
                "RB|9": [1],
                "RB|10": [1],
                "RB|11": [1],
                "RB|12": [3],
                "RB|37": [3],
                "RB|13": [3],
                "RB|15": [3],
                "RB|31": [1],
                "RB|32": [1],
                "RB|33": [3],
                "RB|36": [1],
                "BS|*": [4],
                "WP|*": [4, 8],
            }
        elif Variation.BONUS_LITE in self.variations:
            self.pool_preset = "Bonus Lite"
            self.item_pool = {
                "TP|Grove": [1],
                "TP|Swamp": [1],
                "TP|Grotto": [1],
                "TP|Valley": [1],
                "TP|Sorrow": [1],
                "TP|Ginso": [1],
                "TP|Horu": [1],
                "TP|Forlorn": [1],
                "TP|Blackroot": [1],
                "HC|1": [12],
                "EC|1": [15],
                "AC|1": [33],
                "RB|0": [3],
                "RB|1": [3],
                "RB|6": [5],
                "RB|9": [1],
                "RB|10": [1],
                "RB|11": [1],
                "RB|12": [3],
                "RB|37": [3],
                "RB|13": [3],
                "RB|15": [3],
                "RB|31": [1],
                "RB|32": [1],
                "RB|33": [3],
                "RB|36": [1],
                "WP|*": [4, 8],
            }
        elif Variation.COMPETITIVE in self.variations:
            self.pool_preset = "Competitive"
            self.item_pool = {
                "TP|Grove": [1],
                "TP|Swamp": [1],
                "TP|Grotto": [1],
                "TP|Valley": [1],
                "TP|Sorrow": [1],
                "TP|Forlorn": [1],
                "HC|1": [12],
                "EC|1": [15],
                "AC|1": [33],
                "RB|0": [3],
                "RB|1": [3],
                "RB|6": [3],
                "RB|9": [1],
                "RB|10": [1],
                "RB|11": [1],
                "RB|12": [1],
                "RB|13": [3],
                "RB|15": [3],
            }
        elif Variation.HARDMODE in self.variations:
            self.pool_preset = "Hard"
            self.item_pool = {
                "TP|Grove": [1],
                "TP|Swamp": [1],
                "TP|Grotto": [1],
                "TP|Valley": [1],
                "TP|Sorrow": [1],
                "TP|Ginso": [1],
                "TP|Horu": [1],
                "TP|Forlorn": [1],
                "EC|1": [4],
            }
        else:
            self.pool_preset = "Standard"
            self.item_pool = {
                "TP|Grove": [1],
                "TP|Swamp": [1],
                "TP|Grotto": [1],
                "TP|Valley": [1],
                "TP|Sorrow": [1],
                "TP|Ginso": [1],
                "TP|Horu": [1],
                "TP|Forlorn": [1],
                "HC|1": [12],
                "EC|1": [15],
                "AC|1": [33],
                "RB|0": [3],
                "RB|1": [3],
                "RB|6": [3],
                "RB|9": [1],
                "RB|10": [1],
                "RB|11": [1],
                "RB|12": [1],
                "RB|13": [3],
                "RB|15": [3],
            }

        if self.players > 1 or self.tracking:
            self.sync_id = args.sync_id or int(time.time() * 1000 % 1073741824)
        if self.players > 1:
            self.sync.enabled = True
            self.sync.mode = MultiplayerGameType.mk(args.share_mode) or MultiplayerGameType.SIMUSOLO
            self.sync.shared = enums_from_strlist(ShareType, args.shared_items.split(","))
            self.sync.cloned = args.cloned or False
            if self.sync.cloned:
                self.sync.hints = args.hints or False
                if args.teams:
                    cnt = 1
                    self.sync.teams = {}
                    for team in args.teams.split("|"):
                        self.sync.teams[cnt] = [int(p) for p in team.split(",")]
                        cnt += 1

        self.verbose_spoiler = args.verbose_spoiler
        # todo: respect these LMAO
        self.do_analysis = args.analysis
        self.do_loc_analysis = args.loc_analysis
        self.repeat_count = args.count

        base_seed = self.seed[:]
        if self.do_analysis:
            key_items = ["WallJump", "ChargeFlame", "DoubleJump", "Bash", "Stomp", "Glide", "Climb", "ChargeJump", "Dash", "Grenade", "GinsoKey", "ForlornKey", "HoruKey", "Water", "Wind", "TPForlorn", "TPGrotto", "TPSorrow", "TPGrove", "TPSwamp", "TPValley", "TPGinso", "TPHoru"]
            info_by_group = defaultdict(defaultgroup)

        if self.do_loc_analysis:
            self.locationAnalysis = {}
            self.itemsToAnalyze = {
                "WallJump": 0,
                "ChargeFlame": 0,
                "DoubleJump": 0,
                "Bash": 0,
                "Stomp": 0,
                "Glide": 0,
                "Climb": 0,
                "ChargeJump": 0,
                "Dash": 0,
                "Grenade": 0,
                "GinsoKey": 0,
                "ForlornKey": 0,
                "HoruKey": 0,
                "Water": 0,
                "Wind": 0,
                "WaterVeinShard": 0,
                "GumonSealShard": 0,
                "SunstoneShard": 0,
                "TPForlorn": 0,
                "TPGrotto": 0,
                "TPSorrow": 0,
                "TPGrove": 0,
                "TPSwamp": 0,
                "TPValley": 0,
                "TPGinso": 0,
                "TPHoru": 0,
                "Relic": 0
            }
            for i in range(1, 10):
                self.locationAnalysis["MapStone " + str(i)] = self.itemsToAnalyze.copy()
                self.locationAnalysis["MapStone " + str(i)]["Zone"] = "MapStone"

        for count in range(0, self.repeat_count):

            if self.repeat_count > 1:
                self.seed = "%s_%s" % (base_seed, count)

            if self.do_loc_analysis:
                print(self.seed)

            sg = SeedGenerator()

            if args.do_reachability_analysis:
                sg.do_reachability_analysis(self)
                return

            raw = sg.setSeedAndPlaceItems(self, preplaced={})
            seeds = []
            spoilers = []
            if not raw:
                    log.error("Couldn't build seed!")
                    if self.do_loc_analysis:
                        continue
                    return
            player = 0
            for player_raw in raw:
                player += 1
                seed, spoiler = tuple(player_raw)
                if self.tracking:
                    seed = "Sync%s.%s," % (self.sync_id, player) + seed
                if args.output_number != "0":
                    seedfile = "randomizer" + args.output_number + "_%s.dat" % player
                    spoilerfile = "spoiler" + args.output_number + "_%s.txt" % player                    
                else:
                    seedfile = "randomizer_%s.dat" % player
                    spoilerfile = "spoiler_%s.txt" % player
                if self.players == 1:
                    if args.output_number != "0":
                        seedfile = "randomizer" + args.output_number + ".dat"
                        spoilerfile = "spoiler" + args.output_number + ".txt"
                    else:
                        seedfile = "randomizer" + str(count) + ".dat"
                        spoilerfile = "spoiler" + str(count) + ".txt"

                if not self.do_analysis and not self.do_loc_analysis:
                    with open(args.output_dir+"/"+seedfile, 'w') as f:
                        f.write(seed)
                    with open(args.output_dir+"/"+spoilerfile, 'w') as f:
                        f.write(spoiler)
                if self.do_analysis:
                    i = 0
                    for spoiler_line in spoiler.split("\n"):
                        fl = first_line_pattern.match(spoiler_line)
                        if fl:
                            raw_group, raw_locs = fl.group(1,2)
                            i = int(raw_group)
                            info_by_group[i]["seeds"] += 1
                            info_by_group[i]["locs"] += raw_locs.count(",") + 1
                            continue
                        fp = forced_pickup_pattern.match(spoiler_line)
                        if fp:
                            info_by_group[i]["force"] += 1
                            for raw in fp.group(1).split(","):
                                info_by_group[i]["forced"][raw.strip(" '")] += 1
                            continue
                        nl = normal_line_pattern.match(spoiler_line)
                        if nl:
                            item = nl.group(1)
                            if item in key_items:
                                info_by_group[i]["items"][item] += 1

        if self.do_analysis:
#            output = open("analysis.csv", 'w')
#            output.write("Location,Zone,WallJump,ChargeFlame,DoubleJump,Bash,Stomp,Glide,Climb,ChargeJump,Dash,Grenade,GinsoKey,ForlornKey,HoruKey,Water,Wind,WaterVeinShard,GumonSealShard,SunstoneShard,TPGrove,TPGrotto,TPSwamp,TPValley,TPSorrow,TPGinso,TPForlorn,TPHoru,Relic\n")
            for i, group in info_by_group.items():
                seeds = float(group["seeds"])
                print("%d (%d): " % (i, int(seeds)))
                print("\tkey items: [", end=" ")
                for item, count in group["items"].items():
                    print('%s: %02.2f%%,' % (item, 100*float(count)/seeds), end=" ")
                print("]\n\tforced: [", end=" ")
                for item, count in group["forced"].items():
                    print('%s: %02.2f%%,' % (item, 100*float(count)/float(group["force"])), end=" ")
                print("]\n\taverage locs", float(group['locs'])/seeds)
            with open("anal.pickle", 'w') as out_file:
                pickle.dump(info_by_group, out_file)
            with open("analysis.csv", 'w') as out_file:
                out_file.write("Group,Seeds,Forced,Locs,WallJump,ChargeFlame,DoubleJump,Bash,Stomp,Glide,Climb,ChargeJump,Dash,Grenade,GinsoKey,ForlornKey,HoruKey,Water,Wind,TPGrove,TPGrotto,TPSwamp,TPValley,TPSorrow,TPGinso,TPForlorn,TPHoru,WallJump,ChargeFlame,DoubleJump,Bash,Stomp,Glide,Climb,ChargeJump,Dash,Grenade,GinsoKey,ForlornKey,HoruKey,Water,Wind,TPGrove,TPGrotto,TPSwamp,TPValley,TPSorrow,TPGinso,TPForlorn,TPHoru,KS,EC,HC,MS,AC\n")
                for i, group in info_by_group.items():
                    seeds = float(group["seeds"])
                    line = [i, int(seeds), int(group["force"]), "%02.2f" % (float(group["locs"])/seeds)]
                    for key_item in ["WallJump", "ChargeFlame", "DoubleJump", "Bash", "Stomp", "Glide", "Climb", "ChargeJump", "Dash", "Grenade", "GinsoKey", "ForlornKey", "HoruKey", "Water", "Wind","TPGrove","TPGrotto","TPSwamp","TPValley","TPSorrow","TPGinso","TPForlorn","TPHoru"]:
                        line.append("%02.2f%%" % (100*float(group["items"][key_item])/seeds))
                    for forced_prog in ["WallJump", "ChargeFlame", "DoubleJump", "Bash", "Stomp", "Glide", "Climb", "ChargeJump", "Dash", "Grenade", "GinsoKey", "ForlornKey", "HoruKey", "Water", "Wind","TPGrove","TPGrotto","TPSwamp","TPValley","TPSorrow","TPGinso","TPForlorn","TPHoru","KS","EC","HC","MS","AC"]:
                        line.append("%02.2f%%" % (100*float(group["forced"][forced_prog])/float(group["force"]) if group["forced"][forced_prog] else 0))
                    out_file.write(",".join([str(x) for x in line])+'\n')
        if self.do_loc_analysis:
            output = open("analysis.csv", 'w')
            output.write("Group,WallJump,ChargeFlame,DoubleJump,Bash,Stomp,Glide,Climb,ChargeJump,Dash,Grenade,Water,Wind,WaterVeinShard,GumonSealShard,SunstoneShard,TPGrove,TPGrotto,TPSwamp,TPValley,TPSorrow,TPGinso,TPForlorn,TPHoru,\n")
            for key in self.locationAnalysis.keys():
                line = key + ","
                line += str(self.locationAnalysis[key]["Zone"]) + ","
                line += str(self.locationAnalysis[key]["WallJump"]) + ","
                line += str(self.locationAnalysis[key]["ChargeFlame"]) + ","
                line += str(self.locationAnalysis[key]["DoubleJump"]) + ","
                line += str(self.locationAnalysis[key]["Bash"]) + ","
                line += str(self.locationAnalysis[key]["Stomp"]) + ","
                line += str(self.locationAnalysis[key]["Glide"]) + ","
                line += str(self.locationAnalysis[key]["Climb"]) + ","
                line += str(self.locationAnalysis[key]["ChargeJump"]) + ","
                line += str(self.locationAnalysis[key]["Dash"]) + ","
                line += str(self.locationAnalysis[key]["Grenade"]) + ","
                line += str(self.locationAnalysis[key]["GinsoKey"]) + ","
                line += str(self.locationAnalysis[key]["ForlornKey"]) + ","
                line += str(self.locationAnalysis[key]["HoruKey"]) + ","
                line += str(self.locationAnalysis[key]["Water"]) + ","
                line += str(self.locationAnalysis[key]["Wind"]) + ","
                line += str(self.locationAnalysis[key]["WaterVeinShard"]) + ","
                line += str(self.locationAnalysis[key]["GumonSealShard"]) + ","
                line += str(self.locationAnalysis[key]["SunstoneShard"]) + ","
                line += str(self.locationAnalysis[key]["TPGrove"]) + ","
                line += str(self.locationAnalysis[key]["TPGrotto"]) + ","
                line += str(self.locationAnalysis[key]["TPSwamp"]) + ","
                line += str(self.locationAnalysis[key]["TPValley"]) + ","
                line += str(self.locationAnalysis[key]["TPSorrow"]) + ","
                line += str(self.locationAnalysis[key]["TPGinso"]) + ","
                line += str(self.locationAnalysis[key]["TPForlorn"]) + ","
                line += str(self.locationAnalysis[key]["TPHoru"]) + ","
                line += str(self.locationAnalysis[key]["Relic"])

                output.write(line + "\n")

    def flag_line(self, verbose_paths=False):
        flags = []
        if verbose_paths:
            flags.append("lps=%s" % "+".join([lp.capitalize() for lp in self.logic_paths]))
        else:
            flags.append(get_preset_from_paths(presets, self.logic_paths))
        flags.append(self.key_mode)
        if Variation.WARMTH_FRAGMENTS in self.variations:
            flags.append("Frags/%s/%s" % (self.frag_count - self.frag_extra, self.frag_count))
        if Variation.WORLD_TOUR in self.variations:
            flags.append("WorldTour=%s" % self.relic_count)
        flags += [v.value for v in self.variations if v not in FLAGLESS_VARS]
        if self.path_diff != PathDifficulty.NORMAL:
            flags.append("prefer_path_difficulty=%s" % self.path_diff.value)
        if self.sync.enabled:
            flags.append("mode=%s" % self.sync.mode.value)
            if self.sync.shared:
                flags.append("shared=%s" % "+".join(self.sync.shared))
        if self.balanced:
            flags.append("balanced")
        return "%s|%s" % (",".join(flags), self.seed)


if __name__ == "__main__":
    params = CLISeedParams()
    params.from_cli()
