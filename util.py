from __future__ import division, print_function
from math import floor
from collections import defaultdict, namedtuple
from seedbuilder.oriparse import get_areas
from enums import Variation, LogicPath
from datetime import datetime, timezone
import logging as log
import os
from time import monotonic
from zlib import crc32

try:
    from flask import request
    flask_imported = True
except ImportError:
    flask_imported = False
try: 
    from google.cloud import ndb
    ndb_imported = True
except ImportError:
    ndb_imported = False

# Naive UTC: our DateTimeProperties carry no tzinfo, and ndb rejects aware values there.
def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


VER = [4, 9, 2]
MIN_VER = [4, 9, 0]
BETA_VER = [4, 9, 2]
VERSION = "%s.%s.%s" % tuple(VER)

# 4.9.x is the 5.0 beta: numeric on the wire, "5.0 beta vN" on the page. Each
# beta build gets its own 4.9.N note; they collapse into 5.0.0 at release.
BETA_OF = [5, 0, 0] if VER[:2] == [4, 9] else None
def display_version(v):
    """What a release is called to a person. Mirrors displayVersion in
    PatchNotes.js -- a note must not be named one thing on the page and
    another in the Discord post that links to it."""
    parts = v.split(".")
    dll, rev = (".".join(parts[:3]), parts[3]) if len(parts) > 3 else (v, None)
    named = "5.0 beta v%s" % dll.split(".")[2] if dll.startswith("4.9.") else dll
    return "%s — Web Update %s" % (named, rev) if rev else named


DISPLAY_VERSION = display_version(VERSION)

# which branch's committed Assembly-CSharp.dll the dll routes hand out
DLL_BRANCH = os.environ.get("DLL_BRANCH", "master")
DLL_BETA_BRANCH = os.environ.get("DLL_BETA_BRANCH", DLL_BRANCH)
DLL_URL = "https://github.com/sparkle-preference/OriDERandomizer/raw/%s/Assembly-CSharp.dll"

# the only Jinja template: the page itself is a JS bundle under template_root
INDEX_TEMPLATE = 'index.html'

# Seed file layout, deliberately not tied to the versions above: bump it only
# when a client that reads one format cannot read the other.
SEED_FORMAT = 2

# Feature flags (env vars). ARCHIPELAGO is a kill switch, so it defaults ON.
def _flag(name, default="1"):
    return os.environ.get(name, default) not in ("", "0", "false", "False")
# off means the link routes 404 and no new AP seed rolls; an existing game's AP
# data is mode-gated and always present, so it breaks only when it needs the bridge
ARCHIPELAGO = _flag("ARCHIPELAGO")
# beta sites only: every visitor gets their own throwaway account (session
# cookie), instead of everyone sharing the one OIDC testing profile
GUEST_USERS = _flag("GUEST_USERS", "0")
# every open socket pins one gunicorn thread (Dockerfile --threads) for its
# whole lifetime. Reject new sockets past this count — with a healthy gap
# below the thread count — so they can't starve the http side of the shared
# pool; rejected clients just keep polling and re-probe on reconnect backoff.
WS_CONN_LIMIT = int(os.environ.get("WS_CONN_LIMIT", "48"))

# the orirando.com -> bf.orirando.com move. Inert until BOTH are set: browser
# traffic (GET/HEAD, non-/netcode/) on any host in REDIRECT_HOSTS 301s to
# https://CANONICAL_HOST with path+query preserved. REDIRECT_HOSTS names the
# hosts that redirect, comma-separated — bfnc.orirando.com must NEVER be in it
# (the dll's plain-http netcode dies on any redirect toward https).
# Patch note announcements. Inert until a webhook URL is set. On the first
# request after a deploy, releases newer than the last announced one get posted;
# a release's "announce" field in patchnotes.json picks who sees it —
# "all" (default) goes to both channels, "dev" to the dev channel only, "none"
# nowhere. The two markers advance independently, so a dev-only release does not
# stop the next public one reaching the main channel.
PATCHNOTES_WEBHOOK_MAIN = os.environ.get("PATCHNOTES_WEBHOOK_MAIN", "")
PATCHNOTES_WEBHOOK_DEV = os.environ.get("PATCHNOTES_WEBHOOK_DEV", "")

