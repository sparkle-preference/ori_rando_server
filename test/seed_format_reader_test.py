"""Golden tests for the READERS of the multiworld/archipelago seed-line fields.

Companion to seed_format_golden_test, which pins the writers. These pin what each
consumer of the comma field extracts from a format-1 line, because every one of them
splits with a maxsplit and would parse a format-2 line without complaint, just wrongly.
Several tests deliberately assert today's WRONG answer for a format-2 shaped input; each
says so and says what format 2 must make it instead.

Run from the repo root:  python3 -m unittest test.seed_format_reader_test -v
"""
import contextlib
import unittest
from datetime import datetime

import google.auth.credentials
from google.cloud import ndb

import main
import models
from archipelago import annotate as annotate_mod
from archipelago import ap_bridge
from archipelago.annotate import annotate
from models import Game, HistoryLine, Player
from pickups import Pickup
from util import SEED_FORMAT
# the AP scout stand-in is defined once, next to the writer goldens
from test.seed_format_golden_test import _FakeScout, fields

class MultiworldItemReaderTests(unittest.TestCase):
    """pickups.MultiworldItem, the reader every /found POST goes through. It
    splits field 3 with maxsplit 2 and validates only the two fields ahead of
    that split, so anything appended to the id lands inside the display name."""

    def test_owner_and_slot_come_off_the_front_and_the_rest_is_the_name(self):
        item = Pickup.n("MW", "2,17,Bash")
        self.assertEqual((item.owner, item.slot), (2, 17))
        self.assertEqual(item.name, "Player 2's Bash")
        self.assertEqual(item.id, "2,17,Bash")  # whole field 3; this is what history stores

    def test_the_name_keeps_its_commas(self):
        """maxsplit 2 is a contract, not an accident: AP labels carry commas.
        It is also exactly what lets a format-2 tail through unnoticed."""
        item = Pickup.n("MW", "3,0,Bombs, Bow (P2)")
        self.assertEqual(item.name, "Player 3's Bombs, Bow (P2)")

    def test_the_only_rejections_are_a_missing_or_non_numeric_owner_or_slot(self):
        # "3,SK,0" is a manifest id -- the reader refuses it because SK is not
        # a number, which is the whole of its type checking
        for bad in ["3,SK,0", "2,17", "", "x,17,Bash", "-2,0,Bash", "2,-1,Bash"]:
            self.assertIsNone(Pickup.n("MW", bad), bad)

    def test_a_format_two_finder_id_parses_clean_and_names_the_item_wrong(self):
        """The silent failure this reader has to be fixed for. owner and slot
        still land, so slot flips keep working and nothing logs; only the name
        rots. Format 2 must make this "Player 2's Bash"."""
        item = Pickup.n("MW", "2,17,SK,0")
        self.assertIsNotNone(item)
        self.assertEqual((item.owner, item.slot), (2, 17))
        self.assertEqual(item.name, "Player 2's SK,0")

    def test_a_format_two_ap_reserved_id_swallows_all_four_new_fields(self):
        item = Pickup.n("MW", "3,0,P2,-1,AP,Bombs, Bow")
        self.assertEqual((item.owner, item.slot), (3, 0))
        self.assertEqual(item.name, "Player 3's P2,-1,AP,Bombs, Bow")

    def test_the_name_is_what_the_history_page_prints(self):
        """A history line stores code and id and rebuilds the pickup to print
        itself, so the name this reader builds is the name players read back."""
        t = datetime(2026, 1, 1)

        def printed(id):
            return HistoryLine(player=1, pickup_code="MW", pickup_id=id, coords=919772,
                               removed=False, timestamp=t).print_line(t)

        self.assertTrue(printed("2,17,Bash").startswith("found Player 2's Bash at "),
                        printed("2,17,Bash"))
        self.assertTrue(printed("2,17,SK,0").startswith("found Player 2's SK,0 at "),
                        printed("2,17,SK,0"))



