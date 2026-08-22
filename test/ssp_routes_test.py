"""The saved-settings routes, driven through test_client.

Stubs in the save/restore style (no mock lib): User.get and the owner lookups
are stubbed, everything between them is the code prod runs.

Run from the repo root:  python3 -m unittest test.ssp_routes_test -v
"""
import contextlib
import json
import unittest

import google.auth.credentials
from google.cloud import ndb

import main
import models
from models import SavedSeedParams, User


class _FakeNdbClient(object):
    def context(self):
        return contextlib.nullcontext()


class _FakeKey(object):
    def __init__(self, kid):
        self._id = kid

    def id(self):
        return self._id

    def __eq__(self, other):
        return isinstance(other, _FakeKey) and other._id == self._id


class _FakeUser(object):
    def __init__(self, name="lapis"):
        self.name = name
        self.key = _FakeKey(name)
        self.store = {}
        self.games = []

    def saved_params(self, name):
        return self.store.get(name)


class _FakeGameKey(object):
    """user.games holds keys; /preset/list and /preset/latest dereference the
    last one."""

    def __init__(self, params="some-params", json=None):
        payload = dict(json or {})

        class _G(object):
            def __init__(self):
                self.params = params

            def fetch_params(self):
                return self

            def to_json(self):
                return dict(payload)

        self.game = _G()

    def get(self):
        return self.game


class _FakeSSP(object):
    """Enough of the entity for the routes: populate/put/delete land in the
    owner's dict instead of the datastore."""

    def __init__(self, owner, name, settings=None, hidden=False, desc=None):
        self.owner, self.name = owner, name
        self.settings = settings if settings is not None else {}
        self.hidden, self.description = hidden, desc
        self.owner_key = owner.key
        self.deleted = False
        self.key = self

    def populate(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)

    def put(self):
        self.owner.store[self.name] = self

    def delete(self):
        self.deleted = True
        self.owner.store.pop(self.name, None)

    def put(self):
        self.owner.store[self.name] = self

    def owned_by(self, user):
        return bool(user) and user is self.owner


class SSPRouteTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        creds = google.auth.credentials.AnonymousCredentials()
        cls.ndb_client = ndb.Client(project="unit-test", credentials=creds)

    def setUp(self):
        self._ctx = self.ndb_client.context()
        self._ctx.__enter__()
        self._ndb_client = models.client
        models.client = _FakeNdbClient()
        self._secret = main.app.secret_key
        main.app.secret_key = main.app.secret_key or "ssp-test"
        self._user_get = User.__dict__["get"]
        self._ssp_get = SavedSeedParams.__dict__["get"]

        # no datastore here, so nothing to open a transaction against; drive the
        # rename logic directly. Its transactionality is untested by design --
        # see the emulator-backed testing item in ACTION_PLAN.md.
        self._rename = main._rename_preset
        main._rename_preset = main._rename_preset_body

        self.user = _FakeUser()
        self.logged_in = None
        User.get = staticmethod(lambda: self.logged_in)
        SavedSeedParams.get = staticmethod(
            lambda owner_name, name: self.user.store.get(name)
            if owner_name == self.user.name else None)
        self.client = main.app.test_client()

    def tearDown(self):
        main._rename_preset = self._rename
        User.get = self._user_get
        SavedSeedParams.get = self._ssp_get
        main.app.secret_key = self._secret
        models.client = self._ndb_client
        self._ctx.__exit__(None, None, None)

    def save(self, **body):
        return self.client.post("/preset/save",
                                data={"preset": json.dumps(body)})

    def test_saving_needs_a_login(self):
        res = self.save(name="mine", params={"paths": ["casual-core"]})
        self.assertEqual(res.status_code, 401)

    def test_latest_is_refused(self):
        self.logged_in = self.user
        res = self.save(name="latest", params={})
        self.assertEqual(res.status_code, 422)
        self.assertIn(b"reserved", res.data)

    def test_default_is_refused_too(self):
        """The dropdown always shows a Default entry, so the name is spoken for."""
        self.logged_in = self.user
        res = self.save(name="Default", params={})
        self.assertEqual(res.status_code, 422)
        self.assertIn(b"reserved", res.data)

    def test_url_unsafe_names_are_refused(self):
        """A preset name is a path segment in its own share link. One with a
        slash saved fine and then 404'd on every read, share and roll."""
        self.logged_in = self.user
        for name in ("a/b", "who?", "hash#tag", "back\\slash", "a&b", "x=y", "at@me"):
            res = self.save(name=name, params={})
            self.assertEqual(res.status_code, 422, "%r should be refused" % name)
        self.assertIsNone(SavedSeedParams.name_problem("perfectly fine 2"))

    def test_names_with_brackets_are_refused(self):
        """A borrowed preset displays as "name (owner)", so a name carrying its
        own brackets reads as an owner it does not have."""
        self.logged_in = self.user
        for name in ("mine (lapis)", "bracket(", "close)"):
            self.assertEqual(self.save(name=name, params={}).status_code, 422)
        self.assertIsNone(SavedSeedParams.name_problem("no brackets here"))

    def test_a_blank_name_is_refused(self):
        self.logged_in = self.user
        self.assertEqual(self.save(name="  ", params={}).status_code, 422)

    def test_reading_someone_elses_needs_no_login(self):
        self.user.store["theirs"] = _FakeSSP(self.user, "theirs",
                                             settings={"paths": ["casual-core"]})
        res = self.client.get("/preset/lapis/theirs")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["settings"], {"paths": ["casual-core"]})

    def test_a_hidden_one_is_404_to_a_stranger(self):
        self.user.store["secret"] = _FakeSSP(self.user, "secret", hidden=True)
        self.assertEqual(self.client.get("/preset/lapis/secret").status_code, 404)

    def test_a_hidden_one_is_visible_to_its_owner(self):
        self.user.store["secret"] = _FakeSSP(self.user, "secret", hidden=True)
        self.logged_in = self.user
        self.assertEqual(self.client.get("/preset/lapis/secret").status_code, 200)

    def test_a_missing_one_is_404(self):
        self.assertEqual(self.client.get("/preset/lapis/nope").status_code, 404)

    def test_an_unknown_owner_is_404(self):
        self.assertEqual(self.client.get("/preset/nobody/x").status_code, 404)


