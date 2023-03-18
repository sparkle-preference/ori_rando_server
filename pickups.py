import logging as log

from enums import ShareType
from util import add_single, inc_stackable

class Pickup(object):
    @staticmethod
    def subclasses():
        return [Skill, Event, Teleporter, Upgrade, Experience, AbilityCell, HealthCell, EnergyCell, Keystone, 
                Mapstone, Message, Hint, Relic, Multiple, Repeatable, Warp, WarpSave, Nothing]
    stacks = False
    has_children = False
    int_id = True
    share_type = ShareType.NOT_SHARED
    def __eq__(self, other):
        return isinstance(other, Pickup) and self.id == other.id and self.code == other.code
    @classmethod
    def from_str(cls, code_id):
        code, _, pid = code_id.partition("|")
        return cls.n(code, pid)

    @classmethod
    def n(cls, code, id):
        for subcls in Pickup.subclasses():
            if code == subcls.code:
                return subcls(id)
        return None
    @classmethod
    def name(cls, code, id):
        for subcls in Pickup.subclasses():
            if id and code == subcls.code and subcls(id):
                return subcls(id).name
        return "%s|%s" % (code, id)
    def add_to_bitfield(self, bits_int, remove=False):
        if self.stacks:
            return inc_stackable(bits_int, self.bit, remove)
        return add_single(bits_int, self.bit, remove)
    def is_shared(self, share_types):
        return self.share_type in share_types

class Skill(Pickup):
    bits = {0: 1, 2: 2, 3: 4, 4: 8, 5: 16, 8: 32, 12: 64, 14: 128, 50: 256, 51: 512, 15: 1024}
    names = {0: "Bash", 2: "Charge Flame", 3: "Wall Jump", 4: "Stomp", 5: "Double Jump", 8: "Charge Jump", 12: "Climb", 14: "Glide", 50: "Dash", 51: "Grenade", 15: "Spirit Flame"}
    code = "SK"
    share_type = ShareType.SKILL
    def __new__(cls, id):
        id = int(id)
        if id not in Skill.bits or id not in Skill.names:
            return None
        inst = super(Skill, cls).__new__(cls)
        inst.id, inst.bit, inst.name = id, Skill.bits[id], Skill.names[id]
        return inst

class Event(Pickup):
    bits = {0: 1, 1: 2, 2: 4, 3: 8, 4: 16, 5: 32}
    names = {0: "Water Vein", 1: "Clean Water", 2: "Gumon Seal", 3: "Wind Restored", 4: "Sunstone", 5: "Warmth Returned"}
    code = "EV"
    share_type = ShareType.EVENT
    def __new__(cls, id):
        id = int(id)
        if id not in Event.bits or id not in Event.names:
            return None
        inst = super(Event, cls).__new__(cls)
        inst.id, inst.bit, inst.name = id, Event.bits[id], Event.names[id]
        return inst

class Teleporter(Pickup):
    bits = {"Grove": 1, "Swamp": 2, "Grotto": 4, "Valley": 8, "Forlorn": 16, "Sorrow": 32, "Ginso": 64, "Horu": 128, "Blackroot": 256, "Glades": 512}
    code = "TP"
    share_type = ShareType.TELEPORTER
    int_id = False
    def __new__(cls, id):
        if id not in Teleporter.bits:
            return None
        inst = super(Teleporter, cls).__new__(cls)
        inst.id, inst.bit, inst.name = id, Teleporter.bits[id], id + " teleporter"
        return inst

