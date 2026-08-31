"""The seedgen form and SeedGenParams.from_json have to agree on the wire.

paramsJson is the highest-traffic contract in the app: every seed rolled from
the site rides it. A key one side renames is not an error anywhere -- the
control still renders, from_json quietly takes its default -- so both sides
are scraped out of the source, settings_wire_test-style.

Run from the repo root:  python -m unittest test.params_wire_test -v
"""
import io
import os
import re
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(HERE, "map", "src", "MainPage.js")
PARAMS = os.path.join(HERE, "seedbuilder", "seedparams.py")

# read by from_json but never sent: pre-syncShared clients said "shared"
LEGACY_ALIASES = {"shared"}
# sent by the page but consumed by the route/UI layer, not from_json
ROUTE_ONLY = set()
# attached by generateSeed after paramsJson returns (the daily/vanilla dance)
CALLER_ATTACHED = {"seed"}


def read(path):
    with io.open(path, encoding="utf-8") as f:
        return f.read()


def params_json_body():
    got = re.search(r"paramsJson = \(\) => \{.*?return \{json: json", read(PAGE), re.S)
    assert got, "paramsJson moved"
    return got.group(0)


def page_emits():
    body = params_json_body()
    keys = set(re.findall(r"json\.(\w+)\s*=[^=]", body))
    # the literal keys of the initial object only; deeper literals are values
    seed_obj = re.search(r"let json = \{(.*?)\n        \}", body, re.S)
    assert seed_obj, "paramsJson no longer opens with a json literal"
    keys |= set(re.findall(r"""['"](\w+)['"]:""", seed_obj.group(1)))
    return keys


def from_json_reads():
    # the lobby keys land in MultiplayerOptions.from_json, the rest in
    # SeedGenParams.from_json; the wire is the union of the two readers
    bodies = re.findall(r"def from_json\(.*?\n    @|def from_json\(.*?\n    def ",
                        read(PARAMS), re.S)
    assert len(bodies) >= 2, "a from_json moved"
    return set(re.findall(r"""json(?:\.get\(|\[)['"](\w+)['"]""", "".join(bodies)))


class ParamsWireTestCase(unittest.TestCase):

    def test_every_key_the_page_sends_is_read(self):
        dropped = page_emits() - from_json_reads() - ROUTE_ONLY
        self.assertEqual(dropped, set(),
                         "from_json silently ignores these page keys")

    def test_every_key_the_server_reads_is_sent(self):
        phantom = from_json_reads() - page_emits() - LEGACY_ALIASES - CALLER_ATTACHED
        self.assertEqual(phantom, set(),
                         "from_json reads keys no page emits; dead or renamed")

    def test_caller_attached_keys_are_still_attached(self):
        gen = re.search(r"generateSeed = .*?postGenJson", read(PAGE), re.S)
        self.assertIsNotNone(gen, "generateSeed moved")
        for k in CALLER_ATTACHED:
            self.assertIn("json.%s = " % k, gen.group(0),
                          "%s stopped riding the build POST" % k)

    def test_the_scrapes_scraped_something(self):
        # both regexes silently matching nothing would pass the diffs above
        self.assertGreater(len(page_emits()), 30)
        self.assertGreater(len(from_json_reads()), 30)
