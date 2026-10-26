"""Seedgen harness for test/seedgen_props.py: cli_gen runs, seed-line parsing, reach walks and strategies."""
import logging
import math
import os
import shlex
import shutil
import sys
import tempfile
from collections import Counter

from hypothesis import event, note, strategies as st

from cli_gen import CLISeedParams
from enums import Variation, presets
from pickups import Pickup
from reachable import Map, PlayerState
from seedbuilder import enemyopts, enemyroll
from seedbuilder.generator import FINALE_LOC, SPAWN_SPOTS, SeedGenerator, keysanity_map
from seedbuilder.oriparse import get_areas
from seedbuilder.relics import relics
from util import SEED_FORMAT, decompose_multi_value

SPAWN_LOC = 2
MANIFEST = range(-257, -1)
MS_LINES = {20 + 4 * i: "MS%d" % i for i in range(1, 10)}
BURIED, EARLY = 20000000, 30000000
CUSHION = 40
ATTEMPTS = 25


class RollTooLong(Exception):
    """A roll that restarted placement more often than the harness waits for."""


class Run(object):
    """One cli_gen invocation: the text of each file it wrote, the generator and the params it walked."""

    def __init__(self, argv, files, gen, params):
        self.argv, self.files, self.gen, self.params = argv, files, gen, params

    def seed_names(self):
        return sorted(n for n in self.files if n.startswith("randomizer") and n.endswith(".bfr"))

    def worlds(self):
        """{world: seed lines}; empty when the roll failed."""
        names = self.seed_names()
        if len(names) == 1 and "_" not in names[0]:
            return {1: self.files[names[0]].splitlines()}
        return {int(n.split("_")[1].split(".")[0]): self.files[n].splitlines() for n in names}

    def seed(self):
        return self.worlds().get(1)


def repro(argv):
    return "python cli_gen.py " + " ".join(shlex.quote(a) for a in argv)


def cli(argv, spies=None, attempts=None):
    """cli_gen with argv (naming --preset and --seed) and spies swapped in; RollTooLong past `attempts` placements."""
    out = tempfile.mkdtemp(prefix="seedprops_")
    captured, calls = {}, [0]
    swaps = dict(spies or {})
    inner = swaps.get("setSeedAndPlaceItems", SeedGenerator.setSeedAndPlaceItems)
    place = swaps.get("placeItems", SeedGenerator.placeItems)

    def capture(sg, params, **kw):
        captured["gen"], captured["params"] = sg, params
        return inner(sg, params, **kw)

    def capped(sg, depth=0, worried=False):
        calls[0] += 1
        if attempts and calls[0] > attempts:
            raise RollTooLong(" ".join(argv))
        return place(sg, depth, worried)
    swaps["setSeedAndPlaceItems"] = capture
    swaps["placeItems"] = capped
    saved = {name: SeedGenerator.__dict__[name] for name in swaps}
    old_argv, old_disable = sys.argv, logging.root.manager.disable
    sys.argv = ["cli_gen", "--output-dir", out] + list(argv)
    logging.disable(logging.CRITICAL)
    try:
        for name, fn in swaps.items():
            setattr(SeedGenerator, name, fn)
        CLISeedParams().from_cli()
        files = {}
        for name in os.listdir(out):
            with open(os.path.join(out, name)) as f:
                files[name] = f.read()
        return Run(list(argv), files, captured.get("gen"), captured.get("params"))
    finally:
        for name, fn in saved.items():
            setattr(SeedGenerator, name, fn)
        logging.disable(old_disable)
        sys.argv = old_argv
        shutil.rmtree(out, ignore_errors=True)


def roll(argv, seed, tries=1, spies=None):
    """The first of `tries` seed strings that generates, each noted as a repro; None when none did."""
    for k in range(tries):
        full = list(argv) + ["--seed", seed if not k else "%s~%d" % (seed, k)]
        note(repro(full))
        try:
            run = cli(full, spies, ATTEMPTS)
        except RollTooLong:
            event("a roll ran out of placement attempts")
            continue
        if not run.worlds():
            event("a seed string failed to generate")
        elif stranded_forced_spots(run):
            event("a forced spot was never reached")
        else:
            return run
    return None


