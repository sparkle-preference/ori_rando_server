"""The plando author routes: upload, delete, rename, hide, download.

These write and delete real entities, and the interesting case is what a `put()` does to a
key that is already taken -- so they run against the emulator rather than stubs, which is
the only way the question is asked honestly.

`User.get` is stubbed in the netcode_test save/restore style so the flask test client
carries an author; everything below it is the route prod runs.

Run from the repo root:  python3 -m unittest test.plando_routes_test -v
"""
import contextlib
import json
import unittest

import main
import models
from models import Seed, User
from test.ndb_base import EmulatorTestCase


class _OuterContext(object):
    """The request middleware opens an ndb context per request, and ndb contexts do not
    nest -- so hand it the one the test case is already inside."""

    def context(self):
        return contextlib.nullcontext()


class _PlandoRoutes(EmulatorTestCase):
    """Stubs only, no tests: a TestCase subclass inherits its parent's."""

    def setUp(self):
        super(_PlandoRoutes, self).setUp()
        self._user_get = User.__dict__["get"]
        self.user = None
        User.get = staticmethod(lambda: self.user)
        self.addCleanup(setattr, User, "get", self._user_get)
        self._ndb_client = models.client
        models.client = _OuterContext()
        self.addCleanup(setattr, models, "client", self._ndb_client)
        self._secret = main.app.secret_key
        main.app.secret_key = main.app.secret_key or "plando-test"
        self.addCleanup(setattr, main.app, "secret_key", self._secret)
        self.client = main.app.test_client()

    def author(self, uid="pl-1", name="pat"):
        user = User(id=uid, email="%s@example.com" % name, name=name,
                    teamname="%s's team" % name)
        user.put()
        self.user = user
        return user

    def seed(self, user, name, desc, hidden=False):
        s = Seed(id="%s:%s" % (user.key.id(), name), name=name, author=user.name,
                 author_key=user.key, description=desc, flags=["ForceTrees"],
                 hidden=hidden)
        s.put()
        return s

    def named(self, user, name):
        return Seed.get_by_id("%s:%s" % (user.key.id(), name))


class RenameTestCase(_PlandoRoutes):
    def test_rename_moves_the_seed(self):
        user = self.author()
        self.seed(user, "alpha", "the original")
        r = self.client.get("/plando/alpha/rename/beta")
        self.assertEqual(r.status_code, 302)
        self.assertIsNone(self.named(user, "alpha"))
        self.assertEqual(self.named(user, "beta").description, "the original")

    def test_an_occupied_name_changes_nothing(self):
        """A rename onto a name the author already uses would put() over that key.
        Both seeds are somebody's work and neither is recoverable."""
        user = self.author()
        self.seed(user, "alpha", "the one being renamed")
        self.seed(user, "beta", "a seed that already exists")
        r = self.client.get("/plando/alpha/rename/beta")
        self.assertEqual(r.status_code, 409)
        self.assertEqual(self.named(user, "beta").description, "a seed that already exists",
                         "the rename overwrote a seed that was already there")
        self.assertIsNotNone(self.named(user, "alpha"),
                             "the source was deleted into an overwrite")

    def test_a_copy_onto_an_occupied_name_changes_nothing(self):
        user = self.author()
        self.seed(user, "alpha", "the source")
        self.seed(user, "beta", "a seed that already exists")
        r = self.client.get("/plando/alpha/rename/beta?cp=1")
        self.assertEqual(r.status_code, 409)
        self.assertEqual(self.named(user, "beta").description, "a seed that already exists")
        self.assertEqual(self.named(user, "alpha").description, "the source")

    def test_a_copy_keeps_the_source(self):
        user = self.author()
        self.seed(user, "alpha", "the source")
        r = self.client.get("/plando/alpha/rename/gamma?cp=1")
        self.assertEqual(r.status_code, 302)
        self.assertIsNotNone(self.named(user, "alpha"), "cp=1 must not delete the source")
        self.assertEqual(self.named(user, "gamma").description, "the source")

    def test_renaming_to_the_same_name_is_not_a_way_to_lose_it(self):
        user = self.author()
        self.seed(user, "alpha", "the only copy")
        self.client.get("/plando/alpha/rename/alpha")
        self.assertIsNotNone(self.named(user, "alpha"), "a no-op rename deleted the seed")
        self.assertEqual(self.named(user, "alpha").description, "the only copy")

    def test_a_stranger_cannot_rename(self):
        owner = self.author()
        self.seed(owner, "alpha", "mine")
        self.user = None
        self.assertEqual(self.client.get("/plando/alpha/rename/beta").status_code, 401)
        self.assertIsNotNone(self.named(owner, "alpha"))

    def test_renaming_something_that_is_not_there(self):
        self.author()
        self.assertEqual(self.client.get("/plando/ghost/rename/beta").status_code, 404)


class DeleteAndHideTestCase(_PlandoRoutes):
    def test_delete_removes_it(self):
        user = self.author()
        self.seed(user, "alpha", "doomed")
        self.assertEqual(self.client.get("/plando/alpha/delete").status_code, 302)
        self.assertIsNone(self.named(user, "alpha"))

    def test_delete_needs_an_author(self):
        user = self.author()
        self.seed(user, "alpha", "mine")
        self.user = None
        self.assertEqual(self.client.get("/plando/alpha/delete").status_code, 401)
        self.assertIsNotNone(self.named(user, "alpha"), "an anonymous delete went through")

    def test_deleting_something_that_is_not_there(self):
        self.author()
        self.assertEqual(self.client.get("/plando/ghost/delete").status_code, 404)

    def test_hide_toggles_both_ways(self):
        user = self.author()
        self.seed(user, "alpha", "seen")
        self.client.get("/plando/alpha/hideToggle")
        self.assertTrue(self.named(user, "alpha").hidden)
        self.client.get("/plando/alpha/hideToggle")
        self.assertFalse(self.named(user, "alpha").hidden)

    def test_hide_needs_an_author(self):
        user = self.author()
        self.seed(user, "alpha", "seen")
        self.user = None
        self.assertEqual(self.client.get("/plando/alpha/hideToggle").status_code, 401)
        self.assertFalse(self.named(user, "alpha").hidden)


class UploadTestCase(_PlandoRoutes):
    BODY = {"name": "alpha", "oldName": "alpha", "desc": "d", "flags": ["ForceTrees"],
            "placements": [], "hidden": False}

    def _post(self, **over):
        body = dict(self.BODY, **over)
        return self.client.post("/plando/%s/upload" % body["name"],
                                data={"seed": json.dumps(body)})

    def test_upload_needs_an_author(self):
        self.user = None
        self.assertEqual(self._post().status_code, 401)

    def test_upload_creates_and_then_updates(self):
        user = self.author()
        self.assertEqual(self._post().status_code, 200)
        self.assertEqual(self.named(user, "alpha").description, "d")
        self.assertEqual(self._post(desc="second pass").status_code, 200)
        self.assertEqual(self.named(user, "alpha").description, "second pass",
                         "a second upload under the same name did not update it")


class DownloadTestCase(_PlandoRoutes):
    def test_a_hidden_seed_is_not_served_to_a_stranger(self):
        owner = self.author()
        self.seed(owner, "alpha", "secret", hidden=True)
        self.user = None
        r = self.client.get("/plando/pat/alpha/download")
        self.assertEqual(r.status_code, 404)

    def test_a_missing_seed_is_a_404(self):
        self.author()
        self.assertEqual(self.client.get("/plando/pat/ghost/download").status_code, 404)


if __name__ == "__main__":
    unittest.main()
