import time
import heapq
import os
from cachetools import TLRUCache, Cache as CacheToolsCache

from util import debug, SPLIT_CACHE
from pymemcache.client.base import PooledClient
from pymemcache import serde


class MemcachedCache(object):
    """Used to interact with memcache"""

    def __init__(self, host, port):
        # PooledClient because gunicorn runs 1 worker x 8 threads (see Dockerfile) and
        # the plain Client shares one socket across threads — interleaved commands
        # desync the protocol (the historical MemcacheUnknownError with another
        # response's bytes in it). ignore_exc turns get-side failures into misses.
        self.memcache = PooledClient((host, port), serde=serde.pickle_serde,
                                     max_pool_size=16, ignore_exc=True)

    def memcache_get(self, key):
        try:
            return self.memcache.get(key=key)
        except Exception:
            return None

    def san_check(self, gid):
        # noreply=False is required: with pymemcache's default noreply, add()
        # always returns True, so this rate limit silently never limited anything
        return self.memcache.add(key="%s.san" % gid, value=True, expire=10, noreply=False)

    def second_strike(self, gid):
        # True only when called twice within the window: first call plants the
        # flag (add succeeds) and returns False; a repeat within 30s finds it.
        # Used to gate sanity_check on persistent (not transient) desyncs.
        # noreply=False for the same reason as san_check above.
        return not self.memcache.add(key="%s.strike" % gid, value=True, expire=30, noreply=False)

    def current_gid(self):
        return self.memcache_get(key="gid_max") or -1

    def get_latest_game(self, user, bingo=False):
        if bingo:
            return self.memcache_get(key="%s.latest_bingo" % user)
        return self.memcache_get(key="%s.latest" % user)

    def set_latest_game(self, user, gid, bingo=False):
        if bingo:
            self.memcache.set(key="%s.latest_bingo" % user, value=gid, expire=604800)
        self.memcache.set(key="%s.latest" % user, value=gid, expire=604800)

    def set_gid(self, gid):
        self.memcache.set(key="gid_max", value=int(gid))

    # --- SPLIT_CACHE helpers: per-player keys ({gid}.{pid}.{suffix}) plus a pid
    # registry ({gid}.pids) so map-shaped readers know which keys to gather.
    # Registration is lazy and self-healing: a lost registry update is repaired by
    # that player's next write (~1/s), unlike the legacy whole-map RMW where a
    # lost update silently discarded another player's data.
    def _pids(self, gid):
        return [int(p) for p in (self.memcache_get(key="%s.pids" % gid) or [])]

    def _register_pid(self, gid, pid):
        pids = set(self._pids(gid))
        if int(pid) not in pids:
            pids.add(int(pid))
            self.memcache.set(key="%s.pids" % gid, value=sorted(pids), expire=604800)

    def _map_get(self, gid, suffix):
        pids = self._pids(gid)
        if not pids:
            return {}
        keymap = {"%s.%s.%s" % (gid, p, suffix): p for p in pids}
        try:
            got = self.memcache.get_many(list(keymap.keys()))
        except Exception:
            return {}
        return {keymap[k]: v for k, v in got.items()}

    def set_hist(self, gid, pid, hist):
        if SPLIT_CACHE:
            self._register_pid(gid, pid)
            self.memcache.set(key="%s.%s.hist" % (gid, pid), value=hist, expire=14400)
            return
        hist_map = self.get_hist(gid) or {}
        hist_map[int(pid)] = hist
        self.memcache.set(key="%s.hist" % gid, value=hist_map, expire=14400)

    def append_hl(self, gid, pid, hl):
        if SPLIT_CACHE:
            # RMW on a single player's key: the only concurrent writers are that
            # player's own requests plus the (rate-limited) sanity check
            self._register_pid(gid, pid)
            hist = self.memcache_get(key="%s.%s.hist" % (gid, pid)) or []
            hist.append(hl)
            self.memcache.set(key="%s.%s.hist" % (gid, pid), value=hist, expire=14400)
            return
        hist_map = self.get_hist(gid) or {}
        if int(pid) not in hist_map:
            hist_map[int(pid)] = [hl]
        else:
            hist_map[int(pid)].append(hl)
        self.memcache.set(key="%s.hist" % gid, value=hist_map, expire=14400)

    def get_hist(self, gid):
        if SPLIT_CACHE:
            return self._map_get(gid, "hist")
        return self.memcache_get(key="%s.hist" % gid)

    def get_reachable(self, gid):
        if SPLIT_CACHE:
            return self._map_get(gid, "reach")
        return self.memcache_get(key="%s.reach" % gid) or {}

    def set_reachable(self, gid, reachable):
        # merge semantics: only the given players are written. Callers may pass a
        # subset (e.g. just-recomputed players) without clobbering the others.
        if SPLIT_CACHE:
            for pid, val in reachable.items():
                self._register_pid(gid, pid)
                self.memcache.set(key="%s.%s.reach" % (gid, pid), value=val, expire=7200)
            return
        reach_map = self.get_reachable(gid) or {}
        reach_map.update({int(p): v for p, v in reachable.items()})
        self.memcache.set(key="%s.reach" % gid, value=reach_map, expire=7200)

    def get_have(self, gid):
        if SPLIT_CACHE:
            return self._map_get(gid, "have")
        return self.memcache_get(key="%s.have" % gid) or {}

    def set_have(self, gid, have):
        # merge semantics, as set_reachable
        if SPLIT_CACHE:
            for pid, val in have.items():
                self._register_pid(gid, pid)
                self.memcache.set(key="%s.%s.have" % (gid, pid), value=val, expire=7200)
            return
        have_map = self.get_have(gid) or {}
        have_map.update({int(p): v for p, v in have.items()})
        self.memcache.set(key="%s.have" % gid, value=have_map, expire=7200)

    def clear_reach(self, gid, pid):
        if SPLIT_CACHE:
            self.memcache.set(key="%s.%s.reach" % (gid, pid), value={}, expire=7200)
            return
        reach_map = self.get_reachable(gid) or {}
        reach_map[int(pid)] = {}
        self.memcache.set(key="%s.reach" % gid, value=reach_map, expire=7200)

    def get_items(self, gid, pid):
        return self.memcache_get(key="%s.%s.items" % (gid, pid)) or ({}, {})

    def set_items(self, gid, pid, items, is_race=False):
        self.memcache.set(key="%s.%s.items" % (gid, pid), value=items, expire=10 if is_race else 14400)

    def get_relics(self, gid):
        return self.memcache_get(key="%s.relics" % gid) or None

    def set_relics(self, gid, relics):
        self.memcache.set(key="%s.relics" % gid, value=relics, expire=14400)

    def clear_items(self, gid, pid=1):
        self.set_items(gid, pid, {})

    def get_pos(self, gid):
        if SPLIT_CACHE:
            return self._map_get(gid, "pos")
        return self.memcache_get(key="%s.pos" % gid)

    def set_pos(self, gid, pid, x, y):
        if SPLIT_CACHE:
            self._register_pid(gid, pid)
            self.memcache.set(key="%s.%s.pos" % (gid, pid), value=(x, y), expire=3600)
            return
        pos_map = self.get_pos(gid) or {}
        pos_map[int(pid)] = (x, y)
        self.memcache.set(key="%s.pos" % gid, value=pos_map, expire=3600)

    def get_git(self, k):
        return self.memcache_get(key="git.%s" % k)

    def set_git(self, k, val):
        self.memcache.set(key="git.%s" % k, value=val, expire=3600)

    def get_board(self, gid):
        return self.memcache_get(key="%s.board" % gid)

    def set_board(self, gid, board):
        # is_owner is viewer-specific and must never be served from cache;
        # clients keep their value from the initial (cache-bypassing) fetch
        board.pop("is_owner", None)
        return self.memcache.set(key="%s.board" % gid, value=board, expire=60)

    def get_areas(self):
        areas = self.memcache_get(key="CURRENT_LOGIC")
        if not areas:
            with open("seedbuilder/areas.ori", 'r') as f:
                areas = f.read()
            self.memcache.set(key="CURRENT_LOGIC", value=areas, expire=3600)
        return areas

    def get_output(self, gpid):
        return self.memcache_get(key="%s.%s.output" % gpid)

    def set_output(self, gpid, outstr):
        self.memcache.set(key="%s.%s.output" % gpid, value=outstr, expire=360)

    def get_names(self, gid):
        return self.memcache_get(key="%s.names" % gid)

    def set_names(self, gid, names):
        self.memcache.set(key="%s.names" % gid, value=names, expire=3600)

    def clear_names(self, gid):
        self.memcache.delete(key="%s.names" % gid)

    def get_seen_checksum(self, gpid):
        return self.memcache_get(key="%s.%s.seenhash" % gpid)

    def set_seen_checksum(self, gpid, seen_checksum):
        self.memcache.set(key="%s.%s.seenhash" % gpid, value=seen_checksum, expire=360)

    def clear_seen_checksum(self, gpid):
        self.memcache.delete(key="%s.%s.seenhash" % gpid)

    def remove_game(self, gid):
        self.memcache.delete_multi(keys=["have", "hist", "san", "pos", "reach", "items", "relics", "board", "names"], key_prefix="%s." % gid)
        if SPLIT_CACHE:
            per_player = ["%s.%s" % (p, suffix) for p in self._pids(gid)
                          for suffix in ("have", "hist", "pos", "reach", "items", "output", "seenhash")]
            self.memcache.delete_multi(keys=per_player + ["pids", "strike"], key_prefix="%s." % gid)

    def clear(self):
        self.memcache.flush_all()
        self.set_gid(0)

