"""Properties of the route surface for a guest or a stranger, and of the plando editor's enemy rolls against the server's."""
from test.strategies.base import examples

import unittest
from urllib.parse import parse_qsl, quote, unquote

from hypothesis import assume, given, note, settings, strategies as st

from seedbuilder import enemyroll
from test import js_bridge
from test.strategies import routes as R

CANONICAL, OLD_HOST = "bf.orirando.com", "orirando.com"
METHODS = ("GET", "HEAD", "POST", "PUT", "DELETE", "PATCH", "OPTIONS")


class NoServerErrors(R.RouteCase):
    def setUp(self):
        super(NoServerErrors, self).setUp()
        self.build_fixture()

    @settings(max_examples=examples(1500))
    @given(R.requests())
    def test_no_get_answers_a_guest_with_a_500(self, req):
        assume(R.open_bug(self, req) is None)
        r = self.send(req)
        if r.status_code >= 500:
            self.fail("%s %r answered %s\n%s" % (req.path, req.query, r.status_code, self.why(r)))


@st.composite
def any_path(draw):
    """A path the app routes, with converter-aware segments, or one it doesn't."""
    if draw(st.booleans()):
        return R.fill(draw, draw(st.sampled_from(R.RULES)))
    segs = draw(st.lists(R.junk.filter(lambda s: s not in ("", ".", "..")), min_size=1, max_size=3))
    return "/" + "/".join(quote(s, safe="") for s in segs)


redir = st.one_of(R.junk, st.from_regex(r"\A[/\\%2Fa-z.@:\t ]{0,10}\Z"), R.junk.map(lambda s: quote(s, safe="")),
                  st.sampled_from(["//evil.example", "/\\evil.example", "https://evil.example", "/\t/evil.example",
                                   "%2F%2Fevil.example", "%252F%252Fevil.example", "\\\\evil.example", " //evil.example",
                                   "https:\\\\evil.example", "/plando/owner?x=1"]))


class Redirects(R.RouteCase):
    def setUp(self):
        super(Redirects, self).setUp()
        R.stub(self, R.util, "CANONICAL_HOST", CANONICAL)
        R.stub(self, R.util, "REDIRECT_HOSTS", [OLD_HOST])

    def follow(self, base, r):
        return R.browser_target(base, r.headers.get("Location", ""))

    @settings(max_examples=examples(1000))
    @given(st.sampled_from(METHODS), any_path(), st.lists(st.tuples(R.junk, R.junk), max_size=3))
    def test_only_browser_reads_leave_the_old_host_and_they_keep_path_and_query(self, method, path, qs):
        r = self.request(method, path, query_string=qs, base_url="https://" + OLD_HOST)
        seen = r.request
        # a browser resolves dot segments before it sends a path
        assume(not any(seg in (".", "..") for seg in seen.path.split("/")))
        target = self.follow("https://%s%s" % (OLD_HOST, seen.path), r)
        note("%s %s -> %s %s" % (method, seen.full_path, r.status_code, r.headers.get("Location")))
        if method not in ("GET", "HEAD") or seen.path.startswith("/netcode/"):
            self.assertNotEqual(r.status_code, 301)
            self.assertNotEqual(target.netloc, CANONICAL)
            return
        self.assertEqual(r.status_code, 301)
        self.assertEqual((target.scheme, target.netloc), ("https", CANONICAL))
        self.assertEqual(unquote(target.path), seen.path)
        self.assertEqual(parse_qsl(target.query, keep_blank_values=True),
                         parse_qsl(seen.query_string.decode("latin-1"), keep_blank_values=True))

    @settings(max_examples=examples(1000))
    @given(redir)
    def test_theme_toggle_never_sends_a_browser_off_site(self, target):
        r = self.get("/theme/toggle", query_string={"redir": target}, base_url="https://" + CANONICAL)
        self.assertIn(r.status_code, (301, 302, 303, 307, 308))
        self.assertEqual(self.follow("https://%s/theme/toggle" % CANONICAL, r).netloc, CANONICAL, r.headers.get("Location"))


