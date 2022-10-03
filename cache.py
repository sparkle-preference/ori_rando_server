from google.appengine.api import memcache

class Cache(object):
    """Used to interact with memcache"""

    @staticmethod
    def san_check(gid):
        return memcache.add(key="%s.san" % gid, value=True, time=10)

    @staticmethod
    def current_gid():
        return memcache.get(key="gid_max") or -1

    @staticmethod
    def get_latest_game(user, bingo=False):
        if bingo:
            return memcache.get(key="%s.latest_bingo" % user)
        return memcache.get(key="%s.latest" % user)

    @staticmethod
    def set_latest_game(user, gid, bingo=False):
        if bingo:
            memcache.set(key="%s.latest_bingo" % user, value=gid, time=604800)
        memcache.set(key="%s.latest" % user, value=gid, time=604800)

    @staticmethod
    def set_gid(gid):
        memcache.set(key="gid_max", value=int(gid))

    @staticmethod
    def set_hist(gid, pid, hist):
        hist_map = Cache.get_hist(gid) or {}
        hist_map[int(pid)] = hist
        memcache.set(key="%s.hist" % gid, value=hist_map, time=14400)

    @staticmethod
    def append_hl(gid, pid, hl):
        hist_map = Cache.get_hist(gid) or {}
        if int(pid) not in hist_map:
            hist_map[int(pid)] = [hl]
        else:
            hist_map[int(pid)].append(hl)
        memcache.set(key="%s.hist" % gid, value=hist_map, time=14400)

    @staticmethod
    def get_hist(gid):
        return memcache.get(key="%s.hist" % gid)

    @staticmethod
    def get_reachable(gid):
        return memcache.get(key="%s.reach" % gid) or {}

    @staticmethod
    def set_reachable(gid, reachable):
        memcache.set(key="%s.reach" % gid, value=reachable, time=7200)

    @staticmethod
    def get_have(gid):
        return memcache.get(key="%s.have" % gid) or {}

    @staticmethod
    def set_have(gid, have):
        memcache.set(key="%s.have" % gid, value=have, time=7200)

    @staticmethod
    def clear_reach(gid, pid):
        reach_map = Cache.get_reachable(gid) or {}
        reach_map[int(pid)] = {}
        memcache.set(key="%s.reach" % gid, value=reach_map, time=7200)

    @staticmethod
    def get_items(gid, pid):
        return memcache.get(key="%s.%s.items" % (gid, pid)) or ({}, {})

    @staticmethod
    def set_items(gid, pid, items, is_race=False):
        memcache.set(key="%s.%s.items" % (gid, pid), value=items, time=10 if is_race else 14400)

    @staticmethod
    def get_relics(gid):
        return memcache.get(key="%s.relics" % gid) or None

    @staticmethod
    def set_relics(gid, relics):
        memcache.set(key="%s.relics" % gid, value=relics, time=14400)

    @staticmethod
    def clear_items(gid, pid=1):
        Cache.set_items(gid, pid, {})

    @staticmethod
    def get_pos(gid):
        return memcache.get(key="%s.pos" % gid)

    @staticmethod
    def set_pos(gid, pid, x, y):
        pos_map = Cache.get_pos(gid) or {}
        pos_map[int(pid)] = (x, y)
        memcache.set(key="%s.pos" % gid, value=pos_map, time=3600)

    @staticmethod
    def get_git(k):
        return memcache.get(key="git.%s" % k)

    @staticmethod
    def set_git(k, val):
        memcache.set(key="git.%s" % k, value=val, time=3600)

    @staticmethod
    def get_board(gid):
        return memcache.get(key="%s.board" % gid)

    @staticmethod
    def set_board(gid, board):
        return memcache.set(key="%s.board" % gid, value=board, time=60)

    @staticmethod
    def get_areas():
        areas = memcache.get(key="CURRENT_LOGIC")
        if not areas:
            with open("seedbuilder/areas.ori", 'r') as f:
                areas = f.read()
            memcache.set(key="CURRENT_LOGIC", value=areas, time=3600)
        return areas

    @staticmethod
    def remove_game(gid):
        memcache.delete_multi(keys=["have", "hist", "san", "pos", "reach", "items", "relics", "board"], key_prefix="%s." % gid)

    @staticmethod
    def clear():
        memcache.flush_all()
        Cache.set_gid(0)