"""Follow-up probes isolating the divergence classes compare.py surfaces.

Run right after compare.py -- reads the sphere-walk round inventories from
ap_in.json before replacing the exchange files with its own queries:
  .venv312\\Scripts\\python.exe archipelago\\difftest\\probes.py <randomizer0.dat>

Writes probes.txt next to this file.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import compare  # noqa: E402

from archipelago.yaml_emit import build_config  # noqa: E402
from enums import presets  # noqa: E402


def main():
    seed_path = sys.argv[1]
    with open(seed_path) as f:
        seed_lines = f.read().splitlines()
    config = build_config(seed_lines, logic_paths=[lp.value for lp in presets["Casual"]],
                          key_mode="events", variations={"open": True})
    universe = set(config["reserved_locations"]) | set(config["local_progression"])

    with open(os.path.join(HERE, "ap_in.json")) as f:
        round_invs = json.load(f)["inventories"]

    probes = {}
    # KS class: sphere-walk mismatch rounds rerun with a flooded keystone
    # pool -- if the diffs vanish, they were purely KS-budget
    for r in (3, 16):
        inv = dict(round_invs[r])
        inv["KS|1"] = inv.get("KS|1", 0) + 96
        probes["round%d_ks_boost" % r] = inv
    # Health class: dboost paths like [ChargeJump, Health=3] with zero
    # Health Cell items; PlayerState starts at has[HC]=3, AP counts items
    probes["chargejump_0hc_bigks"] = {"TP|Grotto": 1, "SK|8": 1, "KS|1": 50}
    probes["chargejump_3hc_bigks"] = {"TP|Grotto": 1, "SK|8": 1, "KS|1": 50, "HC|1": 3}
    # pedestal class: BlackrootMap home reachable but none of the pedestal
    # conn's casual reqs (WallJump / Climb+DJ / Bash+Grenade / CJ) held
    probes["blackroot_pedestal"] = {"TP|Blackroot": 1, "SK|50": 1, "SK|51": 1, "MS|1": 6}

    names = list(probes)
    invs = [probes[n] for n in names]
    srv_results = compare.run_server(invs)
    ap_out = compare.run_ap(invs)

    lines = []
    for i, name in enumerate(names):
        areas = set(srv_results[i])
        srv = {n for n in universe
               if n in areas or (n == "FinalEscape" and "HoruEscapeInnerDoor" in areas)}
        ap = set(ap_out["results"][i]) & universe
        lines.append("=== %s ===" % name)
        lines.append("inventory: %s" % json.dumps(probes[name], sort_keys=True))
        lines.append("server=%d ap=%d" % (len(srv), len(ap)))
        lines.append("  server-only: %s" % sorted(srv - ap))
        lines.append("  ap-only:     %s" % sorted(ap - srv))
        lines.append("  server pedestal areas: %s" % sorted(a for a in areas if a.endswith("Map")))
        lines.append("")
    text = "\n".join(lines) + "\n"
    with open(os.path.join(HERE, "probes.txt"), "w") as f:
        f.write(text)
    print(text)


if __name__ == "__main__":
    main()
