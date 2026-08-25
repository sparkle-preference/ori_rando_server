"""The scenarios. Each takes a LocalStack, returns a Judge."""
import json

import requests

from mockclient.client import LegacyClient, WsClient
from mockclient.scenario import Judge, Rolled, base_params, run_clients
from mockclient.seedfile import goal_shapes_from


def fetch_goals(stack, gid, pid):
    r = requests.get(stack.base_url + "/netcode/game/%s/player/%s/goals" % (gid, pid),
                     timeout=30)
    return r.status_code, r.text


def _collect_plan(client, count, start=2, spacing=2):
    picks = list(range(min(count, len(client.seed.pickups))))
    client.plan = [(start + i * spacing, "collect", (i,)) for i in picks]
    return picks


def solo_ws(stack):
    """One current-profile client plays a tracked solo seed end to end."""
    j = Judge("solo_ws")
    rolled = Rolled(stack, base_params("mock-solo-ws"))
    c = WsClient(stack.base_url, rolled.seed_text(1))
    j.check("seed carries the sync line", c.seed.sync_id is not None,
            "line0: %r" % c.seed.lines[0][:120])
    picks = _collect_plan(c, 10)
    c.send_complete = True
    run_clients(c)
    j.check("no client-side exceptions", not c.errors, "; ".join(c.errors))
    j.equal("every pickup acked 200", sorted(set(c.acks.values())), [200])
    j.check("nothing dropped", not c.dropped_pickups, repr(c.dropped_pickups))
    j.equal("complete acked", c.completeack, 200)
    # own finds never re-grant over the wire; the server truth is the tracker's seen list
    status, body = rolled.tracker_update()
    j.equal("tracker fetch/update still serves (post-sweep)", status, 200)
    if status == 200:
        seen = set(body["players"].get("1", {}).get("seen", []))
        want = {int(c.seed.pickups[i]["loc"]) for i in picks}
        j.check("tracker seen list carries every collected loc", want <= seen,
                "missing %r of %r" % (sorted(want - seen)[:6], sorted(want)[:6]))
    return j


def solo_legacy(stack):
    """The 4.1.7 straggler profile: pure http, no version field anywhere."""
    j = Judge("solo_legacy")
    rolled = Rolled(stack, base_params("mock-solo-legacy"))
    c = LegacyClient(stack.base_url, rolled.seed_text(1))
    picks = _collect_plan(c, 8)
    c.send_complete = True
    run_clients(c)
    j.check("no client-side exceptions", not c.errors, "; ".join(c.errors))
    j.equal("every pickup acked 200", sorted(set(c.acks.values())), [200])
    j.equal("complete answered ok", c.completeack, 200)
    status, body = rolled.tracker_update()
    j.equal("tracker still serves the legacy game", status, 200)
    if status == 200:
        seen = set(body["players"].get("1", {}).get("seen", []))
        want = {int(c.seed.pickups[i]["loc"]) for i in picks}
        j.check("tick POST + found GET landed server-side", want <= seen,
                "missing %r" % sorted(want - seen)[:6])
    return j


def mw2(stack):
    """Two-world multiworld: cross-world sends arrive as pickup: signals."""
    j = Judge("mw2")
    rolled = Rolled(stack, base_params("mock-mw-two", players=2))
    j.equal("two players rolled", rolled.player_count, 2)
    cs = [WsClient(stack.base_url, rolled.seed_text(p), tick_period=0.12, rng_seed=p)
          for p in (1, 2)]
    sent = {1: [], 2: []}
    for c in cs:
        # collect every pickup that belongs to someone else, plus a few of our own
        mine = [i for i, p in enumerate(c.seed.pickups) if p["code"] != "MW"][:5]
        theirs = [i for i, p in enumerate(c.seed.pickups) if p["code"] == "MW"][:6]
        c.plan = [(2 + n * 2, "collect", (i,)) for n, i in enumerate(mine + theirs)]
        for i in theirs:
            sent[c.pid].append(c.seed.pickups[i])
    run_clients(*cs)
    for c in cs:
        j.check("%s: no exceptions" % c.label, not c.errors, "; ".join(c.errors))
        j.check("%s: no failed acks" % c.label,
                all(s < 300 for s in c.acks.values()), repr(c.acks))
    for finder, owner in ((cs[0], cs[1]), (cs[1], cs[0])):
        want = len(sent[finder.pid])
        got = len(owner.received_items)
        j.check("%s's %d cross-world sends reached %s" % (finder.label, want, owner.label),
                got >= want, "owner saw %d pickup: signals: %r" % (got, owner.received_items))
    j.check("names field rode the multiworld tick",
            cs[0].last_tick and len(cs[0].last_tick.fields) >= 8,
            "fields: %r" % (cs[0].last_tick.fields if cs[0].last_tick else None))
    return j