CANONICAL_HOST = os.environ.get("CANONICAL_HOST", "")
REDIRECT_HOSTS = [h.strip() for h in os.environ.get("REDIRECT_HOSTS", "").split(",") if h.strip()]
# the host this deployment tells players to fetch things from
SITE_HOST = CANONICAL_HOST or "orirando.com"
# what the launcher calls each non-prod server; play links carry it as endpoint=<name>
PLAY_ENDPOINTS = {"bfbeta.eiko.blue": "beta", "bfdev.eiko.blue": "dev"}

def play_endpoint():
    return PLAY_ENDPOINTS.get(CANONICAL_HOST, "")

# Perf instrumentation: stable, grep-able log lines ("NETPERF <what> ms=<dur> tag=<revision:pid> k=v ...").
# tag identifies the Cloud Run revision + worker process, to detect cross-process cache misses.
NETPERF_TAG = "%s:%s" % (os.environ.get("K_REVISION", "local"), os.getpid())

def netperf(what, t0, **kw):
    extras = " ".join("%s=%s" % (k, v) for k, v in sorted(kw.items()))
    log.info("NETPERF %s ms=%d tag=%s %s", what, int((monotonic() - t0) * 1000), NETPERF_TAG, extras)

def parse_fass(raw):
    """Forced assignments as the generator's preplaced map. Each is
    "[world.]loc:item[@owner]", joined by "|"; world defaults to 1 and an owner
    rides the value, which is how a cross-world preplacement is expressed.
    Raises ValueError on a location that isn't a number."""
    out = {}
    for fass in (raw or "").split("|"):
        if not fass:
            continue
        rawloc, _, item = fass.partition(":")
        world, _, loc = rawloc.rpartition(".")
        item, _, owner = item.partition("@")
        out[(int(world or 1), int(loc))] = "%s|%s" % (item, owner) if owner else item
    return out


def is_mw_manifest_loc(coords):
    """Multiworld slot manifests live at pseudo-locations -2..-257 in the
    owner's seed; display/tracker surfaces that resolve real coordinates
    should skip them."""
    try:
        return -257 <= int(coords) <= -2
    except (TypeError, ValueError):
        return False

def seed_sync_id(seed_field):
    """Extract the Sync id ("<gid>.<pid>") from a setSeed upload, or None.
    The client joins seed lines with commas after swapping line 1's commas to
    pipes, so the first comma-segment is the entire first line."""
    if not seed_field:
        return None
    first = seed_field.split(",", 1)[0]
    if not first.startswith("Sync"):
        return None
    return first[4:].split("|", 1)[0]

def json_default(o):
    # google-cloud-ndb wraps structured-property values in _BaseValue in place when
    # an entity is put(); a board json computed after a put in the same request
    # carries these wrappers, and caching spreads them to every viewer.
    # b_val holds the plain primitive. Used as json.dumps(default=...).
    if ndb_imported:
        from google.cloud.ndb.model import _BaseValue
        if isinstance(o, _BaseValue):
            return o.b_val
    log.warning("json_default: coercing non-serializable %s to str", type(o).__name__)
    return str(o)

def version_check(version):
    try:
        nums = [int(num) for num in version.split(".")]
        for latest, test in zip(MIN_VER, nums):
            if latest > test:
                return False
            if test > latest:
                return True
        return True
    except Exception as e:
        log.error("failed version check for version %s: %s", version, e)
        return False

# grant pairing changed in 4.2.12: an older dll against the new bridge can
# dupe self-items, so AP rooms hold a higher floor than the global MIN_VER
AP_MIN_DLL = [4, 2, 12]

def version_at_least(version, floor):
    """Dotted version string >= floor (a [major, minor, patch] list).
    Garbage reads as too old; missing segments read as zero."""
    try:
        nums = [int(num) for num in str(version).split(".")]
    except ValueError:
        return False
    for want, got in zip(floor, nums + [0] * max(0, len(floor) - len(nums))):
        if got != want:
            return got > want
    return True

def clone_entity(e, **extra_args):
    klass = e.__class__
    if ndb_imported:
        props = dict((v._code_name, v.__get__(e, klass)) for v in klass._properties.values() if
                 type(v) != ndb.ComputedProperty)
    else:
        log.error("clone_entity called but ndb was not imported??? Trying my best...........")
        props = dict((v._code_name, v.__get__(e, klass)) for v in klass._properties.values())
    props.update(extra_args)
    return klass(**props)


