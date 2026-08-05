"""Ori DE Randomizer -- Archipelago world for orirando.com seeds.

This world does NOT roll its own seed: orirando.com generates the Ori seed,
reserves K locations for AP fill, exports K items to the AP pool, and emits
a paired yaml whose `orirando` blob carries the seed's config (logic
pathsets, variations, reserved locations, local progression placements,
graph overrides, goal). Local progression is pre-placed here as locked
items so AP's reachability state simulates the Ori seed exactly.
"""
import json
import logging
import pkgutil
from collections import Counter

from BaseClasses import Item, ItemClassification, Location, Region, Tutorial
from worlds.AutoWorld import WebWorld, World

from .options import OriDEOptions
from .rules import RuleCompiler, make_rule
from .version import data_version_problem

# pre-release working name; safe to change until first public apworld
# release. Renaming it also renames the game-info doc: WebHost looks for
# docs/en_<secure_filename(game)>.md, i.e. docs/en_Ori_DE_Rando.md today.
GAME_NAME = "Ori DE Rando"

logger = logging.getLogger("oride")


def _load(name):
    # a packaged .apworld is a zip: open() on a __file__ path inside it finds
    # nothing, pkgutil goes through the loader either way
    return json.loads(pkgutil.get_data(__name__, "data/" + name).decode("utf-8"))


ITEMS = _load("items.json")
LOCATIONS = _load("locations.json")
GRAPH = _load("graph.json")

ITEM_TABLE = {item["name"]: item for item in ITEMS}
LOC_TABLE = {loc["name"]: loc for loc in LOCATIONS}

# cells count toward Health=/Energy=/Ability= requirements, so everything
# except the bonus grab-bag is progression. upgrades/experience/warps are
# filler: no compiled rule names one. Warps in particular are filler even
# under the InLogicWarps variation -- the graph shipped here has no warp
# edges at all, which under-models reach and so stays conservative.
PROGRESSION_CATEGORIES = {"skills", "events", "teleporters", "cells", "stones"}

# Warmth Returned is a no-op troll pickup (game-end triggers are positional;
# no logic path requires it) -- exportable, but never progression
FILLER_OVERRIDES = {"Warmth Returned"}

MAPSTONE_TURNIN_NAMES = ["MS%d" % n for n in range(1, 10)]


class OriDEItem(Item):
    game = GAME_NAME


class OriDELocation(Location):
    game = GAME_NAME


class OriDEWeb(WebWorld):
    theme = "grass"
    # every option lives in the seed rolled on orirando.com; the yaml is
    # downloaded, never hand-written, so send people there instead of to a
    # player-options form (the FF1 pattern)
    options_page = "https://orirando.com/"
    game_info_languages = ["en"]  # -> docs/en_Ori_DE_Rando.md
    tutorials = [Tutorial(
        "Multiworld Setup Guide",
        "A guide to playing Ori DE Rando in an Archipelago multiworld.",
        "English",
        "setup_en.md",
        "setup/en",
        ["orirando.com"],
    )]


