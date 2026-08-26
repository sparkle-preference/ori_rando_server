"""The settings modal and /user/settings have to agree on the wire.

Both sides are read out of the source, so renaming a field on one without the
other fails here instead of in the browser. Route tests cannot catch it: they
post whatever the route reads, so the two agree by construction.

Run from the repo root:  python3 -m unittest test.settings_wire_test -v
"""
import io
import os
import re
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN = os.path.join(HERE, "main.py")
BAR = os.path.join(HERE, "map", "src", "SiteBar.js")


def read(path):
    with io.open(path, encoding="utf-8") as f:
        return f.read()


def route_body(name):
    body = re.search(r"def %s\(\):.*?(?=\n@app\.route)" % name, read(MAIN), re.S)
    assert body, "%s is gone from main.py" % name
    return body.group(0)


class SettingsWireTestCase(unittest.TestCase):

    def posted_fields(self):
        got = re.search(r"let fields = \{([^}]*)\}", read(BAR))
        self.assertIsNotNone(got, "the modal no longer builds a fields object")
        return set(re.findall(r"(\w+):", got.group(1)))

    def test_the_modal_posts_only_fields_the_route_reads(self):
        body = route_body("user_set_settings")
        served = set(re.findall(r'request\.form\.get\("(\w+)"\)', body))
        served |= set(re.findall(r'"(\w+)" in request\.form', body))
        extra = self.posted_fields() - served
        self.assertFalse(extra, "the modal posts %s, which the route ignores" % sorted(extra))

    def test_the_route_reads_only_fields_the_modal_posts(self):
        body = route_body("user_set_settings")
        served = set(re.findall(r'request\.form\.get\("(\w+)"\)', body))
        served |= set(re.findall(r'"(\w+)" in request\.form', body))
        missing = served - self.posted_fields()
        self.assertFalse(missing, "the route reads %s, which nothing posts" % sorted(missing))

    def test_the_modal_reads_only_keys_the_getter_sends(self):
        body = route_body("user_get_settings")
        # keys land either in the dict literal or by assignment after it
        sent = set(re.findall(r'res\["(\w+)"\]', body)) | set(re.findall(r'"(\w+)":', body))
        loader = re.search(r"loadSettings = .*?\n    \}", read(BAR), re.S)
        self.assertIsNotNone(loader, "the modal no longer loads settings")
        read_keys = set(re.findall(r"res\.(\w+)", loader.group(0)))
        missing = read_keys - sent
        self.assertFalse(missing, "the modal reads %s, which the route never sends"
                         % sorted(missing))

    def test_the_save_posts_to_a_route_that_exists(self):
        called = set(re.findall(r'postNetForm\("(/[^"]+)"', read(BAR)))
        routed = set(re.findall(r"@app\.route\('(/user/settings[^']*)'", read(MAIN)))
        for url in called:
            self.assertIn(url, routed, "the modal posts to %s, which no route serves" % url)

    def test_opening_the_modal_does_not_read_every_user(self):
        """Name collisions are one indexed query against the name being typed,
        not the whole table shipped to the browser for it to search."""
        body = route_body("user_get_settings")
        self.assertNotIn("User.query()", body)
        self.assertNotIn(".fetch()", body)

    def test_every_theme_the_modal_can_show_is_one_the_model_accepts(self):
        """The modal renders whatever /user/settings sends, so the list has to
        come from the model rather than a second copy in the page."""
        self.assertIn("SITE_THEMES", route_body("user_get_settings"))
        self.assertNotIn("cerulean", read(BAR), "the page is keeping its own theme list")


if __name__ == "__main__":
    unittest.main()
