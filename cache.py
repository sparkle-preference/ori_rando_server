from google.appengine.api import memcache

class Cache(object):
    """Used to interact with memcache"""

    @staticmethod
    def sanCheck(gid):
        return memcache.add(key="%s.san" % gid, value=True, time=10)

    @staticmethod
    def setHist(gid, pid, hist):
        hist_map = Cache.getHist(gid) or {}
        hist_map[int(pid)] = hist
        memcache.set(key="%s.hist" % gid, value=hist_map, time=3600)

    @staticmethod
    def appendHl(gid, pid, hl):
        hist_map = Cache.getHist(gid) or {}
        hist_map[int(pid)].append(hl)
        memcache.set(key="%s.hist" % gid, value=hist_map, time=3600)

    @staticmethod
    def getHist(gid):
        return memcache.get(key="%s.hist" % gid)

    @staticmethod
    def getReachable(gid):
        return memcache.get(key="%s.reach" % gid) or {}

    @staticmethod
    def setReachable(gid, reachable):
        memcache.set(key="%s.reach" % gid, value=reachable, time=7200)

    @staticmethod
    def clearReach(gid, pid):
        reach_map = Cache.getReachable(gid) or {}
        reach_map[int(pid)] = {}
        memcache.set(key="%s.reach" % gid, value=reach_map, time=7200)

    @staticmethod
    def getPos(gid):
        return memcache.get(key="%s.pos" % gid)

    @staticmethod
    def setPos(gid, pid, x, y):
        pos_map = Cache.getPos(gid) or {}
        pos_map[int(pid)] = (x, y)
        memcache.set(key="%s.pos" % gid, value=pos_map, time=3600)

    @staticmethod
    def removeGame(gid):
        memcache.delete_multi(keys=["hist", "san", "pos"], key_prefix="%s." % gid)

    @staticmethod
    def clear():
        memcache.flush_all()