class ApSpoilerCommaFieldTests(unittest.TestCase):
    """ap_spoiler splits the comma field twice: manifest lines into
    finder,code,id and this world's reserved AP lines into shadow,slot,label.
    Both use split(",", 2), an arity every format-2 line also satisfies."""

    K = 2
    WORLD = 1
    GID = 909
    PLACEMENTS = [
        ("2", "SK", "0", "Glades"),                        # plain local pickup
        ("919908", "MW", "3,0,AP Item #1", "Grove"),       # reserved, slot 0
        ("959960", "MW", "3,1,AP Item #2", "Sorrow"),      # reserved, slot 1
        ("1799708", "MW", "2,55,Valley teleporter", "Valley"),   # plain cross-world
        ("-2", "MW", "3,SK,0", "Glades"),                  # our export, manifest slot 0
        # native, and a TW id carries commas of its own
        ("-3", "MW", "2,TW,Warp to Ginso Escape,510,910,GinsoEscape", "Glades"),
    ]

    @classmethod
    def setUpClass(cls):
        import google.auth.credentials
        from google.cloud import ndb
        cls.ndb_client = ndb.Client(
            project="unit-test",
            credentials=google.auth.credentials.AnonymousCredentials())

    def setUp(self):
        from ap_models import APNames
        self._ctx = self.ndb_client.context()
        self._ctx.__enter__()
        self.rows = {}
        self._load, self._promises = APNames.load, APNames.load_promises
        APNames.load = staticmethod(
            lambda gid, world: self.rows.get(int(world), ({}, None)))
        APNames.load_promises = staticmethod(lambda gid, world: None)

    def tearDown(self):
        from ap_models import APNames
        APNames.load = staticmethod(self._load)
        APNames.load_promises = staticmethod(self._promises)
        self._ctx.__exit__(None, None, None)

    def spoiler(self, entries, extra=()):
        from enums import MultiplayerGameType
        from seedbuilder.seedparams import (MultiplayerOptions, Placement,
                                            SeedGenParams, Stuff)
        self.rows[self.WORLD] = (entries, 1)
        params = SeedGenParams(
            seed="apspoiler", players=self.K, tracking=False, ap_mode=True,
            ap_export=["skills"],
            sync=MultiplayerOptions(str_mode=MultiplayerGameType.MULTIWORLD.value),
            placements=[Placement(location=loc, zone=zone,
                                  stuff=[Stuff(code=code, id=id, player="1")])
                        for loc, code, id, zone in list(self.PLACEMENTS) + list(extra)])
        return params.ap_spoiler(self.WORLD, self.GID)

    def sections(self, text):
        """(what this world holds, incoming manifest), each name -> text."""
        world, _, incoming = text.partition("Incoming (this world's slot manifest):")
        pairs = lambda chunk: dict(tuple(p.strip() for p in l.strip().split("  ", 1))
                                   for l in chunk.splitlines() if "  " in l.strip())
        return pairs(world.split("This world:")[1]), pairs(incoming)

    def test_a_reserved_line_shows_the_whole_third_comma_piece(self):
        """The scout label is field 3 after two commas and nothing else --
        maxsplit 2 is what lets an item name carry its own comma."""
        world, _ = self.sections(
            self.spoiler({0: _FakeScout(to="Zelda", item="Bow, Arrows")}))
        self.assertIn("Bow, Arrows (Zelda)", world.values())

    def test_an_unscouted_reserved_line_is_counted_by_that_same_piece(self):
        text = self.spoiler({0: _FakeScout()})
        self.assertIn("1 locations not scouted yet", text)
        self.assertIn("AP Item #2", self.sections(text)[0].values())

    def test_a_cross_world_line_for_another_owner_is_named_by_pickup(self):
        """Only field 3's first piece decides: the shadow means read the label,
        anything else means hand the whole id to Pickup."""
        world, _ = self.sections(self.spoiler({0: _FakeScout()}))
        self.assertIn("Player 2's Valley teleporter", world.values())

    def test_the_manifest_split_is_finder_then_code_then_the_rest(self):
        """Finder first, then the code, then an id that keeps its own commas --
        a warp id carries three, so a wider split unpacks too many names."""
        _, incoming = self.sections(self.spoiler({0: _FakeScout()}))
        self.assertEqual(sorted(incoming), ["Bash", "Warp to Ginso Escape"])
        self.assertEqual(incoming["Bash"], "somewhere in the Archipelago")   # ours
        self.assertEqual(incoming["Warp to Ginso Escape"], "found by P2")    # native

    def test_a_format_two_shaped_reserved_line_is_read_without_error(self):
        """THE silent failure this module exists for: the format-2 comma field
        still splits into three, so its tail reaches the spoiler verbatim and
        the unscouted counter never sees the placeholder behind it."""
        text = self.spoiler({0: _FakeScout()},
                            extra=[("2919744", "MW", "3,4,P2,-1,SK,0", "Grotto")])
        self.assertIn("P2,-1,SK,0", self.sections(text)[0].values())
        self.assertIn("1 locations not scouted yet", text)


class _FetchSeedNdbClient(object):
    def context(self):
        return contextlib.nullcontext()


class _FetchSeedParams(object):
    """Feeds tracker_fetch_seed whatever lines a test wants, annotation and all."""
    ap_mode = True
    players = 2
    variations = []

    def __init__(self, lines):
        self.lines = lines

    def get_seed_data(self, player=1, no_door_zone=True):
        return self.lines

    def ap_named(self, seed_data, player, game_id):
        return seed_data


