"""The seedgen page and the preset routes have to agree on the wire.

Both sides are read out of the source, so renaming one without the other fails
here instead of in the browser.

Run from the repo root:  python3 -m unittest test.preset_wire_test -v
"""
import io
import os
import re
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRESETS = os.path.join(HERE, "web", "presets.py")
PAGE = os.path.join(HERE, "map", "src", "MainPage.js")


def read(path):
    with io.open(path, encoding="utf-8") as f:
        return f.read()


class PresetWireTestCase(unittest.TestCase):
    def test_save_posts_the_field_the_route_reads(self):
        page = read(PAGE)
        field = re.search(r'postNetForm\("/preset/save",\s*\{(\w+):', page)
        self.assertIsNotNone(field, "the page no longer posts to /preset/save")
        # scoped to ssp_save: the module has other routes reading form fields
        body = re.search(r"def ssp_save\(\):.*?(?=\n@bp\.route)", read(PRESETS), re.S)
        self.assertIsNotNone(body, "ssp_save is gone")
        served = re.search(r'request\.form\.get\("(\w+)"\)', body.group(0))
        self.assertIsNotNone(served, "ssp_save no longer reads a form field")
        self.assertEqual(field.group(1), served.group(1),
                         "the page posts %r but the route reads %r"
                         % (field.group(1), served.group(1)))

    def test_every_preset_url_the_page_calls_is_routed(self):
        page = read(PAGE)
        main = read(PRESETS)
        routes = set(re.findall(r"@bp\.route\('(/preset/[^']*|/myPresets)'", main))
        # strip flask's <converters> so a template compares against a template
        shapes = {re.sub(r"<[^>]+>", "*", r) for r in routes}
        called = set(re.findall(r'["`](/preset/[^"`]*)["`]', page))
        for url in called:
            shape = re.sub(r"\$\{[^}]*\}", "*", url)
            self.assertIn(shape, shapes,
                          "the page calls %s, which no route serves" % url)

    def test_the_page_never_loads_a_seed_from_a_preset(self):
        """Only a ?param_id= rehydrate may fill the seed box. The lobby list is
        skipped for "Last Seed", so the guard cannot live there."""
        page = read(PAGE)
        never = re.search(r"const PRESET_NEVER_LOAD = \[([^\]]*)\]", page)
        self.assertIsNotNone(never, "PRESET_NEVER_LOAD is gone")
        self.assertIn('"seed"', never.group(1))
        lobby = re.search(r"const SSP_LOBBY_KEYS = \[([^\]]*)\]", page, re.S)
        self.assertNotIn('"seed"', lobby.group(1),
                         "seed is in the lobby list, which Last Seed loads anyway")

    def test_the_share_link_param_matches_what_the_page_reads(self):
        page = read(PAGE)
        read_by_page = re.search(r'url\.searchParams\.get\("(\w+)"\)\s*\|\|\s*""\)\.split\(":"\)', page)
        self.assertIsNotNone(read_by_page, "the page no longer parses a share link")
        emitted = re.search(r'<a href="/\?(\w+)=%s:%s">', read(PRESETS))
        self.assertIsNotNone(emitted, "the presets page no longer emits a load link")
        self.assertEqual(read_by_page.group(1), emitted.group(1),
                         "the page reads ?%s= but the link says ?%s="
                         % (read_by_page.group(1), emitted.group(1)))


if __name__ == "__main__":
    unittest.main()