def mw_bingo_solo_optin(stack):
    """Two-world multiworld where ONLY world 1 opted into bingo."""
    j = Judge("mw_bingo_solo_optin")
    params = base_params("mock-mw-bingo-solo", players=2,
                         worldSettings=[{"variations": ["Bingo", "ForceTrees"],
                                        "bingoLines": 3},
                                       {}])
    rolled = Rolled(stack, params)
    rolled.start_bingo(lines=3, difficulty="normal")
    s1, s2 = rolled.seed_text(1), rolled.seed_text(2)
    c1 = WsClient(stack.base_url, s1, tick_period=0.12, rng_seed=1)
    c2 = WsClient(stack.base_url, s2, tick_period=0.12, rng_seed=2)
    j.check("world 1's seed has the bingo flag", c1.seed.bingo,
            "flags: %r" % c1.seed.flags)
    j.check("no seed bakes a Goals line anymore", c1.seed.goals_line is None,
            "last lines: %r" % s1.strip().split("\n")[-2:])
    j.check("world 2's seed has NO bingo flag", not c2.seed.bingo,
            "flags: %r" % c2.seed.flags)
    status, goals_body = fetch_goals(stack, rolled.game_id, 1)
    j.equal("the goals route answers the bingo world", status, 200)
    status2, _ = fetch_goals(stack, rolled.game_id, 2)
    j.equal("the goals route refuses the non-bingo world", status2, 404)
    board = rolled.fetch_board()
    j.check("board payload has per-world boards", "boards" in board,
            "keys: %r" % sorted(board.keys()))
    worlds = sorted((board.get("boards") or {}).keys())
    j.equal("exactly world 1 has a board", worlds, ["1"])
    goals = sorted(goal_shapes_from(goals_body))
    j.check("the channel names the board's cards", len(goals) >= 5, "parsed: %r" % goals[:8])
    done = goals[:3]
    c1.plan = [(4 + i, "complete_goal", (g,)) for i, g in enumerate(done)]
    _collect_plan(c2, 4)
    run_clients(c1, c2)
    j.check("bingo posts acked", c1.bingoacks and all(s == 200 for s in c1.bingoacks),
            repr(c1.bingoacks))
    j.check("the client learned its goals over the socket", len(c1.bingo_goals) >= 5,
            repr(sorted(c1.bingo_goals))[:120])
    after = rolled.fetch_board()
    j.check("the first report started the clock",
            (after.get("start_time_posix") or 0) > 0, "keys: %r" % sorted(after)[:12])
    cards = (after.get("boards", {}).get("1") or {}).get("cards", [])
    completed = set()
    for card in cards:
        for pid, prog in (card.get("progress") or {}).items():
            if prog.get("completed"):
                completed.add(card.get("name"))
    j.check("the board shows the completed goals",
            set(done) <= completed, "done %r, board says %r" % (done, sorted(completed)))
    j.check("world 2 played on unbothered",
            all(s < 300 for s in c2.acks.values()) and not c2.errors,
            "%r %r" % (c2.acks, c2.errors))
    # a public overlay probe for the non-bingo world must refuse, not adopt it
    r = requests.get(stack.base_url + "/bingo/bingothon/%s/player/2" % rolled.game_id, timeout=30)
    j.equal("bingothon refuses the non-bingo world", r.status_code, 404)
    r = requests.get(stack.base_url + "/bingo/bingothon/%s/player/1" % rolled.game_id, timeout=30)
    j.equal("bingothon serves the bingo world", r.status_code, 200)
    rolled.fetch_board()
    j.check("the board still fetches after the probes", True)
    return j