class _FetchSeedGame(object):
    def __init__(self, params):
        self._params = params
        self.params = self

    def get(self):
        return self._params

    def fetch_params(self):
        return self._params

    def player(self, pid, create=True, delay_put=False):
        class _P(object):
            def is_ap_shadow(self):
                return False

            def name(self):
                return "tester"

            def mw_names_field(self):
                return "1.Asm;2.Cap"
        return _P()


class TrackerFetchSeedFormatTests(unittest.TestCase):
    """What /tracker/.../fetch/player/N/seed pulls out of a seed line: field 3
    split(",", 2) for MW, field 5 for the AP annotation. Format 2 moves both,
    and every assertion here keeps parsing without raising."""

    def setUp(self):
        self._ndb = models.client
        models.client = _FetchSeedNdbClient()
        self._secret = main.app.secret_key
        main.app.secret_key = main.app.secret_key or "fetch-seed-test"
        self._with_id = models.Game.__dict__["with_id"]
        self.client = main.app.test_client()

    def tearDown(self):
        models.Game.with_id = self._with_id
        main.app.secret_key = self._secret
        models.client = self._ndb

    def seed(self, *lines):
        game = _FetchSeedGame(_FetchSeedParams(list(lines)))
        models.Game.with_id = staticmethod(lambda gid: game)
        r = self.client.get("/tracker/game/4242/fetch/player/1/seed")
        self.assertEqual(r.status_code, 200)
        return r.get_json()["seed"]

    def test_the_finder_label_is_everything_after_the_second_comma(self):
        """maxsplit 2 is load-bearing: AP item names carry commas, and today
        every one of them lands in the display name."""
        seed = self.seed(("1799708", "MW", "2,55,Bombs, Bow", "Valley"))
        self.assertEqual(seed["1799708"], "Cap's Bombs, Bow")

    def test_an_owner_with_no_wire_name_falls_back_to_player_n(self):
        seed = self.seed(("5000", "MW", "5,3,Bash", "Grove"))
        self.assertEqual(seed["5000"], "Player 5's Bash")

    def test_the_shadow_line_takes_its_item_from_field_five_not_the_label(self):
        seed = self.seed(("919908", "MW", "3,0,AP Item #7", "Grove", "P2;Grotto Keystone"))
        self.assertEqual(seed["919908"], "Cap's Grotto Keystone")

    def test_a_sixth_field_is_invisible_to_this_reader(self):
        seed = self.seed(("959960", "MW", "3,1,AP Item #8", "Sorrow", "P1;Bash", "12"))
        self.assertEqual(seed["959960"], "Bash")

    def test_an_empty_field_five_falls_back_to_the_label(self):
        seed = self.seed(("799804", "MW", "3,2,AP Item #9", "Grove", ""))
        self.assertEqual(seed["799804"], "AP Item #9")

    def test_a_plain_line_is_named_from_its_code_and_id(self):
        seed = self.seed(("2", "SK", "0", "Glades"), ("-3", "MW", "1,SK,0", "Glades"))
        self.assertEqual(seed["2"], "Bash")
        self.assertNotIn("-3", seed)

    def test_a_format_two_finder_line_parses_without_complaint(self):
        """The silent failure this site cannot detect: code,id splits clean at
        maxsplit 2 and the tracker renders the raw pair as the item name."""
        seed = self.seed(("1799708", "MW", "2,55,TP,Valley", "Valley"))
        self.assertEqual(seed["1799708"], "Cap's TP,Valley")

    def test_a_format_two_reserved_line_reads_as_an_unscouted_placeholder(self):
        """Fields 5 and 6 gone means the scouted branch never fires: the whole
        folded tail becomes the display name."""
        seed = self.seed(("919908", "MW", "3,0,P2,-1,KS,0", "Grove"))
        self.assertEqual(seed["919908"], "P2,-1,KS,0")