def stranded_forced_spots(run):
    """{(world, loc): item} forced onto spots the fill never reached."""
    gen = run.gen
    return {k: v for k, v in gen.forcedAssignments.items() if k not in gen.forceAssignedLocs}


def page_pool(flag):
    """(preset name, item pool) the page sends for a cli_gen pool flag."""
    run = cli(["--preset", "standard", "--seed", "pool"] + ([flag] if flag else []),
              spies={"setSeedAndPlaceItems": lambda sg, params, **kw: None})
    return run.params.pool_preset, run.params.item_pool


def body(lines):
    return [l for l in lines[1:] if l and not l.startswith("//")]


class Seed(object):
    """One world's lines: placements {loc: (code, id, zone)}, manifest {slot: (finder, code, id, zone)}, EN lines."""

    def __init__(self, lines):
        self.placements, self.manifest, self.dups, self.en, self.malformed = {}, {}, [], [], []
        for line in body(lines):
            fields = line.split("|")
            if len(fields) != 4:
                self.malformed.append(line)
                continue
            loc, code, id, zone = fields
            loc = int(loc)
            if code == "EN":
                self.en.append(line)
            elif loc in MANIFEST:
                finder, _holder, icode, iid = id.split(",", 3)
                self.manifest[-loc - 2] = (int(finder), icode, iid, zone)
            elif loc in self.placements:
                self.dups.append(loc)
            else:
                self.placements[loc] = (code, id, zone)

    def spawn(self):
        return self.placements.get(SPAWN_LOC, ("MU", "", "Glades"))


def parts(code, id):
    """A line's pickups, a multipickup split into its children."""
    return decompose_multi_value(id) if code in ("MU", "RP") else [(code, id)]


def totals(placements, wild=("EX", "WT", "TW")):
    """(code, id) multiset over a world's lines, spawn parts included; wild codes count under id "*"."""
    c = Counter()
    for code, id, zone in placements.values():
        for pc, pid in parts(code, id):
            c[(pc, "*" if pc in wild else pid)] += 1
    return c


def pool(placements):
    """The totals minus experience, whose count follows how many items the spawn line holds."""
    return Counter({k: n for k, n in totals(placements).items() if k[0] != "EX"})


_areas = {}


def _loc_key(info):
    return int(math.floor(int(info["x"]) / 4.0) * 4) * 10000 + int(math.floor(int(info["y"]) / 4.0) * 4)


def loc_areas():
    """{seed line loc: reachable.py area}; the mapstone turn-ins are MS1..MS9 at 24..56."""
    if "areas" not in _areas:
        out = dict(MS_LINES)
        for name, info in get_areas()["locs"].items():
            if info["item"] != "MapStone":
                out[_loc_key(info)] = name
        _areas["areas"] = out
    return _areas["areas"]


def loc_zones():
    if "zones" not in _areas:
        _areas["zones"] = {_loc_key(info): info["zone"] for info in get_areas()["locs"].values()
                           if info["item"] != "MapStone"}
    return _areas["zones"]


def expected_locs():
    return set(loc_areas()) | {SPAWN_LOC, FINALE_LOC}


def structure_problems(lines, entrance=False):
    seed = Seed(lines)
    out = ["fields: %s" % l for l in seed.malformed[:3]]
    if seed.dups:
        out.append("duplicate locs %s" % seed.dups[:5])
    exp, got = expected_locs(), set(seed.placements)
    if got != exp:
        out.append("locs: missing %s extra %s" % (sorted(exp - got)[:5], sorted(got - exp)[:5]))
    if len(seed.en) != (24 if entrance else 0):
        out.append("%s EN lines" % len(seed.en))
    return out


