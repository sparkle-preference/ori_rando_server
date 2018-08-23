from math import floor
from collections import defaultdict, namedtuple 
from datetime import datetime, timedelta
import xml.etree.ElementTree as XML
import logging as log

import sys,os
LIBS = os.path.join(os.path.dirname(os.path.realpath(__file__)),"lib")
if LIBS not in sys.path:
	sys.path.insert(0, LIBS)


coord_correction_map = {
	679620: 719620,
	-4560020: -4600020,
	-520160: -560160,
#	-4199936: -4600020, Past me WHY, WHY DID YOU DO THIS
	8599908: 8599904,
	2959744: 2919744, 
}
# for picks_by_loc_gen
non_area_lines = {
	"EC": "\t{'loc': -280256, 'name': 'EC', 'zone': 'Glades', 'area': 'SunkenGladesRunaway', 'y': -256, 'x': -28},\n",
	"EX": "\t{'loc': -1680104, 'name': 'EX100', 'zone': 'Grove', 'area': 'SpritTreeRefined', 'y': -104, 'x': -168},\n",
	"Pl": "\t{'loc': -12320248, 'name': 'Plant', 'zone': 'Forlorn', 'area': 'RightForlornPlant', 'y': -248, 'x': -1232},\n",
	"KS": "\t{'loc': -10440008, 'name': 'KS', 'zone': 'Misty', 'area': 'Misty', 'y': 8, 'x': -1044},\n"
}
PickLoc = namedtuple("PickLoc", ["coords", "name", "zone", "area", "y", "x"])

extra_PBT = [
	PickLoc(24, 'Mapstone 1', 'Mapstone', 'MS1', 24,  0),
	PickLoc(28, 'Mapstone 2', 'Mapstone', 'MS2', 28,  0),
	PickLoc(32, 'Mapstone 3', 'Mapstone', 'MS3', 32,  0),
	PickLoc(36, 'Mapstone 4', 'Mapstone', 'MS4', 36,  0),
	PickLoc(40, 'Mapstone 5', 'Mapstone', 'MS5', 40,  0),
	PickLoc(44, 'Mapstone 6', 'Mapstone', 'MS6', 44,  0),
	PickLoc(48, 'Mapstone 7', 'Mapstone', 'MS7', 48,  0),
	PickLoc(52, 'Mapstone 8', 'Mapstone', 'MS8', 52,  0),
	PickLoc(56, 'Mapstone 9', 'Mapstone', 'MS9', 56,  0)
]

def enums_from_strlist(enum, strlist):
	enums = []
	for elem in strlist:
		maybe_enum = enum.mk(elem)
		if maybe_enum:
			enums.append(maybe_enum)
		else:
			log.warning("%s is not a valid %s! Skipping param." % (elem, enum))
	return enums

	
def int_to_bits(n, min_len=2):
	raw = [1 if digit=='1' else 0 for digit in bin(n)[2:]]
	if len(raw) < min_len:
		raw = [0]*(min_len-len(raw))+raw
	return raw

def bits_to_int(n):
	return int("".join([str(b) for b in n]),2)

def rm_none(itr):
	return [elem for elem in itr if elem is not None]
	

log_2 = {1:0, 2:1, 4:2, 8:3, 16:4, 32:5, 64:6, 128:7, 256:8, 512:9, 1024:10, 2048:11, 4096:12, 8192:13, 16384:14, 32768:15, 65536:16}

special_coords = {(0,0): "Vanilla Water Vein",
	(0,4): "Ginso Escape Finish",
	(0,8): "Misty Orb Turn-In",
	(0,12): "Forlorn Escape Start",
	(0,16): "Vanilla Sunstone",
	(0,20): "Final Escape Start"}

special_coords.update({(0,20+4*x): "Mapstone %s" % x for x in range(1,10)})


