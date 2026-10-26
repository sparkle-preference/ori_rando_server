"""The route enumerator, request strategies, open-bug masks and emulator harness for test/routes_props.py."""
import contextlib
import json
import logging
import os
import re
import traceback
from collections import namedtuple
from urllib.parse import quote, unquote, urljoin, urlsplit

import flask
from google.cloud import datastore, ndb
from hypothesis import strategies as st
from jinja2 import ChoiceLoader, FileSystemLoader
from werkzeug.datastructures import MultiDict
from werkzeug.exceptions import HTTPException

import main
import models
import util
from cache import Cache
from models import BingoGameData, Game, Player, SavedSeedParams, Seed, User, pbc
from seedbuilder import seedparams
from seedbuilder.seedparams import SeedGenParams
from test.ndb_base import EmulatorTestCase

MAP_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "map", "src")

OWNER, STRANGER = "rp-owner", "rp-stranger"
OWNER_KEY = ("User2", OWNER)
SOLO, BINGO, MISSING = 31001, 31002, 31009
PARAMS = 31010
PLANDOS = ("alpha", "beta")
PRESETS = ("pre", "secret")

# the oidc routes reach the identity provider over the network
OFF_LIMITS = ("/login", "/logout", "/authorize", "/oidc_callback")

Rule = namedtuple("Rule", "rule endpoint methods args")


def _rules():
    out = []
    for rule in main.app.url_map.iter_rules():
        if rule.endpoint == "static" or rule.rule in OFF_LIMITS or rule.rule.endswith("/ws"):
            continue
        args = re.findall(r"<(?:(\w+):)?(\w+)>", rule.rule)
        out.append(Rule(rule.rule, rule.endpoint, frozenset(rule.methods - {"HEAD", "OPTIONS"}), args))
    return sorted(out, key=lambda r: (r.rule, r.endpoint))


RULES = _rules()
GET_RULES = [r for r in RULES if "GET" in r.methods]
# the dll's surface takes any client holding a game id: it has no owner to protect
SITE_RULES = [r for r in RULES if not r.rule.startswith("/netcode/")]

ODD = ["\t", "\n", "\r", "\x00", "\x7f", "\u3000", "\uff0f", "\u0663", "\ud7ff", "\u00e9"]
junk = st.text(alphabet=st.sampled_from(list("aZ09/\\%.:@?#&=+-_ ~") + ODD), max_size=12)
# str.isdigit() takes these and int() refuses them
SUPERSCRIPTS = "\u00b2\u00b3\u2079"


def rarely(common, rare, odds=12):
    """common, and one draw in odds rare; shrinks toward common."""
    return st.integers(0, odds - 1).flatmap(lambda k: rare if k == odds - 1 else common)


text = rarely(junk, st.tuples(junk, st.sampled_from(SUPERSCRIPTS)).map("".join))
INT_EDGES = ("0", "00", str(2 ** 63), "99999999999999999999")
small_int = st.integers(1, 40).map(str)
any_int = st.one_of(small_int, st.integers(1, 2 ** 63 - 1).map(str), st.sampled_from(INT_EDGES), st.just("\u0663"))

_words = {"name": ("owner", "stranger", "nobody") + PRESETS, "author_name": ("owner", "stranger", "nobody"),
          "owner_name": ("owner", "stranger", "nobody", "mine"), "seed_name": PLANDOS + ("gamma",),
          "new_name": PLANDOS + ("gamma",), "params_id": (str(PARAMS), "1"), "param_id": (str(PARAMS), "1"),
          "pid": ("1", "2"), "version": ("4.9.13", "all", "3.x", "nope"), "kind": ("SK", "EX", "RB", "MU"),
          "coords": ("-280256", "2", "1", "12345"), "id": ("0", "1", "15", "SK/0"), "signal": ("msg:hi", "ok"),
          "hours": ("1", "12", "x"), "game_id": (str(SOLO), str(BINGO), "-1")}
_ints = {"game_id": (SOLO, BINGO, MISSING), "player_id": (1, 2, 4), "world_id": (1, 2)}


def segment(conv, name):
    """One path segment for a converter and argument name, percent-encoded."""
    if conv == "int":
        return st.one_of(st.sampled_from(_ints.get(name, (1,))).map(str), any_int)
    words = st.sampled_from(_words.get(name, ("x",)))
    raw = st.one_of(words, words, text.filter(lambda s: s.strip("/")))
    if conv != "path":
        raw = raw.filter(lambda s: "/" not in s)
    return raw.filter(lambda s: s not in (".", "..")).map(lambda s: quote(s, safe="/" if conv == "path" else ""))


