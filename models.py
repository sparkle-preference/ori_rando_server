from google.appengine.ext import ndb
from google.appengine.api import users

import logging as log
from json import dumps as jsonify
from datetime import datetime, timedelta
from calendar import timegm
from collections import defaultdict

from seedbuilder.seedparams import Placement, Stuff, SeedGenParams
from enums import MultiplayerGameType, ShareType
from util import picks_by_coord, get_bit, get_taste, enums_from_strlist, PickLoc, ord_suffix
from pickups import Pickup, Skill, Teleporter, Event
from cache import Cache

def _pid(pkey):
    try:
        return int(pkey.id().partition(".")[2])
    except Exception as e:
        log.error("invalid pkey %s: %s, returning 1", pkey, e)
        return 1

def round_time(t):
    parts = str(t).split(":")
    parts[-1] = str(round(float(parts[-1]), 2))
    return ":".join(parts)


pbc = picks_by_coord(extras=True)
map_coords_by_zone = { "valleyOfTheWind": -4080172, "sorrowPass": -4519716, "sunkenGlades": -840248, "forlornRuins": -8440308, "hollowGrove": 3479880, "mangrove": 4159708, "moonGrotto": 4759608, "mountHoru": 560340, "thornfeltSwamp": 6759868}
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
    player = ndb.KeyProperty("Player", required=True)
    completed = ndb.BooleanProperty()
    locked = ndb.BooleanProperty()
    count = ndb.IntegerProperty()
    completed_subgoals = ndb.StringProperty(repeated=True)

    def complete(self):    return self.completed and not self.locked
    def to_json(self):
        return {
            'completed': self.complete(),
            'count': self.count,
            'subgoals': self.completed_subgoals
        }

class BingoCard(ndb.Model):
    name = ndb.StringProperty()
    disp_name = ndb.TextProperty()
    help_lines = ndb.TextProperty(repeated=True)
    goal_type = ndb.StringProperty()
    goal_method = ndb.StringProperty()
    target = ndb.IntegerProperty()
    square = ndb.IntegerProperty()  # position in the single-dimension array
    subgoals = ndb.JsonProperty(repeated=True)
    player_progress = ndb.LocalStructuredProperty(BingoCardProgress, repeated=True)
    current_owner = ndb.IntegerProperty(repeated=True)

    def to_json(self):
        res = {
            "name": self.name,
            "disp_name": self.disp_name,
            "help_lines": self.help_lines,
            "type": self.goal_type,
            "progress": {_pid(pp.player): pp.to_json() for pp in self.player_progress}
            }
        if self.square or self.square == 0:
            res["square"] = self.square
        if self.subgoals:
            res["subgoals"] = {subgoal["name"]: subgoal for subgoal in self.subgoals}
        if self.target:
            res["target"] = self.target
        if self.current_owner:
            res["owner"] = self.current_owner[0]
        return res


    def progress(self, pkey):
        p_progress = [pp for pp in self.player_progress if pp.player == pkey]
        if not p_progress:
            p_progress = [BingoCardProgress(player=pkey, completed=False, count=0)]
            self.player_progress.append(p_progress[0])
        if len(p_progress) > 1:
            log.warning("too many playerprogress for player %s" % pkey)
        return p_progress[0]
    
    def update(self, card_data, team, pid, players):
        pkey = players[pid].key
        p_progress = self.progress(pkey)
        prior_value = p_progress.completed
        if self.goal_type == "bool":
            p_progress.completed = card_data["value"]
        elif self.goal_type == "int":
            p_progress.count = min(int(card_data["value"]), self.target)
            p_progress.completed = p_progress.count >= self.target
        elif self.goal_type == "multi":
            p_progress.count = min(int(card_data["total"]), self.target)
            p_progress.completed_subgoals = [subgoal["name"] for subgoal in self.subgoals if card_data["value"][subgoal["name"]]["value"]]
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

        if team and team["teammates"]:
            completed = False
            all_pkeys = [players[t].key for t in team["teammates"]]
            all_pkeys.append(players[team['cap']].key)
            all_progress = [self.progress(p) for p in all_pkeys if p != pkey] + [p_progress]
            if self.goal_type == "bool":
                completed = any([prog.completed for prog in all_progress])
            elif self.goal_type == "int":
                completed = max([prog.count for prog in all_progress]) >= self.target
            elif self.goal_type == "multi":
                count = max([prog.count for prog in all_progress])
                team_subgoals = set([subgoal for prog in all_progress for subgoal in prog.completed_subgoals])
                if self.goal_method == "count":
                    completed = count >= self.target
                elif self.goal_method == "and":
                    completed = all([subgoal["name"] in team_subgoals for subgoal in self.subgoals])
                elif self.goal_method == "or":
                    completed = any([subgoal["name"] in team_subgoals for subgoal in self.subgoals])
            for prog in all_progress:
                prog.completed = completed
            p_progress.completed = completed

        if prior_value != p_progress.completed:
            event = BingoEvent(event_type="square", loss = not p_progress.completed, square=self.square, player=pkey, timestamp=datetime.utcnow())
            return event