DEFAULT_TIME = 604800
class TLRUCacheWithCustomExpiry(TLRUCache):
    """Dev-only in-process stand-in for memcached with per-item TTLs.

    (Rewritten 2026-07-20: the previous version hand-copied TLRUCache internals,
    but name mangling and a zero-arg ttu meant it raised on every set. Prod is
    unaffected — MemcachedCache is used whenever MEMCACHED_HOST is set.)
    """

    def __init__(self, maxsize, timer=time.monotonic, getsizeof=None):
        super().__init__(maxsize, ttu=self._ttu, timer=timer, getsizeof=getsizeof)
        self._next_ttl = DEFAULT_TIME

    def _ttu(self, _key, _value, now):
        return now + self._next_ttl

    def add(self, key, value, time=DEFAULT_TIME):
        # memcached add semantics: store only if absent; True if stored
        if key in self:
            return False
        self.set(key, value, time=time)
        return True

    def set(self, key, value, time=DEFAULT_TIME):
        # route the per-call TTL to _ttu via instance state; dev-server only,
        # so the non-thread-safety of this handoff is acceptable
        self._next_ttl = time
        try:
            self[key] = value
        finally:
            self._next_ttl = DEFAULT_TIME

    def get(self, key):
        try:
            return self[key]
        except KeyError:
            return None


