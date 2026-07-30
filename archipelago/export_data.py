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
from seedbuilder.oriparse import get_areas
from util import coords_in_order, picks_by_coord, picks_by_type

BASE_ID = 524288  # 2**19; deliberately not c-ostic's 262144

DATA_DIR = os.path.join(os.path.dirname(__file__), "oride_apworld", "oride", "data")

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
    [("RB", rb, "bonus") for rb in (6, 13, 15, 8, 9, 10, 11, 12, 0, 1, 33, 36, 37)]
)


def build_items():
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
