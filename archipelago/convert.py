"""Archipelago game-mode conversion pass over rendered multiworld seeds.

AP mode = a normal K-world multiworld seed, generated unchanged (except the
AP-only keystone pin in the generator), then converted before the seed text
is parsed/stored. Converted placements become AP slots: the host location
line is rewritten to an MW placeholder owned by the host world's AP shadow
player (pid K+world, netcode-only), and the item moves to the AP pool via a
manifest entry appended to its owner's seed. See
prior_notes/ARCHIPELAGO_NOTES.md "Generator AP game mode" for the design.

What converts:
- Same-world placements of the user-selected export categories.
- EVERY cross-landed progression item, regardless of selection: a native MW
  manifest line is invisible to its owner's AP logic, so any logic-relevant
  item left native under-models the world and breaks accessibility (the
  E2E-discovered Misty Ability Cell case).
- Cross-landed EX, exported under the nearest denomination (50/100/200
  experience); the manifest entry keeps the true value, so exact in-game
  amounts survive (the bridge maps by slot, not name).
Generic keystones never convert AND never cross (the generator pins them to
their owner's world in AP mode); bonus RBs, warps and relics may stay native
cross-world -- invisible to AP logic and harmless.

Per-world balance: AP requires exported-count == reserved-count per slot.
Cross-world drift skews this, so conversion REVERTS cross-landed EX
conversions (revert = back to a native MW line, harmless for filler) until
every deficit is zero. Progression conversions are mandatory and never
reverted. A single revert strictly reduces total imbalance exactly when its
host world over-reserves and its owner world over-exports; deficits sum to
zero and cross EX is plentiful, so balancing effectively always succeeds --
if no such revert exists the conversion fails cleanly.
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

# everything the apworld's logic can see. Placed instances pin local when
# same-world and un-selected, export otherwise; nothing progression may ride
# a native manifest.
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
}


class ApConversionError(Exception):
    """AP conversion or yaml derivation can't produce a sound result."""


def is_progression(code, pid):
    return code in LOCAL_CODES or (code == "RB" and pid in LOCAL_RB_IDS)


def nearest_ex_denom(value):
    """True EX value -> datapackage denomination (ties round down)."""
    return min(EX_DENOMS, key=lambda d: (abs(d - int(value)), d))


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

    # candidates: same-world placements of the selected categories, every
    # cross-landed progression item, and cross-landed EX (balancing currency)
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
                if icode == "KS":
                    raise ApConversionError(
                        "world %s keystone crossed into world %s at %s "
                        "(the AP keystone pin failed)" % (owner, v, loc))
                if not is_progression(icode, iid) and icode != "EX":
                    continue  # filler may ride the native MW fabric
                if (v, loc) in keep_locs:
                    if is_progression(icode, iid):
                        raise ApConversionError(
                            "forced cross-world %s|%s at %s of world %s: AP "
                            "mode can't model it natively or convert it" %
                            (icode, iid, loc, v))
                    continue  # forced cross-world filler stays native
                candidates.append({
                    "v": v, "loc": loc, "line": idx, "owner": owner,
                    "code": icode, "id": iid, "zone": zone,
                    "kind": "cross", "manifest_line": m_idx})
            elif (v, loc) in keep_locs:
                continue  # forced assignments stay local placements
            elif (code, pid) in export_ids:
                candidates.append({
                    "v": v, "loc": loc, "line": idx, "owner": v,
                    "code": code, "id": pid, "zone": zone, "kind": "local"})
    candidates.sort(key=lambda c: (c["v"], c["loc"]))

    # balance: deficit>0 = world hosts more AP slots than it exports.
    # Revert cross-landed EX until every deficit is zero.
    deficit = {p: 0 for p in range(1, players + 1)}
    for c in candidates:
        deficit[c["v"]] += 1
        deficit[c["owner"]] -= 1
    reverted = []
    ex_pool = sorted((c for c in candidates
                      if c["kind"] == "cross" and c["code"] == "EX"),
                     key=lambda c: (c["owner"], c["v"], c["loc"]))
    while any(deficit[p] for p in deficit):
        c = next((c for c in ex_pool
                  if deficit[c["v"]] > 0 and deficit[c["owner"]] < 0), None)
        if c is None:
            raise ApConversionError(
                "can't balance AP export with EX reverts: deficits %s" %
                {p: d for p, d in sorted(deficit.items()) if d})
        ex_pool.remove(c)
        candidates.remove(c)
        reverted.append(c)
        deficit[c["v"]] -= 1
        deficit[c["owner"]] += 1

    reserved = {p: [c for c in candidates if c["v"] == p]
                for p in range(1, players + 1)}
    exported = {p: [c for c in candidates if c["owner"] == p]
                for p in range(1, players + 1)}

    # AP manifest entries share the 0..255 slot space with native MW slots.
    # Conversion drops most native entries, freeing their slots; nothing
    # references a dropped slot, so exports fill the gaps in ascending order
    # (the generator itself reuses freed slots the same way). The reserved
    # side lives in the shadow player's fresh slot space (0..n-1).
    drops = [set() for _ in range(players)]
    for c in candidates:
        if c["kind"] == "cross":
            drops[c["owner"] - 1].add(c["manifest_line"])
    # A player carries 8x32 slot bits and nothing more (models.Player.
    # mark_slot refuses 256+), so a surplus has nowhere to live: the seed
    # would render fine and every grant past the cap would evaporate.
    # Balancing leaves reserved == exported, so the live check is the
    # free-slot one; the flat caps hold the line if that ever changes.
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
            rewrites[p - 1][c["line"]] = "%s|MW|%s,%s,AP Item #%s|%s" % (
                c["loc"], players + p, i, i + 1, c["zone"])

    new_texts = []
    for p in range(1, players + 1):
        out = []
        for idx, line in enumerate(worlds[p - 1]):
            if idx in drops[p - 1]:
                continue
            out.append(rewrites[p - 1].get(idx, line))
        for i2, c in enumerate(exported[p]):
            out.append("%s|MW|%s,%s,%s|%s" % (
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
    progression lines pin local_progression. The only things still riding
    the native MW fabric are filler (reverted EX, bonus RBs, warps):
    invisible to AP, and omitting filler is sound -- rules never rely on
    it. A progression item on a native manifest means the conversion pass
    failed, so yaml derivation fails with it. K=1 has no native MW lines.
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
                if icode == "EX":
                    name = ITEM_NAMES[("EX", str(nearest_ex_denom(iid)))]
                else:
                    name = ITEM_NAMES[(icode, iid)]
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
            local[loc_name] = ITEM_NAMES[(code, pid)]
        # anything else (EX, bonus RBs, warps, relics, entrances) is
        # invisible to AP
    if sum(exported.values()) != len(reserved):
        raise ApConversionError(
            "world %s: %s exported != %s reserved (unbalanced conversion?)" %
            (world, sum(exported.values()), len(reserved)))
    return make_config(exported, reserved, local, logic_paths,
                       key_mode=key_mode, spawn=ap_spawn_region(spawn_zone),
                       variations=variations, params_id=params_id, world=world)