def header_problems(run, world, players):
    """Line 1 ends in the seed name, the format and player-count lines follow, enemy meta lines match a fresh roll."""
    lines, seed = run.worlds()[world], run.params.seed
    out = []
    if not lines[0].endswith("|" + seed):
        out.append("line 1 %r doesn't name seed %r" % (lines[0], seed))
    if lines[1:3] != ["// SEED_FORMAT: %s" % SEED_FORMAT, "// PLAYERS: %s" % players]:
        out.append("header %r" % lines[1:3])
    view = run.params.world_params(world)
    if Variation.ENEMY_RANDO in view.variations:
        opts = getattr(view, "enemy_opts", None)
        metas = [l for l in lines if l.startswith("//Enem")]
        want = [m for m in (enemyopts.meta_line(opts), enemyroll.meta_line(enemyroll.roll(seed, world, opts))) if m]
        if sorted(metas) != sorted(want):
            out.append("enemy meta lines %s, a fresh roll gives %s" % ([m[:40] for m in metas], [m[:40] for m in want]))
    return out


def spawn_zone(spawn_id):
    for zone, (x, y) in SPAWN_SPOTS.items():
        if "WS/%s,%s," % (x, y) in spawn_id:
            return zone
    return "Glades"


def modes_for(params, p=1):
    view = params.world_params(p)
    modes = [lp.value for lp in view.logic_paths]
    if Variation.OPEN_WORLD in view.variations:
        modes.append("OPEN_WORLD")
    if Variation.CLOSED_DUNGEONS in view.variations:
        modes.append("CLOSED_DUNGEON")
    return tuple(modes)


def reached(picks, modes, spawn):
    return set(Map.get_reachable_areas(PlayerState(list(picks)), modes, spawn, need_reached_with=False))


def unreachable(placements, modes, spawn, cushion=0):
    """Locations a collect-and-expand walk of reachable.py never gets to, from the spawn's grants."""
    return joint_unreachable({1: placements}, {1: modes}, {1: spawn}, [], cushion, parsed=True).get(1, [])


class Netcode(object):
    """Game.mw_shareable for a seed's shared categories, without a Game."""

    def __init__(self, shared):
        from models import Game
        self.shared = list(shared)
        self._rule = Game.mw_shareable

    def mw_shareable(self, pickup):
        return self._rule(self, pickup)

    def shares(self, code, id):
        return bool(self.mw_shareable(Pickup.n(code, id)))


def deliveries(worlds, shared, parsed=False):
    """{(world, loc): [(recipient, code, id)]}: MW lines go to the owner, shared pickups everywhere, spawns stay home."""
    net = Netcode(shared)
    out = {}
    for q, lines in worlds.items():
        for loc, (code, id, zone) in (lines if parsed else Seed(lines).placements).items():
            got = []
            if loc == SPAWN_LOC:
                got.append((q, code, id))
            elif code == "MW":
                owner, _slot, icode, iid = id.split(",", 3)
                got.append((int(owner), icode, iid))
            elif code in ("MU", "RP"):
                got.append((q, code, id))
                for c, i in decompose_multi_value(id):
                    if net.shares(c, i):
                        got += [(r, c, i) for r in worlds if r != q]
            elif net.shares(code, id):
                got += [(r, code, id) for r in worlds]
            else:
                got.append((q, code, id))
            out[(q, loc)] = got
    return out


