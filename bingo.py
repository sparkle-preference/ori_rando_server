from random import choice, randint, sample
from collections import defaultdict
import json
import logging as log

from webapp2 import RequestHandler, redirect, uri_for
from webapp2_extras.routes import RedirectRoute as Route
from google.appengine.ext.webapp import template

from enums import MultiplayerGameType
from models import Game, User
from pickups import Pickup, Skill, AbilityCell, HealthCell, EnergyCell, Multiple
from util import param_val, param_flag, resp_error, debug, path
from seedbuilder.vanilla import seedtext as vanilla_seed

if debug:
    from test.data import bingo_data 


class BingoGoal(object):
    maxRepeats = 1
    tags = []
    def getCard(self, banned_goals=[], banned_methods=[]):
        cardData = {'name': self.name, 'type': self.goalType}
        return cardData
    def isAllowed(self, allowed_tags=[]):
        # if any([tag not in allowed_tags for tag in self.tags]):
        #     print "Excluding %s for tag mismatch: [%s] contains an element not in [%s]" % (self.name, ",".join(self.tags), ",".join(allowed_tags))
        return not any([tag not in allowed_tags for tag in self.tags])

class BoolGoal(BingoGoal):
    goalType = "bool"
    def __init__(self, name, tags=[]):
        self.name = name
        self.tags = tags

class IntGoal(BingoGoal):
    goalType = "int"
    def __init__(self, name, rangeFunc, tags=[]):
        self.name = name
        self.rangeFunc = rangeFunc
        self.tags = tags

    def getCard(self, banned_goals=[], banned_methods=[]):
        cardData = super(IntGoal, self).getCard()
        cardData['target'] = self.rangeFunc()
        return cardData

class GoalGroup(BingoGoal):
    def __init__(self, name, goals, methods, low=1, maxRepeats=1, tags=[]):
        self.name = name
        self.maxRepeats = maxRepeats
        self.goals = goals
        self.low = low
        self.methods = methods
        self.tags = []

    def getCard(self, banned_goals=[], banned_methods=[]):
        method, countFunc = choice([(m,c) for m,c in self.methods if m not in banned_methods])
        count = countFunc()
        if method == "count":
            return {'name': self.name, 'type': "multi", 'method': method, 'target': count}
        subgoals = [goal for goal in self.goals if goal.name not in banned_goals]
        count = min(count, len(subgoals))
        if count > 0:
            goals = sample(subgoals, count)
            return {'name': self.name, 'type': "multi", 'method': method, 'parts': [goal.getCard() for goal in goals]}
        else:
            return None