# what the routes read, less testIters, path and logic_mode: each runs board or seed generation
QUERY_KEYS = ("game_id", "player_id", "teams", "squares", "seed", "players", "lines", "force", "download",
              "difficulty", "verbose_paths", "tracking", "text", "skills", "modes", "joinTeam", "fass", "exclude",
              "dark", "cells", "all", "world", "verbose", "usermap", "time", "since", "showInfo", "redir", "pids",
              "p", "overwrite", "override", "offset", "noTimer", "name", "misc", "meta", "lockout", "limit",
              "highlights", "first", "discCount", "cp", "channel", "by_zone", "sec", "x")
query_value = st.one_of(text, small_int, st.sampled_from(
    ["", "0", "1", "-1", "true", "owner", str(SOLO), str(BINGO), "standard-core", "standard-core OPEN_WORLD", "1|2"]))
query = st.lists(st.tuples(st.sampled_from(QUERY_KEYS), query_value), max_size=4)


def _json(**fields):
    return st.fixed_dictionaries({}, optional=fields).map(json.dumps)


_name = st.one_of(st.sampled_from(PLANDOS + PRESETS + ("gamma", "owner", "stranger", "")), text)
# the bodies the site's own pages post, with names the owner's things already use
FORMS = {
    "plando.plando_upload": st.fixed_dictionaries({"seed": _json(oldName=_name, name=_name, desc=text, hidden=st.booleans(),
                                                                 flags=st.just(["ForceTrees"]), placements=st.just([]))}),
    "presets.ssp_save": st.fixed_dictionaries({"preset": _json(name=_name, desc=text, hidden=st.booleans(),
                                                               params=st.just({"paths": ["casual-core"]}))}),
    "presets.preset_edit": st.fixed_dictionaries({"preset": _json(name=_name, newName=_name, desc=text, hidden=st.booleans())}),
    "presets.preset_delete": st.fixed_dictionaries({"preset": _json(name=_name)}),
    "presets.ssp_import": st.fixed_dictionaries(
        {"presets": st.lists(st.fixed_dictionaries({"name": _name, "settings": st.just({"paths": ["casual-core"]})}),
                             max_size=2).map(json.dumps)}, optional={"overwrite": st.just("1")}),
    "users.user_set_settings": st.fixed_dictionaries({}, optional={"name": _name, "teamname": text, "theme": text,
                                                                   "verbose": st.sampled_from(["0", "1"])}),
    "plando.plando_reachable": st.fixed_dictionaries({"modes": st.just('["casual-core"]'), "inventory": st.just('{"SK|0": 1}')}),
    "generator.gen_seed_from_params": st.fixed_dictionaries({"params": st.sampled_from(["", "{", '{"paths": []}', "[]"])}),
    "seedstats.seedstats_roll": st.just({}),
}

Req = namedtuple("Req", "method path query form endpoint args")


def route(method, path):
    """(endpoint, decoded args) the app routes this percent-encoded path to, or (None, {})."""
    try:
        return main.app.url_map.bind("localhost").match(unquote(path), method=method)
    except HTTPException:
        return None, {}


def fill(draw, rule):
    """The rule's path with each argument drawn for its converter and name."""
    path = rule.rule
    for conv, name in rule.args:
        path = path.replace("<%s>" % (conv + ":" + name if conv else name), draw(segment(conv, name)), 1)
    return path


@st.composite
def requests(draw, rules=GET_RULES, methods=("GET",)):
    """A request for one of rules, routed the way the app will so a mask can read its endpoint and args."""
    rule = draw(st.sampled_from(rules))
    method = draw(st.sampled_from(sorted(rule.methods & set(methods))))
    path = fill(draw, rule)
    endpoint, args = route(method, path)
    form = draw(FORMS.get(endpoint, st.just({}))) if method == "POST" else None
    return Req(method, path, draw(query), form, endpoint, args)


def _datastore_id(value):
    try:
        return 0 < int(value) < 2 ** 63
    except (TypeError, ValueError):
        return False


def _asked(req, key):
    return [v for k, v in req.query if k == key]


def _first(req, key, default=None):
    """What param_val reads: the first value given for key."""
    return (_asked(req, key) or [default])[0]


def _no_logic_path(req):
    return not any(k in ("path", "logic_mode") for k, _ in req.query)


def id_past_the_datastore(case, req):
    """A game id of 0, or any int past int64, in the path or ?game_id."""
    ints = {k: v for k, v in req.args.items() if isinstance(v, int)}
    return ints.get("game_id") == 0 or any(v >= 2 ** 63 for v in ints.values()) or any(
        v.isdecimal() and not _datastore_id(v) for v in _asked(req, "game_id"))


