"""Scenario plumbing: roll a game, download seeds, run clients, judge invariants."""
import json

import requests

STANDARD_PATHS = ["casual-core", "casual-dboost", "standard-core", "standard-dboost",
                  "standard-lure", "standard-abilities"]
STANDARD_POOL = {"TP|Grove": [1], "TP|Swamp": [1], "TP|Grotto": [1], "TP|Valley": [1],
                 "TP|Sorrow": [1], "TP|Ginso": [1], "TP|Horu": [1], "TP|Forlorn": [1],
                 "HC|1": [12], "EC|1": [15], "AC|1": [33], "RB|0": [3], "RB|1": [3],
                 "RB|6": [3], "RB|9": [1], "RB|10": [1], "RB|11": [1], "RB|12": [1],
                 "RB|13": [3], "RB|15": [3]}
# tick field [0]: bit index per skill id, as SkillInfos orders them
SKILL_BIT = {0: 0, 2: 1, 3: 2, 4: 3, 5: 4, 8: 5, 12: 6, 14: 7, 50: 8, 51: 9}


def base_params(seed, players=1, **extra):
    p = {"seed": seed, "tracking": True, "paths": STANDARD_PATHS,
         "keyMode": "Clues", "pathDiff": "Normal", "variations": ["ForceTrees"],
         "expPool": 10000, "cellFreq": 40, "fillAlg": "Balanced",
         "itemPool": dict(STANDARD_POOL), "players": players}
    if players > 1:
        p["coopGameMode"] = "Multiworld"
        p["coopGenMode"] = "Cloned Seeds"
        p["syncMode"] = 4
    p.update(extra)
    return p


class Rolled(object):
    """One built game: param_id, game_id, and each player's downloaded seed text."""

    def __init__(self, stack, params):
        r = requests.post(stack.base_url + "/generator/build",
                          data={"params": json.dumps(params)}, timeout=120)
        assert r.status_code == 200, "build failed %s: %s" % (r.status_code, r.text[:400])
        body = r.json()
        self.stack = stack
        self.param_id = body["paramId"]
        self.game_id = body.get("gameId")
        self.player_count = body.get("playerCount", 1)
        self.build = body

    def seed_text(self, player):
        r = requests.get(self.stack.base_url + "/generator/seed/%s" % self.param_id,
                         params={"player_id": player, "game_id": self.game_id}, timeout=60)
        assert r.status_code == 200, "seed download %s: %s" % (r.status_code, r.text[:200])
        return r.text

    def start_bingo(self, **args):
        args.setdefault("noTimer", 1)
        r = requests.get(self.stack.base_url + "/bingo/from_game/%s" % self.game_id,
                         params=args, timeout=60)
        assert r.status_code == 200, "bingo/from_game %s: %s" % (r.status_code, r.text[:300])
        return r

    def fetch_board(self):
        r = requests.get(self.stack.base_url + "/bingo/game/%s/fetch" % self.game_id,
                         params={"first": 1}, timeout=30)
        assert r.status_code == 200, "bingo fetch %s: %s" % (r.status_code, r.text[:200])
        return r.json()

    def tracker_update(self):
        r = requests.get(self.stack.base_url + "/tracker/game/%s/fetch/update" % self.game_id,
                         params={"modes": " ".join(STANDARD_PATHS)}, timeout=60)
        return r.status_code, (r.json() if r.status_code == 200 else r.text)


class Judge(object):
    """Collects invariant verdicts; a scenario passes when every check held."""

    def __init__(self, name):
        self.name = name
        self.checks = []

    def check(self, label, ok, detail=""):
        self.checks.append((label, bool(ok), detail))
        return ok

    def equal(self, label, got, want):
        return self.check(label, got == want, "got %r, want %r" % (got, want))

    @property
    def passed(self):
        return all(ok for _, ok, _ in self.checks)

    def report(self):
        lines = ["%s: %s" % (self.name, "PASS" if self.passed else "FAIL")]
        for label, ok, detail in self.checks:
            lines.append("  [%s] %s%s" % ("ok" if ok else "XX", label,
                                          (" -- " + detail) if (detail and not ok) else ""))
        return "\n".join(lines)


def run_clients(*clients, timeout=120):
    for c in clients:
        c.start()
    for c in clients:
        c.join(timeout)
    hung = [c.label for c in clients if c.is_alive()]
    if hung:
        raise RuntimeError("clients never finished: %s" % hung)


def expected_skills(client, collected_indices):
    """The [0]-field bits this client's collected SK pickups should have set."""
    bits = 0
    for i in collected_indices:
        p = client.seed.pickups[i]
        if p["code"] == "SK":
            sid = int(p["id"].split("|")[0].split(",")[0])
            if sid in SKILL_BIT:
                bits |= 1 << SKILL_BIT[sid]
    return bits
