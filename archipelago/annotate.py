"""Download-time annotation of an AP-mode world's seed text from the K scout rows.

  reserved line   <coord>|MW|<K+w>,<slot>,<label>|<zone>|<recipient>;<item>[|<own slot>]
  manifest line   -(slot+2)|MW|<K+w>,<code>,<id>|<true zone>|<holder>

Fields 0..3 are untouched (old clients read only those). Field 6, on own-item
reserved lines, is the bridge's persisted promise map verbatim. Items placed in
a foreign game are invisible to scouts: holder "Archipelago", no zone.
"""
from archipelago.convert import ITEM_BY_AP_ID, match_key
from util import is_mw_manifest_loc

FOREIGN_HOLDER = "Archipelago"


def _reserved_slot(code, id, shadow):
    """(slot, item code, item id) if this is a reserved AP line of the shadow."""
    if code != "MW":
        return None
    parts = id.split(",", 5)
    if len(parts) != 6 or parts[0] != shadow or not parts[1].isdigit():
        return None
    return int(parts[1]), parts[4], parts[5]


def _exports(seed_data, shadow):
    """This world's manifest slots -> the datapackage key each exports."""
    out = {}
    for loc, code, id, zone in seed_data:
        if code != "MW" or not is_mw_manifest_loc(int(loc)):
            continue
        finder, _holder, icode, iid = id.split(",", 3)
        if finder != shadow:
            continue
        out[-int(loc) - 2] = match_key(icode, iid)
    return out


def _holder_hits(players, world, rows, seed_data_for):
    """Scouted resting places of world w's exported items across the K worlds.
    -> {datapackage key: [(holder token, true zone), ...]}"""
    _, our_slot = rows.get(world, ({}, None))
    if our_slot is None:
        return {}
    found = {}
    for v in range(1, players + 1):
        entries, _ = rows.get(v, ({}, None))
        if not entries:
            continue
        zones = {}
        for loc, code, id, zone in seed_data_for(v):
            held = _reserved_slot(code, id, str(players + v))
            if held:
                zones[held[0]] = zone
        for slot, scout in entries.items():
            if scout.ap_owner != our_slot:
                continue
            key = ITEM_BY_AP_ID.get(scout.ap_item)
            if key is not None:
                found.setdefault(key, []).append(("P%s" % v, zones.get(slot, "")))
    return found


def _holders(players, world, rows, seed_data_for):
    """_holder_hits keys with exactly one copy found; several copies can't be
    told apart per line."""
    return {key: hits[0] for key, hits
            in _holder_hits(players, world, rows, seed_data_for).items()
            if len(hits) == 1}


def annotate(seed_data, players, world, rows, seed_data_for, promises=None):
    """Seed tuples with this world's AP lines annotated. rows: {world: (APNames
    entries, room slot)}; promises: persisted blob, or None for no field 6."""
    entries, our_slot = rows.get(world, ({}, None))
    if not entries:
        return seed_data
    shadow = str(int(players) + int(world))
    exports = _exports(seed_data, shadow)
    holders = _holders(players, world, rows, seed_data_for)
    counts = {}
    for key in exports.values():
        counts[key] = counts.get(key, 0) + 1
    out = []
    for line in seed_data:
        loc, code, id, zone = line
        if is_mw_manifest_loc(int(loc)):
            key = exports.get(-int(loc) - 2)
            hit = holders.get(key) if key is not None and counts.get(key) == 1 else None
            # an unplaced entry keeps custody and no zone; the holder must stay
            # non-empty or the client renders the finder as "P<shadow>"
            holder, true_zone = hit if hit else (FOREIGN_HOLDER, "")
            finder, _, item = id.split(",", 2)
            line = (loc, code, "%s,%s,%s" % (finder, holder, item), true_zone)
        else:
            held = _reserved_slot(code, id, shadow)
            scout = entries.get(held[0]) if held else None
            if scout is not None:
                # an Ori item keeps its own code so the client can classify it;
                # anything from another game has only the name the room gave it
                pair = ITEM_BY_AP_ID.get(scout.ap_item)
                icode, iid = pair if pair else ("AP", scout.item)
                mine = promises.get(held[0]) if promises else None
                line = (loc, code, "%s,%s,%s,%s,%s,%s" % (
                    shadow, held[0], scout.to, -1 if mine is None else mine, icode, iid), zone)
        out.append(line)
    return out
