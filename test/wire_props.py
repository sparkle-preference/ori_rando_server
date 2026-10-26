"""Wire formats, params and parsers: what the server writes reads back the way its readers read it."""
from test.strategies.base import examples

import copy
import logging
import re
import unittest
from unittest import mock

from hypothesis import event, given, settings, strategies as st
from werkzeug.datastructures import MultiDict

from ap_models import sanitize_display_name, wire_safe_name
from enums import KeyMode, LogicPath, MultiplayerGameType, PathDifficulty, ShareType, Variation, presets
from pickups import Multiple, MultiworldItem, Pickup, Upgrade
from seedbuilder import seedparams
from seedbuilder.oriparse import ori_load
from seedbuilder.seedparams import MultiplayerOptions, Placement, SeedGenParams, Stuff, WORLD_FIELDS, world_view
from test.js_bridge import call
from test.ndb_base import NdbTestCase
from test.strategies.wire import (any_text, at_text, code, fass_rows, line_text, logic_line, owner_tagged, page_json,
                                  pieces, raw_multi, real_pickup, release, render_fass, slashy_text, versions,
                                  world_blob)
from util import (add_single, all_locs, bfields_to_coords, compose_multi_value, coords_in_order, decompose_multi_value,
                  display_version, get, get_bit, get_preset_from_paths, get_taste, inc_stackable, is_mw_manifest_loc,
                  log_2, normalize_multi_value, parse_fass, split_owner, unpack, version_at_least)


class Quiet(unittest.TestCase):
    """The code under test logs each malformed input it meets."""

    def setUp(self):
        super().setUp()
        self.addCleanup(logging.disable, logging.root.manager.disable)
        logging.disable(logging.CRITICAL)


class QuietNdb(Quiet, NdbTestCase):
    pass


def lead_safe(id):
    return " " + id if id.startswith("/") else id


def build(j):
    """from_json, unsaved, as a rolled seed: to_json reads spoilers[0]."""
    p = SeedGenParams.from_json(copy.deepcopy(j), store=False)
    if p is None:
        raise AssertionError("from_json refused %r" % (j,))
    p.spoilers = [""]
    return p


def worlds(p):
    return range(1, (p.players or 1) + 1)


def digits_int_refuses(s):
    """isdigit() takes superscripts and the like, which int() refuses."""
    return s.isdigit() and not s.isdecimal()


def owner_tag_int_refuses(text):
    head, at, tail = text.rpartition("@")
    return bool(at) and digits_int_refuses(tail)


bitfield = st.integers(0, 2**20)
single_bit = st.sampled_from(sorted(log_2))
STACK_BITS = sorted(Upgrade.bits[i] for i in Upgrade.stacking)


