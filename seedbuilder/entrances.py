"""Entrance shuffle's doors, and the logic rules shared by everything that walks an Entrance world."""

# PlandoBuilder's DOORS order: the client's touched-door bitfield uses these indices
DOORS = [
    ("GinsoInnerDoor", 522, 1), ("ForlornInnerDoor", -717, -408), ("HoruInnerDoor", 68, 169),
    ("L1InnerDoor", -24, 369), ("L2InnerDoor", -13, 301), ("L3InnerDoor", -28, 244), ("L4InnerDoor", -12, 188),
    ("R2InnerDoor", 163, 266), ("R3InnerDoor", 171, 218), ("R4InnerDoor", 144, 151), ("HoruEscapeInnerDoor", -242, 489),
    ("GinsoOuterDoor", 527, -43), ("ForlornOuterDoor", -668, -246), ("HoruOuterDoor", -78, 2),
    ("L1OuterDoor", 20, 371), ("L2OuterDoor", 13, 293), ("L3OuterDoor", 18, 248), ("L4OuterDoor", 14, 191),
    ("R2OuterDoor", 128, 288), ("R3OuterDoor", 126, 245), ("R4OuterDoor", 126, 196), ("HoruEscapeOuterDoor", 18, 100),
    ("R1OuterDoor", 125, 382), ("R1InnerDoor", 153, 413),
]
DOOR_NAMES = frozenset(name for name, _, _ in DOORS)
DOOR_BY_COORDS = {(x, y): name for name, x, y in DOORS}
# every seed sends R1 Outer to R1 Inner, so its line is known before the door is used
ALWAYS_KNOWN = frozenset(["R1OuterDoor"])

# generator.py's Entrance + Shards teleporters each also want two of their dungeon's shards: {target: (token, shard)}
SHARD_TELEPORTERS = {"GinsoTeleporter": ("TwoWaterVeinShards", "RB17"), "ForlornTeleporter": ("TwoGumonSealShards", "RB19"),
                     "HoruTeleporter": ("TwoSunstoneShards", "RB21")}

_KEY_DOORS = {"GinsoKey": "GinsoOuterDoor", "ForlornKey": "ForlornOuterDoor", "HoruKey": "HoruOuterDoor"}


def door_key(x, y):
    """Door.get_key(): the door's coordinates floored to the 4-unit grid."""
    return (x // 4) * 4 * 10000 + (y // 4) * 4


def keys_only_for_doors(home, target, path):
    """A dungeon key gates only the walk into its own outer door from outside."""
    path = list(path)
    for key, door in _KEY_DOORS.items():
        if key in path and (target != door or "InnerDoor" in home):
            path.remove(key)
    return path


def is_door_edge(home, target):
    """A conn from a shuffled door through to another door: vanilla wiring an Entrance world replaces."""
    return home in DOOR_NAMES and ("OuterDoor" in target or "InnerDoor" in target)


def parse_entrances(rows):
    """{door key: (x, y)} from a world's seed rows (loc, code, id, ...); EN ids are "x|y"."""
    out = {}
    for row in rows:
        if row[1] != "EN":
            continue
        try:
            x, y = str(row[2]).split("|")[:2]
            out[int(row[0])] = (int(x), int(y))
        except ValueError:
            continue
    return out


def known_edges(entrances, touched=None):
    """{door: {target door}} for the doors the player knows; touched=None knows them all.
    A target that isn't a door (plando's raw coordinates) has no logic node, so it adds nothing."""
    edges = {}
    for i, (name, x, y) in enumerate(DOORS):
        target = entrances.get(door_key(x, y))
        if target is None:
            continue
        if touched is not None and not (touched >> i) & 1 and name not in ALWAYS_KNOWN:
            continue
        dest = DOOR_BY_COORDS.get(target)
        if dest:
            edges.setdefault(name, set()).add(dest)
    return edges
