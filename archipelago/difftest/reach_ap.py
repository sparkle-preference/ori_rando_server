"""AP-side reach oracle for the differential test.

Run from the Archipelago checkout with its venv:
  .venv\\Scripts\\python.exe <difftest>\\reach_ap.py <player yaml> in.json out.json

in.json:  {"inventories": [{"CODE|ID": count}, ...]}
out.json: {"results": [[reachable location base name, ...], ...],
           "results_sweep": same but after sweep_for_advancements,
           "skipped_item_keys": inventory keys with no AP item (EX, bonus RBs)}

"results" collects exactly the given inventory (the differential contract:
same items in, reach out). "results_sweep" additionally auto-collects locked
local-progression events AP itself can reach -- kept for reference, but it
double-counts pickups the inventory already carries, so compare.py diffs
against "results".
"""
import json
import os
import sys

sys.path.insert(0, os.getcwd())  # invoked with cwd = Archipelago root


def main():
    yaml_path, in_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
    import Utils
    from BaseClasses import CollectionState
    from test.general import setup_multiworld
    import worlds.oride as oride

    with open(yaml_path, encoding="utf-8-sig") as f:
        doc = Utils.parse_yaml(f.read())
    blob = doc["Ori DE Rando"]["orirando"]

    multiworld = setup_multiworld(oride.OriDEWorld, seed=1, options={"orirando": blob})
    world = multiworld.worlds[1]
    name_by_codeid = {(i["code"], str(i["id"])): i["name"] for i in oride.ITEMS}
    all_locations = multiworld.get_locations(1)

    def reach_set(state):
        names = set()
        for loc in all_locations:
            if loc.can_reach(state):
                name = loc.name
                if name.endswith(" (local)"):
                    name = name[:-len(" (local)")]
                names.add(name)
        return sorted(names)

    with open(in_path) as f:
        query = json.load(f)

    results, results_sweep, skipped = [], [], set()
    for inv in query["inventories"]:
        for do_sweep, bucket in ((False, results), (True, results_sweep)):
            state = CollectionState(multiworld)
            for key, count in inv.items():
                code, _, pid = key.partition("|")
                name = name_by_codeid.get((code, pid))
                if name is None:
                    skipped.add(key)
                    continue
                for _ in range(int(count)):
                    state.collect(world.create_item(name), prevent_sweep=True)
            if do_sweep:
                state.sweep_for_advancements()
            bucket.append(reach_set(state))

    with open(out_path, "w") as f:
        json.dump({"results": results, "results_sweep": results_sweep,
                   "skipped_item_keys": sorted(skipped)}, f, indent=1)


if __name__ == "__main__":
    main()