coord_correction_map = {
    679620: 719620,
    -4560020: -4600020,
    -520160: -560160,
    8599908: 8599904,
    2959744: 2919744,
}

PickLoc = namedtuple("PickLoc", ["coords", "name", "zone", "area", "x", "y"])

extra_PBT = [
    PickLoc(24, 'Mapstone 1', 'Mapstone', 'MS1', 0, 24),
    PickLoc(28, 'Mapstone 2', 'Mapstone', 'MS2', 0, 28),
    PickLoc(32, 'Mapstone 3', 'Mapstone', 'MS3', 0, 32),
    PickLoc(36, 'Mapstone 4', 'Mapstone', 'MS4', 0, 36),
    PickLoc(40, 'Mapstone 5', 'Mapstone', 'MS5', 0, 40),
    PickLoc(44, 'Mapstone 6', 'Mapstone', 'MS6', 0, 44),
    PickLoc(48, 'Mapstone 7', 'Mapstone', 'MS7', 0, 48),
    PickLoc(52, 'Mapstone 8', 'Mapstone', 'MS8', 0, 52),
    PickLoc(56, 'Mapstone 9', 'Mapstone', 'MS9', 0, 56),
    PickLoc(-280256, "EC", "Glades", "SunkenGladesFirstEC", -28, -256),
    PickLoc(-2399488, "EVWarmth", "Horu", "FinalEscape", -240, 512),
    PickLoc(-12320248, "Plant", "Forlorn", "ForlornEscapePlant", -1232, -248),
    PickLoc(2, "SPAWN", "Glades", "FirstPickup", 189, -210),
]

def ord_suffix(n):
    return str(n)+("th" if 4<=n%100<=20 else {1:"st",2:"nd",3:"rd"}.get(n%10, "th"))

def enums_from_strlist(enum, strlist):
    enums = []
    for elem in strlist:
        maybe_enum = enum.mk(elem)
        if maybe_enum:
            enums.append(maybe_enum)
    return enums


def int_to_bits(n, min_len=2):
    raw = [1 if digit == '1' else 0 for digit in bin(n)[2:]]
    if len(raw) < min_len:
        raw = [0] * (min_len - len(raw)) + raw
    return raw


log_2 = {1: 0, 2: 1, 4: 2, 8: 3, 16: 4, 32: 5, 64: 6, 128: 7, 256: 8, 512: 9, 1024: 10, 2048: 11, 4096: 12, 8192: 13, 16384: 14, 32768: 15, 65536: 16}

all_locs = set([2, 2999808, 5280264, -4159572, 4479832, 4559492, 919772, -3360288, 24, -8400124, 28, 32, 1599920, -6479528, 36, 40, 3359580, 2759624, 44, 4959628, 4919600, 3279920, -12320248, 1479880,
                52, 56, 3160244, 960128, 799804, -6159632, -800192, 5119584, 5719620, -6279608, -3160308, 5320824, 4479568, 9119928, -319852, 1719892, -480168, 919908, 1519708, -6079672, 2999904,
                -6799732, -11040068, 5360732, 559720, 4039612, 4439632, 1480360, -2919980, -120208, -2480280, 4319860, -7040392, -1800088, -4680068, 4599508, 2919744, 3319936, 1720000, 120164,
                -4600188, 5320328, 6999916, 3399820, 1920384, -400240, -6959592, 4319892, 2239640, 2719900, -160096, 3559792, 1759964, -5160280, 6359836, 5080496, 5359824, 1959768, 5039560, 4560564,
                -10440008, 2519668, -2240084, -10760004, -4879680, 799776, -5640092, -6080316, 6279880, 4239780, -5119796, 7599824, 5919864, -4160080, 4999892, 3359784, 4479704, -1800156, -6280316,
                -5719844, -8600356, -2160176, 5399780, -6119704, 5639752, 3439744, 7959788, 5080304, 5320488, -10120036, -7960144, -1680140, -8920328, 1839836, 2520192, 1799708, 5399808, -8720256,
                639888, 719620, 6639952, 3919624, -4600020, 5200140, 39756, 2480400, 959960, 6839792, -1680104, -8880252, 5320660, 3279644, -6719712, 48, 599844, -3600088, 8839900, 4199724, 3039472,
                -4559584, -1560272, 1600136, 4759860, 5280500, 2559800, 3119768, 6159900, 5879616, -10759968, 5280296, 3919688, -2080116, 5119900, 3199820, 2079568, -5400236, -4199936, -8240012,
                -5479592, -3200164, 8599904, -5039728, 7839588, -5159576, 4079964, -1840196, 7679852, 5400100, -7680144, -6720040, -5919556, 1880164, -3559936, -6319752, 5280404, 39804, 6399872,
                -280256, -9799980, 1280164, -1560188, -2200184, 6080608, -1919808, 4639628, 7639816, -6800032, 5160336, 3879576, 4199828, 3959588, 5119556, 5400276, -1840228, 5160864, 1040112,
                4680612, -11880100, -4440152, -3520100, 7199904, -2200148, 7559600, -10839992, 5040476, -8160268, 4319676, 5160384, 5239456, -2400212, 2599880, 3519820, -9120036, 3639880, -6119656,
                3039696, 1240020, -5159700, -4359680, -5400104, -5959772, 5439640, -8440352, 3639888, -2480208, 399844, -560160, 4359656, -4799416, 8719856, -6039640, -5479948, 5519856, 6199596,
                -4600256, -2840236, 5799932, -600244, 5360432, -1639664, -199724, -919624, -959848,  1720288,  2160192,  2640380,  3040304, -2399488, -5599400, -7200024, -7320236,  4999752, 5480952, -1])