class BingoEvent(ndb.Model):
    loss = ndb.BooleanProperty(default=False)
    event_type = ndb.StringProperty(default="square")
    square = ndb.IntegerProperty() # position in the single-dimension array
    bingo = ndb.StringProperty()
    timestamp = ndb.DateTimeProperty()
    first = ndb.BooleanProperty()
    player = ndb.KeyProperty("Player")
    def to_json(self, start_time):
        res =  {'loss': self.loss, 'type': self.event_type, 'time': round_time(self.timestamp-start_time), 'player': _pid(self.player)}
        if self.event_type == 'square':
            res['square'] = self.square
        if self.event_type == 'bingo':
            res['bingo'] = self.bingo
            if self.first:
                res['first'] = True
                res['square'] = self.square
        return res


class BingoGameData(ndb.Model):
    board            = ndb.LocalStructuredProperty(BingoCard, repeated=True)
    start_time       = ndb.DateTimeProperty()
    started          = ndb.BooleanProperty(default=True)
    creator          = ndb.KeyProperty("User")
    teams            = ndb.JsonProperty(repeated=True)
    event_log        = ndb.LocalStructuredProperty(BingoEvent, repeated=True)
    bingo_count      = ndb.IntegerProperty(default=3)
    current_highest  = ndb.IntegerProperty(default=0)
    difficulty       = ndb.StringProperty()
    subtitle         = ndb.StringProperty()
    required_squares = ndb.IntegerProperty(repeated=True)
    seed             = ndb.TextProperty(compressed=True)
    teams_allowed    = ndb.BooleanProperty(default=False)
    lockout          = ndb.BooleanProperty(default=False)
    square_count     = ndb.IntegerProperty()
    teams_shared     = ndb.BooleanProperty(default=False)

    def update(self, player_data, pid, team, players):
        change_squares = set()
        loss_squares = set()
        win_players = False
        capkey = players[team["cap"]].key
        pkey = players[pid].key
        team["score"] = 0
        for card in self.board:
            if card.name in player_data:
                ev = card.update(player_data[card.name], team, pid, players)
                if ev:
                    self.event_log.append(ev)
                    change_squares.add(ev.square)
                    if ev.loss:
                        loss_squares.add(ev.square)
                    if self.lockout:
                        if ev.loss and team["cap"] in card.current_owner:
                            card.current_owner.remove(team["cap"])
                        elif not ev.loss and team["cap"] not in card.current_owner:
                            card.current_owner.append(team["cap"])
                        if card.current_owner:
                            for prog in card.player_progress:
                                prog.locked = (card.current_owner[0] != _pid(prog.player))
            else:
                log.warning("card %s was not in bingo data for team/player %s", card.name if card else card, team['cap'] if team else team)
            if card.progress(capkey).complete():
                team["score"] += 1
        if self.square_count:
            if team["score"] >= self.square_count and "place" not in team and all([self.board[square].progress(pkey).complete() for square in self.required_squares]):
                self.event_log.append(BingoEvent(event_type = "win", loss = False, player = capkey, timestamp = datetime.utcnow()))
                team["place"] = len([1 for e in self.event_log if e.event_type == "win"])
                win_players = True
        elif change_squares:
            for bingo, line in lines_by_index.items():
                if set(line) & change_squares:
                    squares = len([square for square in line if self.board[square].progress(pkey).complete()])
                    lost_squares = len(set(line) & loss_squares)
                    if lost_squares + squares == 5:
                        loss = lost_squares > 0
                        ev = BingoEvent(event_type = "bingo", loss = loss, bingo = bingo, player = capkey, timestamp = datetime.utcnow())
                        if loss and bingo in team["bingos"]:
                            team["bingos"].remove(bingo)
                        elif bingo not in team["bingos"]:
                            team["bingos"].append(bingo)
                            if(len(team["bingos"]) > self.current_highest):
                                ev.first = True
                                ev.square = len(team["bingos"]) # i hate this
                                self.current_highest += 1
                        self.event_log.append(ev)
                        if len(team["bingos"]) >= self.bingo_count:
                            if "place" not in team and all([self.board[square].progress(pkey).complete() for square in self.required_squares]):
                                self.event_log.append(BingoEvent(event_type = "win", loss = False, player = capkey, timestamp = datetime.utcnow()))
                                team["place"] = len([1 for e in self.event_log if e.event_type == "win"])
                                win_players = True
            return win_players


