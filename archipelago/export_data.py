"""Exports the canonical Ori DE data tables consumed by the oride apworld.

Run from repo root:  python -m archipelago.export_data
Regenerates archipelago/oride_apworld/oride/data/{items,locations,graph}.json
from the same sources the seed generator uses (pickups.py, util.py, areas.ori),
so the apworld's datapackage and logic graph can never drift from the server.

AP ids are frozen once shipped: names may be appended, never renumbered or
removed. Enforced here by diffing against the committed data files.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pickups import Pickup, Skill, Event, Teleporter, Upgrade
from seedbuilder.generator import warp_targets2
from seedbuilder.oriparse import get_areas
from util import coords_in_order, picks_by_coord, picks_by_type

BASE_ID = 524288  # 2**19; deliberately not c-ostic's 262144

DATA_DIR = os.path.join(os.path.dirname(__file__), "oride_apworld", "oride", "data")

# highest exact "N experience" item; above it EX rides the legacy
# denominations. Measured range over 5 seeds was 1..514.
EX_EXACT_CAP = 600

# Every warp destination the generator can roll. A TW pickup id is
# "Warp to <dest>,<x>,<y>,<logic node>", and Pickup.n("TW", id).name is the
# leading "Warp to <dest>" -- so the destination alone names the item and the
# seed line keeps the coordinates the client warps to. Custom teleporters are
# plando-only, so a generated seed can never leave this table.
# APPEND-ONLY, like ITEM_ORDER; check_warp_table() below fails the export if
# the generator's table grows and this one didn't.
WARP_DESTINATIONS = (
    "Warp to Above Cflame Tree EX",
    "Warp to Above Gladeser",
    "Warp to Above Grotto Crushers",
    "Warp to Butter Cell Floor",
    "Warp to Dash Plant",
    "Warp to Death Gauntlet Roof",
    "Warp to Forlorn HC",
    "Warp to Forlorn Orb",
    "Warp to Forlorn Plant",
    "Warp to Forlorn entrance",
    "Warp to Ginso Escape",
    "Warp to Glades Loop Keystone",
    "Warp to Grotto Energy Vault",
    "Warp to Horu Escape Access",
    "Warp to Horu Fields Push Block",
    "Warp to Horu R1 Mapstone",
    "Warp to Horu R4 Cutscene Rock",
    "Warp to Inner Swamp EC",
    "Warp to Kuro CS AC",
    "Warp to Lost Grove Laser Lever",
    "Warp to Lower Ginso Keystones",
    "Warp to Misty Entrance",
    "Warp to Outer Swamp AC",
    "Warp to Outer Swamp HC",
    "Warp to Right of Grenade Area",
    "Warp to Sorrow Mapstone",
    "Warp to Spidersack Energy Door",
    "Warp to Spirit Cavern AC",
    "Warp to Stomp Tree Roof",
    "Warp to Stompless AC",
    "Warp to Sunstone Plant",
    "Warp to Swamp Swim",
    "Warp to Three Bird AC",
    "Warp to Triforce AC",
    "Warp to Tumbleweed Keystone Door",
    "Warp to Upper Ginso EC",
    "Warp to Valley entry (upper)",
    "Warp to Water Vein",
    "Warp to Wilhelm EX",
)

# (code, id, category) in frozen datapackage order. Append-only!
ITEM_ORDER = (
    [("SK", sk, "skills") for sk in (0, 2, 3, 4, 5, 8, 12, 14, 50, 51, 15)] +
    [("EV", ev, "events") for ev in range(6)] +
    [("TP", tp, "teleporters") for tp in ("Grove", "Swamp", "Grotto", "Valley", "Forlorn",
                                          "Sorrow", "Ginso", "Horu", "Blackroot", "Glades")] +
    [("HC", 1, "cells"), ("EC", 1, "cells"), ("AC", 1, "cells")] +
    [("KS", 1, "stones"), ("MS", 1, "stones")] +
    [("RB", rb, "events") for rb in (17, 19, 21, 28)] +      # shards + warmth frags
    [("RB", rb, "stones") for rb in range(300, 312)] +       # keysanity area keys
    [("RB", rb, "upgrades") for rb in (6, 13, 15, 8, 9, 10, 11, 12, 0, 1, 33, 36, 37)] +
    # spirit light denominations: the fallback above EX_EXACT_CAP
    [("EX", ex, "experience") for ex in (50, 100, 200)] +
    # --- append-only past here: ids are frozen once shipped ---
    [("RB", rb, "upgrades") for rb in (31, 32, 102, 106, 111)] +   # bonus skills
    # exact spirit light amounts, so an item name means one number
    [("EX", ex, "experience") for ex in range(1, EX_EXACT_CAP + 1)
     if ex not in (50, 100, 200)] +
    # the rest of the BS* bonus-skill roll (generator.py:634-646)
    [("RB", rb, "upgrades") for rb in (101, 103, 104, 105, 107, 109, 110, 113)] +
    [("TW", dest, "warps") for dest in WARP_DESTINATIONS] +
    [("RB", rb, "upgrades") for rb in (38, 39)]              # mini health/energy
)


def check_warp_table():
    """WARP_DESTINATIONS must cover the generator's table exactly."""
    live = {"Warp to %s" % entry[0] for group in warp_targets2 for entry in group}
    known = set(WARP_DESTINATIONS)
    assert len(WARP_DESTINATIONS) == len(known), "duplicate WARP_DESTINATIONS entry"
    assert not live - known, (
        "generator.warp_targets2 gained destinations: %s -- APPEND them to the "
        "end of WARP_DESTINATIONS (never reorder; ap_ids are frozen)"
        % sorted(live - known))
    assert not known - live, (
        "WARP_DESTINATIONS names the generator no longer rolls: %s -- leave the "
        "entries in place (frozen ids) and remove this half of the check"
        % sorted(known - live))