spawn_defaults = {
    "Glades": {
        1: [3, 1, 0], # Casual
        2: [3, 1, 0], # Standard
        3: [3, 1, 0], # Expert
        4: [3, 1, 0], # Master
        5: [3, 1, 0], # Glitched / timed-level
        7: [3, 1, 0], # Insane
    },
    "Grove": {
        1: [3, 1, 1], # Casual
        2: [3, 1, 1], # Standard
        3: [3, 1, 1], # Expert
        4: [3, 1, 0], # Master
        5: [3, 1, 0], # Glitched / timed-level
        7: [3, 1, 0], # Insane
    },
    "Swamp": {
        1: [4, 2, 1], # Casual
        2: [3, 2, 1], # Standard
        3: [3, 1, 1], # Expert
        4: [3, 1, 0], # Master
        5: [3, 1, 0], # Glitched / timed-level
        7: [3, 1, 0], # Insane
    },
    "Grotto": {
        1: [4, 2, 1], # Casual
        2: [3, 2, 1], # Standard
        3: [3, 1, 0], # Expert
        4: [3, 1, 0], # Master
        5: [3, 1, 0], # Glitched / timed-level
        7: [3, 1, 0], # Insane
    },
    "Forlorn": {
        1: [5, 3, 2], # Casual
        2: [4, 2, 1], # Standard
        3: [4, 2, 1], # Expert
        4: [3, 2, 1], # Master
        5: [3, 1, 0], # Glitched / timed-level
        7: [3, 1, 0], # Insane
    },
    "Valley": {
        1: [5, 3, 2], # Casual
        2: [4, 2, 2], # Standard
        3: [4, 2, 1], # Expert
        4: [3, 2, 1], # Master
        5: [3, 1, 0], # Glitched / timed-level
        7: [3, 1, 0], # Insane
    },
    "Horu": {
        1: [5, 3, 3], # Casual
        2: [4, 2, 3], # Standard
        3: [4, 2, 2], # Expert
        4: [4, 2, 2], # Master
        5: [3, 1, 0], # Glitched / timed-level
        7: [3, 1, 0], # Insane
    },
    "Ginso": {
        1: [5, 3, 2], # Casual
        2: [4, 2, 2], # Standard
        3: [4, 2, 1], # Expert
        4: [3, 2, 1], # Master
        5: [3, 1, 0], # Glitched / timed-level
        7: [3, 1, 0], # Insane
    },
    "Sorrow": {
        1: [6, 3, 3], # Casual
        2: [5, 2, 3], # Standard
        3: [5, 2, 2], # Expert
        4: [4, 2, 2], # Master
        5: [3, 1, 0], # Glitched / timed-level
        7: [3, 1, 0], # Insane
    },
    "Blackroot": {
        1: [4, 2, 2], # Casual
        2: [4, 2, 2], # Standard
        3: [3, 1, 2], # Expert
        4: [3, 1, 2], # Master
        5: [3, 1, 0], # Glitched / timed-level
        7: [3, 1, 0], # Insane
    },
}


