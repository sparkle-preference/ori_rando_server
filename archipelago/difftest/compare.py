"""Differential sphere walk: server tracker engine vs apworld compiled rules.

Run with the server venv from anywhere:
  .venv312\\Scripts\\python.exe archipelago\\difftest\\compare.py <randomizer0.bfr>

Each round the server oracle reports reachable areas for the round's
inventory; the inventory for the next round is every pickup sitting at a
server-reachable location in the sample seed. Both oracles are run on every
round's inventory and their reachable-location sets are diffed over the
universe the apworld models (reserved + local_progression names).
Writes report.txt next to this file.
"""
import json
import os
import subprocess
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
AP_ROOT = os.path.normpath(os.path.join(REPO, "..", "..", "Archipelago"))
SERVER_PY = os.path.join(REPO, ".venv312", "Scripts", "python.exe")
AP_PY = os.path.join(AP_ROOT, ".venv", "Scripts", "python.exe")
YAML_PATH = os.path.join(AP_ROOT, "Players", "TestOriReal.yaml")

MODES = ["casual-core", "casual-dboost"]
SPAWN = "Glades"  # engine name for the SunkenGladesRunaway start
SPAWN_COORD = 2
MAX_ROUNDS = 40

sys.path.insert(0, REPO)
from archipelago.yaml_emit import build_config, parse_seed  # noqa: E402
from enums import presets  # noqa: E402

DATA_DIR = os.path.join(REPO, "archipelago", "oride_apworld", "oride", "data")


def load_locations():
    with open(os.path.join(DATA_DIR, "locations.json")) as f:
        locs = json.load(f)
    return {l["name"]: l["coord"] for l in locs}


def run_server(inventories):
    in_path = os.path.join(HERE, "server_in.json")
    out_path = os.path.join(HERE, "server_out.json")
    with open(in_path, "w") as f:
        json.dump({"spawn": SPAWN, "modes": MODES, "inventories": inventories}, f)
    env = os.environ.copy()
    env["PYTHONPATH"] = REPO
    # greedy KS spending makes reach traversal-order sensitive; pin the
    # string hash seed so the report is reproducible
    env["PYTHONHASHSEED"] = "0"
    subprocess.run([SERVER_PY, os.path.join(HERE, "reach_server.py"), in_path, out_path],
                   cwd=REPO, env=env, check=True)
    with open(out_path) as f:
        return json.load(f)["results"]


def run_ap(inventories):
    in_path = os.path.join(HERE, "ap_in.json")
    out_path = os.path.join(HERE, "ap_out.json")
    with open(in_path, "w") as f:
        json.dump({"inventories": inventories}, f)
    subprocess.run([AP_PY, os.path.join(HERE, "reach_ap.py"), YAML_PATH, in_path, out_path],
                   cwd=AP_ROOT, check=True)
    with open(out_path) as f:
        return json.load(f)


def describe_inventory(inv):
    counts = Counter()
    named = []
    for key, count in sorted(inv.items()):
        code, _, pid = key.partition("|")
        if code in ("KS", "MS", "HC", "EC", "AC"):
            counts[code] += count
        elif code in ("SK", "TP", "EV"):
            named.append(key if count == 1 else "%s x%d" % (key, count))
    parts = ["%s=%d" % (c, counts[c]) for c in ("KS", "MS", "HC", "EC", "AC")]
    return " ".join(parts) + (" | " + ", ".join(named) if named else "")


def main():
    seed_path = sys.argv[1]
    with open(seed_path) as f:
        seed_lines = f.read().splitlines()
    _, placement_list = parse_seed(seed_lines)
    placements = {coord: (code, pid) for coord, code, pid, _ in placement_list}

    config = build_config(seed_lines, logic_paths=[lp.value for lp in presets["Casual"]],
                          key_mode="events", variations={"open": True})
    universe = sorted(set(config["reserved_locations"]) | set(config["local_progression"]))
    coord_by_name = load_locations()

    def inventory_at(area_set):
        inv = Counter()
        seen = set(area_set)
        if "HoruEscapeInnerDoor" in area_set:
            seen.add("FinalEscape")  # not a graph node; free once the door region is reached
        for name in seen:
            coord = coord_by_name.get(name)
            if coord is None or coord == SPAWN_COORD:
                continue
            placed = placements.get(coord)
            if placed:
                inv["%s|%s" % placed] += 1
        return dict(sorted(inv.items()))

    # sphere walk on the server engine; the walk accumulates ever-reached
    # areas because greedy KS spending makes single-round reach non-monotonic
    inv = {}
    ever_reached = set()
    rounds = []  # (inventory, server area set, areas lost vs previous round)
    while True:
        areas = set(run_server([inv])[0])
        lost = sorted(rounds[-1][1] - areas) if rounds else []
        rounds.append((inv, areas, lost))
        ever_reached |= areas
        next_inv = inventory_at(ever_reached)
        if next_inv == inv:
            break
        inv = next_inv
        if len(rounds) >= MAX_ROUNDS:
            raise AssertionError("no fixpoint after %d rounds" % MAX_ROUNDS)

    ap_out = run_ap([r[0] for r in rounds])

    def server_locs(areas):
        reachable = set()
        for name in universe:
            if name in areas or (name == "FinalEscape" and "HoruEscapeInnerDoor" in areas):
                reachable.add(name)
        return reachable

    lines = []
    universe_set = set(universe)
    mismatch_rounds = 0
    for r, (rinv, areas, lost) in enumerate(rounds):
        srv = server_locs(areas)
        ap = set(ap_out["results"][r]) & universe_set
        ap_sweep = set(ap_out["results_sweep"][r]) & universe_set
        srv_only = sorted(srv - ap)
        ap_only = sorted(ap - srv)
        lines.append("=== round %d ===" % r)
        lines.append("inventory: %s" % (describe_inventory(rinv) or "(empty)"))
        if lost:
            lines.append("server reach SHRANK vs round %d: %s" % (r - 1, ", ".join(lost)))
        lines.append("victory: server=%s ap=%s" % (
            "HoruEscapeInnerDoor" in areas, "Victory" in ap_out["results"][r]))
        lines.append("reachable: server=%d ap=%d (universe %d)" % (len(srv), len(ap), len(universe)))
        if srv_only or ap_only:
            mismatch_rounds += 1
            for name in srv_only:
                lines.append("  SERVER-ONLY %s (coord %s)" % (name, coord_by_name.get(name)))
            for name in ap_only:
                lines.append("  AP-ONLY     %s (coord %s)" % (name, coord_by_name.get(name)))
        else:
            lines.append("  (match)")
        if ap_sweep != ap:
            lines.append("  [sweep-mode delta: +%s -%s]" % (sorted(ap_sweep - ap), sorted(ap - ap_sweep)))
        lines.append("")

    lines.append("rounds: %d, rounds with mismatches: %d" % (len(rounds), mismatch_rounds))
    if ap_out["skipped_item_keys"]:
        lines.append("inventory keys invisible to AP: %s" % ", ".join(ap_out["skipped_item_keys"]))
    report = "\n".join(lines) + "\n"
    with open(os.path.join(HERE, "report.txt"), "w") as f:
        f.write(report)
    print(report)


if __name__ == "__main__":
    main()
