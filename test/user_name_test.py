"""One rule decides whether a name can be taken.

The modal asks before you submit and the rename decides when you do. If those
two ever disagree the page either promises a name it cannot deliver or refuses
one it could, so both go through `User.name_available`.

Needs the datastore emulator: the check is a query, and a stub that answers the
same for every name tests nothing.

Run from the repo root:  python3 -m unittest test.user_name_test -v
"""
import unittest

from test.ndb_base import EmulatorTestCase


class NameAvailableTestCase(EmulatorTestCase):

    def make(self, name, uid="someone"):
        from models import User
        u = User(id=uid, name=name)
        u.put()
        return u

    def test_a_name_nobody_holds_is_free(self):
        from models import User
        self.assertTrue(User.name_available("unclaimed"))

    def test_a_name_someone_holds_is_not(self):
        from models import User
        self.make("taken")
        self.assertFalse(User.name_available("taken"))

    def test_your_own_name_is_free_to_you(self):
        from models import User
        me = self.make("mine")
        self.assertTrue(User.name_available("mine", me),
                        "resaving the form without touching the name must not fail")

    def test_your_own_name_is_taken_to_everyone_else(self):
        from models import User
        self.make("mine")
        someone_else = User(id="other", name="other")
        self.assertFalse(User.name_available("mine", someone_else))

    def test_blank_is_refused(self):
        from models import User
        self.assertFalse(User.name_available(""))
        self.assertFalse(User.name_available(None))

    def test_url_unsafe_characters_are_refused(self):
        from models import URL_UNSAFE_NAME_CHARS, User
        for c in URL_UNSAFE_NAME_CHARS:
            self.assertFalse(User.name_available("ok%sno" % c),
                             "a name is a path segment, so %r cannot be in one" % c)

    def test_the_quote_characters_are_in_the_list(self):
        from models import URL_UNSAFE_NAME_CHARS
        for c in ('"', "'"):
            self.assertIn(c, URL_UNSAFE_NAME_CHARS,
                          "the page has always refused these, so the server must too")

    def test_rename_refuses_exactly_what_the_check_refuses(self):
        from models import User
        self.make("held")
        me = User(id="me", name="me")
        me.put()
        for candidate in ("held", "", "bad/name", 'quo"te'):
            self.assertEqual(User.name_available(candidate, me), me.rename(candidate),
                             "the check and the rename disagreed about %r" % candidate)
            self.assertEqual(me.name, "me", "a refused rename must not stick")

    def test_a_permitted_rename_sticks(self):
        from models import User
        me = User(id="me", name="me")
        me.put()
        self.assertTrue(me.rename("renamed"))
        self.assertEqual(User.get_by_name("renamed").key, me.key)


if __name__ == "__main__":
    unittest.main()
