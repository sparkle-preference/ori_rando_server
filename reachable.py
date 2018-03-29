import xml.etree.ElementTree as XML
from collections import defaultdict, Counter

class PlayerState(object):
	name_from_id = {("SK",14): 'Glide', ("SK",50): 'Dash', ("TP","Swamp"): 'TPSwamp', ("EV", 4): 'HoruKey', ("TP","Grove"): 'TPGrove', ("SK",4): 'Stomp', ("SK",51): 'Grenade', ("EV", 1): 'Water', ("SK",0): 'Bash', ("SK",8): 'ChargeJump', ("TP","Valley"): 'TPValley', ("SK",12): 'Climb', ("TP","Grotto"): 'TPGrotto', ("EV", 3): 'Wind', ("EV", 2): 'ForlornKey', ("TP","Forlorn"): 'TPForlorn', ("SK",2): 'ChargeFlame', ("SK",3): 'WallJump', ("EV", 0): 'GinsoKey', ("TP","Sorrow"): 'TPSorrow', ("SK",5):  'DoubleJump'}
	def __init__(self, player):
		self.has = Counter()
		wv = ss = gs = 0
		for hl in player.history:				
			code = hl.pickup_code
			if code in ["EX", "AC"]:
				continue
			id = hl.pickup_id if code=="TP" else int(hl.pickup_id)
			if (code,id) in PlayerState.name_from_id:
				self.has[PlayerState.name_from_id[(code,id)]] = (0 if hl.removed else 1)
			elif code == "RB":
				if id == 17:
					wv += (-1 if hl.removed else 1)
				elif id == 19:
					gs += (-1 if hl.removed else 1)
				if id == 21:
					ss += (-1 if hl.removed else 1)
			elif code in ["HC","EC","KS"]:			
				self.has[code] += (-id if hl.removed else id)

class Area(object):
	def __init__(self, name):
		self.name = name
		self.conns = []		
	def get_reachable(self, state, modes):
		return [conn.target for conn in self.conns if conn.is_active(state, modes)]

class Connection(object):
	def __init__(self, target):
		self.target = target
		self.reqs = defaultdict(list)
	def is_active(self, state, modes):
		for mode in modes:
			for reqs in self.reqs[mode]:
				if not reqs.cnt - state.has:
					return True
		return False
	

class Requirement(object):
	def __init__(self, raw):
		self.cnt = Counter([r for r in raw.split('+') if r != "Free"])


class Map(object):
	areas = {}
	@staticmethod
	def build():
		tree = XML.parse("seedbuilder/areas.xml")
		root = tree.getroot()
		for child in root:
			area = Area(child.attrib["name"])
			for c in child.find("Connections"):
				conn = Connection(c.find("Target").attrib["name"])
				for req in c.find("Requirements"):
					conn.reqs[req.attrib["mode"]].append(Requirement(req.text))
				area.conns.append(conn)
			Map.areas[area.name] = area

	@staticmethod
	def get_reachable_areas(state, modes):
		if not Map.areas:
			Map.build()
		unchecked_areas = set(["SunkenGladesRunaway"])
		checked_areas = set()
		while(len(unchecked_areas) > 0):
			curr = unchecked_areas.pop()
			checked_areas.add(curr)
			unchecked_areas |= set([r for r in Map.areas[curr].get_reachable(state, modes) if r not in checked_areas])
		return list(checked_areas)
				
			
