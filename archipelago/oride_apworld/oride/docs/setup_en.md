# Ori DE Rando Setup Guide

## Read this first: how this world is different

Most Archipelago worlds roll their randomization inside the apworld. This one does not.

Ori seeds are rolled on **[orirando.com](https://orirando.com/)**, the Ori and the Blind Forest: Definitive
Edition randomizer site. When you tick the Archipelago option there, the generator reserves some of the seed's
pickup locations for Archipelago and hands the items that were in them to the Archipelago item pool. It then
emits a ready-made **yaml per Ori world**, which is what you feed to Archipelago's generator. You never write
that yaml by hand, and the player-options page on the website does not apply to this game.

The second unusual part: **Ori players do not run an Archipelago client.** orirando.com's own server holds one
websocket to the Archipelago room on behalf of every Ori world, and items ride the Ori randomizer's existing
multiworld netcode. There is nothing to install for the connection, no port to open on a player's PC, and
nothing to keep running while you play — but the room itself has to be reachable from the internet, because
orirando.com is the side doing the dialing. See [Hosting the room](#5-host-the-room) below.

## What you need

* **Ori and the Blind Forest: Definitive Edition** on PC, plus the Ori randomizer mod:
  * Join the [Ori Discord](https://orirando.com/discord) — it is the best place to get help.
  * Copy the [randomizer dll](https://orirando.com/dll) into your `Ori DE/oriDE_Data/Managed` folder.
    Step-by-step instructions are in the [install FAQ](https://orirando.com/faq?g=install).
  * Optional but recommended: the [item tracker](https://orirando.com/tracker).
* **Archipelago 0.6.7 or newer**, from the
  [Archipelago releases page](https://github.com/ArchipelagoMW/Archipelago/releases/latest).
* **`oride.apworld`**, the file this guide comes with.

Every Ori player needs the game and the randomizer dll. Only the person generating the Archipelago session
needs Archipelago itself and this apworld.

## 1. Install the apworld

Put `oride.apworld` in your Archipelago install's **`custom_worlds`** folder (next to `ArchipelagoLauncher.exe`;
create the folder if it is not there). If you are replacing an older copy, delete the old one first — two builds
of the same world in that folder is asking for trouble.

You can check it took by launching `ArchipelagoLauncher` and generating; the generator log lists
`Ori DE Rando` with its item and location counts.

While Ori DE Rando is in closed testing, the apworld build and the seeds have to match. If they do not, the
generator says so in plain words and tells you which side to update — see [Troubleshooting](#troubleshooting).

## 2. Roll the Ori seed on orirando.com

The seed is rolled **once, for all Ori players in the session**. One person does this.

1. Go to [orirando.com](https://orirando.com/). During closed testing the Archipelago controls are hidden
   until you visit `https://orirando.com/?ap_test=1` once — that browser then keeps them until you visit
   `https://orirando.com/?ap_test=0`. If you see no Archipelago option, that is why.
2. Pick your logic paths, key mode, goal and so on as you would for any Ori seed.
3. On the **Multiplayer Options** tab, set **Players** to the number of Ori players. 1 is fine — one Ori world
   inside somebody else's Archipelago session. With 2 or more, also set **Multiplayer Game Type** to
   **Multiworld**.
4. Press the **Archipelago** button that appears.
5. Choose which kinds of item get handed to Archipelago's pool with the **Export …** buttons:
   *Export Skills*, *Export Teleporters* and *Export World Events* are on by default; *Export Cells* and
   *Export Stones* are optional. A category cannot be both Shared and Exported, so selecting one deselects
   the other. With more than one Ori player, items that land in another Ori world travel through Archipelago
   as well regardless of category — so a multi-player game exports more than you picked here.
6. Hit **Generate Seed**. You land on the **Seed** tab, and the page URL now carries `param_id` and `game_id` —
   bookmark it, it is the page you and the other Ori players come back to.

## 3. Download the yamls

The Seed tab has one row per Ori world. Each row has an **AP YAML** button; download all of them.

The files are named `ap_world_1.yaml`, `ap_world_2.yaml`, and so on, and their slot names are `Ori1`, `Ori2`,
… — one Archipelago slot per Ori world.

Put them in your Archipelago install's **`Players`** folder, alongside the yamls for every other game in the
session.

Do not edit them. The `orirando` block in each one is the whole Ori seed: which locations Archipelago owns,
which items it was given, and enough of the seed's logic for Archipelago to know what is reachable.

## 4. Generate the session

Run `ArchipelagoLauncher` → **Generate**, or `python Generate.py` from an Archipelago source install. This
produces an `AP_<seed>.zip` in `output/`, the same as for any other session.

If generation fails, read the message: this world checks its input up front and says which slot and what is
wrong.

## 5. Host the room

**The room must be reachable from the public internet**, because orirando.com connects *out* to it. This is
the one requirement that trips people up.

* **[archipelago.gg](https://archipelago.gg/uploads)** — upload the `AP_<seed>.zip`, and use the host and
  port the room page shows you (something like `archipelago.gg:38281`). This always works.
* **Self-hosted** — you can run `ArchipelagoServer` yourself, but the port you host on has to be forwarded to
  the internet on your router, and you have to give out your public IP. `localhost`, `127.0.0.1`, LAN
  the internet. `localhost`, `127.0.0.1`, literal LAN addresses and `.local` names are rejected outright:
  orirando.com's server cannot reach your PC through them. A hostname that resolves to a LAN address is not
  caught, but the connection attempt will fail within ten seconds and say so.

## 6. Connect the room to the Ori game

Back on the seed page from step 2 (the URL with `param_id` and `game_id`), scroll to the
**Archipelago Room** panel under the seed rows:

1. Type the room's **host** and **port**, plus the room **password** if it has one.
2. Hit **Connect**.
3. Within a few seconds the status line should read **connected**. Each Ori world gets a row showing its slot
   name, how many items the room has sent it, and how many of its Archipelago locations it can name.

If it says **reconnecting** with an error underneath, the room is not reachable — check the address, the port,
and the port forwarding. The bridge keeps retrying on its own, so fixing the room is enough; you do not have
to click Connect again. To point the game at a *different* room, hit Disconnect first, then Connect.

## 7. Download the seeds — after connecting

Each Ori world's row has a **Download Seed** button that gives you `randomizer.dat`. Put it next to
`OriDE.exe` in your Ori install (the same folder, not `oriDE_Data`).

**Connect the room before handing seeds out.** Until the bridge has joined the room, nobody knows what
Archipelago put in the reserved locations, so a seed downloaded early calls them all `AP Item #1`,
`AP Item #2`, and so on. Once every world reports its item names — the panel says so — download again and the
real names are baked in, so the game announces things like `Found Archipelago's Progressive Sword (Zelda)!`.

The placeholder names are cosmetic only. A seed with them plays exactly the same and no item is ever lost.
But re-downloading is much nicer, and it is free.

Send the other Ori players the URL of the seed page so they can grab their own world's seed.

## 8. Play

Play the Ori seed normally. Picking up a location Archipelago owns sends the check to the room; items other
games find for you arrive in game the same way Ori multiworld items always have. Finishing the seed's goal
reports your goal to the room; what happens to your remaining items after that is up to the room's release
settings, exactly like any other game.

## Troubleshooting

**"it was made for … data version N" / "this oride.apworld needs at least N"** — the apworld build and
the yaml are from different generations of the item tables. The message says which side is behind: either get
the newer `oride.apworld` from whoever rolled the seed, or re-download the yaml with the AP YAML button (a
fresh yaml for the same seed is fine).

**"empty orirando data"** — the yaml did not come from orirando.com's Archipelago mode, or the `orirando`
block was emptied. Download it again from the seed page.

**"exported item count X != reserved location count Y"** — a hand-edited or truncated yaml. Download it again.

**The website shows no Archipelago option** — closed testing; visit `https://orirando.com/?ap_test=1` once.

**The room panel is stuck on "reconnecting"** — orirando.com cannot reach the room. The error line under the
status usually says exactly why. Use an archipelago.gg room if you are not sure.

**The panel never appears** — it only shows on the seed page of a game generated with Archipelago mode on, and
it needs the `game_id` in the URL.
