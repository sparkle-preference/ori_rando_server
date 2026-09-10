"""Server-side reach oracle for the differential test.

Run from the repo root with the server venv (PYTHONPATH=repo root):
  .venv312\\Scripts\\python.exe archipelago\\difftest\\reach_server.py in.json out.json

in.json:  {"spawn": "Glades", "modes": [...], "key_tiers": [positional or absent],
           "inventories": [{"CODE|ID": count}, ...]}
out.json: {"results": [[reachable area name, ...], ...]}
"""
import json
import sys

from archipelago.convert import tier_map_from_list
from reachable import Map, PlayerState


def main():
    in_path, out_path = sys.argv[1], sys.argv[2]
    with open(in_path) as f:
        query = json.load(f)
    spawn = query.get("spawn", "Glades")
    modes = query.get("modes", ["casual-core", "casual-dboost"])
    # the yaml's tiers, so keystone doors are charged the way the apworld charges them
    ks_tiers = tier_map_from_list(query["key_tiers"]) if query.get("key_tiers") else None
    results = []
    for inv in query["inventories"]:
        pickinfos = []
        for key, count in inv.items():
            code, _, pid = key.partition("|")
            pickinfos.append((code, pid, int(count), False))
        state = PlayerState(pickinfos)
        # mirrors the tracker route
        if ks_tiers is None and state.has["KS"] > 8 and "standard-core" in modes:
            state.has["KS"] += 2 * (state.has["KS"] - 8)
        areas = Map.get_reachable_areas(state, modes, spawn, need_reached_with=False,
                                        ks_tiers=ks_tiers)
        results.append(sorted(areas))
    with open(out_path, "w") as f:
        json.dump({"results": results}, f, indent=1)


if __name__ == "__main__":
    main()
