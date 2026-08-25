"""The AP bridge's transactional writers, against a real datastore.

These are the newest code in the repo and the least covered: every one is a
read-modify-write whose whole point is what happens when two of them race, and
a stub that returns the same entity to both callers cannot show that. Here the
transaction is real, so a losing writer actually retries against fresh state.
"""
import json
import time
import unittest

from test.ndb_base import EmulatorTestCase


class APEmulatorTestCase(EmulatorTestCase):
    """Shared fixture: one APLink for game 700."""

    GID = 700

    def link(self, **kw):
        from ap_models import APLink
        row = APLink(id=self.GID, **kw)
        row.put()
        return row

    def reload(self):
        from ap_models import APLink
        return APLink.with_id(self.GID)


class RecvIndexTestCase(APEmulatorTestCase):
    """recv_index is monotone per world: a twin session replaying an older
    batch must never walk a world's progress backwards."""

    def test_a_higher_count_advances(self):
        from archipelago import ap_bridge
        self.link(recv_index=[3, 0])
        ap_bridge._persist_recv(self.GID, 1, 9)
        self.assertEqual(self.reload().recv_index, [9, 0])

    def test_a_stale_twin_cannot_rewind(self):
        from archipelago import ap_bridge
        self.link(recv_index=[9, 0])
        ap_bridge._persist_recv(self.GID, 1, 4)
        self.assertEqual(self.reload().recv_index, [9, 0], "the smaller count must lose")

    def test_a_late_world_pads(self):
        from archipelago import ap_bridge
        self.link(recv_index=[2])
        ap_bridge._persist_recv(self.GID, 3, 5)
        self.assertEqual(self.reload().recv_index, [2, 0, 5])

    def test_no_link_is_survivable(self):
        from archipelago import ap_bridge
        ap_bridge._persist_recv(self.GID, 1, 5)   # must not raise
        self.assertIsNone(self.reload())


class DropListTestCase(APEmulatorTestCase):
    """A dropped item is recorded exactly once per stream position, and only
    the first record returns True -- that return is what tells the player."""

    def entry(self, i, world=1):
        return {"w": world, "i": i, "a": 55, "f": "someone", "n": "Bash", "t": 1}

    def test_first_record_wins_and_reports(self):
        from archipelago import ap_bridge
        self.link()
        self.assertTrue(ap_bridge._persist_drop(self.GID, 1, self.entry(4)))
        self.assertEqual(len(self.reload().drop_list()), 1)

    def test_a_resend_of_the_same_position_is_silent(self):
        from archipelago import ap_bridge
        self.link()
        ap_bridge._persist_drop(self.GID, 1, self.entry(4))
        self.assertFalse(ap_bridge._persist_drop(self.GID, 1, self.entry(4)),
                         "index-0 resends and twin sessions re-drop the same position")
        self.assertEqual(len(self.reload().drop_list()), 1)

    def test_the_same_index_in_another_world_is_its_own_drop(self):
        from archipelago import ap_bridge
        self.link()
        ap_bridge._persist_drop(self.GID, 1, self.entry(4))
        self.assertTrue(ap_bridge._persist_drop(self.GID, 2, self.entry(4, world=2)))
        self.assertEqual(len(self.reload().drop_list()), 2)

    def test_the_cap_holds(self):
        from archipelago import ap_bridge
        self.link(dropped=json.dumps([self.entry(i) for i in range(ap_bridge.DROPPED_CAP)]))
        self.assertFalse(ap_bridge._persist_drop(self.GID, 1, self.entry(9999)))
        self.assertEqual(len(self.reload().drop_list()), ap_bridge.DROPPED_CAP)


class GoalAndStatusTestCase(APEmulatorTestCase):

    def test_a_goal_world_is_recorded_once(self):
        from archipelago import ap_bridge
        self.link()
        ap_bridge._persist_goal(self.GID, 2)
        ap_bridge._persist_goal(self.GID, 2)
        self.assertEqual(self.reload().goal_worlds, [2])

    def test_goals_accumulate_across_worlds(self):
        from archipelago import ap_bridge
        self.link()
        for w in (3, 1, 2):
            ap_bridge._persist_goal(self.GID, w)
        self.assertEqual(sorted(self.reload().goal_worlds), [1, 2, 3])

    def test_status_writes_and_dedupes(self):
        from archipelago import ap_bridge
        self.link(status="disconnected")
        ap_bridge._persist_status(self.GID, "connected", None)
        self.assertEqual(self.reload().status, "connected")
        before = self.reload().last_activity
        ap_bridge._persist_status(self.GID, "connected", None)
        self.assertEqual(self.reload().last_activity, before,
                         "a no-op status must not touch the row")

    def test_an_error_is_persisted_with_its_status(self):
        from archipelago import ap_bridge
        self.link(status="connected")
        ap_bridge._persist_status(self.GID, "error", "room said no")
        row = self.reload()
        self.assertEqual((row.status, row.last_error), ("error", "room said no"))


