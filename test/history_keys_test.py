"""Undo restores the keys in HIST_KEYS and silently forgets every other one.

A setting the seedgen page sends but the history does not track has no error and
no failing build: it just never rewinds. This reads both lists out of the source
so adding a setting without tracking it fails here instead of in the browser.

The list is hand-authored on purpose -- it also holds display mirrors and preset
fields paramsJson never reads, and those cannot be pinned from this direction.

Run from the repo root:  python3 -m unittest test.history_keys_test -v
"""
import io
import os
import re
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(HERE, "map", "src", "MainPage.js")
HISTORY = os.path.join(HERE, "map", "src", "history.js")

# A key paramsJson sends that undo deliberately does not restore. Empty on purpose;
# anything added here needs a reason beside it.
UNTRACKED = set()


def read(path):
    with io.open(path, encoding="utf-8") as f:
        return f.read()


def hist_keys():
    block = re.search(r"const HIST_KEYS = \[(.*?)\]", read(HISTORY), re.S)
    assert block, "HIST_KEYS is gone from history.js"
    return re.findall(r'"(\w+)"', block.group(1))


def params_json_body():
    """Stop at the next sibling class property. generateSeed, loadSspList and
    mergeSettings all sit between this and settingsNow, and what they read off
    state is not what the page sends."""
    page = read(PAGE)
    rest = page[page.index("paramsJson = "):]
    nxt = re.search(r"\n    [a-zA-Z_]\w* = ", rest[1:])
    assert nxt, "paramsJson is the last thing in the class?"
    return rest[:nxt.start() + 1]


class HistoryKeysTestCase(unittest.TestCase):

    def test_every_setting_the_page_sends_is_tracked(self):
        reads = set(re.findall(r"this\.state\.(\w+)", params_json_body()))
        missing = sorted(reads - set(hist_keys()) - UNTRACKED)
        self.assertFalse(missing, "paramsJson sends %s, which undo would never restore. "
                                  "Add it to HIST_KEYS, or to UNTRACKED with a reason."
                                  % missing)

    def test_nothing_is_tracked_twice(self):
        keys = hist_keys()
        dupes = sorted({k for k in keys if keys.count(k) > 1})
        self.assertFalse(dupes, "a duplicate shifts every later key's position: %s" % dupes)

    def test_every_tracked_key_exists_on_the_page(self):
        page = read(PAGE)
        gone = [k for k in hist_keys() if not re.search(r"\b%s\b" % k, page)]
        self.assertFalse(gone, "HIST_KEYS names %s, which the page no longer has" % gone)

    def test_the_untracked_list_still_describes_something_real(self):
        reads = set(re.findall(r"this\.state\.(\w+)", params_json_body()))
        stale = sorted(UNTRACKED - reads)
        self.assertFalse(stale, "UNTRACKED excuses %s, which paramsJson no longer reads"
                                % stale)

    def test_a_frame_is_positional_so_order_is_load_bearing(self):
        """Frames store values by index, so the reader has to rebuild the same order.

        The writer's map body is not pinned -- a key may be massaged on the way in,
        as worldPresets is. Walking HIST_KEYS in order at both ends is the invariant.
        """
        self.assertIn("HIST_KEYS.map(k =>", read(HISTORY))
        self.assertIn("HIST_KEYS.forEach", read(PAGE))


if __name__ == "__main__":
    unittest.main()