class HistoryLine(ndb.Model):
    pickup_code = ndb.StringProperty()
    pickup_id = ndb.StringProperty()
    timestamp = ndb.DateTimeProperty()
    removed = ndb.BooleanProperty()
    coords = ndb.IntegerProperty()
    map_coords = ndb.IntegerProperty()

    def pickup(self):
        return Pickup.n(self.pickup_code, self.pickup_id)

    def print_line(self, start_time=None):
        t = (self.timestamp - start_time) if start_time and self.timestamp else self.timestamp
        if not self.removed:
            name = ""
            if self.coords in pbc:
                name = pbc[self.coords].area
            else:
                log.warning("Unknown coords: %s", self.coords)
                name = str(self.coords)
            return "found %s at %s. (%s)" % (self.pickup().name, name, t)
        else:
            return "lost %s! (%s)" % (self.pickup().name, t)

class User(ndb.Model):
    # key = user_id
    name = ndb.StringProperty()
    preferred_player = ndb.IntegerProperty()
    games = ndb.KeyProperty("Game", repeated=True)
    dark_theme = ndb.BooleanProperty(default=False)
    teamname = ndb.StringProperty()

    @staticmethod
    def login_url(redirect_after):
        return users.create_login_url(redirect_after)

    @staticmethod
    def logout_url(redirect_after):
        return users.create_logout_url(redirect_after)

    @staticmethod
    def get():
        app_user = users.get_current_user()
        if not app_user:
            return None
        user = User.get_by_id(app_user.user_id())
        if not user:
            return User.create(app_user)
        return user

    def rename(self, desired_name):
        if any([forbidden in desired_name for forbidden in ["@", "/", "\\", "?", "#", "&", "="]]):
            return False
        if User.get_by_name(desired_name):
            return False
        self.name = desired_name
        if self.put():
            return True
        return False

    @staticmethod
    def get_by_name(name):
        return User.query().filter(User.name == name).get()

    @staticmethod
    def create(app_user):
        user = User(id=app_user.user_id())
        user.name = app_user.email().partition("@")[0]
        user.teamname = "%s's team" % user.name
        key = user.put()
        for old in Seed.query(Seed.author == user.name).fetch():
            new = Seed(
                id="%s:%s" % (key.id(), old.name), 
                placements=old.placements, 
                flags=old.flags, 
                hidden=old.hidden, 
                description=old.description, 
                players=old.players, 
                author_key=key,
                name=old.name
            )
            new = new.put()
            old.key.delete()
            log.info("Seed conversion: %s -> %s", old.key, new)
        return user
    
    def plando(self, seed_name):
        return Seed.get_by_id("%s:%s" % (self.key.id(), seed_name))

