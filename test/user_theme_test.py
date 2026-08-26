"""One field decides the theme, and it has to answer for accounts older than it.

`theme` is the control; `dark_theme` is the boolean it replaced. A user who has
not touched the new picker still has only the boolean, so `site_theme` reads
through to it, and `set_theme` keeps it in step for whatever it can express.

Run from the repo root:  python3 -m unittest test.user_theme_test -v
"""
import unittest

from test.ndb_base import NdbTestCase


class SiteThemeTestCase(NdbTestCase):

    def user(self, **kw):
        from models import User
        return User(id="theme-test", **kw)

    def test_an_untouched_account_follows_the_browser(self):
        self.assertEqual(self.user().site_theme(), "system")

    def test_the_old_boolean_still_answers(self):
        self.assertEqual(self.user(dark_theme=True).site_theme(), "dark")
        self.assertEqual(self.user(dark_theme=False).site_theme(), "light")

    def test_the_new_field_wins_over_the_old_boolean(self):
        u = self.user(dark_theme=True, theme="sketchy")
        self.assertEqual(u.site_theme(), "sketchy")

    def test_system_sticks_instead_of_falling_back(self):
        u = self.user(dark_theme=True)
        u.set_theme("system")
        self.assertEqual(u.site_theme(), "system",
                         "picking system must not read the old boolean back out")

    def test_a_mode_keeps_the_boolean_in_step(self):
        u = self.user()
        u.set_theme("dark")
        self.assertIs(u.dark_theme, True)
        u.set_theme("light")
        self.assertIs(u.dark_theme, False)

    def test_a_skin_leaves_the_boolean_with_nothing_to_say(self):
        u = self.user(dark_theme=True)
        u.set_theme("cyborg")
        self.assertEqual(u.site_theme(), "cyborg")
        self.assertIsNone(u.dark_theme, "a skin is neither light nor dark")

    def test_junk_lands_on_system(self):
        u = self.user()
        u.set_theme("'; DROP TABLE users--")
        self.assertEqual(u.site_theme(), "system")

    def test_every_offered_theme_round_trips(self):
        from models import SITE_THEMES
        for name in SITE_THEMES:
            u = self.user()
            u.set_theme(name)
            self.assertEqual(u.site_theme(), name)

    def test_the_offered_list_has_no_duplicates(self):
        from models import SITE_THEMES
        self.assertEqual(len(SITE_THEMES), len(set(SITE_THEMES)))


class ThemeBrightnessTestCase(NdbTestCase):
    """Components ask resolve_dark whether they are dark, and the server feeds
    it. A skin has a brightness, so picking one has to answer that question."""

    def user(self, **kw):
        from models import User
        return User(id="brightness-test", **kw)

    def test_system_admits_it_cannot_know(self):
        self.assertIsNone(self.user(theme="system").theme_dark(),
                          "only the browser knows, so the page must be left to ask it")

    def test_the_modes_answer_for_themselves(self):
        self.assertIs(self.user(theme="dark").theme_dark(), True)
        self.assertIs(self.user(theme="light").theme_dark(), False)

    def test_a_dark_skin_reads_dark(self):
        self.assertIs(self.user(theme="cyborg").theme_dark(), True)

    def test_a_light_skin_reads_light(self):
        self.assertIs(self.user(theme="sketchy").theme_dark(), False)

    def test_the_old_boolean_still_answers_for_old_accounts(self):
        self.assertIs(self.user(dark_theme=True).theme_dark(), True)

    def test_every_dark_skin_is_a_theme_you_can_pick(self):
        from models import DARK_SKINS, SITE_THEMES
        self.assertTrue(DARK_SKINS <= set(SITE_THEMES),
                        "a skin nobody can choose classifies nothing")


if __name__ == "__main__":
    unittest.main()