class PythonCache(object):
    """Used to interact with memcache"""

    def __init__(self):
        self.cache = TLRUCacheWithCustomExpiry(2048)
        self.gid_max = None
    
    def san_check(self, gid):
        return self.cache.add(key="%s.san" % gid, value=True, time=10)

    def second_strike(self, gid):
        return not self.cache.add(key="%s.strike" % gid, value=True, time=30)

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
        # merge semantics to match MemcachedCache — callers may pass subsets.
        # (dev cache keeps map storage; SPLIT_CACHE only changes prod layout)
        reach_map = self.get_reachable(gid) or {}
        reach_map.update({int(p): v for p, v in reachable.items()})
        self.cache.set(key="%s.reach" % gid, value=reach_map, time=7200)

    def get_have(self, gid):
        return self.cache.get(key="%s.have" % gid) or {}

    def set_have(self, gid, have):
        # merge semantics, as set_reachable
        have_map = self.get_have(gid) or {}
        have_map.update({int(p): v for p, v in have.items()})
        self.cache.set(key="%s.have" % gid, value=have_map, time=7200)

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
        self.set_items(gid, pid, {})

    def get_pos(self, gid):
        return self.cache.get(key="%s.pos" % gid)

    def set_pos(self, gid, pid, x, y):
        pos_map = self.get_pos(gid) or {}
        pos_map[int(pid)] = (x, y)
        self.cache.set(key="%s.pos" % gid, value=pos_map, time=3600)

    def get_git(self, k):
        return self.cache.get(key="git.%s" % k)

    def set_git(self, k, val):
        self.cache.set(key="git.%s" % k, value=val, time=3600)

    def get_board(self, gid):
        return self.cache.get(key="%s.board" % gid)

    def set_board(self, gid, board):
        board.pop("is_owner", None)  # viewer-specific, never cache (see MemcachedCache)
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

    def get_names(self, gid):
        return self.cache.get(key="%s.names" % gid)

    def set_names(self, gid, names):
        self.cache.set(key="%s.names" % gid, value=names, time=3600)

    def clear_names(self, gid):
        self.cache.pop("%s.names" % gid, None)

    def get_seen_checksum(self, gpid):
        return self.cache.get(key="%s.%s.seenhash" % gpid)

    def set_seen_checksum(self, gpid, seen_checksum):
        self.cache.set(key="%s.%s.seenhash" % gpid, value=seen_checksum, time=360)

    def clear_seen_checksum(self, gpid):
        # tolerate missing keys, like memcached delete (a bare del raised
        # KeyError whenever no checksum was armed, e.g. signal_send on a
        # player who hadn't ticked yet -- dev-only crash)
        self.cache.pop("%s.%s.seenhash" % gpid, None)

    def remove_game(self, gid):
        for key in ["have", "hist", "san", "pos", "reach", "items", "relics", "board"]:
            self.cache.pop(f"{gid}.{key}", None)

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


