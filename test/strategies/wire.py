"""Strategies for the wire-format properties: pickups, multipickup pieces, seed params, fass rows, logic lines."""
from hypothesis import strategies as st

from archipelago.convert import EXPORTABLE_CATEGORIES
from enums import KeyMode, LogicPath, PathDifficulty, Variation
from pickups import Event, Pickup, Skill, Teleporter, Upgrade
from seedbuilder import oriparse

CODES = [cls.code for cls in Pickup.subclasses()]
code = st.sampled_from(CODES)


def _chars(exclude=""):
    return st.characters(exclude_categories=("Cs",), exclude_characters=exclude)


any_text = st.text(_chars(), max_size=12)
# one field of a seed line
line_text = st.text(_chars("|\n\r"), max_size=12)
# the characters multipickup values and owner tags treat specially
slashy_text = st.text(st.sampled_from("ab/ @SH1,|"), max_size=12)
at_text = st.text(st.sampled_from("SK0@12²١ a"), max_size=8)
# text ending in an @ and digits, ASCII or not
owner_tagged = st.builds("{}@{}".format, at_text, st.text(st.sampled_from("²12١"), min_size=1, max_size=2))


@st.composite
def client_text(draw):
    """Words joined by the characters line 1's flags use, one in ten also holding one the client splits on."""
    words = draw(st.lists(st.text(_chars("|,\n\r+=/@ ;"), max_size=4), min_size=1, max_size=3))
    text = words[0] + "".join(draw(st.sampled_from("+=/@ ;")) + w for w in words[1:])
    if draw(st.integers(0, 9)) == 9:
        at = draw(st.integers(0, len(text)))
        text = text[:at] + draw(st.sampled_from("|,\n\r")) + text[at:]
    return text


warp_id = st.builds("Warp to {},{},{},{}".format, st.sampled_from(["Grove", "Stomp Tree Roof", "Swamp Swim"]),
                    st.integers(-2000, 2000), st.integers(-2000, 2000),
                    st.sampled_from(["GinsoEscape", "SwampWaterWarp"]))
real_pickup = st.one_of(
    st.tuples(st.just("SK"), st.sampled_from(sorted(Skill.names)).map(str)),
    st.tuples(st.just("EV"), st.sampled_from(sorted(Event.names)).map(str)),
    st.tuples(st.just("TP"), st.sampled_from(sorted(Teleporter.bits))),
    st.tuples(st.just("RB"), st.sampled_from(sorted(Upgrade.names)).map(str)),
    st.tuples(st.sampled_from(["HC", "EC", "AC", "KS", "MS"]), st.just("1")),
    st.tuples(st.just("EX"), st.integers(1, 500).map(str)),
    st.tuples(st.just("TW"), warp_id),
    st.tuples(st.just("SH"), line_text),
)

piece = st.tuples(code, st.one_of(slashy_text, line_text))
pieces = st.lists(piece, max_size=6)
# text a multipickup value might hold, stray pieces and bare "SHtext" tails among it
raw_multi = st.one_of(slashy_text, st.text(st.sampled_from("SHK0/"), max_size=14))

versions = st.lists(st.integers(0, 30), min_size=1, max_size=5)
# a dll version, maybe with a site revision: 4.9.x is the 5.0 beta
release = st.builds(lambda dll, rev: ".".join(map(str, dll + rev)),
                    st.tuples(st.sampled_from([4, 5]), st.sampled_from([0, 8, 9]), st.integers(0, 20)).map(list),
                    st.lists(st.integers(0, 9), max_size=2))

SHARE_NAMES = ["Skills", "World Events", "Teleporters", "Upgrades", "Misc"]
ZONES = ["Glades", "Grove", "Swamp", "Grotto", "Forlorn", "Valley", "Horu", "Ginso", "Sorrow", "Blackroot", "Random"]
VARIATIONS = [v.value for v in Variation]
FASS_ITEMS = ["SK|0", "SK|3", "HC|1", "EV|1", "TP|Grove", "RB|6", "EX|15", "MU|SK/0/HC/1", "MU|EX/1/SHhi", "SH|hello"]
FASS_LOCS = ["919772", "-3160308", "5480952", "2"]

