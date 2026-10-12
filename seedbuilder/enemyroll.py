"""Enemy rando: the server rolls what each placeholder spawns, the client looks it up by index.

enemies.json comes from prior_notes/tools/enemy_rando/gen_data.py, in the client's placement order.
"""
import json
import os
import random
from collections import Counter, defaultdict
from hashlib import sha256

from seedbuilder.enemyopts import DEFAULTS, normalize

META_PREFIX = "//EnemyRolls="
RANGED = ("Elementals", "Spiders")
# a scene holds this many more ranged fliers than vanilla gave it
RANGED_EXTRA = 2
LASER = "floatingRockLaserEnemy"
# kinds that want level floor under them when they take a floor spot that never held one
GROUNDED = ("Banelings", "Sharks", "Rhinos")

# a miniboss room holding one of these kinds needs one of the listed skills past its door: spirit flame can't kill them
KILLERS = {
    "Elementals": ("Grenade", "Bash", "ChargeFlame", "ChargeJump", "Stomp"),
    "Rhinos": ("Stomp", "ChargeFlame", "Grenade"),
}
# arena scene -> the logic edges its door gates (Lapis, 2026-10-09); rooms absent here gate nothing
ARENA_EDGES = {
    "ginsoTreePuzzles": [("LowerGinsoTree", "GinsoMiniBossDoor")],
    "ginsoTreeResurrection": [("GinsoTeleporter", "TopGinsoTree")],
    "mangroveFallsGrenadeEscalation": [("LowerBlackroot", "LowerBlackrootGrenadeThrow")],
    "mangroveFallsGrenadeEscalationR": [("LowerBlackroot", "LostGrove")],
    "mistyWoodsShortPath": [("MistyOrbRoom", "MistyPreKeystone2")],
    "moonGrottoEnemyPuzzle": [("GumoHideout", "GumoHideoutMiniboss")],
    "mountHoruHubBottom": [("HoruInnerEntrance", "HoruBasement")],
    "mountHoruProjectileCorridor": [("R2", "HoruR2")],
}

_table = None


def table():
    global _table
    if _table is None:
        with open(os.path.join(os.path.dirname(__file__), "enemies.json")) as f:
            _table = json.load(f)
        for kind in _table["kinds"]:
            kind["variants"] = [i for i, v in enumerate(_table["variants"]) if v["kind"] == kind["name"]]
    return _table


def same_family(a, b):
    """a kept enemy rerolls within its family: its own kind, or spiders and turret elementals for each other"""
    return a == b or (a in RANGED and b in RANGED)


def roll(seed, world, opts):
    """One variant index (or None, vanilla) per placement, for a world's seed and options."""
    t = table()
    o = dict(DEFAULTS)
    o.update(normalize(opts) or {})
    pool, keep = set(o["pool"]), set(o["keep"])
    logic_on, pools_on = o["logic"] == "on", o["pools"] == "on"
    flying_fish, walkers = o["flyingfish"] == "on", o["walkers"] == "on"
    arena_kind, shooter_cap = o["arena"] == "kind", o["shootercap"] == "on"
    kinds = {k["name"]: k for k in t["kinds"]}
    kind_of_prefab = {p: k["name"] for k in t["kinds"] for p in k["prefabs"]}
    ranged_vanilla = Counter(p["scene"] for p in t["placements"] if p["kind"] in RANGED)
    ranged_rolled = defaultdict(int)
    out = []
    for p in t["placements"]:
        chosen = pick(p, pool, keep, logic_on, pools_on, flying_fish, walkers, arena_kind, shooter_cap, kinds, kind_of_prefab,
                      ranged_rolled[p["scene"]] >= ranged_vanilla[p["scene"]] + RANGED_EXTRA,
                      random.Random(int(sha256(("%s|%s|%s" % (seed, world, p["guid"])).encode("utf-8")).hexdigest(), 16)))
        out.append(chosen)
        kind = t["variants"][chosen]["kind"] if chosen is not None else p["kind"]
        if kind in RANGED:
            ranged_rolled[p["scene"]] += 1
    return out