class StrangersLeaveTheOwnersThingsAlone(R.RouteCase):
    def setUp(self):
        super(StrangersLeaveTheOwnersThingsAlone, self).setUp()
        self.build_fixture()
        self.owned = set(self.snapshot()) - {("User2", R.STRANGER)}

    @settings(max_examples=examples(200))
    @given(st.sampled_from([None, R.STRANGER]), R.requests(R.SITE_RULES, ("GET", "POST")))
    def test_a_guest_or_stranger_leaves_the_owners_things_and_reading_routes_write_nothing(self, who, req):
        self.requester = who
        assume(R.open_bug(self, req, R.WRITE_BUGS) is None)
        before = self.snapshot()
        r = self.send(req)
        writes = R.stranger_writes(req, who, self.owned, before, self.snapshot())
        self.assertEqual(writes, [], "%s %s %r %r as %s answered %s" % (req.method, req.path, req.query, req.form,
                                                                        who or "a guest", r.status_code))


class OpenBugRepros(R.RouteCase):
    """One minimal repro per input class an open bug's mask keeps out of the properties above."""

    def assertAllBelow500(self, *paths):
        for path in paths:
            r = self.get(path)
            if r.status_code >= 500:
                self.fail("%s answered %s\n%s" % (path, r.status_code, self.why(r)))

    @unittest.expectedFailure
    def test_an_id_the_datastore_cant_hold_is_not_a_500(self):
        self.build_fixture()
        self.assertAllBelow500("/game/0", "/game/%s" % 2 ** 63, "/generator/seed/%s?game_id=0" % R.PARAMS,
                               "/netcode/game/%s/player/%s/found/-280256/SK/0" % (R.SOLO, 2 ** 63))

    @unittest.expectedFailure
    def test_a_params_id_that_isnt_a_number_is_not_a_500(self):
        self.assertAllBelow500("/generator/seed/x", "/generator/seed/0", "/generator/spoiler/x", "/generator/metadata/x")

    @unittest.expectedFailure
    def test_a_build_with_no_logic_path_is_not_a_500(self):
        self.assertAllBelow500("/generator/build", "/generator/json")

    @unittest.expectedFailure
    def test_a_login_route_without_a_user_is_not_a_500(self):
        self.assertAllBelow500("/reroll", "/myGames", "/myPresets")

    @unittest.expectedFailure
    def test_a_bare_fillgen_is_not_a_500(self):
        self.assertAllBelow500("/plando/fillgen")

    @unittest.expectedFailure
    def test_a_patchnotes_version_with_a_newline_is_not_a_500(self):
        self.assertAllBelow500("/patchnotes/%0A")

    @unittest.expectedFailure
    def test_a_spectate_query_with_a_newline_is_not_a_500(self):
        self.build_fixture()
        self.assertAllBelow500("/tracker/spectate/owner?x=%0A")

    @unittest.expectedFailure
    def test_a_superscript_digit_is_not_a_500(self):
        self.build_fixture()
        self.assertAllBelow500("/activeGames/%C2%B2/", "/bingo/userboard/owner/fetch/%C2%B2",
                               "/game/%s/history/?pids=%%C2%%B2" % R.SOLO, "/generator/seed/%s?game_id=%%C2%%B2" % R.PARAMS)

    @unittest.expectedFailure
    def test_the_trackers_of_a_game_without_a_seed_are_not_a_500(self):
        self.build_fixture()
        self.assertAllBelow500("/tracker/game/%s/fetch/items/1" % R.BINGO,
                               "/tracker/game/%s/fetch/update?modes=standard-core" % R.BINGO)

    @unittest.expectedFailure
    def test_the_params_a_failed_roll_leaves_are_not_a_500(self):
        with self.ndb_client.context():
            pid = R.SeedGenParams.from_json({"seed": "x", "paths": ["casual-core"]}).id()
        self.assertAllBelow500("/generator/metadata/%s" % pid, "/generator/spoiler/%s" % pid)

    @unittest.expectedFailure
    def test_a_history_page_for_a_player_past_the_games_is_not_a_500(self):
        self.build_fixture()
        self.assertAllBelow500("/game/%s?p=1" % R.SOLO, "/game/%s/history/?p=-2" % R.SOLO)

    @unittest.expectedFailure
    def test_a_history_line_at_an_unknown_coordinate_still_prints(self):
        self.build_fixture()
        self.get("/netcode/game/%s/player/1/found/12345/SK/0" % R.SOLO)
        self.assertAllBelow500("/game/%s/history/" % R.SOLO, "/game/%s/players/" % R.SOLO)

    @unittest.expectedFailure
    def test_a_player_the_bingo_board_never_seated_does_not_break_it(self):
        self.build_fixture()
        self.get("/netcode/game/%s/player/4/found/-280256/SK/0" % R.BINGO)
        self.assertAllBelow500("/bingo/bingothon/%s/player/4" % R.BINGO, "/bingo/game/%s/fetch?first=1" % R.BINGO)

    @unittest.expectedFailure
    def test_a_seed_download_claims_a_seat_only_in_its_own_game(self):
        self.build_fixture()
        self.requester = R.STRANGER
        self.get("/generator/seed/%s?game_id=%s&player_id=1" % (R.PARAMS, R.BINGO))
        seat = self.snapshot()[("Game", R.BINGO, "Player", "%s.1" % R.BINGO)]
        self.assertEqual(seat["user"].flat_path, R.OWNER_KEY)

    @unittest.expectedFailure
    def test_an_export_leaves_the_datastore_as_it_was(self):
        self.build_fixture()
        self.requester = R.OWNER
        before = self.snapshot()
        self.get("/user/export")
        self.assertEqual(sorted(self.snapshot().keys() - before.keys(), key=str), [])