def joint_unreachable(worlds, modes, spawns, shared, cushion=0, parsed=False):
    """{world: locations no walk gets to}, every world collecting and handing out at once."""
    areas_of = loc_areas()
    deliv = deliveries(worlds, shared, parsed)
    picks = {q: [("KS", "1", cushion, False)] if cushion else [] for q in worlds}
    pending = {q: [] for q in worlds}
    for (q, loc), got in deliv.items():
        if loc == SPAWN_LOC:
            for r, c, i in got:
                picks[r].append((c, i, 1, False))
        elif loc in areas_of:
            pending[q].append(loc)
    dirty = set(worlds)
    while dirty:
        found = []
        for q in sorted(dirty):
            here = reached(picks[q], modes[q], spawns[q])
            found += [(q, loc) for loc in pending[q] if areas_of[loc] in here]
        dirty = set()
        for q, loc in found:
            pending[q].remove(loc)
            for r, c, i in deliv[(q, loc)]:
                picks[r].append((c, i, 1, False))
                if any(opens_doors(pc, pid) for pc, pid in parts(c, i)):
                    dirty.add(r)
    return {q: sorted(locs) for q, locs in pending.items() if locs}


def opens_doors(code, id):
    """Whether PlayerState counts this pickup toward any requirement."""
    return code in ("SK", "EV", "TP", "HC", "EC", "AC", "KS", "MS") or (code == "RB" and id in ("17", "19", "21"))


def received(worlds, shared, from_spawn):
    """{world: Counter((code, id))} handed to each world by the spawn lines, or by every other line."""
    out = {q: Counter() for q in worlds}
    for (q, loc), got in deliveries(worlds, shared).items():
        if (loc == SPAWN_LOC) != from_spawn:
            continue
        for r, code, id in got:
            for pc, pid in parts(code, id):
                out[r][(pc, pid)] += 1
    return out


def mw_problems(worlds):
    """check_mw_invariants as text: MW lines and manifests pair one to one, nobody holds their own."""
    out, pointed, manifest = [], Counter(), set()
    for p, lines in worlds.items():
        seed = Seed(lines)
        out += ["w%s: %s" % (p, s) for s in structure_problems(lines, entrance=bool(seed.en))]
        for loc, (code, id, zone) in seed.placements.items():
            if code == "MW":
                owner, slot = (int(x) for x in id.split(",")[:2])
                if owner == p:
                    out.append("w%s holds its own MW at %s" % (p, loc))
                if slot >= SeedGenerator.MAX_SLOTS:
                    out.append("w%s slot %s" % (p, slot))
                pointed[(owner, slot)] += 1
        for slot, (finder, code, id, zone) in seed.manifest.items():
            manifest.add((p, slot))
            if finder == p:
                out.append("w%s manifest names itself" % p)
    if set(pointed) != manifest:
        out.append("MW/manifest mismatch: %s" % sorted(set(pointed) ^ manifest)[:5])
    out += ["slot %s pointed %s times" % (k, v) for k, v in pointed.items() if v != 1]
    return out


def share_disagreements(run):
    """(code, id, generator shares it) for each line the generator and the netcode share differently."""
    gen, net = run.gen, Netcode(run.params.sync.shared)
    out = set()
    for lines in run.worlds().values():
        for loc, (code, id, zone) in Seed(lines).placements.items():
            if loc == SPAWN_LOC or code in ("MW", "MU", "RP", "EX", "TW", "WT"):
                continue
            base = code if code in ("HC", "EC", "AC", "KS", "MS") else gen.codeToName.get(code + id, code + id)
            if (base in gen.shared_pool_bases) != net.shares(code, id):
                out.add((code, id, base in gen.shared_pool_bases))
    return out


KEYSANITY_KEYS = {("RB", SeedGenerator.keysanityOutput[name][2:]) for names in keysanity_map.values() for name in names}


def misc_keysanity_split(argv):
    """Sharing misc with keysanity on."""
    return "misc" in (flag_value(argv, "--shared-items") or "").split(",") and "--keysanity" in argv


def records_spy(records):
    """Spies logging (item, locations opened, round, the count its round opened at) per assignment."""
    orig_acc, orig_assign = SeedGenerator.get_all_accessible_locations, SeedGenerator.assign_to_location
    opened = {}

    def accessible(sg):
        opened[sg.balanceLevel] = sg.total_locs() - sg.locations()
        return orig_acc(sg)

    def assign(sg, item, location):
        records.append((item, sg.total_locs() - sg.locations(), sg.balanceLevel, opened.get(sg.balanceLevel, 0)))
        return orig_assign(sg, item, location)
    return {"get_all_accessible_locations": accessible, "assign_to_location": assign}