def pick(p, pool, keep, logic_on, pools_on, flying_fish, walkers, arena_kind, shooter_cap, kinds, kind_of_prefab, ranged_full, rng):
    own = p["kind"]
    if own is None or p["pinned"] or own in keep or (arena_kind and p["arena"]):
        return None
    # a role ending in ! is a puzzle pin and outlives logic=off
    role = p["role"]
    if role and role.endswith("!"):
        role = role[:-1]
    elif not logic_on:
        role = None
    bash_only, keep_kind = role == "bashable", role == "keep"
    only_kinds = role[6:].split("+") if role and role.startswith("kinds:") else None
    only_prefab = role[7:] if role and role.startswith("prefab:") else None
    if only_prefab:
        only_kinds = [kind_of_prefab[only_prefab]] if only_prefab in kind_of_prefab else []
    spot, ranged = p["spot"], own in RANGED
    candidates = []
    for kind in kinds.values():
        name, flags = kind["name"], kind["flags"]
        if spot not in kind["spots"] and not (spot == "rhino" and "floor" in kind["spots"]):
            continue
        if keep_kind and not same_family(name, own):
            continue
        if name != own and name not in pool:
            continue
        if ((not pools_on and spot == "water" and name != "Fish")
                or (not flying_fish and name == "Fish" and spot != "water")
                or (not walkers and "clings" not in flags and spot in ("roof", "wall") and name != own)):
            continue
        if only_kinds is not None and name not in only_kinds:
            continue
        # a ranged flier at a spot that never held one needs room and a seat
        if shooter_cap and name in RANGED and not ranged and ((spot == "air" and not p["clear"]) or ranged_full):
            continue
        if spot == "floor" and name in GROUNDED and own != name and not p["flat"]:
            continue
        if spot == "water" and ((name == "Slimes" and not p["surface"]) or (name == "Frogs" and not p["floor"])):
            continue
        if (not bash_only or "bash" in flags) and not (p["wet"] and "drowns" in flags):
            candidates.append(kind)
    if not candidates:
        return None
    # kinds by their table weight (slimes a little likelier, the ground bruisers less), then a variant
    draw = rng.randrange(sum(k["weight"] for k in candidates))
    chosen = candidates[-1]
    for kind in candidates:
        draw -= kind["weight"]
        if draw < 0:
            chosen = kind
            break
    variants = [dict(table()["variants"][i], index=i) for i in chosen["variants"]]
    if only_prefab:
        variants = [v for v in variants if v["prefab"] == only_prefab]
    elif keep_kind and p["prefab"] != LASER:
        variants = [v for v in variants if v["prefab"] != LASER]  # a laser's beam can't be bashed
    if not variants:
        return None
    # elementals by vanilla frequency (more lasers is bad), every other kind's variants evenly
    weights = [v["count"] if chosen["name"] == "Elementals" else 1 for v in variants]
    draw = rng.randrange(sum(weights))
    for v, weight in zip(variants, weights):
        draw -= weight
        if draw < 0:
            return v["index"]
    return None


def arena_threats(rolls):
    """scene -> the kinds in KILLERS a miniboss room holds after this roll."""
    t = table()
    out = defaultdict(set)
    for p, r in zip(t["placements"], rolls):
        kind = t["variants"][r]["kind"] if r is not None else p["kind"]
        if p["arena"] and kind in KILLERS:
            out[p["scene"]].add(kind)
    return {scene: sorted(kinds) for scene, kinds in sorted(out.items())}


def gated_edges(threats):
    """(home, target) -> the kinds a path there must be able to kill."""
    edges = defaultdict(set)
    for scene, kinds in threats.items():
        for edge in ARENA_EDGES.get(scene, ()):
            edges[edge].update(kinds)
    return {edge: sorted(kinds) for edge, kinds in edges.items()}


def kill_paths(path, kinds):
    """A path past a miniboss room: per kind there, as it is when it can kill one, else one copy per killer."""
    paths = [(tuple(path[0]),) + tuple(path[1:])]
    for kind in kinds:
        grown = []
        for p in paths:
            grown += [p] if any(token in KILLERS[kind] for token in p[1:]) else [p + (killer,) for killer in KILLERS[kind]]
        paths = list(dict.fromkeys(grown))
    return paths


def meta_line(rolls):
    return META_PREFIX + table()["version"] + ":" + ",".join("" if r is None else str(r) for r in rolls)


def parse_meta(line):
    """The rolls on an //EnemyRolls= line (None where vanilla), or None when it isn't one of ours."""
    if not line.lower().startswith(META_PREFIX.lower()):
        return None
    version, _, body = line[len(META_PREFIX):].strip().partition(":")
    if version != table()["version"]:
        return None
    rolls = [None if r == "" else int(r) for r in body.split(",")]
    return rolls if len(rolls) == len(table()["placements"]) else None


def spoiler(rolls, header="Enemies"):
    """Kinds per zone, and the purple-door rooms whose elemental put a killer into the logic."""
    t = table()
    counts = defaultdict(Counter)
    for p, r in zip(t["placements"], rolls):
        kind = t["variants"][r]["kind"] if r is not None else (p["kind"] or "Sharks")
        counts[p["zone"]][kind] += 1
    out = header + ": {\n"
    width = max(len(z) for z in counts)
    for zone in sorted(counts):
        out += "    %s%s%s\n" % (zone, " " * (2 + width - len(zone)), ", ".join("%s %d" % kv for kv in counts[zone].most_common()))
    for scene, kinds in arena_threats(rolls).items():
        if scene in ARENA_EDGES:
            out += "    %s: %s (logic wants %s)\n" % (scene, ", ".join(kinds), "; ".join(" | ".join(KILLERS[k]) for k in kinds))
    return out + "}\n"