def params_id_not_a_datastore_id(case, req):
    """A params id segment that isn't a positive int64."""
    pid = req.args.get("params_id", req.args.get("param_id"))
    return pid is not None and not _datastore_id(pid)


def nothing_to_build(case, req):
    """/generator/build or /generator/json naming no logic path."""
    return req.endpoint in ("generator.gen_seed_from_params", "generator.gen_seed_from_url") and _no_logic_path(req)


def guest_on_a_login_route(case, req):
    """A guest on /reroll, /myGames or /myPresets."""
    return case.requester is None and req.endpoint in ("generator.reroll_seed", "tracker.my_games", "presets.my_settings")


def bare_fillgen(case, req):
    """/plando/fillgen naming no logic path."""
    return req.endpoint == "plando.plando_fillgen" and _no_logic_path(req)


def newline_in_a_patchnotes_version(case, req):
    """A /patchnotes/<version> holding CR or LF."""
    return req.endpoint == "patchnotes.patchnotes_version" and any(c in req.args["version"] for c in "\r\n")


def newline_in_a_spectate_query(case, req):
    """A /tracker/spectate/<name> query holding CR or LF."""
    return req.endpoint == "tracker.get_map_by_name" and any(c in k + v for k, v in req.query for c in "\r\n")


def superscript_digit(case, req):
    """A superscript digit in ?game_id, ?pids, or the hours or game_id segment."""
    values = [req.args.get(k) for k in ("hours", "game_id") if isinstance(req.args.get(k), str)]
    values += _asked(req, "game_id") + _asked(req, "pids")
    return any(c in SUPERSCRIPTS for v in values for c in v)


def _game(case, gid, kind=Game):
    if not _datastore_id(gid):
        return None
    with case.ndb_client.context():
        return kind.get_by_id(int(gid))


def tracker_on_a_game_without_a_seed(case, req):
    """The item or map tracker of a game with no params."""
    if req.endpoint not in ("tracker.tracker_get_items_update", "tracker.tracker_update_map"):
        return False
    game = _game(case, req.args.get("game_id"))
    return bool(game) and not game.params


def params_that_never_generated(case, req):
    """The metadata or spoiler routes of params with no spoilers."""
    if req.endpoint not in ("generator.get_metadata_no_gid", "generator.get_param_metadata",
                            "generator.get_spoiler_from_params"):
        return False
    params = _game(case, req.args.get("params_id", req.args.get("param_id")), SeedGenParams)
    return bool(params) and not params.spoilers


def history_page_past_the_players(case, req):
    """A history page asked for a ?p= other than 0."""
    if req.endpoint != "tracker.game_show_history":
        return False
    try:
        return int(_first(req, "p", "0")) != 0
    except ValueError:
        return False


def history_line_at_an_unknown_coordinate(case, req):
    """A found pickup at a coordinate no location holds."""
    if req.endpoint != "netcode.netcode_found_pickup":
        return False
    try:
        coords = int(req.args["coords"])
    except ValueError:
        return False
    return util.coord_correction_map.get(coords, coords) not in pbc and abs(coords) != 1


def stray_player_in_a_bingo_game(case, req):
    """A netcode call or seed claim for a player the bingo board never seated."""
    if (req.endpoint or "").startswith("netcode.") and "player_id" in req.args:
        gid, pid = req.args.get("game_id"), req.args["player_id"]
    elif req.endpoint == "generator.load_seed_from_params" and case.requester:
        gid, pid = _first(req, "game_id"), _first(req, "player_id", "1")
    else:
        return False
    bingo = _game(case, gid, BingoGameData)
    return bool(bingo) and str(pid).strip() not in [str(p) for p in bingo.player_nums()]


def seat_claim_through_another_games_seed(case, req):
    """A seed download whose ?game_id names a game rolled from other params."""
    if req.endpoint != "generator.load_seed_from_params" or not case.requester:
        return False
    game = _game(case, _first(req, "game_id"))
    return bool(game) and (game.params is None or str(game.params.id()) != str(req.args.get("params_id")))


def an_export_stores_params(case, req):
    return req.endpoint == "users.user_export"


OPEN_BUGS = (id_past_the_datastore, params_id_not_a_datastore_id, nothing_to_build, guest_on_a_login_route,
             bare_fillgen, newline_in_a_patchnotes_version, newline_in_a_spectate_query, superscript_digit,
             tracker_on_a_game_without_a_seed, params_that_never_generated, history_page_past_the_players,
             history_line_at_an_unknown_coordinate, stray_player_in_a_bingo_game)
