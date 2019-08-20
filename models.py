from google.appengine.ext import ndb
from google.appengine.api import users

import logging as log
from json import dumps as jsonify
from datetime import datetime, timedelta
from calendar import timegm
from collections import defaultdict

from seedbuilder.seedparams import Placement, Stuff, SeedGenParams
from enums import MultiplayerGameType, ShareType, Variation
from util import picks_by_coord, get_bit, get_taste, enums_from_strlist, ord_suffix
from pickups import Pickup, Skill, Teleporter, Event
from cache import Cache

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

def _pid(pkey):
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
    return pickup.id in [6, 9, 12, 13, 15, 17, 19, 21, 28, 30, 31, 32, 33]


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

    def print_line(self, start_time=None):
        t = (self.timestamp - start_time) if start_time and self.timestamp else self.timestamp
        if not self.removed:
            name = "at "
            if self.coords in pbc:
                name += pbc[self.coords].area
            elif self.coords == -1:
                name = "via manual activation"
            else:
                log.warning("Unknown coords: %s", self.coords)
                name += str(self.coords)
            return "found %s %s. (%s)" % (self.pickup().name, name, t)
        else:
            return "lost %s! (%s)" % (self.pickup().name, t)

class User(ndb.Model):
    # key = user_id
    name = ndb.StringProperty()
    games = ndb.KeyProperty("Game", repeated=True)
    dark_theme = ndb.BooleanProperty(default=False)
    teamname = ndb.StringProperty()
    pref_num  = ndb.IntegerProperty()
    theme  = ndb.StringProperty()

    @staticmethod
    def login_url(redirect_after):
        return users.create_login_url(redirect_after)

    @staticmethod
    def logout_url(redirect_after):
        return users.create_logout_url(redirect_after)

    @staticmethod
    def prune_games():
        keys = [k for k in Game.query().iter(keys_only=True)]
        for user in User.query().fetch():
            game_count = len(user.games)
            user.games = [g for g in user.games if g in keys]
            if len(user.games) < game_count:
                print "removed %s games from %s's gamelist" % (game_count - len(user.games), user.name)
                user.put()


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
    user        = ndb.KeyProperty('User')
    can_nag     = ndb.BooleanProperty(default=True)
    bingo_prog  = ndb.LocalStructuredProperty(BingoCardProgress, repeated=True)

    def sharetuple(self):
        return (self.skills, self.events, self.teleporters, len(self.bonuses))

    def name(self):
        if self.user:
            u = self.user.get()
            if u and u.name:
                return u.name
        return "Player %s" % self.pid()

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

    @staticmethod
    @ndb.transactional(retries=5, xg=True)
    def transaction_pickup(pkey, pickup, remove=False, delay_put=False, coords=None, finder=None):
        p = pkey.get()
        p.give_pickup(pickup, remove=remove, coords=coords, finder=finder)

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
                    if (not stacks(pickup)) or (pickup.max and self.bonuses[pick_id] >= pickup.max):
                        log.info("Will not give %s pickup %s, as they already have %s" % (self.name(), pickup.name, self.bonuses[pick_id]))
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

    def to_json(self, players, initial=False): #, progresses
        res = {
            "name": self.name,
            "progress": {p.pid(): p.bingo_prog[self.square].to_json() for p in players},
            "completed_by": self.completed_by
        }

        if initial:
            res["disp_name"] = self.disp_name
            res["help_lines"] = self.help_lines
            if self.square or self.square == 0:
                res["type"] = self.goal_type
                res["square"] = self.square
            if self.subgoals:
                res["subgoals"] = {subgoal["name"]: subgoal for subgoal in self.subgoals}
            if self.target:
                res["target"] = self.target

        return res


    def progress(self, player):
        if not player or len(player.bingo_prog) < self.square:
            return None
        return player.bingo_prog[self.square]
    
    def update(self, card_data, player, teammates, capkey):
        p_progress = self.progress(player)
        prior_value = _pid(capkey) in self.completed_by
        prior_count = p_progress.count

        if self.goal_type == "bool":
            p_progress.completed = card_data["value"]
        elif self.goal_type == "int":
            p_progress.count = min(int(card_data["value"]), self.target)
            p_progress.completed = p_progress.count >= self.target
        elif self.goal_type == "multi":
            p_progress.count = min(int(card_data["total"]), self.target)
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
            event = BingoEvent(event_type="square", loss = not completed, square=self.square, player=capkey, timestamp=datetime.utcnow())
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
        return res