class Seed(ndb.Model):
    # Seed ids used to be author_name:name but are being migrated to author_id:name
    placements = ndb.LocalStructuredProperty(Placement, repeated=True)
    flags = ndb.StringProperty(repeated=True)
    hidden = ndb.BooleanProperty(default=False)
    description = ndb.TextProperty()
    players = ndb.IntegerProperty(default=1)
    author_key = ndb.KeyProperty(User)
    author = ndb.StringProperty()  # deprecated: will remove after migration is complete
    name = ndb.StringProperty()

    @staticmethod
    def get(author_name, seed_name):
        author = User.get_by_name(author_name)
        if author:
            return author.plando(seed_name)
        log.warning("No user found for %s, looking for old-style seed instead...", author_name)
        return Seed.get_by_id("%s:%s" % (author_name, seed_name))

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
                flags = data['flags'],
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
                if int(player) > players:
                    players = int(player)
                plc.stuff.append(Stuff(code=stuff['code'], id=stuff['id'], player=player))
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
                flags = data.get('flags', self.flags),
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
                stuffs.append({"player": stuff.player, "code": stuff.code, "id": stuff.id})
            placements.append({'loc': p.location, 'stuff': stuffs})
        return jsonify({'placements': placements, 'flagline': self.flag_line()})

    def to_lines(self, player=1, extraFlags=[]):
        return ["%s|%s" % (",".join(extraFlags + self.flags), self.name)] + ["|".join((str(p.location), s.code, s.id, p.zone)) for p in self.placements for s in p.stuff if int(s.player) == player]


class Player(ndb.Model):
    # id = gid.pid
    skills      = ndb.IntegerProperty()
    events      = ndb.IntegerProperty()
    bonuses     = ndb.JsonProperty(default={})
    hints       = ndb.JsonProperty(default={})
    teleporters = ndb.IntegerProperty()
    seed        = ndb.TextProperty()
    signals     = ndb.StringProperty(repeated=True)
    history     = ndb.LocalStructuredProperty(HistoryLine, repeated=True)
    last_update = ndb.DateTimeProperty(auto_now=True)
    teammates   = ndb.KeyProperty('Player', repeated=True)
    user        = ndb.KeyProperty(User)
    can_nag     = ndb.BooleanProperty(default=True)

    def name(self):
        if self.user:
            u = self.user.get()
            if u and u.name:
                return u.name
        return "Player %s" % self.pid()

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

    # post-refactor version of bitfields
    def output(self):
        outlines = [str(x) for x in [self.skills, self.events, self.teleporters]]
        outlines.append(";".join([str(id) + "x%s" % count for (id, count) in self.bonuses.iteritems()]))
        outlines.append(";".join([str(loc) + ":%s" % finder for (loc, finder) in self.hints.iteritems()]))
        if self.signals:
            outlines.append("|".join(self.signals))
        return ",".join(outlines)

    def signal_send(self, signal):
        if signal not in self.signals:
            self.signals.append(signal)
            self.put()

    def signal_conf(self, signal):
        if signal in self.signals:
            self.signals.remove(signal)
        # basically it is never ok to be spamming ppl, so if we get a message callback
        # we remove the first message we find if we don't get an exact match.
        elif signal.startswith("msg:"):
            for s in self.signals:
                self.signals.remove(s)
                if s.startswith("msg:"):
                    log.warning("No exact match for signal %s, removing %s instead (spam protection)" % (signal, s))
                    break
        self.put()

    def give_pickup(self, pickup, remove=False, delay_put=False, coords=None, finder=None):
        if coords and finder:
            self.hints[str(coords)] = finder
        if pickup.code == "RB":
            # handle upgrade refactor storage
            pick_id = str(pickup.id)
            if remove:
                if pick_id in self.bonuses:
                    self.bonuses[pick_id] -= 1
                    if self.bonuses[pick_id] == 0:
                        del self.bonuses[pick_id]
            else:
                if pick_id in self.bonuses:
                    if not (pickup.max and self.bonuses[pick_id] >= pickup.max):
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
        if pickup.code == "RB":
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