paths = st.sets(st.sampled_from([p.value for p in LogicPath])).map(lambda s: sorted(s | {"casual-core"}))
pool = st.dictionaries(st.sampled_from(["HC|1", "EC|1", "RB|6", "MU|EX/1/SHhi", "WP|*", "TP|Grove"]),
                       st.lists(st.integers(0, 20), min_size=1, max_size=2), max_size=4)
enemy_opts = st.dictionaries(st.sampled_from(["keepFamilies", "bashable", "shooters"]), st.booleans(), max_size=2)


def fass_row(players):
    return st.fixed_dictionaries({"loc": st.sampled_from(FASS_LOCS), "item": st.sampled_from(FASS_ITEMS)},
                                 optional={"world": st.integers(1, players), "owner": st.integers(1, players)})


# a preset's row: the world whose blob holds it is its holder and owner
world_fass_row = st.fixed_dictionaries({"loc": st.sampled_from(FASS_LOCS), "item": st.sampled_from(FASS_ITEMS)})


def world_blob():
    """One world's overrides, as a preset blob carries them."""
    text = client_text()
    return st.fixed_dictionaries({}, optional={
        "paths": paths,
        "pathDiff": st.sampled_from([d.value for d in PathDifficulty]),
        "keyMode": st.sampled_from([k.value for k in KeyMode]),
        "variations": st.lists(st.sampled_from(VARIATIONS), unique=True, max_size=4),
        "expPool": st.integers(0, 20000),
        "fragCount": st.integers(1, 60),
        "fragReq": st.integers(1, 60),
        "relicCount": st.integers(1, 11),
        "spawn": st.sampled_from(ZONES),
        "spawnHCs": st.integers(1, 12),
        "itemPool": pool,
        "selectedPool": st.one_of(st.sampled_from(["Standard", "Hard", "Custom"]), text),
        "senseData": st.one_of(st.none(), text),
        "enemyOpts": enemy_opts,
        "fass": st.lists(world_fass_row, min_size=1, max_size=2),
    })


@st.composite
def page_json(draw):
    """What the seedgen page posts to /generator/build."""
    text = client_text()
    players = draw(st.integers(1, 3))
    mode = draw(st.sampled_from(["Multiworld", "Co-op", "Race"])) if players > 1 else "Race"
    ap = draw(st.booleans())
    j = {
        "seed": draw(text.filter(bool)),
        "players": players,
        "paths": draw(paths),
        "variations": draw(st.lists(st.sampled_from(VARIATIONS), unique=True, max_size=5)),
        "keyMode": draw(st.sampled_from([k.value for k in KeyMode])),
        "pathDiff": draw(st.sampled_from([d.value for d in PathDifficulty])),
        "expPool": draw(st.integers(0, 20000)),
        "fillAlg": draw(st.sampled_from(["Balanced", "Classic"])),
        "tracking": draw(st.booleans()),
        "fragCount": draw(st.integers(1, 60)),
        "fragReq": draw(st.integers(1, 60)),
        "relicCount": draw(st.integers(1, 11)),
        "cellFreq": draw(st.integers(1, 512)),
        "antiBkBias": draw(st.floats(0, 1)),
        "coopGameMode": mode,
        "coopGenMode": "Cloned Seeds",
        "syncShared": draw(st.lists(st.sampled_from(SHARE_NAMES), unique=True, max_size=3)),
        "dedupShared": draw(st.booleans()),
        "senseData": draw(st.one_of(st.none(), text)),
        "itemPool": draw(pool),
        "selectedPool": draw(st.one_of(st.sampled_from(["Standard", "Hard", "Bonus Lite", "Custom"]), text)),
        "fass": draw(st.lists(fass_row(players), max_size=3)),
        "spawn": draw(st.sampled_from(ZONES)),
        "spawnECs": draw(st.integers(0, 15)),
        "spawnHCs": draw(st.integers(1, 12)),
        "spawnSKs": draw(st.integers(0, 3)),
        "spawnWeights": draw(st.lists(st.floats(0, 5), max_size=3)),
        "verboseSpoiler": draw(st.booleans()),
        "bingoLines": draw(st.integers(1, 12)),
        "bingoDiff": draw(st.sampled_from(["easy", "normal", "hard"])),
        "bingoGoal": draw(st.sampled_from(["bingos", "squares"])),
        "bingoSquares": draw(st.integers(1, 25)),
        "bingoMeta": draw(st.booleans()),
        "bingoDisc": draw(st.integers(0, 6)),
        "enemyOpts": draw(enemy_opts),
        "playerNames": draw(st.lists(st.text(max_size=6), max_size=players)),
        "worldSettings": draw(st.lists(st.one_of(st.none(), world_blob()), max_size=players)),
    }
    if ap:
        j.update(apMode=True, apExport=draw(st.lists(st.sampled_from(EXPORTABLE_CATEGORIES), unique=True, max_size=3)),
                 apDeathLink=draw(st.booleans()), apDeathsPerLink=draw(st.integers(1, 5)))
    return j


