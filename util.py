from protorpc import messages

class GameMode(messages.Enum):
	SHARED = 1
	SWAPPED = 2				#not implemented, needs client work
	SPLITSHARDS = 3


class ShareType(messages.Enum):
	DUNGEON_KEY = 1
	UPGRADE = 2
	SKILL = 3
	EVENT = 4
	TELEPORTER = 5

share_map = {
	"keys": ShareType.DUNGEON_KEY,
	"upgrades": ShareType.UPGRADE,
	"skills": ShareType.SKILL,
	"events": ShareType.EVENT,
	"teleporters": ShareType.TELEPORTER
}
rev_map = {v:k for k,v in share_map.iteritems()}

def share_from_url(s):
	return share_map[s]

def url_from_share(share_types):
	"+".fold(rev_map[type] for type in share_types)