def mw_bingo_two_boards(stack):
    """Both worlds play bingo on their own settings; boards must stay independent."""
    j = Judge("mw_bingo_two_boards")
    params = base_params("mock-mw-bingo-two", players=2,
                         worldSettings=[{"variations": ["Bingo", "ForceTrees"],
                                        "bingoDiff": "easy", "bingoLines": 3},
                                       {"variations": ["Bingo", "ForceTrees"],
                                        "bingoDiff": "hard", "bingoLines": 5}])
    rolled = Rolled(stack, params)
    rolled.start_bingo(lines=3, difficulty="normal")
    c1 = WsClient(stack.base_url, rolled.seed_text(1), tick_period=0.12, rng_seed=1)
    c2 = WsClient(stack.base_url, rolled.seed_text(2), tick_period=0.12, rng_seed=2)
    j.check("both seeds carry bingo", c1.seed.bingo and c2.seed.bingo)
    j.check("neither seed bakes goals",
            c1.seed.goals_line is None and c2.seed.goals_line is None)
    _, g1 = fetch_goals(stack, rolled.game_id, 1)
    _, g2 = fetch_goals(stack, rolled.game_id, 2)
    board = rolled.fetch_board()
    worlds = sorted((board.get("boards") or {}).keys())
    j.equal("a board per world", worlds, ["1", "2"])
    b1 = [c.get("name") for c in board["boards"]["1"]["cards"]]
    b2 = [c.get("name") for c in board["boards"]["2"]["cards"]]
    j.check("the two boards differ", b1 != b2, "identical card list")
    j.equal("world 1's channel matches world 1's board",
            sorted(goal_shapes_from(g1)), sorted(set(b1)))
    j.equal("world 2's channel matches world 2's board",
            sorted(goal_shapes_from(g2)), sorted(set(b2)))
    done1 = sorted(goal_shapes_from(g1))[:3]
    c1.plan = [(4 + i, "complete_goal", (g,)) for i, g in enumerate(done1)]
    run_clients(c1, c2)
    after = rolled.fetch_board()
    prog2 = [c for c in after["boards"]["2"]["cards"]
             if any(p.get("completed") for p in (c.get("progress") or {}).values())]
    j.check("world 2's board untouched by world 1's play", not prog2,
            "world 2 cards showing progress: %r" % [c.get("name") for c in prog2])
    prog1 = set()
    for card in after["boards"]["1"]["cards"]:
        if any(p.get("completed") for p in (card.get("progress") or {}).values()):
            prog1.add(card.get("name"))
    j.check("world 1's board shows its own progress", set(done1) <= prog1,
            "done %r, board %r" % (done1, sorted(prog1)))
    return j


def bingo_reroll_flow(stack):
    """Reroll is free until the clock starts, and the clock starts with play."""
    j = Judge("bingo_reroll_flow")
    params = base_params("mock-reroll", players=2,
                         worldSettings=[{"variations": ["Bingo", "ForceTrees"],
                                        "bingoLines": 3}, {}])
    rolled = Rolled(stack, params)
    rolled.start_bingo(lines=3, difficulty="normal")
    board = rolled.fetch_board()
    j.check("no clock before anyone plays", "start_time_posix" not in board,
            "keys: %r" % sorted(board)[:12])
    _, before = fetch_goals(stack, rolled.game_id, 1)
    s1 = rolled.seed_text(1)
    r = requests.get(stack.base_url + "/bingo/game/%s/reroll_board" % rolled.game_id,
                     params={"lines": 3}, timeout=60)
    j.equal("reroll allowed before the clock starts (seed already downloaded)",
            r.status_code, 200)
    _, after_reroll = fetch_goals(stack, rolled.game_id, 1)
    j.check("the reroll moved the goals", before != after_reroll, "identical channel body")
    c1 = WsClient(stack.base_url, s1, tick_period=0.12, rng_seed=1)
    done = sorted(goal_shapes_from(after_reroll))[:2]
    c1.plan = [(4 + i, "complete_goal", (g,)) for i, g in enumerate(done)]
    run_clients(c1)
    j.check("the client tracked the REROLLED goals, not its stale seed file",
            sorted(c1.bingo_goals) == sorted(goal_shapes_from(after_reroll)),
            "client: %r" % sorted(c1.bingo_goals)[:6])
    j.check("posts acked", c1.bingoacks and all(s == 200 for s in c1.bingoacks),
            repr(c1.bingoacks))
    board = rolled.fetch_board()
    j.check("the first report started the clock", (board.get("start_time_posix") or 0) > 0)
    r = requests.get(stack.base_url + "/bingo/game/%s/reroll_board" % rolled.game_id,
                     timeout=60)
    j.equal("reroll refused once the game is live", r.status_code, 412)
    return j