class DeathLinkTokenTestCase(APEmulatorTestCase):
    """The token has to keep climbing: a restart that reissued one the client
    already acked would look like a death the client should ignore."""

    def test_tokens_climb_per_world(self):
        from archipelago import ap_bridge
        self.link()
        self.assertEqual(ap_bridge._bump_death_in(self.GID, 2), 1)
        self.assertEqual(ap_bridge._bump_death_in(self.GID, 2), 2)
        self.assertEqual(ap_bridge._bump_death_in(self.GID, 1), 1, "worlds count apart")
        self.assertEqual(self.reload().dl_in, [1, 2])

    def test_a_padded_world_starts_at_one(self):
        from archipelago import ap_bridge
        self.link(dl_in=[4])
        self.assertEqual(ap_bridge._bump_death_in(self.GID, 3), 1)
        self.assertEqual(self.reload().dl_in, [4, -1, 1],
                         "padding is -1: a real 0 means a world with none")


class NameCountsTestCase(APEmulatorTestCase):

    def test_counts_land_at_the_right_world(self):
        from archipelago import ap_bridge
        self.link()
        ap_bridge._persist_name_counts(self.GID, 2, 30, 12)
        row = self.reload()
        self.assertEqual((row.name_totals, row.name_counts), ([-1, 30], [-1, 12]))

    def test_an_unchanged_write_is_a_no_op(self):
        from archipelago import ap_bridge
        self.link()
        ap_bridge._persist_name_counts(self.GID, 1, 30, 12)
        before = self.reload().last_activity
        ap_bridge._persist_name_counts(self.GID, 1, 30, 12)
        self.assertEqual(self.reload().last_activity, before)


class HintClaimTestCase(EmulatorTestCase):
    """A hint costs points the player cannot earn back, so the claim is the
    thing that must be exactly-once across processes and reconnects."""

    GID, WORLD, SLOT = 701, 1, 42

    def state(self):
        from ap_models import APHints
        return (APHints.load(self.GID, self.WORLD).get(self.SLOT) or {}).get("s")

    def test_the_first_claim_wins_and_the_second_loses(self):
        from archipelago import ap_bridge
        self.assertTrue(ap_bridge._claim_hint(self.GID, self.WORLD, self.SLOT, 9))
        self.assertFalse(ap_bridge._claim_hint(self.GID, self.WORLD, self.SLOT, 9),
                         "a 1 Hz client that never stops asking must not buy twice")

    def test_a_resolved_slot_is_never_reclaimed(self):
        from archipelago import ap_bridge
        from archipelago.ap_bridge import HINT_RESOLVED
        ap_bridge._claim_hint(self.GID, self.WORLD, self.SLOT, 9)
        ap_bridge._persist_hint(self.GID, self.WORLD, self.SLOT, HINT_RESOLVED, text="Bash")
        self.assertFalse(ap_bridge._claim_hint(self.GID, self.WORLD, self.SLOT, 9,
                                               stale_ok=True))

    def test_a_stale_pending_can_be_reclaimed_only_when_asked(self):
        from ap_models import APHints
        from archipelago import ap_bridge
        from archipelago.ap_bridge import HINT_CLAIM_TTL, HINT_PENDING
        stale = APHints.entry(HINT_PENDING, ap_item=9)
        stale["u"] = int(time.time() - HINT_CLAIM_TTL - 60)
        APHints.store(self.GID, self.WORLD, {self.SLOT: stale})
        self.assertFalse(ap_bridge._claim_hint(self.GID, self.WORLD, self.SLOT, 9),
                         "a multi-copy item must never retry blind")
        self.assertTrue(ap_bridge._claim_hint(self.GID, self.WORLD, self.SLOT, 9,
                                              stale_ok=True))

    def test_resolved_is_sticky_against_a_later_deferral(self):
        from archipelago import ap_bridge
        from archipelago.ap_bridge import HINT_DEFERRED, HINT_RESOLVED
        ap_bridge._persist_hint(self.GID, self.WORLD, self.SLOT, HINT_RESOLVED, text="Bash")
        ap_bridge._persist_hint(self.GID, self.WORLD, self.SLOT, HINT_DEFERRED)
        self.assertEqual(self.state(), HINT_RESOLVED,
                         "a reconnect must not un-answer a slot")

    def test_worlds_keep_their_own_rows(self):
        from archipelago import ap_bridge
        from ap_models import APHints
        ap_bridge._claim_hint(self.GID, 1, self.SLOT, 9)
        self.assertTrue(ap_bridge._claim_hint(self.GID, 2, self.SLOT, 9),
                        "one key per world is what keeps K sessions from contending")
        self.assertEqual(APHints.load(self.GID, 2).keys(), {self.SLOT})


if __name__ == "__main__":
    unittest.main()
