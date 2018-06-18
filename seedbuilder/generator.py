import re
import math
import xml.etree.ElementTree as XML
from collections import OrderedDict, defaultdict

# A custom implementation of a Mersenne Twister
# (since javascript hates everything)
# https://en.wikipedia.org/wiki/Mersenne_Twister
class Random:

	def seed(self, seed):
		self.index = 624
		self.mt = [0] * 624
		self.mt[0] = hash(seed)
		for i in range(1, 624):
			self.mt[i] = int(0xFFFFFFFF & (1812433253 * (self.mt[i - 1] ^ self.mt[i - 1] >> 30) + i))

	def generate_sequence(self):
		for i in range(624):
			# Get the most significant bit and add it to the less significant
			# bits of the next number
			y = int(0xFFFFFFFF & (self.mt[i] & 0x80000000) + (self.mt[(i + 1) % 624] & 0x7fffffff))
			self.mt[i] = self.mt[(i + 397) % 624] ^ y >> 1

			if y % 2 != 0:
				self.mt[i] = self.mt[i] ^ 0x9908b0df
		self.index = 0

	def random(self):
		if self.index >= 624:
			self.generate_sequence()

		y = self.mt[self.index]

		# Right shift by 11 bits
		y = y ^ y >> 11
		# Shift y left by 7 and take the bitwise and of 2636928640
		y = y ^ y << 7 & 2636928640
		# Shift y left by 15 and take the bitwise and of y and 4022730752
		y = y ^ y << 15 & 4022730752
		# Right shift by 18 bits
		y = y ^ y >> 18

		self.index = self.index + 1

		return int(0xFFFFFFFF & y) / float(0x100000000)

	def randrange(self, length):
		return int(self.random() * length)

	def randint(self, low, high):
		return int(low + self.random() * (high - low + 1))

	def uniform(self, low, high):
		return self.random() * (high - low) + low

	def shuffle(self, items):
		original = list(items)
		for i in range(len(items)):
			items[i] = original.pop(self.randrange(len(original)))

class Area:
	def __init__(self, name):
		self.name = name
		self.connections = []
		self.locations = []
		self.difficulty = 1

	def add_connection(self, connection):
		self.connections.append(connection)

	def get_connections(self):
		return self.connections

	def remove_connection(self, connection):
		self.connections.remove(connection)

	def add_location(self, location):
		self.locations.append(location)

	def get_locations(self):
		return self.locations

	def clear_locations(self):
		self.locations = []

	def remove_location(self, location):
		self.locations.remove(location)

class Connection:

	def __init__(self, home, target, sg):
		self.home = home
		self.target = target
		self.keys = 0
		self.mapstone = False
		self.requirements = []
		self.difficulties = []
		self.sg = sg

	def add_requirements(self, req, difficulty):
		if self.sg.shards:
			match = re.match(".*GinsoKey.*", str(req))
			if match:
				req.remove("GinsoKey")
				req.append("WaterVeinShard")
				req.append("WaterVeinShard")
				req.append("WaterVeinShard")
				req.append("WaterVeinShard")
				req.append("WaterVeinShard")
			match = re.match(".*ForlornKey.*", str(req))
			if match:
				req.remove("ForlornKey")
				req.append("GumonSealShard")
				req.append("GumonSealShard")
				req.append("GumonSealShard")
				req.append("GumonSealShard")
				req.append("GumonSealShard")
			match = re.match(".*HoruKey.*", str(req))
			if match:
				req.remove("HoruKey")
				req.append("SunstoneShard")
				req.append("SunstoneShard")
				req.append("SunstoneShard")
				req.append("SunstoneShard")
				req.append("SunstoneShard")
		self.requirements.append(req)
		self.difficulties.append(difficulty)
		match = re.match(".*KS.*KS.*KS.*KS.*", str(req))
		if match:
			self.keys = 4
			return
		match = re.match(".*KS.*KS.*", str(req))
		if match:
			self.keys = 2
			return
		match = re.match(".*MS.*", str(req))
		if match:
			self.mapstone = True
			return

	def get_requirements(self):
		return self.requirements

	def cost(self):
		minReqScore = 7777
		minDiff = 7777
		minReq = []
		for i in range(0, len(self.requirements)):
			score = 0
			energy = 0
			health = 0
			for abil in self.requirements[i]:
				if abil == "EC":
					energy += 1
					if  self.sg.inventory["EC"] < energy:
						score += self.sg.costs[abil.strip()]
				elif abil == "HC":
					health += 1
					if self.sg.inventory["HC"] < health:
						score += self.sg.costs[abil.strip()]
				else:
					score += self.sg.costs[abil.strip()]
			if score < minReqScore:
				minReqScore = score
				minReq = self.requirements[i]
				minDiff = self.difficulties[i]
		return (minReqScore, minReq, minDiff)

class Location:
	factor = 4.0

	def __init__(self, x, y, area, orig, difficulty, zone):
		self.x = int(math.floor((x) / self.factor) * self.factor)
		self.y = int(math.floor((y) / self.factor) * self.factor)
		self.orig = orig
		self.area = area
		self.difficulty = difficulty
		self.zone = zone

	def get_key(self):
		return self.x * 10000 + self.y

	def to_string(self):
		return self.area + " " + self.orig + " (" + str(self.x) + " " + str(self.y) + ")"

