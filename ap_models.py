"""Archipelago bridge state.

APLink: a game's AP room, slot names and per-world progress, keyed by game id.
APNames: one world's scouted placements; APHints: one world's hint purchases.
Both keyed '<gid>.<world>'. Importable without main.py, like netcode.py.
"""
import json
import logging as log
import re
import time

from google.cloud import ndb

from cache import Cache


def ap_slot_name(world):
    """Default per-world AP slot name; the yaml and the bridge must agree on it."""
    return "Ori%s" % int(world)


def ap_slot_names(worlds, names=None):
    """Per-world slot names as AP's Generate keeps them: the rolled name (else OriN),
    at most 16 chars, unique ignoring case; a collision takes its world number."""
    worlds = int(worlds)
    out, seen = [], set()
    for w in range(1, worlds + 1):
        raw = names[w - 1] if names and w <= len(names) else ""
        name = sanitize_display_name(raw, AP_SLOT_NAME_MAX)
        if not name or name == "Archipelago":
            name = ap_slot_name(w)
        base, n = name, w
        while name.lower() in seen:
            suffix = str(n)
            name = base[:AP_SLOT_NAME_MAX - len(suffix)] + suffix
            n += worlds
        seen.add(name.lower())
        out.append(name)
    return out


# names ride '|'-split seed lines and paste unescaped into the client's /found/ URL: drop '|',
# URL breakers, color markers ($*@#) and non-ASCII. ',' stays: every parser is maxsplit-bounded.
_NAME_DROP = re.compile(r"[^A-Za-z0-9 ,_.'\-()!:+&]")
ITEM_NAME_MAX = 40
PLAYER_NAME_MAX = 20
AP_SLOT_NAME_MAX = 16    # Archipelago's Generate.handle_name truncates to this


def sanitize_display_name(name, limit=ITEM_NAME_MAX):
    """Wire-safe form of an AP-supplied name: dropped characters become spaces,
    then runs collapse."""
    clean = _NAME_DROP.sub(" ", name or "")
    return re.sub(r"\s+", " ", clean).strip()[:limit].strip()


def ap_display_name(item, player):
    """'<item> (<player>)' for clients that read only four seed fields; "" when
    the item name sanitizes away (keep the placeholder)."""
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
    # index w-1 = DeathLinks delivered to world w; only grows, and is the signal's token
    dl_in         = ndb.IntegerProperty(repeated=True)
    # JSON list of undeliverable ReceivedItems, unique per (w, i):
    # {"w": world, "i": stream index, "a": ap item id, "f": sender, "n": name, "t": unix secs}
    dropped       = ndb.TextProperty()
    enabled       = ndb.BooleanProperty(default=False)
    status        = ndb.StringProperty(default="disconnected")
    last_error    = ndb.StringProperty()
    last_activity = ndb.DateTimeProperty(auto_now=True)

    @staticmethod
    def with_id(gid):
        return APLink.get_by_id(int(gid))

    def _post_put_hook(self, future):
        # inside a txn this fires pre-commit; ap_bridge._busts_report re-busts after.
        # Swallowed: a raising done-callback would poison the put future.
        try:
            Cache.clear_aplink_report(self.key.id())
        except Exception:
            pass

    @classmethod
    def _post_delete_hook(cls, key, future):
        try:
            Cache.clear_aplink_report(key.id())
        except Exception:
            pass

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
    """What the room said sits in one reserved slot: item + who (the comma-field
    label), to (field 5), and the raw AP ids annotate's cross-world join reads."""
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
    """One world's scouted placements, id '<gid>.<world>'. Display data the bridge
    rewrites every connection; a missing or unreadable row loads as empty."""
    # JSON {"<shadow slot>": {"i": item, "t": recipient, "a": ap item id,
    #                         "o": ap owner slot}}
    names   = ndb.TextProperty(compressed=True)
    # JSON {"<shadow slot>": manifest slot}: the bridge's promise map, baked into field 6 verbatim
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
        """(names json, ap_slot, promises json), cached as raw text; the writers below bust."""
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
        # each writer carries the other's field forward. No txn (the golden harness patches
        # entity ops); a promise blob lost to the race is rewritten by the next build.
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


# p: claimed before the room is asked; r: answered; d: unaffordable; o: for sale;
# q: buy pressed on the site, the only state a session may spend on (its claim makes it p)
HINT_PENDING, HINT_RESOLVED, HINT_DEFERRED = "p", "r", "d"
HINT_OFFERED, HINT_REQUESTED = "o", "q"


class APHints(ndb.Model):
    """One world's hint purchases, id '<gid>.<world>'. Every session claims here,
    which makes a purchase exactly-once across processes and reconnects."""
    # JSON {"<slot>": {"s": state, "t": resolved text, "a": ap item id,
    #                  "k": "<code>|<id>", "u": unix seconds of the transition}}
    hints   = ndb.TextProperty(compressed=True)
    updated = ndb.DateTimeProperty(auto_now=True)
    # what the room last said this world can spend, and what one hint costs.
    # Here so the seed page can price its button with no session in the loop.
    points  = ndb.IntegerProperty(default=0)
    cost    = ndb.IntegerProperty(default=0)

    @staticmethod
    def key_id(gid, world):
        return "%s.%s" % (int(gid), int(world))

    @staticmethod
    def unpack(row):
        """Entity (or None) -> {slot: entry dict}; an unreadable row reports empty."""
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
    def store(gid, world, entries, row=None, points=None, cost=None):
        """A put rebuilds the whole entity, so the price has to be carried
        across every write that is not about the price."""
        key_id = APHints.key_id(gid, world)
        if points is None or cost is None:
            if row is None:
                row = APHints.get_by_id(key_id)
            points = row.points if points is None and row else (points or 0)
            cost = row.cost if cost is None and row else (cost or 0)
        blob = {str(k): v for k, v in sorted(entries.items())}
        APHints(id=key_id, hints=json.dumps(blob),
                points=int(points), cost=int(cost)).put()

    @staticmethod
    @ndb.transactional(retries=5)
    def request(gid, world, slot):
        """Offered -> requested, which lets a session spend points. False when the
        slot was not for sale."""
        key_id = APHints.key_id(gid, world)
        row = APHints.get_by_id(key_id)
        entries = APHints.unpack(row)
        cur = entries.get(int(slot)) or {}
        if cur.get("s") != HINT_OFFERED:
            return False
        entries[int(slot)] = dict(cur, s=HINT_REQUESTED, u=int(time.time()))
        APHints.store(gid, world, entries, row=row)
        return True

    @staticmethod
    def price(gid, world):
        """(points, cost) as the room last reported them, 0 before it has."""
        row = APHints.get_by_id(APHints.key_id(gid, world))
        return (row.points, row.cost) if row else (0, 0)

    @staticmethod
    def entry(state, text="", ap_item=0, key=""):
        return {"s": state, "t": text, "a": int(ap_item), "k": key,
                "u": int(time.time())}
