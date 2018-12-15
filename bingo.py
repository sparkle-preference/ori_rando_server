import logging as log
from random import choice, randint, sample

# constants
DUNGEONS = ["Forlorn Ruins", "Ginso Tree", "Mount Horu"]
AREAS_WITH_TPS = ["Ginso Tree", "Forlorn Ruins", "Moon Grotto", "Hollow Grove", "Sunken Glades",
    "Blackroot Burrows", "Thornfelt Swamp", "Valley of the Wind", "Sorrow Pass", "Lost Grove", "Mount Horu"]
AREAS = AREAS_WITH_TPS + ["Misty Woods"]
AREAS_WITH_MAPSTONES = ["Sunken Glades", "Forlorn Ruins", "Moon Grotto", "Blackroot Burrows", "Thornfelt Swamp", "Valley of the Wind", "Sorrow Pass", "Mount Horu", "Hollow Grove"]
SKILLS = ["Wall Jump", "Charge Flame", "Double Jump", "Bash", "Stomp", "Glide", "Climb", "Charge Jump", "Dash", "Grenade"]
EVENTS = ["Water Vein", "Clean Water", "Gumon Seal", "Wind Restored", "Sunstone", "Warmth Returned"]
BONUS_PICKUPS = ["Extra Double Jump", "Extra Air Dash", "Explosion Power Upgrade", "Charge Dash Efficiency", "Spirit Light Efficiency"]


class Card(object):
    @staticmethod
    def singletons(is_rando):
        tuples = [
            ("StomplessOrCoreSkip", "Fast Stompless or Core Skip"),
            ("Triforce", "Collect the Triforce AC"),
            ("Wilhelm", "Hear Wilhelm's scream"),
            ("CatMouse", "Escape Kuro outside of Forlorn"),
            ("DrownFrog", "Drown an amphibian"),
            ("DrainSwamp", "Drain the swamp"),
            ("BanelingKill, ""Kill an enemy with a baneling"),
            ("L4 lava", "Escape the L4 Lava")
        ] + [
            ("UselessPickup", "Warmth Returned or 1 exp"),
            ("QuadJump", "Quad Jump"),
            ("Regen", "Collect a regen pickup")
        ] if is_rando else [("TripleJump", "Triple Jump")]
        return [{'name': name, 'text': text} for (name, text) in tuples]
    @staticmethod
    def all_cards(is_rando):
        return [{'text': c.get(is_rando), 'name': c.__name__} for c in Card.__subclasses__() if c.valid(is_rando)] + Card.singletons(is_rando)

    @staticmethod
    def get_cards(is_rando, gridSize=5):
        cards = gridSize * gridSize
        c = Card.all_cards(is_rando)
        if cards > len(c):
            log.warning("Not enough cards! %s>%s" % (cards, len(c)))
            cards = 25
        return sample(c, cards)
    @staticmethod
    def get_json(is_rando, cards=25):
        return "[%s]" % ",\n".join(['{"name": "%s"}' % card["text"] for card in Card.get_cards(is_rando, cards)])

    @staticmethod
    def valid(rando):
        return True

class Rando():
    @staticmethod
    def valid(rando):
        return rando

class HoruRoomXorY(Card):
    @staticmethod
    def get(rando):
        return "Complete %s or %s" % (choice(["L1", "L2", "L3", "L4"]), choice(["R1", "R2", "R3", "R4"]))

class CollectNMapstones(Card):
    @staticmethod
    def get(rando):
        return "Collect %s mapstones" % (randint(4, 6) + randint(0, 2) + randint(0, 1) + randint(0, 1))

class OpenNDoors(Card):
    @staticmethod
    def get(rando):
        return "Open %s keystone doors" % randint(3, 6)

class BreakNBarriers(Card):
    @staticmethod
    def get(rando):
        return "Break %s breakable walls" % randint(3, 6)

class BreakNVertBarriers(Card):
    @staticmethod
    def get(rando):
        return "Break %s breakable floors/ceilings" % randint(4, 8)


class OpenNrgyDoors(Card):
    @staticmethod
    def get(rando):
        return "Open %s energy doors" % randint(2, 4)

class MaxAbilityTree(Card):
    @staticmethod
    def get(rando):
        return "Get %s abilities in the %s tree" % ("all" if rando else randint(6,10), choice(["Red", "Purple", "Blue"]))

class HaveNKeystones(Card):
    @staticmethod
    def get(rando):
        return "Have %s unspent keystones" % randint(8, 16)

class DieToXorY(Card):
    @staticmethod
    def get(rando):
        return "Die to %s or %s" % tuple(sample(["Kuro (anywhere)", "Forlorn Approach Baneling", "Horu Lava", "Spidersack spikes", "Misty Baneling", "Lightning above Sorrow Pass", "Lasers above far right Forlorn plant", "Lost Grove Bottom Lasers"], 2))

class NTotalPickups(Card):
    @staticmethod
    def get(rando):
        return "Collect %s pickups" % (randint(60, 140) if rando else randint(50, 90))

class GrenadeLocked(Card):
    @staticmethod
    def get(rando):
        return "Light %s grenade-lanterns" % randint(3, 6)

class CollectNPlants(Card):
    @staticmethod
    def get(rando):
        return "Break %s Plants" % randint(3, 6)

class CollectNUnderwater(Card):
    @staticmethod
    def get(rando):
        return "Collect %s pickups underwater" % randint(2, 5)

