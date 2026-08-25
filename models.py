from google.cloud import ndb
from google.cloud.ndb.model import ModelKey


import logging as log
import random
from json import dumps as jsonify
from datetime import datetime, timedelta
from calendar import timegm
from collections import defaultdict, OrderedDict
from typing import List, Dict, Optional
from flask import g

from seedbuilder.seedparams import Placement, Stuff, SeedGenParams, bingo_worlds
from enums import MultiplayerGameType, ShareType, Variation
from util import picks_by_coord, get_bit, get_taste, enums_from_strlist, ord_suffix, debug, bfields_to_coords, bfield_checksum, unpack, netperf, is_mw_manifest_loc
import re
import threading
import zlib
from time import monotonic
from pickups import Pickup, Skill, Teleporter, Event
from cache import Cache

# Per-game locks serializing all writers of a game's BingoGameData within this
# (single) process; dict.setdefault is atomic under the GIL.
# CORRECT ONLY SINGLE-INSTANCE: bingo writes are plain puts serialized by these
# locks, so the service must stay one process (gunicorn --workers 1, Cloud Run
# max-instances=1 — see Dockerfile). Revisit before any horizontal scaling.
_bingo_locks = {}

def bingo_lock(gid):
    return _bingo_locks.setdefault(int(gid), threading.Lock())

try:
    client = ndb.Client()
except Exception as e:
    # no default credentials (e.g. unit tests, which provide their own client
    # and context). In prod the Cloud Run service account always supplies ADC.
    log.warning("ndb.Client() unavailable at import (%s); requests will fail unless a context is provided elsewhere", e)
    client = None

def ndb_wsgi_middleware(wsgi_app):
    def middleware(environ, start_response):
        with client.context():
            return wsgi_app(environ, start_response)

    return middleware

trees_by_coords = {
    -3160308: Pickup.n("RB", 900),
    -560160: Pickup.n("RB", 901),
    7839588: Pickup.n("RB", 902),
    5320328: Pickup.n("RB", 903),
    8599904: Pickup.n("RB", 904),
    -4600020: Pickup.n("RB", 905),
    -11880100: Pickup.n("RB", 906),
    -6959592: Pickup.n("RB", 907),
    719620: Pickup.n("RB", 908),
    2919744: Pickup.n("RB", 909),
}

dedup_bonus_ids = [17, 19, 21, 28] + list(range(300, 312))

zone_translate = {
    "Valley": "valleyOfTheWind",
    "Sorrow": "sorrowPass",
    "Glades": "sunkenGlades",
    "Forlorn": "forlornRuins",
    "Grove": "hollowGrove",
    "Blackroot": "mangrove",
    "Grotto": "moonGrotto",
    "Horu": "mountHoru",
    "Swamp": "thornfeltSwamp",
    "Misty": "mistyWoods",
    "Ginso": "ginsoTree",
}

map_coords_by_zone = {
    "valleyOfTheWind": -4080172,
    "sorrowPass": -4519716,
    "sunkenGlades": -840248,
    "forlornRuins": -8440308,
    "hollowGrove": 3479880,
    "mangrove": 4159708,
    "moonGrotto": 4759608,
    "mountHoru": 560340,
    "thornfeltSwamp": 6759868
}

relics_by_zone = {
    "sunkenGlades": Pickup.n("RB", 911),
    "hollowGrove": Pickup.n("RB", 912),
    "moonGrotto": Pickup.n("RB", 913),
    "mangrove": Pickup.n("RB", 914),
    "thornfeltSwamp": Pickup.n("RB", 915),
    "ginsoTree": Pickup.n("RB", 916),
    "valleyOfTheWind": Pickup.n("RB", 917),
    "mistyWoods": Pickup.n("RB", 918),
    "forlornRuins": Pickup.n("RB", 919),
    "sorrowPass": Pickup.n("RB", 920),
    "mountHoru": Pickup.n("RB", 921)
}

def _conf_signals(signals, signal):
    """The signal_conf edit, in place on a list. Keeps the known quirk: the
    fallback removes while iterating, so a non-msg signal queued first is what
    an unmatched msg: callback eats."""
    if signal in signals:
        signals.remove(signal)
    # basically it is never ok to be spamming ppl, so if we get a message callback
    # we remove the first message we find if we don't get an exact match.
    elif signal.startswith("msg:"):
        for s in signals:
            signals.remove(s)
            if s.startswith("msg:"):
                log.warning("No exact match for signal %s, removing %s instead (spam protection)" % (signal, s))
                break
    return signals


def _pid(pkey):
    # type: (ModelKey) -> int
    try:
        return int(pkey.id().partition(".")[2])
    except Exception as e:
        log.error("invalid pkey %s: %s, returning 1", pkey, e)
        return 1

def round_time(t):
    parts = str(t).split(":")
    parts[-1] = str(round(float(parts[-1]), 2))
    if len(parts[-1].partition(".")[0]) < 2:
        parts[-1] = "0"+parts[-1]
    return ":".join(parts)

# helper function, checks if a pickup stacks
def stacks(pickup):
    if pickup.stacks:
        return True
    if pickup.code != "RB":
        return False
    return pickup.id in ([6, 9, 12, 13, 15, 17, 19, 21, 28, 30, 31, 32, 33, 37, 81] + list(range(300, 312)))


pbc = picks_by_coord(extras=True)

lines_by_index = {
    'Row 1': [0, 1, 2, 3, 4],
    'Row 2': [5, 6, 7, 8, 9],
    'Row 3': [10, 11, 12, 13, 14],
    'Row 4': [15, 16, 17, 18, 19],
    'Row 5': [20, 21, 22, 23, 24],
    'Col A': [0, 5, 10, 15, 20],
    'Col B': [1, 6, 11, 16, 21],
    'Col C': [2, 7, 12, 17, 22],
    'Col D': [3, 8, 13, 18, 23],
    'Col E': [4, 9, 14, 19, 24],
    'A1-E5': [0, 6, 12, 18, 24],
    'E1-A5': [4, 8, 12, 16, 20]
}


class BingoCardProgress(ndb.Model):
    square = ndb.IntegerProperty()
    completed = ndb.BooleanProperty(default=False)
    count = ndb.IntegerProperty(default=0)
    completed_subgoals = ndb.StringProperty(repeated=True)
    # a regression (posted progress un-completing a square) is only applied after a
    # second consecutive update from this player confirms it; guards against
    # stale/out-of-order POSTs causing goal flicker. Real death-rollbacks confirm
    # within one client post cycle.
    pending_loss = ndb.BooleanProperty(default=False)

    def to_json(self):
        return {
            'completed': self.completed,
            'count': self.count,
            'subgoals': self.completed_subgoals
        }
class HistoryLine(ndb.Model):
    player = ndb.IntegerProperty()
    pickup_code = ndb.StringProperty()
    pickup_id = ndb.StringProperty()
    timestamp = ndb.DateTimeProperty()
    removed = ndb.BooleanProperty()
    coords = ndb.IntegerProperty()
    map_coords = ndb.IntegerProperty()

    def pickup(self):
        return Pickup.n(self.pickup_code, self.pickup_id)

    def equals(self, other):
        return self.player == other.player and self.pickup_code == other.pickup_code and self.pickup_id == other.pickup_id and self.coords == other.coords

    def print_line(self, start_time=None, names=None):
        t = (self.timestamp - start_time) if start_time and self.timestamp else self.timestamp
        pick = self.pickup()
        shown = pick.named_for(names) if hasattr(pick, "named_for") else pick.name
        if not self.removed:
            name = "at "
            if self.coords in pbc:
                name += pbc[self.coords].area
            elif abs(self.coords) == 1:
                name = "via manual activation"
            else:
                log.warning("Unknown coords: %s", self.coords)
                name += "unknown coordset %s (%s, %s)" % (self.coords, unpack(self.coords))
            return "found %s %s. (%s)" % (shown, name, t)
        else:
            return "lost %s! (%s)" % (shown, t)

HIST_CHUNK_SIZE = 50   # lines per chunk entity
HIST_TAIL = 20         # legacy dedup exemption window (Game.hls[:-20])

def hl_dedup_key(hl):
    # the legacy key is (player, code, id, coords); player is implicit because
    # dedup state lives on that player's own entity. crc32 keeps the stored set
    # to one int per distinct pickup (~250 max), vs. a full HistoryLine each.
    return zlib.crc32(("%s|%s|%s" % (hl.pickup_code, hl.pickup_id, hl.coords)).encode("utf-8")) & 0xffffffff

class HistoryChunk(ndb.Model):
    """A fixed-size slice of one player's history, stored as a child of the
    Game (same entity group, so existing single-group transactions keep
    working). Written by appends, read only by Game.history()."""
    lines = ndb.LocalStructuredProperty(HistoryLine, repeated=True)

    @staticmethod
    def key_for(game_key, gid, pid, n):
        return ndb.Key(HistoryChunk, "%s.%s.%s" % (gid, pid, n), parent=game_key)

class User(ndb.Model):
    @classmethod
    def _get_kind(cls):
        return 'User2'
    # key = user_id
    name = ndb.StringProperty()
    games = ndb.KeyProperty("Game", repeated=True)
    # no default: None means "never chose", which follows the browser
    dark_theme = ndb.BooleanProperty()
    email = ndb.StringProperty()
    teamname = ndb.StringProperty()
    pref_num  = ndb.IntegerProperty()
    theme  = ndb.StringProperty()
    verbose = ndb.BooleanProperty(default=False)
    admin = ndb.BooleanProperty(default = False, indexed= False)


    @staticmethod
    def latest_game(username):
        gid = Cache.get_latest_game(username)
        if gid:
            return gid
        user = User.get_by_name(username)
        if not user or not user.games:
            return False
        gid = int(user.games[-1].id())
        Cache.set_latest_game(username, gid)
        return gid

    @staticmethod
    def is_admin():
        user = User.get()
        if user:
            return user.admin
        return False

    @staticmethod
    def prune_games():
        keys = [k for k in Game.query().iter(keys_only=True)]
        for user in User.query().fetch():
            game_count = len(user.games)
            user.games = [g for g in user.games if g in keys]
            if len(user.games) < game_count:
                print("removed %s games from %s's gamelist" % (game_count - len(user.games), user.name))
                user.put()

    @staticmethod
    def get():
        app_user = g.oidc_user
        if not app_user.logged_in:
            return None
        user = User.get_by_id(app_user.unique_id)
        if not user:
            legacy_user_query = LegacyUser.query(LegacyUser.email == app_user.email).fetch()
            if len(legacy_user_query) == 1:
                user = User.migrate(app_user, legacy_user_query[0])
            elif len(legacy_user_query) == 0:
                user = User.create(app_user)
            else:
                log.error("Users with same email detected: " + ",".join(lu.id for lu in legacy_user_query))
            # create and migrate build the entity but never store it; lookups by name need this put
            if user:
                user.put()
        return user

    def rename(self, desired_name):
        if any([forbidden in desired_name for forbidden in URL_UNSAFE_NAME_CHARS]):
            return False
        if User.get_by_name(desired_name):
            return False
        self.name = desired_name
        if self.put():
            return True
        return False

    @staticmethod
    def get_by_name(name):
        return User.query(User.name == name).get()

    @staticmethod
    def create(app_user):
        user = User(id=app_user.unique_id)
        user.email = app_user.email.lower()
        if app_user.name:
            user.name = app_user.name
        else:
            user.name = app_user.email.split("@")[0]
        user.teamname = "%s's team" % user.name
        return user
    
    @staticmethod
    def migrate(app_user, old_user):
        user = User(id=app_user.unique_id)
        user.email = app_user.email.lower()
        if old_user.name:
            user.name = old_user.name
        else:
            user.name = old_user
        user.teamname = old_user.teamname
        user.dark_theme = old_user.dark_theme
        user.games = old_user.games
        user.pref_num = old_user.pref_num
        user.theme = old_user.theme
        user.verbose = old_user.verbose
        key = user.put()
        for seed in Seed.query(Seed.legacy_author_key == old_user.key):
            try:
                if seed.key.id().split(":")[0] == key.id():
                    log.warning(f"Trying to migrate already migrated Plando {seed.key}")
                    continue
                new_seed = Seed(
                        id=f"{key.id()}:{seed.name}",
                        placements = seed.placements,
                        flags = seed.flags,
                        hidden = seed.hidden,
                        description = seed.description,
                        players = seed.players,
                        author_key = key,
                        legacy_author_key = old_user.key,
                        author = seed.author,
                        name = seed.name
                        )
                new_seed.put()
                seed.key.delete()
            except Exception as e:
                log.error(f"Error migrating plando {seed.name} for user {user.name}")
        for gkey in user.games:
            try:
                game = gkey.get()
                if not game:
                    continue
                # You can have a game on your gameslist without being the creator
                # have to check the see if the old game was one you rolled
                if game.legacy_creator != old_user.key:
                    continue
                game.creator = key
                game.put()
            except Exception as e:
                log.error(f"Error migrating game {gkey} for user {user.name}")
        for player in Player.query(Player.legacy_user == old_user.key):
            try:
                if player.user is not None:
                    log.warning(f"Trying to migrate already migrated Player {player.key}")
                    continue
                player.user = key
                player.put()
            except Exception as e:
                log.error(f"Error migrating player {player.key} for user {user.name}")
        for bingo in BingoGameData.query(BingoGameData.legacy_creator == old_user.key):
            try:
                if bingo.creator is not None:
                    log.warning(f"Trying to migrate already migrated Bingo {bingo.key}")
                    continue
                bingo.creator = key
                bingo.put()
            except Exception as e:
                log.error(f"Error migrating bingo game data {bingo.key} for user {user.name}")
        
        return user
    
    def plando(self, seed_name):
        return Seed.get_by_id(f"{self.key.id()}:{seed_name}")

    def saved_params(self, name):
        return SavedSeedParams.get_by_id(f"{self.key.id()}:{name}")

