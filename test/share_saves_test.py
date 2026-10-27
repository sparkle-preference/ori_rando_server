"""Share Saves: a share type no pickup has, read by the client off the flag line.

Run from the repo root:  python -m unittest test.share_saves_test -v
"""
import io
import os
import re
import unittest

import google.auth.credentials
from google.cloud import ndb

from enums import ShareType
from pickups import Pickup
from seedbuilder.seedparams import JSON_SHARE, SHARE_FROM_LABEL, MultiplayerOptions, SeedGenParams

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(HERE, "map", "src")


def read(name):
    with io.open(os.path.join(SRC, name), encoding="utf-8-sig") as f:
        return f.read()


def page_share_labels():
    page = read("MainPage.js")
    lists = re.findall(r"shareButtons\(\[(.*?)\]", page)
    assert len(lists) == 2, "the share button lists moved"
    return {label for body in lists for label in re.findall(r'"([^"]+)"', body)}


def page_label_map():
    pmap = re.search(r"let pMap = \{(.*?)\}", read("MainPage.js"))
    assert pmap, "pMap moved"
    return dict(re.findall(r'"([^"]+)": "([^"]+)"', pmap.group(1)))


class ShareLabelTestCase(unittest.TestCase):
    def test_every_button_label_round_trips(self):
        pmap = page_label_map()
        for label in page_share_labels():
            sent = pmap.get(label, label)
            st = ShareType.mk(SHARE_FROM_LABEL.get(sent, sent.replace(" ", "")))
            self.assertIsNotNone(st, "%s reaches the server as no share type" % label)
            self.assertEqual(st.value, sent, "%s must be sent in its flag spelling" % label)
            self.assertEqual(JSON_SHARE(st), label, "%s comes back from to_json as another label" % label)

    def test_saved_labels_still_parse(self):
        # stored presets hold the button labels, not the flag spelling
        opts = MultiplayerOptions.from_json({"players": 2, "coopGameMode": "Multiworld",
                                             "shared": ["World Events", "Saves"]})
        self.assertEqual(opts.shared, [ShareType.EVENT, ShareType.SAVES])

    def test_plando_editor_types_are_flag_spellings(self):
        types = re.search(r"const SHARE_TYPES = \[(.*?)\]", read("PlandoBuilder.js"))
        self.assertIsNotNone(types, "SHARE_TYPES moved")
        for t in re.findall(r'"([^"]+)"', types.group(1)):
            self.assertEqual(ShareType(t).value, t)

    def test_both_modes_default_it_on(self):
        state = re.search(r"shared: (\[.*?\]), mwShared: (\[.*?\])", read("MainPage.js"))
        self.assertIsNotNone(state, "the share defaults moved")
        self.assertIn('"Saves"', state.group(1))
        self.assertIn('"Saves"', state.group(2))

    def test_no_pickup_carries_it(self):
        # sharing Saves must move no items between players
        for cls in Pickup.subclasses():
            self.assertNotEqual(cls.share_type, ShareType.SAVES, cls.__name__)
            for pid in list(getattr(cls, "names", {})) + list(getattr(cls, "bits", {})):
                p = Pickup.n(cls.code, pid)
                self.assertNotEqual(p and p.share_type, ShareType.SAVES, "%s|%s" % (cls.code, pid))


class ShareSavesFlagTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        creds = google.auth.credentials.AnonymousCredentials()
        cls.ndb_client = ndb.Client(project="unit-test", credentials=creds)

    def setUp(self):
        self._ctx = self.ndb_client.context()
        self._ctx.__enter__()

    def tearDown(self):
        self._ctx.__exit__(None, None, None)

    def flags(self, mode, shared):
        params = SeedGenParams.from_json({"seed": "1", "paths": ["casual-core", "standard-core"], "players": 2,
                                          "tracking": True, "coopGameMode": mode, "coopGenMode": "cloned",
                                          "syncShared": shared}, store=False)
        return params.flag_line().split("|")[0].split(",")

    def test_multiworld_carries_it(self):
        flags = self.flags("Multiworld", ["Saves"])
        self.assertIn("share=Saves", flags)
        self.assertIn("mode=Multiworld", flags)

    def test_coop_carries_it(self):
        self.assertIn("share=Skills+Saves", self.flags("Shared", ["Skills", "Saves"]))


if __name__ == "__main__":
    unittest.main()
