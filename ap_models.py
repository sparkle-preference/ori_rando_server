"""Archipelago bridge state.

APLink is a game's durable record of its AP room: where to connect, each
world's slot name, and how far into each world's ReceivedItems stream the
bridge has applied (AP's index contract). Key = game id, same as Game.

APNames holds one world's scouted item names, keyed '<gid>.<world>'.

Must stay importable without main.py (no Flask), like netcode.py.
"""
import json
import logging as log
import re

from google.cloud import ndb


def ap_slot_name(world):
    """The deterministic per-world AP slot name. Shared with to_ap_yaml:
    the yaml a world hands to the AP generator and the name the bridge
    connects with must always agree."""
    return "Ori%s" % int(world)


# Reserved-slot display names ride a seed line the C# client parses as
#   line.Split('|')  ->  [coord, "MW", "<owner>,<slot>,<name>", zone]
#   value.Split(',', 3)  ->  [owner, slot, name]         (Randomizer.cs:139,
#                                                         RandomizerSwitch.cs:358)
# and then paste UNESCAPED into /found/<coords>/<kind>/<id> (CleanedId in
# RandomizerSyncManager.cs, which itself already drops '#' and truncates at
# '\'). So:
#   ','  stays -- the name is the last field and EVERY parser on both sides is
#        maxsplit-bounded (pickups.MultiworldItem, models.mw_release,
#        ap_bridge.maps_from_params, the client's Split(',', 3)); TW ids have
#        carried commas down the same path for years.
#   '|'  is fatal (shifts the zone out of the line) and goes.
#   '/ \ ? %'  break the found URL, '$ * @ #' are the message-box color
#        markers (RandomizerMW.ColorWrap; '#' also starts a URL fragment,
#        which is why the client strips it), non-ASCII is a Mono Uri gamble
#        -- all go.
_NAME_DROP = re.compile(r"[^A-Za-z0-9 ,_.'\-()!:+&]")
ITEM_NAME_MAX = 40
PLAYER_NAME_MAX = 20


def sanitize_display_name(name, limit=ITEM_NAME_MAX):
    """Wire-safe form of an Archipelago-supplied name (see _NAME_DROP).
    Dropped characters become a space, then runs collapse: AP loves names
    like "Bow/Arrows", and "Bow Arrows" beats "BowArrows"."""
    clean = _NAME_DROP.sub(" ", name or "")
    return re.sub(r"\s+", " ", clean).strip()[:limit].strip()


def ap_display_name(item, player):
    """'<item> (<player>)', the reserved-slot label the client shows as
    "Found Archipelago's <this>!". Empty when the item name doesn't survive
    sanitization, which the caller reads as "keep the placeholder"."""
    item = sanitize_display_name(item, ITEM_NAME_MAX)
    player = sanitize_display_name(player, PLAYER_NAME_MAX)
    if not item:
        return ""
    return "%s (%s)" % (item, player) if player else item


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
    # scouted/named counts per world, -1 = not reported yet (names: APNames)
    name_totals   = ndb.IntegerProperty(repeated=True)
    name_counts   = ndb.IntegerProperty(repeated=True)
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
            "names_total": list(self.name_totals),
            "names_resolved": list(self.name_counts),
            "last_error": self.last_error,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
        }


class APNames(ndb.Model):
    """One world's scouted Archipelago item names, id '<gid>.<world>'.

    Pure display data: always regenerable by rescouting, so a missing row
    just means the seed keeps its "AP Item #n" placeholders and nothing
    breaks. Its own kind rather than a field on APLink because (a) APLink is
    written on every ReceivedItems batch and every status change, and up to
    256 names per world would ride all of those puts, and (b) the K bridge
    threads scout concurrently, so a per-world key keeps them from
    contending on one entity. Compressed like SeedGenParams.spoilers.
    """
    # JSON {"<shadow slot>": "<display name>"}
    names   = ndb.TextProperty(compressed=True)
    scouted = ndb.IntegerProperty(default=0)
    updated = ndb.DateTimeProperty(auto_now=True)

    @staticmethod
    def key_id(gid, world):
        return "%s.%s" % (int(gid), int(world))

    @staticmethod
    def load(gid, world):
        """{slot: display name} for one world; {} when nothing is scouted."""
        row = APNames.get_by_id(APNames.key_id(gid, world))
        if row is None or not row.names:
            return {}
        try:
            return {int(k): v for k, v in json.loads(row.names).items()}
        except (TypeError, ValueError):
            log.warning("APNames %s holds unreadable json", APNames.key_id(gid, world))
            return {}

    @staticmethod
    def store(gid, world, names):
        APNames(id=APNames.key_id(gid, world), scouted=len(names),
                names=json.dumps({str(k): v for k, v in sorted(names.items())})).put()