all_locs = set([0, 2999808, 4, 5280264, -4159572, 12, 16, 4479832, 4559492, 919772, -3360288, 24, -8400124, 28, 32, 1599920, -6479528, 36, 40, 3359580, 2759624, 44, 4959628, 4919600, 3279920, -12320248, 1479880, 52, 56, 3160244, 960128, 799804, -6159632, -800192, 
				5119584, 5719620, -6279608, -3160308, 5320824, 4479568, 9119928, -319852, 1719892, -480168, 919908, 1519708, 20, -6079672, 2999904, -6799732, -11040068, 5360732, 559720, 4039612, 4439632, 1480360, -2919980, -120208, -2480280, 4319860, -7040392, 
				-1800088, -4680068, 4599508, 2919744, 3319936, 1720000, 120164, -4600188, 5320328, 6999916, 3399820, 1920384, -400240, -6959592, 4319892, 2239640, 2719900, -160096, 3559792, 1759964, -5160280, 6359836, 5080496, 5359824, 1959768, 5039560, 4560564, 
				-10440008, 2519668, -2240084, -10760004, -4879680, 799776, -5640092, -6080316, 6279880, 4239780, -5119796, 7599824, 5919864, -4160080, 4999892, 3359784, 4479704, -1800156, -6280316, -5719844, -8600356, -2160176, 5399780, -6119704, 5639752, 3439744, 
				7959788, 5080304, 5320488, -10120036, -7960144, -1680140, 8, -8920328, 1839836, 2520192, 1799708, 5399808, -8720256, 639888, 719620, 6639952, 3919624, -4600020, 5200140, 39756, 2480400, 959960, 6839792, -1680104, -8880252, 5320660, 3279644, -6719712, 
				48, 599844, -3600088, 8839900, 4199724, 3039472, -4559584, -1560272, 1600136, 4759860, 5280500, 2559800, 3119768, 6159900, 5879616, -10759968, 5280296, 3919688, -2080116, 5119900, 3199820, 2079568, -5400236, -4199936, -8240012, -5479592, -3200164, 
				8599904, -5039728, 7839588, -5159576, 4079964, -1840196, 7679852, 5400100, -7680144, -6720040, -5919556, 1880164, -3559936, -6319752, 5280404, 39804, 6399872, -280256, -9799980, 1280164, -1560188, -2200184, 6080608, -1919808, 4639628, 7639816, -6800032,
				5160336, 3879576, 4199828, 3959588, 5119556, 5400276, -1840228, 5160864, 1040112, 4680612, -11880100, -4440152, -3520100, 7199904, -2200148, 7559600, -10839992, 5040476, -8160268, 4319676, 5160384, 5239456, -2400212, 2599880, 3519820, -9120036, 
				3639880, -6119656, 3039696, 1240020, -5159700, -4359680, -5400104, -5959772, 5439640, -8440352, 3639888, -2480208, 399844, -560160, 4359656, -4799416, 8719856, -6039640, -5479948, 5519856, 6199596, -4600256, -2840236, 5799932, -600244, 5360432])


def get_bit(bits_int, bit):
	return int_to_bits(bits_int, log_2[bit]+1)[-(1+log_2[bit])]

def get_taste(bits_int, bit):
	bits = int_to_bits(bits_int,log_2[bit]+2)[-(2+log_2[bit]):][:2]
	return 2*bits[0]+bits[1]

def add_single(bits_int, bit, remove=False):
	if bit<0:
		return bits_int
	if bits_int >= bit:
		if remove:
			return bits_int-bit
		if get_bit(bits_int, bit) == 1:
			return bits_int
	return bits_int + bit

def inc_stackable(bits_int, bit, remove=False):
	if bit<0:
		return bits_int
	if remove:
		if get_taste(bits_int, bit) > 0:
			return bits_int - bit
		return bits_int
	if get_taste(bits_int, bit) > 2:
		return bits_int
	return bits_int+bit


def get(x,y):
	return x*10000 + y

def sign(x):
	return 1 if x>=0 else -1

def rnd(x):
	return int(floor((x) / 4.0) * 4.0)

def unpack(coord):
	y = coord % (sign(coord)*10000)
	if y > 2000:
		y -= 10000
	elif y < -2000:
		y += 10000
	if y < 0:
		coord -= y
	x = rnd(coord/10000)
	return x,y

def is_int(s):
    try: 
        int(s)
        return True
    except ValueError:
        return False


def picks_by_type_gen():
	tree = XML.parse("seedbuilder/areas.xml")
	root = tree.getroot()
	picks_by_type=defaultdict(lambda: [])
	all_locs_unpacked = { unpack(loc) : loc for loc in all_locs }
	for child in root:
		area = child.attrib["name"]
		for loc in child.find("Locations"):
			x = loc.find("X").text
			y = loc.find("Y").text
			item = loc.find("Item").text
			if item == "MapStone":
				continue
			zone = loc.find("Zone").text
			crd = get(rnd(int(x)),rnd(int(y)))
			if crd not in all_locs:
				secondary_match = all_locs_unpacked.get((rnd(int(x)),rnd(int(y))))
				if secondary_match:
					crd = secondary_match
				else:
					print "No secondary match found here!", crd, item, zone, area, y, x
			line = PickLoc(crd,item,zone,area,y,x)
			picks_by_type[item[0:2]].append(line)
	return picks_by_type