def bfield_checksum(bfdstrs):
    # crc32 is stable across processes/instances; hash() is randomized per interpreter
    # (PYTHONHASHSEED), which made checksums written by one Cloud Run instance
    # unmatchable by another. Note: gunicorn workers fork from one master and share
    # a seed, which is why the old version still worked single-instance.
    return crc32(",".join(str(i) for i in bfdstrs).encode())

def get_bit(bits_int, bit):
    return int_to_bits(bits_int, log_2[bit] + 1)[-(1 + log_2[bit])]

def get_taste(bits_int, bit):
    bits = int_to_bits(bits_int, log_2[bit] + 2)[-(2 + log_2[bit]):][:2]
    return 2 * bits[0] + bits[1]

def add_single(bits_int, bit, remove=False):
    if bit < 0:
        return bits_int
    if bits_int >= bit:
        if remove:
            return bits_int - bit
        if get_bit(bits_int, bit) == 1:
            return bits_int
    return bits_int + bit

def inc_stackable(bits_int, bit, remove=False):
    if bit < 0:
        return bits_int
    if remove:
        if get_taste(bits_int, bit) > 0:
            return bits_int - bit
        return bits_int
    if get_taste(bits_int, bit) > 2:
        return bits_int
    return bits_int + bit


def get(x, y):
    return x * 10000 + y

def sign(x):
    return 1 if x >= 0 else -1

