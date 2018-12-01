from seedbuilder.oriparse import ori_load_url
from collections import defaultdict, Counter
from pickups import Pickup

class PlayerState(object):
    name_from_id = {
        ("SK", 0): 'Bash', ("SK", 2): 'ChargeFlame', ("SK", 3): 'WallJump', ("SK", 4): 'Stomp', ("SK", 5): 'DoubleJump',
        ("SK", 8): 'ChargeJump', ("SK", 12): 'Climb', ("SK", 14): 'Glide', ("SK", 50): 'Dash', ("SK", 51): 'Grenade',
        ("EV", 0): 'GinsoKey', ("EV", 1): 'Water', ("EV", 2): 'ForlornKey', ("EV", 3): 'Wind', ("EV", 4): 'HoruKey',
        ("TP", "Swamp"): 'TPSwamp', ("TP", "Grove"): 'TPGrove', ("TP", "Valley"): 'TPValley', ("TP", "Horu"): 'TPHoru',
        ("TP", "Ginso"): 'TPGinso', ("TP", "Grotto"): 'TPGrotto', ("TP", "Forlorn"): 'TPForlorn', ("TP", "Sorrow"): 'TPSorrow'
    }

    def add_to_inventory(self, pickup, removed, count):
        if not pickup:
            return
        if (pickup.code, pickup.id) in PlayerState.name_from_id:
            self.has[PlayerState.name_from_id[(pickup.code, pickup.id)]] = (0 if removed else count)
        elif pickup.code == "RB":
            if pickup.id in [17, 19, 21]:
                self.has["RB%s" % pickup.id] += (-count if removed else count)
        elif pickup.code in ["HC", "EC", "KS", "MS", "AC"]:
            self.has[pickup.code] += (-count if removed else count)

    def __init__(self, pickinfos):
        self.has = Counter()
        self.has["HC"] = 3
        self.wv = self.ss = self.gs = 0
        pickinfos = [x for x in pickinfos if len(x) == 4]
        for code, id, count, removed in pickinfos:
            if code in ["EX", "HN", "SH"]:
                continue
            pickup = Pickup.n(code, id)
            if code in ["MU", "RP"]:
                for child in pickup.children:
                    self.add_to_inventory(child, removed, count)
            else:
                self.add_to_inventory(pickup, removed, count)
        if self.has["RB17"] == 5:
            self.has['GinsoKey'] = 1
        if self.has["RB19"] == 5:
            self.has['ForlornKey'] = 1
        if self.has["RB21"] == 5:
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


longform_to_code = {"Health": ["HC"], "Energy": ["EC"], "Ability": ["AC"], "Keystone": ["KS"], "Mapstone": ["MS"], "Free": []}

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

    def add_requirements(self, req, mode):
        def translate(req_part):
            """Helper function. Turns a req from areas.ori into
            the list of the things that req indicates are required"""
            if req_part in longform_to_code:
                return longform_to_code[req_part]
            if '=' not in req_part:
                return [req_part]
            item, _, count = req_part.partition("=")
            count = int(count)
            if item in longform_to_code:
                return count * longform_to_code[item]
            return count * [item]
        self.reqs[mode].append(Req([t_part for part in req for t_part in translate(part)]))

class Req(object):
    def __init__(self, req):
        self.cnt = Counter(req)
    def __str__(self):
        return str(self.cnt)
    def __eq__(self, other):
        return other and not ((self.cnt - other.cnt) or (other.cnt - self.cnt))
    def __hash__(self):
        return hash(tuple(self.cnt.items()))

class Map(object):
    areas = {}
    reached_with = defaultdict(lambda: set())

    @staticmethod
    def build():
        areas = ori_load_url('http://raw.githubusercontent.com/sigmasin/OriDERandomizer/3.0/seed_gen/areas.ori')["homes"]
        for name, area_data in areas.iteritems():
            area = Area(name)
            for target, conn_data in area_data["conns"].iteritems():
                conn = Connection(target)
                if not conn_data["paths"]:
                    conn.add_requirements([], "casual-core")
                if conn_data["type"] == "pickup" and target not in Map.areas:
                    Map.areas[target] = Area(target)
                for path in conn_data["paths"]:
                    conn.add_requirements(path[1:], path[0])
                area.conns.append(conn)
            Map.areas[area.name] = area

    @staticmethod
    def get_reachable_areas(state, modes):
        if not Map.areas:
            Map.build()
        Map.reached_with = defaultdict(lambda: set())
        unchecked_areas = {"SunkenGladesRunaway"}
        if "CLOSED_DUNGEON" not in modes:
            state.has["Open"] = 1
        else:
            state.has["TPGinso"] = 0
            state.has["TPHoru"] = 0
        if "OPEN_WORLD" in modes:
            state.has["OpenWorld"] = 1
        reachable_areas = {"SunkenGladesFirstEC"}
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
