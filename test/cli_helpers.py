"""cli_gen in a test: the seed and spoiler text it writes, or the params it would have walked."""
import os
import shutil
import sys
import tempfile
from unittest import mock

from cli_gen import CLISeedParams
from seedbuilder.generator import SeedGenerator


def cli_lines(extra, seed="test", out=None):
    """Seed and spoiler text from cli_gen with the standard test flags."""
    out = out or tempfile.mkdtemp(prefix="cli_")
    old = sys.argv
    sys.argv = ["cli_gen", "--output-dir", out, "--preset", "standard", "--force-trees",
                "--balanced", "--seed", seed] + extra
    try:
        CLISeedParams().from_cli()
        files = {}
        for name in os.listdir(out):
            with open(os.path.join(out, name)) as f:
                files[name] = f.read().splitlines()
        return files
    finally:
        sys.argv = old
        shutil.rmtree(out, ignore_errors=True)


def cli_params(extra, seed="test"):
    captured = []
    with mock.patch.object(SeedGenerator, "setSeedAndPlaceItems", lambda sg, params, **kw: captured.append(params)):
        cli_lines(extra, seed)
    return captured[0]
