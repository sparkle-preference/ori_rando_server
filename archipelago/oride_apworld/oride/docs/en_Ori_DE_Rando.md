# Ori DE Rando

Ori and the Blind Forest: Definitive Edition, as randomized by
**[orirando.com](https://orirando.com/)** — the long-running community randomizer, not a new one written for
Archipelago.

## Where is the options page?

There isn't one here. Every setting lives in the seed you roll on [orirando.com](https://orirando.com/):
logic paths, key mode, goal mode, world size, variations, and which item categories go to Archipelago. The
site emits a finished yaml per Ori world, and that yaml is what you put in `Players`. Writing one by hand does
not work — it carries the whole seed, not a set of preferences.

This game's **Multiworld Setup Guide** walks through rolling a seed, generating, and connecting the room.

## What does randomization do to this game?

Ori's pickups are shuffled among themselves: skills, teleporters, dungeon keys, health/energy/ability cells,
keystones, mapstones and spirit light are all moved around the map. The randomizer also changes how the game
plays — you start with no abilities, the world is open, and logic paths decide how much movement tech the seed
expects of you. Multiple Ori players can share one seed as an Ori multiworld, with items landing in each
other's worlds.

Archipelago sits on top of that. When the seed is rolled with Archipelago mode on, some of its pickup
locations are handed over to Archipelago's fill instead of holding Ori items, and the Ori items that would
have been there go into the Archipelago pool for anyone in the session to find.

## What items and locations get shuffled?

Locations are Ori pickup spots — 256 of them are modelled here, everything the Ori randomizer can fill.
Archipelago only owns the subset the seed reserved for it; the rest still hold Ori items and are invisible to
Archipelago.

Items are the Ori pickups from the categories you chose to export. What can appear in the pool:

* **Skills** — Bash, Charge Flame, Wall Jump, Stomp, Double Jump, Charge Jump, Climb, Glide, Dash, Grenade,
  Spirit Flame
* **Teleporters** — Grove, Swamp, Grotto, Valley, Forlorn, Sorrow, Ginso, Horu, Blackroot, Glades
* **World Events** — Water Vein, Gumon Seal, Sunstone, Clean Water, Wind Restored, Warmth Returned, and their
  shard/fragment forms in the seed modes that use them
* **Cells** — Health Cell, Energy Cell, Ability Cell
* **Stones** — Mapstone, and the per-area keystones of Keysanity seeds
* **Spirit light** — 50/100/200 experience, which the generator also uses to keep each world's give-and-take
  balanced

Generic Keystones are never exported: they are consumable door currency, and the seed's own supply rules
guarantee you can always open the door in front of you. Bonus pickups (the optional upgrades and abilities)
stay inside Ori too.

## Which items can appear in other players' worlds?

Every item from the exported categories, plus anything that a multi-world Ori game happened to place in
another Ori player's world: those cross-world items have to travel through Archipelago too, whatever their
category. In a 1-player Ori game only the exported categories leave. In a multi-player Ori game, expect
cells, keystones and spirit light in the pool as well — often most of it.

## What does another world's item look like in Ori DE Rando?

Exactly like an Ori multiworld item for another player: the pickup announces itself as belonging to
`Archipelago`, naming the item and whose world it is going to, for example
`Found Archipelago's Progressive Sword (Zelda)!`.

Those names are learned from the room, so a seed downloaded before the room was connected shows
`AP Item #1`, `AP Item #2`, … instead. Re-downloading the seed after the room connects bakes the real names
in. This is cosmetic: a seed with placeholders sends and receives exactly the same checks.

## When the player receives an item, what happens?

It arrives in game the moment it is sent, with the usual Ori multiworld pickup message and effects — a skill
becomes usable immediately, a cell raises your maximum, a teleporter unlocks. There is nothing to collect and
no client window to watch.

Ori players do not run an Archipelago client at all. orirando.com's server holds the connection to the room
for every Ori world in the game, so items flow both ways as long as the room is up and reachable; whoever
rolled the seed points the game at the room once, from the seed page.

## What is the goal?

Whatever the Ori seed's goal mode asks for — by default, collecting every skill tree and then finishing the
game through the Mount Horu escape. Completing the seed reports your goal to the Archipelago room like any
other game.
