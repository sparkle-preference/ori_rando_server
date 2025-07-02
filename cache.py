import time
import heapq
import os
from cachetools import TLRUCache, Cache as CacheToolsCache

from util import debug
from pymemcache.client.base import Client
from pymemcache import serde


class MemcachedCache(object):
    """Used to interact with memcache"""
    
    def __init__(self, host, port):
        self.memcache = Client((host, port), serde=serde.pickle_serde)

    def san_check(self, gid):
        return self.memcache.add(key="%s.san" % gid, value=True, expire=10)

    def current_gid(self):
        return self.memcache.get(key="gid_max") or -1

    def get_latest_game(self, user, bingo=False):
        if bingo:
            return self.memcache.get(key="%s.latest_bingo" % user)
        return self.memcache.get(key="%s.latest" % user)

    def set_latest_game(self, user, gid, bingo=False):
        if bingo:
            self.memcache.set(key="%s.latest_bingo" % user, value=gid, expire=604800)
        self.memcache.set(key="%s.latest" % user, value=gid, expire=604800)

    def set_gid(self, gid):
        self.memcache.set(key="gid_max", value=int(gid))

    def set_hist(self, gid, pid, hist):
        hist_map = self.get_hist(gid) or {}
        hist_map[int(pid)] = hist
        self.memcache.set(key="%s.hist" % gid, value=hist_map, expire=14400)

    def append_hl(self, gid, pid, hl):
        hist_map = self.get_hist(gid) or {}
        if int(pid) not in hist_map:
            hist_map[int(pid)] = [hl]
        else:
            hist_map[int(pid)].append(hl)
        self.memcache.set(key="%s.hist" % gid, value=hist_map, expire=14400)

    def get_hist(self, gid):
        return self.memcache.get(key="%s.hist" % gid)

    def get_reachable(self, gid):
        return self.memcache.get(key="%s.reach" % gid) or {}

    def set_reachable(self, gid, reachable):
        self.memcache.set(key="%s.reach" % gid, value=reachable, expire=7200)

    def get_have(self, gid):
        return self.memcache.get(key="%s.have" % gid) or {}

    def set_have(self, gid, have):
        self.memcache.set(key="%s.have" % gid, value=have, expire=7200)

    def clear_reach(self, gid, pid):
        reach_map = self.get_reachable(gid) or {}
        reach_map[int(pid)] = {}
        self.memcache.set(key="%s.reach" % gid, value=reach_map, expire=7200)

    def get_items(self, gid, pid):
        return self.memcache.get(key="%s.%s.items" % (gid, pid)) or ({}, {})

    def set_items(self, gid, pid, items, is_race=False):
        self.memcache.set(key="%s.%s.items" % (gid, pid), value=items, expire=10 if is_race else 14400)

    def get_relics(self, gid):
        return self.memcache.get(key="%s.relics" % gid) or None

    def set_relics(self, gid, relics):
        self.memcache.set(key="%s.relics" % gid, value=relics, expire=14400)

    def clear_items(self, gid, pid=1):
        self.set_items(gid, pid, {})

    def get_pos(self, gid):
        return self.memcache.get(key="%s.pos" % gid)

    def set_pos(self, gid, pid, x, y):
        pos_map = self.get_pos(gid) or {}
        pos_map[int(pid)] = (x, y)
        self.memcache.set(key="%s.pos" % gid, value=pos_map, expire=3600)

    def get_git(self, k):
        return self.memcache.get(key="git.%s" % k)

    def set_git(self, k, val):
        self.memcache.set(key="git.%s" % k, value=val, expire=3600)

    def get_board(self, gid):
        return self.memcache.get(key="%s.board" % gid)

    def set_board(self, gid, board):
        return self.memcache.set(key="%s.board" % gid, value=board, expire=60)

    def get_areas(self):
        areas = self.memcache.get(key="CURRENT_LOGIC")
        if not areas:
            with open("seedbuilder/areas.ori", 'r') as f:
                areas = f.read()
            self.memcache.set(key="CURRENT_LOGIC", value=areas, expire=3600)
        return areas

    def get_output(self, gpid):
        return self.memcache.get(key="%s.%s.output" % gpid)

    def set_output(self, gpid, outstr):
        self.memcache.set(key="%s.%s.output" % gpid, value=outstr, expire=360)

    def get_seen_checksum(self, gpid):
        return self.memcache.get(key="%s.%s.seenhash" % gpid)

    def set_seen_checksum(self, gpid, seen_checksum):
        self.memcache.set(key="%s.%s.seenhash" % gpid, value=seen_checksum, expire=360)

    def clear_seen_checksum(self, gpid):
        self.memcache.delete(key="%s.%s.seenhash" % gpid)

    def remove_game(self, gid):
        self.memcache.delete_multi(keys=["have", "hist", "san", "pos", "reach", "items", "relics", "board"], key_prefix="%s." % gid)

    def clear(self):
        self.memcache.flush_all()
        self.set_gid(0)

DEFAULT_TIME = 604800
class TLRUCacheWithCustomExpiry(TLRUCache):
    
    def __init__(self, maxsize, timer=time.monotonic, getsizeof=None):
        ttu = lambda: DEFAULT_TIME
        super().__init__(maxsize, ttu, timer, getsizeof)
    
    def add(self, key, value, time=DEFAULT_TIME):
        with self.timer as timer:
            expires = timer + time
            if timer >= expires:
                return  # skip expired items
            self.expire(timer)
            CacheToolsCache.cache_setitem(self, key, value)
        # removing an existing item would break the heap structure, so
        # only mark it as removed for now
        try:
            self.__getitem(key).removed = True
        except KeyError:
            pass
        self.__items[key] = item = TLRUCache._Item(key, expires)
        heapq.heappush(self.__order, item)
    
    def get(self, key):
        if self.__contains__(key):
            return self[key]
        else:
            return None


