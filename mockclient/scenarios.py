"""The scenarios. Each takes a LocalStack, returns a Judge."""
import json

import requests

from mockclient.client import LegacyClient, WsClient
from mockclient.scenario import Judge, Rolled, base_params, run_clients


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
    j.check("world 1's seed carries a Goals line", c1.seed.goals_line is not None,
            "last lines: %r" % s1.strip().split("\n")[-2:])
    j.check("world 2's seed has NO bingo flag", not c2.seed.bingo,
            "flags: %r" % c2.seed.flags)
    board = rolled.fetch_board()
    j.check("board payload has per-world boards", "boards" in board,
            "keys: %r" % sorted(board.keys()))
    worlds = sorted((board.get("boards") or {}).keys())
    j.equal("exactly world 1 has a board", worlds, ["1"])
    goals = c1.seed.goal_names()
    j.check("goals line names the board's cards", len(goals) >= 5, "parsed: %r" % goals[:8])
    done = goals[:3]
    c1.plan = [(3 + i, "complete_goal", (g,)) for i, g in enumerate(done)]
    _collect_plan(c2, 4)
    run_clients(c1, c2)
    j.check("bingo posts acked", c1.bingoacks and all(s == 200 for s in c1.bingoacks),
            repr(c1.bingoacks))
    after = rolled.fetch_board()
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
    j.check("both seeds carry Goals lines",
            c1.seed.goals_line is not None and c2.seed.goals_line is not None)
    board = rolled.fetch_board()
    worlds = sorted((board.get("boards") or {}).keys())
    j.equal("a board per world", worlds, ["1", "2"])
    b1 = [c.get("name") for c in board["boards"]["1"]["cards"]]
    b2 = [c.get("name") for c in board["boards"]["2"]["cards"]]
    j.check("the two boards differ", b1 != b2, "identical card list")
    j.equal("world 1 goals line matches world 1's board",
            sorted(c1.seed.goal_names()), sorted(set(b1)))
    j.equal("world 2 goals line matches world 2's board",
            sorted(c2.seed.goal_names()), sorted(set(b2)))
    done1 = c1.seed.goal_names()[:3]
    c1.plan = [(3 + i, "complete_goal", (g,)) for i, g in enumerate(done1)]
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


ALL = [solo_ws, solo_legacy, mw2, mw_bingo_solo_optin, mw_bingo_two_boards]
