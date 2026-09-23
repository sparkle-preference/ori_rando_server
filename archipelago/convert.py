"""Archipelago game-mode conversion pass over rendered multiworld seeds.

A K-world MW seed is converted before it is stored: a converted placement's
line becomes an MW placeholder owned by the host world's shadow player K+w,
and the item moves to the AP pool as a manifest entry on its owner's seed.
Converts the selected categories plus every cross-landed item the datapackage
can name; generic keystones only when "stones" is exported. Per-world counts
differ by design; only the game-wide item/location totals must match.
"""
import json
import os
import re
import sys
import types

from archipelago.export_data import EX_EXACT_CAP
from seedbuilder.generator import SPAWN_SPOTS
from archipelago.yaml_emit import (LOC_NAMES, ITEM_NAMES, local_item_name,
                                   make_config, SPAWN_COORD)
from util import is_mw_manifest_loc

DATA_DIR = os.path.join(os.path.dirname(__file__), "oride_apworld", "oride", "data")


def oride_module(name):
    """Import an apworld submodule without its __init__ (which needs Archipelago
    core); the shim package resolves their relative imports."""
    import importlib
    if "_oride_shim" not in sys.modules:
        pkg = types.ModuleType("_oride_shim")
        pkg.__path__ = [os.path.join(os.path.dirname(__file__), "oride_apworld", "oride")]
        sys.modules["_oride_shim"] = pkg
    return importlib.import_module("_oride_shim." + name)

with open(os.path.join(DATA_DIR, "items.json")) as _f:
    _ITEMS = json.load(_f)
ITEM_BY_CODE_ID = {(i["code"], i["id"]): i for i in _ITEMS}
ITEM_BY_AP_ID = {i["ap_id"]: (i["code"], i["id"]) for i in _ITEMS}

EXPORTABLE_CATEGORIES = ("skills", "teleporters", "events", "cells", "stones",
                         "upgrades")
DEFAULT_EXPORT = ("skills", "teleporters", "events")
# datapackage categories each export category hands over
CATEGORY_ITEMS = {"teleporters": ("teleporters", "warps")}
RETIRED_CATEGORIES = {"warps": "teleporters"}

# a shared category is one item fanned out by the netcode, so it can't also export.
# Keyed by ShareType value; bonus RBs share as upgrades.
SHARE_TO_AP = {
    "Skills": ("skills",),
    "Teleporters": ("teleporters",),
    "WorldEvents": ("events",),
    "Upgrades": ("upgrades",),
}

MAX_SLOTS = 256  # 8x32-bit slot bitfields on the Player entity: wire format

# everything the apworld's logic can see: pinned local when same-world and unselected,
# exported otherwise, never left on a native manifest
LOCAL_CODES = {"KS", "MS", "HC", "EC", "AC", "SK", "TP", "EV"}
LOCAL_RB_IDS = {"17", "19", "21", "28"} | {str(n) for n in range(300, 312)}

EX_DENOMS = (50, 100, 200)

# seed spawn zone -> areas.ori region the run actually starts in
SPAWN_REGIONS = {
    "Glades": "SunkenGladesRunaway",
    "Grotto": "MoonGrottoAboveTeleporter",
    "Swamp": "SwampTeleporter",
    "Valley": "ValleyTeleporter",
    "Sorrow": "SorrowTeleporter",
    "Forlorn": "ForlornTeleporter",
    "Ginso": "GinsoTeleporter",
    "Horu": "HoruTeleporter",
    "Grove": "SpiritTreeRefined",
    "Blackroot": "BlackrootGrottoConnection",
}

# a Random spawn stores only the sentinel; the seed's forced WS warp carries
# the resolved point (generator.SPAWN_SPOTS, inverted)
SPAWN_ZONE_BY_COORDS = {xy: zone for zone, xy in SPAWN_SPOTS.items()}