class Upgrade(Pickup):
    stacking = set([6, 13, 15, 17, 19, 21])
    name_only = set([0, 1, 2, 34, 35, 81, 1100] + range(40, 50))
    maxes = {17: 3, 19: 3, 21: 3}
    names = {
            17: "Water Vein Shard", 19: "Gumon Seal Shard", 21: "Sunstone Shard", 28: "Warmth Fragment", 6: "Attack Upgrade", 13: "Health Regeneration", 2: "Go Home",
            15: "Energy Regeneration", 8: "Explosion Power Upgrade", 9: "Spirit Light Efficiency", 10: "Extra Air Dash", 11: "Charge Dash Efficiency",
            12: "Extra Double Jump", 0: "Mega Health", 1: "Mega Energy", 30: "Bleeding", 31: "Health Drain", 32: "Energy Drain", 33: "Skill Velocity Upgrade",
            101: "Polarity Shift", 102: "Gravity Swap", 103: "Extreme Speed", 104: "Teleport: Last AltR", 105: "Teleport: Soul Link", 106: "Respec", 107: "Level Explosion", 110: "Invincibility",
            81: "Stompnade Hint", 40: "Remove Wall Jump", 41: "Remove Charge Flame", 42: "Remove Double Jump", 43: "Remove Bash", 44: "Remove Stomp", 45: "Remove Glide",
            46: "Remove Climb", 47: "Remove Charge Jump", 48: "Remove Dash", 49: "Remove Grenade", 34: "Disable Alt+R", 35: "Enable Alt+R", 36: "Underwater Skill Usage", 109: "Timewarp",
            111: "Wither", 113: "Bash/Stomp Damage", 1587: "Credit Warp", 37: "Jump Upgrade",
            900: "Wall Jump Tree", 901: "Charge Flame Tree", 902: "Double Jump Tree", 903: "Bash Tree", 904: "Stomp Tree", 905: "Glide Tree", 906: "Climb Tree",
            907: "Charge Jump Tree", 908: "Dash Tree", 909: "Grenade Tree", 911: "Glades Relic", 912: "Grove Relic", 913: "Grotto Relic", 914: "Blackroot Relic",
            915: "Swamp Relic", 916: "Ginso Relic", 917: "Valley Relic", 918: "Misty Relic", 919: "Forlorn Relic", 920: "Sorrow Relic", 921: "Horu Relic", 1100: "Enable Frag Sense",
        }

    bits = {17: 1, 19: 4, 21: 16, 6: 64, 13: 256, 15: 1024, 8: 4096, 9: 8192, 10: 16384, 11: 32768, 12: 65536}
    code = "RB"
    def __new__(cls, id):
        id = int(id)
        if id in Upgrade.name_only:
            inst = super(Upgrade, cls).__new__(cls)
            inst.id, inst.share_type, inst.name, inst.max = id, ShareType.NOT_SHARED, Upgrade.names[id], None
            if id in [81]:
                inst.share_type = ShareType.SKILL
            return inst
        if id not in Upgrade.names:
            return None
        inst = super(Upgrade, cls).__new__(cls)
        inst.id, inst.name = id, Upgrade.names[id]
        inst.bit = Upgrade.bits[id] if id in Upgrade.bits else -1
        inst.max = Upgrade.maxes[id] if id in Upgrade.maxes else None
        inst.stacks = id in Upgrade.stacking
        if id in [17, 19, 21, 28]:  # shards and warmth fragments are world events
            inst.share_type = ShareType.EVENT
        elif id >= 900:  # trees and relics are misc pickups
            inst.share_type = ShareType.MISC
        else:
            inst.share_type = ShareType.UPGRADE
        return inst

class Experience(Pickup):
    code = "EX"
    def __new__(cls, id):
        id = int(id)
        inst = super(Experience, cls).__new__(cls)
        inst.id, inst.bit, inst.name = id, None, "%s experience" % id
        return inst

class AbilityCell(Pickup):
    code = "AC"
    def __new__(cls, id):
        id = int(id)
        inst = super(AbilityCell, cls).__new__(cls)
        inst.id, inst.bit, inst.name = id, None, "Ability Cell"
        return inst

class HealthCell(Pickup):
    code = "HC"
#    share_type = ShareType.MISC
    def __new__(cls, id):
        id = int(id)
        inst = super(HealthCell, cls).__new__(cls)
        inst.id, inst.bit, inst.name = id, None, "Health Cell"
        return inst