class _ModelsMwCase(unittest.TestCase):
    """A MULTIWORLD Game whose datastore-touching statics are stubbed, so the
    seed-line readers in models.py can be driven with no emulator. Slot flips,
    history lines and grant batches land on the objects the test holds."""

    @classmethod
    def setUpClass(cls):
        cls.ndb_client = ndb.Client(project="unit-test",
                                    credentials=google.auth.credentials.AnonymousCredentials())

    def setUp(self):
        self._ctx = self.ndb_client.context()
        self._ctx.__enter__()
        self._saved = {n: getattr(Player, n) for n in
                       ("mark_slot_txn", "mark_slots_txn", "signal_send_txn",
                        "append_hl_chunked_txn", "transaction_pickup_batch")}
        self._mark_history = Game.mark_history_txn
        Game.mark_history_txn = staticmethod(lambda key: None)

    def tearDown(self):
        for name, fn in self._saved.items():
            setattr(Player, name, fn)
        Game.mark_history_txn = self._mark_history
        self._ctx.__exit__(None, None, None)

    def game(self, shared=()):
        players = {pid: Player(id="88.%s" % pid, skills=0, events=0, teleporters=0,
                               bonuses={}, hints={}) for pid in (1, 2)}
        for p in players.values():
            p.put = lambda *a, **k: None
        g = Game(id="88", str_mode="Multiworld", str_shared=list(shared))
        g.get_players = lambda: list(players.values())
        g.player = lambda pid, create=True, delay_put=False: players[pid]
        g.hist, g.grants = [], []
        by_key = {p.key: p for p in players.values()}
        Player.mark_slot_txn = staticmethod(lambda pkey, slot: by_key[pkey].mark_slot(slot))
        Player.mark_slots_txn = staticmethod(
            lambda pkey, slots: sum(1 for s in slots if by_key[pkey].mark_slot(s)))
        Player.signal_send_txn = staticmethod(
            lambda pkey, signal: by_key[pkey].signals.append(signal) or True)
        Player.append_hl_chunked_txn = staticmethod(lambda pkey, hl: g.hist.append(hl) or True)
        Player.transaction_pickup_batch = staticmethod(
            lambda pkeys, grants: g.grants.append(grants))
        return g, players[1], players[2]


class _ModelsMwParams(object):
    """params, as the release readers use it: get_seed_data and nothing else."""

    def __init__(self, rows):
        self.rows = rows

    def get_seed_data(self, pid):
        return self.rows


class MwReleaseFieldTests(_ModelsMwCase):
    """models.py:2133-2145. mw_release reads field 3 as owner,slot and throws
    the rest away; it is the loc, not the comma field, that tells a manifest
    line from a finder line."""

    def test_owner_and_slot_are_the_first_two_of_three_comma_parts(self):
        g, _, owner = self.game()
        released = g.mw_release(1, params=_ModelsMwParams(
            [("919772", "MW", "2,17,Bash", "Glades")]))
        self.assertEqual(released, 1)
        self.assertTrue(owner.slot_check(17))

    def test_the_tail_may_contain_commas_and_is_discarded(self):
        """One maxsplit: an item name with a comma in it must not steal the
        slot field, and nothing downstream looks at the name."""
        g, _, owner = self.game()
        released = g.mw_release(1, params=_ModelsMwParams(
            [("39756", "MW", "2,17,Bombs, Bow", "Glades")]))
        self.assertEqual(released, 1)
        self.assertTrue(owner.slot_check(17))

    def test_a_manifest_loc_is_skipped_before_its_comma_field_is_read(self):
        """A manifest's field 3 is finder,code,id -- shaped exactly like a
        finder's owner,slot,name. Only the negative loc separates them."""
        g, _, owner = self.game()
        released = g.mw_release(1, params=_ModelsMwParams(
            [("-19", "MW", "2,17,Bash", "Glades")]))
        self.assertEqual(released, 0)
        self.assertFalse(owner.slot_check(17))

    def test_a_comma_field_of_the_wrong_arity_is_skipped_not_fatal(self):
        g, _, owner = self.game()
        rows = [("919772", "MW", "2,17", "Glades"),
                ("39756", "MW", "2,18,Bash", "Glades")]
        self.assertEqual(g.mw_release(1, params=_ModelsMwParams(rows)), 1)
        self.assertFalse(owner.slot_check(17))
        self.assertTrue(owner.slot_check(18))

    def test_the_finder_releases_nothing_from_their_own_world(self):
        g, finder, _ = self.game()
        self.assertEqual(g.mw_release(1, params=_ModelsMwParams(
            [("919772", "MW", "1,17,Bash", "Glades")])), 0)
        self.assertFalse(finder.slot_check(17))


class MwShareableTests(_ModelsMwCase):
    """models.py:2075-2082. The release's shared pass reads field 2, never the
    comma field: a cross-world line is somebody else's slot, not a share."""

    def test_a_cross_world_line_never_fans_out_whatever_its_tail_says(self):
        g, _, _ = self.game(shared=["Skills"])
        mw = Pickup.n("MW", "2,17,Bash")
        self.assertIsNotNone(mw)  # a line the reader rejected would pass vacuously
        self.assertEqual(g.mw_shareable(mw), [])
        self.assertEqual(g.mw_shareable(Pickup.n("SK", "0")), [Pickup.n("SK", "0")])

    def test_warps_and_the_finale_event_never_fan_out(self):
        g, _, _ = self.game(shared=["Skills", "Teleporters", "Misc", "WorldEvents"])
        self.assertEqual(g.mw_shareable(Pickup.n("TW", "Warp to Grove,1,2,Grove")), [])
        self.assertEqual(g.mw_shareable(Pickup.n("EV", "5")), [])
        self.assertEqual(g.mw_shareable(Pickup.n("EV", "0")), [Pickup.n("EV", "0")])

    def test_an_unreadable_line_is_dropped_silently(self):
        g, _, _ = self.game(shared=["Skills"])
        self.assertEqual(g.mw_shareable(Pickup.n("MW", "nonsense")), [])