T = enemyroll.table()
SPOTS, VARIANTS = len(T["placements"]), len(T["variants"])
roll = st.one_of(st.none(), st.integers(0, VARIANTS - 1), st.integers(0, 99).map("b%d".__mod__))
# a placement-long list costs too much to draw whole, so a rolled or uniform line takes a few edits
BASES = [[None] * SPOTS, enemyroll.roll("routes", 1, None), enemyroll.roll("props", 2, None),
         [k % VARIANTS for k in range(SPOTS)], ["b%d" % (k % 100) for k in range(SPOTS)]]


def _edited(base, edits):
    out = list(base)
    for at, r in edits.items():
        out[at] = r
    return out


rolls = st.builds(_edited, st.sampled_from(BASES), st.dictionaries(st.integers(0, SPOTS - 1), roll, max_size=12))
# the game's int.Parse: ASCII digits, a sign, and ASCII whitespace at either end; any other token fails the seed load
game_token = st.tuples(st.sampled_from(["", " ", "\t", "\x0b", "\x0c"]), st.sampled_from(["", "+", "-"]),
                       st.sampled_from(["", "00"]), st.one_of(st.integers(0, VARIANTS + 2), st.integers(0, 10 ** 4)),
                       st.sampled_from(["", " ", "\r", "\t"]))
game_token = game_token.map(lambda t: "%s%s%s%d%s" % t)
game_token = st.one_of(game_token, game_token.map("b".__add__))


class EnemyRollsReadAlike(unittest.TestCase):
    @settings(max_examples=examples(300))
    @given(rolls)
    def test_a_line_the_editor_writes_reads_back_in_the_server(self, rs):
        self.assertEqual(enemyroll.rolls_of(js_bridge.call("enemies.js", "rolls_line", rs)), rs)

    @settings(max_examples=examples(300))
    @given(rolls)
    def test_a_line_the_server_writes_reads_back_in_the_editor(self, rs):
        self.assertEqual(js_bridge.call("enemies.js", "parse_rolls", enemyroll.meta_line(rs)), rs)

    @settings(max_examples=examples(300))
    @given(rolls, st.integers(0, SPOTS - 1), game_token)
    def test_a_roll_the_game_reads_reads_alike_in_the_editor_and_the_server(self, rs, at, token):
        line = enemyroll.meta_line(rs[:at] + ["@"] + rs[at + 1:]).replace("@", token)
        note(token)
        self.assertEqual(js_bridge.call("enemies.js", "parse_rolls", line), enemyroll.rolls_of(line))


if __name__ == "__main__":
    unittest.main()