class BingoGenerator(object):
    @staticmethod
    def get_cards(cards=25, rando=False, difficulty="normal"):
        easy = difficulty == "easy"
        hard = difficulty == "hard"

        def r(low, easy_high, high, hard_high, scalar=1):
            if easy:
                return lambda: randint(low, easy_high)*scalar
            if hard:
                return lambda: randint(easy_high, hard_high)*scalar
            return lambda: randint(low, high)*scalar
        teleporterNames = ["sunkenGlades", "moonGrotto", "mangroveFalls", "valleyOfTheWind", "spiritTree", "mangroveB", "horuFields", "ginsoTree", "forlorn", "mountHoru"] + (["swamp", "sorrowPass"] if rando else [])
        goals = [
            BoolGoal("DrainSwamp"),
            BoolGoal("WilhelmScream"),
            IntGoal("OpenKSDoors", r(3, 4, 8, 11)),
            IntGoal("OpenEnergyDoors", r(3, 4, 5, 6)),
            IntGoal("BreakFloors", r(4, 10, 25, 42)),
            IntGoal("BreakWalls", r(4, 10, 20, 28)),
            IntGoal("UnspentKeystones", r(4, 10, 18, 24)),
            IntGoal("BreakPlants", r(5, 10, 15, 21)),
            IntGoal("TotalPickups", r(60, 100, 140, 180)) if rando else IntGoal("TotalPickups", r(50, 70, 120, 180)),
            IntGoal("UnderwaterPickups", r(2, 6, 10, 16)),
            IntGoal("LightLanterns", r(4, 6, 10, 14)), 
            IntGoal("SpendPoints", r(15, 25, 30, 35)),
            IntGoal("GainExperience", r(8, 10, 16, 20, scalar=500)),  # todo: see if these suck or not
            IntGoal("KillEnemies", r(5, 15, 25, 40, scalar=5)),
            GoalGroup(
                name="CompleteHoruRoom", 
                goals=[BoolGoal(name) for name in ["L1", "L2", "L3", "L4", "R1", "R2", "R3", "R4"]], 
                methods=[("or", lambda: 2), ("and", r(1, 2, 3, 4)), ("count", r(2, 4, 5, 7))]
                ),
            GoalGroup(
                name="ActivateTeleporter", 
                goals=[BoolGoal(name) for name in teleporterNames],   
                methods=[("or", lambda: 2), ("and", r(1, 3, 3, 4)), ("count", r(4, 7, 9, 11) if rando else r(4, 6, 8, 10))],
                maxRepeats=3
                ),
            GoalGroup(
                name="EnterArea", 
                goals=[BoolGoal(name) for name in ["Lost Grove", "Misty Woods", "Sorrow Pass", "Forlorn Ruins", "Mount Horu", "Ginso Tree"]],
                methods=[("or", (lambda: 3) if easy else (lambda: 2)), ("and", r(1, 2, 2, 3))],
                maxRepeats=2
                ),
            GoalGroup(
                name="GetItemAtLoc", 
                goals=[BoolGoal(name) for name in ["LostGroveLongSwim", "ValleyEntryGrenadeLongSwim", "SpiderSacEnergyDoor", "SorrowHealthCell", "SunstonePlant", "GladesLaser", "LowerBlackrootLaserAbilityCell", 
                                                "MistyGrenade", "LeftSorrowGrenade", "DoorWarpExp", "HoruR3Plant", "RightForlornHealthCell", "ForlornEscapePlant"]],
                methods=[("or", (lambda: 3) if easy else (lambda: 2)), ("and", r(1, 2, 3, 4))],
                maxRepeats=2
                ),
            GoalGroup(
                name="VisitTree", 
                goals=[BoolGoal(name) for name in ["Wall Jump", "Charge Flame", "Double Jump", "Bash", "Stomp", "Glide", "Climb", "Charge Jump", "Grenade", "Dash"]],
                methods=[("or", (lambda: 3) if easy else (lambda: 2)), ("and", r(2, 2, 3, 4)), ("count", r(4, 6, 8, 10))],
                maxRepeats=2
                ),
            GoalGroup(
                name="GetAbility", 
                goals=[BoolGoal(name) for name in ["Ultra Defense", "Spirit Light Efficiency", "Ultra Stomp"]],
                methods=[("or", (lambda: 2) if easy else (lambda: 1)), ("and", r(1, 2, 2, 3))],
                ),
            GoalGroup(
                name="StompPeg", 
                goals=[BoolGoal(name) for name in ["BlackrootTeleporter", "SwampPostStomp", "GroveMapstoneTree", "HoruFieldsTPAccess", "L1", "R2", 
                                                "L2", "L4Fire", "L4Drain", "SpiderLake", "GroveGrottoUpper", "GroveGrottoLower"]],
                methods=[("count", r(3, 5, 7, 10)), ("or", (lambda: 3) if easy else (lambda: 2)), ("and", r(2, 3, 3, 4 ))],
                maxRepeats=2
                ),
            GoalGroup(
                name="HuntEnemies", 
                goals=[BoolGoal(name) for name in ["Fronkey Fight", "Misty Miniboss", "Lost Grove Fight Room", "Grotto Miniboss", 
                                                "Lower Ginso Miniboss", "Upper Ginso Miniboss", "Swamp Rhino Miniboss", "Mount Horu Miniboss"]],
                methods=[("count", r(3, 4, 6, 7)), ("and", r(1, 2, 3, 4)), ("or", (lambda: 3) if easy else (lambda: 2))],
                maxRepeats=3
                ),
            GoalGroup(
                name="CompleteEscape", 
                goals=[BoolGoal(name) for name in ["Forlorn Ruins", "Mount Horu", "Ginso Tree"]],
                methods=[("and", r(1, 2, 2, 3)), ("or", (lambda: 1) if hard else (lambda: 2))],
                ),
            GoalGroup(
                name="DieTo",
                goals=[BoolGoal(name) for name in ["Sunstone Lightning", "Lost Grove Laser", "Forlorn Void", "Stomp Rhino", "Horu Fields Acid", "Doorwarp Lava", "Ginso Escape Fronkey", "Blackroot Teleporter Crushers", "NoobSpikes"]],
                methods=[("and", r(1, 2, 2, 3)), ("and_", r(1, 2, 2, 3)), ("or", (lambda: 2))],
                maxRepeats=3
            )
        ]
        if rando:
            goals += [
                IntGoal("HealthCellLocs", r(4, 6, 9, 11)),
                IntGoal("EnergyCellLocs", r(4, 6, 9, 13)),
                IntGoal("AbilityCellLocs", r(6, 15, 20, 30)),
                IntGoal("MapstoneLocs", r(3, 5, 7, 9)),
                GoalGroup(
                    name="VanillaEventLocs",
                    goals=[BoolGoal(name) for name in ["Water Vein", "Gumon Seal", "Sunstone", "Clean Water", "Wind Restored", "Warmth Returned"]],
                    methods=[("or", (lambda: 3) if easy else (lambda: 2)), ("and", r(1, 2, 2, 3))],
                    maxRepeats=2
                    ),
                GoalGroup(
                    name="GetEvent",
                    goals=[BoolGoal(name) for name in ["Water Vein", "Gumon Seal", "Sunstone"]],
                    methods=[("or", (lambda: 2)), ("and", r(1, 2, 2, 3))],
                    maxRepeats=1
                ),
            ]
        else:
            goals += [
                IntGoal("CollectMapstones", r(3, 5, 7, 9)),
                IntGoal("ActivateMaps", r(3, 5, 7, 9)),
                IntGoal("HealthCells", r(4, 6, 9, 11)),
                IntGoal("EnergyCells", r(4, 6, 9, 13)),
                IntGoal("AbilityCells", r(6, 15, 20, 30)),
                GoalGroup(
                    name="GetEvent",
                    goals=[BoolGoal(name) for name in ["Water Vein", "Gumon Seal", "Sunstone", "Clean Water", "Wind Restored", "Warmth Returned"]],
                    methods=[("or", (lambda: 3) if easy else (lambda: 2)), ("and", r(1, 2, 2, 3))],
                    maxRepeats=2
                ),
            ]
        if hard:
            goals += [
                BoolGoal("CoreSkip"),
                BoolGoal("FastStompless"),
            ]
        else:
            goals.append(BoolGoal("DrownFrog"))
        groupSeen = defaultdict(lambda: (1, [], []))
        output = []
        goals = [goal for goal in goals]
        while len(output) < cards:
            goal = choice(goals)
            repeats, banned_subgoals, banned_methods = groupSeen[goal.name]
            if repeats == goal.maxRepeats:
                goals.remove(goal)
            elif repeats > goal:
                assert "help?" and False
            cardData = goal.getCard(banned_subgoals, banned_methods)
            if not cardData:
                continue
            if "method" in cardData:
                banned_methods.append(cardData["method"])
                cardData["method"] = cardData["method"].replace("_", "")
            if "parts" in cardData:
                banned_subgoals += [part["name"] for part in cardData["parts"]]
            output.append(cardData)
            groupSeen[goal.name] = (repeats+1, banned_subgoals, banned_methods) 
        return output

