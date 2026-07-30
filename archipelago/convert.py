"""Archipelago game-mode conversion pass over rendered multiworld seeds.

AP mode = a normal K-world multiworld seed, generated completely unchanged,
then converted before the seed text is parsed/stored: every placed instance
of an exported category becomes an AP slot. Its location line is rewritten
to an MW placeholder owned by the world's AP shadow player (pid K+world,
netcode-only), and the item itself moves to the AP pool via a manifest
entry appended to its owner's seed. See prior_notes/ARCHIPELAGO_NOTES.md
"Generator AP game mode" for the full design.

Per-world balance: AP requires exported-count == reserved-count per slot.
Cross-world landings skew this. Balancing prefers PADDING: additionally
convert a cross-world cell/bonus pickup owned by the over-slot world and
located in an over-export world (+1 export for the owner, +1 slot for the
holder -- both deficits move toward zero, and only threshold-counted or
filler items are added to the pool). Only when no pad exists does it fall
back to REVERTING a conversion (leaving the item as an ordinary native MW
pickup): reverting a singleton progression item (a skill/TP/event) makes
it invisible to its owner's AP logic and can render regions unreachable
(the E2E-discovered Wall Jump case), so that is a logged last resort.
Deficits sum to zero across worlds, so balancing always terminates.
"""
import json
import os

from archipelago.yaml_emit import (LOC_NAMES, ITEM_NAMES, make_config,
                                   SPAWN_COORD)

DATA_DIR = os.path.join(os.path.dirname(__file__), "oride_apworld", "oride", "data")

with open(os.path.join(DATA_DIR, "items.json")) as _f:
    _ITEMS = json.load(_f)
ITEM_BY_CODE_ID = {(i["code"], i["id"]): i for i in _ITEMS}

EXPORTABLE_CATEGORIES = ("skills", "teleporters", "events", "cells", "stones")
DEFAULT_EXPORT = ("skills", "teleporters", "events")
# generic keystones are consumable door currency under the generator's
# cumulative-supply invariant; exporting them breaks the per-door thresholds
# the apworld compiles (it hard-rejects them too). Keysanity zone keys and
# mapstones are what "stones" exports.
BANNED_EXPORTS = {("KS", "1")}

MAX_SLOTS = 256  # 8x32-bit slot bitfields on the Player entity: wire format

# balancing reverts eat the boring categories first, keeping skills/TPs in AP
REVERT_RANK = {"cells": 0, "stones": 1, "events": 2, "teleporters": 3, "skills": 4}

# non-exported placed progression gets pinned in the yaml so AP reachability
# mirrors the seed; everything else is invisible to AP
LOCAL_CODES = {"KS", "MS", "HC", "EC", "AC", "SK", "TP", "EV"}
LOCAL_RB_IDS = {"17", "19", "21", "28"} | {str(n) for n in range(300, 312)}

# mapstone turn-in pseudo-locations (coords 20+4n, names MS1..MS9). Their AP
# rule counts the world's Mapstone items, and in K>1 games part of that
# supply rides native manifests (invisible to AP logic, see build_ap_config)
# -- so a converted turn-in could be unreachable-by-construction, which
# accessibility:full rejects. K>1 never converts them; K=1 supply is fully
# visible, so its turn-ins convert like anything else.
MS_TURNIN_COORDS = frozenset(range(24, 57, 4))
MS_TURNIN_NAMES = frozenset("MS%d" % n for n in range(1, 10))
# the engines reserve the pool's +2 slack: 8th turn-in wants 9 stones, 9th
# wants 11 (mirrors the apworld's MAPSTONE_BUMPS)
MAPSTONE_BUMPS = {8: 9, 9: 11}

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
}


class ApConversionError(Exception):
    """AP conversion or yaml derivation can't produce a sound result."""


def export_code_ids(categories):
    """Category names -> set of exportable (code, id) pairs."""
    bad = [c for c in categories if c not in EXPORTABLE_CATEGORIES]
    if bad:
        raise ApConversionError("unknown AP export categories: %s" % ", ".join(bad))
    cats = set(categories)
    return {(i["code"], i["id"]) for i in _ITEMS
            if i["category"] in cats} - BANNED_EXPORTS


def ap_variations(variations):
    """Params variation enums (or their string values) -> apworld variations
    dict. Default seeds run with open dungeons, so open is on unless the
    ClosedDungeons variation is."""
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