class NHealth(Card):
    @staticmethod
    def get(rando):
        return "Collect %s Health Cells" % randint(4, 8)

class NPoints(Card):
    @staticmethod
    def get(rando):
        return "Level up %s abilities in any tree" % randint(12, 24)

# disabled until integration
# class ReachLevelN(Card):
#	@staticmethod
#	def get(rando):
#		return "Reach level %s" % randint(8,16)

class Nrgy(Card):
    @staticmethod
    def get(rando):
        return "Collect %s Energy Cells" % randint(4, 8)

class CollectNUnderwater(Card):
    @staticmethod
    def get(rando):
        return "Collect %s pickups underwater" % randint(2, 5)

class EnterArea(Card):
    @staticmethod
    def get(rando):
        return "Enter %s" % choice(["Lost Grove", "Sorrow Pass", "Misty Woods"] + DUNGEONS)

class EnterAreaXorY(Card):
    @staticmethod
    def get(rando):
        return "Enter %s or %s" % tuple(sample(["Lost Grove", "Sorrow Pass", "Misty Woods"] + DUNGEONS, 2))

class DungeonEscape(Card):
    @staticmethod
    def get(rando):
        return "Complete the %s escape" % choice(DUNGEONS)

class NEscapeS(Card):
    @staticmethod
    def get(rando):
        return "Complete %s dungeon escape(s)" % randint(1, 3)

class ActivateNTPs(Card):
    @staticmethod
    def get(rando):
        return "Activate %s Spirit Wells" % randint(2, 5)

class StompPegXorY(Card):
    @staticmethod
    def get(rando):
        return "Stomp the peg(s) at %s or %s" % tuple(sample(["Hollow Groves Spider Lake", "Kuro CS Tree", "Sorrow Tumbleweed Area", "Swamp Post-Stomp", "Above Death Gauntlet"], 2))
    
class ActivateNTrees(Card):
    @staticmethod
    def get(rando):
        return "Activate %s Trees" % (randint(2, 5) + randint(1, 3) + randint(0, 2))


class KillByLevelup(Card):
    @staticmethod
    def get(rando):
        return "Kill %s enemies by leveling up" % randint(2, 6)

class MapstoneN(Card):
    @staticmethod
    def get(rando):
        return "Turn in Mapstone %s" % randint(2, 9)

class XorYTp(Rando, Card):
    @staticmethod
    def get(rando):
        return "Find or Activate the %s, %s, or %s TP" % tuple(sample(AREAS_WITH_TPS, 3))

class XorYFullClear(Card):
    @staticmethod
    def get(rando):
        return "Get every pickup in %s, %s, or %s" % tuple(sample(AREAS_WITH_TPS, 3))

class FindXInY(Card):
    @staticmethod
    def get(rando):
        return "Get %s pickups from %s" % (randint(2, 10), choice(AREAS_WITH_TPS))

class XorYEvent(Card):
    @staticmethod
    def get(rando):
        return "%s or %s" % tuple(sample(EVENTS, 2))

class XandYMapstoneTurnins(Card):
    @staticmethod
    def get(rando):
        return "Activate the %s and %s Mapstones" % tuple(sample(AREAS_WITH_MAPSTONES, 2))

class GarbagePickupXorY(Card):
    @staticmethod
    def get(rando):
        return "Get the pickup at %s or %s" % tuple(sample(["Lost Grove Underwater AC", "Sunstone", "Forlorn Escape Plant", "Validation Exp", "Gladezer EC", "Forlorn HC", "R3 Plant", "Misty Grenade Pickup", "Valley Enterance Long Swim EC"], 2))

class EventLocationXorY(Card):
    @staticmethod
    def get(rando):
        return "Collect the pickup at vanilla %s or %s" % tuple(sample(["Water Vein", "Clean Water", "Gumon Seal", "Wind Restored", "Sunstone"], 2))

class WatchXorY(Card):
    @staticmethod
    def get(rando):
        return "Watch (don't skip) %s or %s" % tuple(sample(["Racist Dad 3", "Spirit Tree Cutscene", "Post-Forlorn Escape Cutscene", "Racist Dad 2", "Sunstone cutscene", "Post-Ginso Escape cutscene"], 2))

class XorYTree(Card):
    @staticmethod
    def get(rando):
        return "Get the %s or %s Tree" % tuple(sample(SKILLS, 2))

class KillEnemyXorY(Card):
    @staticmethod
    def get(rando):
        return "Kill %s or %s" % tuple(sample(["Stomp Tree Rhino", "Grotto Miniboss", "Lower Ginso Miniboss", "Lost Grove Fight Room", "Upper Ginso Miniboss", "Misty Minibosses", "Horu Final Miniboss"], 2))

class AltRAfter(Rando, Card):
    @staticmethod
    def get(rando):
        return "Alt-r immediately after you Find %s" % choice(["1 Experience"] + SKILLS + EVENTS)

class CollectNSkills(Rando, Card):
    @staticmethod
    def get(rando):
        return "Collect %s Skills" % (randint(2, 6) + randint(1, 3) + randint(0, 1))

class XorYSkill(Rando, Card):
    @staticmethod
    def get(rando):
        return "%s or %s" % tuple(sample(SKILLS, 2))

class XandYSkill(Rando, Card):
    @staticmethod
    def get(rando):
        return "%s and %s" % tuple(sample(SKILLS, 2))

class XorYBonus(Rando, Card):
    @staticmethod
    def get(rando):
        return "%s or %s" % tuple(sample(BONUS_PICKUPS, 2))
