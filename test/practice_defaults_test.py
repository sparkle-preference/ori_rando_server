"""The default practice segments: the two /netcode/practice routes, and every file
shipped in practice_defaults/ being one the client will take.

Run from the repo root:  python3 -m unittest test.practice_defaults_test -v
"""
import contextlib
import hashlib
import os
import shutil
import tempfile
import unittest
import zipfile

import main
import models
import practice

# PracticeFolder.SafeName's rules: a name it would change is refused
INVALID = set('<>:"/\\|?*') | {chr(c) for c in range(32)}
DEVICES = {"CON", "PRN", "AUX", "NUL"} | {"COM%d" % n for n in range(1, 10)} | {"LPT%d" % n for n in range(1, 10)}
RESERVED = {"export", "map-tiles"}


class _FakeNdbClient(object):
    def context(self):
        return contextlib.nullcontext()


def _bfrp(path, entries):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED) as z:
        for name, data in entries.items():
            z.writestr(name, data)


class RoutesTestCase(unittest.TestCase):
    def setUp(self):
        self._client, models.client = models.client, _FakeNdbClient()
        self._secret = main.app.secret_key
        main.app.secret_key = main.app.secret_key or "practice-defaults-test"
        self.client = main.app.test_client()
        self._dir = practice.DIR
        self.tmp = tempfile.mkdtemp()
        practice.DIR = self.tmp

    def tearDown(self):
        models.client = self._client
        main.app.secret_key = self._secret
        practice.DIR = self._dir
        shutil.rmtree(self.tmp)

    def test_lists_names_without_the_extension(self):
        for name in ("Glades warmup.bfrp", "Bridge Skip.bfrp", "notes.txt"):
            _bfrp(os.path.join(self.tmp, name), {"segment.json": "{}"})
        r = self.client.get("/netcode/practice")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_data(as_text=True), "Bridge Skip\nGlades warmup")

    def test_order_file_puts_its_names_first(self):
        for name in ("a", "B", "c", "d"):
            _bfrp(os.path.join(self.tmp, name + ".bfrp"), {"segment.json": "{}"})
        with open(os.path.join(self.tmp, practice.ORDER), "w", encoding="utf-8-sig", newline="\r\n") as f:
            f.write("c\nD.bfrp\n\n missing \nc\n")
        r = self.client.get("/netcode/practice")
        self.assertEqual(r.get_data(as_text=True), "c\nd\na\nB")
        self.assertIsNotNone(practice.default_path("d.bfrp"))
        self.assertIsNone(practice.default_path("order.txt"))

    def test_serves_a_listed_file_by_its_escaped_name(self):
        _bfrp(os.path.join(self.tmp, "Bridge Skip (any%).bfrp"), {"segment.json": "{}", "save.sav": "x"})
        with open(os.path.join(self.tmp, "Bridge Skip (any%).bfrp"), "rb") as f:
            raw = f.read()
        r = self.client.get("/netcode/practice/Bridge%20Skip%20(any%25).bfrp")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data, raw)
        self.assertEqual(r.mimetype, "application/octet-stream")
        r.close()

    def test_nothing_outside_the_listing_is_served(self):
        _bfrp(os.path.join(self.tmp, "a.bfrp"), {})
        with open(os.path.join(self.tmp, "notes.txt"), "w") as f:
            f.write("no")
        for path in ("notes.txt", "missing.bfrp", "a", "..%2Fpractice.py", "..%2F..%2Fpractice_defaults%2Fa.bfrp"):
            self.assertEqual(self.client.get("/netcode/practice/" + path).status_code, 404, path)
        self.assertIsNone(practice.default_path("../a.bfrp"))

    def test_retired_demos_list_hashes_no_longer_shipped(self):
        shipped, gone, other = b"current demo", b"old demo", b"older variant demo"
        _bfrp(os.path.join(self.tmp, "Seg.bfrp"), {"segment.json": "{}", "ghosts/demo.ghost": shipped,
                                                   "variants/v/segment.json": "{}"})
        sha = {k: hashlib.sha1(v).hexdigest() for k, v in (("shipped", shipped), ("gone", gone), ("other", other))}
        with open(os.path.join(self.tmp, practice.RETIRED), "w", encoding="utf-8") as f:
            f.write("# replaced demos\n%s  Seg\n%s\n\n%s # variant v\n%s again\nnot-a-hash\n"
                    % (sha["gone"], sha["shipped"], sha["other"].upper(), sha["gone"]))
        r = self.client.get("/netcode/practice-retired")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_data(as_text=True), "%s\n%s" % (sha["gone"], sha["other"]))
        # once the variant ships that demo again, it leaves the list
        _bfrp(os.path.join(self.tmp, "Seg.bfrp"), {"segment.json": "{}", "ghosts/demo.ghost": shipped,
                                                   "variants/v/segment.json": "{}", "variants/v/ghosts/demo.ghost": other})
        self.assertEqual(self.client.get("/netcode/practice-retired").get_data(as_text=True), sha["gone"])

    def test_no_retired_file_lists_nothing(self):
        r = self.client.get("/netcode/practice-retired")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_data(as_text=True), "")

    def test_a_missing_folder_lists_nothing(self):
        practice.DIR = os.path.join(self.tmp, "gone")
        r = self.client.get("/netcode/practice")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_data(as_text=True), "")


class ShippedDefaultsTestCase(unittest.TestCase):
    """What gets dropped into practice_defaults/ must load in the game."""

    def files(self):
        return [f for f in os.listdir(practice.DIR) if f not in ("README.md", practice.ORDER, practice.RETIRED)]

    def test_retired_lines_are_comments_or_start_with_a_sha1(self):
        path = os.path.join(practice.DIR, practice.RETIRED)
        if not os.path.isfile(path):
            return
        with open(path, encoding="utf-8-sig") as f:
            for line in f:
                words = line.split("#", 1)[0].split()
                if words:
                    self.assertRegex(words[0], r"^[0-9a-f]{40}$", "%s: %r" % (practice.RETIRED, line))

    def test_order_names_only_shipped_files(self):
        shipped = {name.lower() for name in practice.defaults()}
        for name in practice.order():
            self.assertIn(name.lower(), shipped, "order.txt names %r, which has no .bfrp here" % name)

    def test_only_bfrp_files(self):
        for f in self.files():
            self.assertTrue(f.endswith(practice.EXT), "%s: not a .bfrp (the extension is lowercase)" % f)

    def test_names_survive_the_clients_safe_name(self):
        for name in practice.defaults():
            self.assertTrue(name and name == name.strip(), "%r: blank, or space at either end" % name)
            self.assertNotIn(".", name, "%s: a dot reads as an extension" % name)
            self.assertFalse(INVALID & set(name), "%s: Windows refuses %s" % (name, INVALID & set(name)))
            self.assertNotIn(name.upper(), DEVICES, "%s: a Windows device name" % name)
            self.assertNotIn(name.lower(), RESERVED, "%s: reserved in the practice folder" % name)

    def test_each_is_a_stored_zip_with_a_segment_and_a_save(self):
        for name in practice.defaults():
            path = practice.default_path(name + practice.EXT)
            with zipfile.ZipFile(path) as z:
                entries = {i.filename: i for i in z.infolist()}
                for entry in ("segment.json", "save.sav"):
                    self.assertIn(entry, entries, "%s: no %s" % (name, entry))
                for i in entries.values():
                    self.assertEqual(i.compress_type, zipfile.ZIP_STORED,
                                     "%s: %s is compressed; the game reads stored entries only" % (name, i.filename))


if __name__ == "__main__":
    unittest.main()
