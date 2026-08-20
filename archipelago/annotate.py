"""Download-time annotation of an AP-mode world's seed text.

The conversion pass runs at generation, before Archipelago has filled
anything, so a freshly generated seed can only say "AP Item #n" and can only
guess where an exported item went. Once the room has been connected each
world scouts its own reserved locations, and the K scout rows together say a
lot more. This pass rewrites the seed at download time:

  reserved line   <coord>|MW|<K+w>,<slot>,<label>|<zone>|<recipient>;<item>[|<own slot>]
  manifest line   -(slot+2)|MW|<K+w>,<code>,<id>|<true zone>|<holder>

Field 6 rides only reserved lines holding our own item, naming the manifest
slot it lands in so the client can grant it on contact. Its values are the
bridge's own persisted promise map, not a local re-derivation.

Fields 5 and 6 are additive and the four fields before them are untouched: every
shipped client splits a seed line on '|' and reads indices 0..3 only, so an
old dll drops field 5 and behaves exactly as it does today -- which is why
the reserved line keeps the combined "<item> (<recipient>)" label in the
comma field and repeats the bare item in field 5. Seeds downloaded before
the room is connected have no scout rows and pass through untouched.

WHAT THE JOIN CAN AND CANNOT SEE. LocationScouts only answers about the
asking slot's own locations, so the K worlds between them know where an
exported item landed exactly when it landed in one of THEM. Anything
Archipelago put in a foreign game is invisible: those keep the holder
"Archipelago" and lose the zone, because the rolled zone is where the item
was taken FROM and measured wrong for 55 of 58 exports on a real room.
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
    """Every scouted resting place of world w's own exported items.

    -> {datapackage key: [(holder token, true zone), ...]} across the K
    worlds. Copies that landed in foreign games are invisible to scouts and
    simply absent from the lists."""
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
    """The UNAMBIGUOUS subset of _holder_hits: exactly one copy found across
    the K worlds. Several copies in flight are indistinguishable per-line in
    the room's answers, so line annotation declines rather than guesses."""
    return {key: hits[0] for key, hits
            in _holder_hits(players, world, rows, seed_data_for).items()
            if len(hits) == 1}


def annotate(seed_data, players, world, rows, seed_data_for, promises=None):
    """Seed tuples -> seed tuples, this world's AP lines gaining a 5th field
    (and a 6th where the item is our own).

    rows: {world: (APNames entries, that world's room slot)}; a world that
    has never scouted contributes nothing. seed_data_for(v) yields world v's
    raw placement tuples, which is where the join reads reserved zones.

    promises: the bridge's persisted {shadow slot: manifest slot} map, baked
    into field 6 VERBATIM -- the self-item draw lives in ap_bridge only, so
    the client grants exactly what the bridge fills. With no blob, no field
    6 at all: the tick still delivers, only the contact-grant priming is
    lost, and an abstention cannot dupe."""
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
