"""patchnotes.json is the whole source of truth for /patchnotes, the two feeds
and the Discord announcements, so a malformed release breaks all of them at
once. These pin the shape of the data and who each channel hears about.

Run from the repo root:  python3 -m unittest test.patchnotes_test -v
"""
import json
import os
import unittest

import main

DOC = json.load(open(os.path.join("map", "src", "patchnotes.json"), encoding="utf-8"))


def version_tuple(v):
    return tuple(int(n) for n in v.split("."))


class PatchNotesDataTestCase(unittest.TestCase):
    def test_releases_are_newest_first_and_unique(self):
        versions = [r["version"] for r in DOC["releases"]]
        self.assertEqual(len(versions), len(set(versions)))
        keys = [version_tuple(v) for v in versions]
        self.assertEqual(keys, sorted(keys, reverse=True))

    def test_every_change_is_well_formed(self):
        categories = set(DOC["categories"])
        for release in DOC["releases"]:
            where = release["version"]
            self.assertRegex(release["date"], r"^\d{4}-\d{2}-\d{2}$", where)
            self.assertIn(release.get("announce", "all"), ("all", "dev", "none"), where)
            self.assertTrue(release["changes"], where)
            for c in release["changes"]:
                self.assertIn(c["category"], categories, where)
                self.assertIn(c["importance"], ("major", "minor"), where)
                # no badge is a real third state, not an omission
                self.assertIn(c.get("type"), (None, "feature", "fix"), where)
                self.assertTrue(c["text"].strip(), where)
                self.assertIsInstance(c.get("sub", []), list)

    def test_the_newest_release_is_the_running_version(self):
        self.assertEqual(DOC["releases"][0]["version"], main.VERSION)


class AnnounceEmbedTestCase(unittest.TestCase):
    RELEASE = {
        "version": "9.9.9",
        "date": "2026-01-01",
        "changes": [
            {"text": "Big one.", "category": "Game", "importance": "major",
             "sub": ["with a detail"]},
            {"text": "Small one.", "category": "Game", "importance": "minor"},
        ],
    }

    def _body(self, **kw):
        return main.announce_embed(self.RELEASE, "https://x", **kw)["description"]

    def test_main_channel_gets_majors_only(self):
        body = self._body()
        self.assertIn("Big one.", body)
        self.assertIn("with a detail", body)
        self.assertNotIn("Small one.", body)

    def test_dev_channel_gets_everything(self):
        body = self._body(everything=True)
        self.assertIn("Big one.", body)
        self.assertIn("Small one.", body)

    def test_an_all_minor_release_still_says_something(self):
        minor_only = dict(self.RELEASE,
                          changes=[c for c in self.RELEASE["changes"]
                                   if c["importance"] == "minor"])
        self.assertIn("Small fixes only", main.announce_embed(minor_only, "https://x")["description"])
        # ...but the dev channel gets the actual list instead
        dev = main.announce_embed(minor_only, "https://x", everything=True)["description"]
        self.assertIn("Small one.", dev)
        self.assertNotIn("Small fixes only", dev)

    def test_the_embed_links_the_release_anchor(self):
        self.assertEqual(main.announce_embed(self.RELEASE, "https://x")["url"],
                         "https://x/patchnotes#9.9.9")


class AnnounceChannelSelectionTestCase(unittest.TestCase):
    """announce_patchnotes(channels=...) is what keeps catching one channel up
    from reposting to the other, so it has to reach the webhook lookup for
    exactly the channels asked for and no others."""

    def setUp(self):
        self.asked = []
        self.real = main.announce_webhook
        # record which channels get as far as looking up a hook, and report
        # every one as unconfigured so nothing tries to POST
        main.announce_webhook = lambda channel: self.asked.append(channel) or ""

    def tearDown(self):
        main.announce_webhook = self.real

    def test_no_channels_means_every_channel(self):
        main.announce_patchnotes("https://x")
        self.assertEqual(sorted(self.asked), sorted(main.ANNOUNCE_CHANNELS))

    def test_naming_one_channel_leaves_the_other_alone(self):
        for channel in main.ANNOUNCE_CHANNELS:
            with self.subTest(channel=channel):
                self.asked = []
                out = main.announce_patchnotes("https://x", channels={channel})
                self.assertEqual(self.asked, [channel])
                # an unconfigured hook is reported when it was asked for by name
                self.assertEqual(out, {channel: "no webhook configured"})

    def test_an_unconfigured_channel_is_silent_on_the_boot_path(self):
        self.assertEqual(main.announce_patchnotes("https://x"), {})


if __name__ == "__main__":
    unittest.main()
