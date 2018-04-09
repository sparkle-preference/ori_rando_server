import argparse
import random
from sys import exit

def split_seed(seed, gameId, player, max_players, hot=False, dk=True, sk=True, ev=True, rb=True, tp=True):
	dungeon_keys = ["RB|17", "RB|19", "RB|21", "EV|0", "EV|2", "EV|4"] # WV, GS, SS
	skills = ["SK|3", "SK|2", "SK|50", "SK|4", "SK|5", "SK|14", "SK|0", "SK|12", "SK|51", "SK|8"] # WJ, CFlame, Dash, Stomp, DJ, Glide, Bash, Climb, Grenade, CJ
	events = ["EV|1", "EV|3"] # Water, Wind
	bonuses = ["RB|8","RB|9","RB|10", "RB|11", "RB|12", "RB|6", "RB|13", "RB|15"] 
	teleporters = ["TP|Forlorn", "TP|Swamp", "TP|Valley", "TP|Grove", "TP|Grotto", "TP|Sorrow"]	
	pickups = (dungeon_keys if dk else []) + (skills if sk else []) + (events if ev else []) + (bonuses if rb else []) + (teleporters if tp else [])
	random.seed(seed)
	prerolled_blunts = {p : random.randint(1,100) for p in pickups}

	random.seed(seed)
	outlines = []
	for line in seed.split("\n"):
		if any(i in line for i in pickups):
			if player == random.randint(1, max_players):
				outlines.append(line)
			else:
				outln = line.split("|")
				repl_exp = prerolled_blunts["%s|%s" % (outln[1],outln[2])]
				outln[1] = "EV" if hot else "EX"
				outln[2] = "5" if hot else str(repl_exp)
				outlines.append("|".join(outln))
		else:
			outlines.append(line)
	outlines[0] = "Sync%s.%s," %(gameId,player) + outlines[0]
	return "\n".join(outlines)