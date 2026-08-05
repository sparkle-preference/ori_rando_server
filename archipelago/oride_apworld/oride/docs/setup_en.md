# Ori DE Rando Setup Guide

## Overview

Ori seeds are rolled on **[orirando.com](https://orirando.com/)**, the Ori 1 solo randomizer site.
When you tick the Archipelago option there, the generator reserves some of the seed's pickup locations 
for Archipelago and hands the items that were in them to the Archipelago item pool. It then creates the
yaml you feed to Archipelago's generator, covering every Ori world. You never write that yaml by hand,
and the player-options page on the website does not apply to this game.

Using this system, players can use their existing ori rando installation and do not need an archipelago client;
The ori rando website handles the connection to the archipelago server instead. All that is required is an
up-to-date randomizer install and an internet connection.

## What you need

* **Ori and the Blind Forest: Definitive Edition** (steam or GoG version), plus the Ori randomizer mod:
  * Copy the [randomizer dll](https://orirando.com/dll) into your `Ori DE/oriDE_Data/Managed` folder.
  * Step-by-step instructions are in the [install FAQ](https://orirando.com/faq?g=install).
  * Optional but recommended: the [item tracker](https://orirando.com/tracker).
* **Archipelago 0.6.7 or newer**, from the
  [Archipelago releases page](https://github.com/ArchipelagoMW/Archipelago/releases/latest).
* **`oride.apworld`**, the file this guide comes with. The current build is always a download away on the seed
  page — see step 1.
* Join the [Ori Discord](https://orirando.com/discord) — it is the best place to get help.

Every Ori player needs the game and the randomizer dll. Only the person generating the Archipelago session
needs Archipelago itself and this apworld.

## 1. Install the apworld

Get `oride.apworld` from the **Get apworld** button in the *Archipelago Setup* panel on the seed page — that is
always the build the site is currently serving. (Direct link, if you have no seed yet:
[orirando.com/generator/apworld](https://orirando.com/generator/apworld).)

Put it in your Archipelago install's **`custom_worlds`** folder (next to `ArchipelagoLauncher.exe`; create the
folder if it is not there). Overwrite the old version when you update, and do not change the file name.

You can check it took by launching `ArchipelagoLauncher` and generating; the generator log lists
`Ori DE Rando` with its item and location counts.

While Ori DE Rando is in closed testing, the apworld build and the seeds have to match. If they do not, the
generator will tell you which side to update — see [Troubleshooting](#troubleshooting).

## 2. Roll the Ori seed(s) on orirando.com

1. Go to [orirando.com](https://orirando.com/).
2. Pick your logic paths, key mode, goal and so on as you would for any Ori seed — anything except the Bingo
   goal, which Archipelago can't use.
3. On the **Multiplayer Options** tab, set **Players** to the number of Ori players. 1 is fine — one Ori world
   inside somebody else's Archipelago session. With 2 or more, also set **Multiplayer Game Type** to
   **Multiworld**.
4. Press the **Archipelago** button that appears.
5. Choose which kinds of item get handed to Archipelago's pool with the **Export …** buttons:
   *Export Skills*, *Export Teleporters* and *Export World Events* are on by default; *Export Cells* and
   *Export Stones* are optional. A category cannot be both Shared and Exported, so selecting one deselects
   the other. With more than one Ori player, items that land in another Ori world travel through Archipelago
   as well regardless of category — so a multi-player game exports more than you picked here.
6. Generate the seed and keep the page open, but don't download or distribute the seed files just yet.

## 3. Download the yamls

The Seed tab's **Archipelago Setup** panel has a **Get YAMLs** button. It downloads one file covering every
Ori world in the game, with slot names `Ori1`, `Ori2`, … — one Archipelago slot per Ori world.

Put it in your Archipelago install's **`Players`** folder, alongside the yamls for every other game in the
session. Only the session host needs it.

Do not edit it. The `orirando` block in each world is the whole Ori seed: which locations Archipelago owns,
which items it was given, and enough of the seed's logic for Archipelago to know what is reachable.

## 4. Generate the session

Run `ArchipelagoLauncher` → **Generate**, or `python Generate.py` from an Archipelago source install. This
produces an `AP_<seed>.zip` in `output/`, the same as for any other session.

If generation fails, read the message: this world checks its input up front and says which slot and what is
wrong.

## 5. Host the room

Host the archipleago room, either using archipelago.gg or elsewhere.
* **[archipelago.gg](https://archipelago.gg/uploads)** — upload the `AP_<seed>.zip`, and use the host and
  port the room page shows you (something like `archipelago.gg:38281`). This is the generally recommended
  option.
* **Self-hosted** — you can run `ArchipelagoServer` yourself if you want to, but the room has to be
  reachable from the internet.

## 6. Connect the room to the Ori game

Back on the seed page from step 2 (the URL with `param_id` and `game_id`), scroll to the
**Archipelago Room** panel under the seed rows:

1. Type the room's **host** and **port**, plus the room **password** if it has one.
2. Hit **Connect**.
3. Within a few seconds the status line should read **connected**. Each Ori world gets a row showing its slot
   name, how many items the room has sent it, and how many of its Archipelago locations it can name.

If it says **reconnecting** with an error underneath, the room is not reachable — check the address and port.
The bridge keeps retrying on its own, so fixing the room is enough; you do not have to click Connect again. 
To point the game at a *different* room, hit Disconnect first, then Connect.

## 7. Download the seeds after connecting

Each Ori world's row has a **Download Seed** button that gives you `randomizer.dat`. Put it next to
`OriDE.exe` in your Ori install (the same folder, not `oriDE_Data`).

**Connect the room before handing seeds out.** Until the bridge has joined the room, nobody knows what
Archipelago put in the reserved locations, so a seed downloaded early calls them all `AP Item #1`,
`AP Item #2`, and so on. Once every world reports its item names — the panel says so — download again and the
real names are baked in, so the game announces things like `Found Archipelago's Progressive Sword (Zelda)!`.

Send the other Ori players the URL of the seed page so they can grab their own world's seed.

## 8. Play

Play the Ori seed normally. Picking up a location Archipelago owns sends the check to the room; items other
games find for you arrive in game the same way Ori multiworld items always have. Finishing the seed's goal
reports your goal to the room; what happens to your remaining items after that is up to the room's release
settings.

## Troubleshooting

**"it was made for … data version N" / "this oride.apworld needs at least N"** — the apworld build and
the yaml are from different generations of the item tables. The message says which side is behind: either
re-download `oride.apworld` from the seed page's **Get apworld** button, or re-download the yaml with the
**Get YAMLs** button (a fresh yaml for the same seed is fine).

**"empty orirando data"** — the yaml did not come from orirando.com's Archipelago mode, or the `orirando`
block was emptied. Download it again from the seed page.

**"exported item count X != reserved location count Y"** — Corrupted Yaml. Redownload and try again.

**The room panel is stuck on "reconnecting"** — orirando.com cannot reach the room. The error line under the
status usually says exactly why. Use an archipelago.gg room if you are not sure.

**Some other issue** - come tell us about it in [our discord](https://orirando.com/discord).