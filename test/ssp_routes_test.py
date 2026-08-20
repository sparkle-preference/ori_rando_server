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

    def saved_params(self, name):
        return self.store.get(name)


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

        self.user = _FakeUser()
        self.logged_in = None
        User.get = staticmethod(lambda: self.logged_in)
        SavedSeedParams.get = staticmethod(
            lambda owner_name, name: self.user.store.get(name)
            if owner_name == self.user.name else None)
        self.client = main.app.test_client()

    def tearDown(self):
        User.get = self._user_get
        SavedSeedParams.get = self._ssp_get
        main.app.secret_key = self._secret
        models.client = self._ndb_client
        self._ctx.__exit__(None, None, None)

    def save(self, **body):
        return self.client.post("/settings/save",
                                data={"ssp": json.dumps(body)})

    def test_saving_needs_a_login(self):
        res = self.save(name="mine", params={"paths": ["casual-core"]})
        self.assertEqual(res.status_code, 401)

    def test_latest_is_refused(self):
        self.logged_in = self.user
        res = self.save(name="latest", params={})
        self.assertEqual(res.status_code, 422)
        self.assertIn(b"reserved", res.data)

    def test_a_blank_name_is_refused(self):
        self.logged_in = self.user
        self.assertEqual(self.save(name="  ", params={}).status_code, 422)

    def test_reading_someone_elses_needs_no_login(self):
        self.user.store["theirs"] = _FakeSSP(self.user, "theirs",
                                             settings={"paths": ["casual-core"]})
        res = self.client.get("/settings/lapis/theirs")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["settings"], {"paths": ["casual-core"]})

    def test_a_hidden_one_is_404_to_a_stranger(self):
        self.user.store["secret"] = _FakeSSP(self.user, "secret", hidden=True)
        self.assertEqual(self.client.get("/settings/lapis/secret").status_code, 404)

    def test_a_hidden_one_is_visible_to_its_owner(self):
        self.user.store["secret"] = _FakeSSP(self.user, "secret", hidden=True)
        self.logged_in = self.user
        self.assertEqual(self.client.get("/settings/lapis/secret").status_code, 200)

    def test_a_missing_one_is_404(self):
        self.assertEqual(self.client.get("/settings/lapis/nope").status_code, 404)

    def test_an_unknown_owner_is_404(self):
        self.assertEqual(self.client.get("/settings/nobody/x").status_code, 404)


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
