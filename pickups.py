from enums import ShareType
from util import add_single, inc_stackable

class Pickup(object):
    @staticmethod
    def subclasses():
        return [Skill, Event, Teleporter, Upgrade, Experience, AbilityCell, HealthCell, EnergyCell, Keystone, Mapstone, Message, Hint, Relic]
    
    stacks = False
    def __eq__(self, other):
        return isinstance(other, Pickup) and self.id == other.id
    @classmethod
    def n(cls, code, id):
        for subcls in Pickup.subclasses():
            if code == subcls.code:
                return subcls(id)
        return None
    @classmethod
    def name(cls, code, id):
        for subcls in Pickup.subclasses():
            if code == subcls.code and subcls(id):
                return subcls(id).name
        return "%s|%s" % (code, id)
    
    def add_to_bitfield(self, bits_int, remove=False):
        if self.stacks:
            return inc_stackable(bits_int, self.bit, remove)
        return add_single(bits_int, self.bit, remove)



class Skill(Pickup):
    bits = {0:1, 2:2, 3:4, 4:8, 5:16, 8:32, 12:64, 14:128, 50:256, 51:512}
    names = {0:"Bash", 2:"Charge Flame", 3:"Wall Jump", 4:"Stomp", 5:"Double Jump",8:"Charge Jump",12:"Climb",14:"Glide",50:"Dash",51:"Grenade"}
    share_type = ShareType.SKILL
    code = "SK"
    def __new__(cls, id):
        id = int(id)
        if id not in Skill.bits or id not in Skill.names:
            return None
        inst = super(Skill, cls).__new__(cls)
        inst.id, inst.bit, inst.name = id, Skill.bits[id], Skill.names[id]
        return inst

class Event(Pickup):
    bits = {0:1, 1:2, 2:4, 3:8, 4:16, 5:32}
    names = {0:"Water Vein", 1:"Clean Water", 2:"Gumon Seal", 3:"Wind Restored", 4:"Sunstone", 5:"Warmth Returned"}
    code = "EV"
    def __new__(cls, id):
        id = int(id)
        if id not in Event.bits or id not in Event.names:
            return None
        inst = super(Event, cls).__new__(cls)
        inst.id, inst.bit, inst.name = id, Event.bits[id], Event.names[id]
        inst.share_type = ShareType.EVENT
        return inst


class Teleporter(Pickup):
    bits = {"Grove":1, "Swamp":2, "Grotto":4, "Valley":8, "Forlorn":16, "Sorrow":32, "Ginso": 64, "Horu": 128}
    code = "TP"
    def __new__(cls, id):
        if id not in Teleporter.bits:
            return None
        inst = super(Teleporter, cls).__new__(cls)
        inst.id, inst.bit, inst.name = id, Teleporter.bits[id], id + " teleporter"
        inst.share_type = ShareType.TELEPORTER
        return inst

class Upgrade(Pickup):
    stacking= set([6,13,15,17,19,21])
    name_only = set([0, 1, 2])
    maxes = {17: 3, 19: 3, 21: 3}
    names = {17:  "Water Vein Shard", 19: "Gumon Seal Shard", 21: "Sunstone Shard", 28: "Warmth Fragment", 6: "Spirit Flame Upgrade", 13: "Health Regeneration", 2: "Go Home",
            15: "Energy Regeneration", 8: "Explosion Power Upgrade", 9:  "Spirit Light Efficiency", 10: "Extra Air Dash", 11:  "Charge Dash Efficiency", 
            12: "Extra Double Jump", 0: "Mega Health", 1: "Mega Energy", 30: "Bleeding", 31: "Lifesteal", 32: "Manavamp", 33: "Skill Velocity Upgrade",
            101: "Polarity Shift", 102: "Gravity Swap", 103: "Drag Racer", 104: "Airbrake"}
    bits = {17:1, 19:4, 21:16, 6:64, 13:256, 15:1024, 8:4096, 9:8192, 10:16384, 11:32768, 12:65536}
    code = "RB"
    def __new__(cls, id):
        id = int(id)
        if id in Upgrade.name_only:
            inst = super(Upgrade, cls).__new__(cls)
            inst.id, inst.share_type, inst.name = id, ShareType.NOT_SHARED, Upgrade.names[id]
            return inst
        if id not in Upgrade.names:
            return None
        inst = super(Upgrade, cls).__new__(cls)
        inst.id, inst.name = id, Upgrade.names[id]
        inst.bit = Upgrade.bits[id] if id in Upgrade.bits else -1
        inst.max = Upgrade.maxes[id] if id in Upgrade.maxes else None
        inst.stacks = id in Upgrade.stacking
        if id in [17, 19, 21]:  # shards are world events
            inst.share_type = ShareType.EVENT
        elif id == 28:  # warmth fragments are misc pickups
            inst.share_type = ShareType.MISC
        else:
            inst.share_type = ShareType.UPGRADE
        return inst

class Experience(Pickup):
    code="EX"
    def __new__(cls, id):
        id = int(id)
        inst = super(Experience, cls).__new__(cls)
        inst.id, inst.bit, inst.name = id, None, "%s experience" % id
        inst.share_type = ShareType.NOT_SHARED
        return inst

class AbilityCell(Pickup):
    code="AC"
    def __new__(cls, id):
    
        id = int(id)
        inst = super(AbilityCell, cls).__new__(cls)
        inst.id, inst.bit, inst.name = id, None, "Ability Cell"
        inst.share_type = ShareType.NOT_SHARED
        return inst

class HealthCell(Pickup):
    code="HC"
    def __new__(cls, id):
        id = int(id)
        inst = super(HealthCell, cls).__new__(cls)
        inst.id, inst.bit, inst.name = id, None, "Health Cell"
        inst.share_type = ShareType.NOT_SHARED
        return inst

class EnergyCell(Pickup):
    code="EC"
    def __new__(cls, id):
        id = int(id)
        inst = super(EnergyCell, cls).__new__(cls)
        inst.id, inst.bit, inst.name = id, None, "Energy Cell"
        inst.share_type = ShareType.NOT_SHARED
        return inst

class Mapstone(Pickup):
    code="MS"
    def __new__(cls, id):
        id = int(id)
        inst = super(Mapstone, cls).__new__(cls)
        inst.id, inst.bit, inst.name = id, None, "Mapstone"
        inst.share_type = ShareType.NOT_SHARED
        return inst

class Keystone(Pickup):
    code="KS"
    def __new__(cls, id):
        id = int(id)
        inst = super(Keystone, cls).__new__(cls)
        inst.id, inst.bit, inst.name = id, None, "Keystone"
        inst.share_type = ShareType.NOT_SHARED
        return inst

class Message(Pickup):
    code = "SH"
    def __new__(cls, id):
        inst = super(Message, cls).__new__(cls)
        inst.id, inst.bit, inst.name = id,None, "Message: " + id
        inst.share_type = ShareType.NOT_SHARED
        return inst

class Hint(Pickup):
    code = "HN"
    def __new__(cls, id):
        inst = super(Hint, cls).__new__(cls)
        inst.id, inst.bit, inst.name = id,None, "Hint: " + id
        inst.share_type = ShareType.NOT_SHARED
        return inst

class Relic(Pickup):
    code = "WT"
    def __new__(cls, id):
        inst = super(Relic, cls).__new__(cls)
        inst.id, inst.bit, inst.name = id,None, "Relic"
        inst.share_type = ShareType.MISC
        return inst
    