def kept_records(records):
    """The records of the attempt that shipped: a restart drops the round count back."""
    start = 0
    for k in range(1, len(records)):
        if records[k][2] < records[k - 1][2]:
            start = k
    return records[start:]


PRESETS = ["casual", "standard", "expert", "master", "glitched"]
KEYMODES = [None, "Clues", "Shards", "LimitKeys", "Free"]
STARTS = ["Glades", "Grove", "Swamp", "Grotto", "Forlorn", "Valley", "Horu", "Ginso", "Sorrow", "Blackroot"]
QUICK_STARTS = [s for s in STARTS if s not in ("Valley", "Sorrow")]
FLAGS = ["--open-world", "--closed-dungeons", "--force-trees", "--force-mapstones", "--starved", "--tp-starved",
         "--wall-starved", "--grenade-starved", "--strict-mapstones", "--easy", "--zeroxp", "--ohko", "--no-tps",
         "--goal-mode-finish", "--enemy-rando", "--classic-fill", "--entrance", "--keysanity",
         "--non-progressive-mapstones"]
POOL_TPS = {None: 8, "--competitive": 6, "--bonus-lite": 9, "--bonus-pickups": 9, "--hard": 5}
FIXED_POOLS = [None, "--competitive", "--hard"]
UNWALKABLE = {"--entrance", "--keysanity", "--in-logic-warps"}
SHARES = ["skills", "worldevents", "teleporters", "upgrades", "misc"]
HELD = {"SK0": "Bash", "SK2": "ChargeFlame", "SK3": "WallJump", "SK4": "Stomp", "SK5": "DoubleJump",
        "SK8": "ChargeJump", "SK12": "Climb", "SK14": "Glide", "SK50": "Dash", "SK51": "Grenade", "EV1": "Water",
        "EV3": "Wind", "TPGrove": "TPGrove", "TPSwamp": "TPSwamp", "HC1": "HC", "EC1": "EC", "RB9": "RB9", "KS1": "KS"}

seed_strings = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789", min_size=1, max_size=8)


def flag_value(argv, flag, default=None):
    return argv[argv.index(flag) + 1] if flag in argv else default


def walkable(argv):
    return not UNWALKABLE & set(argv)


def warp_sampling_overflows(argv):
    """--warps-instead-of-tps with a --warp-count above a world's own teleporters."""
    if "--warps-instead-of-tps" not in argv or "--warp-count" not in argv:
        return False
    pool = next((p for p in POOL_TPS if p and p in argv), None)
    shared_tps = "teleporters" in (flag_value(argv, "--shared-items") or "").split(",")
    return int(flag_value(argv, "--warp-count")) > (0 if shared_tps else POOL_TPS[pool])


def closed_dungeons_swap_missing_tps(argv):
    """--warps-instead-of-tps with closed dungeons."""
    return "--warps-instead-of-tps" in argv and "--closed-dungeons" in argv


def spawn_shards_pile_up(argv):
    """Multiworld Shards sharing world events from a dungeon or random start."""
    shared = (flag_value(argv, "--shared-items") or "").split(",")
    return (flag_value(argv, "--keymode") == "Shards" and "worldevents" in shared
            and flag_value(argv, "--share-mode") == "multiworld" and "--entrance" not in argv
            and flag_value(argv, "--start") in ("Ginso", "Forlorn", "Horu", "Random"))


def double_skills_strand_the_spawn(argv):
    """--easy from a Valley, Ginso or Sorrow start."""
    return "--easy" in argv and flag_value(argv, "--start") in ("Valley", "Ginso", "Sorrow")


def masked(args):
    """argv with each open bug's input class taken out."""
    if double_skills_strand_the_spawn(args):
        args.remove("--easy")
    if warp_sampling_overflows(args) or closed_dungeons_swap_missing_tps(args):
        i = args.index("--warps-instead-of-tps")
        del args[i:i + 2]
    return args