# the open bugs that write where a guest or stranger may not; the rest answer 500 and write nothing
WRITE_BUGS = (stray_player_in_a_bingo_game, seat_claim_through_another_games_seed, an_export_stores_params)


def open_bug(case, req, bugs=OPEN_BUGS):
    """The name of the open bug whose input class holds this request, or None."""
    return next((bug.__name__ for bug in bugs if bug(case, req)), None)


def browser_target(base, location):
    """Where a browser on base lands following location: tab and newline dropped, C0 and space trimmed, \\ as /."""
    location = re.sub(r"[\t\n\r]", "", location).strip("".join(chr(c) for c in range(0x21))).replace("\\", "/")
    return urlsplit(urljoin(base, location))


# the routes a guest or a stranger may write through; any other leaves the datastore as it was
WRITERS = frozenset([
    "bingo.bingo_create_game", "bingo.bingo_add_player", "bingo.add_bingo_to_game", "bingo.bingo_reroll_seed",
    "bingo.bingo_download_seed", "generator.load_seed_from_params", "generator.get_param_metadata",
    "generator.get_metadata_no_gid", "generator.gen_seed_from_url", "generator.gen_seed_from_params",
    "generator.reroll_seed", "plando.plando_download", "plando.plando_fillgen", "plando.plando_upload",
    "plando.plando_delete", "plando.plando_rename", "plando.plando_toggle_hide", "presets.ssp_roll",
    "presets.ssp_save", "presets.ssp_import", "presets.preset_edit", "presets.preset_delete", "presets.ssp_delete",
    "presets.ssp_hide_toggle", "users.user_toggle_darkmode", "users.user_set_settings"])


def may_change(req, requester, before):
    """Kinds of the owner's this request may change for a guest or a stranger."""
    if req.endpoint == "bingo.bingo_add_player":
        return {"BingoGameData", "Game", "Player"}  # a lobby seats whoever has its link
    if req.endpoint == "generator.load_seed_from_params":
        return {"Player", "Game"}  # downloading a world's seed claims that world
    if req.endpoint == "bingo.bingo_download_seed":
        return {"SeedGenParams"}  # a board's seed takes the Bingo flag when first handed out
    if req.endpoint == "bingo.add_bingo_to_game":
        board = before.get(("BingoGameData", req.args.get("game_id")))
        builder = board and board.get("User2")
        if board is None or (requester and builder and builder.flat_path == ("User2", requester)):
            return {"BingoGameData", "Game", "Player"}  # a game's first board is anyone's, and its builder's to rebuild
    return set()


def _values(v):
    if isinstance(v, (list, tuple)):
        return [x for item in v for x in _values(item)]
    if isinstance(v, dict):
        return _values(list(v.values()))
    return [v]


def names_the_owner(path, entity):
    """Whether an entity outside the owner's own holds the owner's key or name."""
    if path == OWNER_KEY:
        return False
    keys = [v.flat_path for v in _values(entity) if isinstance(v, datastore.Key)]
    return OWNER_KEY in keys or (path[0] == "User2" and entity.get("name") == "owner")


def stranger_writes(req, requester, owned, before, after):
    """What a guest's or a stranger's request wrote that it may not, as readable lines."""
    out = []
    allowed = may_change(req, requester, before)
    for path in sorted(before.keys() | after.keys(), key=str):
        was, now = before.get(path), after.get(path)
        if was == now:
            continue
        if now is None:
            what = "deleted %s" % (path,)
        elif was is None:
            what = "made %s" % (path,)
        else:
            what = "changed %s: %s" % (path, ", ".join(sorted(k for k in was.keys() | now.keys() if was.get(k) != now.get(k))))
        if req.endpoint not in WRITERS or (path in owned and path[-2] not in allowed):
            out.append(what)
        elif path not in owned and now is not None and names_the_owner(path, now):
            out.append(what + ", in the owner's name")
    return out


class _OuterContext(object):
    """Stands in for models.client: the harness opens each request's ndb context itself."""

    def context(self):
        return contextlib.nullcontext()


def stub(case, obj, name, value):
    """obj.name = value for this test, put back at cleanup."""
    old = obj.__dict__[name] if isinstance(obj, type) else getattr(obj, name)
    setattr(obj, name, value)
    case.addCleanup(setattr, obj, name, old)


_solo_params = None


