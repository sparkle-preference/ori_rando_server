# archipelago/ — Archipelago support for the Ori DE randomizer

Everything that makes an orirando seed part of an [Archipelago](https://archipelago.gg/) session lives here,
plus the apworld itself. Design notes and history are in `prior_notes/ARCHIPELAGO_NOTES.md`; this file is the
operator's manual.

The one-paragraph version: orirando rolls a normal K-world **Multiworld** seed, then a conversion pass turns
some of its placements into Archipelago slots — the location line becomes a placeholder owned by a *shadow
player* (pid `K+world`, netcode-only), and the item that was there moves to the world's manifest as an export.
The paired yaml describes that to Archipelago, and at play time a server-side bridge holds one websocket per
world to the room and translates in both directions. No new client wire format; the 4.2.4 dll already speaks
all of it.

Everything is gated by the `ARCHIPELAGO` env flag (`util.py`), plus a per-browser `?ap_test=1` opt-in during
closed testing (`seedparams.seed_mode_problem`, `map/src/common.js`).

## Modules

| file | what it is |
| --- | --- |
| `export_data.py` | Regenerates the apworld's data tables (`oride_apworld/oride/data/*.json`) from the same sources the seed generator uses — `pickups.py`, `util.py`, `areas.ori` — so the datapackage and the logic graph can never drift from the server. AP ids are frozen: `freeze_check` refuses to renumber a name that already shipped. |
| `yaml_emit.py` | Builds the `orirando` yaml blob (`make_config`) and renders it as yaml (`_emit`/`emit_yaml`, a small hand-rolled emitter — no pyyaml on the server). Also holds `DATA_VERSION`, the contract version testers' apworlds check. Its `build_config` CLI path is the *prototype* classifier for unconverted solo seeds and is only used by `difftest`. |
| `convert.py` | The conversion pass over rendered multiworld seed texts: picks what becomes an AP slot, balances each world's exports against its reserved locations by reverting cross-world spirit light, rewrites the seed lines, and derives the per-world yaml config (`build_ap_config`). Every refusal is an `ApConversionError`. |
| `ap_bridge.py` | The room bridge: one daemon thread per `(game, world)`, lazy-started from the `ap/connect` route and re-armed by `heal()` on the request path. Sends `LocationChecks` from the shadow player's slot bits, applies `ReceivedItems` onto the real player's manifest slots, reports the goal, and scouts item names. Its module docstring is the protocol contract. |
| `build_apworld.py` | Packages `oride_apworld/oride` into `dist/oride.apworld` (CLI) or into zip bytes for the `/generator/apworld` route (`zip_bytes`). Also the guard rail: it fails the build if the package calls `open()`, if the manifest is missing keys, or if a data or docs file is absent. |
| `difftest/` | Differential logic harness: walks spheres and diffs the server's own reachability engine against the apworld's compiled rules over the locations the apworld models. Not part of the unit suite — run it by hand when the rule compiler or `areas.ori` changes. |
| `oride_apworld/oride/` | The apworld. `__init__.py` is the `World`; `rules.py` compiles areas.ori requirements into AP access rules; `shared.py` is the token vocabulary both sides must agree on; `options.py` is the single `orirando` blob option; `version.py` is the compatibility check; `docs/` is what the launcher and the AP website serve; `data/` is generated, never hand-edited. |

Related code outside this directory: `ap_models.py` (the `APLink` and `APNames` entities), `netcode.py`
(`ap_connect` / `ap_status` / `ap_disconnect` and the bridge hooks), `main.py` (thin routes, including
`/generator/apyaml/<params_id>/<world>` and `/generator/apworld`), `seedbuilder/seedparams.py` (`ap_mode` / `ap_export` params,
`get_seed`'s name substitution, `to_ap_yaml`), and the UI in `map/src/MainPage.js` + `map/src/helpbox.js`.

## Commands

All of these run from the **repo root** with the server venv and `PYTHONPATH` pointing at the repo root:

```powershell
$env:PYTHONPATH = $PWD
.venv312\Scripts\python.exe -m archipelago.build_apworld     # -> archipelago/dist/oride.apworld
.venv312\Scripts\python.exe -m archipelago.export_data       # regenerate the data tables
```

The test suite (must stay green; the AP tests are `ApModeGenTests`, `ApModeSoloTests`,
`ApNameSubstitutionTests`, `ApExportSlotCapTests`, `ApDataVersionTests` in `test/seedgentest.py`, plus all of
`test/ap_bridge_test.py`):

```powershell
.venv312\Scripts\python.exe -m unittest test.seedgentest test.golden_wire_test test.netcode_test `
    test.session_golden_test test.ws_adapter_test test.ws_push_test test.ap_bridge_test
```

Differential logic check, when the rules or the graph move:

```powershell
.venv312\Scripts\python.exe archipelago\difftest\compare.py <randomizer0.dat>   # writes report.txt
.venv312\Scripts\python.exe archipelago\difftest\probes.py  <randomizer0.dat>   # writes probes.txt
```

Release: the site serves the apworld itself (below), so deploying is the release. `dist/` is only for verifying
the zip by hand and for handing someone a file out of band; it is gitignored either way.

## Serving the apworld

`/generator/apworld` (`main.py`, `ARCHIPELAGO`-gated, deliberately *not* behind the `ap_test` opt-in — a
tester's session host never visits the seed page) hands out the same package the CLI writes.

The bytes come from `oride_apworld/oride/` in the deployed source tree, never from `dist/`: the route calls
`build_apworld.zip_bytes()`, which is `collect()` + `check()` + an in-memory zip, so a package that fails its
own checks raises and 500s instead of downloading as a dud. They are cached in `main.apworld_zip` because the
contents are fixed per deploy — set it back to `None` (or restart) after editing the world in a live dev
server.

**The filename `oride.apworld` is load-bearing.** Archipelago derives the world's module name from the file
stem (`worlds/__init__.py`, `Path(path).stem`), so anything versioned like `oride-v2.apworld` fails to load.
Version the world in `archipelago.json` (`world_version`) instead — that string and `yaml_emit.DATA_VERSION`
are what the seed page's *Archipelago Setup* panel shows testers, via `main.ap_versions()`.

## The gotcha: dev junction vs packaged zip

The AP harness at `../../Archipelago` has `worlds/oride` as a **directory junction** pointing straight at
`archipelago/oride_apworld/oride`. That is what makes edit-and-generate fast, and it is also a lie: a junction
has a filesystem, and a real `.apworld` is a zip that does not.

Consequences, both of which have already bitten:

* **Never use `open()` inside the package.** Read package data with `pkgutil.get_data(__name__, "data/x.json")`,
  which works loose *and* zipped. `build_apworld.py` tokenizes every `.py` and fails the build on a bare
  `open` for exactly this reason.
* **The junction path never exercises the manifest or the zip layout.** A missing `compatible_version` in
  `archipelago.json` is invisible in dev and an `InvalidDataError` in a real install.

So: any change to how the package reads its own files, or to `archipelago.json`, has to be verified as a zip.
The recipe is to remove the junction, drop `dist/oride.apworld` in the harness's `custom_worlds/`, run
`Generate.py` with the yamls in `Players/`, then **restore the junction and delete the zip** — leaving both in
place means two copies of the same world are registered.

## Regenerating the data tables

`python -m archipelago.export_data` rewrites `items.json`, `locations.json` and `graph.json`. Run it whenever
`pickups.py`, `util.py`'s coord tables, or `areas.ori` change.

Two rules it enforces for you:

* **AP ids are append-only.** `ITEM_ORDER` is a frozen list; append to the end, never reorder or remove. Ids
  are baked into every yaml and every room that has already generated. `freeze_check` asserts that every
  name→id pair already on disk survives regeneration.
* **Location names come from areas.ori** where it has one, because the graph speaks those names.

Then bump the data version (next section), rebuild the apworld, and run the suite — `ApModeGenTests` and the
seed canaries will tell you if the conversion pass moved.

## Data version bump rule

A tester holding an old `oride.apworld` and a yaml from a newer server used to fail as a `KeyError` on some
item name their build had never heard of. Now every yaml carries `orirando.data_version`, and the apworld
refuses what it cannot read with a sentence naming the fix.

The constant lives on both sides of the zip boundary and is maintained **by hand**:

* `archipelago/yaml_emit.py` → `DATA_VERSION` (what the server stamps into yamls)
* `archipelago/oride_apworld/oride/version.py` → `DATA_VERSION` (newest yaml this build reads) and
  `COMPATIBLE_DATA_VERSION` (oldest yaml this build reads)

**Bump `DATA_VERSION` on both sides together** whenever the data tables or the blob's shape change in a way an
older apworld would misread: new item or location names (appending ap_ids counts — an old build has never
heard of the new name), a new cfg key the world has to honor, different rule compilation.
`ApDataVersionTests.test_emitter_and_apworld_agree` fails the suite on a one-sided bump.

**Leave `COMPATIBLE_DATA_VERSION` alone** unless a change genuinely makes older yamls unreadable: raising it
invalidates every yaml testers are already holding. Yamls with no `data_version` at all predate the check and
read as version 1.

## Debugging a live game on prod

Prod is App Engine, so the evidence is in Cloud Logging and the datastore, and the read-only service-account
key at `prior_notes/orirandov3-ca1b108d0490.json` is enough to read both. The scripts described below live in
a scratchpad rather than the repo — they are twenty lines each and disposable, but the shapes are worth
keeping:

* **`read_ap_logs.py <fragment> <minutes> <limit>`** — Cloud Logging API query for app lines containing a
  fragment (`APBRIDGE`, a game id, `Traceback`) over the last N minutes. Filter on `textPayload:*` to drop the
  structured request records, and exclude the tracker and `NETPERF` chatter or the bridge lines drown.
* **`read_window.py <start_min_ago> <end_min_ago> <limit>`** — the same query bounded to a window, for reading
  around a known incident time instead of tailing.
* **`ap_probe.py <gid>`** — pulls the `APLink` for a game id straight from the prod datastore along with its
  `SeedGenParams`: `status`, `host`/`port`, `recv_index` per world, `goal_worlds`, `last_error`,
  `last_activity`, and the name counters. This is the fastest way to tell "the bridge never connected" from
  "the bridge is connected and the client isn't ticking".

Two traps found the hard way:

* **A deploy leaves two revisions serving.** Log lines from `00071` and `00072` interleaved during the first
  live test; check the revision label before concluding that a fix did not take.
* **The UI's own retries erase the diagnosis.** Every Connect click resets the link's status and clears
  `last_error`. `ap_connect` now only clears the error when the room address actually changes, but when
  reading logs, prefer the earliest failure in a burst over the latest state.

The signals worth knowing: `APBRIDGE connected gid=… world=… slot='Ori…'` is a good handshake;
`APBRIDGE connection lost …` with a timeout means the room is not reachable *from Google's network* (the
number one cause — see the setup guide's hosting section); `APBRIDGE no free slot for AP item …` means an
incoming item matched no manifest entry, which should be impossible by the conversion balance invariant and
is worth a bug report.

For anything reproducible, run it locally instead: `prior_notes/LOCAL_DEV.md` has the Flask recipe, and seed
generation needs the datastore emulator (`gcloud beta emulators datastore start` + `DATASTORE_EMULATOR_HOST`)
because the prod key cannot write. Set `ARCHIPELAGO=1 MULTIWORLD=1` and host a real `MultiServer` from the AP
harness to exercise the whole loop.
