"""Token vocabulary shared between areas.ori requirements and AP item names.

The expansion tables mirror seedbuilder/generator.py:19-26 exactly; the
name maps mirror pickups.py display names and generator.py:444. Divergence
here silently corrupts logic -- the differential reach test is the guard.
"""

# requirement token -> AP item name (all count 1)
SIMPLE_ITEM_TOKENS = {
    "Bash": "Bash", "ChargeFlame": "Charge Flame", "WallJump": "Wall Jump",
    "Stomp": "Stomp", "DoubleJump": "Double Jump", "ChargeJump": "Charge Jump",
    "Climb": "Climb", "Glide": "Glide", "Dash": "Dash", "Grenade": "Grenade",
    "SpiritFlame": "Spirit Flame",
    "TPGrove": "Grove teleporter", "TPSwamp": "Swamp teleporter",
    "TPGrotto": "Grotto teleporter", "TPValley": "Valley teleporter",
    "TPForlorn": "Forlorn teleporter", "TPSorrow": "Sorrow teleporter",
    "TPGinso": "Ginso teleporter", "TPHoru": "Horu teleporter",
    "TPBlackroot": "Blackroot teleporter", "TPGlades": "Glades teleporter",
    "Water": "Clean Water", "Wind": "Wind Restored", "Warmth": "Warmth Returned",
    "WaterVeinShard": "Water Vein Shard", "GumonSealShard": "Gumon Seal Shard",
    "SunstoneShard": "Sunstone Shard",
}

# Health=N / Keystone=N style tokens -> counted AP item
LONGFORM_ITEMS = {
    "Health": "Health Cell", "Energy": "Energy Cell", "Ability": "Ability Cell",
    "Keystone": "Keystone", "Mapstone": "Mapstone",
}

# dungeon key tokens; resolution depends on the seed's key mode
KEY_EVENT_ITEMS = {"GinsoKey": "Water Vein", "ForlornKey": "Gumon Seal", "HoruKey": "Sunstone"}
KEY_SHARD_ITEMS = {"GinsoKey": ("Water Vein Shard", 5), "ForlornKey": ("Gumon Seal Shard", 5),
                   "HoruKey": ("Sunstone Shard", 5)}

# keysanity area-key tokens -> (item, count); mirrors generator.py keysanity_map
KEYSANITY_TOKENS = {
    "GladesPoolKeys": ("Glades Pool Keystone", 2), "LowerSpiritCavernsKeys": ("Lower Spirit Caverns Keystone", 2),
    "GrottoKeys": ("Grotto Keystone", 2), "SwampKeys": ("Swamp Keystone", 2),
    "UpperSpiritCavernsKeys": ("Upper Spirit Caverns Keystone", 4), "LowerGinsoKeys": ("Lower Ginso Keystone", 4),
    "UpperGinsoKeys": ("Upper Ginso Keystone", 4), "MistyKeys": ("Misty Keystone", 4),
    "ForlornKeys": ("Forlorn Keystone", 4), "LowerSorrowKeys": ("Lower Sorrow Keystone", 4),
    "MidSorrowKeys": ("Mid Sorrow Keystone", 4), "UpperSorrowKeys": ("Upper Sorrow Keystone", 4),
}

# variation-flag pseudo-tokens, resolved from the yaml's variations dict
VARIATION_TOKENS = {"Open": "open", "OpenWorld": "open_world", "Keysanity": "keysanity"}

# Generic-keystone door edges in canonical order, with in-game key costs.
# When generic Keystones ride the AP pool, doors can't use face costs (any
# spend order must stay safe), so each door requires the CUMULATIVE cost of
# its tier prefix: at count C every door you could have opened lies in the
# prefix whose total is <= C, so the door in front of you is always payable.
# Any fixed order is sound -- the seed's yaml/flagline carry per-world tiers
# ranked by the generator's own walk (spawn, TPs and logic shape it), and
# this list is the POSITION identity for those values plus the fallback
# ranking when no walk order is available. Append, don't reorder.
KEYSTONE_DOORS = [
    ("GladesFirstKeyDoor", "GladesFirstKeyDoorOpened", 2),
    ("SpiritCavernsDoor", "SpiritCavernsDoorOpened", 2),
    ("GumoHideout", "DoubleJumpKeyDoor", 2),
    ("SwampKeyDoorPlatform", "SwampKeyDoorOpened", 2),
    ("SpiritTreeDoor", "SpiritTreeDoorOpened", 4),
    ("BashTreeDoorClosed", "BashTreeDoorOpened", 4),
    ("UpperGinsoDoorClosed", "UpperGinsoDoorOpened", 4),
    ("MistyBeforeMiniBoss", "MistyOrbRoom", 4),
    ("ForlornKeyDoor", "ForlornKeyDoorOpened", 4),
    ("LowerSorrow", "LeftSorrowLowerDoor", 4),
    ("LeftSorrowMiddleDoorClosed", "LeftSorrowMiddleDoorOpen", 4),
    ("ChargeJumpDoor", "ChargeJumpDoorOpen", 4),
]


def keystone_door_tiers(variations):
    """(home, target) -> cumulative threshold, for doors live under these
    (apworld-form) variations. OpenWorld pre-opens the Glades door, which
    also shifts every later tier down by its cost."""
    tiers, total = {}, 0
    for home, target, cost in KEYSTONE_DOORS:
        if variations.get("open_world") and home == "GladesFirstKeyDoor":
            continue
        total += cost
        tiers[(home, target)] = total
    return tiers