def solo_params():
    """A generated seed, rolled once per process and stored under PARAMS by each fixture."""
    global _solo_params
    if _solo_params is None:
        # from_url stores what it builds; with put stubbed it hands back the entity instead
        put, SeedGenParams.put = SeedGenParams.put, lambda self: self
        try:
            params = SeedGenParams.from_url(MultiDict([("seed", "routes"), ("logic_mode", "standard")]))
        finally:
            SeedGenParams.put = put
        assert params.generate(store=False), "the fixture seed did not generate"
        _solo_params = params
    _solo_params.key = ndb.Key(SeedGenParams, PARAMS)
    return _solo_params


class RouteCase(EmulatorTestCase):
    """Requests through the real app as a guest (requester None) or a user id, each in a fresh ndb context."""
    requester = None

    def setUp(self):
        super(RouteCase, self).setUp()
        # the base holds one context for the whole test, and prod's middleware gives each request its own
        self._ctx.__exit__(None, None, None)
        self._ctx = contextlib.nullcontext()
        stub(self, User, "get", staticmethod(lambda: User.get_by_id(self.requester) if self.requester else None))
        stub(self, models, "client", _OuterContext())
        stub(self, main.app, "secret_key", main.app.secret_key or "routes-props")
        stub(self, util, "GUEST_USERS", False)
        stub(self, util, "CANONICAL_HOST", "")
        stub(self, util, "REDIRECT_HOSTS", [])
        # an exception answers 500 through the app's own handler, as it does in prod
        was = main.app.config.get("PROPAGATE_EXCEPTIONS")
        main.app.config["PROPAGATE_EXCEPTIONS"] = False
        self.addCleanup(main.app.config.__setitem__, "PROPAGATE_EXCEPTIONS", was)
        if not os.path.exists(os.path.join(util.template_root, util.INDEX_TEMPLATE)):
            stub(self, main.app.jinja_env, "loader", ChoiceLoader([main.app.jinja_env.loader, FileSystemLoader(MAP_SRC)]))
        self.addCleanup(logging.disable, logging.root.manager.disable)
        logging.disable(logging.CRITICAL)
        Cache.clear()
        with seedparams._PARAMS_LOCK:
            seedparams._PARAMS_CACHE.clear()
        self.raised = None
        flask.got_request_exception.connect(self._caught, main.app)
        self.addCleanup(flask.got_request_exception.disconnect, self._caught, main.app)
        self.client = main.app.test_client()

    def _caught(self, sender, exception, **kw):
        self.raised = exception

    def request(self, method, path, **kw):
        self.raised = None
        with self.ndb_client.context():
            return self.client.open(path, method=method, **kw)

    def get(self, path, **kw):
        return self.request("GET", path, **kw)

    def send(self, req):
        return self.request(req.method, req.path, query_string=req.query, data=req.form)

    def why(self, r):
        """What a response says about itself, for a failure message."""
        if self.raised is not None:
            return "".join(traceback.format_exception(self.raised, limit=-3))
        return r.get_data()[:300].decode("utf-8", "replace")

    def snapshot(self):
        """Every entity in the emulator, as {key path: properties}."""
        if not hasattr(self, "_datastore"):
            self._datastore = datastore.Client(project="orirandov3")
        return {e.key.flat_path: dict(e) for e in self._datastore.query().fetch()}

    def build_fixture(self):
        """The owner's account, a solo game, a bingo lobby, plandos and presets; a stranger with nothing."""
        was = self.requester
        self.requester = OWNER
        with self.ndb_client.context():
            owner = User(id=OWNER, name="owner", email="owner@example.com", teamname="owner's team")
            owner.put()
            User(id=STRANGER, name="stranger", email="stranger@example.com", teamname="stranger's team").put()
            params = solo_params()
            params.put()
            game = Game.from_params(params, SOLO)
            Player.claim_user_txn(game.player(1).key, owner.key)
            owner.games = [game.key]
            owner.put()
            for name, hidden in zip(PLANDOS, (False, True)):
                Seed(id="%s:%s" % (OWNER, name), name=name, author="owner", author_key=owner.key, flags=["ForceTrees"],
                     description="the owner's %s" % name, spoiler="spoiler for %s" % name, hidden=hidden,
                     players=1).put()
            settings = SavedSeedParams.settings_from(params.to_json())
            for name, hidden in zip(PRESETS, (False, True)):
                SavedSeedParams(id="%s:%s" % (OWNER, name), name=name, owner_key=owner.key, hidden=hidden,
                                description="the owner's %s" % name, settings=settings).put()
        Cache.set_gid(SOLO)
        for path in ("/bingo/new?seed=routes", "/bingo/game/%s/add/1" % BINGO):
            r = self.get(path)
            assert r.status_code == 200, (path, r.status_code, self.why(r))
        self.requester = was
