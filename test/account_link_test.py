"""The two beta account conveniences: take your things off the box, or take
the account itself to another browser.

The link is a bearer token in a URL, so the properties that matter are that it
works exactly once and that it stops working. Both are pinned here.

Run from the repo root:  python -m unittest test.account_link_test -v
"""
from datetime import timedelta
import io
import zipfile

from test.guest_users_test import _GuestHarness


class _BetaHarness(_GuestHarness):
    """Stubs only -- no tests. A beta build, with the guest seat live."""

    def setUp(self):
        super(_BetaHarness, self).setUp()
        self._beta = self.util.BETA_OF
        self.util.BETA_OF = [5, 0, 0]

    def tearDown(self):
        self.util.BETA_OF = self._beta
        super(_BetaHarness, self).tearDown()

    def _req(self, client, path):
        # same dance as _whoami: the middleware opens its own ndb context
        self._ctx.__exit__(None, None, None)
        try:
            return client.get(path)
        finally:
            self._ctx = self.ndb_client.context()
            self._ctx.__enter__()

    def _mint(self, client):
        res = self._req(client, "/user/link/new")
        self.assertEqual(res.status_code, 200, res.data)
        body = res.data.decode()
        nonce = body.split("/user/link/")[1].split("<")[0].strip()
        self.assertTrue(nonce, "no link in the page")
        return nonce


class AccountLinkTestCase(_BetaHarness):

    def test_a_link_seats_the_second_browser_on_the_first_account(self):
        a, b = self.main.app.test_client(), self.main.app.test_client()
        mine, theirs = self._whoami(a), self._whoami(b)
        self.assertNotEqual(mine, theirs)
        res = self._req(b, "/user/link/%s" % self._mint(a))
        self.assertEqual(res.status_code, 302, res.data)
        self.assertEqual(self._whoami(b), mine, "the link did not move the account")

    def test_only_the_first_visitor_gets_in(self):
        a, b, c = (self.main.app.test_client() for _ in range(3))
        mine = self._whoami(a)
        nonce = self._mint(a)
        was_c = self._whoami(c)
        self._req(b, "/user/link/%s" % nonce)
        res = self._req(c, "/user/link/%s" % nonce)
        self.assertEqual(res.status_code, 404, "a spent link let a second visitor in")
        self.assertEqual(self._whoami(c), was_c, "the loser's own account changed")
        self.assertEqual(self._whoami(b), mine)

    def test_a_stale_link_is_refused(self):
        from models import AccountLink
        a, b = self.main.app.test_client(), self.main.app.test_client()
        was_b = self._whoami(b)
        nonce = self._mint(a)
        link = AccountLink.get_by_id(nonce)
        link.created = link.created - AccountLink.TTL - timedelta(minutes=1)
        link.put()
        res = self._req(b, "/user/link/%s" % nonce)
        self.assertEqual(res.status_code, 404, "an expired link still worked")
        self.assertEqual(self._whoami(b), was_b)

    def test_an_invented_nonce_is_refused(self):
        b = self.main.app.test_client()
        res = self._req(b, "/user/link/not-a-real-nonce")
        self.assertEqual(res.status_code, 404, res.data)

    def test_a_release_build_has_neither_route(self):
        self.util.BETA_OF = None
        c = self.main.app.test_client()
        for path in ("/user/link/new", "/user/link/whatever", "/user/export"):
            self.assertEqual(self._req(c, path).status_code, 404,
                             "%s answered on a release build" % path)


class UserExportTestCase(_BetaHarness):

    def _seed_content(self, user_key):
        from models import Seed, SavedSeedParams
        from seedbuilder.seedparams import Placement, Stuff
        SavedSeedParams(id="%s:apreset" % user_key.id(), name="apreset",
                        owner_key=user_key, settings={}).put()
        Seed(id="%s:aplando" % user_key.id(), name="aplando", author_key=user_key,
             description="what it is", spoiler="what is in it", flags=["OpenWorld"],
             players=1,
             placements=[Placement(location="919772", zone="Glades",
                                   stuff=[Stuff(code="SK", id="0", player="1")])]).put()

    def test_the_zip_holds_the_presets_and_each_plandos_files(self):
        from models import User
        c = self.main.app.test_client()
        name = self._whoami(c)
        self._seed_content(User.get_by_name(name).key)
        res = self._req(c, "/user/export")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.headers["Content-Type"], "application/zip")
        names = zipfile.ZipFile(io.BytesIO(res.data)).namelist()
        self.assertIn("presets.json", names)
        self.assertIn("plandos/aplando/randomizer.dat", names)
        self.assertIn("plandos/aplando/description.txt", names)
        self.assertIn("plandos/aplando/spoiler.txt", names)

    def test_the_seed_file_is_the_real_thing(self):
        from models import User
        c = self.main.app.test_client()
        self._seed_content(User.get_by_name(self._whoami(c)).key)
        res = self._req(c, "/user/export")
        dat = zipfile.ZipFile(io.BytesIO(res.data)).read(
            "plandos/aplando/randomizer.dat").decode()
        self.assertTrue(dat.startswith("OpenWorld|aplando"), dat)
        self.assertIn("919772|SK|0|Glades", dat)

    def test_prose_only_ships_when_the_author_wrote_some(self):
        from models import Seed, User
        c = self.main.app.test_client()
        user = User.get_by_name(self._whoami(c))
        Seed(id="%s:bare" % user.key.id(), name="bare", author_key=user.key,
             flags=["OpenWorld"], players=1).put()
        res = self._req(c, "/user/export")
        names = zipfile.ZipFile(io.BytesIO(res.data)).namelist()
        self.assertIn("plandos/bare/randomizer.dat", names)
        self.assertNotIn("plandos/bare/description.txt", names)
        self.assertNotIn("plandos/bare/spoiler.txt", names)
