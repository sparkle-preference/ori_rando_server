"""The seed page's bingo settings have to survive the trip to the board's modal.

Three builders hand the board its opening settings -- two in MainPage.js and
_bingo_board_url in main.py -- and the board's constructor reads them back.
A setting that one side stops emitting is silently ignored by the other, so
both sides are scraped out of the source here.

Run from the repo root:  python3 -m unittest test.bingo_board_url_test -v
"""
import io
import os
import re
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN = os.path.join(HERE, "main.py")
BINGO = os.path.join(HERE, "map", "src", "Bingo.js")
PAGE = os.path.join(HERE, "map", "src", "MainPage.js")

# discovery rides as disc: the board treats a count of 0 as off
SENT_AS = {"bingoDisc": "disc"}


def read(path):
    with io.open(path, encoding="utf-8") as f:
        return f.read()


def advanced_tab_settings():
    """The keys paramsJson hangs on a bingo seed, i.e. what the tab collects."""
    block = re.search(r'url \+= "\?bingo=1"(.*?)\n\s*\}', read(PAGE), re.S)
    assert block, "paramsJson no longer builds the bingo block"
    return set(re.findall(r"json\.(\w+)", block.group(1)))


def board_ctor(bingo):
    """Bingo.js declares BingoBoard first, so an unanchored scrape reads that one."""
    got = re.search(r"export default class Bingo\b.*?constructor\(props\) \{.*?\n    \}",
                    bingo, re.S)
    assert got, "the board constructor moved"
    return got.group(0)


class BingoBoardUrlTestCase(unittest.TestCase):

    def emitted_by(self, text, what):
        got = set(re.findall(r"[?&](\w+)=", text))
        self.assertTrue(got, "%s builds no query string" % what)
        return got

    def test_advanced_tab_settings_all_reach_the_url(self):
        want = {SENT_AS.get(k, k) for k in advanced_tab_settings()}

        page = read(PAGE)
        helper = re.search(r"bingoBoardParams = \(\) => \{(.*?)\n    \}", page, re.S)
        self.assertIsNotNone(helper, "MainPage no longer builds the board's params")
        # the helper is a suffix; bingoLines rides the base url next to game_id
        client = self.emitted_by(helper.group(1), "bingoBoardParams")
        client |= self.emitted_by("".join(re.findall(r"`/bingo/board\?[^`]*`", page)),
                                  "MainPage's board urls")
        self.assertEqual(want - client, set(), "the seed page drops these")

        server = re.search(r"def _bingo_board_url\(.*?\n    return url", read(MAIN), re.S)
        self.assertIsNotNone(server, "_bingo_board_url is gone from main.py")
        self.assertEqual(want - self.emitted_by(server.group(0), "_bingo_board_url"),
                         set(), "the server redirect drops these")

    def test_board_reads_every_param_the_seed_page_sends(self):
        want = {SENT_AS.get(k, k) for k in advanced_tab_settings()}
        bingo = read(BINGO)

        read_here = set(re.findall(r'searchParams\.(?:get|has)\("(\w+)"\)', board_ctor(bingo)))
        self.assertEqual(want - read_here, set(), "the board never reads these")

        # a stale param outliving its board would reopen the modal on it
        strip = re.search(r"\[([^\]]*)\]\.forEach\(p => \{", bingo)
        self.assertIsNotNone(strip, "updateUrl no longer strips the seed's params")
        stripped = set(re.findall(r'"(\w+)"', strip.group(1)))
        self.assertEqual(want - stripped, set(), "updateUrl leaves these behind")

    def test_board_defaults_come_from_the_url(self):
        """The four settings that used to be hardcoded in the initial state."""
        ctor = board_ctor(read(BINGO))
        for literal in ('squareCount: 13', 'goalMode: "bingos"',
                        'difficulty: "normal"', 'meta: false'):
            self.assertNotIn(literal, ctor,
                             "%s is hardcoded again, so the url cannot set it" % literal)


if __name__ == "__main__":
    unittest.main()
