"""Enemy rando options: the page's form, the seed's //Enemies= line, and what each key may say."""
import re

KINDS = ["Fronkeys", "Frogs", "Slimes", "Banelings", "DropSlugs", "Worms", "Rhinos", "Birds",
         "Elementals", "Swarms", "Spiders", "Fish", "Sharks"]
MODES = ("zone", "vanilla")
ARENAS = ("hp", "kind")
SWITCHES = ("pools", "flyingfish", "walkers", "shootercap", "logic")

# key -> default; an absent key on the line means this
DEFAULTS = {
    "pool": KINDS, "keep": [], "hp": "zone", "dmg": "zone", "arena": "hp",
    "pools": "on", "flyingfish": "off", "walkers": "on", "shootercap": "on", "logic": "on",
}
META_PREFIX = "//Enemies="
RANGE = re.compile(r"^(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)$")

PRESETS = {
    "Standard": {},
    "Mild": {"pool": [k for k in KINDS if k not in ("Rhinos", "Elementals", "Sharks")], "keep": ["Worms"],
             "arena": "kind", "pools": "off", "walkers": "off"},
    "Chaos": {"hp": "0.5-2", "dmg": "0.5-2", "flyingfish": "on", "shootercap": "off"},
}


def mode_ok(value):
    if not isinstance(value, str):
        return False
    if value in MODES:
        return True
    m = RANGE.match(value)
    return bool(m) and 0.25 <= float(m.group(1)) <= float(m.group(2)) <= 4


def normalize(opts):
    """The options with defaults dropped, unknown keys gone, values checked; None when nothing is left."""
    out = {}
    for key, value in (opts or {}).items():
        if key in ("pool", "keep"):
            kinds = [k for k in (value.split("+") if isinstance(value, str) else list(value or [])) if k in KINDS]
            if key == "pool" and sorted(kinds) == sorted(KINDS):
                continue
            if key == "keep" and not kinds:
                continue
            out[key] = kinds
        elif key in ("hp", "dmg") and mode_ok(value) and value != DEFAULTS[key]:
            out[key] = value
        elif key == "arena" and value in ARENAS and value != DEFAULTS[key]:
            out[key] = value
        elif key in SWITCHES and value in ("on", "off") and value != DEFAULTS[key]:
            out[key] = value
    return out or None


def problem(opts):
    """Why these options can't make a seed, or None."""
    for key, name in (("hp", "health"), ("dmg", "damage")):
        value = (opts or {}).get(key)
        if value not in (None, "") and not mode_ok(value):
            return "Enemy Rando's %s range needs two numbers from 0.25 to 4, low first." % name
    opts = normalize(opts) or {}
    if "pool" in opts and not opts["pool"]:
        return "Enemy Rando needs at least one kind of enemy that may appear."
    return None


def meta_line(opts):
    """The //Enemies= line for a world, or None when every option is the default."""
    opts = normalize(opts)
    if not opts:
        return None
    parts = []
    for key in ("pool", "keep", "hp", "dmg", "arena") + SWITCHES:
        if key in opts:
            value = opts[key]
            parts.append("%s=%s" % (key, "+".join(value) if isinstance(value, list) else value))
    return META_PREFIX + ";".join(parts)


def parse_meta(line):
    """The options on an //Enemies= line, or None when it isn't one."""
    if not line.lower().startswith(META_PREFIX.lower()):
        return None
    opts = {}
    for part in line[len(META_PREFIX):].split(";"):
        key, _, value = part.partition("=")
        if key:
            opts[key.strip()] = value.strip()
    return normalize(opts) or {}


def parse_kv(text):
    """CLI form: 'pool=Frogs+Slimes;hp=0.5-2'."""
    return parse_meta(META_PREFIX + (text or ""))
