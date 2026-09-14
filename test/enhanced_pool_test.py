"""ES|* and ES|**: Enhanced skills rolled from the item pool.

Neither becomes a pickup of its own. The rolled skills ride out on their world's spawn
multipickup, which is the only delivery that reaches a skill the seed never places -- Spirit
Flame in most presets, and anything a trimmed pool leaves out.
"""
import glob
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cli_gen import CLISeedParams
from seedbuilder.generator import SeedGenerator

ENHANCED = {"410": "SpiritFlame", "411": "WallJump", "412": "ChargeFlame", "413": "DoubleJump",
            "414": "Bash", "415": "Stomp", "416": "Glide", "417": "Climb", "418": "ChargeJump",
            "419": "Dash", "420": "Grenade", "422": "Water"}


def generate(seed, pool=None, world_pools=None, args=()):
    """-> {world number: [seed line]}. pool goes to every world; world_pools, when given, is
    a per-world list and pool is ignored."""
    outdir = tempfile.mkdtemp(prefix="enhanced_pool_")
    orig = SeedGenerator.setSeedAndPlaceItems

    def patched(sg, params, **kwargs):
        if world_pools:
            params.world_settings = [
                {"itemPool": dict(params.item_pool or {}, **extra)} if extra else None
                for extra in world_pools]
        elif pool:
            params.item_pool = dict(params.item_pool or {}, **pool)
        return orig(sg, params, **kwargs)

    old_argv = sys.argv
    sys.argv = ["cli_gen", "--output-dir", outdir, "--preset", "standard", "--seed", seed] + list(args)
    SeedGenerator.setSeedAndPlaceItems = patched
    try:
        CLISeedParams().from_cli()
    finally:
        SeedGenerator.setSeedAndPlaceItems = orig
        sys.argv = old_argv

    worlds = {}
    for n, path in enumerate(sorted(glob.glob(os.path.join(outdir, "*.bfr"))), start=1):
        with open(path) as f:
            worlds[n] = [l for l in f.read().splitlines()[1:] if l and not l.startswith("//")]
    shutil.rmtree(outdir, ignore_errors=True)
    return worlds


def spawn_line(lines):
    return next((l for l in lines if l.split("|")[0] == "2"), "")


def granted(lines):
    """-> the Enhanced ids on this world's spawn."""
    members = spawn_line(lines).split("|")[2].split("/") if spawn_line(lines) else []
    return {members[i + 1] for i, m in enumerate(members)
            if m == "RB" and i + 1 < len(members) and members[i + 1] in ENHANCED}


def enhanced_elsewhere(lines):
    return [l for l in lines if l.split("|")[0] != "2"
            and any("RB/" + rb in l or "RB," + rb in l for rb in ENHANCED)]


class EnhancedPoolTests(unittest.TestCase):
    def test_weighted_rolls_are_distinct_and_never_wall_jump(self):
        """Wall Jump is the one skill ES|* will not roll, and no two rolls agree."""
        for seed in ("espool1", "espool2", "espool3"):
            got = granted(generate(seed, pool={"ES|*": [6]})[1])
            self.assertNotIn("411", got, "%s rolled Enhanced Wall Jump from ES|*" % seed)
            self.assertGreaterEqual(len(got), 6, "%s: %s" % (seed, sorted(got)))

    def test_five_weighted_rolls_always_bring_sein(self):
        """Each ES|* adds a fifth to Sein's chance, so five of them is a certainty -- and
        Spirit Flame not being a placement in this preset no longer matters."""
        for seed in ("essein1", "essein2", "essein3"):
            self.assertIn("410", granted(generate(seed, pool={"ES|*": [5]})[1]), seed)

    def test_unweighted_reaches_every_enhanced_skill(self):
        """Twelve ES|** exhaust the list, Spirit Flame and Wall Jump included."""
        self.assertEqual(granted(generate("esflat1", pool={"ES|**": [12]})[1]), set(ENHANCED))

    def test_nothing_enhanced_is_placed_in_the_world(self):
        """They ride the spawn or nowhere: no location holds one."""
        worlds = generate("esplace", pool={"ES|**": [12]})
        self.assertEqual(enhanced_elsewhere(worlds[1]), [])

    def test_riding_along_costs_the_seed_no_locations(self):
        """The pool slot an ES burns comes back as an EX, so the line count is unmoved."""
        self.assertEqual(len(generate("esbalance", pool={"ES|*": [4]})[1]),
                         len(generate("esbalance")[1]))

    def test_the_spawn_keeps_its_warp_save_last(self):
        """A non-Glades spawn ends on the warp save; the Enhanced go in ahead of it."""
        worlds = generate("esforlorn", pool={"ES|**": [12]}, args=("--start", "Forlorn"))
        members = spawn_line(worlds[1]).split("|")[2].split("/")
        self.assertIn("WS", members, spawn_line(worlds[1]))
        self.assertEqual(members.index("WS"), len(members) - 2, spawn_line(worlds[1]))


class EnhancedPoolMultiworldTests(unittest.TestCase):
    ARGS = ("--players", "3", "--share-mode", "multiworld")

    def test_only_the_asking_world_is_given_enhanced_skills(self):
        """One world's ES|** reaches that world's spawn and nobody else's."""
        worlds = generate("esmw", args=self.ARGS, world_pools=[{"ES|**": [6]}, None, None])
        self.assertEqual(len(granted(worlds[1])), 6, sorted(granted(worlds[1])))
        for p in (2, 3):
            self.assertEqual(granted(worlds[p]), set(), "world %s was given Enhanced skills" % p)

    def test_no_enhanced_skill_crosses_a_world(self):
        """A spawn grant is the owner's own line, so none of this needs a multiworld ref."""
        worlds = generate("esmw", args=self.ARGS, world_pools=[{"ES|**": [6]}, None, None])
        for p, lines in worlds.items():
            self.assertEqual(enhanced_elsewhere(lines), [], "world %s" % p)


if __name__ == "__main__":
    unittest.main()
