import argparse
import random
from sys import exit

def split_seed(seed, gameId, player, max_players, hot=False, sk=True, ev=True, rb=True):
	shards = ["RB|17", "RB|19", "RB|21"] # WV, GS, SS
	stacking_bonuses = ["RB|6", "RB|13", "RB|15"] # Spirit Flame Upgrade, Health Regen, Energy Regen
	skills = ["SK|3", "SK|2", "SK|50", "SK|4", "SK|5", "SK|14", "SK|0", "SK|12", "SK|51", "SK|8"] # WJ, CFlame, Dash, Stomp, DJ, Glide, Bash, Climb, Grenade, CJ
	events = ["EV|0", "EV|1","EV|2", "EV|3", "EV|4"] # Water, Wind, keys
	bonuses = ["RB|8","RB|9","RB|10", "RB|11", "RB|12"] # Explosion Power Upgrade, Spirit Light Efficiency, Extra Air Dash, Charge Dash Efficiency, Extra DJ
	
	pickups = shards + stacking_bonuses + (skills if sk else []) + (events if ev else []) + (bonuses if rb else [])
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
				outln[2] = "5" if hot else repl_exp 
				outlines.append("|".join(outln))
		else:
			outlines.append(line)
	outlines[0] = "Sync%s.%s," %(gameId,player) + outlines[0]
	return "\n".join(outlines)