class Door:
	factor = 4.0

	def __init__(self, name, x, y):
		self.x = x
		self.y = y
		self.name = name

	def get_key(self):
		return int(math.floor(self.x / self.factor) * self.factor) * 10000 + int(
			math.floor(self.y / self.factor) * self.factor)

class SeedGenerator:

	def reach_area(self, target):
		if target in self.sharedMap and self.playerID > 1:
			for sharedItem in self.sharedMap[target]:
				if sharedItem[1] == self.playerID:
					self.assignQueue.append(sharedItem[0])
					self.itemCount += 1
				else:
					self.assign(sharedItem[0])
					if sharedItem[0] not in self.spoilerGroup:
						self.spoilerGroup[sharedItem[0]] = []
					self.spoilerGroup[sharedItem[0]].append(sharedItem[0] + " from Player " + str(sharedItem[1]) + "\n")
		self.currentAreas.append(target)
		self.areasReached[target] = True

	def open_free_connections(self):
		found = False
		keystoneCount = 0
		mapstoneCount = 0
		# python 3 wont allow concurrent changes
		# list(areasReached.keys()) is a copy of the original list
		for area in list(self.areasReached.keys()):
			for connection in self.areas[area].get_connections():
				cost = connection.cost()
				if cost[0] <= 0:
					self.areas[connection.target].difficulty = cost[2]
					if connection.keys > 0:
						if area not in self.doorQueue.keys():
							self.doorQueue[area] = connection
							keystoneCount += connection.keys
					elif connection.mapstone:
						if connection.target not in self.areasReached:
							visitMap = True
							for mp in self.mapQueue.keys():
								if mp == area or self.mapQueue[mp].target == connection.target:
									visitMap = False
							if visitMap:
								self.mapQueue[area] = connection
								mapstoneCount += 1
					else:
						if connection.target not in self.areasReached:
							self.seedDifficulty += cost[2] * cost[2]
							self.reach_area(connection.target)
						if connection.target in self.areasRemaining:
							self.areasRemaining.remove(connection.target)
						self.connectionQueue.append((area, connection))
						found = True
		return (found, keystoneCount, mapstoneCount)

	def get_all_accessible_locations(self):
		locations = []
		for area in self.areasReached.keys():
			currentLocations = self.areas[area].get_locations()
			for location in currentLocations:
				location.difficulty += self.areas[area].difficulty
			if self.limitkeys:
				loc = ""
				for location in currentLocations:
					if location.orig in self.keySpots.keys():
						loc = location
						break
				if loc:
					self.force_assign(self.keySpots[loc.orig], loc)
					currentLocations.remove(loc)
			if self.forcedAssignments:
				reachable_forced_ass_locs = [l for l in currentLocations if l.get_key() in self.forcedAssignments]
				for loc in reachable_forced_ass_locs:
					self.force_assign(forcedAssignments[loc.get_key()], loc)
					currentLocations.remove(loc)
				
			locations.extend(currentLocations)
			self.areas[area].clear_locations()
		if self.reservedLocations:
			locations.append(self.reservedLocations.pop(0))
			locations.append(self.reservedLocations.pop(0))
		if self.itemCount > 2 and len(locations) >= 2:
			self.reservedLocations.append(locations.pop(self.random.randrange(len(locations))))
			self.reservedLocations.append(locations.pop(self.random.randrange(len(locations))))
		return locations

	def prepare_path(self, free_space):
		abilities_to_open = OrderedDict()
		totalCost = 0.0
		free_space += len(self.balanceList)
		# find the sets of abilities we need to get somewhere
		for area in self.areasReached.keys():
			for connection in self.areas[area].get_connections():
				if connection.target in self.areasReached:
					continue
				if self.limitkeys and connection.get_requirements() and (
						"GinsoKey" in connection.get_requirements()[0] or "ForlornKey" in connection.get_requirements()[
					0] or "HoruKey" in connection.get_requirements()[0]):
					continue
				for req_set in connection.get_requirements():
					requirements = []
					cost = 0
					cnts = defaultdict(lambda: 0)
					for req in req_set:
						# for paired randomizer -- if the item isn't yours to assign, skip connection
						if self.itemPool[req] == 0:
							requirements = []
							break
						if self.costs[req] > 0:
							if req in ["HC", "EC", "WaterVeinShard", "GumonSealShard", "SunstoneShard"]:
								cnts[req] += 1
								if cnts[req] > self.inventory[req]:
									requirements.append(req)
									cost += self.costs[req]
							else:
								requirements.append(req)
								cost += self.costs[req]
					# cost *= len(requirements) # decrease the rate of multi-ability paths
					if len(requirements) <= free_space:
						for req in requirements:
							if req not in abilities_to_open:
								abilities_to_open[req] = (cost, requirements)
							elif abilities_to_open[req][0] > cost:
								abilities_to_open[req] = (cost, requirements)
		# pick a random path weighted by cost
		for path in abilities_to_open:
			totalCost += 1.0 / abilities_to_open[path][0]
		position = 0
		target = self.random.random() * totalCost
		for path in abilities_to_open:
			position += 1.0 / abilities_to_open[path][0]
			if target <= position:
				for req in abilities_to_open[path][1]:
					if self.itemPool[req] > 0:
						self.assignQueue.append(req)
				return abilities_to_open[path][1]

	def get_location_from_balance_list(self):
		target = int(pow(self.random.random(), 1.0 / self.balanceLevel) * len(self.balanceList))
		location = self.balanceList.pop(target)
		self.balanceListLeftovers.append(location[0])
		return location[1]

	def assign_random(self, recurseCount=0):
		value = self.random.random()
		position = 0.0
		denom = float(sum(self.itemPool.values()))
		for key in self.itemPool.keys():
			position += self.itemPool[key] / denom
			if value <= position:
				if self.starved and key in self.skillsOutput and recurseCount < 3:
					return self.assign_random(recurseCount=recurseCount + 1)
				return self.assign(key)

	def assign(self, item):
		self.itemPool[item] = max(self.itemPool[item] - 1, 0) if item in self.itemPool else 0
		if item == "EC" or item == "KS" or item == "HC":
			if self.costs[item] > 0:
				self.costs[item] -= 1
		elif item == "WaterVeinShard" or item == "GumonSealShard" or item == "SunstoneShard":
			if self.costs[item] > 0:
				self.costs[item] -= 1
		elif item in self.costs.keys():
			self.costs[item] = 0
		self.inventory[item] = 1 + (self.inventory[item] if item in self.inventory else 0)
		return item

	# for use in limitkeys mode
	def force_assign(self, item, location):
		self.assign(item)
		self.assign_to_location(item, location)

	def assign_to_location(self, item, location):
		assignment = ""
		zone = location.zone
		value = 0

		# if this is the first player of a paired seed, construct the map
		if self.playerCount > 1 and self.playerID == 1 and item in self.sharedList:
			player = self.random.randint(1, self.playerCount)
			if location.area not in self.sharedMap:
				self.sharedMap[location.area] = []
			self.sharedMap[location.area].append((item, player))

			if player != self.playerID:
				if player not in self.sharedMap:
					self.sharedMap[player] = 0
				self.sharedMap[player] += 1
				if item not in self.spoilerGroup:
					self.spoilerGroup[item] = []
				self.spoilerGroup[item].append(item + " from Player " + str(player) + "\n")
				item = "EX*"
				self.expSlots += 1

		# if mapstones are progressive, set a special location
		if not self.nonProgressiveMapstones and location.orig == "MapStone":
			self.mapstonesAssigned += 1
			assignment += (str(20 + self.mapstonesAssigned * 4) + "|")
			zone = "Mapstone"
			if item in self.costs.keys():
				if item not in self.spoilerGroup:
					self.spoilerGroup[item] = []
				self.spoilerGroup[item].append(item + " from MapStone " + str(self.mapstonesAssigned) + "\n")
		else:
			assignment += (str(location.get_key()) + "|")
			if item in self.costs.keys():
				if item not in self.spoilerGroup:
					self.spoilerGroup[item] = []
				self.spoilerGroup[item].append(item + " from " + location.to_string() + "\n")

		if item in self.skillsOutput:
			assignment += (str(self.skillsOutput[item][:2]) + "|" + self.skillsOutput[item][2:])
		elif item in self.eventsOutput:
			assignment += (str(self.eventsOutput[item][:2]) + "|" + self.eventsOutput[item][2:])
		elif item == "EX*":
			value = self.get_random_exp_value()
			self.expRemaining -= value
			self.expSlots -= 1
			assignment += "EX|" + str(value)
		elif item[2:]:
			assignment += (item[:2] + "|" + item[2:])
		else:
			assignment += (item[:2] + "|1")
		assignment += ("|" + zone + "\n")

		if item in self.eventsOutput:
			self.eventList.append(assignment)
		elif self.balanced and item not in self.costs.keys() and location.orig != "MapStone":
			if value > 0:
				item = "EX" + str(value)
			self.balanceList.append((item, location, assignment))
		else:
			self.outputStr += assignment

	def get_random_exp_value(self):
		min = self.random.randint(2, 9)

		if self.expSlots <= 1:
			return max(self.expRemaining, min)

		return int(max(self.expRemaining * (self.inventory["EX*"] + self.expSlots / 4) * self.random.uniform(0.0, 2.0) / (
					self.expSlots * (self.expSlots + self.inventory["EX*"])), min))

	def preferred_difficulty_assign(self, item, locationsToAssign):
		total = 0.0
		for loc in locationsToAssign:
			if self.pathDifficulty == "easy":
				total += (15 - loc.difficulty) * (15 - loc.difficulty)
			else:
				total += (loc.difficulty * loc.difficulty)
		value = self.random.random()
		position = 0.0
		for i in range(0, len(locationsToAssign)):
			if self.pathDifficulty == "easy":
				position += (15 - locationsToAssign[i].difficulty) * (15 - locationsToAssign[i].difficulty) / total
			else:
				position += locationsToAssign[i].difficulty * locationsToAssign[i].difficulty / total
			if value <= position:
				self.assign_to_location(item, locationsToAssign[i])
				break
		del locationsToAssign[i]

	def connect_doors(self, door1, door2, requirements=["Free"]):
		connection1 = Connection(door1.name, door2.name, self)
		connection1.add_requirements(requirements, 1)
		self.areas[door1.name].add_connection(connection1)
		connection2 = Connection(door2.name, door1.name, self)
		connection2.add_requirements(requirements, 1)
		self.areas[door2.name].add_connection(connection2)
		return str(door1.get_key()) + "|EN|" + str(door2.x) + "|" + str(door2.y) + "\n" + str(
			door2.get_key()) + "|EN|" + str(door1.x) + "|" + str(door1.y) + "\n";

	def randomize_entrances(self):
		tree = XML.parse("seedbuilder/doors.xml")
		root = tree.getroot()

		outerDoors = [[], [], [], [], [], [], [], [], [], [], [], [], []]
		innerDoors = [[], [], [], [], [], [], [], [], [], [], [], [], []]

		for child in root:
			inner = child.find("Inner")
			innerDoors[int(inner.find("Group").text)].append(
				Door(child.attrib["name"] + "InnerDoor", int(inner.find("X").text), int(inner.find("Y").text)))

			outer = child.find("Outer")
			outerDoors[int(outer.find("Group").text)].append(
				Door(child.attrib["name"] + "OuterDoor", int(outer.find("X").text), int(outer.find("Y").text)))

		self.random.shuffle(outerDoors[0])
		self.random.shuffle(innerDoors[12])

		firstDoors = []
		lastDoors = []

		firstDoors.append(outerDoors[0].pop(0))
		firstDoors.append(outerDoors[0].pop(0))

		lastDoors.append(innerDoors[12].pop(0))
		lastDoors.append(innerDoors[12].pop(0))

		doorStr = ""

		# activeGroups = [0, 1, 2]
		# targets = [3, 4, 5, 6, 7, 8, 9, 10, 12]
		# for now, make R1 vanilla

		doorStr += self.connect_doors(outerDoors[2].pop(0), innerDoors[7].pop(0))

		activeGroups = [0, 1, 8]
		targets = [3, 4, 5, 6, 8, 9, 10, 12]

		self.random.shuffle(targets)

		horuEntryGroup = self.random.randint(4, 9)
		if horuEntryGroup >= 7:
			horuEntryGroup += 2
		if horuEntryGroup == 11:
			horuEntryGroup = 1
			if self.random.random() > 0.5:
				doorStr += self.connect_doors(firstDoors[0], innerDoors[1].pop(0))
				outerDoors[0].append(firstDoors[1])
			else:
				doorStr += self.connect_doors(firstDoors[0], outerDoors[1].pop(0))
				outerDoors[0].append(firstDoors[1])
				outerDoors[0].append(innerDoors[1].pop(0))
		else:
			requirements = ["Free"]
			if firstDoors[1].name == "GinsoDoorOuter":
				requirements = ["GinsoKey"]
			if firstDoors[1].name == "ForlornDoorOuter":
				requirements = ["ForlornKey"]
			doorStr += self.connect_doors(firstDoors[0], outerDoors[horuEntryGroup].pop(0), requirements)
			doorStr += self.connect_doors(firstDoors[1], innerDoors[horuEntryGroup - 1].pop(0))
			targets.remove(horuEntryGroup - 1)

		while len(targets) > 0:
			index = self.random.randrange(len(activeGroups))
			group = activeGroups[index]
			if not outerDoors[group]:
				del activeGroups[index]
				continue

			target = targets[0]
			if not innerDoors[target]:
				del targets[0]
				continue

			if target < 12:
				activeGroups.append(target + 1)

			if (target == 6 and 10 not in targets) or (target == 10 and 6 not in targets):
				activeGroups.append(12)

			doorStr += self.connect_doors(outerDoors[group].pop(0), innerDoors[target].pop(0))

		lastDoorIndex = 0

		for group in range(13):
			if innerDoors[group]:
				doorStr += self.connect_doors(innerDoors[group].pop(0), lastDoors[lastDoorIndex])
				lastDoorIndex += 1
			if outerDoors[group]:
				doorStr += self.connect_doors(outerDoors[group].pop(0), lastDoors[lastDoorIndex])
				lastDoorIndex += 1

		return doorStr

	def setSeedAndPlaceItems(self, seed, expPool, hardMode, includePlants, shardsMode, limitkeysMode, cluesMode, noTeleporters,
						modes, flags, starvedMode, preferPathDifficulty,
						setNonProgressiveMapstones, playerCountIn, balanced, entrance, sharedItems, wild=False, preplacedIn={}, retries=5):
		self.sharedMap = {}
		self.sharedList = []
		self.playerCount = playerCountIn
		self.random = Random()
		self.random.seed(seed)
		self.shards = shardsMode
		self.limitkeys = limitkeysMode
		self.clues = cluesMode
		self.starved = starvedMode
		self.pathDifficulty = preferPathDifficulty
		self.nonProgressiveMapstones = setNonProgressiveMapstones
		self.balanced = balanced
		self.hardMode = hardMode
		self.includePlants = includePlants
		self.noTeleporters = noTeleporters
		self.wild = wild
		self.entrance = entrance
		self.preplaced = preplacedIn
		self.expPool = expPool
		self.modes = modes
		self.flags = flags

		if self.playerCount > 1:
			if "skills" in sharedItems:
				self.sharedList += ["WallJump", "ChargeFlame", "Dash", "Stomp", "DoubleJump", "Glide", "Bash", "Climb", "Grenade", "ChargeJump"]
			if "keys" in sharedItems:
				if self.shards:
					self.sharedList.append("WaterVeinShard")
					self.sharedList.append("GumonSealShard")
					self.sharedList.append("SunstoneShard")
				else:
					self.sharedList.append("GinsoKey")
					self.sharedList.append("ForlornKey")
					self.sharedList.append("HoruKey")
			if "events" in sharedItems:
				self.sharedList.append("Water")
				self.sharedList.append("Wind")
				self.sharedList.append("Warmth")
			if "teleporters" in sharedItems:
				self.sharedList.append("TPForlorn")
				self.sharedList.append("TPGrotto")
				self.sharedList.append("TPSorrow")
				self.sharedList.append("TPGrove")
				self.sharedList.append("TPSwamp")
				self.sharedList.append("TPValley")
			if "upgrades" in sharedItems:
				self.sharedList += ["RB6", "RB8", "RB9", "RB10", "RB11", "RB12", "RB13", "RB15" ]

		return self.placeItemsMulti(seed, retries)

	def placeItemsMulti(self, seed, retries=5):

		placements = []
		self.sharedMap = {}
		self.playerID = 1

		placement = self.placeItems(seed, 0)
		if not placement:
			if self.preplaced:
				if retries > 0:
					retries -= 1
				else:
					print "ERROR: Seed not completeable with these params and placements"
					return None
			return self.placeItemsMulti(seed, retries)
		placements.append(placement)
		while self.playerID < self.playerCount:
			self.playerID += 1
			placement = self.placeItems(seed, 0)
			if not placement:
				if self.preplaced:
					if retries > 0:
						retries -= 1
					else:
						print "ERROR: Seed not completeable with these params and placements"
						return None
				return self.placeItemsMulti(seed, retries)
			placements.append(placement)

		return placements

	def placeItems(self, seed, depth=0):
		
		self.expRemaining = self.expPool
		self.balanceLevel = 0
		self.balanceList = []
		self.balanceListLeftovers = []

			
		self.forcedAssignments = self.preplaced

		self.skillsOutput = {
			"WallJump": "SK3",
			"ChargeFlame": "SK2",
			"Dash": "SK50",
			"Stomp": "SK4",
			"DoubleJump": "SK5",
			"Glide": "SK14",
			"Bash": "SK0",
			"Climb": "SK12",
			"Grenade": "SK51",
			"ChargeJump": "SK8"
		}

		self.eventsOutput = {
			"GinsoKey": "EV0",
			"Water": "EV1",
			"ForlornKey": "EV2",
			"Wind": "EV3",
			"HoruKey": "EV4",
			"Warmth": "EV5",
			"WaterVeinShard": "RB17",
			"GumonSealShard": "RB19",
			"SunstoneShard": "RB21"
		}

		seedDifficultyMap = {
			"Dash": 2,
			"Bash": 2,
			"Glide": 3,
			"DoubleJump": 2,
			"ChargeJump": 1
		}
		self.seedDifficulty = 0

		limitKeysPool = ["SKWallJump", "SKChargeFlame", "SKDash", "SKStomp", "SKDoubleJump", "SKGlide", "SKClimb",
						 "SKGrenade", "SKChargeJump", "EVGinsoKey", "EVForlornKey", "EVHoruKey", "SKBash", "EVWater",
						 "EVWind"]

		difficultyMap = {
			"normal": 1,
			"speed": 2,
			"lure": 2,
			"speed-lure": 3,
			"dboost": 2,
			"dboost-light": 1,
			"dboost-hard": 3,
			"cdash": 2,
			"cdash-farming": 2,
			"dbash": 3,
			"extended": 3,
			"extended-damage": 3,
			"lure-hard": 4,
			"extreme": 4,
			"glitched": 5,
			"timed-level": 5
		}

		self.outputStr = ""
		self.eventList = []
		spoilerStr = ""
		groupDepth = 0

		self.costs = {
			"Free": 0,
			"MS": 0,
			"KS": 2,
			"EC": 6,
			"HC": 12,
			"WallJump": 13,
			"ChargeFlame": 13,
			"DoubleJump": 13,
			"Bash": 41,
			"Stomp": 29,
			"Glide": 17,
			"Climb": 41,
			"ChargeJump": 59,
			"Dash": 13,
			"Grenade": 29,
			"GinsoKey": 12,
			"ForlornKey": 12,
			"HoruKey": 12,
			"Water": 80,
			"Wind": 80,
			"WaterVeinShard": 5,
			"GumonSealShard": 5,
			"SunstoneShard": 5,
			"TPForlorn": 120,
			"TPGrotto": 60,
			"TPSorrow": 90,
			"TPGrove": 60,
			"TPSwamp": 60,
			"TPValley": 90
		}

		# we use OrderedDicts here because the order of a dict depends on the size of the dict and the hash of the keys
		# since python 3.3 the order of a given dict is also dependent on the random hash seed for the current Python invocation
		#	 which apparently ignores our random.seed()
		# https://stackoverflow.com/questions/15479928/why-is-the-order-in-dictionaries-and-sets-arbitrary/15479974#15479974
		# Note that as of Python 3.3, a random hash seed is used as well, making hash collisions unpredictable
		# to prevent certain types of denial of service (where an attacker renders a Python server unresponsive
		# by causing mass hash collisions). This means that the order of a given dictionary is then also
		# dependent on the random hash seed for the current Python invocation.

		self.areas = OrderedDict()

		self.areasReached = OrderedDict([])
		self.currentAreas = []
		self.areasRemaining = []
		self.connectionQueue = []
		self.assignQueue = []

		self.itemCount = 244.0
		keystoneCount = 0
		mapstoneCount = 0

		if not self.hardMode:
			self.itemPool = OrderedDict([
				("EX1", 1),
				("EX*", 91),
				("KS", 40),
				("MS", 11),
				("AC", 33),
				("EC", 14),
				("HC", 12),
				("WallJump", 1),
				("ChargeFlame", 1),
				("Dash", 1),
				("Stomp", 1),
				("DoubleJump", 1),
				("Glide", 1),
				("Bash", 1),
				("Climb", 1),
				("Grenade", 1),
				("ChargeJump", 1),
				("GinsoKey", 1),
				("ForlornKey", 1),
				("HoruKey", 1),
				("Water", 1),
				("Wind", 1),
				("Warmth", 1),
				("RB0", 3),
				("RB1", 3),
				("RB6", 3),
				("RB8", 1),
				("RB9", 1),
				("RB10", 1),
				("RB11", 1),
				("RB12", 1),
				("RB13", 3),
				("RB15", 3),
				("WaterVeinShard", 0),
				("GumonSealShard", 0),
				("SunstoneShard", 0),
				("TPForlorn", 1),
				("TPGrotto", 1),
				("TPSorrow", 1),
				("TPGrove", 1),
				("TPSwamp", 1),
				("TPValley", 1)
			])
		else:
			self.itemPool = OrderedDict([
				("EX1", 1),
				("EX*", 167),
				("KS", 40),
				("MS", 11),
				("AC", 0),
				("EC", 3),
				("HC", 0),
				("WallJump", 1),
				("ChargeFlame", 1),
				("Dash", 1),
				("Stomp", 1),
				("DoubleJump", 1),
				("Glide", 1),
				("Bash", 1),
				("Climb", 1),
				("Grenade", 1),
				("ChargeJump", 1),
				("GinsoKey", 1),
				("ForlornKey", 1),
				("HoruKey", 1),
				("Water", 1),
				("Wind", 1),
				("Warmth", 1),
				("WaterVeinShard", 0),
				("GumonSealShard", 0),
				("SunstoneShard", 0),
				("TPForlorn", 1),
				("TPGrotto", 1),
				("TPSorrow", 1),
				("TPGrove", 1),
				("TPSwamp", 1),
				("TPValley", 1)
			])

		plants = []
		if not self.includePlants:
			self.itemCount -= 24
			self.itemPool["EX*"] -= 24

		if self.wild:
			self.itemPool["RB6"] += 2
			self.itemPool["RB31"] = 3
			self.itemPool["RB32"] = 3
			self.itemPool["RB33"] = 3
			self.itemPool["RB12"] += 5
			self.itemPool["RB101"] = 1
			self.itemPool["RB102"] = 1
			self.itemPool["RB103"] = 1
			self.itemPool["RB104"] = 1
			self.itemPool["EX*"] -= 20

		if self.shards:
			self.itemPool["WaterVeinShard"] = 5
			self.itemPool["GumonSealShard"] = 5
			self.itemPool["SunstoneShard"] = 5
			self.itemPool["GinsoKey"] = 0
			self.itemPool["ForlornKey"] = 0
			self.itemPool["HoruKey"] = 0
			self.itemPool["EX*"] -= 12

		if self.limitkeys:
			satisfied = False
			while not satisfied:
				ginso = self.random.randint(0, 12)
				if ginso == 12:
					ginso = 14
				forlorn = self.random.randint(0, 13)
				horu = self.random.randint(0, 14)
				if ginso != forlorn and ginso != horu and forlorn != horu and ginso + forlorn < 26:
					satisfied = True
			self.keySpots = {self.limitKeysPool[ginso]: "GinsoKey", self.limitKeysPool[forlorn]: "ForlornKey",
						self.limitKeysPool[horu]: "HoruKey"}
			self.itemPool["GinsoKey"] = 0
			self.itemPool["ForlornKey"] = 0
			self.itemPool["HoruKey"] = 0
			self.itemCount -= 3
		
		for item in self.forcedAssignments.values():			
			self.itemCount -= 1
			if item in self.itemPool:
				self.itemPool[item] -= 1
		
		if self.noTeleporters:
			self.itemPool["TPForlorn"] = 0
			self.itemPool["TPGrotto"] = 0
			self.itemPool["TPSorrow"] = 0
			self.itemPool["TPGrove"] = 0
			self.itemPool["TPSwamp"] = 0
			self.itemPool["TPValley"] = 0
			self.itemPool["EX*"] += 6

		self.inventory = OrderedDict([
			("EX1", 0),
			("EX*", 0),
			("KS", 0),
			("MS", 0),
			("AC", 0),
			("EC", 1),
			("HC", 3),
			("WallJump", 0),
			("ChargeFlame", 0),
			("Dash", 0),
			("Stomp", 0),
			("DoubleJump", 0),
			("Glide", 0),
			("Bash", 0),
			("Climb", 0),
			("Grenade", 0),
			("ChargeJump", 0),
			("GinsoKey", 0),
			("ForlornKey", 0),
			("HoruKey", 0),
			("Water", 0),
			("Wind", 0),
			("Warmth", 0),
			("RB0", 0),
			("RB1", 0),
			("RB6", 0),
			("RB8", 0),
			("RB9", 0),
			("RB10", 0),
			("RB11", 0),
			("RB12", 0),
			("RB13", 0),
			("RB15", 0),
			("RB31", 0),
			("RB32", 0),
			("RB101", 0),
			("RB102", 0),
			("RB103", 0),
			("RB104", 0),
			("WaterVeinShard", 0),
			("GumonSealShard", 0),
			("SunstoneShard", 0),
			("TPForlorn", 0),
			("TPGrotto", 0),
			("TPSorrow", 0),
			("TPGrove", 0),
			("TPSwamp", 0),
			("TPValley", 0)
		])
		

		# paired setup for subsequent players
		if self.playerID > 1:
			for item in self.sharedList:
				self.itemPool["EX*"] += self.itemPool[item]
				self.itemPool[item] = 0
			if self.playerID not in self.sharedMap:
				self.sharedMap[self.playerID] = 0
			self.itemPool["EX*"] -= self.sharedMap[self.playerID]
			self.itemCount -= self.sharedMap[self.playerID]

		tree = XML.parse("seedbuilder/areas.xml")
		root = tree.getroot()

		for child in root:
			area = Area(child.attrib["name"])
			self.areasRemaining.append(child.attrib["name"])

			for location in child.find("Locations"):
				loc = Location(int(location.find("X").text), int(location.find("Y").text), area.name,
							   location.find("Item").text, int(location.find("Difficulty").text),
							   location.find("Zone").text)
				if not self.includePlants:
					if re.match(".*Plant.*", area.name):
						plants.append(loc)
						continue
				area.add_location(loc)
			for conn in child.find("Connections"):
				connection = Connection(conn.find("Home").attrib["name"], conn.find("Target").attrib["name"], self)
				entranceConnection = conn.find("Entrance")
				if self.entrance and entranceConnection is not None:
					continue
				if not self.includePlants:
					if re.match(".*Plant.*", connection.target):
						continue
				for req in conn.find("Requirements"):
					if req.attrib["mode"] in self.modes:
						connection.add_requirements(req.text.split('+'), difficultyMap[req.attrib["mode"]])
				if connection.get_requirements():
					area.add_connection(connection)
			self.areas[area.name] = area

		# flags line
		self.outputStr += (self.flags + "|" + str(seed) + "\n")

		if self.entrance:
			self.outputStr += self.randomize_entrances()

		self.outputStr += ("-280256|EC|1|Glades\n") #if not (preplaced and -280256 in forcedAssignments) else "" # first energy cell
		self.outputStr += ("-1680104|EX|100|Grove\n") #if not (preplaced and -280256 in forcedAssignments) else ""  # glitchy 100 orb at spirit tree
		self.outputStr += ("-12320248|EX|100|Forlorn\n") #if not (preplaced and -280256 in forcedAssignments) else ""  # forlorn escape plant
		# the 2nd keystone in misty can get blocked by alt+R, so make it unimportant
		self.outputStr += ("-10440008|EX|100|Misty\n") #if not (preplaced and -10440008 in forcedAssignments) else ""

		if not self.includePlants:
			for location in plants:
				self.outputStr += (str(location.get_key()) + "|NO|0\n")
		
		locationsToAssign = []
		self.connectionQueue = []
		self.reservedLocations = []

		self.skillCount = 10
		self.mapstonesAssigned = 0
		self.expSlots = self.itemPool["EX*"]

		self.spoilerGroup = {"MS": [], "KS": [], "EC": [], "HC": []}

		self.doorQueue = OrderedDict()
		self.mapQueue = OrderedDict()
		spoilerPath = ""

		self.reach_area("SunkenGladesRunaway")

		while self.itemCount > 0 or (self.balanced and self.balanceListLeftovers):

			self.balanceLevel += 1
			# open all paths that we can already access
			opening = True
			while opening:
				(opening, keys, mapstones) = self.open_free_connections()
				keystoneCount += keys
				mapstoneCount += mapstones
				if mapstoneCount == 8:
					mapstoneCount = 9
				if mapstoneCount == 10:
					mapstoneCount = 11
				for connection in self.connectionQueue:
					self.areas[connection[0]].remove_connection(connection[1])
				self.connectionQueue = []

			locationsToAssign = self.get_all_accessible_locations()
			# if there aren't any doors to open, it's time to get a new skill
			# consider -- work on stronger anti-key-lock logic so that we don't
			# have to give keys out right away (this opens up the potential of
			# using keys in the wrong place, will need to be careful)
			if not self.doorQueue and not self.mapQueue:
				spoilerPath = self.prepare_path(len(locationsToAssign))
				if not self.assignQueue:
					# we've painted ourselves into a corner, try again
					if not self.reservedLocations:
						if self.playerID == 1:
							self.sharedMap = {}
						if depth > self.playerCount * self.playerCount:
							return
						return self.placeItems(seed, depth + 1)
					locationsToAssign.append(self.reservedLocations.pop(0))
					locationsToAssign.append(self.reservedLocations.pop(0))
					spoilerPath = self.prepare_path(len(locationsToAssign))
				if self.balanced:
					for item in self.assignQueue:
						if len(self.balanceList) == 0:
							break
						locationsToAssign.append(self.get_location_from_balance_list())
			# pick what we're going to put in our accessible space
			itemsToAssign = []
			if len(locationsToAssign) < len(self.assignQueue) + max(keystoneCount - self.inventory["KS"], 0) + max(
					mapstoneCount - self.inventory["MS"], 0):
				# we've painted ourselves into a corner, try again
				if not self.reservedLocations:
					if self.playerID == 1:
						self.sharedMap = {}
					if depth > self.playerCount * self.playerCount:
						return
					return self.placeItems(seed, depth + 1)
				locationsToAssign.append(self.reservedLocations.pop(0))
				locationsToAssign.append(self.reservedLocations.pop(0))
			for i in range(0, len(locationsToAssign)):
				if self.assignQueue:
					itemsToAssign.append(self.assign(self.assignQueue.pop(0)))
				elif self.inventory["KS"] < keystoneCount:
					itemsToAssign.append(self.assign("KS"))
				elif self.inventory["MS"] < mapstoneCount:
					itemsToAssign.append(self.assign("MS"))
				elif self.balanced and self.itemCount == 0:
					itemsToAssign.append(self.balanceListLeftovers.pop(0))
					self.itemCount += 1
				else:
					itemsToAssign.append(self.assign_random())
				self.itemCount -= 1

			# force assign things if using --prefer-path-difficulty
			if self.pathDifficulty:
				for item in list(itemsToAssign):
					if item in self.skillsOutput or item in self.eventsOutput:
						self.preferred_difficulty_assign(item, locationsToAssign)
						itemsToAssign.remove(item)

			# shuffle the items around and put them somewhere
			self.random.shuffle(itemsToAssign)
			for i in range(0, len(locationsToAssign)):
				self.assign_to_location(itemsToAssign[i], locationsToAssign[i])

			currentGroupSpoiler = ""

			if spoilerPath:
				currentGroupSpoiler += ("	Forced pickups: " + str(spoilerPath) + "\n")

			for skill in self.skillsOutput:
				if skill in self.spoilerGroup:
					for instance in self.spoilerGroup[skill]:
						currentGroupSpoiler += "	" + instance
					if skill in seedDifficultyMap:
						self.seedDifficulty += groupDepth * seedDifficultyMap[skill]

			for event in self.eventsOutput:
				if event in self.spoilerGroup:
					for instance in self.spoilerGroup[event]:
						currentGroupSpoiler += "	" + instance

			for key in self.spoilerGroup:
				if key[:2] == "TP":
					for instance in self.spoilerGroup[key]:
						currentGroupSpoiler += "	" + instance

			for instance in self.spoilerGroup["MS"]:
				currentGroupSpoiler += "	" + instance

			for instance in self.spoilerGroup["KS"]:
				currentGroupSpoiler += "	" + instance

			for instance in self.spoilerGroup["HC"]:
				currentGroupSpoiler += "	" + instance

			for instance in self.spoilerGroup["EC"]:
				currentGroupSpoiler += "	" + instance

			if currentGroupSpoiler:
				groupDepth += 1
				self.currentAreas.sort()

				spoilerStr += str(groupDepth) + ": " + str(self.currentAreas) + " {\n"

				spoilerStr += currentGroupSpoiler

				spoilerStr += "}\n"

			self.currentAreas = []

			# open all reachable doors (for the next iteration)
			for area in self.doorQueue.keys():
				if self.doorQueue[area].target not in self.areasReached:
					difficulty = self.doorQueue[area].cost()[2]
					self.seedDifficulty += difficulty * difficulty
				self.reach_area(self.doorQueue[area].target)
				if self.doorQueue[area].target in self.areasRemaining:
					self.areasRemaining.remove(self.doorQueue[area].target)
				self.areas[area].remove_connection(self.doorQueue[area])

			for area in self.mapQueue.keys():
				if self.mapQueue[area].target not in self.areasReached:
					difficulty = self.mapQueue[area].cost()[2]
					self.seedDifficulty += difficulty * difficulty
				self.reach_area(self.mapQueue[area].target)
				if self.mapQueue[area].target in self.areasRemaining:
					self.areasRemaining.remove(self.mapQueue[area].target)
				self.areas[area].remove_connection(self.mapQueue[area])

			locationsToAssign = []
			self.spoilerGroup = {"MS": [], "KS": [], "EC": [], "HC": []}

			self.doorQueue = OrderedDict()
			self.mapQueue = OrderedDict()
			spoilerPath = ""

		if self.balanced:
			for item in self.balanceList:
				self.outputStr += item[2]

		spoilerStr = self.flags + "|" + str(seed) + "\n" + "Difficulty Rating: " + str(self.seedDifficulty) + "\n" + spoilerStr
		self.random.shuffle(self.eventList)
		for event in self.eventList:
			self.outputStr += event

		return (self.outputStr, spoilerStr)