class MwFoundPickupTests(_ModelsMwCase):
    """models.py:2256-2267 and 2331-2342. A found MW pickup flips the owner's
    slot and records the whole comma field on the history line, which the
    game's history page renders through MultiworldItem's name."""

    def test_the_slot_flip_reads_the_same_two_fields_as_the_release(self):
        g, _, owner = self.game()
        field = "2,17,Bash"
        g.found_pickup(1, Pickup.n("MW", field), 919772, False, False, "Glades")
        self.assertTrue(owner.slot_check(17))
        g2, _, owner2 = self.game()
        g2.mw_release(1, params=_ModelsMwParams([("39756", "MW", field, "Glades")]))
        self.assertTrue(owner2.slot_check(17))

    def test_history_renders_the_tail_as_the_item_name(self):
        """The tail is a display name, so the history page reads as prose. The
        item's code lives only on the owner's manifest line."""
        g, _, _ = self.game()
        g.found_pickup(1, Pickup.n("MW", "2,17,Bash"), 919772, False, False, "Glades")
        self.assertEqual(len(g.hist), 1)
        self.assertEqual((g.hist[0].pickup_code, g.hist[0].pickup_id), ("MW", "2,17,Bash"))
        self.assertIn("found Player 2's Bash at FirstPickup", g.hist[0].print_line())

    def test_a_cross_world_find_is_exempt_from_a_shared_category(self):
        g, _, _ = self.game(shared=["Skills"])
        g.found_pickup(1, Pickup.n("SK", "0"), 919772, False, False, "Glades")
        self.assertEqual(len(g.grants), 1)  # a local skill still fans out
        g.found_pickup(1, Pickup.n("MW", "2,17,Bash"), 39756, False, False, "Glades")
        self.assertEqual(len(g.grants), 1)


class ApReservedIdReaderTests(unittest.TestCase):
    """annotate._reserved_slot, the reserved-line id reader. Its split(",", 2)
    is what lets a format-2 id through unchallenged, so pin what it accepts
    and -- the load-bearing half -- what it rejects."""

    SHADOW = "3"                       # players 2 + world 1

    def read(self, id, code="MW", shadow=None):
        return annotate_mod._reserved_slot(code, id, shadow or self.SHADOW)

    def test_it_returns_the_slot_and_the_label(self):
        self.assertEqual(self.read("3,0,AP Item #0"), (0, "AP Item #0"))

    def test_the_label_is_the_whole_tail_commas_and_all(self):
        """One maxsplit, so an AP name keeps its commas -- and so a longer
        id parses as a slot plus one long label instead of failing."""
        self.assertEqual(self.read("3,7,Bow, Arrows (Zelda)"),
                         (7, "Bow, Arrows (Zelda)"))

    def test_slot_zero_is_truthy_to_the_callers_tuple_test(self):
        # both call sites write `if held:`; slot 0 must not read as absent
        self.assertTrue(self.read("3,0,AP Item #0"))

    def test_a_native_cross_world_line_is_not_reserved(self):
        self.assertIsNone(self.read("2,0,Bash"))

    def test_another_worlds_shadow_is_not_reserved(self):
        self.assertIsNone(self.read("4,0,AP Item #0"))

    def test_a_non_mw_line_is_never_reserved(self):
        self.assertIsNone(self.read("3,0,AP Item #0", code="SK"))

    def test_a_short_id_is_rejected(self):
        self.assertIsNone(self.read("3,0"))

    def test_the_digit_test_is_what_keeps_our_own_manifest_out(self):
        """_holder_hits feeds it every line of a world, manifests included.
        A manifest id has the same arity and the same shadow; only the
        non-numeric code in field two separates the two shapes."""
        self.assertIsNone(self.read("3,SK,0"))
        self.assertIsNone(self.read("3,TW,Warp to Ginso Escape,510,910,GinsoEscape"))