def resolve_spawn_zone(placements, spawn_zone):
    """The world's real spawn zone: 'Random' reads its forced spawn warp;
    no warp on the spawn line means the roll landed Glades itself."""
    if spawn_zone != "Random":
        return spawn_zone
    for loc, code, pid, zone in placements:
        if str(loc) != str(SPAWN_COORD):
            continue
        m = re.search(r"WS/(-?\d+),(-?\d+)", "%s/%s" % (code, pid))
        if m:
            coords = (int(m.group(1)), int(m.group(2)))
            resolved = SPAWN_ZONE_BY_COORDS.get(coords)
            if resolved is None:
                raise ApConversionError(
                    "spawn warp to %s,%s has no AP zone mapping" % coords)
            return resolved
    return "Glades"


class ApConversionError(Exception):
    """AP conversion or yaml derivation can't produce a sound result."""


def is_progression(code, pid):
    return code in LOCAL_CODES or (code == "RB" and pid in LOCAL_RB_IDS)


def nearest_ex_denom(value):
    """True EX value -> datapackage denomination (ties round down)."""
    return min(EX_DENOMS, key=lambda d: (abs(d - int(value)), d))


def ex_export_value(value):
    """True EX value -> the amount both the AP pool and the manifest use: exact
    up to the cap, a denomination above it."""
    try:
        v = int(value)
    except (TypeError, ValueError):
        return nearest_ex_denom(0)
    return v if 1 <= v <= EX_EXACT_CAP else nearest_ex_denom(v)


def match_key(code, id):
    """Seed-line (code, id) -> datapackage identity. EX buckets to its exported
    amount; a TW id "<name>,<x>,<y>,<node>" is named by its destination alone."""
    if code == "EX":
        return ("EX", str(ex_export_value(id)))
    if code == "TW":
        return ("TW", str(id).split(",")[0])
    return (code, str(id))


def is_exportable(code, id):
    """Can this pickup ride the AP pool? Datapackage membership is the whole rule."""
    return match_key(code, id) in ITEM_BY_CODE_ID


def share_export_clash(shared, exported):
    """Export categories a seed can't have while sharing those categories."""
    clash = set()
    for s in shared:
        clash |= set(SHARE_TO_AP.get(getattr(s, "value", s), ())) & set(exported)
    return sorted(clash)


def normalize_categories(categories):
    """Selected category names, with retired ones folded into their survivor."""
    return sorted({RETIRED_CATEGORIES.get(c, c) for c in categories})


def export_code_ids(categories):
    """Category names -> set of exportable (code, id) pairs. Generic keystones
    ride "stones" (inert under keysanity, which places none)."""
    bad = [c for c in categories if c not in EXPORTABLE_CATEGORIES]
    if bad:
        raise ApConversionError("unknown AP export categories: %s" % ", ".join(bad))
    cats = set()
    for c in categories:
        cats.update(CATEGORY_ITEMS.get(c, (c,)))
    return {(i["code"], i["id"]) for i in _ITEMS
            if i["category"] in cats}


def ap_export_categories(params):
    """The category list conversion runs with, resolved from params."""
    return (normalize_categories(getattr(params, "ap_export", None) or [])
            or list(DEFAULT_EXPORT))


def exports_generic_keystones(params):
    """True when conversion pulls generic keystones into the AP pool."""
    return (bool(getattr(params, "ap_mode", False))
            and "stones" in ap_export_categories(params))


