"""Emits the paired Archipelago yaml for a rolled Ori seed (prototype).

The K placed SK/TP/EV items move to the AP pool and their locations become
AP slots; every other progression placement (KS/MS/HC/EC/AC, shards, frags,
keysanity keys) is pinned local so AP reachability mirrors the seed exactly.
EX and bonus RBs never leave the seed and are invisible to AP.

Run from repo root:
  python -m archipelago.yaml_emit <randomizer.dat> <out.yaml> [slot_name]
"""
import json
import os
import re
import sys
from collections import Counter

from seedbuilder.oriparse import get_path_tags_from_pathsets

DATA_DIR = os.path.join(os.path.dirname(__file__), "oride_apworld", "oride", "data")

EXPORT_CODES = {"SK", "TP", "EV"}
LOCAL_CODES = {"KS", "MS", "HC", "EC", "AC"}
LOCAL_RB_IDS = {"17", "19", "21", "28"} | {str(n) for n in range(300, 312)}
SKIP_CODES = {"EX", "NO"}

SPAWN_COORD = 2  # spawn pickup stays fully local

GOAL_REGION = "HoruEscapeInnerDoor"
# fillable locations areas.ori doesn't model as graph nodes
EXTRA_LOCATIONS = {
    # the escape itself is free once the door region is reached
    "FinalEscape": {"region": "HoruEscapeInnerDoor", "paths": []},
    # in-escape plant: wind starts the escape, fire opens the plant
    "ForlornEscapePlant": {"region": "ForlornLaserRoom", "paths": [
        {"tags": [], "reqs": ["Wind", "ChargeFlame"]},
        {"tags": [], "reqs": ["Wind", "Grenade"]},
    ]},
}


def _load(name):
    with open(os.path.join(DATA_DIR, name)) as f:
        return json.load(f)


ITEM_NAMES = {(i["code"], i["id"]): i["name"] for i in _load("items.json")}
LOC_NAMES = {l["coord"]: l["name"] for l in _load("locations.json")}


def parse_seed(seed_lines):
    """-> (flagline, [(coord, code, id, zone)])."""
    placements = []
    for line in seed_lines[1:]:
        if not line:
            continue
        coord, code, pid, zone = line.split("|", 3)
        placements.append((int(coord), code, pid, zone))
    return seed_lines[0], placements


def keymode_to_ap(key_mode):
    """Engine key mode (enum value or string) -> apworld key_mode."""
    km = str(key_mode or "").lower()
    if km == "shards":
        return "shards"
    if km == "free":
        return "free"
    return "events"  # Default/Clues/LimitKeys all place keys as EV items


def make_config(exported, reserved, local, logic_paths, key_mode="events",
                spawn="SunkenGladesRunaway", variations=None,
                params_id=0, world=1):
    """Classified placements + generation options -> orirando yaml blob.
    exported: {item name: count}; reserved: [location name]; local:
    {location name: item name}. Shared by the file-based prototype path
    below and archipelago.convert.build_ap_config (converted seeds)."""
    return {
        "params_id": params_id,
        "world": world,
        "spawn": spawn,
        "pathsets": get_path_tags_from_pathsets(list(logic_paths)),
        "variations": dict(variations or {}),
        "key_mode": keymode_to_ap(key_mode),
        "exported_items": dict(sorted(exported.items())),
        "reserved_locations": sorted(reserved),
        "local_progression": dict(sorted(local.items())),
        "extra_locations": EXTRA_LOCATIONS,
        "goal": {"region": GOAL_REGION},
    }