@st.composite
def enemy_opts(draw):
    """Enemy rando options as the page and enemyopts.normalize take them."""
    o = {}
    if draw(st.booleans()):
        o["pool"] = draw(st.lists(st.sampled_from(enemyopts.KINDS), min_size=1, unique=True))
    if draw(st.booleans()):
        o["keep"] = draw(st.lists(st.sampled_from(enemyopts.KINDS), unique=True, max_size=4))
    for k in enemyopts.SWITCHES:
        if draw(st.booleans()):
            o[k] = draw(st.sampled_from(["on", "off"]))
    if draw(st.booleans()):
        o["arena"] = draw(st.sampled_from(enemyopts.ARENAS))
    for k in ("hp", "dmg"):
        if draw(st.integers(0, 3)) == 0:
            o[k] = draw(st.sampled_from(["zone", "vanilla", "0.5-2", "1-4", "0.25-0.25"]))
    return o


def enemy_opts_arg(opts):
    return ";".join("%s=%s" % (k, "+".join(v) if isinstance(v, list) else v) for k, v in sorted(opts.items()) if v)


def _start(draw, flags, random_ok=True, starts=STARTS):
    starts = starts + (["Random"] if random_ok else [])
    if "--closed-dungeons" in flags:
        starts = [s for s in starts if s not in ("Horu", "Ginso")]
    start = draw(st.sampled_from(starts))
    return [] if start == "Glades" else ["--start", start]


def _players(draw):
    """Extra argv for a solo roll, or a two-world multiworld sharing a random set."""
    players = draw(st.sampled_from([1, 1, 2]))
    if players == 1:
        return []
    shared = draw(st.lists(st.sampled_from(SHARES), unique=True, max_size=3))
    return ["--players", str(players), "--share-mode", "multiworld", "--shared-items", ",".join(shared)]


@st.composite
def solo_settings(draw, random_parts=True):
    """argv (no --seed) for a solo roll seed_mode_problem accepts; random_parts=False fixes the pool by the settings."""
    args = ["--preset", draw(st.sampled_from(PRESETS))]
    km = draw(st.sampled_from(KEYMODES))
    if km:
        args += ["--keymode", km]
    flags = draw(st.lists(st.sampled_from(FLAGS), unique=True, max_size=6))
    args += flags
    pool = draw(st.sampled_from(list(POOL_TPS) if random_parts else FIXED_POOLS))
    if pool:
        args.append(pool)
    args += _start(draw, flags, random_ok=random_parts)
    if "--start" in args and draw(st.integers(0, 3)) == 0:
        args += ["--starting-skills", str(draw(st.integers(0, 3)))]
    if draw(st.booleans()):
        args += ["--world-tour", str(draw(st.integers(1, 11)))]
    if draw(st.integers(0, 3)) == 0:
        frags = draw(st.integers(5, 60))
        args += ["--warmth-frags", str(frags), "--extra-frags", str(draw(st.integers(0, frags - 1)))]
    if random_parts and draw(st.integers(0, 3)) == 0:
        if draw(st.booleans()):
            args += ["--warp-count", str(draw(st.integers(1, 13)))]
        if draw(st.booleans()):
            args += ["--warps-instead-of-tps", str(draw(st.integers(1, 9)))]
        if draw(st.booleans()):
            args.append("--in-logic-warps")
    if "--enemy-rando" in flags and draw(st.booleans()):
        args += ["--enemy-opts", enemy_opts_arg(draw(enemy_opts()))]
    pd = draw(st.sampled_from([None, None, "easy", "hard"]))
    if pd:
        args += ["--prefer-path-difficulty", pd]
    if draw(st.integers(0, 3)) == 0:
        args += ["--exp-pool", str(draw(st.integers(0, 20000)))]
    if draw(st.integers(0, 3)) == 0:
        args += ["--force-cells", str(draw(st.integers(5, 60)))]
    return masked(args)


