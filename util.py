from math import floor
from collections import defaultdict, namedtuple
from seedbuilder.oriparse import get_areas
import logging as log
import os

VER = [3, 4, 3]
MIN_VER = [3, 4, 1]

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
    PickLoc(-1680104, "EX100", "Grove", "UnsafeSpiritTree100Ex", -168, -104),
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

def bits_to_int(n):
    return int("".join([str(b) for b in n]), 2)

def rm_none(itr):
    return [elem for elem in itr if elem is not None]


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
    return int(floor((x) / 4.0) * 4.0)

def unpack(coord):
    y = coord % (sign(coord) * 10000)
    if y > 2000:
        y -= 10000
    elif y < -2000:
        y += 10000
    if y < 0:
        coord -= y
    x = rnd(coord / 10000)
    return x, y

def is_int(s):
    try:
        int(s)
        return True
    except ValueError:
        return False


def picks_by_type(extras=False):
    locs = get_areas()["locs"]

    picks_by_type = defaultdict(lambda: [])
    all_locs_unpacked = {unpack(loc): loc for loc in all_locs}
    for area, loc_info in locs.iteritems():
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
                print "No secondary match found here!", crd, item, zone, area, x, y
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
    return pbc

def picks_by_type_generator():
    lines = "{\n"
    pbt = picks_by_type(extras=True)
    for key in sorted(pbt.keys()):
        lines += '"%s": [\n' % key
        for item in sorted(pbt[key], key=lambda x: str(x.coords)):
            lines += """\t{"loc": %s, "name": "%s", "zone": "%s", "area": "%s", "x": %s, "y": %s}, \n""" % item
        lines = lines[:-3] + '\n], '
    lines = lines[:-2] + "\n}"
    return lines

# request helpers
def template_vals(app, title, user):
    template_values = {'app': app, 'title': title, 'version': "%s.%s.%s" % tuple(VER)}
    if user:
        template_values['user'] = user.name
        template_values['dark'] = user.dark_theme
        if user.theme:
            template_values['theme'] = user.theme
    return template_values


debug = os.environ.get('SERVER_SOFTWARE', '').startswith('Dev')
path = os.path.join(os.path.dirname(__file__), 'map/build/index.html')

def param_val(s, f):
    return s.request.get(f, None)

def param_flag(s, f):
    return param_val(s, f) is not None

def resp_error(handler, code=400, response=None, altRespType=None):
    handler.response.status = code
    if altRespType:
        handler.response.headers['Content-Type'] = altRespType
    handler.response.write(response)

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
    i = 0
    flat_bits = [b for bfield in bfields for b in int_to_bits(bfield, 32)[::-1]]
    return [ c for b,c in zip(flat_bits, coords_in_order) if b ]