class Game(ndb.Model):
    
    # id = Sync ID
    DEFAULT_SHARED = [ShareType.SKILL, ShareType.EVENT, ShareType.TELEPORTER]

    str_mode = ndb.StringProperty(default="None")
    str_shared = ndb.StringProperty(repeated=True)

    def get_mode(self):            return MultiplayerGameType.mk(self.str_mode) or MultiplayerGameType.SIMUSOLO
    def set_mode(self, mode):      self.str_mode = mode.value
    def get_shared(self):          return [ShareType.mk(st) for st in self.str_shared if ShareType.mk(st)]
    def set_shared(self, shared):  self.str_shared = [s.value for s in shared]
    mode        = property(get_mode, set_mode)
    shared      = property(get_shared, set_shared)
    start_time  = ndb.DateTimeProperty(auto_now_add=True)
    last_update = ndb.DateTimeProperty(auto_now=True)
    players     = ndb.KeyProperty(Player, repeated=True)
    params      = ndb.KeyProperty(SeedGenParams)
    bingo       = ndb.LocalStructuredProperty(BingoGameData)

    def next_player(self):
        if self.mode != MultiplayerGameType.SIMUSOLO:
            return False
        player_nums = self.player_nums()
        return max(player_nums)+1

    def player_nums(self):
        return [_pid(k) for k in self.players]        

    def summary(self):
        out_lines = ["%s (%s)" % (self.mode, ",".join([s.name for s in self.shared]))]
        if self.mode in [MultiplayerGameType.SHARED, MultiplayerGameType.SIMUSOLO] and len(self.players):
            src = self.players[0].get()
            for (field, cls) in [("skills", Skill), ("teleporters", Teleporter), ("events", Event)]:
                bitmap = getattr(src, field)
                names = []
                for id, bit in cls.bits.iteritems():
                    i = cls(id)
                    if i:
                        if i.stacks:
                            cnt = get_taste(bitmap, i.bit)
                            if cnt > 0:
                                names.append("%sx %s" % (cnt, i.name))
                        elif get_bit(bitmap, i.bit):
                            names.append(i.name)
                out_lines.append("%s: %s" % (field, ", ".join(names)))
            out_lines.append("upgrades: %s" % (",".join(["%sx %s" % (k, v) for k, v in src.bonuses.iteritems()])))
        return "\n\t" + "\n\t".join(out_lines)

    def get_players(self):
        return [p.get() for p in self.players]

    def remove_player(self, key):
        key = ndb.Key(Player, key)
        self.players.remove(key)
        key.delete()
        self.put()

    def sanity_check(self):
        # helper function, checks if a pickup stacks
        def stacks(pickup):
            if pickup.stacks:
                return True
            if pickup.code != "RB":
                return False
            return pickup.id in [6, 12, 13, 15, 17, 19, 21, 28, 30, 31, 32, 33]

        if self.mode != MultiplayerGameType.SHARED:
            return
        if not Cache.canSanCheck(self.key.id()):
            log.warning("Skipping sanity check.")
            return
        Cache.doSanCheck(self.key.id())
        allPlayers = self.get_players()

        sanFailedSignal = "msg:@Major Error during sanity check. If this persists across multiple alt+l attempts please contact Eiko@"
        playerGroups = []
        if self.bingo:
            for team in self.bingo.teams:
                playerGroups.append([p for p in allPlayers if p.pid() in team["teammates"] + [team["cap"]]])
        else:
             playerGroups = [allPlayers]
        for players in playerGroups:
            inv = defaultdict(lambda: 0)
            for hl in [hl for player in players for hl in player.history]:
                pick = hl.pickup()
                if pick.code == "MU":
                    for c in pick.children:
                        if c.is_shared(self.shared):
                            inv[(c.code, c.id)] += -1 if hl.removed else 1
                elif pick.is_shared(self.shared):
                    inv[(pick.code, pick.id)] += -1 if hl.removed else 1
            i = 0
            for key, count in inv.iteritems():
                pickup = Pickup.n(key[0], key[1])
                if not stacks(pickup):
                    count = 1
                elif pickup.max:
                    count = min(count, pickup.max)
                for player in players:
                    has = player.has_pickup(pickup)
                    if has < count:
                        if has == 0 and count == 1:
                            log.error("Player %s should have %s but did not. Fixing..." % (player.key.id(), pickup.name))
                        else:
                            log.error("Player %s should have had %s of %s but had %s instead. Fixing..." % (player.key.id(), count, pickup.name, has))
                        while(has < count):
                            i += 1
                            last = has
                            player.give_pickup(pickup, delay_put=True)
                            has = player.has_pickup(pickup)
                            if has == last:
                                log.critical("Aborting sanity check for Player %s: tried and failed to increment %s (at %s, should be %s)" % (player.key.id(), pickup.name, has, count))
                                return False
                            if i > 100:
                                player.signal_send(sanFailedSignal)
                                log.critical("Aborting sanity check for Player %s after too many iterations." % player.key.id())
                                return False
                    elif has > count:
                        log.error("Player %s should have had %s of %s but had %s instead. Fixing..." % (player.key.id(), count, pickup.name, has))
                        while(has > count):
                            i += 1
                            last = has
                            player.give_pickup(pickup, remove=True, delay_put=True)
                            has = player.has_pickup(pickup)
                            if has == last:
                                log.critical("Aborting sanity check for Player %s: tried and failed to decrement %s (at %s, should be %s)" % (player.key.id(), pickup.name, has, count))
                                return False
                            if i > 100:
                                player.signal_send(sanFailedSignal)
                                log.critical("Aborting sanity check for Player %s after too many iterations." % player.key.id())
                                return False
            for player in players:
                Cache.setHist(self.key.id(), player.pid(), player.history)
                player.put()
        return True

    def rebuild_hist(self):
        gid = self.key.id()
        for player in self.get_players():
            pid = player.pid()
            Cache.setHist(gid, pid, player.history)
        return Cache.getHist(gid)
    
    def get_all_hls(self):
        hist = self.rebuild_hist()
        if not hist:
            return []
        return [hl for players, hls in hist.items() for hl in hls]

    def player(self, pid):
        full_pid = "%s.%s" % (self.key.id(), pid)
        player = Player.get_by_id(full_pid)
        if not player:
            if(self.mode == MultiplayerGameType.SHARED and len(self.players)):
                src = self.players[0].get()
                player = Player(id=full_pid, skills=src.skills, events=src.events, teleporters=src.teleporters, bonuses=src.bonuses, history=[], signals=[], hints=src.hints)
            else:
                player = Player(id=full_pid, skills=0, events=0, teleporters=0, history=[])
            k = player.put()
            Cache.setHist(self.key.id(), pid, [])
        else:
            k = player.key
        if k not in self.players:
            self.players.append(k)
            self.put()
        return player

    def found_pickup(self, pid, pickup, coords, remove, dedup, zone=""):
        retcode = 200
        share = pickup.is_shared(self.shared)
        finder = self.player(pid)
        players = self.get_players()
        if coords in [h.coords for h in finder.history]:
            if share and dedup:
                log.error("Duplicate pickup at location %s from player %s" % (coords, pid))
                return 410
            elif any([h for h in finder.history if h.coords == coords and h.pickup_code == pickup.code and h.pickup_id == pickup.id]):
                log.debug("Not writing this to history, as an identical HL already exists (death dupe)")
                return 200
        elif share and dedup and coords in [h.coords for teammate in players for h in teammate.history if teammate.key in finder.teammates]:
                log.info("Won't grant %s to player %s, as a teammate found it already" % (pickup.name, pid))
                return 410
        if pickup.code == "MU":
            for child in pickup.children:
                retcode = max(self.found_pickup(pid, child, coords, remove, False), retcode)
            return retcode
        if self.mode == MultiplayerGameType.SHARED:
            if self.bingo:
                team = self.bingo_team(pid, cap_only=False, as_list=True)
                if team: 
                    players = [p for p in players if p.pid() in team]
                    log.debug("Bingo share: players pruned down to %s" % [p.pid() for p in players])
                else:
                    log.error("No bingo team found for player %s!" % pid)
            if share:
                for player in players:
                    player.give_pickup(pickup, remove, coords=coords, finder=pid)
            else:
                retcode = 406
                if pickup.code == "HN":
                    for player in players:
                        if str(coords) not in player.hints:
                            player.hints[str(coords)] = 0  # hint 0 means the clue's been found
                        player.put()
        elif self.mode == MultiplayerGameType.SPLITSHARDS:
            if pickup.code != "RB" or pickup.id not in [17, 19, 21]:
                retcode = 406
            else:
                my_shards = len([h.coords for h in finder.history if h.pickup_code == "RB" and int(h.pickup_id) == pickup.id])
                if my_shards < 3:
                    shard_locs = [h.coords for player in players for h in player.history if h.pickup_code == "RB" and h.pickup_id in ["17", "19", "21"]]
                    if coords in shard_locs:
                        log.info("%s at %s already taken, player %s will not get one." % (pickup.name, coords, pid))
                        return 410
        elif self.mode in [MultiplayerGameType.SIMUSOLO, MultiplayerGameType.BINGO]:
            pass
        else:
            log.error("game mode %s not implemented" % self.mode)
            retcode = 404
        hl = HistoryLine(pickup_code=pickup.code, timestamp=datetime.utcnow(), pickup_id=str(pickup.id), coords=coords, removed=remove)
        if coords in range(24, 60, 4) and zone in map_coords_by_zone:
            hl.map_coords = map_coords_by_zone[zone]
        finder.history.append(hl)
        finder.put()
        self.put()
        Cache.setHist(self.key.id(), pid, finder.history)
        return retcode

    def clean_up(self):
        [p.delete() for p in self.players]
        Cache.removeGame(self.key.id())
        if self.params:
            self.params.delete()
        log.info("Deleting game %s" % self)
        self.key.delete()

    @staticmethod
    def with_id(id):
        return Game.get_by_id(int(id))

    @staticmethod
    def clean_old(timeout_window=timedelta(hours=720)):
        old = [game for game in Game.query(Game.last_update < datetime.now() - timeout_window)]
        return len([Game.clean_up(game) for game in old])

    @staticmethod
    def get_open_gid():
        id = 1
        game_ids = set([int(game.key.id()) for game in Game.query()])
        while id in game_ids:
            id += 1
        if id > 100000:
            Game.clean_old()
        return id

    @staticmethod
    def from_params(params, id=None):
        id = int(id) if id else Game.get_open_gid()
        game = Game(
            id=id, params=params.key, players=[],
            str_shared=[s.value for s in params.sync.shared],
            str_mode=params.sync.mode.value
        )
        game.put()
        teams = params.sync.teams
        if teams:
            for playerNums in teams.itervalues():
                team = [game.player(p) for p in playerNums]
                teamKeys = [p.key for p in team]
                for player in team:
                    tset = set(teamKeys)
                    tset.remove(player.key)
                    player.teammates = list(tset)
                    player.put()
        else:
            for i in range(params.players):
                player = game.player(i + 1)
                player.put()
                Cache.setPos(id, i + 1, 189, -210)
        game.rebuild_hist()
        log.info("Game.from_params(%s, %s): Created game %s ", params.key, id, game)
        return game

    @staticmethod
    def new(_mode=None, _shared=None, id=None):
        if isinstance(_shared, (list,)):
            shared = enums_from_strlist(ShareType, _shared)
        else:
            shared = Game.DEFAULT_SHARED
        mode = MultiplayerGameType.mk(_mode) if _mode else MultiplayerGameType.SIMUSOLO
        id = int(id) if id else Game.get_open_gid()
        game = Game(id=id, players=[], str_shared=[s.value for s in shared], str_mode=mode.value)
        key = game.put()
        log.info("Game.new(%s, %s, %s): Created game %s ", _mode, _shared, id, game)
        return key

    def bingo_json(self, initial=False):
        res = {
            'cards':  [c.to_json() for c in self.bingo.board],
            'events': [e.to_json(self.bingo.start_time) for e in self.bingo.event_log],
            'teams': {t["cap"]: t for t in self.bingo.teams},
            'required_squares': self.bingo.required_squares,
            "gameId": self.key.id()
        }
        for t in res['teams'].values():
            p = self.player(t["cap"])
            t["name"] = p.teamname() if t["teammates"] else p.name()
            t["teammates"] = [{'pid': tm, 'name': self.player(tm).name()} for tm in t["teammates"]]

        if self.bingo.creator:
            res["creator"] = self.bingo.creator.get().name
            user = User.get()
            res["is_owner"] = user and self.bingo.creator == user.key

        if self.bingo.start_time:
            res['countdown'] = datetime.utcnow() < self.bingo.start_time
            res['start_time_posix'] = timegm(self.bingo.start_time.timetuple())
  

        if initial:
            res["difficulty"] = self.bingo.difficulty
            res["bingo_count"] = self.bingo.bingo_count
            res["subtitle"] = self.bingo.subtitle
            res["teams_allowed"] = self.bingo.teams_allowed
            if self.params:
                res["paramId"] = self.params.id()
                if self.bingo.teams_shared:
                    params = self.params.get()
                    res["teamMax"] = params.players
        return res

    def bingo_update(self, bingo_data, player_id):
        player_id = int(player_id)
        if not self.bingo.start_time:
            log.debug("game not started")
            return
        if self.bingo.difficulty != "hard" and "HuntEnemies" in bingo_data and bingo_data["HuntEnemies"]["value"]["Fronkey Fight"]["value"]:
            bingo_data["HuntEnemies"]["total"] -= 1
        players = {p.pid() : p for p in self.get_players()}
        player = players[player_id]
        team = self.bingo_team(player_id, cap_only = False)
        cap = players[team["cap"]]
        now = round_time(datetime.utcnow() - self.bingo.start_time)
        if self.bingo.update(bingo_data, player_id, team, players):
            p_list = [team["cap"]]
            p_list += team["teammates"]
            send_log = []
            for p in p_list:
                players[int(p)].signal_send("win:$Finished in %s place at %s!" % (ord_suffix(team["place"]), now))
                send_log.append(p)
            log.debug("Sent victory message to these players: %s" % send_log)
        self.put()
    
    def bingo_seed(self, pid):
        sync_flag = ("Sync%s.%s," % (self.key.id(), pid))
        if not self.params:
            return sync_flag + self.bingo.seed
        else:
            sync_flag += "Bingo,"
            params = self.params.get()
            if params.players == 1:
                return sync_flag + params.get_seed(1, include_sync=False)
            else:
                team = self.bingo_team(pid, cap_only=False, as_list=True)
                if not team:
                    log.error("No team found for player %s" % pid)
                    return None
                p_number = team.index(pid) + 1
                if params.players < p_number:
                    log.error("player %s can't join team as there is no seed available" % pid)
                    return None
                return sync_flag + params.get_seed(p_number, include_sync=False)
                

    def bingo_team(self, pid, cap_only=True, as_list=False):
        pid = int(pid)
        maybe_team = [team for team in self.bingo.teams if int(team["cap"]) == pid]
        if not maybe_team and not cap_only:
            maybe_team += [team for team in self.bingo.teams if pid in team["teammates"]]
        if maybe_team:
            if len(maybe_team) > 1 and cap_only:
                log.error("Multiple teams found with the same player %s (%s), returning %s", pid, maybe_team, maybe_team[0]["cap"])
            res = maybe_team[0]
            if as_list:
                return [res["cap"]] + res["teammates"]
            p = self.player(res["cap"])
            res["name"] = p.teamname() if res["teammates"] else p.name()
            return res
        return None