class BingoGameData(ndb.Model):
    players          = ndb.KeyProperty("Player", repeated=True)
    board            = ndb.LocalStructuredProperty(BingoCard, repeated=True)
    start_time       = ndb.DateTimeProperty()
    started          = ndb.BooleanProperty(default=True)
    creator          = ndb.KeyProperty("User")
    teams            = ndb.LocalStructuredProperty(BingoTeam, repeated=True)
    event_log        = ndb.LocalStructuredProperty(BingoEvent, repeated=True)
    bingo_count      = ndb.IntegerProperty(default=3)
    current_highest  = ndb.IntegerProperty(default=0)
    difficulty       = ndb.StringProperty()
    subtitle         = ndb.StringProperty()
    seed             = ndb.TextProperty(compressed=True)
    teams_allowed    = ndb.BooleanProperty(default=False)
    square_count     = ndb.IntegerProperty()
    teams_shared     = ndb.BooleanProperty(default=False)
    game             = ndb.KeyProperty("Game")

    @staticmethod
    def with_id(id):
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
        return [p.get() for p in self.players]

    def player_nums(self):  return [_pid(k) for k in self.players]

    def player(self, pid, create=False, delay_put=False):
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
            p.put()
        return p

    def get_json(self, initial=False):
        players = self.get_players()
        players_by_pkey = {p.key: p for p in players}
        res = {
            'cards':  [c.to_json(players, initial) for c in self.board],
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
            res["subtitle"] = self.subtitle
            res["teams_allowed"] = self.teams_allowed
            game = self.game.get()
            if game.params:
                res["paramId"] = game.params.id()
                if self.teams_shared:
                    params = game.params.get()
                    res["teamMax"] = params.players
        return res

    def get_seed(self, pid):
        sync_flag = ("Sync%s.%s," % (self.key.id(), pid))
        game = self.game.get()
        if not game.params:
            return sync_flag + self.seed
        else:
            params = game.params.get()
            if Variation.BINGO not in params.variations:
                params.variations.append(Variation.BINGO)
                params = params.put().get()
            if params.players == 1:
                return sync_flag + params.get_seed(1, include_sync=False)
            else:
                team = self.team(pid, cap_only=False)
                if not team:
                    log.error("No team found for player %s" % pid)
                    return None
                p_number = team.pids().index(pid) + 1
                if params.players < p_number:
                    log.error("player %s can't get seed as there is no seed available" % pid)
                    return None
                return sync_flag + params.get_seed(p_number, include_sync=False)


    def team(self, pid, cap_only=True):
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

    @ndb.transactional(retries=2, xg=True)
    def update(self, bingo_data, player_id):
        player_id = int(player_id)
        if not self.start_time:
            return
        now = datetime.utcnow()
        change_squares = set()
        loss_squares = set()
        win_players = False
        round_now = round_time(now - self.start_time)
        place = ""
        win_sig = "win:$Finished in %s place at %s!"
        team = self.team(player_id, cap_only=False)
        team.score = 0
        player = self.player(player_id)
        cpid = _pid(team.captain)
        teammates = [self.player(pid) for pid in team.pids() if pid != player_id]
        need_write = False
        for card in self.board:
            if card.name in bingo_data:
                ev = card.update(bingo_data[card.name], player, teammates, team.captain)
                if ev:
                    need_write = True
                    self.event_log.append(ev)
                    change_squares.add(ev.square)
                    if ev.loss:
                        loss_squares.add(ev.square)
                        if cpid in card.completed_by:
                            card.completed_by.remove(cpid)
                    elif cpid not in card.completed_by:
                        card.completed_by.append(cpid)
            else:
                log.warning("card %s was not in bingo data for team/player %s", card.name if card else card, team.captain if team else team)
            if cpid in card.completed_by:
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
                    squares = len([square for square in line if cpid in self.board[square].completed_by])
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
        player.put()
        if need_write:
            self.put()

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
                stuffs.append({"player": stuff.player, "code": stuff.code, "id": stuff.id})
            placements.append({'loc': p.location, 'stuff': stuffs})
        return jsonify({'placements': placements, 'flagline': self.flag_line()})

    def to_lines(self, player=1, extraFlags=[]):
        return ["%s|%s" % (",".join(extraFlags + self.flags), self.name)] + ["|".join((str(p.location), s.code, s.id, p.zone)) for p in self.placements for s in p.stuff if int(s.player) == player]


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
    hls         = ndb.LocalStructuredProperty(HistoryLine, repeated=True)
    players     = ndb.KeyProperty(Player, repeated=True)
    relics      = ndb.StringProperty(repeated=True)
    params      = ndb.KeyProperty(SeedGenParams)
    bingo       = ndb.LocalStructuredProperty(BingoGameData)
    bingo_data  = ndb.KeyProperty(BingoGameData)
    dedup       = ndb.BooleanProperty(default=False)

    def history(self, pids=[]):
        if not self.hls:
             # legacy migration branch
            for p in self.get_players():
                pid = p.pid()
                for hl in p.history:
                    hl.player = pid
                    self.hls.append(hl)
            self.put()
        if pids:
            return [hl for hl in self.hls if hl.player in pids]
        else:
            return self.hls
    
    def next_player(self):
        if self.mode != MultiplayerGameType.SIMUSOLO:
            return False
        player_nums = self.player_nums()
        return max(player_nums)+1

    def player_nums(self):  return [_pid(k) for k in self.players]

    def summary(self, p=0):
        out_lines = ["%s (%s)" % (self.mode, ",".join([s.name for s in self.shared]))]
        if self.mode in [MultiplayerGameType.SHARED, MultiplayerGameType.SIMUSOLO] and len(self.players):
            src = self.players[p].get()
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
                            names.append(i.name.replace(" teleporter", ""))
                if names:
                    out_lines.append("%s: %s" % (field, ", ".join(names)))
            trees = []
            relics = []
            bonuses = []
            for (name, cnt) in [(Pickup.name("RB", k), v) for k, v in sorted(src.bonuses.iteritems(), lambda (lk, _), (rk, __): int(lk) - int(rk))]:
                if "Tree" in name:
                    trees.append(name.replace(" Tree", ""))
                elif "Relic" in name:
                    relics.append(name)
                else:
                    bonuses.append((name, cnt))
            if trees:
                out_lines.append("trees: %s" % ", ".join(trees))
            if relics:
                out_lines.append("relics: %s" % ", ".join(relics))
            if bonuses:
                out_lines.append("upgrades:\n\t\t%s" % ("\n\t\t".join(["%s x%s" % b for b in bonuses])))
        return "\n\t" + "\n\t".join(out_lines)

    def get_players(self):
        return [p.get() for p in self.players]

    def remove_player(self, key):
        key = ndb.Key(Player, key, parent=self.key)
        if key in self.players:
            self.players.remove(key)
            self.put()
        else:
            log.warning("Can't remove %s from %s" % (key, self.players))
        key.delete()
        
    def get_player_groups(self, int_ids=False):
        player_groups = []
        if self.bingo_data:
            bingo = self.bingo_data.get()
            for team in bingo.teams:
                player_groups.append([team.captain] + team.teammates)
        else:
            player_groups = [self.players]
        if int_ids:
            return [[_pid(p)for p in group] for group in player_groups]
        return player_groups

    def sanity_check(self):
        if self.mode != MultiplayerGameType.SHARED:
            return False
        if not Cache.san_check(self.key.id()):
            log.info("Skipping sanity check")
            return False
        sanFailedSignal = "msg:@Major Error during sanity check. If this persists across multiple alt+l attempts please contact Eiko@"
        playerGroups = self.get_player_groups()
        for playerKeys in playerGroups:
            players = [pkey.get() for pkey in playerKeys]
            inv = defaultdict(lambda: 0)
            for hl in self.history([_pid(p) for p in playerKeys]):
                pick = hl.pickup()
                if pick.code == "MU":
                    for c in pick.children:
                        if c.is_shared(self.shared):
                            inv[(c.code, c.id)] += -1 if hl.removed else 1
                elif pick.is_shared(self.shared):
                    inv[(pick.code, pick.id)] += -1 if hl.removed else 1
                if ShareType.MISC in self.shared:
                    if hl.coords in trees_by_coords:
                        tree_pick = trees_by_coords[hl.coords]
                        inv[(tree_pick.code, tree_pick.id)] += -1 if hl.removed else 1
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
                    log.error("lost HL error! Player %s had %s for sks instead of %s" % (player.pid(), player.skills, sk_max))
                    player.skills = sk_max
                if player.events < ev_max:
                    log.error("lost HL error! Player %s had %s for evs instead of %s" % (player.pid(), player.events, ev_max))
                    player.events = ev_max
                if player.teleporters < tp_max:
                    log.error("lost HL error! Player %s had %s for tps instead of %s" % (player.pid(), player.teleporters, tp_max))
                    player.teleporters = tp_max
                if len(player.bonuses) < rb_cnt:
                    msglines = ["lost HL error!"]
                    for item in player.bonuses:
                        cnt = player.bonuses[item]
                        mx = bonus_max[item]
                        if cnt  < mx:
                            msglines.append("Player %s had %s of %s instead of %s" % (player.pid(), cnt, item, mx))
                            player.bonuses[item] = mx
                    log.error("\n".join(msglines))
                player.put()
        return True

    def rebuild_hist(self):
        gid = self.key.id()
        for pid in [_pid(p) for p in self.players]:
            Cache.set_hist(gid, pid, self.history([pid]))
        return Cache.get_hist(gid)
    
    def get_all_hls(self):
        hist = self.rebuild_hist()
        if not hist:
            return []
        return [hl for players, hls in hist.items() for hl in hls]

    def player(self, pid, create=True, delay_put=False):
        gid = self.key.id()
        full_pid = "%s.%s" % (gid, pid)
        player = Player.get_by_id(full_pid, parent=self.key)
        k = None
        if not player:
            if not create:
                log.debug("Game %s has no player %s, will not create", gid, pid)
                return None
            log.debug("Game %s has no player %s (%s) creating...", gid, pid, self.players)
            if(self.mode == MultiplayerGameType.SHARED and len(self.players)):
                src = self.players[0].get()
                player = Player(id=full_pid, skills=src.skills, events=src.events, teleporters=src.teleporters, bonuses=src.bonuses, history=[], signals=[], hints=src.hints, parent=self.key)
            else:
                player = Player(id=full_pid, skills=0, events=0, teleporters=0, history=[], parent=self.key)
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

    def found_pickup(self, pid, pickup, coords, remove, dedup, zone=""):
        pid = int(pid)
        retcode = 200
        share = pickup.is_shared(self.shared)
        finder_hist = self.history([pid])
        players = self.get_players()
        finder = [p for p in players if p.pid() == pid]
        if not finder:
            log.error("Got pickup from unknown player %s! Creating to avoid crash" % pid)
            finder = self.player(pid)
        else:
            finder = finder[0]

        if pickup.code == "WT" and zone in relics_by_zone:
            Cache.clear_items(self.key.id())
            pickup = relics_by_zone[zone]
            share = ShareType.MISC in self.shared

        if coords == -1:
            share = ShareType.MISC in self.shared
            dedup = False

        if coords in [h.coords for h in finder_hist]:
            if share and dedup:
                log.error("Duplicate pickup at location %s from player %s (previous: %s)" % (coords, pid, [h for h in finder_hist if h.coords == coords]))
                return 410
            elif any([h for h in finder_hist if h.coords == coords and h.pickup_code == pickup.code and h.pickup_id == pickup.id]):
                return 200

        if pickup.code == "MU":
            for child in pickup.children:
                retcode = max(self.found_pickup(pid, child, coords, remove, False), retcode)
            return retcode
        if self.mode == MultiplayerGameType.SHARED:
            if self.bingo_data:
                bingo = self.bingo_data.get()
                team = bingo.team(pid, cap_only=False)
                if team:
                    players = [p for p in players if p.pid() in team.pids()]
                else:
                    log.error("No bingo team found for player %s!" % pid)
            if share and dedup and (self.dedup or (pickup.code == "RB" and pickup.id in [17, 19, 21, 28])):
                if coords in [h.coords for h in self.history([teammate.pid() for teammate in players])]:
                    log.info("Won't grant %s to player %s, as a teammate found it already" % (pickup.name, pid))
                    return 410
            ftple = finder.sharetuple()
            for p in players:
                ptple = p.sharetuple()
                if ftple != ptple:
                    log.error("sharetuple mismatch! %s is not %s, triggering san check" % (ftple, ptple))
                    self.sanity_check()
                    break
            shared_misc = False
            if ShareType.MISC in self.shared:
                if coords in trees_by_coords:
                    for player in players:
                        Player.transaction_pickup(player.key, trees_by_coords[coords], remove)
                    shared_misc = True
            if share:
                for player in players:
                    Player.transaction_pickup(player.key, pickup, remove, coords=coords, finder=pid)
            elif not shared_misc:
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
                my_shards = len([h.coords for h in finder_hist if h.pickup_code == "RB" and int(h.pickup_id) == pickup.id])
                if my_shards < 3:
                    shard_locs = [h.coords for h in self.history() if h.pickup_code == "RB" and h.pickup_id in ["17", "19", "21"]]
                    if coords in shard_locs:
                        log.info("%s at %s already taken, player %s will not get one." % (pickup.name, coords, pid))
                        return 410
        elif self.mode in [MultiplayerGameType.SIMUSOLO, MultiplayerGameType.BINGO]:
            pass
        else:
            log.error("game mode %s not implemented" % self.mode)
            retcode = 404
        hl = HistoryLine(pickup_code=pickup.code, timestamp=datetime.utcnow(), pickup_id=str(pickup.id), coords=coords, removed=remove, player=pid)
        if coords in range(24, 60, 4) and zone in map_coords_by_zone:
            hl.map_coords = map_coords_by_zone[zone]
        self.append_hl(hl)
        if pickup.code in ["AC", "KS", "HC", "EC", "SK", "EV", "TP"] or (pickup.code == "RB" and pickup.id in [17, 19, 21]):
            Cache.clear_reach(self.key.id(), pid)
            Cache.clear_items(self.key.id())
        elif hl.map_coords or coords in trees_by_coords:
            Cache.clear_items(self.key.id())
        return retcode

    @ndb.transactional(retries=5)
    def append_hl(self, hl):
        if not any([h for h in self.hls[:-20] if h.equals(hl)]):
            self.hls.append(hl)
            Cache.append_hl(self.key.id(), hl.player, hl)
        self.put()

    def clean_up(self):
        [p.delete() for p in self.players]
        Cache.remove_game(self.key.id())
        if self.params:
            self.params.delete()
        if self.bingo_data:
            self.bingo_data.delete()
        log.debug("Deleting game %s" % self.key)
        self.key.delete()
        return self.key

    @staticmethod
    def with_id(id):
        return Game.get_by_id(int(id))

    @staticmethod
    def clean_old(timeout_window=timedelta(hours=1440)):
        old = [game for game in Game.query(Game.last_update < datetime.now() - timeout_window)]
        keys = set([Game.clean_up(game) for game in old])
        return len(keys)

    @staticmethod
    def get_open_gid():
        id = 1
        game_ids = set([int(game.key.id()) for game in Game.query()])
        while id in game_ids:
            id += 1
        return id

    @staticmethod
    def from_params(params, gid=None):
        retries = 0
        while retries < 5:
            gid = int(gid) if gid else Game.get_open_gid()
            try:
                return Game.from_params_transactional(params, gid)
            finally:
                retries += 1
        return Game.from_params_transactional(params, gid)

    @staticmethod
    @ndb.transactional(retries=0, xg=True)
    def from_params_transactional(params, gid):
        game = Game(
            id=gid, params=params.key, players=[],
            str_shared=[s.value for s in params.sync.shared],
            str_mode=params.sync.mode.value,
            dedup=params.sync.dedup
        )
        if Variation.WORLD_TOUR in params.variations:
            game.relics = [zone for (_, code, __, zone) in params.get_seed_data() if code == "WT"]
        if Variation.BINGO not in params.variations:
            teams = params.sync.teams
            if teams:
                for playerNums in teams.itervalues():
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
        game.put()
        game.rebuild_hist()
        log.debug("Game.from_params(%s, %s): Created game %s ", params.key, id, game)
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

