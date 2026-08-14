"""Download-time annotation of an AP-mode world's seed text.

The conversion pass runs at generation, before Archipelago has filled
anything, so a freshly generated seed can only say "AP Item #n" and can only
guess where an exported item went. Once the room has been connected each
world scouts its own reserved locations, and the K scout rows together say a
lot more. This pass rewrites the seed at download time:

  reserved line   <coord>|MW|<K+w>,<slot>,<label>|<zone>|<recipient>;<item>[|<own slot>]
  manifest line   -(slot+2)|MW|<K+w>,<code>,<id>|<true zone>|<holder>

Field 6 rides only reserved lines holding our own item, naming the manifest
slot it lands in so the client can grant it on contact.

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
    """(slot, label) if this is a reserved AP line of the given shadow."""
    if code != "MW":
        return None
    parts = id.split(",", 2)
    if len(parts) != 3 or parts[0] != shadow or not parts[1].isdigit():
        return None
    return int(parts[1]), parts[2]


def _exports(seed_data, shadow):
    """This world's manifest slots -> the datapackage key each exports."""
    out = {}
    for loc, code, id, zone in seed_data:
        if code != "MW" or not is_mw_manifest_loc(int(loc)):
            continue
        finder, icode, iid = id.split(",", 2)
        if finder != shadow:
            continue
        out[-int(loc) - 2] = match_key(icode, iid)
    return out


def _holders(players, world, rows, seed_data_for):
    """Where each of world w's exported items actually sits.

    -> {datapackage key: (holder token, true zone)} for the keys the join
    identifies UNAMBIGUOUSLY: exactly one copy found across the K worlds.
    Several copies in flight are indistinguishable in the room's answers, so
    they are left out rather than guessed at.
    """
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
    return {key: hits[0] for key, hits in found.items() if len(hits) == 1}


def _own_slot(scout, our_slot, own_pool):
    """Field 6: the manifest slot a self-item will land in, so the client can
    grant it on contact instead of waiting out the room round trip. Handed
    out without replacement: every copy of a duplicated item needs its own
    slot, or the client mistakes the second copy for a re-touch."""
    if our_slot is None or scout.ap_owner != our_slot:
        return None
    key = ITEM_BY_AP_ID.get(scout.ap_item)
    if key is None:
        return None
    pool = own_pool.get(key)
    return pool.pop(0) if pool else None


def annotate(seed_data, players, world, rows, seed_data_for):
    """Seed tuples -> seed tuples, this world's AP lines gaining a 5th field
    (and a 6th where the item is our own).

    rows: {world: (APNames entries, that world's room slot)}; a world that
    has never scouted contributes nothing. seed_data_for(v) yields world v's
    raw placement tuples, which is where the join reads reserved zones.
    """
    entries, our_slot = rows.get(world, ({}, None))
    if not entries:
        return seed_data
    shadow = str(int(players) + int(world))
    exports = _exports(seed_data, shadow)
    holders = _holders(players, world, rows, seed_data_for)
    counts = {}
    for key in exports.values():
        counts[key] = counts.get(key, 0) + 1
    # field-6 slot pools, consumed in seed-line order: stable across downloads
    own_pool = {}
    for slot, key in sorted(exports.items()):
        own_pool.setdefault(key, []).append(slot)
    out = []
    for line in seed_data:
        loc, code, id, zone = line
        if is_mw_manifest_loc(int(loc)):
            key = exports.get(-int(loc) - 2)
            hit = holders.get(key) if key is not None and counts.get(key) == 1 else None
            if hit:
                line = (loc, code, id, hit[1], hit[0])
            else:
                # the rolled zone is where the item was taken FROM, wrong for
                # nearly every export once the room refills (55 of 58 on a
                # real room -- game 135658's door hints). An entry the join
                # can't place keeps custody and no zone; the holder must be
                # non-empty or shipped clients fall back to "P<shadow>".
                line = (loc, code, id, "", FOREIGN_HOLDER)
        else:
            held = _reserved_slot(code, id, shadow)
            scout = entries.get(held[0]) if held else None
            if scout is not None:
                fields = [loc, code, "%s,%s,%s" % (shadow, held[0], scout.label()),
                          zone, "%s;%s" % (scout.to, scout.item)]
                mine = _own_slot(scout, our_slot, own_pool)
                if mine is not None:
                    fields.append(str(mine))
                line = tuple(fields)
        out.append(line)
    return out