def _is_manifest_loc(loc):
    return -257 <= loc <= -2


def ap_convert(texts, categories, keep_locs=frozenset()):
    """The conversion pass. texts: per-world rendered seed texts (index 0 =
    world 1, flagline + placement lines + native manifest). keep_locs:
    (world, loc) pairs that must stay local placements (forced assignments).
    Returns (new_texts, info); same inputs always yield identical outputs.
    """
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
            parts = line.split("|", 3)
            f.append(parts if len(parts) == 4 else None)
            if len(parts) != 4:
                continue
            try:
                loc = int(parts[0])
            except ValueError:
                continue
            if _is_manifest_loc(loc) and parts[1] == "MW":
                m[-loc - 2] = idx
        worlds.append(lines)
        fields.append(f)
        manifests.append(m)

    # every placed instance of an exported category, wherever it landed
    candidates = []
    for v in range(1, players + 1):
        for idx, parts in enumerate(fields[v - 1]):
            if parts is None:
                continue
            try:
                loc = int(parts[0])
            except ValueError:
                continue
            if loc == SPAWN_COORD or _is_manifest_loc(loc):
                continue
            if players > 1 and loc in MS_TURNIN_COORDS:
                continue  # K>1: turn-in reachability isn't AP-modelable
            if (v, loc) in keep_locs:
                continue  # forced assignments stay local placements
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
                _, icode, iid = fields[owner - 1][m_idx][2].split(",", 2)
                if (icode, iid) in export_ids:
                    candidates.append({
                        "v": v, "loc": loc, "line": idx, "owner": owner,
                        "code": icode, "id": iid, "zone": zone,
                        "kind": "cross", "manifest_line": m_idx})
            elif (code, pid) in export_ids:
                candidates.append({
                    "v": v, "loc": loc, "line": idx, "owner": v,
                    "code": code, "id": pid, "zone": zone, "kind": "local"})
    candidates.sort(key=lambda c: (c["v"], c["loc"]))

    # balance: deficit>0 = world hosts more AP slots than it contributes.
    # Revert cross-world conversions until every deficit is zero (each revert
    # moves one unit off the location world and one onto the owner world;
    # deficits sum to zero, so this terminates).
    deficit = {p: 0 for p in range(1, players + 1)}
    for c in candidates:
        deficit[c["v"]] += 1
        deficit[c["owner"]] -= 1
    reverted = []
    while True:
        over = [p for p in deficit if deficit[p] > 0]
        if not over:
            break
        v = min(over)
        pool = [c for c in candidates if c["kind"] == "cross" and c["v"] == v]
        if not pool:
            raise ApConversionError(
                "world %s deficit %s with no cross-world conversions to revert"
                % (v, deficit[v]))  # unreachable: deficit>0 implies inflow>0
        c = min(pool, key=lambda c: (
            0 if deficit[c["owner"]] < 0 else 1,
            REVERT_RANK[ITEM_BY_CODE_ID[(c["code"], c["id"])]["category"]],
            c["owner"], c["loc"]))
        candidates.remove(c)
        reverted.append(c)
        deficit[v] -= 1
        deficit[c["owner"]] += 1

    reserved = {p: [c for c in candidates if c["v"] == p]
                for p in range(1, players + 1)}
    exported = {p: [c for c in candidates if c["owner"] == p]
                for p in range(1, players + 1)}

    # AP manifest slots share the 0..255 space with native MW slots: continue
    # after the world's highest ORIGINALLY-used native slot (conversion frees
    # native slots but never reuses them, so this can't collide). The
    # reserved side lives in the shadow player's fresh slot space (0..n-1).
    ap_base = {}
    for p in range(1, players + 1):
        native = manifests[p - 1].keys()
        ap_base[p] = (max(native) + 1) if native else 0
        if len(reserved[p]) > MAX_SLOTS:
            raise ApConversionError(
                "world %s reserves %s AP slots (max %s)" %
                (p, len(reserved[p]), MAX_SLOTS))
        if ap_base[p] + len(exported[p]) > MAX_SLOTS:
            raise ApConversionError(
                "world %s manifest needs %s slots after %s native (max %s)" %
                (p, len(exported[p]), ap_base[p], MAX_SLOTS))

    rewrites = [{} for _ in range(players)]
    drops = [set() for _ in range(players)]
    for p in range(1, players + 1):
        for i, c in enumerate(reserved[p]):
            rewrites[p - 1][c["line"]] = "%s|MW|%s,%s,AP Item #%s|%s" % (
                c["loc"], players + p, i, i + 1, c["zone"])
    for c in candidates:
        if c["kind"] == "cross":
            drops[c["owner"] - 1].add(c["manifest_line"])

    new_texts = []
    for p in range(1, players + 1):
        out = []
        for idx, line in enumerate(worlds[p - 1]):
            if idx in drops[p - 1]:
                continue
            out.append(rewrites[p - 1].get(idx, line))
        for i2, c in enumerate(exported[p]):
            out.append("%s|MW|%s,%s,%s|%s" % (
                -(ap_base[p] + i2 + 2), players + p, c["code"], c["id"], c["zone"]))
        new_texts.append("\n".join(out) + "\n")

    info = {
        "players": players,
        "categories": sorted(set(categories)),
        "ap_base": ap_base,
        "reserved": {p: [(c["loc"], i) for i, c in enumerate(reserved[p])]
                     for p in reserved},
        "exported": {p: [(c["code"], c["id"], ap_base[p] + i2)
                         for i2, c in enumerate(exported[p])]
                     for p in exported},
        "reverted": [(c["v"], c["loc"], c["owner"], c["code"], c["id"])
                     for c in reverted],
    }
    return new_texts, info