def build_items():
    check_warp_table()
    items = []
    for i, (code, pid, category) in enumerate(ITEM_ORDER):
        pickup = Pickup.n(code, str(pid))
        assert pickup, "ITEM_ORDER references unknown pickup %s|%s" % (code, pid)
        items.append({
            "ap_id": BASE_ID + i,
            "name": pickup.name,
            "code": code,
            "id": str(pid),
            "category": category,
        })
    names = [item["name"] for item in items]
    assert len(names) == len(set(names)), "duplicate item names in datapackage"
    return items


def build_locations():
    pbc = picks_by_coord(extras=True)
    # extra_PBT entries shadow areas.ori names in picks_by_coord (e.g.
    # SunkenGladesFirstEC vs areas.ori's FirstEnergyCell); the graph speaks
    # areas.ori, so the datapackage must prefer those names
    ori_names = {p.coords: p for group in picks_by_type(extras=False).values() for p in group}
    locations = []
    for i, coord in enumerate(coords_in_order):
        pick = ori_names.get(coord, pbc[coord])
        locations.append({
            "ap_id": BASE_ID + i,
            "name": pick.area,
            "coord": coord,
            "zone": pick.zone,
        })
    names = [loc["name"] for loc in locations]
    assert len(names) == len(set(names)), "duplicate location names in datapackage"
    return locations


def build_graph():
    areas = get_areas()
    known_locs = {loc["name"]: loc for loc in build_locations()}
    homes = {}
    for name, home in areas["homes"].items():
        conns = {}
        for target, conn in home["conns"].items():
            paths = [{"tags": path[0], "reqs": list(path[1:])} for path in conn.get("paths", [])]
            entry = {"type": conn["type"], "paths": paths}
            if conn["type"] == "pickup":
                loc_info = areas["locs"].get(target)
                if loc_info:
                    entry["item"] = loc_info["item"]
                if target not in known_locs:
                    # unfillable node (mapstone pedestals etc.) -- logic-only
                    entry["unfillable"] = True
                else:
                    entry["coord"] = known_locs[target]["coord"]
            conns[target] = entry
        homes[name] = conns
    return {"homes": homes}


def freeze_check(path, fresh, keys=("name", "ap_id")):
    """Committed name->id pairs must survive regeneration verbatim."""
    if not os.path.exists(path):
        return
    with open(path) as f:
        old = json.load(f)
    old_ids = {e["name"]: e["ap_id"] for e in old}
    new_ids = {e["name"]: e["ap_id"] for e in fresh}
    for name, ap_id in old_ids.items():
        assert new_ids.get(name) == ap_id, \
            "frozen ap_id changed for %r: %s -> %s" % (name, ap_id, new_ids.get(name))


def write(path, data):
    with open(path, "w", newline="\n") as f:
        json.dump(data, f, indent=1, sort_keys=True)
        f.write("\n")


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    items = build_items()
    locations = build_locations()
    freeze_check(os.path.join(DATA_DIR, "items.json"), items)
    freeze_check(os.path.join(DATA_DIR, "locations.json"), locations)
    write(os.path.join(DATA_DIR, "items.json"), items)
    write(os.path.join(DATA_DIR, "locations.json"), locations)
    write(os.path.join(DATA_DIR, "graph.json"), build_graph())
    print("items:", len(items), "locations:", len(locations))


if __name__ == "__main__":
    main()