def mw4_concurrency(stack):
    """Four worlds hammering the stack at once: transactions, cache, slots."""
    j = Judge("mw4_concurrency")
    rolled = Rolled(stack, base_params("mock-mw-four", players=4))
    j.equal("four players rolled", rolled.player_count, 4)
    cs = [WsClient(stack.base_url, rolled.seed_text(p), tick_period=0.08, rng_seed=p)
          for p in (1, 2, 3, 4)]
    sent = {}
    for c in cs:
        c.linger = 30
        mine = [i for i, p in enumerate(c.seed.pickups) if p["code"] != "MW"][:4]
        theirs = [i for i, p in enumerate(c.seed.pickups) if p["code"] == "MW"][:6]
        # every client acts on the same tick numbers, so the requests collide
        c.plan = [(2 + n, "collect", (i,)) for n, i in enumerate(mine + theirs)]
        sent[c.pid] = len(theirs)
    run_clients(*cs)
    for c in cs:
        j.check("%s: no exceptions" % c.label, not c.errors, "; ".join(c.errors)[:160])
        j.check("%s: no failed acks" % c.label,
                all(s < 300 for s in c.acks.values()),
                repr({k: v for k, v in c.acks.items() if v >= 300}))
    total_sent = sum(sent.values())
    total_got = sum(len(c.received_items) for c in cs)
    j.check("every cross-world send arrived somewhere (%d sent)" % total_sent,
            total_got >= total_sent, "only %d arrived" % total_got)
    status, body = rolled.tracker_update()
    j.equal("tracker serves the four-way game", status, 200)
    if status == 200:
        ok = all(str(c.pid) in body["players"] for c in cs)
        j.check("tracker knows all four players", ok, "players: %r" % sorted(body["players"]))
    return j