def build_ap_config(placements, players, world, logic_paths, key_mode,
                    spawn_zone, variations, params_id=0):
    """One CONVERTED world's placement tuples -> orirando yaml config dict.

    placements: [(loc, code, id, zone)] including manifest pseudo-locs.
    Classification is by wire shape: shadow-owned MW lines are the reserved
    slots, shadow-finder manifest entries are the exported items, plain
    progression lines pin local_progression. Native MW lines (this world's
    location holding another real player's item, e.g. balancing reverts) and
    native manifest entries (this world's items landed in other worlds,
    arriving by netcode) are invisible to AP: their delivery timing is
    unknowable to AP logic, and omitting them is strictly sound -- rules
    just never rely on them. K=1 has neither.
    """
    exported = {}
    reserved = []
    local = {}
    for raw_loc, code, pid, zone in placements:
        loc = int(raw_loc)
        if loc == SPAWN_COORD:
            continue
        if _is_manifest_loc(loc):
            if code != "MW":
                raise ApConversionError("non-MW line at manifest loc %s" % loc)
            finder_s, icode, iid = pid.split(",", 2)
            if int(finder_s) > players:  # exported to the AP pool
                name = ITEM_NAMES[(icode, iid)]
                exported[name] = exported.get(name, 0) + 1
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
            local[loc_name] = ITEM_NAMES[(code, pid)]
        # anything else (EX, bonus RBs, warps, relics, entrances) is
        # invisible to AP
    # In K>1 games part of this world's Mapstone supply landed in other
    # worlds and rides native manifests -- invisible above, so turn-ins
    # whose threshold exceeds the AP-visible supply are unreachable by
    # construction. Drop their local pins: losing an available item is
    # strictly stricter, therefore sound (the seed still delivers it by
    # netcode). Supply counts pins at regular locations plus this world's
    # exported Mapstones; pins AT turn-ins are excluded (they only become
    # collectable through a turn-in themselves). K=1 supply is fully
    # visible and the AP sweep models progressive turn-in collection
    # exactly (difftest-proven), so it keeps every pin.
    if players > 1:
        ms_available = exported.get("Mapstone", 0) + sum(
            1 for name, item in local.items()
            if item == "Mapstone" and name not in MS_TURNIN_NAMES)
        for n in range(1, 10):
            name = "MS%d" % n
            if name in local and MAPSTONE_BUMPS.get(n, n) > ms_available:
                del local[name]
    if sum(exported.values()) != len(reserved):
        raise ApConversionError(
            "world %s: %s exported != %s reserved (unbalanced conversion?)" %
            (world, sum(exported.values()), len(reserved)))
    return make_config(exported, reserved, local, logic_paths,
                       key_mode=key_mode, spawn=ap_spawn_region(spawn_zone),
                       variations=variations, params_id=params_id, world=world)
