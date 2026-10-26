"""Hypothesis profiles for test/*_props.py, picked by HYPOTHESIS_PROFILE: dev (default), ci or deep."""
import os
import unittest

from hypothesis import HealthCheck, settings

PROFILE = os.environ.get("HYPOTHESIS_PROFILE", "dev")
SCALE = {"dev": 0.2, "ci": 1, "deep": 5}[PROFILE]
DEEP = PROFILE == "deep"

_common = dict(deadline=None, suppress_health_check=[HealthCheck.too_slow])
settings.register_profile("dev", **_common)
settings.register_profile("ci", database=None, print_blob=True, **_common)
settings.register_profile("deep", database=None, print_blob=True, **_common)
settings.load_profile(PROFILE)


def examples(n):
    """A test's ci example count, scaled to the active profile."""
    return max(1, int(round(n * SCALE)))


deep_only = unittest.skipUnless(DEEP, "deep profile only (HYPOTHESIS_PROFILE=deep)")