# handlers

class BingoBoard(RequestHandler):
    def get(self):
        template_values = {'app': "Bingo", 'title': "OriDE Bingo"}
        user = User.get()
        if user:
            template_values['user'] = user.name
            template_values['dark'] = user.dark_theme
        self.response.write(template.render(path, template_values))

class BingoCreate(RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'application/json'
        difficulty = param_val(self, "difficulty") or "normal"
        skills = param_val(self, "skills")
        cells = param_val(self, "cells")
        skills = int(skills) if skills and skills != "NaN" else 3
        cells = int(cells) if cells and cells != "NaN" else 3
        show_info = param_flag(self, "showInfo")
        misc_raw = param_val(self, "misc")
        misc_pickup = Pickup.from_str(misc_raw) if misc_raw and misc_raw != "NO|1" else None
        skill_pool = [Skill(x) for x in [0, 2, 3, 4, 5, 8, 12, 14, 50, 51]]
        cell_pool  = [Multiple.with_pickups([AbilityCell(1), AbilityCell(1)]), HealthCell(1), EnergyCell(1)]

        start_pickups = sample(skill_pool, skills)
        for _ in range(cells):
            start_pickups.append(choice(cell_pool))
        if misc_pickup:
            start_pickups.append(misc_pickup)
        start_with = Multiple.with_pickups(start_pickups)
        key = Game.new(_mode="Bingo", _shared=[])
        if show_info and start_with:
            tps = []
            skills = []
            misc = []
            cells = Counter()
            for pick in start_with.children:
                if pick.code == "TP":
                    tps.append(pick.name[:-11])
                elif pick.code == "SK":
                    skills.append(pick.name)
                elif pick.code in ["HC", "EC", "AC"]:
                    cells[pick.code]+=1
                else:
                    misc.append(pick.name)
            sw_parts = []
            if skills:
                sw_parts.append("Skills: " + ", ".join(skills))
            if tps:
                sw_parts.append("TPs: " + ", ".join(tps))
            if cells:
                sw_parts.append("Cells: " + ", ".join([cell if amount == 1 else "%s %ss" % (amount, cell) for cell,amount in cells.items()]))
            if misc:
                sw_parts.append(", ".join(misc))
        base = vanilla_seed.split("\n")
        base[0] = "OpenWorld,Bingo|Bingo Game %s" % key.id()
        if start_with:
            mu_line = "2|MU|%s|Glades" % start_with.id
            base.insert(1, mu_line)
        res = {
            'gameId':     key.id(),
            'seed':       "\n".join(base),
            'cards':      BingoGenerator.get_cards(25, False, difficulty),
            'difficulty': difficulty,
            'playerData': {},
            'teams':      {},
        }
        if show_info:
            res["subtitle"] = " | ".join(sw_parts)

        game = key.get()
        game.bingo = res
        game.put()
        self.response.write(json.dumps(res))

class AddBingoToGame(RequestHandler):
    def get(self, game_id):
        self.response.headers['Content-Type'] = 'application/json'

        game_id = int(game_id)
        difficulty = param_val(self, "difficulty") or "normal"
        if not game_id or int(game_id) < 1:
            return resp_error(self, 404, "please provide a valid game id", 'plain/text')
        game = Game.with_id(game_id)
        if not game:
            return resp_error(self, 404, "game not found", 'plain/text')
        if not game.params:
            return resp_error(self, 412, "game did not have required seed data", 'plain/text')
        if game.mode in [MultiplayerGameType.SHARED, MultiplayerGameType.SPLITSHARDS]:
            return resp_error(self, 412, "Co-op / splitshards bingo are not currently supported", 'plain/text')
        params = game.params.get()
        params.tracking = False
        res = {
            'gameId':     game_id,
            'seed':       "Bingo," + params.get_seed(),
            'cards':      BingoGenerator.get_cards(25, True, difficulty),
            'difficulty': difficulty,
            'subtitle':   params.flag_line(),
            'playerData': {},
            'teams':      {},
        }
        game.bingo = res
        game.put()
        for p in game.get_players():
            game.remove_player(p.key.id())
        self.response.write(json.dumps(res))

class BingoAddPlayer(RequestHandler):
    def get(self, game_id, player_id):
        player_id = int(player_id)
        res = {}
        game = Game.with_id(game_id)
        if not game:
            return resp_error(self, 404, "Game not found", "text/plain")
        if player_id in game.player_nums() and not game.params:
            return resp_error(self, 409, "Player id already in use!", "text/plain")
            self.response.status = 409
            return
        p = game.player(player_id)
        user = User.get()
        if user:
            p.user = user.key
            p.put()
            user.games.append(game.key)
            user.put()

        team = str(param_val(self, "joinTeam") or player_id)
        if team not in game.bingo["teams"]:
            game.bingo["teams"][team] = []
        game.bingo["teams"][team].append(player_id)
        game.put()

        res = game.bingo
        
        res["playerData"] = {}
        for player in game.get_players():
            pid = player.pid()
            res["playerData"][pid] = {'name': player.name(), 'teamname': player.teamname(), 'bingoData': player.bingo_data}

        self.response.headers['Content-Type'] = 'application/json'
        self.response.write(json.dumps(res))

class BingoGetGame(RequestHandler):
    def get(self, game_id):
        res = {}
        game = Game.with_id(game_id)
        if not game:
            return resp_error(self, 404, "Game not found", "text/plain")
            
        res = game.bingo
        if not res:
            return resp_error(self, 404, "Game found but had no bingo data...", "text/plain")
        res["playerData"] = {}
        for player in game.get_players():
            pid = player.pid()
            res["playerData"][pid] = {'name': player.name(), 'teamname': player.teamname(), 'bingoData': player.bingo_data}
            if debug and str(pid) in bingo_data:
                res["playerData"][pid] = bingo_data[str(pid)]

        self.response.headers['Content-Type'] = 'application/json'
        self.response.write(json.dumps(res))

class HandleBingoUpdate(RequestHandler):
    def post(self, game_id, player_id):
        game = Game.with_id(game_id)
        if not game:
            return resp_error(self, 404)
        p = game.player(player_id)
        p.bingo_data = json.loads(self.request.POST["bingoData"])
        p.put()

routes = [
    Route('/bingo/board', handler=BingoBoard, name="bingo-board", strict_slash=True),
    Route('/bingo/spectate', handler=BingoBoard, name="bingo-board-spectate", strict_slash=True),
    Route('/bingo/game/<game_id>/fetch', handler=BingoGetGame, name="bingo-get-game", strict_slash=True),
    Route('/bingo/game/<game_id>/add/<player_id>', handler=BingoAddPlayer, name="bingo-add-player", strict_slash=True),
    Route('/bingo/new', handler=BingoCreate, name="bingo-create-game", strict_slash=True),
    Route('/bingo/from_game/<game_id>', handler=AddBingoToGame, name="add-bingo-to-game", strict_slash=True),
    Route('/netcode/game/<game_id:\d+>/player/<player_id:\d+>/bingo', handler=HandleBingoUpdate,  name="netcode-player-bingo-tick"),
]

