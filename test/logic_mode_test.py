"""`?logic_mode=` on the url seedgen routes, for the bot.

Naming a Logic Mode button stands in for spelling out its paths, its path difficulty
and the variations it turns on. Everything else in the query still applies on top:
paths and vars add to the mode's, path_diff overrides it because a single value has
nothing to add to. An absent seed is the clock rather than an error, for the same
caller's sake.

The definitions are a second copy of the page's -- Lapis accepted that, since they do
not change -- so the last case here reads both and fails if they ever drift.

Run from the repo root:  python3 -m unittest test.logic_mode_test -v
"""
import io
import os
import re
import time
import unittest

from werkzeug.datastructures import MultiDict

from enums import (LogicPath, PathDifficulty, Variation, presets,
                   preset_path_diff, preset_variations)
from seedbuilder.seedparams import SeedGenParams
from test.ndb_base import NdbTestCase

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMMON = os.path.join(HERE, "map", "src", "common.js")
PAGE = os.path.join(HERE, "map", "src", "MainPage.js")


def read(path):
    with io.open(path, encoding="utf-8") as f:
        return f.read()


class LogicModeTestCase(NdbTestCase):

    def setUp(self):
        super(LogicModeTestCase, self).setUp()
        # from_url ends in put(); hand the entity back instead of storing it
        self._put = SeedGenParams.__dict__.get("put")
        SeedGenParams.put = lambda self: self

    def tearDown(self):
        if self._put is None:
            del SeedGenParams.put
        else:
            SeedGenParams.put = self._put
        super(LogicModeTestCase, self).tearDown()

    def build(self, seed="logicmode", **kw):
        """from_url over a query. seed=None leaves it out of the query entirely."""
        pairs = [("seed", seed)] if seed is not None else []
        for key, val in kw.items():
            for one in (val if isinstance(val, list) else [val]):
                pairs.append((key, one))
        return SeedGenParams.from_url(MultiDict(pairs))

    def test_a_mode_stands_in_for_its_paths(self):
        got = self.build(logic_mode="expert")
        self.assertEqual(set(got.logic_paths), presets["Expert"])

    def test_a_mode_brings_its_difficulty_and_variations(self):
        master = self.build(logic_mode="master")
        self.assertEqual(master.path_diff, PathDifficulty.HARD)
        self.assertIn(Variation.STARVED, master.variations)
        # glitched is Hard too, but is not Starved
        glitched = self.build(logic_mode="glitched")
        self.assertEqual(glitched.path_diff, PathDifficulty.HARD)
        self.assertNotIn(Variation.STARVED, glitched.variations)

    def test_a_mode_without_extras_keeps_the_ordinary_defaults(self):
        got = self.build(logic_mode="casual")
        self.assertEqual(got.path_diff, PathDifficulty.NORMAL)
        self.assertEqual(got.variations, [])

    def test_paths_add_to_the_mode_rather_than_replacing_it(self):
        got = self.build(logic_mode="casual", path="gjump")
        self.assertEqual(set(got.logic_paths), presets["Casual"] | {LogicPath.GJUMP})

    def test_variations_add_to_the_mode_rather_than_replacing_it(self):
        got = self.build(logic_mode="master", var="OpenWorld")
        self.assertEqual(set(got.variations), {Variation.STARVED, Variation.OPEN_WORLD})

    def test_an_explicit_path_diff_wins_over_the_mode(self):
        """A scalar cannot be added to, so the argument replaces rather than merges."""
        self.assertEqual(self.build(logic_mode="master", path_diff="Easy").path_diff,
                         PathDifficulty.EASY)

    def test_the_name_is_case_insensitive(self):
        for spelling in ("expert", "Expert", "EXPERT"):
            self.assertEqual(set(self.build(logic_mode=spelling).logic_paths),
                             presets["Expert"], spelling)

    def test_an_unknown_mode_is_refused_rather_than_ignored(self):
        """Silently rolling standard would hand the bot a seed nobody asked for."""
        self.assertIsNone(self.build(logic_mode="lunatic"))

    def test_a_query_with_neither_mode_nor_paths_is_still_refused(self):
        self.assertIsNone(self.build())

    def test_an_absent_seed_is_the_clock_rather_than_an_error(self):
        before = int(time.time())
        got = self.build(seed=None, logic_mode="standard")
        self.assertIsNotNone(got, "a bot with nothing to say about the seed still gets one")
        self.assertRegex(got.seed, r"^\d+$")
        self.assertTrue(before <= int(got.seed) <= int(time.time()) + 1,
                        "%s is not a plausible unix timestamp" % got.seed)

    def test_a_seed_that_was_given_is_left_alone(self):
        self.assertEqual(self.build(seed="handpicked", logic_mode="standard").seed, "handpicked")

    def test_paths_alone_still_work_untouched(self):
        got = self.build(path=["casual-core", "dbash"])
        self.assertEqual(got.logic_paths, [LogicPath.CASUAL_CORE, LogicPath.DBASH])
        self.assertEqual(got.path_diff, PathDifficulty.NORMAL)


class LogicModeRouteTestCase(unittest.TestCase):
    """A bot cannot read the log, so the route answers a typo itself. The check runs
    before from_url, which is why nothing here needs params stubbing."""

    def setUp(self):
        import contextlib
        import main
        import models

        class _FakeNdbClient(object):
            def context(self):
                return contextlib.nullcontext()
        self.main, self.models = main, models
        self._client = models.client
        models.client = _FakeNdbClient()
        self._secret = main.app.secret_key
        main.app.secret_key = main.app.secret_key or "logic-mode-route"
        self.client = main.app.test_client()

    def tearDown(self):
        self.models.client = self._client
        self.main.app.secret_key = self._secret

    def test_a_typo_is_a_409_naming_the_modes_that_exist(self):
        res = self.client.get("/generator/json?seed=x&logic_mode=lunatic")
        self.assertEqual(res.status_code, 409)
        said = res.get_json()["error"]
        self.assertIn("lunatic", said)
        for name in presets:
            self.assertIn(name, said, "the answer should list every mode")


class PresetsAgreeTestCase(unittest.TestCase):
    """The page and the server each hold the mode definitions. They are allowed to,
    on the grounds that they never change -- so this fails the moment one does."""

    def js_block(self, src, name):
        """None of the three has a nested object, so stop at the first brace -- two of
        them are one-liners, and .*? would run on into the next const."""
        got = re.search(r"const %s = \{([^}]*)\}" % name, src, re.S)
        self.assertIsNotNone(got, "%s is gone from the source" % name)
        return got.group(1)

    def test_the_path_lists_match(self):
        block = self.js_block(read(COMMON), "presets")
        js = {name.capitalize(): set(re.findall(r"'([\w-]+)'", body))
              for name, body in re.findall(r"(\w+):\s*\[(.*?)\]", block, re.S)}
        self.assertEqual(js, {k: {p.value for p in v} for k, v in presets.items()})

    def test_the_variations_match(self):
        block = self.js_block(read(PAGE), "varPaths")
        js = {name.capitalize(): set(re.findall(r'"(\w+)"', body))
              for name, body in re.findall(r'"(\w+)":\s*\[(.*?)\]', block, re.S)}
        self.assertEqual(js, {k: {v.value for v in vs} for k, vs in preset_variations.items()})

    def test_the_path_difficulties_match(self):
        block = self.js_block(read(PAGE), "diffPaths")
        js = {name.capitalize(): diff for name, diff in re.findall(r'"(\w+)":\s*"(\w+)"', block)}
        self.assertEqual(js, {k: v.value for k, v in preset_path_diff.items()})


if __name__ == "__main__":
    unittest.main()