def picks_by_type_formatter():
	retval = ""
	picks_by_type = picks_by_type_gen()
	for key in sorted(picks_by_type.keys()):
		if key in ["EV", "MP", "Ma"]:
			continue
		retval += '"%s": [\n' % key
		if key in non_area_lines:
			retval += non_area_lines[key]
		for item in sorted(picks_by_type[key], key=lambda x: str(x[0])):
			retval += """\t{'loc': %s, 'name': '%s', 'zone': '%s', 'area': '%s', 'y': %s, 'x': %s}, \n""" % item # tuple(list(item[1:]))
		retval += '], '
	return retval

from seedbuilder.generator import SeedGenerator
from pickups import Pickup
import seedbuilder.seedparams
import random
from enums import Variation, LogicPath, KeyMode, PathDifficulty, ShareType
anal_table = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: 0)))
count = 0

def analysis(runs=50):
	global count, anal_table
	count += runs
	pbt = picks_by_type_gen()
	pbt["MA"] = extra_PBT
	loc_ref = { str(pick.coords) : pick for picks in pbt.values() for pick in picks }
	initial_seed = random.randint(1,10000000)

	params = seedbuilder.seedparams.SeedGenParams(tracking=False)
	params.variations=[Variation.FORCE_TREES]
	params.logic_paths=[LogicPath.NORMAL, LogicPath.SPEED, LogicPath.LURE]
	params.key_mode = KeyMode.CLUES
	params.path_diff = PathDifficulty.NORMAL
	params.players = 1
	params.balanced = True
	params.sync = seedbuilder.seedparams.MultiplayerOptions(enabled=False)
	params.warmth = seedbuilder.seedparams.WarmthFragmentOptions(enabled=False)
	sg = SeedGenerator()
	for i in range(runs):
		params.seed = str(initial_seed+i)
		placements = sg.setSeedAndPlaceItems(params)
		if placements:
			for line in placements[0][0].split("\n")[1:-1]:
				loc,code,id,zone = tuple(line.split('|'))
				if loc in ["-280256", "-1680104", "-12320248", "-10440008"]:
					continue
				pick = Pickup.n(code,id)
				if pick.share_type in [ShareType.EVENT, ShareType.DUNGEON_KEY, ShareType.SKILL, ShareType.UPGRADE, ShareType.TELEPORTER]:
					anal_table[zone][loc][pick.name] += 1
					anal_table[zone][loc]["TOTAL"] += 1
		
	retlines = ["%s runs total" % count, "Location, Zone, Total, WallJump, ChargeFlame, DoubleJump, Bash, Stomp, Glide, Climb, ChargeJump, Dash, Grenade, GinsoKey, ForlornKey, HoruKey, Water, Wind, TPForlorn, TPGrotto, TPSorrow, TPGrove, TPSwamp, TPValley"]
	for zone in sorted(anal_table.keys()):
		for loc in sorted(anal_table[zone].keys(), reverse=True, key=lambda x: anal_table[zone][x]["TOTAL"]):
			t = anal_table[zone][loc]
			p = loc_ref[loc]
			line = ["%s %s (%s %s)" % (p.area, p.name, p.x, p.y), zone, t["TOTAL"]]
			line += [t["Wall Jump"], t["Charge Flame"], t["Double Jump"], t["Bash"], t["Stomp"], t["Glide"], t["Climb"], t["Charge Jump"], t["Dash"], t["Grenade"]]
			line += [t["Water Vein"], t["Gumon Seal"], t["Sunstone"], t["Clean Water"], t["Wind Restored"]]
			line += [t["Forlorn teleporter"], t["Grotto teleporter"], t["Sorrow teleporter"], t["Grove teleporter"], t["Swamp teleporter"], t["Valley teleporter"]]
			retlines.append(", ".join([str(x) for x in line]))
	return "\n".join(retlines)

			


def dll_last_update():
	if os.environ.get('SERVER_SOFTWARE', '').startswith('Dev'):
		return "N/A"
	from github import Github
	# hidiously bad practice but the token only has read rights so w/eeeeee
	return Github("d060d7ef01443cdf653" + "" + "eb2e9ae7b66f37313b769").get_repo(124633989).get_commits(path="Assembly-CSharp.dll")[0].commit.last_modified