class LegacyUser(ndb.Model):
    @classmethod
    def _get_kind(cls):
        return 'User'
    
    # key = user_id
    name = ndb.StringProperty()
    games = ndb.KeyProperty("Game", repeated=True)
    # no default: None means "never chose", which follows the browser
    dark_theme = ndb.BooleanProperty()
    email = ndb.StringProperty()
    teamname = ndb.StringProperty()
    pref_num  = ndb.IntegerProperty()
    theme  = ndb.StringProperty()
    verbose = ndb.BooleanProperty(default=False)

    def plando(self, seed_name):
        return Seed.get_by_id(f"{self.key.id()}:{seed_name}")

    @staticmethod
    def get_by_name(name):
        return LegacyUser.query(LegacyUser.name == name).get()


# marks the AP outbox players; the only thing that ever sets a nickname
AP_SHADOW_NICK = "Archipelago"

class Player(ndb.Model):
    # id = gid.pid
    skills      = ndb.IntegerProperty()
    events      = ndb.IntegerProperty()
    bonuses     = ndb.JsonProperty()
    hints       = ndb.JsonProperty()
    teleporters = ndb.IntegerProperty()
    seed        = ndb.TextProperty()
    signals     = ndb.StringProperty(repeated=True)
    history     = ndb.LocalStructuredProperty(HistoryLine, repeated=True)
    last_update = ndb.DateTimeProperty(auto_now=True)
    teammates   = ndb.KeyProperty("Player", repeated=True)
    user        = ndb.KeyProperty(User)
    legacy_user = ndb.KeyProperty(LegacyUser)
    can_nag     = ndb.BooleanProperty(default=True)
    seen_bflds  = ndb.IntegerProperty(repeated=True)
    have_bflds  = ndb.IntegerProperty(repeated=True)
    # multiworld: which of this player's item slots other players have found
    # (8x32 bits; slot semantics live in the player's own seed manifest)
    slot_bflds  = ndb.IntegerProperty(repeated=True)
    # multiworld: locations in this world the shared release already spent.
    # Shared singletons are local seed lines, not slots, so nothing else does.
    shared_released = ndb.IntegerProperty(repeated=True)
    bingo_prog  = ndb.LocalStructuredProperty(BingoCardProgress, repeated=True)
    # history dedup state (constant size): hist_tail is the rolling
    # last-HIST_TAIL keys, hist_seen is every key that has fallen out of that
    # window — the "skip if in history[:-20]" replay guard, minus the scan.
    hist_chunk  = ndb.IntegerProperty(default=0)
    hist_tail   = ndb.IntegerProperty(repeated=True)
    hist_seen   = ndb.IntegerProperty(repeated=True)
    # last spirit well this player touched on foot; no goal tracks it, journey
    # cards use it to show whether they are live right now
    bingo_last_tp = ndb.StringProperty()
    # dll version, refreshed from the tick (client >= 4.1.10 sends it every tick).
    # The capability-negotiation hook for the websocket migration: it tells us
    # what the live fleet is actually running, per game and per player.
    dll_version = ndb.StringProperty()
    # fixed display name; overrides the user-derived one. Set on AP shadow
    # players (pid K+w) so the tick names field renders '<K+w>.Archipelago'.
    nickname    = ndb.StringProperty()
    # name this world was rolled with; a claimed seed's user still wins
    seed_name   = ndb.StringProperty()
    # Archipelago progressive hints: {manifest slot: resolved hint text}, the
    # answers to this player's own hint requests. Tick field 8; the purchase
    # state machine lives on APHints.
    ap_hints    = ndb.JsonProperty()

    def note_version(self, vers, game_id=None):
        """Record the client's reported dll version. Returns True if it changed
        (caller puts) — false on every tick after the first, so this costs
        nothing steady-state."""
        if not vers or self.dll_version == vers:
            return False
        log.info("NETPERF dll_version gid=%s pid=%s vers=%s was=%s",
                 game_id if game_id is not None else self.key.id(), self.pid(), vers, self.dll_version)
        self.dll_version = vers
        return True

    
    def seen_coords(self):
        return bfields_to_coords(self.seen_bflds) + [2]

    def have_coords(self):
        return bfields_to_coords(self.have_bflds) + [2]

    # --- multiworld slots ---
    def mark_slot(self, slot, delay_put=False):
        """Set a slot bit. Returns True if it was newly set (caller busts the
        owner's tick cache), False if already set or out of range."""
        if slot < 0 or slot > 255:
            log.error("invalid multiworld slot %s for %s", slot, self.key.id())
            return False
        if not self.slot_bflds:
            self.slot_bflds = 8 * [0]
        if self.slot_check(slot):
            return False
        self.slot_bflds[slot // 32] |= 1 << (slot % 32)
        if not delay_put:
            self.put()
        return True

    def slot_check(self, slot):
        if not self.slot_bflds:
            return False
        return bool((self.slot_bflds[slot // 32] >> (slot % 32)) & 1)

    @staticmethod
    @ndb.transactional(retries=5)
    def tick_update_txn(pkey, vers, seen_bflds, have_bflds):
        """The tick slow path's write: fresh read inside a txn, touching only
        tick-owned fields (seen/have bitfields, dll_version). Putting the
        handler's stale copy here raced concurrent grant txns and erased
        their bits — 134701 lost two shared skills, and multiworld has no
        sanity check to repair that. Returns the fresh entity so the caller
        renders tick output from post-grant state."""
        p = pkey.get()
        changed = False
        if vers and p.dll_version != vers:
            p.dll_version = vers
            changed = True
        if p.seen_bflds != seen_bflds:
            p.seen_bflds = list(seen_bflds)
            changed = True
        if p.have_bflds != have_bflds:
            p.have_bflds = list(have_bflds)
            changed = True
        if changed:
            p.put()
        return p

    @staticmethod
    @ndb.transactional(retries=5)
    def mark_slot_txn(pkey, slot):
        return pkey.get().mark_slot(slot)

    @staticmethod
    @ndb.transactional(retries=5)
    def mark_slots_txn(pkey, slots, signal_for=None, signal_latest_only=False):
        """Batch slot marking (multiworld release). Returns newly-set count.
        signal_for(newly-set slots) may return one signal to ride the same
        write, so a client can read it on the tick that grants them.
        signal_latest_only drops earlier signals of the same kind: a client
        that never acks one (an older dll) would otherwise carry every one of
        them on every tick."""
        p = pkey.get()
        fresh = [s for s in slots if p.mark_slot(s, delay_put=True)]
        if fresh and signal_for:
            signal = signal_for(fresh)
            if signal and signal_latest_only:
                kind = signal.split(":", 1)[0] + ":"
                p.signals = [s for s in p.signals if not s.startswith(kind)]
            if signal and signal not in p.signals:
                p.signals.append(signal)
        if fresh:
            p.put()
        return len(fresh)

    def claim_shared_released(self, coords):
        """Claim locations for the shared release, returning the ones this call
        won. Claiming before granting is what keeps a repeated /complete (the
        client retries until acked) from stacking a bonus once per retry."""
        already = set(self.shared_released or [])
        fresh = [c for c in coords if c not in already]
        if fresh:
            self.shared_released = (self.shared_released or []) + fresh
            self.put()
        return fresh

    @staticmethod
    @ndb.transactional(retries=5)
    def claim_shared_released_txn(pkey, coords):
        p = pkey.get()
        return p.claim_shared_released(coords) if p else []

    @staticmethod
    @ndb.transactional(retries=5)
    def signal_latest_txn(pkey, kind, signal):
        """Send `signal`, dropping any earlier one of the same `kind` prefix.
        For signals where only the newest matters (a DeathLink owed to a
        client that was away is one death, not the backlog)."""
        p = pkey.get()
        signals = [s for s in p.signals if not s.startswith(kind)] + [signal]
        if signals == p.signals:
            return False
        p.signals = signals
        p.put()
        return True

    @staticmethod
    @ndb.transactional(retries=5)
    def set_ap_hints_txn(pkey, answers, keep=None, limit=16):
        """Merge resolved Archipelago hint text in. `keep` is the slots the
        client is still asking about; anything else is evicted first, so a
        long keysanity run can't wedge against the cap holding answers
        nobody is reading. Returns True if anything changed."""
        p = pkey.get()
        hints = dict(p.ap_hints or {})
        changed = False
        if keep is not None:
            wanted = {str(s) for s in keep} | {str(s) for s in answers}
            for slot in [s for s in hints if s not in wanted]:
                del hints[slot]
                changed = True
        for slot, text in answers.items():
            if hints.get(str(slot)) == text:
                continue
            if str(slot) not in hints and len(hints) >= limit:
                log.warning("ap hint cap reached for %s, dropping slot %s", p.key.id(), slot)
                continue
            hints[str(slot)] = text
            changed = True
        if changed:
            p.ap_hints = hints
            p.put()
        return changed

    def clear_progress(self):
        """Everything a reset forgets, minus the put. The seed, identity, and ap_hints are kept."""
        self.can_nag = True
        self.skills = 0
        self.events = 0
        self.teleporters = 0
        self.bonuses = {}
        self.hints = {}
        self.signals = []
        self.history = []
        self.seen_bflds = 8 * [0]
        self.have_bflds = 8 * [0]
        self.slot_bflds = 8 * [0]
        self.shared_released = []
        # dedup state must not outlive the run it describes
        self.hist_chunk = 0
        self.hist_tail = []
        self.hist_seen = []
        self.bingo_last_tp = None
        self.bingo_prog = [BingoCardProgress(square=i) for i in range(25)]

    @ndb.transactional(retries=5)
    def reset(self):
        self.clear_progress()
        self.put()

    def sharetuple(self):
        return (self.skills, self.events, self.teleporters, len(self.bonuses))

    def name(self):
        if self.nickname:
            return self.nickname
        if self.user:
            u = self.user.get()
            if u and u.name:
                return u.name
        if self.seed_name:
            return self.seed_name
        return "Player %s" % self.pid()

    def is_ap_shadow(self):
        """AP outbox players (pid K+w). No client ever connects as one, and
        nothing player-facing should render or compute for them."""
        return self.nickname == AP_SHADOW_NICK

    def wire_name(self):
        """Name as safe to embed in the tick wire format and signal text:
        no field separators, no message color characters."""
        clean = re.sub(r"[^A-Za-z0-9 _.'-]", "", self.name()).strip()[:20]
        return clean or "Player %s" % self.pid()

    def mw_names_field(self):
        """Tick field 7 (multiworld): ;-joined pid.name pairs for the game."""
        gid = self.idpts()[0]
        names = Cache.get_names(gid)
        if names is None:
            parent = self.key.parent()
            game = parent.get() if parent else None
            if not game:
                return ""
            names = ";".join("%s.%s" % (p.pid(), p.wire_name()) for p in game.get_players())
            Cache.set_names(gid, names)
        return names

    def ap_hints_field(self):
        """Tick field 8 (Archipelago): ';'-joined '<slot>=<hint>'. Only ever
        answers to slots this client asked about, so it is empty on every
        game that is not buying AP hints -- and an empty field is omitted,
        which keeps every existing multiworld tick body byte-identical."""
        if not self.ap_hints:
            return ""
        pairs = sorted(self.ap_hints.items(), key=lambda kv: int(kv[0]))
        return ";".join("%s=%s" % (slot, text) for slot, text in pairs if text)

    def userdata(self):
        name = "Player %s" % self.pid()
        ppid = self.pid()
        if self.user:
            u = self.user.get()
            if u:
                name = u.name
                ppid = u.pref_num
        return {'name': name, 'ppid': ppid, 'pid': self.pid()}

    def teamname(self):
        if self.user:
            u = self.user.get()
            if u:
                if u.teamname:
                    return u.teamname
                elif u.name:
                    return "%s's team" % u.name
        return "Player %s's team" % self.pid()

    def pid(self):
        return _pid(self.key)

    def idpts(self):
        try:
            gid,_,pid = self.key.id().partition(".")
            return int(gid),int(pid)
        except Exception as e:
            log.error("invalid pkey %s: %s, returning 0,0", pkey, e)
            return 0,0

    # post-refactor version of bitfields
    def output(self, include_slots=False):
        outlines = [str(x) for x in [self.skills, self.events, self.teleporters]]
        bonuses = []
        for (_id, cnt) in self.bonuses.items():
            if _id.startswith("Warp to"):
                parts = _id.split(",")
                bonuses.append("%s_%sx1" % (parts[1], parts[2]))
            else:
                bonuses.append("%sx%s" % (_id, cnt))
        outlines.append(";".join(bonuses))
        outlines.append(";".join(["%s:%s" % (loc, finder) for (loc, finder) in self.hints.items()]))
        if include_slots:
            # multiworld games only (new clients by definition): the signals
            # field is ALWAYS present -- possibly empty -- so the slot
            # bitfields land at a fixed index 6, player names at 7. Legacy
            # games keep the conditional-signals format below untouched.
            outlines.append("|".join(self.signals))
            outlines.append(";".join(str(b) for b in (self.slot_bflds or 8 * [0])))
            outlines.append(self.mw_names_field())
            # field 8 is APPENDED ONLY WHEN NONEMPTY: it is last, so absence
            # shifts nothing, and every multiworld body that predates AP
            # hints stays byte-identical
            ap_hints = self.ap_hints_field()
            if ap_hints:
                outlines.append(ap_hints)
        elif self.signals:
            outlines.append("|".join(self.signals))
        out = ",".join(outlines)
        Cache.set_output(self.idpts(), out)
        return out

    def signal_send(self, signal):
        # stale-put hazard: request paths want signal_send_txn. The callers
        # here (bingo update tail, sanity repair) re-put their copies anyway
        # and must convert together or the tail put erases the txn's append.
        if signal not in self.signals:
            self.signals.append(signal)
            self.put()
            # bust the tick output cache, or an idle player (unchanged bitfields)
            # hits the cached fast path forever and never sees the signal
            Cache.clear_seen_checksum(self.idpts())

    def signal_conf(self, signal):
        _conf_signals(self.signals, signal)
        self.put()
        Cache.clear_seen_checksum(self.idpts())

    @staticmethod
    @ndb.transactional(retries=5)
    def signal_conf_txn(pkey, signal):
        """Clear a confirmed signal on a fresh read, touching only signals.
        The handler's copy is stale by the time the client answers, and a
        plain put of it erased concurrent grant transactions' slot bits."""
        p = pkey.get()
        if p is None:
            return False
        before = list(p.signals)
        _conf_signals(p.signals, signal)
        if p.signals == before:
            return False
        p.put()
        return True

    @staticmethod
    @ndb.transactional(retries=5)
    def connect_update_txn(pkey, vers, nag_signal=None):
        """connect's write: dll version and the out-of-date nag, on a fresh
        read. Same rule as signal_conf_txn -- connect's own copy is stale."""
        p = pkey.get()
        if p is None:
            return False
        changed = p.note_version(vers)
        if nag_signal and p.can_nag:
            if nag_signal not in p.signals:
                p.signals.append(nag_signal)
            p.can_nag = False
            changed = True
        if changed:
            p.put()
        return changed

    @staticmethod
    @ndb.transactional(retries=5)
    def signal_send_txn(pkey, signal):
        """signal_send's write, same fresh-read rule as signal_conf_txn."""
        p = pkey.get()
        if p is None or signal in p.signals:
            return False
        p.signals.append(signal)
        p.put()
        return True

    @staticmethod
    @ndb.transactional(retries=5)
    def claim_user_txn(pkey, user_key):
        """The seed download's write: claim this world for a site account on
        a fresh read, touching only `user`. Re-downloads happen mid-game, so
        this races grant txns like every other Player write."""
        p = pkey.get()
        if p is None or p.user == user_key:
            return False
        p.user = user_key
        p.put()
        return True

    @staticmethod
    def hl_chunk_append(p, chunk, hl):
        """Dedup + append + tail bookkeeping. Returns True if the line was
        appended (False = dedup skip) and whether the chunk is now sealed.
        Datastore-free so it can be tested directly; the txn below wraps it."""
        key = hl_dedup_key(hl)
        if key in p.hist_seen:
            return False
        chunk.lines.append(hl)
        p.hist_tail.append(key)
        while len(p.hist_tail) > HIST_TAIL:
            fell_out = p.hist_tail.pop(0)
            if fell_out not in p.hist_seen:
                p.hist_seen.append(fell_out)
        if len(chunk.lines) >= HIST_CHUNK_SIZE:
            p.hist_chunk = (p.hist_chunk or 0) + 1
        return True

    @staticmethod
    @ndb.transactional(retries=5, xg=True)
    def append_hl_chunked_txn(pkey, hl):
        # the line goes into a fixed-size child entity, so neither this append
        # nor any hot-path Player read grows with game length (two gets and a
        # put_multi of two small entities per line).
        p = pkey.get()
        gid, _, pid = pkey.id().partition(".")
        ckey = HistoryChunk.key_for(pkey.parent(), gid, pid, p.hist_chunk or 0)
        chunk = ckey.get() or HistoryChunk(key=ckey)
        if not Player.hl_chunk_append(p, chunk, hl):
            return False
        ndb.put_multi([chunk, p])
        return True

    @staticmethod
    @ndb.transactional(retries=5, xg=True)
    def transaction_pickup_batch(pkeys, grants):
        # grant every pickup to every player in ONE transaction — all Players
        # share the Game entity group, so this is a single-group txn with one
        # get_multi and one put_multi.
        # grants: list of (pickup, remove, coords, finder)
        players = [p for p in ndb.get_multi(pkeys) if p is not None]
        for p in players:
            for (pickup, remove, coords, finder) in grants:
                p.give_pickup(pickup, remove=remove, coords=coords, finder=finder, delay_put=True)
        ndb.put_multi(players)

    def give_pickup(self, pickup, remove=False, delay_put=False, coords=None, finder=None):
        if coords and finder:
            self.hints[str(coords)] = finder
        if pickup.code in ["RB", "TW"]:
            # handle upgrade refactor storage
            pick_id = str(pickup.id)
            if remove:
                if pick_id in self.bonuses:
                    self.bonuses[pick_id] -= 1
                    if self.bonuses[pick_id] == 0:
                        del self.bonuses[pick_id]
            else:
                if pick_id in self.bonuses:
                    if (not stacks(pickup)) or (pickup.max and self.bonuses[pick_id] >= pickup.max):
                        log.debug("Will not give %s pickup %s, as they already have %s" % (self.name(), pickup.name, self.bonuses[pick_id]))
                        self.bonuses[pick_id] = 1
                        return
                    self.bonuses[pick_id] += 1
                else:
                    self.bonuses[pick_id] = 1
        # bitfields
        elif pickup.code == "SK":
            self.skills = pickup.add_to_bitfield(self.skills, remove)
        elif pickup.code == "TP":
            self.teleporters = pickup.add_to_bitfield(self.teleporters, remove)
        elif pickup.code == "EV":
            self.events = pickup.add_to_bitfield(self.events, remove)
        if delay_put:
            return
        return self.put()

    def has_pickup(self, pickup):
        if pickup.code in ["RB", "TW"]:
            pick_id = str(pickup.id)
            return self.bonuses[pick_id] if pick_id in self.bonuses else 0
        elif pickup.code == "SK":
            return get_bit(self.skills, pickup.bit)
        elif pickup.code == "TP":
            return get_bit(self.teleporters, pickup.bit)
        elif pickup.code == "EV":
            return get_bit(self.events, pickup.bit)
        else:
            return 0

class BingoTeam(ndb.Model):
    captain = ndb.KeyProperty(Player)
    score = ndb.IntegerProperty(default=0)
    place = ndb.IntegerProperty()
    blackout_place = ndb.IntegerProperty()
    bingos = ndb.StringProperty(repeated=True)
    teammates = ndb.KeyProperty(Player, repeated=True)
    
    def name(self, cap=None):
        cap = cap or self.captain.get()
        teammates = self.teammates
        return cap.teamname() if self.teammates else cap.name()
    
    def pids(self):
        return [_pid(key) for key in [self.captain] + self.teammates]

    def to_json(self, players):
        cap = players.get(self.captain)
        if not cap:
            log.error("Player %s captain of team %s but not in provided players list %s", cap, _pid(self.captain), players)
            cap = self.captain.get()
        
        res = {"cap": {'pid': cap.pid(), 'name': cap.name()}, "score": self.score, "teammates": [], "bingos": self.bingos}
        if self.place:
            res["place"] = self.place
        res["name"] = self.name(cap = cap)
        for tm in self.teammates:
            if tm not in players:
                log.error("Player %s part of team %s but not in provided players list %s", tm, res["name"], players)
                continue
            res["teammates"].append({'pid': _pid(tm), 'name': players[tm].name()})
        return res

class BingoCard(ndb.Model):
    name = ndb.StringProperty()
    disp_name = ndb.TextProperty()
    help_lines = ndb.TextProperty(repeated=True)
    goal_type = ndb.StringProperty()
    goal_method = ndb.StringProperty()
    target = ndb.IntegerProperty()
    square = ndb.IntegerProperty()  # position in the single-dimension array
    subgoals = ndb.JsonProperty(repeated=True)
    completed_by = ndb.IntegerProperty(repeated=True)
    owner = ndb.IntegerProperty(default=0)
    early = ndb.BooleanProperty()  # i hate this but w/e
    meta = ndb.BooleanProperty(default=False)

    def bingothon_json(self, player):
        name = self.disp_name
        prog = player.bingo_prog[self.square]
        if self.goal_method == "count" or self.goal_type == "int":
            name += "\n%s/%s" % (prog.count, self.target)
        elif self.subgoals:
            for subgoal in self.subgoals:
                s = "*" if subgoal["name"] in prog.completed_subgoals else ''
                n = subgoal["disp_name"] if "disp_name" in subgoal else subgoal["name"]
                name += "\n%s%s%s" % (s, n, s)
        return {
            "name": name,
            "completed": prog.completed
        }

    def to_json(self, players, initial=False):
        res = {
            "name": self.name,
            "progress": {p.pid(): self.prog_json(p) for p in players},
            "completed_by": self.completed_by,
            "owner": self.owner
        }

        if initial:
            res["disp_name"] = self.disp_name
            res["help_lines"] = [s for s in self.help_lines]
            if self.square or self.square == 0:
                res["type"] = self.goal_type
                res["square"] = self.square
            if self.subgoals:
                res["subgoals"] = {subgoal["name"]: subgoal for subgoal in self.subgoals}
            if self.target:
                res["target"] = self.target

        return res


    def journey_origin(self):
        """Origin well of a journey card, or None. Subgoal keys are 'origin-destination'."""
        if self.name != "Journey" or not self.subgoals:
            return None
        return self.subgoals[0]["name"].partition("-")[0]

    def prog_json(self, player):
        res = player.bingo_prog[self.square].to_json()
        origin = self.journey_origin()
        if origin:
            # standing at the origin with nothing touched since: the card is live
            res["in_progress"] = player.bingo_last_tp == origin and not res["completed"]
        return res

    def progress(self, player):
        # type: (Player) -> Optional[BingoCardProgress]
        if not player or len(player.bingo_prog) < self.square:
            return None
        return player.bingo_prog[self.square]
    
    def update(self, card_data, player, teammates, capkey):
        # type: (dict, Player, List[Player], int) -> Optional['BingoEvent']
        p_progress = self.progress(player)
        prior_value = _pid(capkey) in self.completed_by
        prior_count = p_progress.count
        prior_completed = p_progress.completed

        if self.goal_type in ["bool"]:
            p_progress.completed = card_data["value"]
        elif self.goal_type == "int":
            p_progress.count = min(int(card_data["value"]), self.target)
            p_progress.completed = p_progress.count >= self.target
        elif self.goal_type == "multi":
            p_progress.count = min(int(card_data["total"]), self.target or 0)
            card_sgs = card_data["value"]
            p_progress.completed_subgoals = [subgoal["name"] for subgoal in self.subgoals if subgoal["name"] in card_sgs and card_sgs[subgoal["name"]]["value"]]
            if self.goal_method == "count":
                p_progress.completed = p_progress.count >= self.target
            elif self.goal_method == "and":
                p_progress.completed = all([subgoal["name"] in p_progress.completed_subgoals for subgoal in self.subgoals])
            elif self.goal_method == "or":
                p_progress.completed = any([subgoal["name"] in p_progress.completed_subgoals for subgoal in self.subgoals])
            else:
                log.error("invalid method %s" % self.goal_method)
        else:
            log.error("invalid goal type %s" % self.goal_type)
        completed = p_progress.completed
        if self.meta:
            # Meta squares (VertSym/HorizSym/Activate Squares) are derived from the
            # team's CURRENT board state — the same inputs for every member — so the
            # poster's freshly computed value is authoritative. Consulting stored
            # teammate snapshots let never-posting players (ghost slots from double
            # joins) freeze a stale pre-start `true` forever (game 133486, C2). No
            # debounce either: the underlying squares are already debounced.
            if prior_value != completed:
                return BingoEvent(event_type="square", loss=not completed, square=self.square, player=capkey, timestamp=datetime.utcnow())
            return None
        if teammates and not completed:
            all_progress = [self.progress(p) for p in teammates]
            if self.goal_type == "bool":
                completed = any([prog.completed for prog in all_progress])
            elif self.goal_type == "int":
                completed = max([prog.count for prog in all_progress]) >= self.target
            elif self.goal_type == "multi":
                all_progress.append(p_progress)
                count = max([prog.count for prog in all_progress])
                team_subgoals = set([subgoal for prog in all_progress for subgoal in prog.completed_subgoals])
                if self.goal_method == "count":
                    completed = count >= self.target
                elif self.goal_method == "and":
                    completed = all([subgoal["name"] in team_subgoals for subgoal in self.subgoals])
                elif self.goal_method == "or":
                    completed = any([subgoal["name"] in team_subgoals for subgoal in self.subgoals])
        if prior_value != completed:
            if completed:
                p_progress.pending_loss = False
                return BingoEvent(event_type="square", loss=False, square=self.square, player=capkey, timestamp=datetime.utcnow())
            # Regression. Only the player whose own data is down may stage/confirm
            # the loss — a teammate's interleaved update reflecting our stored
            # (possibly stale) state must not fast-track it. Staging requires the
            # transition (was completed, now isn't); confirming only requires the
            # pending flag plus still-down data, since our stored `completed` was
            # already overwritten to False by the staging update.
            if not p_progress.completed:
                if p_progress.pending_loss:
                    p_progress.pending_loss = False
                    return BingoEvent(event_type="square", loss=True, square=self.square, player=capkey, timestamp=datetime.utcnow())
                if prior_completed:
                    p_progress.pending_loss = True
            return None
        p_progress.pending_loss = False


class BingoEvent(ndb.Model):
    loss = ndb.BooleanProperty(default=False)
    event_type = ndb.StringProperty(default="square")
    square = ndb.IntegerProperty() # position in the single-dimension array
    bingo = ndb.StringProperty()
    timestamp = ndb.DateTimeProperty()
    first = ndb.BooleanProperty()
    player = ndb.KeyProperty(Player)
    def to_json(self, start_time):
        timeStr = ""
        if start_time:
            if self.timestamp < start_time:
                timeStr = "-" + round_time(start_time - self.timestamp)
            else:
                timeStr = round_time(self.timestamp-start_time)
        else:
            timeStr = str(self.timestamp.time())
        if self.event_type.startswith("misc"):
            return {'type': self.event_type, 'time': timeStr}
        res =  {'loss': self.loss, 'type': self.event_type, 'time': timeStr, 'player': _pid(self.player)}
        if self.event_type == 'square':
            res['square'] = self.square
        if self.event_type == 'bingo':
            res['bingo'] = self.bingo
            if self.first:
                res['first'] = True
                res['square'] = self.square
        if self.event_type == 'owner':
            res['square'] = self.square
        return res


EVLOG_KEEP = 100     # events kept on the entity: this IS the board feed
EVLOG_ARCHIVE = 50   # archive once this many have piled up past the tail

class BingoEventChunk(ndb.Model):
    """Events aged out of the on-entity feed, kept as a child of
    the BingoGameData so nothing is lost (the legacy 400-cap prune simply
    dropped them). Write-only from the netcode's perspective — get_json renders
    the entity's own tail, and it must stay that way: it runs on every update."""
    events = ndb.LocalStructuredProperty(BingoEvent, repeated=True)

    @staticmethod
    def key_for(bingo_key, gid, n):
        return ndb.Key(BingoEventChunk, "%s.%s" % (gid, n), parent=bingo_key)


def pick_discovery_squares(board, seed, square_count=2):
    """Which squares a board starts revealed. Early squares are preferred; a
    pick that is all symmetry squares, or has two squares touching, is redrawn."""
    if square_count > 25 or square_count < 1:
        square_count = 2
    rand = random.Random()
    rand.seed(seed)
    noncounts = [card.square for card in board if card.early]
    i = 0
    squares = []
    while i < 10:
        if len(noncounts) >= square_count:
            squares = rand.sample(noncounts, square_count)
        else:
            squares = noncounts + rand.sample(range(25), square_count - len(noncounts))
        if all("Sym" in board[card].name for card in squares): # girl noooooo
            i += 1
            continue
        # todo - i think this code might be useless?
        for s in squares:
            if (s % 5 != 4 and s+1 in squares) or (s % 5 != 0 and s-1 in squares) or (s > 4 and s-5 in squares) or (s < 20 and s+5 in squares):
                i += 1
                break
        else:
            break
    return squares[:]


class BingoWorldBoard(ndb.Model):
    """One world's board and the rules it finishes by."""
    world        = ndb.IntegerProperty()
    board        = ndb.LocalStructuredProperty(BingoCard, repeated=True)
    bingo_count  = ndb.IntegerProperty(default=3)
    square_count = ndb.IntegerProperty()
    goal         = ndb.StringProperty(default="bingos")
    difficulty   = ndb.StringProperty()
    meta         = ndb.BooleanProperty(default=False)
    discovery    = ndb.IntegerProperty(default=0)
    disc_squares = ndb.IntegerProperty(repeated=True)

    def to_json(self, players, initial=False):
        # progress is per-square per-player; another world's marks on the same
        # square index are its own board's business, never this one's
        players = [p for p in players if p.pid() == self.world]
        out = {"cards": [c.to_json(players, initial) for c in self.board]}
        if initial:
            out.update({"bingo_count": self.bingo_count, "square_count": self.square_count,
                        "goal": self.goal, "difficulty": self.difficulty, "meta": self.meta,
                        "disc_count": self.discovery})
            if self.disc_squares:
                out["discovery"] = list(self.disc_squares)
        return out


class BingoGameData(ndb.Model):
    players          = ndb.KeyProperty(Player, repeated=True)
    board            = ndb.LocalStructuredProperty(BingoCard, repeated=True)
    # empty means one board for the game, which is every board that exists today
    boards           = ndb.LocalStructuredProperty(BingoWorldBoard, repeated=True)
    start_time       = ndb.DateTimeProperty()
    started          = ndb.BooleanProperty(default=True)
    creator          = ndb.KeyProperty("User2", User)
    legacy_creator   = ndb.KeyProperty("User", LegacyUser)
    teams            = ndb.LocalStructuredProperty(BingoTeam, repeated=True)
    event_log        = ndb.LocalStructuredProperty(BingoEvent, repeated=True)
    bingo_count      = ndb.IntegerProperty(default=3)
    current_highest  = ndb.IntegerProperty(default=0)
    difficulty       = ndb.StringProperty()
    subtitle         = ndb.StringProperty()
    seed             = ndb.StringProperty()
    teams_allowed    = ndb.BooleanProperty(default=False)
    square_count     = ndb.IntegerProperty()
    teams_shared     = ndb.BooleanProperty(default=False)
    game             = ndb.KeyProperty("Game")
    discovery        = ndb.IntegerProperty()
    lockout          = ndb.BooleanProperty(default=False)
    disc_squares     = ndb.IntegerProperty(repeated=True)
    rand_dat         = ndb.TextProperty(compressed=True)
    meta             = ndb.BooleanProperty(default=False)
    ev_chunk         = ndb.IntegerProperty(default=0)  # next evlog archive index
    # Archipelago boards: K worlds, one team, pid == world. 0 = not an AP board.
    ap_worlds        = ndb.IntegerProperty(default=0)

    def ap_world_for(self, pid):
        """This board's AP world for a player, or None if it isn't an AP board
        (or the pid isn't one of its worlds)."""
        if not self.ap_worlds:
            return None
        pid = int(pid)
        return pid if 1 <= pid <= self.ap_worlds else None

    def board_for(self, world):
        """The squares that world plays. One board for the game until some world
        has its own."""
        for wb in self.boards:
            if wb.world == world:
                return wb.board
        return self.board

    def all_boards(self):
        return [wb.board for wb in self.boards] or [self.board]

    def discovery_squares(self, square_count=2):
        self.discovery = square_count
        if len(self.disc_squares) > 0:
            return self.disc_squares[:]
        self.disc_squares = pick_discovery_squares(self.board, self.seed, square_count)
        return self.disc_squares[:]
    

    @ndb.transactional(retries=5, xg=True)
    def reset(self):
        self.event_log = self.event_log[0:1]
        self.current_highest = 0
        self.started = False
        if 'start_time' in self._values:
            del self._values['start_time']
        for card in [c for b in self.all_boards() for c in b]:
            card.completed_by = []
        for team in self.teams:
            team.bingos = []
            team.score = 0
            if 'place' in team._values:
                del team._values['place']
            if 'blackout_place' in team._values:
                del team._values['blackout_place']
        self.put()

    @staticmethod
    def with_id(id):
        # type: (int) -> 'BingoGameData'
        return BingoGameData.get_by_id(int(id))

    def remove_player(self, pid):
        player = self.player(pid, False)
        if not player:
            log.error("Couldn't delete player: player not found")
            return False
        team = self.team(pid, False)
        pkeys_to_delete = [player.key]
        if team.captain == player.key:
            pkeys_to_delete += team.teammates
            self.teams.remove(team)
        else:
            team.teammates.remove(player.key)
        game = self.game.get()
        for k in pkeys_to_delete:
            game.remove_player(k.id())
            self.players.remove(k)
        return self.put()

    def get_players(self):
        # type: () -> List[Player]
        return [p.get() for p in self.players]

    def player_nums(self):  return [_pid(k) for k in self.players]

    def player(self, pid, create=False, delay_put=False):
        # type: (int, bool, bool) -> Optional[Player]
        # a shadow player resolves in the game's namespace like any other, and
        # adopting one onto the roster wedges every later board render
        if self.ap_worlds and not self.ap_world_for(pid):
            log.warning("Bingo game %s: pid %s is not one of its %s AP worlds",
                        self.key.id(), pid, self.ap_worlds)
            return None
        # per-world membership is settled at seating (the one create=True path);
        # adopting a stray world's bare player wedges every later board render
        if self.boards and not create and int(pid) not in self.player_nums():
            log.warning("Bingo game %s: world %s is not on its boards", self.key.id(), pid)
            return None
        gid = self.game.id()
        full_pid = "%s.%s" % (gid, pid)
        player = Player.get_by_id(full_pid, parent=self.game)
        if not player:
            if create:
                player = self.game.get().player(pid)
            else:
                log.warning("Bingo game %s has no player %s, returning None!", gid, pid)
                return None
        k = player.key
        if k not in self.players:
            self.players.append(k)
            if not delay_put:
                self.put()
        return player

    def init_player(self, pid):
        p = self.player(pid, True, True)
        if p.bingo_prog:
            log.warning("Player %s already had bingo card progress, won't reinit" % pid)
        else:
            p.bingo_prog = [BingoCardProgress(square=i) for i in range(25)]
            if self.meta:
                pass
            p.put()
        return p

    def get_json(self, initial=False, players=[]):
        players = players or self.get_players()
        players_by_pkey = {p.key: p for p in players}
        res = {
            'cards':  [c.to_json(players, initial) for c in self.board],
            # keyed by world; absent means the one board above is everyone's
            'boards': {str(wb.world): wb.to_json(players, initial) for wb in self.boards},
            'events': [e.to_json(self.start_time) for e in self.event_log],
            'teams': {_pid(t.captain): t.to_json(players_by_pkey) for t in self.teams},
            "gameId": self.game.id()
        }
        if self.creator:
            res["creator"] = self.creator.get().name
            user = User.get()
            res["is_owner"] = user and self.creator == user.key

        if self.start_time:
            res['countdown'] = datetime.utcnow() < self.start_time
            res['start_time_posix'] = timegm(self.start_time.timetuple())
  
        if initial:
            res["difficulty"] = self.difficulty
            res["bingo_count"] = self.bingo_count
            res["lockout"] = self.lockout
            res["subtitle"] = self.subtitle
            res["teams_allowed"] = self.teams_allowed
            res["ap_worlds"] = self.ap_worlds
            # the settings a board reroll rebuilds from: its modal opens on these
            res["board_seed"] = self.seed
            res["square_count"] = self.square_count
            res["meta"] = self.meta
            res["disc_count"] = self.discovery
            if self.discovery or len(self.disc_squares):
                res["discovery"] = self.discovery_squares()

            game = self.game.get()
            if game.params:
                res["paramId"] = game.params.id()
                if self.teams_shared:
                    params = game.fetch_params()
                    res["teamMax"] = params.players
        return res

    def plays_bingo(self, pid):
        """Whether this world's generator-page seed should carry bingo tracking.
        Only per-world games hand seeds out there; legacy boards' pids are
        join-order, a different space than the generator's player numbers."""
        return any(wb.world == int(pid) for wb in self.boards)

    def goals_line(self, pid):
        goals = OrderedDict()
        goals[""] = []
        for card in self.board_for(pid):
            if card.subgoals:
                goals[card.name] = [subgoal["name"] for subgoal in card.subgoals] + goals.get(card.name, [])
            elif card.goal_method == "count":
                goals[card.name] = goals.get(card.name, []) + ["COUNT"]
            else:
                goals[""].append(card.name + ("-%s" % card.target if card.target else ""))
        return "Goals" + "/".join(["%s:%s" % (goal, ",".join(set(subgoals))) for (goal, subgoals) in goals.items()]) + "\n"

    def get_seed(self, pid):
        sync_flag = ("Sync%s.%s," % (self.key.id(), pid))
        game = self.game.get()
        goalstr = self.goals_line(pid)
        if not game.params:
            return sync_flag + self.rand_dat + "\n" + goalstr
        else:
            params = game.params.get()
            # per-world games carry Bingo on the opted worlds' own flags already
            if not self.boards and Variation.BINGO not in params.variations:
                params.variations.append(Variation.BINGO)
                params = params.put().get()
            if self.ap_worlds:
                # pid is the world, so a rejoin can't shuffle anyone's AP slot.
                # Ahead of the solo shortcut: at K=1 that would hand world 1's
                # seed to any pid, the shadow's included
                p_number = self.ap_world_for(pid)
                if not p_number:
                    log.error("player %s is outside this AP board's %s worlds", pid, self.ap_worlds)
                    return None
                return sync_flag + params.get_seed(p_number, game_id=self.key.id(), include_sync=False) + goalstr
            elif self.boards:
                # per-world: the board's pids are the multiworld's worlds, so the
                # world number is the seed number -- never the team-index dance
                p_number = int(pid)
                if params.players < p_number or not self.plays_bingo(pid):
                    log.error("world %s has no per-world bingo seed here" % pid)
                    return None
                return sync_flag + params.get_seed(p_number, game_id=self.key.id(), include_sync=False) + goalstr
            elif params.players == 1:
                return sync_flag + params.get_seed(1, game_id=self.key.id(), include_sync=False) + goalstr
            else:
                team = self.team(pid, cap_only=False)
                if not team:
                    log.error("No team found for player %s" % pid)
                    return None
                p_number = team.pids().index(pid) + 1
                if params.players < p_number:
                    log.error("player %s can't get seed as there is no seed available" % pid)
                    return None
                return sync_flag + params.get_seed(p_number, game_id=self.key.id(), include_sync=False) + goalstr


    def team(self, pid, cap_only=True):
        # type: (int, bool) -> Optional[BingoTeam]
        pid = int(pid)
        maybe_team = [team for team in self.teams if _pid(team.captain) == pid]
        if not maybe_team and not cap_only:
            maybe_team += [team for team in self.teams if pid in team.pids()]
        if maybe_team:
            if len(maybe_team) > 1 and cap_only:
                log.error("Multiple teams found with the same player %s (%s), returning %s", pid, maybe_team, maybe_team[0].captain)
            res = maybe_team[0]
            return res
        return None

    def update(self, bingo_data, player_id, game_id, meta_init = False):
        # caller MUST hold bingo_lock(game_id): plain puts cannot conflict
        # because every writer of this entity holds the same lock (see the
        # bingo routes).
        self.archive_evlog(game_id)
        return self._update_inner(bingo_data, player_id, game_id, meta_init)

    def evlog_overflow(self):
        """Split event_log into (kept, archived) without touching the datastore.
        Keeps the newest EVLOG_KEEP plus every misc marker (the game's framing
        entries), exactly like the legacy prune — but the remainder is returned
        for archiving instead of dropped. Returns (None, None) if under the mark."""
        if len(self.event_log) <= EVLOG_KEEP + EVLOG_ARCHIVE:
            return None, None
        older, tail = self.event_log[:-EVLOG_KEEP], self.event_log[-EVLOG_KEEP:]
        keep_misc = [e for e in older if e.event_type.startswith("misc")]
        archived = [e for e in older if not e.event_type.startswith("misc")]
        return keep_misc + tail, archived

    def archive_evlog(self, game_id):
        """Age the event log's overflow into a chunk child. Caller must hold
        bingo_lock (update's contract). Puts self immediately so a crash or a
        no-write update can't lose ev_chunk and overwrite the archive."""
        kept, archived = self.evlog_overflow()
        if not archived:
            return 0
        t0 = monotonic()
        n = self.ev_chunk or 0
        BingoEventChunk(key=BingoEventChunk.key_for(self.key, game_id, n), events=archived).put()
        self.event_log = kept
        self.ev_chunk = n + 1
        self.put()
        netperf("evlog_archive", t0, gid=game_id, archived=len(archived), chunk=n, kept=len(kept))
        return len(archived)

    def all_events(self):
        """Full event log, archive included (cold path — never call from update:
        get_json's feed must stay the entity's own tail)."""
        res = []
        for chunk in BingoEventChunk.query(ancestor=self.key):
            res.extend(chunk.events)
        res.extend(self.event_log)
        res.sort(key=lambda e: e.timestamp or datetime.min)
        return res

    def _update_inner(self, bingo_data, player_id, game_id, meta_init = False):
        if not bingo_data and not meta_init:
            log.error("no bingo data????")
            return
        player_id = int(player_id)
        if not self.start_time and not meta_init:
            return
        now = datetime.utcnow()
        change_squares = set()
        loss_squares = set()
        win_players = False
        round_now = round_time(now - self.start_time) if not meta_init else "00:00"
        place = ""
        win_sig = "win:$Finished in %s place at %s!"
        team = self.team(player_id, cap_only=False)
        team.score = 0
        players_by_id = {_pid(p.key): p for p in self.get_players()}  # type: Dict[int, Player]
        player = players_by_id[player_id]
        # no card is named for it; journey cards read it via prog_json
        player.bingo_last_tp = ((bingo_data or {}).get("LastTouchedTeleporter") or {}).get("value") or ""
        cpid = _pid(team.captain)
        teammates = [players_by_id[pid] for pid in team.pids() if pid != player_id]
        need_write = False
        meta_cards = []
        
        def handle_event(ev):
            self.event_log.append(ev)
            change_squares.add(ev.square)
            if ev.loss:
                loss_squares.add(ev.square)
                if cpid in card.completed_by:
                    card.completed_by.remove(cpid)
            elif cpid not in card.completed_by:
                card.completed_by.append(cpid)
            if self.lockout:
                if not ev.loss and not card.owner:
                    card.owner = cpid
                    self.event_log.append(BingoEvent(loss=False, event_type="owner", square=ev.square, player=team.captain, timestamp=datetime.utcnow()))
                elif ev.loss and card.owner == cpid:
                    card.owner = 0
                    self.event_log.append(BingoEvent(loss=True, event_type="owner", square=ev.square, player=team.captain, timestamp=datetime.utcnow()))
                    if len(card.completed_by):
                        new_id = card.completed_by[0]
                        new_team = self.team(new_id, cap_only=False)
                        new_owner = new_team.captain if new_team else None  # type: Optional[ModelKey]
                        if new_owner is None:
                            log.error("Card is completed by player %d without team?!", new_id)
                        else:
                            card.owner = _pid(new_owner)
                            self.event_log.append(BingoEvent(loss=False, event_type="owner", square=ev.square, player=new_owner, timestamp=datetime.utcnow()))

        for card in self.board_for(cpid):  # type: BingoCard
            if card.meta:
                meta_cards.append(card)
                continue
            if card.name in bingo_data:
                ev = card.update(bingo_data[card.name], player, teammates, team.captain)
                if ev:
                    need_write = True
                    handle_event(ev)

            elif not meta_init:
                log.warning("card %s was not in bingo data for team/player %s", card.name if card else card, team.captain if team else team)
            if (cpid == card.owner) if self.lockout else (cpid in card.completed_by):
                team.score += 1
        if meta_cards:
            meta_data={}
            square_update = False
            cards_data = {str(i) : {"value":  (cpid == card.owner) if self.lockout else (cpid in self.board_for(cpid)[i].completed_by)} for i in range(25)}
            meta_data["Activate Squares"] = {"value": cards_data, "total": len([0 for p in cards_data.values() if p["value"]])}
            for card in meta_cards:
                if card.name in meta_data:
                    ev = card.update(meta_data[card.name], player, teammates, team.captain)
                    if ev:
                        need_write = square_update = True
                        handle_event(ev)
                    if (cpid == card.owner) if self.lockout else (cpid in card.completed_by):
                        team.score += 1
            if square_update:
                cards_data = {str(i) : {"value":  (cpid == card.owner) if self.lockout else (cpid in self.board_for(cpid)[i].completed_by)} for i in range(25)}
            meta_data={}
            meta_data["VertSym"] = {"value": all([cards_data[str(i + left)]["value"] == cards_data[str(i + right)]["value"]
                                     for i in range(0, 25, 5) for (left, right) in [(0, 4), (1,3)]])}
            meta_data["HorizSym"] = {"value": all([cards_data[str(i + top)]["value"] == cards_data[str(i + bot)]["value"]
                                     for i in range(5) for (top, bot) in [(0, 20), (5,15)]])}
            for card in meta_cards:
                if card.name in meta_data:
                    ev = card.update(meta_data[card.name], player, teammates, team.captain)
                    if ev:
                        need_write = square_update = True
                        handle_event(ev)
                    if (cpid == card.owner) if self.lockout else (cpid in card.completed_by):
                        team.score += 1
        if self.square_count:
            if team.score >= self.square_count and not team.place:
                self.event_log.append(BingoEvent(event_type = "win", loss = False, player = team.captain, timestamp = now))
                team.place = len([t.place for t in self.teams if t.place]) + 1
                place = ord_suffix(team.place)
                win_players = True
        elif change_squares:
            for bingo, line in lines_by_index.items():
                if set(line) & change_squares:
                    squares = len([square for square in line if cpid in self.board_for(cpid)[square].completed_by])
                    lost_squares = len(set(line) & loss_squares)
                    if lost_squares + squares == 5:
                        loss = lost_squares > 0
                        ev = BingoEvent(event_type = "bingo", loss = loss, bingo = bingo, player = team.captain, timestamp = now)
                        if loss and bingo in team.bingos:
                            team.bingos.remove(bingo)
                        elif bingo not in team.bingos:
                            team.bingos.append(bingo)
                            if(len(team.bingos) > self.current_highest):
                                ev.first = True
                                ev.square = len(team.bingos) # i hate this
                                self.current_highest += 1
                        self.event_log.append(ev)
                        if len(team.bingos) >= self.bingo_count and not team.place:
                            self.event_log.append(BingoEvent(event_type = "win", loss = False, player = team.captain, timestamp = now))
                            team.place = len([t.place for t in self.teams if t.place]) + 1
                            place = ord_suffix(team.place)
                            win_players = True
        if team.score == 25 and not team.blackout_place:
            team.blackout_place = len([1 for t in self.teams if t.blackout_place]) + 1
            win_players = True
            win_sig = "win:$%s to blackout at %s!"
            place = ord_suffix(team.blackout_place)
            need_write = True
        if win_players:
            p_list = [player] + teammates
            for p in p_list:
                p.signal_send(win_sig % (place, round_now))
            # Stash for the caller to re-bust AFTER this update fully lands.
            # signal_send busts the tick checksum itself, but a 1 Hz tick that
            # read this player just before the signal was put can finish after
            # the bust and re-arm the fast path with signal-less output; a
            # finished player's bitfields never change again, so the win sits
            # undelivered until alt+l (game 133908, pid 221: 16s stall).
            self._signal_pids = [p.idpts() for p in p_list]
            # an AP board's pids are its worlds, so winning it is those worlds'
            # Archipelago goal. Stashed for the caller: the room must not hear
            # about a win the transaction is still free to roll back
            if self.ap_worlds:
                self._ap_goal_worlds = [w for w in (self.ap_world_for(p.pid()) for p in p_list) if w]
        # Stash the board for the CALLER to publish after the transaction commits.
        # Writing the cache here published uncommitted state: a doomed concurrent
        # attempt (computed without the other player's just-committed progress)
        # would overwrite the cache before aborting — the source of the goal
        # flicker seen in games 133478/133482.
        self._board_json = self.get_json(players=players_by_id.values())
        player.put()
        if need_write:
            self.put()

class Seed(ndb.Model):
    # Seed ids used to be author_name:name but are being migrated to author_id:name
    placements = ndb.LocalStructuredProperty(Placement, repeated=True)
    flags = ndb.StringProperty(repeated=True)
    flagline = ndb.ComputedProperty(lambda self: ", ".join(sorted(self.flags)))
    hidden = ndb.BooleanProperty(default=False)
    description = ndb.StringProperty()
    # author-written spoiler, served in place of description when set
    spoiler = ndb.TextProperty(compressed=True)
    players = ndb.IntegerProperty(default=1)
    author_key = ndb.KeyProperty("author_key2", User)
    legacy_author_key = ndb.KeyProperty("author_key", LegacyUser)
    author = ndb.StringProperty()  # deprecated: will remove after migration is complete
    name = ndb.StringProperty()

    @staticmethod
    def get(author_name, seed_name):
        author = User.get_by_name(author_name)
        if author:
            return author.plando(seed_name)
        legacy_author = LegacyUser.get_by_name(author_name)
        if legacy_author:
            return legacy_author.plando(seed_name)
        log.warning("No user found for %s, doing a query instead...", author_name)
        return Seed.query(Seed.author == author_name, Seed.name == seed_name).get()

    def mode(self):
        mode_opt = [MultiplayerGameType.mk(f[5:]) for f in self.flags if f.lower().startswith("mode=")]
        return mode_opt[0] if mode_opt else None

    def shared(self):
        shared_opt = [f[7:].replace("+", " ").split(" ") for f in self.flags if f.lower().startswith("shared=")]
        return enums_from_strlist(ShareType, shared_opt[0]) if shared_opt else []

    @staticmethod
    def new(data):
        author = User.get()
        if not author:
            log.error("Error! No author found when attempting to create seed: %s", data)
            return None
        placements, players = Seed.get_placements(data['placements'])
        s = Seed(
            id="%s:%s" % (author.key.id(), data["name"]),
                description = data['desc'],
                spoiler = data.get('spoiler') or None,
                flags = [f.replace(' ', '+') for f in data['flags']],
                name = data['name'],
                author_key = author.key,
                placements = placements,
                players = players,
                hidden = data.get('hidden', False),
            )
        return s.put()

    @staticmethod
    def get_placements(raw_data):
        players = 1
        placements = []
        for placement in raw_data:
            plc = Placement(location=placement['loc'], zone=placement['zone'])
            for stuff in placement['stuff']:
                player = stuff['player']
                # absent owner means the world holding it owns it; a cross-world
                # item's owner counts toward the player total on its own, since
                # that player need hold nothing
                owner = stuff.get('owner')
                owner = str(owner) if owner and str(owner) != str(player) else None
                players = max(players, int(player), int(owner or player))
                plc.stuff.append(Stuff(code=stuff['code'], id=stuff['id'], player=player, owner=owner))
            placements.append(plc)
        return placements, players

    def update(self, data):
        author = self.author_key.get()
        if not author:
            log.error("Error! No author found when attempting to update seed %s with data %s",self, data)
            return None
        if self.key.id() != "%s:%s" % (author.key.id(), data["name"]):
            log.info("Deleting due to rename... goodbye world")
            new = Seed.new(data)
            self.key.delete()
            return new
        else:
            placements, players = Seed.get_placements(data['placements']) if 'placements' in data else (self.placements, self.players)
            self.populate(
                description = data.get('desc', self.description),
                spoiler = data.get('spoiler', self.spoiler) or None,
                flags = [f.replace(' ', '+') for f in data.get('flags', self.flags)],
                name = data.get('name', self.name),
                author_key = author.key,
                placements = placements,
                players = players,
                hidden = data.get('hidden', self.hidden),
            )
            
            return self.put()

    def flag_line(self):
        return "%s|%s" % (",".join(self.flags), self.name)

    def get_plando_json(self):
        placements = []
        for p in self.placements:
            stuffs = []
            for stuff in p.stuff:
                entry = {"player": stuff.player, "code": stuff.code, "id": stuff.id}
                if stuff.owner and stuff.owner != stuff.player:
                    entry["owner"] = stuff.owner
                stuffs.append(entry)
            placements.append({'loc': p.location, 'stuff': stuffs})
        return jsonify({'placements': placements, 'flagline': self.flag_line()})


# The multiplayer half of a seedgen request, plus the seed. A saved setting is
# player-agnostic on purpose: it describes one world, so it can later be
# assigned to a world rather than deciding how many there are. Tracking is NOT
# denied -- it is a property of the settings, and a bingo setting needs it.
# Denied rather than allowed, so a new variation is saved without being
# registered anywhere -- forgetting would silently roll the default instead.
SSP_DENY = frozenset([
    "seed", "players", "playerNames", "coopGenMode", "coopGameMode",
    "dedupShared", "antiBkBias", "syncShared", "shared", "teams",
    "apMode", "apExport", "apDeathLink",
    # a preset is one world's rulebook; it never carries the lobby's assignments
    "worldSettings",
])

# names that end up in a url path or query cannot carry these
URL_UNSAFE_NAME_CHARS = ["@", "/", "\\", "?", "#", "&", "="]

# both are entries the dropdown always shows: "latest" is the user's last seed,
# "default" is the untouched form
SSP_RESERVED_NAMES = frozenset(["latest", "default"])

# description is an indexed StringProperty, so anything past 1500 bytes fails at put()
SSP_DESC_MAX = 200


class SavedSeedParams(ndb.Model):
    """A preset: seedgen options a user saved under a name. Stored as a blob
    rather than a schema, since SeedGenParams.from_json defaults every field it
    reads, so a blob saved today still rolls once later versions add options."""
    settings = ndb.JsonProperty(compressed=True)
    name = ndb.StringProperty()
    description = ndb.StringProperty()
    hidden = ndb.BooleanProperty(default=False)
    owner_key = ndb.KeyProperty("owner_key", User)
    created = ndb.DateTimeProperty(auto_now_add=True)
    updated = ndb.DateTimeProperty(auto_now=True)

    @staticmethod
    def settings_from(params_json, world=1):
        """The saveable half of a seedgen request. A preset describes ONE world,
        so forced assignments are taken from that world alone -- keeping every
        world's would apply all of them to whichever world loaded it."""
        out = {k: v for k, v in (params_json or {}).items() if k not in SSP_DENY}
        world = str(world)
        # cross-world rows name another player and belong to the multiplayer
        # half; world and owner go with them, since the world a setting lands in
        # is whichever one loads it
        fass = [{k: v for k, v in f.items() if k not in ("world", "owner")}
                for f in (params_json or {}).get("fass") or []
                if str(f.get("world") or 1) == world
                and str(f.get("owner") or f.get("world") or 1) == world]
        if fass:
            out["fass"] = fass
        else:
            out.pop("fass", None)
        return out

    @staticmethod
    def desc_problem(desc):
        """User-facing reason this description can't be used, or None."""
        if len((desc or "").strip()) > SSP_DESC_MAX:
            return "That description is too long (%s characters max)." % SSP_DESC_MAX
        return None

    @staticmethod
    def name_problem(name):
        """User-facing reason this preset name can't be used, or None."""
        name = (name or "").strip()
        if not name:
            return "Give your preset a name."
        if name.lower() in SSP_RESERVED_NAMES:
            return "'%s' is a reserved name: the preset list always has an entry by that name." % name
        if len(name) > 64:
            return "That name is too long (64 characters max)."
        if ":" in name:
            return "Names can't contain a colon."
        # a preset name is a path segment in its own share link, so it takes the
        # same forbidden set as a username (User.rename)
        bad = [c for c in URL_UNSAFE_NAME_CHARS if c in name]
        if bad:
            return "Names can't contain %s." % " or ".join(bad)
        # someone else's preset shows as "name (them)", so a name with parens in
        # it reads as an owner that isn't there
        if "(" in name or ")" in name:
            return "Names can't contain brackets."
        return None

    @staticmethod
    def get(owner_name, name):
        owner = User.get_by_name(owner_name)
        return owner.saved_params(name) if owner else None

    def owned_by(self, user):
        return bool(user) and self.owner_key == user.key


class Game(ndb.Model):
    # id = Sync ID
    DEFAULT_SHARED = [ShareType.SKILL, ShareType.EVENT, ShareType.TELEPORTER]

    str_mode = ndb.StringProperty(default="None")
    str_shared = ndb.StringProperty(repeated=True)

    def get_mode(self):            return MultiplayerGameType.mk(self.str_mode) or MultiplayerGameType.SIMUSOLO
    def set_mode(self, mode):      self.str_mode = mode.value
    def get_shared(self):          return [ShareType.mk(st) for st in self.str_shared if ShareType.mk(st)]
    def set_shared(self, shared):  self.str_shared = [s.value for s in shared]
    mode           = property(get_mode, set_mode)
    shared         = property(get_shared, set_shared)
    start_time     = ndb.DateTimeProperty(auto_now_add=True)
    last_update    = ndb.DateTimeProperty(auto_now=True)
    # did anyone actually play? Set once, on the first pickup. Deliberately
    # has NO default: a game written before this property existed reads None
    # ("unknown", so game lists still show it) while a fresh game is written
    # explicitly False ("empty, hide it"). Reading it replaces a per-game
    # history walk that cost an ancestor query and a get per player.
    has_history    = ndb.BooleanProperty()
    hls            = ndb.LocalStructuredProperty(HistoryLine, repeated=True)
    players        = ndb.KeyProperty(Player, repeated=True)
    relics         = ndb.StringProperty(repeated=True)
    relics_by_world = ndb.JsonProperty()
    params         = ndb.KeyProperty(SeedGenParams)
    player_names   = ndb.StringProperty(repeated=True)
    bingo_data     = ndb.KeyProperty(BingoGameData)
    dedup          = ndb.BooleanProperty(default=False)
    creator        = ndb.KeyProperty("User2", User)
    legacy_creator = ndb.KeyProperty("User", LegacyUser)
    is_race        = ndb.BooleanProperty(default=False)
    spawn          = ndb.StringProperty(default="Glades")
    def mw_names(self):
        """pid -> the name that world's player chose, for anything naming a
        cross-world item. Empty on a game nobody named."""
        return {i + 1: n for i, n in enumerate(self.player_names or []) if n}

    def history(self, pids=[]):
        # Readers merge every storage layout unconditionally, so games written
        # under any older revision still read back whole. Oldest first:
        # Game.hls, Player.history (both write-retired), HistoryChunk children.
        players = self.get_players()
        res = list(self.hls)
        for p in players:
            pid = p.pid()
            for hl in p.history:
                if not hl.player:
                    hl.player = pid
                res.append(hl)
        # skip the ancestor query entirely unless some player has written a chunk
        # (hist_tail is set on the first chunked append and never cleared)
        if any(p.hist_tail or p.hist_chunk for p in players):
            for chunk in HistoryChunk.query(ancestor=self.key):
                cpid = int(chunk.key.id().split(".")[1])
                for hl in chunk.lines:
                    if not hl.player:
                        hl.player = cpid
                    res.append(hl)
        if pids:
            res = [hl for hl in res if hl.player in pids]
        res.sort(key=lambda hl: hl.timestamp or datetime.min)
        # Drop exact duplicates. Merging is only unsafe for one shape of legacy
        # data: the pre-2018 read-time migration copied Player.history into
        # Game.hls without clearing the source, so such a game holds each line
        # twice. A real re-find always differs in timestamp, so identical
        # five-tuples are never two genuine events.
        seen, out = set(), []
        for hl in res:
            k = (hl.player, hl.pickup_code, hl.pickup_id, hl.coords, hl.timestamp)
            if k not in seen:
                seen.add(k)
                out.append(hl)
        return out
    
    def player_nums(self):  return [_pid(k) for k in self.players]

    def summary(self, p=0):
        out_lines = ["%s (%s)" % (self.mode, ",".join([s.name for s in self.shared]))]
        if self.mode in [MultiplayerGameType.SHARED, MultiplayerGameType.SIMUSOLO] and len(self.players):
            src = self.players[p].get()
            for (field, cls) in [("skills", Skill), ("teleporters", Teleporter), ("events", Event)]:
                bitmap = getattr(src, field)
                names = []
                for id, bit in cls.bits.items():
                    i = cls(id)
                    if i:
                        if i.stacks:
                            cnt = get_taste(bitmap, i.bit)
                            if cnt > 0:
                                names.append("%sx %s" % (cnt, i.name))
                        elif get_bit(bitmap, i.bit):
                            names.append(i.name.replace(" teleporter", ""))
                if names:
                    out_lines.append("%s: %s" % (field, ", ".join(names)))
            trees = []
            relics = []
            warps = []
            bonuses = []
            for (name, cnt) in [(Pickup.name("RB" if k.isnumeric() else "TW", k), v) for k, v in src.bonuses.items()]:
                if "Tree" in name:
                    trees.append(name.replace(" Tree", ""))
                elif "Warp to" in name:
                    warps.append(name.replace("Warp to ", ""))
                elif "Relic" in name:
                    relics.append(name)
                else:
                    bonuses.append((name, cnt))
            if warps:
                out_lines.append("warps: %s" % ", ".join(warps))
            if trees:
                out_lines.append("trees: %s" % ", ".join(trees))
            if relics:
                out_lines.append("relics: %s" % ", ".join(relics))
            if bonuses:
                out_lines.append("upgrades:\n\t\t%s" % ("\n\t\t".join(["%s x%s" % b for b in bonuses])))
        return "\n\t" + "\n\t".join(out_lines)

    def get_players(self):
        return [p.get() for p in self.players]

    def visible_players(self):
        """get_players() minus the AP shadows. Every player-facing surface —
        tracker, history, item tracker — wants this one, not get_players():
        rendering a shadow leaks the bridge's plumbing, and computing
        reachability for one is pure waste on the request path."""
        return [p for p in self.get_players() if p and not p.is_ap_shadow()]

    def fetch_params(self):
        """The game's SeedGenParams via the process cache: SHARED and
        READ-ONLY. A path that mutates and puts (the bingo variation append)
        must keep using self.params.get() for a private copy."""
        return SeedGenParams.cached_by_key(self.params)

    def remove_player(self, key):
        key = ndb.Key(Player, key, parent=self.key)
        if key in self.players:
            self.players.remove(key)
            self.put()
        else:
            log.warning("Can't remove %s from %s" % (key, self.players))
        key.delete()

    # returns a dict; tuple group pids -> shared inventory
    def get_inventories(self, players, include_unshared_prog=False, use_have=False):
        inventories = {}

        def relevant(p, personal=False):
            if personal:
                return (not p.is_shared(self.shared)) and (p.code in ["AC", "KS", "HC", "EC", "SK", "EV", "TP"] or (p.code == "RB" and p.id in dedup_bonus_ids))
            return p.is_shared(self.shared)

        def add_pick_to_inv(inv, code, pid, coord, zone, personal=False):
            pick = Pickup.n(code, pid)
            if not pick:
                return
            if pick.code == "MU":
                for c in pick.children:
                    if relevant(c, personal):
                        inv[(c.code, c.id)] =  1 + inv.get((c.code, c.id), 0)
            if relevant(pick, personal):
                inv[(pick.code, pick.id)] =  1 + inv.get((pick.code, pick.id), 0)
            if personal or ShareType.MISC in self.shared:
                if coord in trees_by_coords:
                    tree_pick = trees_by_coords[coord]
                    inv[(tree_pick.code, tree_pick.id)] = 1
                if pick.code == "WT":
                    if zone in zone_translate and zone_translate[zone] in relics_by_zone:
                        pick = relics_by_zone[zone_translate[zone]]
                        inv[(pick.code, pick.id)] = 1
                    else:
                        log.error("Unknown relic zone %s" % zone)

        params  = self.fetch_params()
        groups = []
        pid_map = {}
        if not params:
            log.error("no placements????")
            return None
        if self.bingo_data:
            bingo = self.bingo_data.get()
            for team in bingo.teams:
                pids = tuple([_pid(p) for p in [team.captain] + team.teammates])
                for pid in pids:
                    pid_map[pid] = pid if bingo.boards else team.pids().index(pid) + 1
                groups.append(pids)
        else:
            groups = [tuple([p.pid() for p in players])]
        if params.sync.cloned:
            pid_map = {p.pid(): 1 for p in players}
        for group in groups:
            inv = {}
            seen_sets = {player.pid(): player.seen_coords() for player in players if player.pid() in group}
            if self.dedup:
                seen = set([c for coord_set in seen_sets.values() for c in coord_set])
                for p in params.placements:
                    coord = int(p.location)
                    if coord in seen:
                        stuff = [s for s in p.stuff if int(s.player) == 1]
                        if(len(stuff) != 1):
                            log.warning("stuff not found in %s", p)
                        else:
                            add_pick_to_inv(inv, stuff[0].code, stuff[0].id, coord, p.zone)
            else:
                shards = set()
                for p in params.placements:
                    coord = int(p.location)
                    for pid, seen in seen_sets.items():
                        if coord in seen:
                            stuff = [s for s in p.stuff if int(s.player) == pid_map.get(pid, pid)]
                            if(len(stuff) != 1):
                                log.warning("stuff not found in %s", p)
                            else:
                                if params.sync.cloned and stuff[0].code == "RB" and int(stuff[0].id) in dedup_bonus_ids:
                                    if coord in shards:
                                        log.debug("Skipping pickup")
                                        continue
                                    else:
                                        shards.add(coord)
                                add_pick_to_inv(inv, stuff[0].code, stuff[0].id, coord, p.zone)
            inventories[group] = inv
        if include_unshared_prog:
            inventories["unshared"] = {}
            for player in players:
                pid = player.pid()
                inv = {}
                seen = player.have_coords() if use_have else player.seen_coords()
                for p in params.placements:
                    coord = int(p.location)
                    if coord in seen:
                        stuff = [s for s in p.stuff if int(s.player) == pid_map.get(pid, pid)]
                        if(len(stuff) != 1):
                            log.warning("stuff not found in %s", p)
                        else:
                            add_pick_to_inv(inv, stuff[0].code, stuff[0].id, coord, p.zone, True)
                inventories["unshared"][pid] = inv
        return inventories

    def sanity_check(self):
        Cache.clear_items(self.key.id())
        ps = self.get_players()
        for p in ps:
            Cache.clear_reach(*p.idpts())
            Cache.clear_seen_checksum(p.idpts())    

        if self.mode != MultiplayerGameType.SHARED:
            return False
        if not Cache.san_check(self.key.id()):
            log.debug("Skipping sanity check")
            return False
        sanFailedSignal = "msg:@Major Error during sanity check. If this persists across multiple alt+l attempts please contact Eiko@"
        san_t0 = monotonic()
        shared_inventories = self.get_inventories(ps)
        i = 0
        for pids, inv in shared_inventories.items():
            players = [p for p in ps if p.pid() in pids]
            for key, count in inv.items():
                if key[0] == "WT":
                    continue # hahahaha fucking christ
                pickup = Pickup.n(key[0], key[1])
                if not stacks(pickup):
                    count = 1
                elif pickup.max:
                    count = min(count, pickup.max)
                for player in players:
                    has = player.has_pickup(pickup)
                    if has != count:
                        if has == 0 and count == 1:
                            log.warning("Player %s should have %s but did not. Fixing..." % (player.key.id(), pickup.name))
                        else:
                            log.warning("Player %s should have had %s of %s but had %s instead. Fixing..." % (player.key.id(), count, pickup.name, has))
                    # each give moves has one step toward count, so the
                    # direction never flips mid-repair
                    while has != count:
                        i += 1
                        last = has
                        player.give_pickup(pickup, remove=(has > count), delay_put=True)
                        has = player.has_pickup(pickup)
                        if has == last:
                            player.signal_send(sanFailedSignal)
                            log.critical("Aborting sanity check for Player %s: tried and failed to %s %s (at %s, should be %s)" % (player.key.id(), "decrement" if last > count else "increment", pickup.name, has, count))
                            return False
                        if i > 100:
                            player.signal_send(sanFailedSignal)
                            log.critical("Aborting sanity check for Player %s after too many iterations." % player.key.id())
                            return False
            stuples, bonuses = tuple(zip(*[(player.sharetuple(), player.bonuses) for player in players]))
            sk_max = max(tup[0] for tup in stuples)
            ev_max = max(tup[1] for tup in stuples)
            tp_max = max(tup[2] for tup in stuples)
            rb_cnt = max(tup[3] for tup in stuples)
            bonus_max = {}
            for p_bonus in bonuses:
                for item, cnt in p_bonus.items():
                    m = max(bonus_max.get(item, 0), cnt)
                    if m:
                        bonus_max[item] = m
            for player in players:
                Cache.set_hist(self.key.id(), player.pid(), self.history([player.pid()]))
                if player.skills < sk_max:
                    log.error("Checksum failure! Player %s had %s for sks instead of %s" % (player.pid(), player.skills, sk_max))
                    player.skills = sk_max
                if player.events < ev_max:
                    log.error("Checksum failure! Player %s had %s for evs instead of %s" % (player.pid(), player.events, ev_max))
                    player.events = ev_max
                if player.teleporters < tp_max:
                    log.error("Checksum failure! Player %s had %s for tps instead of %s" % (player.pid(), player.teleporters, tp_max))
                    player.teleporters = tp_max
                if len(player.bonuses) < rb_cnt:
                    msglines = ["Checksum failure!"]
                    for item, mx in bonus_max.items():
                        cnt = player.bonuses.get(item, 0)
                        if cnt  < mx:
                            msglines.append("Player %s had %s of %s instead of %s" % (player.pid(), cnt, item, mx))
                            player.bonuses[item] = mx
                    if len(player.bonuses) < rb_cnt:
                        msglines.append("Failed to update bonuses! bonuses: %s, player is %s, calculated maxes are %s" % (bonuses, player.pid(), bonus_max))
                    log.error("\n".join(msglines))
                player.put()
        netperf("sanity_check", san_t0, gid=self.key.id(), players=len(ps), fixes=i)
        return True
    
    def mw_shareable(self, pickup):
        """What a seed line shares, by found_pickup's rules: MW slots, TW warps
        and EV5 never do; a multipickup shares whichever children do."""
        if not pickup or pickup.code in ["MW", "TW"] or (pickup.code == "EV" and int(pickup.id) == 5):
            return []
        if pickup.code == "MU":
            return [p for child in pickup.children for p in self.mw_shareable(child)]
        return [pickup] if pickup.is_shared(self.shared) else []

    def mw_release_shared(self, finisher_pid, params):
        """The shared half of the release, granted to every player. A shared
        category is one copy total, sitting as a plain local line with no owner
        and no slot, so the slot pass above cannot see it -- and a finished
        world is nobody's to explore (game 136058 stranded Climb)."""
        if not self.shared:
            return 0
        finisher = self.player(finisher_pid)
        seen = set(finisher.seen_coords())
        by_coords = defaultdict(list)
        for (loc, code, id, zone) in params.get_seed_data(finisher_pid):
            try:
                coords = int(loc)
            except ValueError:
                continue
            if coords in seen:
                continue
            picks = self.mw_shareable(Pickup.n(code, id))
            if picks:
                by_coords[coords] += [(p, zone) for p in picks]
        fresh = Player.claim_shared_released_txn(finisher.key, sorted(by_coords))
        grants = [(pickup, False, coords, finisher_pid) for coords in fresh for pickup, _ in by_coords[coords]]
        if not grants:
            return 0
        players = [p for p in self.get_players() if p]
        Player.transaction_pickup_batch([p.key for p in players], grants)
        Cache.clear_items(self.key.id())
        for p in players:
            Cache.clear_seen_checksum(p.idpts())
            Cache.clear_reach(*p.idpts())
        for coords in fresh:
            for pickup, zone in by_coords[coords]:
                hl = HistoryLine(pickup_code=pickup.code, timestamp=datetime.utcnow(), pickup_id=str(pickup.id),
                                 coords=coords, removed=False, player=finisher_pid)
                if Player.append_hl_chunked_txn(finisher.key, hl):
                    Cache.append_hl(self.key.id(), finisher_pid, hl)
        return len(grants)

    def mw_release(self, finisher_pid, params=None):
        """Multiworld release: when a player finishes, every item still
        sitting in their world that belongs to someone else is granted to its
        owner (their world is done being explored). Idempotent."""
        t0 = monotonic()
        params = params or self.fetch_params()
        # AP mode: slots owned by shadow players (pid > K) are the bridge's
        # outbox; releasing a world must never force-check them (whether the
        # AP room releases on goal is the room's policy, not ori's)
        ap_worlds = int(params.players) if getattr(params, "ap_mode", False) else None
        by_owner = defaultdict(list)
        for (loc, code, id, zone) in params.get_seed_data(finisher_pid):
            if code != "MW" or is_mw_manifest_loc(loc):
                continue  # manifests are our own slots, not the world's contents
            try:
                owner, slot, _ = id.split(",", 2)
                owner, slot = int(owner), int(slot)
            except ValueError:
                log.warning("unparseable MW placement %s in game %s", id, self.key.id())
                continue
            if ap_worlds and owner > ap_worlds:
                continue
            if owner != finisher_pid:
                by_owner[owner].append(slot)
        netperf("mw_release_prep", t0, gid=self.key.id(), pid=finisher_pid, owners=len(by_owner))
        t_shared = monotonic()
        shared = self.mw_release_shared(finisher_pid, params)
        netperf("mw_release_shared", t_shared, gid=self.key.id(), pid=finisher_pid, shared=shared)
        released = shared
        finisher_name = self.player(finisher_pid).wire_name()
        gained = defaultdict(int)
        if shared:
            # shadows take the grant like anyone else, but never a message
            for p in self.visible_players():
                gained[p.pid()] += shared
        for owner_pid, slots in by_owner.items():
            t_owner = monotonic()
            owner = self.player(owner_pid)
            newly = Player.mark_slots_txn(owner.key, slots)
            if newly:
                released += newly
                gained[owner_pid] += newly
                Cache.clear_seen_checksum(owner.idpts())
            netperf("mw_release_owner", t_owner, gid=self.key.id(), owner=owner_pid, slots=len(slots), newly=newly)
        for pid, count in gained.items():
            if pid == finisher_pid or not count:
                continue
            p = self.player(pid)
            # fires mid grant-burst, the worst window for a stale put
            msg = "msg:@%s finished! %s item%s from their world released to you@" % (
                finisher_name, count, "" if count == 1 else "s")
            if Player.signal_send_txn(p.key, msg):
                Cache.clear_seen_checksum(p.idpts())
        log.info("mw_release: game %s player %s released %s items (%s shared)", self.key.id(), finisher_pid, released, shared)
        return released


    def rebuild_hist(self):
        # shadows have no history, and registering their pids here is what
        # puts them in the cache's pid map for every later reader
        gid = self.key.id()
        for pid in [p.pid() for p in self.visible_players()]:
            Cache.set_hist(gid, pid, self.history([pid]))
        return Cache.get_hist(gid)
    
    def create_ap_shadows(self, params):
        """AP-mode games: shadow players K+1..2K, one per world. Their slot
        bitfields are the AP bridge's durable outbox (found_pickup flips bit i
        on shadow K+v when world v checks reserved slot i); no client ever
        connects as one. Idempotent."""
        k = int(params.players)
        for w in range(1, k + 1):
            shadow = self.player(k + w)
            if shadow.nickname != AP_SHADOW_NICK:
                shadow.nickname = AP_SHADOW_NICK
                shadow.put()
        Cache.clear_names(self.key.id())

    def rolled_name(self, pid):
        """The name this world was rolled with, if any."""
        names = self.player_names or []
        pid = int(pid)
        return names[pid - 1] if 1 <= pid <= len(names) else None

    def player(self, pid, create=True, delay_put=False):
        gid = self.key.id()
        full_pid = "%s.%s" % (gid, pid)
        player = Player.get_by_id(full_pid, parent=self.key)
        k = None
        if not player:
            if not create:
                log.warning("Game %s has no player %s, will not create", gid, pid)
                return None
            if(self.mode == MultiplayerGameType.SHARED and len(self.players)):
                src = self.players[0].get()
                player = Player(id=full_pid, skills=src.skills, events=src.events, teleporters=src.teleporters, hints={}, bonuses=src.bonuses.copy(), history=[], signals=[], parent=self.key)
            else:
                player = Player(id=full_pid, skills=0, events=0, teleporters=0, history=[], hints={}, bonuses={}, parent=self.key)
            player.seed_name = self.rolled_name(pid)
            k = player.put()
            Cache.set_pos(gid, pid, 189, -210)
            Cache.set_hist(gid, pid, [])
        else:
            k = player.key
        if k not in self.players:
            self.players.append(k)
            if not delay_put:
                self.put()
        return player

    def found_pickup(self, pid, pickup, coords, remove, override, zone="", finder_bflds=None):
        pid = int(pid)
        retcode = 200
        share = pickup.is_shared(self.shared)
        players = self.get_players()
        finder = [p for p in players if p.pid() == pid]
        if not finder:
            log.error("Got pickup from unknown player %s! Creating to avoid crash" % pid)
            finder = self.player(pid)
        else:
            finder = finder[0]
        finder_seen = finder.seen_coords()

        if pickup.code == "WT":
            if coords in pbc:
                zone = zone_translate[pbc[coords].zone]
            if zone in relics_by_zone:
                Cache.clear_items(self.key.id())
                pickup = relics_by_zone[zone]
                share = ShareType.MISC in self.shared

        if abs(coords) == 1 and pickup.code == "TP":
            share = ShareType.TELEPORTER in self.shared
            override = True # fuck no it actually should work like this. lol.
        if self.mode == MultiplayerGameType.MULTIWORLD:
            # shared-category singletons fan out (see the mode branch below);
            # everything else is client-local or a slot flip. TW warps are
            # world-local by construction; EV5 is each world's finale trigger.
            if pickup.code in ["MW", "TW"] or (pickup.code == "EV" and int(pickup.id) == 5):
                share = False
            if pickup.code == "MW":
                # no seen-coords dedup: the finder's 1Hz tick can deliver the
                # seen bit BEFORE the found POST arrives, and the early return
                # below would silently drop the slot flip (slot handling is
                # idempotent, so reprocessing is free)
                finder_seen = []
        if coords in finder_seen:
            if share:
                if not override:
                    # man just. fuck it?
#                    log.info("Ignoring duplicate pickup at location %s from player %s" % (coords, pid))
#                    return 410
                    # a lone duplicate is usually a client resend, not a desync —
                    # only run the (expensive) sanity check on a second strike.
                    if Cache.second_strike(self.key.id()):
                        self.sanity_check()
                    return 200
            else:
                return 200

        if pickup.code == "MU":
            for child in pickup.children:
                retcode = max(self.found_pickup(pid, child, coords, remove, False, zone, finder_bflds), retcode)
            return retcode
        if self.mode == MultiplayerGameType.SHARED:
            if self.bingo_data:
                bingo = self.bingo_data.get()
                team = bingo.team(pid, cap_only=False)
                if team:
                    players = [p for p in players if p.pid() in team.pids()]
                else:
                    log.error("No bingo team found for player %s!" % pid)
            if share and (self.dedup or (pickup.code == "RB" and pickup.id in dedup_bonus_ids)):
                p = self.fetch_params()
                if p.sync.cloned and coords in [coord for p in players if p.pid() != pid for coord in p.seen_coords()]:
                    log.debug("Won't grant %s to player %s, as a teammate found it already" % (pickup.name, pid))
                    return 410
            ftple = finder.sharetuple()
            for p in players:
                ptple = p.sharetuple()
                if ftple != ptple:
                    log.warning("sharetuple mismatch! %s is not %s, triggering san check" % (ftple, ptple))
                    # transient mismatches are expected while a grant propagates;
                    # only sanity-check when the mismatch persists.
                    if Cache.second_strike(self.key.id()):
                        self.sanity_check()
                    break
            grants = []
            shared_tree = False
            if ShareType.MISC in self.shared and coords in trees_by_coords:
                grants.append((trees_by_coords[coords], remove, None, None))
                shared_tree = True
            if share:
                grants.append((pickup, remove, coords, pid))
            elif not shared_tree:
                retcode = 406
            if grants:
                Player.transaction_pickup_batch([p.key for p in players], grants)
                # clear AFTER commit so a failed txn can't leave stale-cleared caches
                for player in players:
                    Cache.clear_seen_checksum(player.idpts())
        elif self.mode == MultiplayerGameType.SPLITSHARDS:
            if pickup.code != "RB" or pickup.id not in [17, 19, 21]:
                retcode = 406
            else:
                if finder.bonuses[str(pickup.id)] < 3:
                    if coords in [coord for p in players if p.pid() != pid for coord in p.seen_coords()]:
                        log.debug("%s at %s already taken, player %s will not get one." % (pickup.name, coords, pid))
                        return 410
        elif self.mode == MultiplayerGameType.MULTIWORLD:
            if pickup.code == "MW":
                owner = next((p for p in players if p.pid() == pickup.owner), None)
                if not owner:
                    # the owner hasn't connected yet: create their Player so
                    # the find is durable, not dropped
                    owner = self.player(pickup.owner)
                if Player.mark_slot_txn(owner.key, pickup.slot):
                    # bust the owner's tick cache, or an idle owner (unchanged
                    # bitfields) never sees the flip -- same failure mode as
                    # the dropped win signals (see signal_send)
                    Cache.clear_seen_checksum(owner.idpts())
            elif share:
                # shared singleton: grant every world. The finder's client
                # already granted itself; its server entity converges here too.
                Player.transaction_pickup_batch([p.key for p in players], [(pickup, remove, coords, pid)])
                Cache.clear_items(self.key.id())
                for player in players:
                    Cache.clear_seen_checksum(player.idpts())
                    Cache.clear_reach(*player.idpts())
            # own-world pickups need no server-side action: the finder's
            # client granted itself already, and seen/have bits arrive by tick.
            # (release-on-finish is triggered by the /complete route at the
            # credits, not by any pickup: warmth returned is granted at the
            # START of the final escape, which is too early)
        elif self.mode in [MultiplayerGameType.SIMUSOLO, MultiplayerGameType.BINGO]:
            pass
        else:
            log.error("game mode %s not supported" % self.mode)
            retcode = 404
        hl = HistoryLine(pickup_code=pickup.code, timestamp=datetime.utcnow(), pickup_id=str(pickup.id), coords=coords, removed=remove, player=pid)
        if coords in range(24, 60, 4) and zone in map_coords_by_zone:
            hl.map_coords = map_coords_by_zone[zone]
        if Player.append_hl_chunked_txn(finder.key, hl):
            Cache.append_hl(self.key.id(), hl.player, hl)
            if not self.has_history:
                try:
                    Game.mark_history_txn(self.key)
                    self.has_history = True   # once per game, not per pickup
                except Exception:
                    # a game-list nicety must never fail a pickup that has
                    # already committed its history line and its grants
                    log.exception("could not mark game %s as played", self.key.id())
        if hl.map_coords or coords in trees_by_coords:
            Cache.clear_items(self.key.id())
        return retcode

    def clean_up(self):
        [p.delete() for p in self.players]
        Cache.remove_game(self.key.id())
        if self.params:
            self.params.delete()
        if self.bingo_data:
            self.bingo_data.delete()
        self.key.delete()
        return self.key

    def reset(self):
        self.hls = []
        self.has_history = False
        self.start_time = datetime.now()
        for player in self.get_players():
            player.reset()
        # chunks outlive Player.history, and Game.history() reads both
        ndb.delete_multi(HistoryChunk.query(ancestor=self.key).fetch(keys_only=True))
        if self.bingo_data:
            b_data = self.bingo_data.get()
            b_data.creator = self.creator
            b_data.reset()
        Cache.remove_game(self.key.id())
        self.rebuild_hist()
        self.put()

    def relics_for(self, player):
        """That world's relic zones; games rolled before this field fall back to
        the one list they stored, which was world 1's."""
        return (self.relics_by_world or {}).get(str(player), self.relics)

    @staticmethod
    def with_id(id):
        return Game.get_by_id(int(id))

    @staticmethod
    @ndb.transactional(retries=3)
    def mark_history_txn(key):
        """Someone actually played: flip has_history on a freshly read entity.
        Never a plain put -- writing a Game read on the pickup path would
        erase whatever the 1Hz tick wrote meanwhile (the 134701 bug class)."""
        game = key.get()
        if game is None or game.has_history:
            return
        game.has_history = True
        game.put()

    @staticmethod
    def clean_old(log_prog = False, timeout_window=timedelta(hours=1440)):
        start_time = datetime.now()
        i = 0
        for game in Game.query(Game.last_update < datetime.now() - timeout_window).fetch(500):
            i+=1
            game.clean_up()
            if datetime.now() - start_time > timedelta(seconds = 30):
                log.warning("stopping early because we're running out of time")
                if log_prog:
                    log.warning("%s remaining" % Game.query(Game.last_update < datetime.now() - timeout_window).count())
                return i, False
        if i == 500:
            log.warning("stopping after hitting 500 targets")
            if log_prog:
                log.warning("%s remaining" % Game.query(Game.last_update < datetime.now() - timeout_window).count())
            return i, False
        return i, True

    @staticmethod
    def get_open_gid():
        gid = Cache.current_gid()
        if gid == -1:
            if not debug:
                log.info("Need to grab the list of games to get a free gid, will be slow...")
            in_use = [int(game.key.id()) for game in Game.query(Game.last_update > datetime.now() - timedelta(hours=24))]
            if len(in_use) == 0:
                if not debug:
                    log.warning("Need to check vs every GID! Will be much slower!")
                in_use = [int(game.key.id()) for game in Game.query()] + [1]
            gid = max(in_use)
        jump = 1
        gid += jump
        while Game.with_id(gid) is not None:
            gid += jump
            jump += 1
        Cache.set_gid(gid)
        return gid

    @staticmethod
    def from_params(params, gid=None):
        game = Game(
            id=int(gid or Game.get_open_gid()),
            params=params.key, players=[], has_history=False,
            str_shared=[s.value for s in params.sync.shared],
            str_mode=params.sync.mode.value,
            dedup=params.sync.dedup,
            player_names=list(params.player_names or [])
        )
        game.is_race = Variation.RACE in params.variations
        if Variation.WORLD_TOUR in params.variations:
            # relic zones are sampled per world, so every world needs its own list
            worlds = range(1, (params.players or 1) + 1)
            game.relics_by_world = {str(w): [zone for (_, code, __, zone) in params.get_seed_data(w)
                                             if code == "WT"] for w in worlds}
            game.relics = game.relics_by_world.get("1", [])
        if not bingo_worlds(params):
            teams = params.sync.teams
            if teams:
                for playerNums in teams.values():
                    team = [game.player(p, delay_put = True) for p in playerNums]
                    teamKeys = [p.key for p in team]
                    for player in team:
                        tset = set(teamKeys)
                        tset.remove(player.key)
                        player.teammates = list(tset)
                        player.put()
            else:
                for i in range(params.players):
                    player = game.player(i + 1)
                    Cache.set_pos(gid, i + 1, 189, -210)
        if getattr(params, "ap_mode", False):
            game.create_ap_shadows(params)
        user = User.get()
        if user:
            game.creator = user.key
        game.put()
        game.rebuild_hist()
        return game

    @staticmethod
    def new(_mode=None, _shared=None, gid=None):
        if isinstance(_shared, (list,)):
            shared = enums_from_strlist(ShareType, _shared)
        else:
            shared = Game.DEFAULT_SHARED
        mode = MultiplayerGameType.mk(_mode) if _mode else MultiplayerGameType.SIMUSOLO
        gid = int(gid or Game.get_open_gid())
        game = Game(id=gid, players=[], str_shared=[s.value for s in shared],
                    str_mode=mode.value, has_history=False)
        user = User.get()
        if user:
            game.creator = user.key
        key = game.put()
        Cache.set_gid(gid)
        log.debug("Game.new(%s, %s, %s): Created game %s ", _mode, _shared, id, game)
        return key


class AnnouncedPatchNotes(ndb.Model):
    """Newest release already posted to an announce channel; the entity id is
    the channel name ("main" / "dev").

    The marker is claimed in a transaction and written BEFORE the webhook call,
    so a redeploy, a retry or a second instance can never double-post. The cost
    is that a failed POST drops that announcement rather than retrying it, which
    is logged loudly and can be resent with /patchnotes/announce. Silence is a
    much better failure here than posting a release to Discord twice."""
    version = ndb.StringProperty()
    updated = ndb.DateTimeProperty(auto_now=True)

    @staticmethod
    @ndb.transactional(retries=5)
    def claim(channel, newest):
        """Advance the marker and return the version it was on, or None if
        there is nothing to announce. The first run on a channel seeds the
        marker silently: otherwise switching this on would replay the whole
        back catalogue into the channel."""
        key = ndb.Key(AnnouncedPatchNotes, channel)
        row = key.get()
        if row and row.version == newest:
            return None
        first_run = row is None
        if first_run:
            row = AnnouncedPatchNotes(key=key)
        was = row.version
        row.version = newest
        row.put()
        if first_run:
            log.info("patchnotes: seeded %s marker at %s, posting nothing", channel, newest)
            return None
        return was