@st.composite
def mw_settings(draw):
    """argv (no --seed) for a 2-4 world multiworld roll."""
    players = draw(st.sampled_from([2, 2, 3, 3, 4]))
    shared = draw(st.lists(st.sampled_from(SHARES), unique=True, max_size=4))
    args = ["--preset", draw(st.sampled_from(["casual", "standard", "expert"])), "--players", str(players),
            "--share-mode", "multiworld", "--shared-items", ",".join(shared)]
    km = draw(st.sampled_from(KEYMODES))
    if km:
        args += ["--keymode", km]
    flags = draw(st.lists(st.sampled_from(["--open-world", "--force-trees", "--closed-dungeons", "--easy",
                                           "--keysanity", "--entrance", "--enemy-rando", "--tracking"]),
                          unique=True, max_size=3))
    args += flags
    if draw(st.integers(0, 2)) == 0:
        args += _start(draw, flags, starts=QUICK_STARTS)
    if draw(st.integers(0, 3)) == 0:
        args += ["--world-tour", str(draw(st.integers(1, 11)))]
    if draw(st.integers(0, 3)) == 0:
        args += ["--warp-count", str(draw(st.integers(1, 8)))]
    if draw(st.booleans()):
        args += ["--anti-bk-bias", str(draw(st.sampled_from([0.25, 0.5, 1.0])))]
    return masked(args)


@st.composite
def held_settings(draw):
    """(argv without the fass, the --fass value, (depth base, depth, held item codes))."""
    args = ["--preset", "standard", "--open-world"] + (["--classic-fill"] if draw(st.booleans()) else [])
    items = draw(st.lists(st.sampled_from(sorted(HELD)), min_size=1, max_size=2, unique=True))
    base = draw(st.sampled_from([BURIED, EARLY]))
    depth = draw(st.integers(2, 200))
    if len(items) == 1:
        value = items[0]
    else:
        value = "MU" + "/".join("%s/%s" % (c[:2], c[2:]) for c in items)
    return args, "%s:%s" % (base + depth, value), (base, depth, items)


@st.composite
def cloned_settings(draw):
    """argv (no --seed) for a cloned co-op roll, teams included; and how many copies it hands out."""
    players = draw(st.integers(2, 4))
    args = ["--preset", draw(st.sampled_from(["casual", "standard", "expert"])), "--players", str(players),
            "--share-mode", "shared", "--cloned"]
    km = draw(st.sampled_from(KEYMODES))
    if km:
        args += ["--keymode", km]
    flags = draw(st.lists(st.sampled_from(["--open-world", "--force-trees", "--entrance", "--keysanity",
                                           "--enemy-rando", "--easy"]), unique=True, max_size=3))
    args += flags + _start(draw, flags, starts=QUICK_STARTS)
    if draw(st.booleans()):
        args += ["--shared-items", ",".join(draw(st.lists(st.sampled_from(SHARES), unique=True, max_size=3)))]
    if draw(st.booleans()):
        args.append("--hints")
    copies = players
    if draw(st.booleans()):
        team_of = draw(st.lists(st.integers(0, players - 1), min_size=players, max_size=players))
        teams = [[p + 1 for p in range(players) if team_of[p] == t] for t in sorted(set(team_of))]
        args += ["--teams", "|".join(",".join(str(p) for p in team) for team in teams)]
        copies = len(teams)
    return masked(args), copies


@st.composite
def warp_settings(draw):
    """argv (no --seed) with --warp-count N and whatever may ride along with it; and N."""
    flags = draw(st.lists(st.sampled_from(["--open-world", "--closed-dungeons", "--entrance", "--in-logic-warps",
                                           "--no-tps"]), unique=True, max_size=3))
    pool = draw(st.sampled_from(list(POOL_TPS)))
    count = draw(st.integers(1, 13))
    args = ["--preset", draw(st.sampled_from(["casual", "standard", "expert"]))] + flags + ([pool] if pool else [])
    args += _start(draw, flags, starts=QUICK_STARTS) + ["--warp-count", str(count)] + _players(draw)
    if draw(st.booleans()):
        args += ["--warps-instead-of-tps", str(draw(st.integers(1, count)))]
    return masked(args), count


