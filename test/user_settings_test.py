"""One JSON column holds the preferences that do not each deserve a column.

`USER_SETTINGS` is the registry: a key in it has a default and a label, and both
/user/settings routes loop over it rather than naming keys one at a time. A key
absent from it can be neither read nor written, which is what keeps the modal and
the datastore from drifting apart. `settings_wire_test` pins the wire; this pins
the column and the one thing the first key does.

Run from the repo root:  python3 -m unittest test.user_settings_test -v
"""
import io
import os
import re
import unittest

from test.ndb_base import NdbTestCase

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(HERE, "map", "src", "MainPage.js")


class UserSettingsTestCase(NdbTestCase):

    def user(self, **kw):
        from models import User
        return User(id="settings-test", **kw)

    def test_an_untouched_account_gets_the_registered_default(self):
        from models import USER_SETTINGS
        u = self.user()
        for key, spec in USER_SETTINGS.items():
            self.assertEqual(u.setting(key), spec["default"])

    def test_a_stored_value_wins_over_the_default(self):
        self.assertIs(self.user(settings={"restoreLastSeed": False}).setting("restoreLastSeed"),
                      False)

    def test_writing_one_key_leaves_the_rest_alone(self):
        u = self.user(settings={"somethingElse": 7})
        u.set_setting("restoreLastSeed", False)
        self.assertEqual(u.settings, {"somethingElse": 7, "restoreLastSeed": False})

    def test_a_write_replaces_the_dict_instead_of_editing_it(self):
        """A JsonProperty mutated in place is not reliably marked dirty, so the
        put would drop the change with nothing raising anywhere."""
        u = self.user()
        held = {"restoreLastSeed": True}
        u.settings = held
        u.set_setting("restoreLastSeed", False)
        self.assertEqual(held, {"restoreLastSeed": True}, "the caller's dict was edited")
        self.assertIs(u.setting("restoreLastSeed"), False)

    def test_an_unregistered_key_has_no_default_to_give(self):
        with self.assertRaises(KeyError):
            self.user().setting("neverRegistered")

    def test_every_registered_key_has_both_halves(self):
        from models import USER_SETTINGS
        for key, spec in USER_SETTINGS.items():
            self.assertIn("default", spec, "%s has no default" % key)
            self.assertTrue(spec.get("label"), "%s has no label for a save to report" % key)


class SeedgenRestoreGateTestCase(unittest.TestCase):
    """restoreLastSeed gates opening on the last seed, and nothing else about it."""

    def page(self):
        with io.open(PAGE, encoding="utf-8") as f:
            return f.read()

    def block(self, pattern):
        got = re.search(pattern, self.page(), re.S)
        self.assertIsNotNone(got, "%s no longer matches the page" % pattern)
        return got.group(0)

    def test_the_restore_consults_the_flag(self):
        self.assertIn("this.restoreLastSeed",
                      self.block(r"restoreLastUsed = \(\) => \{.*?\n    \}"))

    def test_the_flag_comes_off_the_preset_list(self):
        self.assertIn("restoreLastSeed", self.block(r"loadSspList = .*?\n    \}\)"))

    def test_the_page_takes_a_baseline_frame_of_its_own(self):
        """Undo's frame 0 used to be a side effect of the restore writing to the
        form. With the toggle off nothing writes at load, so without a baseline
        of its own the user's first edit IS frame 0 and undo has nowhere to go."""
        self.assertIn("this.history.touch()",
                      self.block(r"componentDidMount\(\) \{.*?\n    \}"))

    def test_last_seed_stays_offered_when_the_toggle_is_off(self):
        """Off means "do not open on it", not "forget it": /reroll still writes
        latest, and the dropdown entry stays pickable by hand."""
        self.assertIn("sspHasLatest: !!hasLatest", self.block(r"loadSspList = .*?\n    \}\)"),
                      "the dropdown entry must not be gated on the toggle")


if __name__ == "__main__":
    unittest.main()