class SSPListTestCase(SSPRouteTestCase):
    """/preset/list feeds the seedgen dropdown."""

    def setUp(self):
        super(SSPListTestCase, self).setUp()
        # the route builds an owner_key filter, and KeyProperty type-checks the
        # value while the expression is built, before any stubbed query runs
        self.user.key = ndb.Key("User2", "lapis")
        self._query = SavedSeedParams.__dict__.get("query")
        SavedSeedParams.query = staticmethod(
            lambda *a, **kw: list(self.user.store.values()))

    def tearDown(self):
        if self._query is None:
            del SavedSeedParams.query
        else:
            SavedSeedParams.query = self._query
        super(SSPListTestCase, self).tearDown()

    def test_anonymous_gets_an_empty_list_not_a_401(self):
        res = self.client.get("/preset/list")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json(),
                         {"owner": None, "hasLatest": False, "settings": []})

    def test_the_owner_sees_their_own_sorted_case_insensitively(self):
        for name in ("zeta", "Alpha", "middle"):
            self.user.store[name] = _FakeSSP(self.user, name)
        self.logged_in = self.user
        body = self.client.get("/preset/list").get_json()
        self.assertEqual(body["owner"], "lapis")
        self.assertEqual([s["name"] for s in body["settings"]],
                         ["Alpha", "middle", "zeta"])

    def test_last_seed_is_offered_only_once_a_game_exists(self):
        """Load and Generate grey out on "Last Seed" until there is a game to
        take options from."""
        self.logged_in = self.user
        self.assertIs(self.client.get("/preset/list").get_json()["hasLatest"], False)
        self.user.games = [_FakeGameKey()]
        self.assertIs(self.client.get("/preset/list").get_json()["hasLatest"], True)

    def test_a_game_without_params_does_not_count(self):
        """A paramless game is one /preset/latest and /reroll both refuse, so
        lighting the buttons for it would promise something that fails."""
        self.logged_in = self.user
        self.user.games = [_FakeGameKey(params=None)]
        self.assertIs(self.client.get("/preset/list").get_json()["hasLatest"], False)

    def test_hidden_ones_are_listed_to_their_owner(self):
        self.user.store["secret"] = _FakeSSP(self.user, "secret", hidden=True)
        self.logged_in = self.user
        body = self.client.get("/preset/list").get_json()
        self.assertEqual(body["settings"], [{"name": "secret", "desc": None,
                                             "hidden": True}])