def shared_bingo_teams(stack):
    """A teams lobby board: three teammates and a rival post square progress
    into the same cards at the same time."""
    j = Judge("shared_bingo_teams")
    r = requests.get(stack.base_url + "/bingo/new",
                     params={"difficulty": "normal", "lines": 3, "teams": 1,
                             "noTimer": 1, "seed": "contend"}, timeout=60)
    j.equal("lobby created", r.status_code, 200)
    gid = r.json()["gameId"]

    def join(pid, team=None):
        q = {"joinTeam": team} if team else {}
        return requests.get(stack.base_url + "/bingo/game/%s/add/%s" % (gid, pid),
                            params=q, timeout=60)

    j.equal("P1 opens team", join(1).status_code, 200)
    j.equal("P2 joins it", join(2, team=1).status_code, 200)
    j.equal("P3 joins it", join(3, team=1).status_code, 200)
    j.equal("P4 goes alone", join(4).status_code, 200)

    def seed_for(pid):
        rr = requests.get(stack.base_url + "/bingo/game/%s/seed/%s" % (gid, pid), timeout=60)
        assert rr.status_code == 200, rr.status_code
        return rr.text

    status, goals_body = fetch_goals(stack, gid, 2)
    j.equal("the channel serves a legacy lobby joiner", status, 200)
    goals = sorted(goal_shapes_from(goals_body))
    j.check("a real goal set", len(goals) >= 8, repr(goals[:6]))
    cs = [WsClient(stack.base_url, seed_for(p), tick_period=0.1, rng_seed=p)
          for p in (1, 2, 3, 4)]
    for c in cs:
        c.linger = 25
    # disjoint thirds for the teammates, all posting on the same beats
    thirds = [goals[0:2], goals[2:4], goals[4:6]]
    for c, mine in zip(cs[:3], thirds):
        c.plan = [(4 + n, "complete_goal", (g,)) for n, g in enumerate(mine)]
    cs[3].plan = [(4 + n, "complete_goal", (g,)) for n, g in enumerate(goals[6:8])]
    run_clients(*cs)
    for c in cs:
        j.check("%s: no exceptions" % c.label, not c.errors, "; ".join(c.errors)[:160])
        j.check("%s: every bingo post acked 200" % c.label,
                c.bingoacks and all(s == 200 for s in c.bingoacks), repr(c.bingoacks))
    rr = requests.get(stack.base_url + "/bingo/game/%s/fetch" % gid,
                      params={"first": 1}, timeout=30)
    board = rr.json()
    by_name = {card["name"]: card for card in board["cards"]}
    team_done = set(thirds[0] + thirds[1] + thirds[2])
    lost = [g for g in team_done if 1 not in by_name.get(g, {}).get("completed_by", [])]
    j.check("the team's union survived concurrent posts (no lost updates)",
            not lost, "missing from team 1: %r" % lost)
    rival_lost = [g for g in goals[6:8] if 4 not in by_name.get(g, {}).get("completed_by", [])]
    j.check("the rival's own squares landed", not rival_lost, repr(rival_lost))
    leaked = [g for g in goals[6:8] if 1 in by_name.get(g, {}).get("completed_by", [])
              and g not in team_done]
    j.check("no cross-team leakage", not leaked, repr(leaked))
    return j


def ws_fallback_limit(stack):
    """A full websocket house: late arrivals ride http and lose nothing.
    Runs its own stack so WS_CONN_LIMIT can be pinned low."""
    j = Judge("ws_fallback_limit")
    from mockclient.stack import LocalStack
    with LocalStack(port=8096, env={"WS_CONN_LIMIT": "2"}) as fb:
        fb.reset()
        rolled = Rolled(fb, base_params("mock-fallback", players=4))
        cs = [WsClient(fb.base_url, rolled.seed_text(p), tick_period=0.15, rng_seed=p)
              for p in (1, 2, 3, 4)]
        for c in cs:
            c.linger = 20
            mine = [i for i, p in enumerate(c.seed.pickups) if p["code"] != "MW"][:3]
            theirs = [i for i, p in enumerate(c.seed.pickups) if p["code"] == "MW"][:4]
            c.plan = [(3 + n * 2, "collect", (i,)) for n, i in enumerate(mine + theirs)]
        run_clients(*cs)
        on_http = [c for c in cs if c.went_http]
        j.check("the limit pushed somebody onto http (limit 2, clients 4)",
                len(on_http) >= 2, "on http: %r" % [c.label for c in on_http])
        for c in cs:
            j.check("%s: no exceptions" % c.label, not c.errors, "; ".join(c.errors)[:160])
            j.check("%s: no failed acks" % c.label,
                    all(s < 300 for s in c.acks.values()),
                    repr({k: v for k, v in c.acks.items() if v >= 300}))
        for c in on_http:
            j.check("%s actually played over http" % c.label,
                    any(d == "http" and "tick -> 200" in t for _, d, t in c.events),
                    "no http ticks in the log")
        total_got = sum(len(c.received_items) for c in cs)
        j.check("cross-world delivery crossed the transport line (16 sent)",
                total_got >= 16, "only %d arrived" % total_got)
    return j


ALL = [solo_ws, solo_legacy, mw2, mw_bingo_solo_optin, mw_bingo_two_boards,
       bingo_reroll_flow, mw4_concurrency, shared_bingo_teams, ws_fallback_limit]
