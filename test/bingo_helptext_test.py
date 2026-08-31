"""Every bingo square explains itself.

A card with no help lines renders an empty hover on the board, and nothing
else notices: generation succeeds, the goal plays fine, players just get a
tile they have to guess at. Sweep the generator's real output across the
shapes a board can take, so a new goal added without text fails here.

Run from the repo root:  python -m unittest test.bingo_helptext_test -v
"""
import random
import unittest

from bingo import BingoGenerator


class BingoHelpTextTestCase(unittest.TestCase):

    def _cards(self, **kw):
        return BingoGenerator.get_cards(random.Random(83117), **kw)

    def assert_explained(self, cards, what):
        for card in cards:
            j = card.to_json([], initial=True)
            name = j.get("name")
            self.assertTrue(j.get("disp_name"),
                            "%s: %r has no display name" % (what, name))
            lines = [l for l in j.get("help_lines", []) if str(l).strip()]
            self.assertTrue(lines, "%s: %r has no help text" % (what, name))
            for sub in (j.get("subgoals") or {}).values():
                self.assertTrue(str(sub.get("disp_name", "")).strip(),
                                "%s: %r subgoal %r has no display name"
                                % (what, name, sub.get("name")))

    def test_every_square_explains_itself(self):
        # the shapes a board can take; each axis changes which goals appear
        for kw in ({"difficulty": "easy"}, {"difficulty": "normal"},
                   {"difficulty": "hard"}, {"rando": True},
                   {"rando": True, "keysanity": True}, {"meta": True},
                   {"rando": True, "spawn": "Random"}):
            for roll in range(3):   # three boards per shape: goals rotate in
                rand = random.Random(1000 * roll + 7)
                cards = BingoGenerator.get_cards(rand, **kw)
                self.assertEqual(len(cards), 25, kw)
                self.assert_explained(cards, "%s roll %s" % (kw, roll))


if __name__ == "__main__":
    unittest.main()