class LastSeedTestCase(SSPRouteTestCase):
    """/preset/latest is the one load that carries a lobby -- and still no seed."""

    def test_it_keeps_the_lobby(self):
        """Rerolling a multiworld has always produced a multiworld; loading the
        last seed's options must not quietly hand back a solo game."""
        self.logged_in = self.user
        self.user.games = [_FakeGameKey(json={"players": 3, "coopGameMode": "Multiworld",
                                              "shared": ["Skills"], "keyMode": "Clues"})]
        body = self.client.get("/preset/latest").get_json()
        self.assertIs(body["withLobby"], True)
        self.assertEqual(body["settings"]["players"], 3)
        self.assertEqual(body["settings"]["coopGameMode"], "Multiworld")

    def test_it_never_sends_the_seed(self):
        """The seed string is the user's to type. Only a ?param_id= rehydrate
        may fill it, which is a different route."""
        self.logged_in = self.user
        self.user.games = [_FakeGameKey(json={"seed": "12345", "keyMode": "Clues",
                                              "flagLine": "Standard,Clues|1", "isPlando": False,
                                              "spoilers": True, "teamStr": "1"})]
        settings = self.client.get("/preset/latest").get_json()["settings"]
        for output_only in ("seed", "flagLine", "isPlando", "spoilers", "teamStr"):
            self.assertNotIn(output_only, settings)
        self.assertEqual(settings["keyMode"], "Clues")


class PresetEditTestCase(SSPRouteTestCase):
    """The gear by the Update button: rename, describe, hide, delete."""

    def edit(self, **body):
        return self.client.post("/preset/edit", data={"preset": json.dumps(body)})

    def delete(self, **body):
        return self.client.post("/preset/delete", data={"preset": json.dumps(body)})

    def given_a_preset(self, name="mine", **kw):
        self.user.store[name] = _FakeSSP(self.user, name, **kw)
        return self.user.store[name]

    def test_editing_needs_a_login(self):
        self.given_a_preset()
        self.assertEqual(self.edit(name="mine", desc="x").status_code, 401)

    def test_deleting_needs_a_login(self):
        self.given_a_preset()
        self.assertEqual(self.delete(name="mine").status_code, 401)
        self.assertIn("mine", self.user.store)

    def test_you_can_only_touch_your_own(self):
        """saved_params is keyed to the caller, so naming someone else's preset
        finds nothing rather than reaching it."""
        self.logged_in = _FakeUser("someone-else")
        self.given_a_preset()
        self.assertEqual(self.edit(name="mine", newName="stolen").status_code, 404)
        self.assertEqual(self.delete(name="mine").status_code, 404)
        self.assertIn("mine", self.user.store)

    def test_metadata_only_edit_leaves_the_options_alone(self):
        ssp = self.given_a_preset(settings={"keyMode": "Clues"}, desc="old", hidden=False)
        self.logged_in = self.user
        res = self.edit(name="mine", newName="mine", desc="new", hidden=True)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(ssp.description, "new")
        self.assertIs(ssp.hidden, True)
        self.assertEqual(ssp.settings, {"keyMode": "Clues"})

    def test_a_rename_onto_an_existing_name_is_refused(self):
        self.given_a_preset("mine")
        self.given_a_preset("taken")
        self.logged_in = self.user
        res = self.edit(name="mine", newName="taken")
        self.assertEqual(res.status_code, 409)
        self.assertIn("mine", self.user.store)

    def test_a_rename_to_a_reserved_name_is_refused(self):
        self.given_a_preset()
        self.logged_in = self.user
        for reserved in ("latest", "Default"):
            res = self.edit(name="mine", newName=reserved)
            self.assertEqual(res.status_code, 422)
            self.assertIn(b"reserved", res.data)

    def test_deleting_your_own_removes_it(self):
        self.given_a_preset()
        self.logged_in = self.user
        res = self.delete(name="mine")
        self.assertEqual(res.status_code, 200)
        self.assertNotIn("mine", self.user.store)


class SettingsSplitOnSaveTestCase(SSPRouteTestCase):
    """The route saves the split, not the raw request."""

    def test_the_lobby_is_not_saved(self):
        self.logged_in = self.user
        # a real entity would be created here; stub the constructor's slot
        made = {}

        def fake_ctor(**kw):
            made.update(kw)
            ssp = _FakeSSP(self.user, kw.get("id", "x").split(":")[-1])
            return ssp

        real = main.SavedSeedParams
        try:
            class Shim(object):
                get = staticmethod(real.get)
                name_problem = staticmethod(real.name_problem)
                settings_from = staticmethod(real.settings_from)

                def __new__(cls, **kw):
                    return fake_ctor(**kw)

            main.SavedSeedParams = Shim
            res = self.save(name="solo", params={
                "paths": ["casual-core"], "keyMode": "Clues",
                "players": 4, "syncShared": ["Skills"], "seed": "12345",
            })
        finally:
            main.SavedSeedParams = real
        self.assertEqual(res.status_code, 200)
        saved = self.user.store["solo"].settings
        self.assertEqual(saved.get("keyMode"), "Clues")
        for gone in ("players", "syncShared", "seed"):
            self.assertNotIn(gone, saved)


if __name__ == "__main__":
    unittest.main()