class PythonCache(object):
    """Used to interact with memcache"""

    def __init__(self):
        self.cache = TLRUCacheWithCustomExpiry(2048)
        self.gid_max = None
    
    def san_check(self, gid):
        return self.cache.add(key="%s.san" % gid, value=True, time=10)

    def current_gid(self):
        return self.gid_max or -1

    def get_latest_game(self, user, bingo=False):
        if bingo:
            return self.cache.get(key="%s.latest_bingo" % user)
        return self.cache.get(key="%s.latest" % user)

    def set_latest_game(self, user, gid, bingo=False):
        if bingo:
            self.cache.set(key="%s.latest_bingo" % user, value=gid, time=604800)
        self.cache.set(key="%s.latest" % user, value=gid, time=604800)

    def set_gid(self, gid):
        self.gid_max = int(gid)

    def set_hist(self, gid, pid, hist):
        hist_map = self.get_hist(gid) or {}
        hist_map[int(pid)] = hist
        self.cache.set(key="%s.hist" % gid, value=hist_map, time=14400)

    def append_hl(self, gid, pid, hl):
        hist_map = self.get_hist(gid) or {}
        if int(pid) not in hist_map:
            hist_map[int(pid)] = [hl]
        else:
            hist_map[int(pid)].append(hl)
        self.cache.set(key="%s.hist" % gid, value=hist_map, time=14400)

    def get_hist(self, gid):
        return self.cache.get(key="%s.hist" % gid)

    def get_reachable(self, gid):
        return self.cache.get(key="%s.reach" % gid) or {}

    def set_reachable(self, gid, reachable):
        self.cache.set(key="%s.reach" % gid, value=reachable, time=7200)

    def get_have(self, gid):
        return self.cache.get(key="%s.have" % gid) or {}

    def set_have(self, gid, have):
        self.cache.set(key="%s.have" % gid, value=have, time=7200)

    def clear_reach(self, gid, pid):
        reach_map = self.get_reachable(gid) or {}
        reach_map[int(pid)] = {}
        self.cache.set(key="%s.reach" % gid, value=reach_map, time=7200)

    def get_items(self, gid, pid):
        return self.cache.get(key="%s.%s.items" % (gid, pid)) or ({}, {})

    def set_items(self, gid, pid, items, is_race=False):
        self.cache.set(key="%s.%s.items" % (gid, pid), value=items, time=10 if is_race else 14400)

    def get_relics(self, gid):
        return self.cache.get(key="%s.relics" % gid) or None

    def set_relics(self, gid, relics):
        self.cache.set(key="%s.relics" % gid, value=relics, time=14400)

    def clear_items(self, gid, pid=1):
        self.cache.set(self, gid, {})

    def get_pos(self, gid):
        return self.cache.get(key="%s.pos" % gid)

    def set_pos(self, gid, pid, x, y):
        pos_map = self.cache.get_pos(self, gid) or {}
        pos_map[int(pid)] = (x, y)
        self.cache.set(key="%s.pos" % gid, value=pos_map, time=3600)

    def get_git(self, k):
        return self.cache.get(key="git.%s" % k)

    def set_git(self, k, val):
        self.cache.set(key="git.%s" % k, value=val, time=3600)

    def get_board(self, gid):
        return self.cache.get(key="%s.board" % gid)

    def set_board(self, gid, board):
        return self.cache.set(key="%s.board" % gid, value=board, time=60)

    def get_areas(self):
        areas = self.cache.get(key="CURRENT_LOGIC")
        if not areas:
            with open("seedbuilder/areas.ori", 'r') as f:
                areas = f.read()
            self.cache.set(key="CURRENT_LOGIC", value=areas, time=3600)
        return areas

    def get_output(self, gpid):
        return self.cache.get(key="%s.%s.output" % gpid)

    def set_output(self, gpid, outstr):
        self.cache.set(key="%s.%s.output" % gpid, value=outstr, time=360)

    def get_seen_checksum(self, gpid):
        return self.cache.get(key="%s.%s.seenhash" % gpid)

    def set_seen_checksum(self, gpid, seen_checksum):
        self.cache.set(key="%s.%s.seenhash" % gpid, value=seen_checksum, time=360)

    def clear_seen_checksum(self, gpid):
        del self.cache["%s.%s.seenhash" % gpid]

    def remove_game(self, gid):
        for key in ["have", "hist", "san", "pos", "reach", "items", "relics", "board"]:
            del self.cache[f"{gid}.{key}"]

    def clear(self):
        self.cache.clear()
        self.set_gid(0)


memcached_host = os.getenv("MEMCACHED_HOST")
memcached_port = os.getenv("MEMCACHED_PORT", 11211)
# DI the actual cache impl we want
if memcached_host:
    Cache = MemcachedCache(memcached_host, memcached_port)
else:
    err_msg = "No MEMCACHED_HOST set; defaulting to in-memory cache. This will cause problems if there's more than one app instance!"
    if debug():
        print(err_msg)
        Cache = PythonCache()
    else:
        raise EnvironmentError(err_msg)

Cache = MemcachedCache("localhost", 11211)