def build_config(seed_lines, logic_paths, key_mode="events",
                 spawn="SunkenGladesRunaway", variations=None,
                 params_id=0, world=1):
    """Seed text lines + generation options -> orirando yaml blob.

    The prototype classifier for UNCONVERTED solo seeds: pretends the
    SK/TP/EV categories were exported. Kept for the file-based CLI below
    (difftest depends on it); AP-mode seeds go through
    archipelago.convert.build_ap_config instead."""
    _, placements = parse_seed(seed_lines)
    exported = Counter()
    reserved = []
    local = {}
    for coord, code, pid, zone in placements:
        if coord == SPAWN_COORD:
            continue
        name = LOC_NAMES.get(coord)
        if name is None:
            raise ValueError("coord %s is not in the datapackage" % coord)
        if code in EXPORT_CODES:
            exported[ITEM_NAMES[(code, pid)]] += 1
            reserved.append(name)
        elif code in LOCAL_CODES or (code == "RB" and pid in LOCAL_RB_IDS):
            local[name] = ITEM_NAMES[(code, pid)]
        elif code == "RB" or code in SKIP_CODES:
            continue
        else:
            raise ValueError("unhandled pickup %s|%s at %s" % (code, pid, name))
    return make_config(exported, reserved, local, logic_paths,
                       key_mode=key_mode, spawn=spawn, variations=variations,
                       params_id=params_id, world=world)


_PLAIN = re.compile(r"^[A-Za-z_][A-Za-z0-9_\- ]*[A-Za-z0-9_\-]$")
_AMBIGUOUS = {"true", "false", "yes", "no", "on", "off", "null", "none", "~"}


def _scalar(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    s = str(value)
    if _PLAIN.match(s) and s.lower() not in _AMBIGUOUS:
        return s
    return "'%s'" % s.replace("'", "''")


def _emit(value, indent):
    """dict/list/scalar -> yaml lines at the given indent depth."""
    pad = "  " * indent
    lines = []
    if isinstance(value, dict):
        for k, v in value.items():
            if isinstance(v, dict) and v:
                lines.append("%s%s:" % (pad, _scalar(k)))
                lines += _emit(v, indent + 1)
            elif isinstance(v, list) and v:
                lines.append("%s%s:" % (pad, _scalar(k)))
                lines += _emit(v, indent + 1)
            elif isinstance(v, dict):
                lines.append("%s%s: {}" % (pad, _scalar(k)))
            elif isinstance(v, list):
                lines.append("%s%s: []" % (pad, _scalar(k)))
            else:
                lines.append("%s%s: %s" % (pad, _scalar(k), _scalar(v)))
    elif isinstance(value, list):
        for v in value:
            if isinstance(v, dict):
                sub = _emit(v, indent + 1)
                lines.append("%s- %s" % (pad, sub[0].strip()))
                lines += sub[1:]
            else:
                lines.append("%s- %s" % (pad, _scalar(v)))
    else:
        lines.append("%s%s" % (pad, _scalar(value)))
    return lines


def emit_yaml(config, slot_name):
    doc = {
        "name": slot_name,
        "description": "orirando seed pairing (generated by archipelago/yaml_emit.py)",
        "game": "Ori DE Rando",
        "Ori DE Rando": {
            "progression_balancing": 50,
            "accessibility": "full",
            "orirando": config,
        },
    }
    return "\n".join(_emit(doc, 0)) + "\n"


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit("usage: python -m archipelago.yaml_emit <randomizer.dat> <out.yaml> [slot_name]")
    seed_path, out_path = sys.argv[1], sys.argv[2]
    slot = sys.argv[3] if len(sys.argv) > 3 else "TestOriReal"
    with open(seed_path) as f:
        seed_lines = f.read().splitlines()
    from enums import presets
    config = build_config(
        seed_lines,
        logic_paths=[lp.value for lp in presets["Casual"]],
        key_mode="events",
        variations={"open": True},  # default seeds run with open dungeons
    )
    text = emit_yaml(config, slot)
    with open(out_path, "w", newline="\n") as f:
        f.write(text)
    print("wrote %s (%d exported / %d reserved / %d local)" % (
        out_path, sum(config["exported_items"].values()),
        len(config["reserved_locations"]), len(config["local_progression"])))