class ApManifestExportReaderTests(unittest.TestCase):
    """annotate._exports, the manifest reader: slot -> the datapackage key
    that slot ships into the AP pool. Manifest lines already carry code,id,
    which is the shape format 2 gives the finder lines."""

    SHADOW = "3"

    def exports(self, *lines):
        return annotate_mod._exports(list(lines), self.SHADOW)

    def test_a_manifest_slot_maps_to_its_code_and_id(self):
        self.assertEqual(self.exports(("-2", "MW", "3,SK,0", "Grove")),
                         {0: ("SK", "0")})

    def test_the_slot_is_the_negated_pseudo_location(self):
        self.assertEqual(list(self.exports(("-14", "MW", "3,HC,1", "Grove"))), [12])

    def test_another_finders_manifest_entry_is_not_our_export(self):
        # a native cross-world delivery world 2 found for us
        self.assertEqual(self.exports(("-2", "MW", "2,HC,1", "Grove")), {})

    def test_a_reserved_line_is_not_a_manifest_line(self):
        self.assertEqual(self.exports(("919772", "MW", "3,0,AP Item #0", "Glades")), {})

    def test_a_non_mw_line_is_skipped(self):
        self.assertEqual(self.exports(("919772", "SK", "0", "Glades")), {})

    def test_a_comma_bearing_id_survives_the_single_maxsplit(self):
        """A warp id is "<name>,<x>,<y>,<node>" and the key is the
        destination alone, so the id has to reach match_key whole."""
        from archipelago.convert import match_key
        id = "TW,Warp to Ginso Escape,510,910,GinsoEscape"
        out = self.exports(("-3", "MW", "3," + id, "Grove"))
        self.assertEqual(out, {1: ("TW", "Warp to Ginso Escape")})
        self.assertEqual(out[1], match_key(*id.split(",", 1)))

    def test_an_ex_amount_buckets_to_the_shared_denomination(self):
        # the key is the amount both sides grant, not the rolled amount
        self.assertEqual(self.exports(("-2", "MW", "3,EX,1337", "Grove")),
                         {0: ("EX", "200")})


class ApReservedIdFormatTwoTests(unittest.TestCase):
    """What a format-2 reserved line does to these readers untouched.
    _exports is unaffected -- the manifest shape does not move. _reserved_slot
    parses it, gets the right slot, and annotate writes format 1 back over."""

    LINE = ("919772", "MW", "3,0,P2,-1,SK,0", "Glades")

    def test_a_format_two_id_parses_here_without_error(self):
        self.assertEqual(annotate_mod._reserved_slot("MW", self.LINE[2], "3"),
                         (0, "P2,-1,SK,0"))

    def test_annotate_writes_format_one_back_over_it(self):
        line = annotate([self.LINE], 2, 1, {1: ({0: _FakeScout()}, 7)},
                        lambda v: [], promises={0: 12})[0]
        self.assertEqual(line[2], "3,0,Bash (P2)")   # code, id and ownslot gone
        self.assertEqual(len(line), 6)               # fields 5 and 6 back on


