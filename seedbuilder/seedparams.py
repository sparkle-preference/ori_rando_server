from Enum import LogicPath, Variation, KeyMode
from collections import namedtuple

MultiplayerParams = namedtuple("MultiplayerParams",["playerCount", "gameType", "shareTypes", "seedType"])
class SeedParams(object):
	def __init__(self, seed, variations, logic_paths, key_mode, pathdiff = "Normal", playerCount = 1, tracking = True, ):
			

