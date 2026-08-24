"""The wire contract as the shipped clients read it. Field indices are load-bearing;
they mirror golden_wire_test.py and must never drift from it."""
from urllib.parse import parse_qs

TICK_SKILLS, TICK_EVENTS, TICK_TELEPORTERS, TICK_UPGRADES, TICK_HINTS, TICK_SIGNALS = range(6)


class TickBody(object):
    """One parsed tick response, split the way RandomizerSyncManager.CheckPickups does."""

    def __init__(self, body):
        self.raw = body
        f = body.split(",")
        self.fields = f
        self.skills = int(f[TICK_SKILLS])
        self.events = int(f[TICK_EVENTS])
        self.teleporters = int(f[TICK_TELEPORTERS])
        self.upgrades = dict(part.split("x", 1) for part in f[TICK_UPGRADES].split(";") if part)
        self.hints = dict(part.split(":", 1) for part in f[TICK_HINTS].split(";") if part)
        # the client gates on array.Length > 5; index 5 only exists when signals pend
        self.signals = f[TICK_SIGNALS].split("|") if len(f) > TICK_SIGNALS and f[TICK_SIGNALS] else []
        # multiworld appends: [6] slot bitfields, [7] player names ("pid.name;...")
        self.slots = f[6] if len(f) > 6 else None
        self.names = dict(p.split(".", 1) for p in f[7].split(";") if p) if len(f) > 7 else {}


def frame(kind, body=""):
    return "%s:%s" % (kind, body)


def parse_frame(text):
    kind, _, body = text.partition(":")
    return kind, body


def form_body(pairs):
    """Form-encode the way the dll's NameValueCollection does (no percent games needed
    for the fields we send; values are ints and simple strings)."""
    from urllib.parse import urlencode
    return urlencode(pairs)


def parse_form(body):
    return {k: v[0] for k, v in parse_qs(body, keep_blank_values=True).items()}
