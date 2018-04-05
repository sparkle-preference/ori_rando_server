import xml.etree.ElementTree as XML
from collections import defaultdict, Counter

class PlayerState(object):
	name_from_id = {
		("SK",0): 'Bash',  ("SK",2): 'ChargeFlame',  ("SK",3): 'WallJump',  ("SK",4): 'Stomp',  ("SK",5):  'DoubleJump', 
		("SK",8): 'ChargeJump',  ("SK",12): 'Climb',  ("SK",14): 'Glide',  ("SK",50): 'Dash',  ("SK",51): 'Grenade',
		("EV", 0): 'GinsoKey', ("EV", 1): 'Water', ("EV", 2): 'ForlornKey', ("EV", 3): 'Wind', ("EV", 4): 'HoruKey', 
		("TP","Swamp"): 'TPSwamp', ("TP","Grove"): 'TPGrove', ("TP","Valley"): 'TPValley', 
		("TP","Grotto"): 'TPGrotto', ("TP","Forlorn"): 'TPForlorn', ("TP","Sorrow"): 'TPSorrow' 
	}
	def __init__(self):
		self.has = Counter()

	@staticmethod
	def from_player(player):
		inst = PlayerState()
		inst.build_from_codes([(h.pickup_code, h.pickup_id, h.removed) for h in player.history])
		return inst


	@staticmethod
	def from_codes(codes):
		inst = PlayerState()
		inst.build_from_codes(codes)
		return inst



	def build_from_codes(self, pickinfos):
		wv = ss = gs = 0
		for code,id,removed in pickinfos:
			if code in ["EX", "AC"]:
				continue
			id = id if code=="TP" else int(id)
			if (code,id) in PlayerState.name_from_id:
				self.has[PlayerState.name_from_id[(code,id)]] = (0 if removed else 1)
			elif code == "RB":
				if id == 17:
					wv += (-1 if removed else 1)
				elif id == 19:
					gs += (-1 if removed else 1)
				if id == 21:
					ss += (-1 if removed else 1)
			elif code in ["HC","EC","KS","MS"]:			
				self.has[code] += (-id if removed else id)
		if wv >= 3:
			self.has['GinsoKey'] = 1
		if gs >= 3:
			self.has['ForlornKey'] = 1
		if ss >= 3:
			self.has['HoruKey'] = 1
			

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
				
			