class ApConversionReadTests(unittest.TestCase):
    """What the AP conversion pass reads off a cross-world line. ap_convert is
    a pure function over seed text, so these drive it with synthetic worlds
    instead of rolling a seed."""

    FLAGS = "Sync0.0,test|mode=Multiworld"

    def _convert(self, worlds, categories=("skills",)):
        from archipelago.convert import ap_convert
        texts = [self.FLAGS + "\n" + "".join(l + "\n" for l in w) for w in worlds]
        return ap_convert(texts, list(categories))

    def _finder(self, loc, owner, slot, name, zone="Grove"):
        return "%s|MW|%s,%s,%s|%s" % (loc, owner, slot, name, zone)

    def _manifest(self, slot, finder, code, id, zone="Swamp"):
        return "%s|MW|%s,%s,%s|%s" % (-(slot + 2), finder, code, id, zone)

    def test_the_finder_supplies_only_owner_and_slot(self):
        """Field 3 splits (",", 2) and the third piece is thrown away: what
        gets exported comes from the owner's manifest, never from the name on
        the finder line."""
        runs = [self._convert([[self._finder(1000000, 2, 0, name)],
                               [self._manifest(0, 1, "SK", "0")]])
                for name in ("Bash", "wholly unrelated text")]
        self.assertEqual(runs[0], runs[1])
        self.assertEqual(runs[0][1]["exported"][2], [("SK", "0", 0)])

    def test_a_format_two_finder_reads_as_a_format_one_finder(self):
        """The silent half of the rework. Format 2 puts code,id where the name
        is; split(",", 2) folds both into the discarded piece, so this site
        converts a format-2 seed byte-identically and never notices."""
        one = self._convert([[self._finder(1000000, 2, 0, "Bash")],
                             [self._manifest(0, 1, "SK", "0")]])
        two = self._convert([[self._finder(1000000, 2, 0, "SK,0")],
                             [self._manifest(0, 1, "SK", "0")]])
        self.assertEqual(one, two)

    def test_the_manifest_index_is_keyed_by_negated_loc(self):
        """Slot n lives at loc -(n+2) and only an MW line there registers, so a
        non-MW line at a manifest loc leaves the slot empty."""
        _, info = self._convert([[self._finder(1000000, 2, 7, "Bash")],
                                 [self._manifest(7, 1, "SK", "0")]])
        self.assertEqual(info["exported"][2], [("SK", "0", 0)])
        from archipelago.convert import ApConversionError
        with self.assertRaises(ApConversionError) as caught:
            self._convert([[self._finder(1000000, 2, 7, "Bash")],
                           ["-9|SK|0|Swamp"]])
        self.assertIn("missing manifest slot 7", str(caught.exception))

    def test_a_finder_pointing_past_the_manifest_fails_loudly(self):
        """The one thing this site does check, and the check the item code on a
        format-2 line would make redundant."""
        from archipelago.convert import ApConversionError
        with self.assertRaises(ApConversionError) as caught:
            self._convert([[self._finder(1000000, 2, 7, "Bash")],
                           [self._manifest(0, 1, "SK", "0")]])
        message = str(caught.exception)
        self.assertIn("missing manifest slot 7", message)
        self.assertIn("of world 2", message)

    def test_an_ex_export_rounds_away_from_the_placed_amount(self):
        """The id that exports is not always the id on the manifest: above the
        exact cap EX rounds so the amount AP announces is the amount the client
        grants. A finder line carrying the true amount would disagree."""
        texts, info = self._convert([[self._finder(1000000, 2, 0, "1337 Experience")],
                                     [self._manifest(0, 1, "EX", "1337")]],
                                    categories=("upgrades",))
        self.assertEqual(info["exported"][2], [("EX", "200", 0)])
        self.assertIn("|MW|4,EX,200|", texts[1])

    def test_a_fifth_field_hides_a_line_from_conversion_entirely(self):
        """Annotated AP lines are excluded by field count, not by content --
        the reason a converted seed can pass through here untouched. Format 2
        gives every line four fields and the exclusion with it."""
        annotated = "1000000|MW|3,0,Bash (P2)|Grove|P2;Bash"
        texts, info = self._convert([[annotated], []])
        self.assertIn(annotated, texts[0].split("\n"))
        self.assertEqual(info["reserved"][1], [])
        from archipelago.convert import ApConversionError
        with self.assertRaises(ApConversionError) as caught:
            self._convert([[annotated.rsplit("|", 1)[0]], []])
        self.assertIn("already carries shadow-owned line", str(caught.exception))


class ApConversionWriteTests(unittest.TestCase):
    """What the pass writes back over a converted location. The rewrite is a
    format-1 finder line whichever format its input arrived in."""

    FLAGS = "Sync0.0,test|mode=Multiworld"

    def _convert(self, worlds, categories=("skills",)):
        from archipelago.convert import ap_convert
        texts = [self.FLAGS + "\n" + "".join(l + "\n" for l in w) for w in worlds]
        return ap_convert(texts, list(categories))

    def test_the_reserved_line_is_shadow_slot_label(self):
        texts, _ = self._convert([["1000000|SK|0|Glades"]])
        line = [l for l in texts[0].split("\n") if l.startswith("1000000|")][0]
        self.assertEqual(fields(line), ["1000000", "MW", "2,0,AP Item #1", "Glades"])
        shadow, slot, label = fields(line)[2].split(",", 2)
        self.assertEqual((shadow, slot, label), ("2", "0", "AP Item #1"))
        self.assertNotIn(",", label)   # the item code the label stands in for

    def test_an_exported_manifest_line_is_shadow_code_id(self):
        texts, _ = self._convert([["1000000|SK|0|Glades"]])
        line = [l for l in texts[0].split("\n") if l.startswith("-2|")][0]
        self.assertEqual(fields(line), ["-2", "MW", "2,SK,0", "Glades"])

    def test_unconverted_cross_lines_pass_through_byte_identical(self):
        """Filler the datapackage cannot name keeps the native fabric, so one
        converted seed carries lines this pass wrote next to lines it only
        copied."""
        native = "1000000|MW|2,0,Relic|Grove"
        texts, _ = self._convert([[native, "1000001|SK|0|Glades"],
                                  ["-2|MW|1,WT,#Abandoned Nest#|Swamp"]])
        lines = texts[0].split("\n")
        self.assertIn(native, lines)
        self.assertIn("1000001|MW|3,0,AP Item #1|Glades", lines)



class _BridgeParams(object):
    """params as maps_from_params reads it: placement tuples, per world."""

    def __init__(self, players, seed):
        self.players, self.ap_mode, self._seed = players, True, seed

    def get_seed_data(self, player=1):
        return self._seed[int(player)]


