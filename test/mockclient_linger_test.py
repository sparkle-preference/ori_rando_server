import types
import unittest

from mockclient.client import MockClient


class Quiet(MockClient):
    """The run loop with the network stubbed out; settles its one peer at tick 15."""

    def connect(self): pass
    def disconnect(self): pass
    def drain(self): pass
    def service_found_queue(self): pass

    def send_tick(self):
        if self.tick_no == 15:
            self.peers[0].settled = True


class LingerTestCase(unittest.TestCase):
    def test_a_client_outlasts_its_peers_finds(self):
        c = Quiet("http://mock", "Sync1.1,Standard|seed\n", tick_period=0)
        c.linger = 3
        c.peers = [types.SimpleNamespace(settled=False)]
        c.run()
        self.assertEqual(c.errors, [])
        self.assertGreater(c.tick_no, 15 + c.linger)

    def test_alone_it_leaves_after_its_linger(self):
        c = Quiet("http://mock", "Sync1.1,Standard|seed\n", tick_period=0)
        c.linger = 3
        c.run()
        self.assertEqual(c.errors, [])
        self.assertLess(c.tick_no, 10)


if __name__ == "__main__":
    unittest.main()