def rnd(x):
    return int(floor((x) // 4.0) * 4.0)

def unpack(coord):
    y = coord % (sign(coord) * 10000)
    if y > 2000:
        y -= 10000
    elif y < -2000:
        y += 10000
    if y < 0:
        coord -= y
    x = rnd(coord // 10000)
    return x, y


def picks_by_type(extras=False):
    locs = get_areas()["locs"]

    picks_by_type = defaultdict(lambda: [])
    all_locs_unpacked = {unpack(loc): loc for loc in all_locs}
    for area, loc_info in locs.items():
        x = loc_info["x"]
        y = loc_info["y"]
        item = loc_info["item"]
        zone = loc_info["zone"]
        crd = get(rnd(int(x)), rnd(int(y)))
        if crd not in all_locs and item != "MapStone":
            secondary_match = all_locs_unpacked.get((rnd(int(x)), rnd(int(y))))
            if secondary_match:
                crd = secondary_match
            else:
                print("No secondary match found here!", crd, item, zone, area, x, y)
        line = PickLoc(crd, item, zone, area, x, y)
        picks_by_type[item[0:2]].append(line)
    if extras:
        for extra in extra_PBT:
            p_type = extra.name[0:2]
            if p_type == "Ma":
                picks_by_type["MP"].append(extra)
            elif p_type in picks_by_type.keys():
                picks_by_type[p_type].append(extra)
    return picks_by_type

def picks_by_coord(extras=False):
    pbt = picks_by_type(extras)
    pbc = {}
    for pickgroup in pbt.values():
        for pick in pickgroup:
            pbc[pick.coords] = pick
    if extras:  # dumb dumb dumb BAD
        pbc[2] = PickLoc(2, "SPAWN", "Glades", "FirstPickup", 189, -210)
    return pbc

def picks_by_type_generator():
    return {
        code: [{"loc": l, "name": n, "zone": z, "area": a, "x": int(x), "y": int(y)} for (l,n,z,a,x,y) in 
                sorted(pickups, key=lambda x: str(x.coords))] for (code, pickups) in picks_by_type(extras=True).items()}

def ap_versions():
    """Versions the Archipelago surfaces quote, read from the packaged sources."""
    # lazy: everything imports util, and archipelago/ is a package the Dockerfile can miss
    from archipelago import build_apworld
    from archipelago.yaml_emit import DATA_VERSION
    try:
        world_version = build_apworld.manifest().get("world_version", "")
    except (OSError, ValueError) as e:
        log.error("APWORLD manifest unreadable, version line will be blank: %s", e)
        world_version = ""
    return {'ap_world_version': world_version, 'ap_data_version': DATA_VERSION}

# request helpers
def template_vals(app, title, user):
    template_values = {'app': app, 'title': title, 'version': DISPLAY_VERSION, 'race_wl': whitelist_ok(), 'admin': user.is_admin() if user else False,
                       'ap_flag': ARCHIPELAGO,
                       'beta': bool(BETA_OF),
                       # play links tell the launcher which server rolled the seed
                       'endpoint': play_endpoint()
}
    if ARCHIPELAGO:
        # the sitebar's apworld link is on every page, so these are too
        template_values.update(ap_versions())
    if user:
        template_values['user'] = user.name
        template_values['theme'] = user.site_theme()
        # omitted unless the theme picks a side, so the page can follow the browser
        if user.theme_dark() is not None:
            template_values['dark'] = user.theme_dark()
        template_values['verbose'] = user.verbose
    return template_values

whitelist_secret = os.getenv("WHITELIST_SECRET")
def whitelist_ok():
    return param_val("sec") == whitelist_secret

def game_flags(params_key):
    """(flag line, is race) for a seed, or (None, False) if the seed is gone.

    A game list wants these two small values and nothing else, out of an
    entity that is mostly placements and spoilers -- inflating one per row is
    what made these pages a landmine. Params never change after generation
    (the single mutate-and-put site busts this cache on put), so the pair
    keeps, and the id for the Seed link comes off the key without a fetch."""
    from cache import Cache   # lazy: cache.py imports util, so not at module scope
    params_id = params_key.id()
    hit = Cache.get_game_flags(params_id)
    if hit:
        return hit
    params = params_key.get()
    if not params:
        return None, False
    flags = (params.flag_line(), Variation.RACE in params.variations)
    try:
        Cache.set_game_flags(params_id, *flags)
    except Exception:   # a cache write must not 500 a page it only speeds up
        log.exception("could not cache game flags for params %s", params_id)
    return flags


is_debug = "K_REVISION" not in os.environ or os.environ["K_REVISION"].startswith('dev')
def debug():
    return is_debug

path = os.path.join(os.path.dirname(__file__), 'map/dist/index.html')
template_root = os.path.join(os.path.dirname(__file__), 'map/dist/')

def param_val(f):
    if not flask_imported:
        return None
    return request.args.get(f, None)

def param_flag(f):
    return param_val(f) is not None

def param_true(f):
    # presence isn't enough where an explicit ?x=0 means off
    val = param_val(f)
    return val is not None and val.strip().lower() not in ("0", "false", "no", "off", "")

coords_in_order = [ -10120036,  -10440008,  -10759968,  -10760004,  -10839992,  -11040068,  -11880100,  -120208,  -12320248,  -1560188,  -1560272,  -160096,  
                    -1639664,  -1680104,  -1680140,  -1800088,  -1800156,  -1840196,  -1840228,  -1919808,  -199724,  -2080116,  -2160176,  -2200148,  -2200184, 
                    -2240084,  -2399488,  -2400212,  -2480208,  -2480280,  -280256,  -2840236,  -2919980,  -3160308,  -319852,  -3200164,  -3360288,  -3520100,  
                    -3559936,  -3600088,  -400240,  -4159572,  -4160080,  -4199936,  -4359680,  -4440152,  -4559584,  -4600020,  -4600188,  -4600256,  -4680068,  
                    -4799416,  -480168,  -4879680,  -5039728,  -5119796,  -5159576,  -5159700,  -5160280,  -5400104,  -5400236,  -5479592,  -5479948,  -5599400, 
                    -560160,  -5640092,  -5719844,  -5919556,  -5959772,  -600244,  -6039640,  -6079672,  -6080316,  -6119656,  -6119704,  -6159632,  -6279608,
                    -6280316,  -6319752,  -6479528,  -6719712,  -6720040,  -6799732,  -6800032,  -6959592,  -7040392,  -7200024,  -7320236,  -7680144,  -7960144,
                    -800192,  -8160268,  -8240012,  -8400124,  -8440352,  -8600356,  -8720256,  -8880252,  -8920328,  -9120036,  -919624,  -959848,  -9799980,
                    1040112,  120164,  1240020,  1280164,  1479880,  1480360,  1519708,  1599920,  1600136,  1719892,  1720000,  1720288,  1759964,  1799708,
                    1839836,  1880164,  1920384,  1959768,  2079568,  2160192,  2239640,  24,  2480400,  2519668,  2520192,  2559800,  2599880,  2640380,  2719900,
                    2759624,  28,  2919744,  2999808,  2999904,  3039472,  3039696,  3040304,  3119768,  3160244,  3199820,  32,  3279644,  3279920,  3319936,  3359580,
                    3359784,  3399820,  3439744,  3519820,  3559792,  36,  3639880,  3639888,  3879576,  3919624,  3919688,  3959588,  39756,  39804,  399844,  40,
                    4039612,  4079964,  4199724,  4199828,  4239780,  4319676,  4319860,  4319892,  4359656,  44,  4439632,  4479568,  4479704,  4479832,  4559492, 
                    4560564,  4599508,  4639628,  4680612,  4759860,  48,  4919600,  4959628,  4999752,  4999892,  5039560,  5040476,  5080304,  5080496,  5119556, 
                    5119584,  5119900,  5160336,  5160384,  5160864,  52,  5200140,  5239456,  5280264,  5280296,  5280404,  5280500,  5320328,  5320488,  5320660,  
                    5320824,  5359824,  5360432,  5360732,  5399780,  5399808,  5400100,  5400276,  5439640,  5480952,  5519856,  559720,  56,  5639752,  5719620,  
                    5799932,  5879616,  5919864,  599844,  6080608,  6159900,  6199596,  6279880,  6359836,  639888,  6399872,  6639952,  6839792,  6999916,  719620,  
                    7199904,  7559600,  7599824,  7639816,  7679852,  7839588,  7959788,  799776,  799804,  8599904,  8719856,  8839900,  9119928,  919772,  919908,  
                    959960,  960128, 
                ]

def bfields_to_coords(bfields):
    flat_bits = [b for bfield in bfields for b in int_to_bits(bfield, 32)[::-1]]
    return [ c for b,c in zip(flat_bits, coords_in_order) if b ]






def get_preset_from_paths(presets, logic_paths):
    pathset = set(logic_paths)
    for name, lps in presets.items():
        if lps == pathset:
            return name
    path_masks = {
        LogicPath.CASUAL_CORE: 1 << 0,
        LogicPath.CASUAL_DBOOST: 1 << 1,
        LogicPath.STANDARD_CORE: 1 << 2,
        LogicPath.STANDARD_DBOOST: 1 << 3,
        LogicPath.STANDARD_LURE: 1 << 4,
        LogicPath.STANDARD_ABILITIES: 1 << 5,
        LogicPath.EXPERT_CORE: 1 << 6,
        LogicPath.EXPERT_DBOOST: 1 << 7,          
        LogicPath.EXPERT_LURE: 1 << 8,
        LogicPath.EXPERT_ABILITIES: 1 << 9,
        LogicPath.DBASH: 1 << 10,
        LogicPath.MASTER_CORE: 1 << 11,
        LogicPath.MASTER_DBOOST: 1 << 12,
        LogicPath.MASTER_LURE: 1 << 13,
        LogicPath.MASTER_ABILITIES: 1 << 14,
        LogicPath.GJUMP: 1 << 15,
        LogicPath.GLITCHED: 1 << 16,
        LogicPath.TIMED_LEVEL: 1 << 17,
        LogicPath.INSANE: 1 << 18,
    }
    path_mask = 0
    for path in logic_paths:
        path_mask |= path_masks[path]
    return "Custom" + str(path_mask)

def decompose_multi_value(value):
    """Multipickup value -> [(code, id)]. "//" is a literal slash; the client's
    RandomizerAction.Decompose reads the same grammar. An odd trailing piece is
    dropped with a warning, matching the client (which throws it away and logs
    "Malformed Multipickup"): callers concatenate code+id and legacy plandos
    predate the escape."""
    parts = []
    if value == "":
        return parts

    i = 0
    part = ""
    firstPiece = None
    while i < len(value):
        c = value[i]
        if c == "/":
            if i < len(value) - 1 and value[i + 1] == "/":
                part += "/"
                i += 1
            else:
                if firstPiece is None:
                    firstPiece = part
                    part = ""
                else:
                    parts.append((firstPiece, part))
                    firstPiece = None
                    part = ""
        else:
            part += c
        i += 1
    
    if firstPiece is None:
        if part:
            log.warning("multipickup value %r has an odd number of pieces; dropping %r", value, part)
    else:
        parts.append((firstPiece, part))
    return parts