def keystone_tier_list(params, player=None):
    """Per-door tiers positional over shared.KEYSTONE_DOORS (0 = door absent), ranked
    by params.ks_door_order, else canonical order. None under keysanity."""
    vals = {getattr(v, "value", v) for v in getattr(params, "variations", [])}
    if "Keysanity" in vals:
        return None  # no generic keystones exist to tier
    shared = oride_module("shared")
    live = shared.keystone_door_tiers(ap_variations(vals))  # liveness + fallback order
    stored = getattr(params, "ks_door_order", None) or {}
    order = stored.get(str(player), stored.get(player)) if player is not None else None
    costs = {(h, t): c for h, t, c in shared.KEYSTONE_DOORS}
    ranked = [e for e in (tuple(d) for d in order or []) if e in live]
    ranked += [e for e in live if e not in ranked]  # unseen doors close the tail
    tiers, total = {}, 0
    for edge in ranked:
        total += costs[edge]
        tiers[edge] = total
    return [tiers.get((h, t), 0) for h, t, _ in shared.KEYSTONE_DOORS]


def keytiers_meta(params, player=None):
    """The '//KeyTiers=' metadata line every AP seed carries, or None. The client
    must charge the same door thresholds as the apworld."""
    if not getattr(params, "ap_mode", False):
        return None
    tiers = keystone_tier_list(params, player)
    if tiers is None:
        return None
    return "//KeyTiers=" + "+".join(str(t) for t in tiers)


def tier_map_from_list(tiers):
    """Positional KeyTiers values -> {(home, target): tier}; absent doors dropped."""
    shared = oride_module("shared")
    return {(h, t): v for (h, t, _), v in zip(shared.KEYSTONE_DOORS, tiers) if v}


def keystone_tier_map(params, player=None):
    """Door thresholds for the tracker engine, keyed by graph edge. None
    outside AP mode (the spend model stays) and under keysanity."""
    if not getattr(params, "ap_mode", False):
        return None
    tiers = keystone_tier_list(params, player)
    return None if tiers is None else tier_map_from_list(tiers)


def ap_variations(variations):
    """Params variations (enums or values) -> apworld variations dict. open is on
    unless ClosedDungeons is set."""
    vals = {getattr(v, "value", v) for v in variations}
    out = {}
    if "ClosedDungeons" not in vals:
        out["open"] = True
    if "OpenWorld" in vals:
        out["open_world"] = True
    if "Keysanity" in vals:
        out["keysanity"] = True
    return out


def ap_spawn_region(zone):
    if not zone:
        zone = "Glades"
    if zone not in SPAWN_REGIONS:
        raise ApConversionError(
            "no AP spawn region mapping for spawn zone %r" % zone)
    return SPAWN_REGIONS[zone]


