"""Archipelago bridge state.

APLink is a game's durable record of its AP room: where to connect, each
world's slot name, and how far into each world's ReceivedItems stream the
bridge has applied (AP's index contract). Key = game id, same as Game.

APNames holds one world's scouted Archipelago placements, keyed
'<gid>.<world>': what is in each reserved slot, who it is for, and the raw
AP ids the download-time cross-world join reads.

APHints holds one world's hint purchases, same key shape: which reveal
slots have been bought, are in flight, or were unaffordable.

Must stay importable without main.py (no Flask), like netcode.py.
"""
import json
import logging as log
import re
import time

from google.cloud import ndb

from cache import Cache


def ap_slot_name(world):
    """The deterministic per-world AP slot name. Shared with to_ap_yaml:
    the yaml a world hands to the AP generator and the name the bridge
    connects with must always agree."""
    return "Ori%s" % int(world)


def ap_slot_names(worlds, names=None):
    """Per-world slot names: the name the seed was rolled with, else OriN.
    AP rejects duplicate slots, so collisions get their world number."""
    out, seen = [], set()
    for w in range(1, int(worlds) + 1):
        raw = names[w - 1] if names and w <= len(names) else ""
        name = sanitize_display_name(raw, PLAYER_NAME_MAX) or ap_slot_name(w)
        if name.lower() in seen:
            suffix = str(w)
            name = name[:PLAYER_NAME_MAX - len(suffix)] + suffix
        seen.add(name.lower())
        out.append(name)
    return out


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
    """'<item> (<player>)', the whole-label form for clients that read only
    the four original seed fields. Empty when the item name doesn't survive
    sanitization, which the caller reads as "keep the placeholder"."""
    item = sanitize_display_name(item, ITEM_NAME_MAX)
    player = sanitize_display_name(player, PLAYER_NAME_MAX)
    if not item:
        return ""
    return "%s (%s)" % (item, player) if player else item


# field 5 and the apfrom signal are split on , ; = and |, so a name on them
# keeps none of those (matches models.Player.wire_name)
_WIRE_NAME_DROP = re.compile(r"[^A-Za-z0-9 _.'-]")


def wire_safe_name(name, limit=PLAYER_NAME_MAX):
    """Name as safe to embed in a seed field or a signal payload."""
    clean = _WIRE_NAME_DROP.sub(" ", name or "")
    return re.sub(r"\s+", " ", clean).strip()[:limit].strip()


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
    # index w-1 = DeathLinks delivered to world w. Only ever grows, and the
    # signal carries it as a token so two deaths a tick apart are two signals
    # rather than one the client already acked.
    dl_in         = ndb.IntegerProperty(repeated=True)
    # JSON list of ReceivedItems entries the bridge could not deliver (every
    # per-item slot already granted -- console sends land here). Each entry:
    # {"w": world, "i": stream index, "a": ap item id, "f": sender,
    #  "n": item name, "t": unix seconds}. The stream index makes the record
    # exactly-once across twin sessions and index-0 resends.
    dropped       = ndb.TextProperty()
    enabled       = ndb.BooleanProperty(default=False)
    status        = ndb.StringProperty(default="disconnected")
    last_error    = ndb.StringProperty()
    last_activity = ndb.DateTimeProperty(auto_now=True)

    @staticmethod
    def with_id(gid):
        return APLink.get_by_id(int(gid))

    @staticmethod
    def make(gid, worlds, names=None):
        """Fresh link for a K-world game: nothing received yet."""
        worlds = int(worlds)
        return APLink(id=int(gid),
                      slot_names=ap_slot_names(worlds, names),
                      recv_index=[0] * worlds)

    def drop_list(self):
        if not self.dropped:
            return []
        try:
            return json.loads(self.dropped)
        except ValueError:
            log.warning("APLink %s holds drop json this build can't read", self.key.id())
            return []

    def report(self):
        return {
            "enabled": self.enabled,
            "status": self.status,
            "dropped": self.drop_list(),
            "host": self.host,
            "port": self.port,
            "slots": list(self.slot_names),
            "recv_index": list(self.recv_index),
            "goal_worlds": list(self.goal_worlds),
            "names_total": list(self.name_totals),
            "names_resolved": list(self.name_counts),
            "deathlinks_in": list(self.dl_in),
            "last_error": self.last_error,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
        }


