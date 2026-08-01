"""Archipelago bridge state.

APLink is a game's durable record of its AP room: where to connect, each
world's slot name, and how far into each world's ReceivedItems stream the
bridge has applied (AP's index contract). Key = game id, same as Game.

Must stay importable without main.py (no Flask), like netcode.py.
"""
from google.cloud import ndb


def ap_slot_name(world):
    """The deterministic per-world AP slot name. Shared with to_ap_yaml:
    the yaml a world hands to the AP generator and the name the bridge
    connects with must always agree."""
    return "Ori%s" % int(world)


class APLink(ndb.Model):
    # id = game id
    host          = ndb.StringProperty()
    port          = ndb.IntegerProperty()
    password      = ndb.StringProperty()
    # index w-1 = world w's AP slot name
    slot_names    = ndb.StringProperty(repeated=True)
    # index w-1 = AP items already applied to world w (the next expected
    # ReceivedItems index)
    recv_index    = ndb.IntegerProperty(repeated=True)
    # worlds that completed (netcode complete path); the bridge owes each a
    # StatusUpdate{goal}, resent per connection (idempotent room-side)
    goal_worlds   = ndb.IntegerProperty(repeated=True)
    enabled       = ndb.BooleanProperty(default=False)
    status        = ndb.StringProperty(default="disconnected")
    last_error    = ndb.StringProperty()
    last_activity = ndb.DateTimeProperty(auto_now=True)

    @staticmethod
    def with_id(gid):
        return APLink.get_by_id(int(gid))

    @staticmethod
    def make(gid, worlds):
        """Fresh link for a K-world game: nothing received yet."""
        worlds = int(worlds)
        return APLink(id=int(gid),
                      slot_names=[ap_slot_name(w) for w in range(1, worlds + 1)],
                      recv_index=[0] * worlds)

    def report(self):
        return {
            "enabled": self.enabled,
            "status": self.status,
            "host": self.host,
            "port": self.port,
            "slots": list(self.slot_names),
            "recv_index": list(self.recv_index),
            "goal_worlds": list(self.goal_worlds),
            "last_error": self.last_error,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
        }