def ap_convert(texts, categories, keep_locs=frozenset()):
    """Per-world seed texts (index 0 = world 1) -> (new_texts, info), deterministic.
    keep_locs: (world, loc) pairs that must stay local placements."""
    players = len(texts)
    export_ids = export_code_ids(categories)

    worlds = []       # per world: seed lines (no trailing empty)
    fields = []       # per world: line index -> split fields (None = flagline)
    manifests = []    # per world: native manifest slot -> line index
    for text in texts:
        lines = text.split("\n")
        if lines and lines[-1] == "":
            lines = lines[:-1]
        f = [None]
        m = {}
        for idx, line in enumerate(lines[1:], start=1):
            # not split("|", 3): an annotated line's 5th field would land in zone
            parts = line.split("|")
            f.append(parts if len(parts) == 4 else None)
            if len(parts) != 4:
                continue
            try:
                loc = int(parts[0])
            except ValueError:
                continue
            if is_mw_manifest_loc(loc) and parts[1] == "MW":
                m[-loc - 2] = idx
        worlds.append(lines)
        fields.append(f)
        manifests.append(m)

    # candidates: same-world placements of the selected categories, plus
    # every cross-landed item the datapackage can name
    candidates = []
    for v in range(1, players + 1):
        for idx, parts in enumerate(fields[v - 1]):
            if parts is None:
                continue
            try:
                loc = int(parts[0])
            except ValueError:
                continue
            if loc == SPAWN_COORD or is_mw_manifest_loc(loc):
                continue
            code, pid, zone = parts[1], parts[2], parts[3]
            if code == "MW":
                owner_s, slot_s, _ = pid.split(",", 2)
                owner, slot = int(owner_s), int(slot_s)
                if owner > players:
                    raise ApConversionError(
                        "world %s already carries shadow-owned line at %s" % (v, loc))
                m_idx = manifests[owner - 1].get(slot)
                if m_idx is None:
                    raise ApConversionError(
                        "world %s MW line at %s points at missing manifest slot "
                        "%s of world %s" % (v, loc, slot, owner))
                _, _, icode, iid = fields[owner - 1][m_idx][2].split(",", 3)
                if icode == "KS" and ("KS", "1") not in export_ids:
                    # unexported keystones may never cross: a native cross-world
                    # KS is invisible to its owner's AP logic
                    raise ApConversionError(
                        "world %s keystone crossed into world %s at %s "
                        "(the AP keystone pin failed)" % (owner, v, loc))
                if not is_exportable(icode, iid):
                    if is_progression(icode, iid):
                        raise ApConversionError(
                            "cross-world progression %s|%s at %s of world %s "
                            "is not in the datapackage" % (icode, iid, loc, v))
                    continue  # unnameable filler rides the native MW fabric
                if (v, loc) in keep_locs:
                    if is_progression(icode, iid):
                        raise ApConversionError(
                            "forced cross-world %s|%s at %s of world %s: AP "
                            "mode can't model it natively or convert it" %
                            (icode, iid, loc, v))
                    continue  # forced cross-world filler stays native
                if icode == "EX":
                    iid = str(ex_export_value(iid))
                candidates.append({
                    "v": v, "loc": loc, "line": idx, "owner": owner,
                    "code": icode, "id": iid, "zone": zone,
                    "kind": "cross", "manifest_line": m_idx})
            elif (v, loc) in keep_locs:
                continue  # forced assignments stay local placements
            elif match_key(code, pid) in export_ids:
                candidates.append({
                    "v": v, "loc": loc, "line": idx, "owner": v,
                    "code": code, "id": pid, "zone": zone, "kind": "local"})
    candidates.sort(key=lambda c: (c["v"], c["loc"]))

    reserved = {p: [c for c in candidates if c["v"] == p]
                for p in range(1, players + 1)}
    exported = {p: [c for c in candidates if c["owner"] == p]
                for p in range(1, players + 1)}
    # one item per location across the game; true by construction, so a failure is a bug
    total_reserved = sum(len(r) for r in reserved.values())
    total_exported = sum(len(e) for e in exported.values())
    if total_reserved != total_exported:
        raise ApConversionError(
            "AP conversion is unbalanced across the game: %s reserved "
            "locations, %s exported items" % (total_reserved, total_exported))

    # exports fill the manifest slots conversion freed, ascending; reserved lines
    # use the shadow player's own slot space 0..n-1
    drops = [set() for _ in range(players)]
    for c in candidates:
        if c["kind"] == "cross":
            drops[c["owner"] - 1].add(c["manifest_line"])
    # a Player holds 8x32 slot bits: a grant past the cap would silently evaporate
    ap_slots = {}
    for p in range(1, players + 1):
        if len(reserved[p]) > MAX_SLOTS:
            raise ApConversionError(
                "world %s reserves %s AP slots (max %s)" %
                (p, len(reserved[p]), MAX_SLOTS))
        if len(exported[p]) > MAX_SLOTS:
            raise ApConversionError(
                "world %s exports %s AP items (max %s)" %
                (p, len(exported[p]), MAX_SLOTS))
        kept = {slot for slot, line in manifests[p - 1].items()
                if line not in drops[p - 1]}
        free = [s for s in range(MAX_SLOTS) if s not in kept]
        if len(exported[p]) > len(free):
            raise ApConversionError(
                "world %s exports %s AP items but only %s of its %s "
                "multiworld slots are free (%s still hold native "
                "cross-world items)" %
                (p, len(exported[p]), len(free), MAX_SLOTS, len(kept)))
        ap_slots[p] = free[:len(exported[p])]

    rewrites = [{} for _ in range(players)]
    for p in range(1, players + 1):
        for i, c in enumerate(reserved[p]):
            # conversion predates the room's fills: no recipient, no promised slot
            rewrites[p - 1][c["line"]] = "%s|MW|%s,%s,,-1,AP,AP Item #%s|%s" % (
                c["loc"], players + p, i, i + 1, c["zone"])

    new_texts = []
    for p in range(1, players + 1):
        out = []
        for idx, line in enumerate(worlds[p - 1]):
            if idx in drops[p - 1]:
                continue
            out.append(rewrites[p - 1].get(idx, line))
        for i2, c in enumerate(exported[p]):
            out.append("%s|MW|%s,,%s,%s|%s" % (
                -(ap_slots[p][i2] + 2), players + p, c["code"], c["id"], c["zone"]))
        new_texts.append("\n".join(out) + "\n")

    info = {
        "players": players,
        "categories": sorted(set(categories)),
        "ap_slots": ap_slots,
        "reserved": {p: [(c["loc"], i) for i, c in enumerate(reserved[p])]
                     for p in reserved},
        "exported": {p: [(c["code"], c["id"], ap_slots[p][i2])
                         for i2, c in enumerate(exported[p])]
                     for p in exported},
    }
    return new_texts, info