class BitfieldProps(Quiet):

    @settings(max_examples=examples(500))
    @given(bitfield, single_bit)
    def test_get_bit_is_a_shift(self, b, bit):
        self.assertEqual(get_bit(b, bit), (b >> log_2[bit]) & 1)

    @settings(max_examples=examples(500))
    @given(bitfield, single_bit)
    def test_get_taste_is_a_two_bit_shift(self, b, bit):
        self.assertEqual(get_taste(b, bit), (b >> log_2[bit]) & 3)

    @settings(max_examples=examples(500))
    @given(bitfield, single_bit)
    def test_add_single_sets_or_clears_only_its_bit(self, b, bit):
        self.assertEqual(add_single(b, bit), b | bit)
        self.assertEqual(add_single(b, bit, remove=True), b & ~bit)
        self.assertEqual(add_single(b, -1), b)

    @settings(max_examples=examples(500))
    @given(bitfield, st.sampled_from(STACK_BITS), st.booleans())
    def test_inc_stackable_moves_its_counter_by_one_within_0_to_3(self, b, bit, remove):
        at = log_2[bit]
        n = (b >> at) & 3
        out = inc_stackable(b, bit, remove)
        self.assertEqual((out >> at) & 3, max(n - 1, 0) if remove else min(n + 1, 3))
        self.assertEqual(out & ~(3 << at), b & ~(3 << at))

    @settings(max_examples=examples(500))
    @given(st.sets(st.sampled_from(coords_in_order)))
    def test_bfields_name_the_coords_whose_bits_are_set(self, coords):
        lanes = [0] * 8
        for i, c in enumerate(coords_in_order):
            if c in coords:
                lanes[i // 32] |= 1 << (i % 32)
        self.assertEqual(bfields_to_coords(lanes), [c for c in coords_in_order if c in coords])

    def test_unpack_inverts_get_on_every_known_loc(self):
        self.assertEqual([c for c in all_locs if get(*unpack(c)) != c], [])

    @settings(max_examples=examples(500))
    @given(st.integers(-1000, 1000).map(lambda x: 4 * x), st.integers(-2000, 2000))
    def test_unpack_inverts_get(self, x, y):
        self.assertEqual(unpack(get(x, y)), (x, y))


class VersionProps(Quiet):

    @settings(max_examples=examples(500))
    @given(st.one_of(st.none(), any_text, versions.map(lambda v: ".".join(map(str, v)))), versions)
    def test_version_at_least_is_total(self, v, floor):
        self.assertIn(version_at_least(v, floor[:3]), (True, False))

    @settings(max_examples=examples(500))
    @given(versions, st.lists(st.integers(0, 30), min_size=3, max_size=3))
    def test_version_at_least_is_the_padded_tuple_order(self, v, floor):
        self.assertEqual(version_at_least(".".join(map(str, v)), floor), (v + [0, 0, 0])[:3] >= floor)

    @settings(max_examples=examples(500))
    @given(versions, versions, st.lists(st.integers(0, 30), min_size=3, max_size=3))
    def test_version_at_least_is_monotone(self, a, b, floor):
        lo, hi = sorted([a, b], key=lambda v: (v + [0] * 5)[:5])
        if version_at_least(".".join(map(str, lo)), floor):
            self.assertTrue(version_at_least(".".join(map(str, hi)), floor))

    @settings(max_examples=examples(500))
    @given(st.one_of(release, st.text(st.sampled_from("4.9123x"), max_size=10), any_text))
    def test_display_version_matches_patchnotes_js(self, v):
        self.assertEqual(display_version(v), call("PatchNotes.js", "displayVersion", v))

    @settings(max_examples=examples(500))
    @given(st.sets(st.sampled_from(list(LogicPath)), min_size=1))
    def test_helpbox_decodes_the_custom_mask_util_writes(self, paths):
        name = get_preset_from_paths(presets, paths)
        if not name.startswith("Custom"):
            self.assertEqual(presets[name], paths)
            return
        bits = call("helpbox.js", "PATH_BITS")
        mask = int(name[len("Custom"):])
        self.assertEqual(mask >> len(bits), 0)
        self.assertEqual({bits[i] for i in range(len(bits)) if mask >> i & 1}, {p.value for p in paths})


def an_empty_id_before_the_last(ps):
    return any(i == "" for _, i in ps[:-1])


def a_pipe_in_an_id(c, i):
    return "|" in i


def js_pack(ps):
    return "/".join(call("multipickup.js", "pack_piece", "%s|%s" % p) for p in ps)


class MultipickupProps(Quiet):

    @settings(max_examples=examples(500))
    @given(pieces)
    def test_decompose_inverts_compose(self, ps):
        if an_empty_id_before_the_last(ps):
            event("masked: an empty id before the last")
            return
        self.assertEqual(decompose_multi_value(compose_multi_value(ps)), [(c, lead_safe(i)) for c, i in ps])

    @unittest.expectedFailure
    def test_decompose_inverts_compose_with_an_empty_id_before_the_last(self):
        ps = [("SK", ""), ("SK", "0")]
        self.assertEqual(decompose_multi_value(compose_multi_value(ps)), ps)

    @settings(max_examples=examples(500))
    @given(raw_multi)
    def test_normalize_is_idempotent(self, v):
        once = normalize_multi_value(v)
        self.assertEqual(normalize_multi_value(once), once)

    @settings(max_examples=examples(500))
    @given(raw_multi)
    def test_normalize_keeps_the_pieces(self, v):
        parts = decompose_multi_value(v)
        # compose writes codes as they are: one holding a slash is outside its domain
        if any("/" in c for c, _ in parts):
            return
        self.assertEqual(decompose_multi_value(normalize_multi_value(v)), [(c, lead_safe(i)) for c, i in parts])

    @settings(max_examples=examples(500))
    @given(raw_multi)
    def test_js_decompose_agrees_but_for_a_bare_message(self, v):
        py = decompose_multi_value(v)
        bare_message = normalize_multi_value(v) != v
        js = [tuple(p) for p in call("multipickup.js", "decompose_pickup", "MU", v)]
        self.assertEqual(js, py[:-1] if bare_message else py)

    @settings(max_examples=examples(500))
    @given(code, st.one_of(slashy_text, line_text))
    def test_js_packs_a_piece_like_compose(self, c, i):
        if a_pipe_in_an_id(c, i):
            event("masked: a pipe in an id")
            return
        want = compose_multi_value([(c, i)])
        self.assertEqual(call("multipickup.js", "pack_piece", "%s|%s" % (c, i)), want)
        self.assertEqual(call("MainPage.js", "partToSegs", "%s|%s" % (c, i)), want)

    @unittest.expectedFailure
    def test_js_packs_a_piece_like_compose_with_a_pipe_in_its_id(self):
        self.assertEqual(call("multipickup.js", "pack_piece", "SH|a|b"), compose_multi_value([("SH", "a|b")]))

    @settings(max_examples=examples(300))
    @given(pieces)
    def test_js_reads_what_python_composes(self, ps):
        if an_empty_id_before_the_last(ps):
            event("masked: an empty id before the last")
            return
        js = [tuple(p) for p in call("multipickup.js", "decompose_pickup", "MU", compose_multi_value(ps))]
        self.assertEqual(js, [(c, lead_safe(i)) for c, i in ps])

    @unittest.expectedFailure
    def test_js_reads_what_js_packs_with_an_empty_id_before_the_last(self):
        ps = [("SK", ""), ("SK", "0")]
        self.assertEqual([tuple(p) for p in call("multipickup.js", "decompose_pickup", "MU", js_pack(ps))], ps)

    @settings(max_examples=examples(300))
    @given(st.lists(real_pickup, min_size=1, max_size=5))
    def test_with_pickups_keeps_every_child(self, ps):
        children = [Pickup.n(c, i) for c, i in ps]
        parts = [(ch.code, str(ch.id)) for ch in children]
        if an_empty_id_before_the_last(parts):
            event("masked: an empty id before the last")
            return
        mu = Multiple.with_pickups(children)
        self.assertEqual([(ch.code, str(ch.id)) for ch in mu.children], [(c, lead_safe(i)) for c, i in parts])


ARABIC_INDIC = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")
plain_piece = real_pickup.filter(lambda p: p[1] and "@" not in p[1] and not p[1].startswith("/"))


def tagged(o, how):
    """World o as an owner tag, one in twenty written zero-padded or in Arabic-Indic digits."""
    return {38: "0%d" % o, 39: str(o).translate(ARABIC_INDIC)}.get(how, str(o))


@st.composite
def mw_placements(draw):
    """(worlds, rows of (loc, holder, [(code, id, owner tag or None)])); several pieces make a multipickup."""
    n = draw(st.integers(2, 6))
    piece = st.tuples(plain_piece, st.one_of(st.none(), st.builds(tagged, st.integers(1, n), st.integers(0, 39))))
    rows = draw(st.lists(st.tuples(st.sampled_from(coords_in_order), st.integers(1, n),
                                   st.lists(piece, min_size=1, max_size=3)),
                         unique_by=lambda r: r[:2], max_size=10))
    return n, [(loc, h, [(c, i, tag) for (c, i), tag in ps]) for loc, h, ps in rows]


def mw_params(n, placements):
    params = SeedGenParams(seed="x", players=n, placements=placements)
    params.sync = MultiplayerOptions(enabled=True, str_mode=MultiplayerGameType.MULTIWORLD.value)
    return params


def placement(loc, holder, ps):
    if len(ps) == 1:
        c, i, tag = ps[0]
        stuff = Stuff(code=c, id=i, player=str(holder), owner=str(int(tag)) if tag else None)
    else:
        stuff = Stuff(code="MU", id=compose_multi_value([(c, i + "@" + tag if tag else i) for c, i, tag in ps]),
                      player=str(holder))
    return Placement(location=str(loc), zone="Glades", stuff=[stuff])


def an_owner_tag_str_would_not_write(rows):
    return any(tag and tag != str(int(tag)) for _, _, ps in rows if len(ps) > 1 for _, _, tag in ps)


class MultiworldReaderProps(QuietNdb):

    @settings(max_examples=examples(200))
    @given(mw_placements())
    def test_every_world_reads_back_what_it_holds_and_what_it_is_owed(self, case):
        n, rows = case
        if an_owner_tag_str_would_not_write(rows):
            event("masked: an owner tag str() would not write")
            return
        params = mw_params(n, [placement(*r) for r in rows])
        held, found, owed = [], {}, {}
        for w in range(1, n + 1):
            for loc, c, i, _ in params.get_seed_data(w):
                if is_mw_manifest_loc(loc):
                    finder, holder, icode, iid = i.split(",", 3)
                    owed[(w, -int(loc) - 2)] = (int(finder), holder, icode, iid)
                    continue
                for pc, pi in decompose_multi_value(i) if c == "MU" else [(c, i)]:
                    if pc != "MW":
                        held.append((int(loc), w, pc, pi))
                        continue
                    item = MultiworldItem(pi, n)
                    self.assertFalse(item.reserved)
                    self.assertEqual(item.name,
                                     "Player %d's %s" % (item.owner, Pickup.name(item.item_code, item.item_id)))
                    self.assertNotIn((item.owner, item.slot), found)
                    found[(item.owner, item.slot)] = (int(loc), w, item.item_code, item.item_id)
        self.assertEqual(sorted(held), sorted((loc, h, c, i) for loc, h, ps in rows for c, i, tag in ps
                                              if not tag or int(tag) == h))
        self.assertEqual(sorted((loc, w, o, c, i) for (o, _), (loc, w, c, i) in found.items()),
                         sorted((loc, h, int(tag), c, i) for loc, h, ps in rows for c, i, tag in ps
                                if tag and int(tag) != h))
        self.assertEqual(owed, {key: (w, "", c, i) for key, (_, w, c, i) in found.items()})

    @unittest.expectedFailure
    def test_every_world_reads_back_what_it_is_owed_with_an_owner_tag_written_as_01(self):
        params = mw_params(2, [placement(919772, 2, [("SK", "0", "1")]),
                               placement(-3160308, 2, [("EX", "5", "01"), ("EX", "7", None)])])
        slots = [loc for loc, _, _, _ in params.get_seed_data(1) if is_mw_manifest_loc(loc)]
        self.assertEqual(len(slots), len(set(slots)))

    @settings(max_examples=examples(200))
    @given(st.integers(1, 16), st.data())
    def test_the_reader_recovers_a_reserved_line(self, players, data):
        shadow = players + data.draw(st.integers(1, players))
        slot = data.draw(st.integers(0, 255))
        to = data.draw(st.one_of(st.integers(1, players).map("P{}".format), any_text.map(wire_safe_name)))
        own_slot = data.draw(st.integers(-1, 255))
        c, i = data.draw(st.one_of(real_pickup, st.tuples(st.just("AP"), any_text.map(sanitize_display_name))))
        item = MultiworldItem("%s,%s,%s,%s,%s,%s" % (shadow, slot, to, own_slot, c, i), players)
        self.assertTrue(item.reserved)
        self.assertEqual((item.owner, item.slot, item.item_code, item.item_id), (shadow, slot, c, i))
        self.assertEqual(item.name, "Player %d's %s" % (shadow, i if c == "AP" else Pickup.name(c, i)))


def a_hint_short_of_dashes(code, id):
    """An MW id names its item after the owner and slot."""
    if code == "MW":
        parts = id.split(",", 2)
        code, _, id = (parts[2] if len(parts) == 3 else "").partition(",")
    return code == "HN" and id.count("-") < 2


def neither_text_nor_none(value):
    return value is not None and not isinstance(value, str)


owner_text = st.one_of(any_text, at_text, owner_tagged)
world_count = st.integers(1, 6)
wild_id = st.one_of(st.text(st.sampled_from("0123-,x /abHN²"), max_size=8), line_text, st.integers(-5, 600).map(str))
mw_field = st.text(st.sampled_from("0123456789-+ x²١"), max_size=4)
mw_id = st.builds("{},{},{},{}".format, mw_field, mw_field, code, wild_id)
ENUMS = [LogicPath, Variation, KeyMode, PathDifficulty, ShareType, MultiplayerGameType]


@st.composite
def enum_and_value(draw):
    """An enum and a JSON value for its mk: half text, a quarter its members' spellings, then None and the rest."""
    enum = draw(st.sampled_from(ENUMS))
    kind = draw(st.integers(0, 7))
    if kind < 4:
        return enum, draw(any_text)
    if kind < 6:
        value = draw(st.sampled_from([m.value for m in enum]))
        return enum, draw(st.sampled_from([value, value.lower(), value.upper(), value.swapcase()]))
    if kind == 6:
        return enum, None
    return enum, draw(st.one_of(st.booleans(), st.integers(), st.floats(allow_nan=False),
                                st.lists(st.integers(), max_size=2)))


def ori_paths(lines):
    text = ["home: Home", "conn: Away"] + [" ".join(t) for t in lines]
    return [p[1:] for p in ori_load(text)["homes"]["Home"]["conns"]["Away"]["paths"]]


def own_requirements(tokens):
    """A path's plain requirements in order, then its Ability= and Health= counts."""
    counts = dict(t.split("=") for t in tokens[1:] if t.startswith(("Health=", "Ability=")))
    plain = [t for t in tokens[1:] if t.partition("=")[0] not in ("Health", "Ability")]
    return tuple(plain + ["%s=%s" % (k, counts[k]) for k in ("Ability", "Health") if k in counts])


def a_bare_count(lines):
    return any(t in ("Health", "Ability") for line in lines for t in line)


class ParserTotalityProps(Quiet):

    @settings(max_examples=examples(500))
    @given(owner_text, world_count)
    def test_split_owner_splits_off_only_a_world_and_loses_nothing(self, text, n):
        if owner_tag_int_refuses(text):
            event("masked: an owner tag int() refuses")
            return
        head, owner = split_owner(text, n)
        if owner:
            self.assertEqual(head + "@" + owner, text)
            self.assertTrue(owner.isdecimal() and 1 <= int(owner) <= n)
        else:
            self.assertEqual(head, text)

    @unittest.expectedFailure
    def test_split_owner_reads_an_owner_tag_int_refuses_as_text(self):
        self.assertEqual(split_owner("SK0@²", 1), ("SK0@²", ""))

    @settings(max_examples=examples(500))
    @given(owner_text, world_count, st.integers(0, 4))
    def test_more_worlds_never_unclaim_an_owner(self, text, n, extra):
        if owner_tag_int_refuses(text):
            event("masked: an owner tag int() refuses")
            return
        if split_owner(text, n)[1]:
            self.assertEqual(split_owner(text, n + extra), split_owner(text, n))

    @settings(max_examples=examples(300))
    @given(fass_rows())
    def test_parse_fass_reads_back_rendered_rows(self, case):
        n, rows = case
        if any(owner_tag_int_refuses(i) for _, _, i, o in rows if o is None):
            event("masked: an owner tag int() refuses")
            return
        want = {(w or 1, l): "%s|%s" % (i, o) if o is not None else i for w, l, i, o in rows}
        self.assertEqual(parse_fass(render_fass(rows), n), want)

    @settings(max_examples=examples(500))
    @given(st.one_of(st.tuples(st.one_of(code, st.sampled_from(["XX", "", "sk"])), wild_id),
                     st.tuples(st.just("MW"), mw_id)))
    def test_n_fails_only_as_found_pickup_catches(self, case):
        c, i = case
        if a_hint_short_of_dashes(c, i):
            event("masked: a hint short of dashes")
            return
        try:
            Pickup.n(c, i)
        except (TypeError, ValueError):
            pass

    @unittest.expectedFailure
    def test_n_fails_only_as_found_pickup_catches_with_a_hint_short_of_dashes(self):
        try:
            Pickup.n("HN", "x")
        except (TypeError, ValueError):
            pass

    @settings(max_examples=examples(500))
    @given(mw_field, mw_field, real_pickup, st.one_of(st.none(), st.integers(1, 4)))
    def test_the_mw_reader_takes_numbers_and_reads_anything_else_as_none(self, owner, slot, pickup, players):
        if digits_int_refuses(owner) or digits_int_refuses(slot):
            event("masked: an owner or slot int() refuses")
            return
        item = MultiworldItem("%s,%s,%s,%s" % ((owner, slot) + pickup), players)
        if owner.isdecimal() and slot.isdecimal():
            self.assertEqual((item.owner, item.slot), (int(owner), int(slot)))
        else:
            self.assertIsNone(item)

    @unittest.expectedFailure
    def test_the_mw_reader_reads_an_owner_int_refuses_as_none(self):
        self.assertIsNone(MultiworldItem("²,0,SK,0"))

    @settings(max_examples=examples(500))
    @given(enum_and_value())
    def test_mk_reads_any_json_value_as_its_member_or_none(self, case):
        enum, value = case
        if neither_text_nor_none(value):
            event("masked: neither text nor None")
            return
        want = next((m for m in enum if isinstance(value, str) and m.value.lower() == value.lower()), None)
        self.assertIs(enum.mk(value), want)

    @unittest.expectedFailure
    def test_mk_reads_a_non_string_as_no_member(self):
        self.assertIsNone(LogicPath.mk(0))

    @settings(max_examples=examples(200))
    @given(st.lists(logic_line(), min_size=1, max_size=4))
    def test_a_path_reads_its_counts_from_its_own_tokens(self, lines):
        if a_bare_count(lines):
            event("masked: a bare count")
            return
        self.assertEqual(ori_paths(lines), [own_requirements(t) for t in lines])

    @unittest.expectedFailure
    def test_a_path_reads_its_counts_from_its_own_tokens_with_a_bare_health(self):
        self.assertNotIn("Health=2", ori_paths([["casual", "Energy=2", "Health"]])[0])


def an_empty_segment(raw):
    return bool(raw) and "" in raw.split("|")


def as_generated(preplaced):
    """A tag naming its holder is no tag, and a spawn item never crosses worlds."""
    out = {}
    for (world, loc), value in preplaced.items():
        item, bar, owner = value.rpartition("|")
        out[(world, loc)] = item if bar and (owner == str(world) or loc == 2) else value
    return out


def from_url_preplaced(raw, n):
    """What generate() hands the generator for ?fass=raw."""
    q = MultiDict([("seed", "x"), ("path", "casual-core"), ("players", str(n)), ("fass", raw)])
    if n > 1:
        q.add("sync_mode", "Multiworld")
    seen = {}

    class Generator(object):
        def setSeedAndPlaceItems(self, params, preplaced):
            seen.update(preplaced)

    with mock.patch.object(seedparams, "SeedGenerator", Generator), \
            mock.patch.object(SeedGenParams, "put", lambda self, **kw: self):
        SeedGenParams.from_url(q).generate(store=False)
    return seen


@st.composite
def fass_query(draw):
    """(worlds, rows, ?fass= text), one in five with an empty segment."""
    n, rows = draw(fass_rows())
    empty = [draw(st.integers(0, len(rows)))] if draw(st.integers(0, 4)) == 4 else []
    return n, rows, render_fass(rows, empty)


class FassQueryProps(QuietNdb):

    @settings(max_examples=examples(150))
    @given(fass_query())
    def test_generate_sees_what_parse_fass_reads(self, case):
        n, rows, raw = case
        if any(owner_tag_int_refuses(i) for _, _, i, o in rows if o is None):
            event("masked: an owner tag int() refuses")
            return
        if an_empty_segment(raw):
            event("masked: an empty segment")
            return
        self.assertEqual(as_generated(from_url_preplaced(raw, n)), as_generated(parse_fass(raw, n)))

    @unittest.expectedFailure
    def test_generate_sees_what_parse_fass_reads_with_an_empty_segment(self):
        self.assertEqual(from_url_preplaced("919772:SK0|", 1), parse_fass("919772:SK0|", 1))


def client_line_one(text):
    """Randomizer.cs reads line 1 as flags|name with the flags comma-split; ReadAllLines breaks on \\r and \\n."""
    head = re.split("\r\n|\r|\n", text)[0].split("|")
    return head[0].split(","), head[1] if len(head) > 1 else None


def splits_the_name(view):
    return any(c in view.seed for c in "|\r\n")


def splits_the_sense(view):
    return any(c in (view.sense or "") for c in ",|\r\n")


def splits_the_pool(view):
    return any(c in (view.pool_preset or "") for c in ",|\r\n")


UNSANITIZED = (splits_the_name, splits_the_sense, splits_the_pool)


def only_worlds_hold_fass(j):
    return not j.get("fass") and any((blob or {}).get("fass") for blob in j.get("worldSettings") or [])


def flag_lines(p):
    return [world_view(p, w).flag_line(verbose) for w in worlds(p) for verbose in (False, True)]


class FlagLineProps(QuietNdb):

    @settings(max_examples=examples(200))
    @given(page_json())
    def test_the_client_reads_line_one_back_as_written(self, j):
        p = build(j)
        for w in worlds(p):
            view = world_view(p, w)
            if any(split(view) for split in UNSANITIZED):
                event("masked: free text the client splits")
                continue
            for verbose in (False, True):
                flags, name = client_line_one(view.flag_line(verbose))
                self.assertEqual(name, view.seed)
                if view.sense:
                    self.assertIn("sense=" + view.sense.replace(" ", "+"), flags)
                if view.pool_preset != "Standard":
                    self.assertIn("pool=" + view.pool_preset, flags)

    @unittest.expectedFailure
    def test_the_client_reads_line_one_back_as_written_with_a_pipe_or_newline_in_the_name(self):
        for seed in ("a|b", "a\nb"):
            p = build({"seed": seed, "paths": ["casual-core"]})
            self.assertEqual(client_line_one(p.flag_line())[1], p.seed)

    @unittest.expectedFailure
    def test_the_client_reads_line_one_back_as_written_with_a_comma_in_sense(self):
        p = build({"seed": "x", "paths": ["casual-core"], "senseData": "x,y"})
        self.assertIn("sense=" + p.sense, client_line_one(p.flag_line())[0])

    @unittest.expectedFailure
    def test_the_client_reads_line_one_back_as_written_with_a_comma_in_the_pool(self):
        p = build({"seed": "x", "paths": ["casual-core"], "selectedPool": "Hard,Mode"})
        self.assertIn("pool=" + p.pool_preset, client_line_one(p.flag_line())[0])


class WorldViewProps(QuietNdb):

    @settings(max_examples=examples(100))
    @given(page_json(), world_blob())
    def test_a_world_flags_like_a_copy_with_its_overrides_set(self, j, blob):
        j = dict(j, players=2, coopGameMode="Multiworld", worldSettings=[{}, blob])
        p = build(j)
        self.assertIs(world_view(p, 1), p)
        twin = build(j)
        for key, (attr, conv) in WORLD_FIELDS.items():
            if blob.get(key) is not None:
                setattr(twin, attr, conv(blob[key]))
        if "variations" in blob and "enemyOpts" not in blob:
            twin.enemy_opts = {}
        twin.world_settings = []
        view = world_view(p, 2)
        self.assertEqual(view.flag_line(), twin.flag_line())
        self.assertEqual(view.flag_line(True), twin.flag_line(True))


class RerollProps(QuietNdb):
    """/reroll is from_json(to_json()) with a new seed."""

    @settings(max_examples=examples(100))
    @given(page_json())
    def test_to_json_is_a_fixpoint_of_the_round_trip(self, j):
        j1 = build(j).to_json()
        self.assertEqual(build(j1).to_json(), j1)

    @settings(max_examples=examples(100))
    @given(page_json())
    def test_a_reroll_keeps_every_worlds_flag_line(self, j):
        p1 = build(j)
        self.assertEqual(flag_lines(build(p1.to_json())), flag_lines(p1))

    @settings(max_examples=examples(100))
    @given(page_json())
    def test_a_reroll_keeps_every_setting(self, j):
        if only_worlds_hold_fass(j):
            event("masked: only worlds hold fass rows")
            return
        p1 = build(j)
        self.assertEqual(build(p1.to_json())._to_dict(), p1._to_dict())

    @unittest.expectedFailure
    def test_a_reroll_keeps_every_setting_when_only_a_world_holds_fass_rows(self):
        p1 = build({"seed": "x", "paths": ["casual-core"], "players": 2, "coopGameMode": "Multiworld",
                    "worldSettings": [{}, {"fass": [{"loc": "919772", "item": "SK|0"}]}]})
        self.assertEqual(build(p1.to_json())._to_dict(), p1._to_dict())


if __name__ == "__main__":
    unittest.main()
