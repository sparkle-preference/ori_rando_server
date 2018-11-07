from seedbuilder.areas import get_areas
from collections import defaultdict, Counter
from pickups import Pickup

class PlayerState(object):
    name_from_id = {
        ("SK", 0): 'Bash', ("SK", 2): 'ChargeFlame', ("SK", 3): 'WallJump', ("SK", 4): 'Stomp', ("SK", 5): 'DoubleJump',
        ("SK", 8): 'ChargeJump', ("SK", 12): 'Climb', ("SK", 14): 'Glide', ("SK", 50): 'Dash', ("SK", 51): 'Grenade',
        ("EV", 0): 'GinsoKey', ("EV", 1): 'Water', ("EV", 2): 'ForlornKey', ("EV", 3): 'Wind', ("EV", 4): 'HoruKey',
        ("TP", "Swamp"): 'TPSwamp', ("TP", "Grove"): 'TPGrove', ("TP", "Valley"): 'TPValley',
        ("TP", "Grotto"): 'TPGrotto', ("TP", "Forlorn"): 'TPForlorn', ("TP", "Sorrow"): 'TPSorrow'
    }

    def __init__(self, pickinfos):
        self.has = Counter()
        self.has["HC"] = 3
        wv = ss = gs = 0
        pickinfos = [x for x in pickinfos if len(x) == 4]
        for code, id, count, removed in pickinfos:
            if code in ["EX"]:
                continue
            id = int(id) if Pickup.n(code, id).int_id else id
            if (code, id) in PlayerState.name_from_id:
                self.has[PlayerState.name_from_id[(code, id)]] = (0 if removed else count)
            elif code == "RB":
                if id == 17:
                    wv += (-count if removed else count)
                elif id == 19:
                    gs += (-count if removed else count)
                elif id == 21:
                    ss += (-count if removed else count)
                else:
                    continue
            elif code in ["HC", "EC", "KS", "MS", "AC"]:
                self.has[code] += (-count if removed else count)
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
    def get_reachable(self, state, modes, spendKS=False):
        reachable = {}
        for conn in self.conns:
            active, conns, ksSpent = conn.is_active(state, modes)
            if not spendKS and ksSpent > 0:
                continue
            if active:
                state.has['KS'] -= ksSpent
                reachable[conn.target] = conns

        return reachable

class Connection(object):
    def __init__(self, target):
        self.target = target
        self.reqs = defaultdict(list)
    def is_active(self, state, modes):
        res = [reqs for mode in modes for reqs in self.reqs[mode] if not reqs.cnt - state.has]
        if not res:
            return (False, [], 0)
        least_ks = min([r.cnt["KS"] for r in res])
        cheapest = [req for req in res if req.cnt["KS"] <= least_ks]
        return (True, cheapest, least_ks)
    def __str__(self):
        return "Connection to %s: %s" % (self.target, "\n".join(["%s: %s" % (mode, "|".join([str(x) for x in req])) for mode, req in self.reqs.items()]))


class Requirement(object):
    def __init__(self, raw):
        self.cnt = Counter([r for r in raw.split('+') if r != "Free"])
    def __str__(self):
        return str(self.cnt)


class Map(object):
    areas = {}
    reached_with = defaultdict(lambda: set())

    @staticmethod
    def build():
        tree = get_areas()
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
        Map.reached_with = defaultdict(lambda: set())
        unchecked_areas = set(["SunkenGladesRunaway"])
        if "OPEN" in modes:
            state.has["Open"] = 1
        reachable_areas = set()
        needs_ks_check = set()
        while len(unchecked_areas) > 0:
            curr = unchecked_areas.pop()
            reachable_areas.add(curr)
            needs_ks_check.add(curr)
            reachable = Map.areas[curr].get_reachable(state, modes)
            for k, v in reachable.iteritems():
                Map.reached_with[k] |= set(v)
            unchecked_areas |= set([r for r in reachable.keys() if r not in reachable_areas])
            while len(unchecked_areas) < len(needs_ks_check):
                curr = needs_ks_check.pop()
                reachable = Map.areas[curr].get_reachable(state, modes, True)
                for k, v in reachable.iteritems():
                    Map.reached_with[k] |= set(v)
                unchecked_areas |= set([r for r in reachable.keys() if r not in reachable_areas])

        mapstone_cnt = min(len([a for a in reachable_areas if a.endswith("Map")]), state.has["MS"])
        if mapstone_cnt == 9 and state.has["MS"] < 11:
            mapstone_cnt -= 1
        if mapstone_cnt == 8 and state.has["MS"] < 9:
            mapstone_cnt -= 1
        ms_areas = ["MS%s" % i for i in range(1, mapstone_cnt + 1)]
        return {area: list(Map.reached_with[area]) for area in (list(reachable_areas) + ms_areas)}