def build_ap_config(placements, players, world, logic_paths, key_mode,
                    spawn_zone, variations, params_id=0, death_link=False,
                    key_tiers=None):
    """One converted world's placements -> yaml config: shadow-owned MW lines are
    reserved, shadow-finder manifest entries exported, progression pinned local."""
    exported = {}
    reserved = []
    local = {}
    for raw_loc, code, pid, zone in placements:
        loc = int(raw_loc)
        if loc == SPAWN_COORD:
            continue
        if is_mw_manifest_loc(loc):
            if code != "MW":
                raise ApConversionError("non-MW line at manifest loc %s" % loc)
            finder_s, _holder, icode, iid = pid.split(",", 3)
            if int(finder_s) > players:  # exported to the AP pool
                name = ITEM_NAMES.get(match_key(icode, iid))
                if name is None:
                    raise ApConversionError(
                        "world %s exports %s|%s, which is not in the "
                        "datapackage" % (world, icode, iid))
                exported[name] = exported.get(name, 0) + 1
            elif is_progression(icode, iid):
                raise ApConversionError(
                    "world %s progression %s|%s rides a native manifest "
                    "(unconverted cross-world progression)" % (world, icode, iid))
            continue
        if code == "MW":
            owner = int(pid.split(",", 1)[0])
            if owner > players:
                if owner != players + world:
                    raise ApConversionError(
                        "world %s holds a reserved slot for shadow %s" %
                        (world, owner))
                loc_name = LOC_NAMES.get(loc)
                if loc_name is None:
                    raise ApConversionError(
                        "reserved coord %s is not in the datapackage" % loc)
                reserved.append(loc_name)
            continue
        if code in LOCAL_CODES or (code == "RB" and pid in LOCAL_RB_IDS):
            loc_name = LOC_NAMES.get(loc)
            if loc_name is None:
                raise ApConversionError(
                    "progression coord %s is not in the datapackage" % loc)
            name = local_item_name(code, pid)
            if name is not None:
                local[loc_name] = name
        # anything else (EX, unexported bonus RBs and warps, relics,
        # entrances) is invisible to AP
    # per-world counts differ by design; ap_convert checks the game-wide totals
    return make_config(exported, reserved, local, logic_paths,
                       key_mode=key_mode,
                       spawn=ap_spawn_region(resolve_spawn_zone(placements, spawn_zone)),
                       variations=variations, params_id=params_id, world=world,
                       death_link=death_link, key_tiers=key_tiers)