class APScout(object):
    """What the room said sits in one reserved slot of one world.

    item + who build the combined label every shipped client reads out of
    the comma field; `to` is the seed's field 5, which prefers 'P<world>' for
    a sibling world so the client can print that player's own name.
    ap_item/ap_owner are the raw AP ids the cross-world join in
    archipelago.annotate needs to see where an exported item actually landed.
    """
    __slots__ = ("item", "who", "to", "ap_item", "ap_owner")

    def __init__(self, item, who, to, ap_item, ap_owner):
        self.item, self.who, self.to = item, who, to
        self.ap_item, self.ap_owner = ap_item, ap_owner

    def label(self):
        """The one-string form clients read out of the comma field."""
        return ap_display_name(self.item, self.who)

    def __eq__(self, other):
        return isinstance(other, APScout) and self.as_json() == other.as_json()

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return "APScout(%r, %r, %r, %r, %r)" % (
            self.item, self.who, self.to, self.ap_item, self.ap_owner)

    def as_json(self):
        return {"i": self.item, "w": self.who, "t": self.to,
                "a": self.ap_item, "o": self.ap_owner}

    @staticmethod
    def from_json(blob):
        return APScout(blob["i"], blob.get("w") or "", blob.get("t") or "",
                       int(blob["a"]), int(blob["o"]))


class APNames(ndb.Model):
    """One world's scouted Archipelago placements, id '<gid>.<world>'.

    Pure display data: always regenerable by rescouting, so a missing row
    just means the seed keeps its "AP Item #n" placeholders and nothing
    breaks. Its own kind rather than a field on APLink because (a) APLink is
    written on every ReceivedItems batch and every status change, and up to
    256 entries per world would ride all of those puts, and (b) the K bridge
    threads scout concurrently, so a per-world key keeps them from
    contending on one entity. Compressed like SeedGenParams.spoilers.

    A row written by an older build stores bare label strings and no
    ap_slot; load() reports those as empty rather than guessing, and the
    bridge rewrites the row on its next connection (it rescouts every time).
    """
    # JSON {"<shadow slot>": {"i": item, "t": recipient, "a": ap item id,
    #                         "o": ap owner slot}}
    names   = ndb.TextProperty(compressed=True)
    # JSON {"<shadow slot>": manifest slot} -- the bridge's promise map,
    # written after a build; annotate bakes it into field 6 VERBATIM, so the
    # self-item draw exists in exactly one place (ap_bridge.promised_slots)
    promises = ndb.TextProperty()
    # this world's own slot number in the room: the join's "is it mine?"
    ap_slot = ndb.IntegerProperty()
    scouted = ndb.IntegerProperty(default=0)
    updated = ndb.DateTimeProperty(auto_now=True)

    @staticmethod
    def key_id(gid, world):
        return "%s.%s" % (int(gid), int(world))

    @staticmethod
    def _row_blobs(gid, world):
        """(names json, ap_slot, promises json), cached: a row only changes
        when a bridge session rescouts, but every download, spoiler and hint
        resolution reads it. The writers below bust; raw text is cached so
        the entry is backend-agnostic and parsing stays per-reader."""
        cached = Cache.get_ap_row(gid, world)
        if cached is not None:
            return cached
        row = APNames.get_by_id(APNames.key_id(gid, world))
        blobs = (row.names, row.ap_slot, row.promises) if row else (None, None, None)
        Cache.set_ap_row(gid, world, blobs)
        return blobs

    @staticmethod
    def load(gid, world):
        """-> ({shadow slot: APScout}, this world's room slot or None)."""
        names, ap_slot, _ = APNames._row_blobs(gid, world)
        if not names:
            return {}, None
        try:
            blob = json.loads(names)
            entries = {int(k): APScout.from_json(v) for k, v in blob.items()}
        except (TypeError, ValueError, KeyError, AttributeError):
            log.warning("APNames %s holds json this build can't read",
                        APNames.key_id(gid, world))
            return {}, None
        return entries, ap_slot

    @staticmethod
    def store(gid, world, entries, ap_slot=None):
        # names and promises have different writers on one row, so each
        # carries the other's field forward. Plain read-then-put (no txn: the
        # golden harness runs these against patched entity ops); a lost blob
        # in the race window is rewritten by the next promise build.
        row = APNames.get_by_id(APNames.key_id(gid, world))
        blob = {str(k): v.as_json() for k, v in sorted(entries.items())}
        APNames(id=APNames.key_id(gid, world), scouted=len(entries),
                ap_slot=ap_slot, names=json.dumps(blob),
                promises=row.promises if row else None).put()
        Cache.clear_ap_row(gid, world)

    @staticmethod
    def store_promises(gid, world, promised):
        """{shadow slot: manifest slot} onto the row, names carried forward."""
        blob = json.dumps({str(k): int(v) for k, v in sorted(promised.items())})
        row = APNames.get_by_id(APNames.key_id(gid, world))
        if row is None:
            row = APNames(id=APNames.key_id(gid, world))
        if row.promises != blob:
            if row.promises:
                # a given room only ever has one answer, so outside a room
                # retarget this line is the promise-desync alarm
                try:
                    before = len(json.loads(row.promises))
                except ValueError:
                    before = "?"
                log.info("APNames %s promises replaced (%s -> %s entries)",
                         APNames.key_id(gid, world), before, len(promised))
            row.promises = blob
            row.put()
            Cache.clear_ap_row(gid, world)

    @staticmethod
    def load_promises(gid, world):
        """{shadow slot: manifest slot}, or None when no build ever
        published -- the caller bakes no field 6 rather than guessing."""
        _, _, promises = APNames._row_blobs(gid, world)
        if not promises:
            return None
        try:
            return {int(k): int(v) for k, v in json.loads(promises).items()}
        except (TypeError, ValueError, AttributeError):
            log.warning("APNames %s holds promise json this build can't read",
                        APNames.key_id(gid, world))
            return None


