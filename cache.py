from datetime import timedelta, datetime

class Cache(object):
    """A static cache object for holding player positions, histories,
        and the time since the last sanity check"""
    pos = {}
    hist = {}
    lastSanCheck = {}

    @staticmethod
    def canSanCheck(gid):
        gid = int(gid)
        if gid not in Cache.lastSanCheck:
            return True
        return timedelta(seconds=10) < datetime.now() - Cache.lastSanCheck[gid]

    @staticmethod
    def doSanCheck(gid):
        gid = int(gid)
        Cache.lastSanCheck[gid] = datetime.now()

    @staticmethod
    def setHist(gid, pid, hist):
        gid = int(gid)
        pid = int(pid)
        newHists = Cache.hist[gid] if gid in Cache.hist else {}
        newHists[pid] = hist
        Cache.hist[gid] = newHists

    @staticmethod
    def getHist(gid):
        gid = int(gid)
        return Cache.hist[gid].copy() if gid in Cache.hist else None

    @staticmethod
    def removeGame(gid):
        gid = int(gid)
        if gid in Cache.hist:
            del Cache.hist[gid]
        if gid in Cache.pos:
            del Cache.pos[gid]
        if gid in Cache.lastSanCheck:
            del Cache.lastSanCheck[gid]

    @staticmethod
    def removePlayer(gid, pid):
        gid = int(gid)
        pid = int(pid)
        if gid in Cache.hist:
            newHists = Cache.hist[gid]
            del newHists[pid]
            Cache.hist[gid] = newHists
        if gid in Cache.pos:
            newPos = Cache.pos[gid]
            del newPos[pid]
            Cache.pos[gid] = newPos

    @staticmethod
    def getPos(gid):
        gid = int(gid)
        return Cache.pos[gid].copy() if gid in Cache.pos else None

    @staticmethod
    def setPos(gid, pid, x, y):
        gid = int(gid)
        pid = int(pid)
        newPos = Cache.pos[gid] if gid in Cache.pos else {}
        newPos[pid] = (x, y)
        Cache.pos[gid] = newPos
