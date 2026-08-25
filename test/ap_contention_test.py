"""Concurrent writers against one entity, on a real datastore.

Everything here is untestable with stubs by construction: a double that hands
both callers the same object shows no conflict, and a transaction that never
retries proves nothing about the code that assumes it does. These tests make
real threads collide and then check the two properties the AP bridge is built
on -- tokens never repeat, and a hint is bought exactly once.
"""
import threading
import unittest

from test.ndb_base import EmulatorTestCase


class _Counter(object):
    def __init__(self):
        self.n = 0
        self._lock = threading.Lock()

    def bump(self):
        with self._lock:
            self.n += 1


def fresh(fn, *args):
    """Read past this thread's ndb context cache. The threads committed in
    their own contexts, so anything this one touched before they ran (a setUp
    put, an earlier read) is still sitting here stale."""
    from google.cloud import ndb
    ndb.get_context().clear_cache()
    return fn(*args)


def run_threaded(client, work, threads):
    """Run work() in N threads, each inside its own ndb context (contexts are
    per-thread and cannot nest). Returns the collected results; the first
    exception is re-raised so a deadlock or a retry-exhaustion is not silent."""
    results, errors = [], []
    lock = threading.Lock()
    ready = threading.Barrier(threads)

    def body():
        try:
            with client.context():
                ready.wait(timeout=30)   # widen the window every thread races into
                got = work()
            with lock:
                results.append(got)
        except Exception as e:   # noqa: BLE001 - re-raised below
            with lock:
                errors.append(e)

    pool = [threading.Thread(target=body) for _ in range(threads)]
    for t in pool:
        t.start()
    for t in pool:
        t.join(60)
    assert not any(t.is_alive() for t in pool), "threads did not finish"
    if errors:
        raise errors[0]
    return results


class DeathTokenContentionTestCase(EmulatorTestCase):
    """dl_in is a read-modify-write, so concurrent deaths are exactly the case
    where a lost update would hand two players the same token."""

    GID, WORLD, THREADS = 800, 1, 8

    def setUp(self):
        super(DeathTokenContentionTestCase, self).setUp()
        from ap_models import APLink
        APLink(id=self.GID).put()

    def test_every_token_is_unique_and_the_count_is_exact(self):
        from archipelago import ap_bridge
        from ap_models import APLink

        attempts = _Counter()
        real = APLink.with_id

        def counting_with_id(gid):
            attempts.bump()          # once per transaction ATTEMPT, retries included
            return real(gid)

        APLink.with_id = staticmethod(counting_with_id)
        try:
            tokens = run_threaded(self.ndb_client,
                                  lambda: ap_bridge._bump_death_in(self.GID, self.WORLD),
                                  self.THREADS)
        finally:
            APLink.with_id = staticmethod(real)

        self.assertEqual(sorted(tokens), list(range(1, self.THREADS + 1)),
                         "tokens must be unique and contiguous: %r" % sorted(tokens))
        self.assertEqual(fresh(APLink.with_id, self.GID).dl_in[self.WORLD - 1], self.THREADS)
        # the point of the exercise: at least one writer lost and re-ran
        self.assertGreater(attempts.n, self.THREADS,
                           "no transaction retried, so this proved nothing about "
                           "contention (attempts=%s, threads=%s)"
                           % (attempts.n, self.THREADS))


class HintClaimContentionTestCase(EmulatorTestCase):
    """The claim is a compare-and-set whose whole job is to survive K sessions,
    several gunicorn processes and a client that asks every second."""

    GID, WORLD, SLOT, THREADS = 801, 1, 7, 8

    def test_exactly_one_claimer_wins(self):
        from archipelago import ap_bridge
        won = run_threaded(
            self.ndb_client,
            lambda: ap_bridge._claim_hint(self.GID, self.WORLD, self.SLOT, 9),
            self.THREADS)
        self.assertEqual(sum(1 for w in won if w), 1,
                         "a hint costs real points: exactly one buyer, got %r" % won)

    def test_different_slots_never_block_each_other(self):
        from archipelago import ap_bridge
        from ap_models import APHints
        slots = list(range(10, 10 + self.THREADS))
        box = {"i": 0}
        lock = threading.Lock()

        def claim_next():
            with lock:
                slot = slots[box["i"]]
                box["i"] += 1
            return ap_bridge._claim_hint(self.GID, self.WORLD, slot, 9)

        won = run_threaded(self.ndb_client, claim_next, self.THREADS)
        self.assertTrue(all(won), "distinct slots share a row but must all succeed: %r" % won)
        self.assertEqual(sorted(fresh(APHints.load, self.GID, self.WORLD)), slots)


class RecvIndexContentionTestCase(EmulatorTestCase):
    """Monotone-or-nothing has to hold when the twin sessions overlap, which is
    the deploy window it was written for."""

    GID, WORLD, THREADS = 802, 1, 8

    def setUp(self):
        super(RecvIndexContentionTestCase, self).setUp()
        from ap_models import APLink
        APLink(id=self.GID).put()

    def test_the_highest_count_survives_a_stampede(self):
        from archipelago import ap_bridge
        from ap_models import APLink
        counts = [5, 40, 12, 3, 33, 7, 21, 1][:self.THREADS]
        box = {"i": 0}
        lock = threading.Lock()

        def persist_next():
            with lock:
                count = counts[box["i"]]
                box["i"] += 1
            return ap_bridge._persist_recv(self.GID, self.WORLD, count)

        run_threaded(self.ndb_client, persist_next, self.THREADS)
        self.assertEqual(fresh(APLink.with_id, self.GID).recv_index[self.WORLD - 1], max(counts),
                         "a late-committing small batch must not rewind the world")


if __name__ == "__main__":
    unittest.main()