@st.composite
def tour_settings(draw):
    """argv (no --seed) with --world-tour R; and R."""
    count = draw(st.integers(1, 11))
    flags = draw(st.lists(st.sampled_from(["--open-world", "--closed-dungeons", "--entrance", "--keysanity",
                                           "--easy", "--enemy-rando"]), unique=True, max_size=3))
    pool = draw(st.sampled_from(list(POOL_TPS)))
    km = draw(st.sampled_from(KEYMODES))
    args = ["--preset", draw(st.sampled_from(["casual", "standard", "expert"])), "--world-tour", str(count)]
    args += flags + ([pool] if pool else []) + (["--keymode", km] if km else [])
    args += _start(draw, flags, starts=QUICK_STARTS) + _players(draw)
    return masked(args), count


@st.composite
def keymode_settings(draw):
    """argv (no --seed) around a keymode, solo or multiworld."""
    km = draw(st.sampled_from(KEYMODES))
    flags = draw(st.lists(st.sampled_from(["--open-world", "--closed-dungeons", "--keysanity", "--entrance",
                                           "--easy", "--force-trees"]), unique=True, max_size=3))
    args = ["--preset", draw(st.sampled_from(["casual", "standard", "expert"]))] + (["--keymode", km] if km else [])
    return masked(args + flags + _start(draw, flags, starts=QUICK_STARTS) + _players(draw))


WEB_VARIATIONS = ["OpenWorld", "ForceTrees", "Entrance", "Keysanity", "ClosedDungeons", "DoubleSkills",
                  "StrictMapstones", "EnemyRando", "WorldTour", "WarmthFrags"]
_pools = {}


@st.composite
def web_json(draw):
    """A seedgen page request: settings, an item pool the way the page sends one, 1-3 players."""
    flag = draw(st.sampled_from(list(POOL_TPS)))
    if flag not in _pools:
        _pools[flag] = page_pool(flag)
    name, pool = _pools[flag]
    players = draw(st.integers(1, 3))
    variations = draw(st.lists(st.sampled_from(WEB_VARIATIONS), unique=True, max_size=3))
    paths = presets[draw(st.sampled_from(["Casual", "Standard", "Expert"]))]
    j = {"seed": draw(seed_strings), "paths": [p.value for p in paths], "variations": variations,
         "keyMode": draw(st.sampled_from(["Clues", "Shards", "Limitkeys", "Free", "Default"])),
         "players": players, "tracking": True, "itemPool": pool, "selectedPool": name}
    if players > 1:
        j["coopGameMode"] = draw(st.sampled_from(["Multiworld", "Co-op", "Race"]))
        j["syncShared"] = draw(st.lists(st.sampled_from(["Skills", "World Events", "Teleporters", "Upgrades", "Misc"]),
                                        unique=True))
    if draw(st.integers(0, 3)) == 0:
        closed = "ClosedDungeons" in variations
        spawn = draw(st.sampled_from(["Grove", "Swamp", "Valley", "Random"] if closed else ["Grove", "Ginso", "Random"]))
        if not double_skills_strand_the_spawn((["--easy"] if "DoubleSkills" in variations else []) + ["--start", spawn]):
            j["spawn"] = spawn
    if "WorldTour" in variations:
        j["relicCount"] = draw(st.integers(1, 11))
    if "WarmthFrags" in variations:
        j["fragCount"] = draw(st.integers(10, 40))
        j["fragReq"] = draw(st.integers(1, j["fragCount"]))
    if "EnemyRando" in variations and draw(st.booleans()):
        j["enemyOpts"] = draw(enemy_opts())
    return j
