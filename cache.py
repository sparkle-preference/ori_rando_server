from google.appengine.api import memcache

class Cache(object):
    """Used to interact with memcache"""

    @staticmethod
    def san_check(gid):
        return memcache.add(key="%s.san" % gid, value=True, time=10)

    @staticmethod
    def set_hist(gid, pid, hist):
        hist_map = Cache.get_hist(gid) or {}
        hist_map[int(pid)] = hist
        memcache.set(key="%s.hist" % gid, value=hist_map, time=3600)

    @staticmethod
    def append_hl(gid, pid, hl):
        hist_map = Cache.get_hist(gid) or {}
        if int(pid) not in hist_map:
            hist_map[int(pid)] = [hl]
        else:
            hist_map[int(pid)].append(hl)
        memcache.set(key="%s.hist" % gid, value=hist_map, time=3600)

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
    def clear_reach(gid, pid):
        reach_map = Cache.get_reachable(gid) or {}
        reach_map[int(pid)] = {}
        memcache.set(key="%s.reach" % gid, value=reach_map, time=7200)

    @staticmethod
    def get_items(gid):
        return memcache.get(key="%s.items" % gid) or {}

    @staticmethod
    def set_items(gid, items):
        memcache.set(key="%s.items" % gid, value=items, time=7200)

    @staticmethod
    def get_relics(gid):
        return memcache.get(key="%s.relics" % gid) or None

    @staticmethod
    def set_relics(gid, relics):
        memcache.set(key="%s.relics" % gid, value=relics, time=7200)

    @staticmethod
    def clear_items(gid):
        Cache.set_items(gid, {})

    @staticmethod
    def get_pos(gid):
        return memcache.get(key="%s.pos" % gid)

    @staticmethod
    def set_pos(gid, pid, x, y):
        pos_map = Cache.get_pos(gid) or {}
        pos_map[int(pid)] = (x, y)
        memcache.set(key="%s.pos" % gid, value=pos_map, time=3600)

    @staticmethod
    def remove_game(gid):
        memcache.delete_multi(keys=["hist", "san", "pos", "reach", "items", "relics"], key_prefix="%s." % gid)

    @staticmethod
    def clear():
        memcache.flush_all()