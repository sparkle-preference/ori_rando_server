"""Mock clients that imitate the shipped dll's netcode, one profile per client era.

WsClient imitates origin/4.3 (ws-first, per-channel http fallback); LegacyClient
imitates the 4.1.7 straggler (http only, no version field). Behavior is derived from
RandomizerSyncManager.cs on those branches; the parsing contract mirrors
golden_wire_test.py via wire.TickBody."""
import json
import random
import threading
import time
from urllib.parse import quote

import requests
import simple_websocket

from mockclient.seedfile import SeedFile, goal_shapes_from
from mockclient.wire import TickBody, form_body, parse_frame
from util import coords_in_order

VERSION_43 = "4.2.16"
# the dll's have_i/seen_i words are positional over the canonical location list
COORD_BIT = {c: i for i, c in enumerate(coords_in_order)}


class MockClient(threading.Thread):
    """One simulated player. Drive with a plan: [(tick_no, method_name, args)]."""

    daemon = True

    def __init__(self, base_url, seed_text, name=None, tick_period=0.15, rng_seed=0):
        super().__init__()
        self.base = base_url
        self.seed = SeedFile(seed_text)
        self.gid, self.pid = self.seed.game_id, self.seed.player_id
        self.root = "%s/netcode/game/%d/player/%d" % (base_url, self.gid, self.pid)
        self.label = name or ("P%d" % self.pid)
        self.period = tick_period
        self.rng = random.Random(rng_seed * 1000 + self.pid)
        self.http = requests.Session()
        self.plan = []
        self.send_complete = False
        # state the scenarios assert on
        self.tick_no = 0
        self.last_tick = None          # TickBody
        self.signals_handled = []
        self.received_items = []       # from pickup: signals
        self.won = False
        self.acks = {}                 # found token -> status
        self.dropped_pickups = []
        self.completeack = None
        self.events = []               # (tick_no, direction, text)
        self.errors = []
        # dll-side counters
        self._found_queue = []
        self._sending = None           # (token, pickup, sent_at_tick, attempts)
        self._token = 0
        self._collected = 0
        self._seen = [0] * 8
        self._have = [0] * 8
        self._confirmed = set()
        self._x, self._y = 189.0, -219.0
        # bingo controller state
        self.bingo_goals = {}          # name -> {"kind", "subs", "done", "count"}
        self._bingo_timer = 5
        self.bingoacks = []
        self._pending_goals = []
        self.went_http = False
        # ticks to keep draining after the plan ends: late slot grants, goals
        # frames and acks arrive on the server's schedule, not ours
        self.linger = 20

        # legacy seeds baked the goals in; the 4.3 flow asks the server instead
        if self.seed.bingo and self.seed.goals_line:
            self._init_goals(self.seed.goal_shapes())
        # multiworld manifest: slot s's item lives at pseudo-loc -(s+2); the
        # tick's [6] bitfields say which slots to grant, no signal involved
        self._manifest = {-int(p["loc"]) - 2: p for p in self.seed.pickups
                          if p["code"] == "MW" and -257 <= int(p["loc"]) <= -2}
        self._granted_slots = set()

    def _init_goals(self, shapes):
        for cname, (kind, subs, target) in shapes.items():
            self.bingo_goals[cname] = {"kind": kind, "subs": subs, "target": target,
                                       "done": set(), "value": False}
        # a plan can ask for a goal before the goals: frame lands; do it now
        pending, self._pending_goals = self._pending_goals, []
        for name, sub in pending:
            self.complete_goal(name, sub)

    def log(self, direction, text):
        self.events.append((self.tick_no, direction, text))

    # ---- scenario-facing actions -------------------------------------------------
    def collect(self, index):
        """Pick up the index-th pickup in this player's seed."""
        p = self.seed.pickups[index]
        self._collected += 1
        f = COORD_BIT.get(int(p["loc"]))
        if f is not None:
            self._seen[f // 32] |= 1 << (f % 32)
            self._have[f // 32] |= 1 << (f % 32)
        self._token += 1
        self._found_queue.append((self._token, p))

    def complete_goal(self, name, sub=None):
        if name not in self.bingo_goals:
            self._pending_goals.append((name, sub))
            return
        g = self.bingo_goals[name]
        if sub:
            g["done"].add(sub)
        elif g["kind"] == "int":
            g["value"] = g["target"] if g["target"] is not None else 9999
        elif g["kind"] == "multi":
            g["done"] = set(g["subs"])
            g["value"] = True
        else:
            g["value"] = True

    def wander(self):
        self._x += self.rng.uniform(-40, 40)
        self._y += self.rng.uniform(-20, 20)

    # ---- profile hooks (WsClient / LegacyClient override) ------------------------
    def on_signal(self, sig):
        self.signals_handled.append(sig)
        if sig.startswith("win:"):
            self.won = True
        elif sig.startswith("pickup:"):
            self.received_items.append(sig[len("pickup:"):])
        self.confirm(sig)

    def handle_tick_body(self, body):
        self.last_tick = TickBody(body)
        for sig in self.last_tick.signals:
            if sig and sig not in self._confirmed:
                self._confirmed.add(sig)
                self.on_signal(sig)
        if self.last_tick.slots:
            for w, word in enumerate(int(x) for x in self.last_tick.slots.split(";")):
                for b in range(32):
                    s = w * 32 + b
                    if word >> b & 1 and s not in self._granted_slots:
                        self._granted_slots.add(s)
                        item = self._manifest.get(s)
                        self.received_items.append(
                            "%s|%s" % (item["id"].split(",")[2], item["id"].split(",")[3])
                            if item else "slot%d-unmanifested" % s)

    def tick_payload(self):
        pairs = [("x", "%.2f" % self._x), ("y", "%.2f" % self._y)]
        if self.version:
            pairs.append(("version", self.version))
        pairs += [("seen_%d" % i, str(self._seen[i])) for i in range(8)]
        pairs += [("have_%d" % i, str(self._have[i])) for i in range(8)]
        return pairs

    def run(self):
        try:
            self.connect()
            plan = sorted(self.plan)
            idle = 0
            while True:
                self.tick_no += 1
                self.drain()
                while plan and plan[0][0] <= self.tick_no:
                    _, method, args = plan.pop(0)
                    getattr(self, method)(*args)
                self.service_found_queue()
                self.wander()
                self.send_tick()
                if self.bingo_goals:
                    self._bingo_timer -= 1
                    if self._bingo_timer <= 0:
                        self._bingo_timer = 5
                        self.post_bingo()
                if not plan and self._sending is None and not self._found_queue:
                    if self.send_complete and self.completeack is None:
                        if self.tick_no % 3 == 0 or idle == 0:
                            self.request_complete()
                    elif idle > self.linger:
                        break
                    idle += 1
                time.sleep(self.period)
            if self.bingo_goals:
                self.post_bingo()
            self.disconnect()
        except Exception as e:
            self.errors.append("%s: %r" % (self.label, e))


class WsClient(MockClient):
    version = VERSION_43

    def connect(self):
        try:
            self.ws = simple_websocket.Client(
                self.base.replace("http://", "ws://") + "/netcode/game/%d/player/%d/ws"
                % (self.gid, self.pid))
            self.ws_open = True
        except (OSError, simple_websocket.ConnectionError,
                simple_websocket.ConnectionClosed):
            self.ws_open = False
            self._go_http()
            return
        try:
            self.send_frame("seed:" + form_body([("seed", self.seed.lines[0]),
                                                 ("version", self.version)]))
            # the bingo flag arms the controller; the goals come from the server,
            # asked on every connect so a pre-start reroll reaches us
            if self.seed.bingo:
                self.send_frame("goals:")
        except simple_websocket.ConnectionClosed:
            self.ws_open = False
            self._go_http()

    def _go_http(self):
        """The dll's per-channel fallback, wholesale: seed and goals re-land
        over http so a mid-session socket loss loses nothing."""
        self.went_http = True
        self.log("http", "falling back to http")
        r = self.http.post(self.root + "/setSeed",
                           data={"seed": self.seed.lines[0], "version": self.version},
                           timeout=10)
        self.log("http", "setSeed -> %s" % r.status_code)
        if self.seed.bingo:
            r = self.http.get(self.root + "/goals", timeout=10)
            self.log("http", "goals -> %s" % r.status_code)
            if r.status_code == 200:
                self.bingo_goals.clear()
                self._init_goals(goal_shapes_from(r.text))

    def disconnect(self):
        if self.ws_open:
            self.ws.close()
            self.ws_open = False

    def send_frame(self, text):
        self.log(">", text if len(text) < 200 else text[:200] + "...")
        self.ws.send(text)

    def drain(self):
        while self.ws_open:
            try:
                got = self.ws.receive(timeout=0)
            except simple_websocket.ConnectionClosed:
                # a full server accepts the handshake then closes 1013
                self.ws_open = False
                self._go_http()
                return
            if got is None:
                return
            self.log("<", got if len(got) < 200 else got[:200] + "...")
            kind, body = parse_frame(got)
            if kind == "tick":
                self.handle_tick_body(body)
            elif kind == "foundack":
                token, _, status = body.partition("|")
                self.on_foundack(int(token), int(status))
            elif kind == "goals":
                self.bingo_goals.clear()
                self._init_goals(goal_shapes_from(body))
            elif kind == "bingoack":
                self.bingoacks.append(int(body))
            elif kind == "completeack":
                self.completeack = int(body)
            elif kind == "err":
                self.errors.append("server err frame: " + body)

    def send_tick(self):
        if self.ws_open:
            self.send_frame("tick:" + form_body(self.tick_payload()))
            return
        r = self.http.post(self.root + "/tick/", data=dict(self.tick_payload()), timeout=10)
        self.log("http", "tick -> %s" % r.status_code)
        if r.status_code == 200:
            self.handle_tick_body(r.text)

    def service_found_queue(self):
        if not self.ws_open:
            while self._found_queue:
                token, p = self._found_queue.pop(0)
                self.send_found_http(token, p)
            return
        if self._sending is None and self._found_queue:
            token, p = self._found_queue.pop(0)
            self._sending = (token, p, self.tick_no, 1)
            self.send_found_ws(token, p)
        elif self._sending is not None:
            token, p, sent_at, attempts = self._sending
            # the dll falls back to http after 5s with no ack
            if self.tick_no - sent_at > 5:
                self._sending = None
                self.send_found_http(token, p)

    def send_found_ws(self, token, p):
        self.send_frame("found:%d|zone=%s|%s|%s|%s"
                        % (token, quote(p["zone"]), p["loc"], p["code"], p["id"]))

    def send_found_http(self, token, p):
        r = self.http.get("%s/found/%s/%s/%s" % (self.root, p["loc"], p["code"],
                                                 quote(p["id"], safe="/,|")),
                          params={"zone": p["zone"]}, timeout=10)
        self.log("http", "found %s -> %s" % (p["loc"], r.status_code))
        self.acks[token] = r.status_code
        if r.status_code >= 300 and r.status_code not in (410, 406):
            self.dropped_pickups.append((p, r.status_code))

    def on_foundack(self, token, status):
        self.acks[token] = status
        if self._sending and self._sending[0] == token:
            _, p, sent_at, attempts = self._sending
            if status < 300 or status in (406, 410):
                self._sending = None
            elif attempts < 3:
                self._sending = (token, p, self.tick_no, attempts + 1)
                self.send_found_ws(token, p)
            else:
                self._sending = None
                self.dropped_pickups.append((p, status))

    def confirm(self, sig):
        if self.ws_open:
            self.send_frame("conf:" + sig)
        else:
            r = self.http.get("%s/callback/%s" % (self.root, quote(sig, safe="")), timeout=10)
            self.log("http", "callback -> %s" % r.status_code)

    def request_complete(self):
        if self.ws_open:
            self.send_frame("complete:")
            return
        r = self.http.get(self.root + "/complete", timeout=10)
        self.log("http", "complete -> %s %s" % (r.status_code, r.text[:30]))
        if r.status_code == 200 and r.text.strip() == "ok":
            self.completeack = 200

    def post_bingo(self):
        data = {}
        for name, g in self.bingo_goals.items():
            if g["kind"] == "bool":
                data[name] = {"value": bool(g["value"])}
            elif g["kind"] == "int":
                data[name] = {"value": int(g["value"] or 0)}
            else:
                total = len(g["done"]) if g["done"] or not g["value"] else 9999
                data[name] = {"value": {s: {"value": True} for s in g["done"]},
                              "total": total}
        body = json.dumps(data)
        if self.ws_open and len(body) < 30000:
            self.send_frame("bingo:bingoData=%s&version=%s" % (quote(body), self.version))
        else:
            r = self.http.post(self.root + "/bingo",
                               data={"bingoData": body, "version": self.version}, timeout=10)
            self.bingoacks.append(r.status_code)


class LegacyClient(MockClient):
    """The 4.1.7 straggler: http only, no version field in the tick."""
    version = None

    def connect(self):
        r = self.http.post(self.root + "/setSeed",
                           data={"seed": self.seed.lines[0]}, timeout=10)
        self.log("http", "setSeed -> %s" % r.status_code)

    def disconnect(self):
        pass

    def drain(self):
        pass

    def send_tick(self):
        r = self.http.post(self.root + "/tick/", data=dict(self.tick_payload()), timeout=10)
        self.log("http", "tick -> %s %s" % (r.status_code, r.text[:120]))
        if r.status_code == 200:
            self.handle_tick_body(r.text)

    def service_found_queue(self):
        while self._found_queue:
            token, p = self._found_queue.pop(0)
            r = self.http.get("%s/found/%s/%s/%s" % (self.root, p["loc"], p["code"],
                                                     quote(p["id"], safe="/,|")),
                              params={"zone": p["zone"]}, timeout=10)
            self.log("http", "found %s -> %s" % (p["loc"], r.status_code))
            self.acks[token] = r.status_code
            if r.status_code >= 300 and r.status_code not in (410, 406):
                self.dropped_pickups.append((p, r.status_code))

    def confirm(self, sig):
        r = self.http.get("%s/callback/%s" % (self.root, quote(sig, safe="")), timeout=10)
        self.log("http", "callback %s -> %s" % (sig[:40], r.status_code))

    def request_complete(self):
        r = self.http.get(self.root + "/complete", timeout=10)
        self.log("http", "complete -> %s %s" % (r.status_code, r.text[:40]))
        if r.status_code == 200 and r.text.strip() == "ok":
            self.completeack = 200

    def post_bingo(self):
        pass