# APHints entry states. PENDING is written BEFORE the room is asked, so a
# crash between the claim and the answer leaves evidence instead of a second
# purchase; DEFERRED means we did the arithmetic and the slot cannot pay yet.
HINT_PENDING, HINT_RESOLVED, HINT_DEFERRED = "p", "r", "d"


class APHints(ndb.Model):
    """One world's Archipelago hint purchases, id '<gid>.<world>'.

    A hint costs the player points they can never earn back, so this row --
    not a bridge thread's memory -- decides whether the room may be asked
    about a slot. Every gunicorn process running that world's session reads
    and claims here, which is what makes the purchase exactly-once across
    processes, reconnects and seed reloads.

    Its own kind for APNames' reasons: off APLink (written on every
    ReceivedItems batch), one key per world so K sessions never contend.
    """
    # JSON {"<slot>": {"s": state, "t": resolved text, "a": ap item id,
    #                  "u": unix seconds of the last transition}}
    hints   = ndb.TextProperty(compressed=True)
    updated = ndb.DateTimeProperty(auto_now=True)

    @staticmethod
    def key_id(gid, world):
        return "%s.%s" % (int(gid), int(world))

    @staticmethod
    def unpack(row):
        """Entity (or None) -> {slot: entry dict}. A row this build can't
        read reports empty: the worst case is one re-derivation, and the
        room's own hint list is consulted before anything is bought."""
        if row is None or not row.hints:
            return {}
        try:
            blob = json.loads(row.hints)
            return {int(k): v for k, v in blob.items() if isinstance(v, dict)}
        except (TypeError, ValueError, AttributeError):
            log.warning("APHints %s holds json this build can't read", row.key.id())
            return {}

    @staticmethod
    def load(gid, world):
        return APHints.unpack(APHints.get_by_id(APHints.key_id(gid, world)))

    @staticmethod
    def store(gid, world, entries):
        blob = {str(k): v for k, v in sorted(entries.items())}
        APHints(id=APHints.key_id(gid, world), hints=json.dumps(blob)).put()

    @staticmethod
    def entry(state, text="", ap_item=0):
        return {"s": state, "t": text, "a": int(ap_item), "u": int(time.time())}
