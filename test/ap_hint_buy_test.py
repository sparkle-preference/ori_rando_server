"""Who may spend a world's hint points, and what pressing buy does.

The rule follows what the room already allows: a passwordless room takes
'!hint' from anyone who knows its address, so the seed page does too; a
password means the room is closed, and then only a logged-in player of this
game may spend. Stubs in the save/restore style, driving netcode directly.

Run from the repo root:  python3 -m unittest test.ap_hint_buy_test -v
"""
import unittest

import netcode
from ap_models import HINT_OFFERED, HINT_REQUESTED


class _Key(object):
    def __init__(self, ident):
        self._id = ident

    def id(self):
        return self._id

    def __eq__(self, other):
        return isinstance(other, _Key) and other._id == self._id

    def __hash__(self):
        return hash(self._id)


class _Player(object):
    def __init__(self, user):
        self.user = user


class _Game(object):
    players = 2

    def __init__(self, gid=7, player_users=()):
        self.key = _Key(gid)
        self._players = [_Player(u) for u in player_users]

    def fetch_params(self):
        return type("P", (), {"ap_mode": True})()

    def get_players(self):
        return list(self._players)


class _Link(object):
    def __init__(self, password=None):
        self.password = password


class HintBuyTestCase(unittest.TestCase):
    OFFER = {5: {"s": HINT_OFFERED, "t": "", "a": 1, "k": "EV|0", "u": 0}}

    def setUp(self):
        self._orig = (netcode.ARCHIPELAGO, netcode.Game, netcode.APLink,
                      netcode.User, netcode.APHints, netcode.ap_bridge.heal)
        netcode.ARCHIPELAGO = True
        netcode.ap_bridge.heal = lambda gid: None
        self.rows = {(7, 1): dict(self.OFFER), (7, 2): {}}
        self.price = {(7, 1): (100, 10), (7, 2): (0, 0)}
        self.game = _Game()
        self.link = _Link()
        self.user = None
        test = self

        class _APLink(object):
            @staticmethod
            def with_id(gid):
                return test.link

        class _User(object):
            @staticmethod
            def get():
                return test.user

        class _APHints(object):
            @staticmethod
            def load(gid, world):
                return dict(test.rows.get((gid, world), {}))

            @staticmethod
            def price(gid, world):
                return test.price.get((gid, world), (0, 0))

            @staticmethod
            def request(gid, world, slot):
                cur = test.rows.get((gid, world), {}).get(slot) or {}
                if cur.get("s") != HINT_OFFERED:
                    return False
                test.rows[(gid, world)][slot] = dict(cur, s=HINT_REQUESTED)
                return True

        netcode.Game = type("G", (), {"with_id": staticmethod(lambda gid: test.game)})
        netcode.APLink, netcode.User, netcode.APHints = _APLink, _User, _APHints

    def tearDown(self):
        (netcode.ARCHIPELAGO, netcode.Game, netcode.APLink,
         netcode.User, netcode.APHints, netcode.ap_bridge.heal) = self._orig

    def buy(self, world=1, slot=5):
        return netcode.ap_buy_hint(7, {"world": world, "slot": slot})

    # --- who may spend ---

    def test_a_passwordless_room_takes_anyone(self):
        """Anyone with the address could '!hint' it by hand already."""
        self.assertEqual(self.buy()[0], 200)

    def test_a_password_refuses_a_stranger(self):
        self.link = _Link("hunter2")
        status, body = self.buy()
        self.assertEqual(status, 403)
        self.assertIn("login", body)

    def test_a_password_refuses_a_logged_in_non_player(self):
        self.link = _Link("hunter2")
        self.user = type("U", (), {"key": _Key("someone-else")})()
        self.assertEqual(self.buy()[0], 403)

    def test_a_password_takes_a_player_of_this_game(self):
        self.link = _Link("hunter2")
        me = _Key("me")
        self.user = type("U", (), {"key": me})()
        self.game = _Game(player_users=[me])
        self.assertEqual(self.buy()[0], 200)

    # --- what pressing it does ---

    def test_buying_marks_the_offer_requested(self):
        self.buy()
        self.assertEqual(self.rows[(7, 1)][5]["s"], HINT_REQUESTED)

    def test_a_second_press_is_refused_rather_than_charged_twice(self):
        self.assertEqual(self.buy()[0], 200)
        self.assertEqual(self.buy()[0], 409)

    def test_a_slot_that_is_not_for_sale_is_refused(self):
        self.assertEqual(self.buy(slot=99)[0], 409)

    def test_a_world_that_cannot_afford_it_is_refused_before_the_room_hears(self):
        self.price[(7, 1)] = (4, 10)
        status, body = self.buy()
        self.assertEqual(status, 402)
        self.assertEqual(self.rows[(7, 1)][5]["s"], HINT_OFFERED)

    def test_a_world_out_of_range_is_refused(self):
        self.assertEqual(self.buy(world=9)[0], 400)

    # --- what the page reads ---

    def test_the_listing_reports_offers_and_the_price_per_world(self):
        status, body = netcode.ap_hints(7)
        self.assertEqual(status, 200)
        self.assertEqual([w["world"] for w in body["worlds"]], [1, 2])
        self.assertEqual(body["worlds"][0]["offers"],
                         [{"slot": 5, "key": "EV|0", "name": "Water Vein"}])
        self.assertEqual((body["worlds"][0]["points"], body["worlds"][0]["cost"]), (100, 10))
        self.assertEqual(body["worlds"][1]["offers"], [])
        self.assertTrue(body["can_buy"])

    def test_the_listing_says_when_the_viewer_may_not_buy(self):
        self.link = _Link("hunter2")
        body = netcode.ap_hints(7)[1]
        self.assertFalse(body["can_buy"])
        self.assertIn("login", body["why"])

    def test_only_offers_are_listed(self):
        """A bought or answered hint is not for sale and must not be priced."""
        self.rows[(7, 1)][6] = {"s": HINT_REQUESTED, "k": "RB|300"}
        self.rows[(7, 1)][7] = {"s": "r", "t": "somewhere", "k": "SK|4"}
        body = netcode.ap_hints(7)[1]
        self.assertEqual(body["worlds"][0]["offers"],
                         [{"slot": 5, "key": "EV|0", "name": "Water Vein"}])


if __name__ == "__main__":
    unittest.main()