class EnergyCell(Pickup):
    code = "EC"
#    share_type = ShareType.MISC
    def __new__(cls, id):
        id = int(id)
        inst = super(EnergyCell, cls).__new__(cls)
        inst.id, inst.bit, inst.name = id, None, "Energy Cell"
        return inst

class Mapstone(Pickup):
    code = "MS"
    def __new__(cls, id):
        id = int(id)
        inst = super(Mapstone, cls).__new__(cls)
        inst.id, inst.bit, inst.name = id, None, "Mapstone"
        return inst

class Keystone(Pickup):
    code = "KS"
    def __new__(cls, id):
        id = int(id)
        inst = super(Keystone, cls).__new__(cls)
        inst.id, inst.bit, inst.name = id, None, "Keystone"
        return inst

class Message(Pickup):
    code = "SH"
    int_id = False
    def __new__(cls, id):
        inst = super(Message, cls).__new__(cls)
        inst.id, inst.bit, inst.name = id, None, "Message: " + id
        return inst

class Hint(Pickup):
    code = "HN"
    int_id = False
    def __new__(cls, id):
        inst = super(Hint, cls).__new__(cls)
        inst.id, inst.bit = id, None
        hintParts = id.split('-')
        inst.name = "Hint: %s for %s" % (hintParts[1], hintParts[2])
        return inst

class Multiple(Pickup):
    code = "MU"
    int_id = False
    has_children = True
    def __new__(cls, id):
        inst = super(Multiple, cls).__new__(cls)
        inst.id, inst.bit = id, None
        subparts = id.split('/')
        inst.children = []
        while len(subparts) > 1:
            try:
                c = Pickup.n(subparts[0], subparts[1])
                if c:
                    inst.children.append(c)
            except Exception as e:
                log.warning("failed creating pickup %s|%s in multipickup %s: %s", subparts[0], subparts[1], id, e)
            subparts = subparts[2:]
        inst.name = ", ".join([child.name for child in inst.children])
        return inst
    @classmethod
    def with_pickups(cls, children):
        if not children:
            log.warning("Can't build empty multipickup.")
            return None
        ids = []
        for child in children:
            if child.has_children:
                for grandchild in child.children:
                    ids += [grandchild.code, str(grandchild.id)]
            else:
                ids += [child.code, str(child.id)]
        return cls.__new__(cls, "/".join(ids))
    def add_pickups(self, children):
        for child in children:
            self.add_pickup(child)

    def add_pickup(self, child):
        if child.has_children:
            self.add_pickups(child.children)
        else:
            self.id += "/%s/%s" % (child.code, child.id)
            self.children.append(child)
    def is_shared(self, share_types):
        return any([c.is_shared(share_types) for c in self.children])

class Repeatable(Multiple):
    code = "RP"
    def __new__(cls, id):
        inst = super(Repeatable, cls).__new__(cls, id)
        inst.name = "Repeatable: " + inst.name
        return inst
    # repeatable pickups can't be shared
    def is_shared(self, share_types):
        return False

class Relic(Pickup):
    code = "WT"
    int_id = False
    share_type = ShareType.MISC
    def __new__(cls, id):
        inst = super(Relic, cls).__new__(cls)
        inst.id, inst.bit, inst.name = id, None, "Relic"
        return inst

class Warp(Pickup):
    code = "WP"
    int_id = False
    def __new__(cls, id):
        inst = super(Warp, cls).__new__(cls)
        inst.id, inst.bit, inst.name = id, None, "Warp to " + id
        return inst

class Nothing(Pickup):
    code = "NO"
    def __new__(cls, id):
        inst = super(Nothing, cls).__new__(cls)
        inst.id, inst.bit, inst.name = id, None, "Nothing"
        return inst


class WarpSave(Pickup):
    code = "WS"
    int_id = False
    def __new__(cls, id):
        inst = super(WarpSave, cls).__new__(cls)
        inst.id, inst.bit, inst.name = id, None, "Warp to " + id + " and save"
        return inst