class ApBridgeMapReaderTests(unittest.TestCase):
    """archipelago/ap_bridge.py maps_from_params -- the bridge's only reader of
    a seed. It takes the shadow id and the slot off a reserved line BY POSITION
    and never reads the tail, so these pin which positions those are.

    Coords are real datapackage locations; K=2 makes world 1's shadow player 3."""

    K = 2
    MANIFEST = [("-2", "MW", "3,SK,0", "Glades"),      # export slot 0
                ("-4", "MW", "3,EV,0", "Swamp")]       # export slot 2, a buyable reveal
    NATIVE = [("5043022", "MW", "2,7,Bash", "Grove")]  # cross-world, owner is a real player

    def maps(self, world_one):
        params = _BridgeParams(self.K, {1: list(world_one), 2: []})
        return ap_bridge.maps_from_params(params)

    def test_the_reserved_id_is_shadow_then_slot_then_free_text(self):
        """Field 3 of a reserved line is <K+w>,<slot>,<label>, split at maxsplit
        2 so the label may hold commas. The label itself reaches nothing."""
        maps = self.maps([("919908", "MW", "3,0,Bombs, Bow (P2)", "Grove"),
                          ("959960", "MW", "3,1,AP Item #2", "Valley")])
        self.assertEqual(maps.outbox[1], {0: 524541, 1: 524542})
        self.assertEqual(maps.zones[1], {0: "Grove", 1: "Valley"})
        self.assertEqual(maps.grant_slots[1], {})

    def test_only_the_first_two_comma_fields_are_load_bearing(self):
        """Fixed-arity fields lead and the free text is last, so widening the
        tail is invisible here -- this reader survives format 2 untouched."""
        f1 = self.maps([("919908", "MW", "3,0,AP Item #1", "Grove")] + self.MANIFEST)
        f2 = self.maps([("919908", "MW", "3,0,P2,-1,AP,AP Item #1", "Grove")] + self.MANIFEST)
        self.assertEqual((f1.outbox, f1.zones), (f2.outbox, f2.zones))
        self.assertEqual(f1.grant_slots, f2.grant_slots)
        self.assertEqual(f1.hint_keys, f2.hint_keys)

    def test_a_native_cross_world_finder_is_never_a_reserved_slot(self):
        """Reserved lines are the ones a shadow owns; an owner at or below K is
        an ordinary multiworld item and belongs to no outbox."""
        for tail in ("Bash", "SK,0"):                  # format 1, then format 2
            maps = self.maps([("5043022", "MW", "2,7,%s" % tail, "Grove")])
            self.assertEqual(maps.outbox[1], {}, tail)
            self.assertEqual(maps.zones[1], {}, tail)

    def test_manifest_and_reserved_lines_split_by_different_rules(self):
        """One loop, one maxsplit, two meanings: the manifest already carries
        code,id -- the shape format 2 gives the reserved line as well."""
        maps = self.maps(self.MANIFEST + self.NATIVE +
                         [("919908", "MW", "3,0,AP Item #1", "Grove")])
        self.assertEqual(maps.grant_slots[1], {("SK", "0"): [0], ("EV", "0"): [2]})
        self.assertEqual(maps.hint_keys[1], {2: ("EV", "0")})
        self.assertEqual(maps.outbox[1], {0: 524541})

    def test_the_bridge_reads_placements_annotate_has_not_touched(self):
        """Fields 5 and 6 never reach here: get_seed_data is raw, and the
        4-tuple unpack refuses an annotated line outright."""
        reserved = ("919772", "MW", "3,0,AP Item #1", "Glades")
        lines = annotate([reserved], self.K, 1, {1: ({0: _FakeScout()}, 7)},
                         lambda v: [], promises={0: 12})
        self.assertEqual(len(lines[0]), 6)
        with self.assertRaises(ValueError):
            self.maps(lines)

    def test_a_field_three_that_stops_leading_with_the_shadow_id_goes_quiet(self):
        """The silent failure: move the shadow id off the front and the outbox
        empties without raising, so the bridge polls nothing and the room never
        sees a check."""
        maps = self.maps([("919908", "MW", "0,3,P2,-1,AP,AP Item #1", "Grove")])
        self.assertEqual(maps.outbox[1], {})


class FormatTwoWorklistTests(unittest.TestCase):
    """Several tests here pin today's WRONG answer for a format-2 shaped input.
    That makes them a worklist rather than an alarm -- a reader left behind at
    format 2 still passes its own test. This is the tripwire that says when to
    work through the list."""

    def test_seed_format_is_still_one(self):
        self.assertEqual(SEED_FORMAT, 1,
                         "SEED_FORMAT moved: revisit every test here that names what format 2 must do")



if __name__ == "__main__":
    unittest.main()
