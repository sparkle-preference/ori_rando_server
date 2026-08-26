"""What the tracker map is told about each player.

`userdata` feeds /tracker/game/<gid>/fetch/gamedata, and GameTracker destructures
the result. Nothing else pins the shape, so a key that quietly appears or leaves
here shows up as players with no icon rather than as a failure.

Run from the repo root:  python3 -m unittest test.tracker_userdata_test -v
"""
import unittest

from test.ndb_base import EmulatorTestCase


class UserdataTestCase(EmulatorTestCase):

    GID = 900

    def player(self, pid, user=None):
        from models import Game, Player
        game = Game(id=self.GID)
        game.put()
        p = Player(id="%s.%s" % (self.GID, pid), user=user.key if user else None)
        p.put()
        return p

    def test_the_keys_are_exactly_what_the_map_reads(self):
        self.assertEqual(set(self.player(1).userdata().keys()), {"name", "pid"},
                         "GameTracker keys its icons off pid alone")

    def test_a_signed_out_player_is_named_by_number(self):
        got = self.player(3).userdata()
        self.assertEqual((got["name"], got["pid"]), ("Player 3", 3))

    def test_a_signed_in_player_is_named_by_account(self):
        from models import User
        u = User(id="tracked", name="lapis")
        u.put()
        self.assertEqual(self.player(2, u).userdata()["name"], "lapis")

    def test_the_account_does_not_change_the_number(self):
        from models import User
        u = User(id="tracked", name="lapis")
        u.put()
        self.assertEqual(self.player(2, u).userdata()["pid"], 2,
                         "the number is the slot in the game, not a profile setting")


if __name__ == "__main__":
    unittest.main()