class OriDEWorld(World):
    """Ori and the Blind Forest: Definitive Edition randomizer (orirando.com).
    Seeds are rolled on orirando.com, which emits the paired yaml for this
    world; item delivery in game rides the orirando multiworld netcode."""
    game = GAME_NAME
    web = OriDEWeb()
    options_dataclass = OriDEOptions
    options: OriDEOptions
    item_name_to_id = {item["name"]: item["ap_id"] for item in ITEMS}
    location_name_to_id = {loc["name"]: loc["ap_id"] for loc in LOCATIONS}
    origin_region_name = "Menu"

    def generate_early(self):
        cfg = dict(self.options.orirando.value)
        if not cfg:
            raise Exception(
                "%s (%s): empty orirando data. Roll a seed with the Archipelago "
                "game mode on orirando.com and use the yaml it emits." %
                (self.player_name, GAME_NAME))
        # ahead of every table read: a yaml from a newer server otherwise
        # dies as a KeyError on a name this build never heard of
        problem = data_version_problem(cfg)
        if problem:
            raise Exception("%s (%s): %s" % (self.player_name, GAME_NAME, problem))
        self.cfg = cfg
        self.reserved = list(cfg.get("reserved_locations", []))
        self.exported = dict(cfg.get("exported_items", {}))
        self.local_progression = dict(cfg.get("local_progression", {}))
        # a K-world orirando game splits items across worlds, so one world's
        # counts differ by design; only the room-wide totals have to match,
        # and AP's own fill is what enforces those
        exported_total = sum(self.exported.values())
        if exported_total != len(self.reserved):
            logger.info(
                "%s (%s): %d exported items, %d reserved locations "
                "(cross-world drift, balanced across the orirando game)",
                self.player_name, GAME_NAME, exported_total, len(self.reserved))
        for name in self.exported:
            if name not in ITEM_TABLE:
                raise Exception("%s (%s): unknown exported item %r" %
                                (self.player_name, GAME_NAME, name))
        if "Keystone" in self.exported:
            # generic KS are consumable: the per-door thresholds these rules
            # compile to are only sound while the generator's own cumulative
            # supply invariant places them locally. Zone keystones (keysanity)
            # export fine -- one key type per door, thresholds exact.
            raise Exception("%s (%s): generic Keystones cannot be exported to "
                            "the AP pool" % (self.player_name, GAME_NAME))
        self.compiler = RuleCompiler(cfg, logger.warning)

    def create_regions(self):
        player = self.player
        regions = {"Menu": Region("Menu", player, self.multiworld)}
        for home in GRAPH["homes"]:
            regions[home] = Region(home, player, self.multiworld)
        self.multiworld.regions.extend(regions.values())

        spawn = self.cfg.get("spawn", "SunkenGladesRunaway")
        regions["Menu"].connect(regions[spawn])

        reserved = set(self.reserved)
        placed = set()
        pedestal_accesses = {}  # pedestal -> [(region, rule)]
        pickup_accesses = {}  # location -> [(home, needs)]
        overrides = {(o["home"], o["target"]): o
                     for o in self.cfg.get("graph_overrides", [])}

        for home, conns in GRAPH["homes"].items():
            for target, conn in conns.items():
                paths = conn["paths"]
                override = overrides.get((home, target))
                if override:
                    if override.get("remove"):
                        continue
                    paths = paths + override.get("add_paths", [])
                needs = self.compiler.compile_paths(paths)
                if conn["type"] == "conn":
                    if not needs:
                        continue  # edge dead under this seed's logic
                    regions[home].connect(
                        regions[target], "%s -> %s" % (home, target),
                        make_rule(needs, player))
                    continue
                # pickup node
                if conn.get("item") == "MapStone":
                    pedestal_accesses.setdefault(target, []).append(
                        (regions[home], make_rule(needs, player)))
                    continue
                pickup_accesses.setdefault(target, []).append((home, needs))

        for target, accesses in pickup_accesses.items():
            if len(accesses) == 1:
                home, needs = accesses[0]
                self._attach_location(regions[home], target, needs, placed)
                continue
            if target not in reserved | set(self.local_progression):
                continue
            # multiple approach regions: OR them via a node region
            node = Region(target, player, self.multiworld)
            self.multiworld.regions.append(node)
            for home, needs in accesses:
                if not needs:
                    continue  # approach dead under this seed's logic
                regions[home].connect(node, "%s -> %s" % (home, target),
                                      make_rule(needs, player))
            self._attach_location(node, target, None, placed)

        # locations orirando fills but areas.ori doesn't model (escapes,
        # first EC): the yaml supplies their region + requirements
        for name, extra in self.cfg.get("extra_locations", {}).items():
            needs = self.compiler.compile_paths(extra.get("paths", [{"tags": [], "reqs": []}]))
            self._attach_location(regions[extra["region"]], name, needs, placed)

        # mapstone turn-ins: MSn needs bump(n) Mapstones and n usable pedestals
        for n, name in enumerate(MAPSTONE_TURNIN_NAMES, start=1):
            if name not in set(self.reserved) | set(self.local_progression):
                continue
            rule = self._mapstone_rule(n, pedestal_accesses)
            self._attach_location(regions[spawn], name, None, placed, rule=rule)

        missing = (reserved | set(self.local_progression)) - placed
        if missing:
            raise Exception("%s (%s): locations not in graph and not in "
                            "extra_locations: %s" %
                            (self.player_name, GAME_NAME, sorted(missing)))

        goal_region = self.cfg.get("goal", {}).get("region")
        if not goal_region or goal_region not in regions:
            raise Exception("%s (%s): goal.region %r missing from graph" %
                            (self.player_name, GAME_NAME, goal_region))
        victory_loc = OriDELocation(player, "Victory", None, regions[goal_region])
        victory_loc.place_locked_item(
            OriDEItem("Victory", ItemClassification.progression, None, player))
        regions[goal_region].locations.append(victory_loc)
        self.multiworld.completion_condition[player] = \
            lambda state: state.has("Victory", player)

    def _attach_location(self, region, name, needs, placed, rule=None):
        """Reserved -> real AP location; local progression -> locked item at
        an event location; anything else isn't AP's business."""
        if rule is None and needs is not None:
            rule = make_rule(needs, self.player)
        if name in set(self.reserved):
            loc = OriDELocation(self.player, name, self.location_name_to_id[name], region)
        elif name in self.local_progression:
            item_name = self.local_progression[name]
            if item_name not in ITEM_TABLE:
                raise Exception("%s (%s): unknown local progression item %r at %r" %
                                (self.player_name, GAME_NAME, item_name, name))
            loc = OriDELocation(self.player, "%s (local)" % name, None, region)
            loc.place_locked_item(OriDEItem(
                item_name, ItemClassification.progression, None, self.player))
        else:
            return
        if rule is not None:
            loc.access_rule = rule
        region.locations.append(loc)
        placed.add(name)

    # the engines reserve the pool's +2 slack: 8th turn-in wants 9 stones,
    # 9th wants 11 (reachable.py:167-171, generator.py:1908-1911)
    MAPSTONE_BUMPS = {8: 9, 9: 11}

    def _mapstone_rule(self, n, pedestal_accesses):
        player = self.player
        stones = self.MAPSTONE_BUMPS.get(n, n)
        def rule(state):
            if not state.has("Mapstone", player, stones):
                return False
            usable = sum(
                1 for accesses in pedestal_accesses.values()
                if any(state.can_reach_region(region.name, player)
                       and (approach is None or approach(state))
                       for region, approach in accesses))
            return usable >= n
        return rule

    def create_items(self):
        for name, count in self.exported.items():
            for _ in range(count):
                self.multiworld.itempool.append(self.create_item(name))

    def create_item(self, name):
        category = ITEM_TABLE[name]["category"]
        classification = (ItemClassification.progression
                          if category in PROGRESSION_CATEGORIES
                          and name not in FILLER_OVERRIDES
                          else ItemClassification.filler)
        return OriDEItem(name, classification, self.item_name_to_id[name], self.player)

    def get_filler_item_name(self):
        return "Energy Cell"

    def fill_slot_data(self):
        return {
            "params_id": self.cfg.get("params_id"),
            "world": self.cfg.get("world"),
            "death_link": bool(self.cfg.get("death_link")),
        }