@st.composite
def fass_rows(draw):
    """(worlds, [(world or None, loc, item, owner or None)]) for a ?fass= string."""
    n = draw(st.integers(1, 6))
    item = st.one_of(real_pickup.map("".join), line_text, at_text, owner_tagged)
    rows = draw(st.lists(st.tuples(st.one_of(st.none(), st.integers(1, n)),
                                   st.one_of(st.just(2), st.integers(-10**7, 10**7)), item,
                                   st.one_of(st.none(), st.integers(1, n))), max_size=6))
    # an untagged item can't end in what reads as an owner tag
    return n, [(w, l, i, o) for w, l, i, o in rows if o is not None or not _reads_as_owned(i, n)]


def _reads_as_owned(item, worlds):
    head, at, tail = item.rpartition("@")
    return bool(at) and tail.isdecimal() and 1 <= int(tail) <= worlds


def render_fass(rows, empty_segments=()):
    """rows as "[world.]loc:item[@owner]|...", with an empty segment before each index in empty_segments."""
    segs = ["%s%d:%s%s" % ("" if w is None else "%d." % w, l, i, "" if o is None else "@%d" % o) for w, l, i, o in rows]
    for at in sorted(empty_segments, reverse=True):
        segs.insert(min(at, len(segs)), "")
    return "|".join(segs)


PLAIN_REQS = [r for r in oriparse._REQS if r not in ("Health", "Ability")]
COUNTED_REQS = ["Energy", "Keystone"]


@st.composite
def logic_line(draw):
    """One logic path's tokens: a difficulty, plain requirements, at most one Health= and one Ability=."""
    plain = draw(st.lists(st.one_of(st.sampled_from(PLAIN_REQS),
                                    st.builds("{}={}".format, st.sampled_from(COUNTED_REQS), st.integers(1, 9))),
                          unique_by=lambda t: t.partition("=")[0], max_size=4))
    counted = draw(st.lists(st.one_of(st.builds("Health={}".format, st.integers(1, 9)),
                                      st.builds("Ability={}".format, st.integers(1, 12))),
                            unique_by=lambda t: t.partition("=")[0], max_size=2))
    # one line in ten has a count with no "="
    bare = {18: ["Health"], 19: ["Ability"]}.get(draw(st.integers(0, 19)), [])
    return [draw(st.sampled_from(oriparse._DIFFICULTIES))] + draw(st.permutations(plain + counted + bare))
