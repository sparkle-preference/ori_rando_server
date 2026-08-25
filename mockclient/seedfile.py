"""Parse a downloaded seed the way Randomizer.initialize does."""


class SeedFile(object):
    def __init__(self, text):
        self.lines = [l for l in text.replace("\r\n", "\n").split("\n") if l.strip()]
        flags_part = self.lines[0].split("|")[0]
        self.flags = [f.strip() for f in flags_part.split(",")]
        lower = [f.lower() for f in self.flags]
        self.sync_id = next((f[4:] for f in lower if f.startswith("sync")), None)
        self.bingo = "bingo" in lower
        # BingoController.Init eats the last line, then pickups parse without it
        self.goals_line = None
        body = self.lines[1:]
        if self.bingo and body and body[-1].startswith("Goals"):
            self.goals_line = body[-1]
            body = body[:-1]
        self.pickups = []
        for line in body:
            if line.startswith("//"):
                continue
            parts = line.split("|")
            if len(parts) < 4:
                continue
            loc, code = parts[0], parts[1]
            id_, zone = "|".join(parts[2:-1]), parts[-1]
            self.pickups.append({"loc": loc, "code": code, "id": id_, "zone": zone})

    @property
    def game_id(self):
        return int(self.sync_id.split(".")[0]) if self.sync_id else None

    @property
    def player_id(self):
        return int(self.sync_id.split(".")[1]) if self.sync_id else None

    def goal_shapes(self):
        return goal_shapes_from(self.goals_line)

    def goal_names(self):
        return sorted(self.goal_shapes())


def goal_shapes_from(line):
    """{card name: (kind, subs, target)} as BingoController builds them, from a
    "Goals..." line -- the ws goals: frame body, or the legacy baked seed line.
    Singles are bool cards, a numeric -suffix makes one an int card with that
    target, and a lone COUNT subgoal marks a counted card; the rest are
    multi cards whose subs are reported nested."""
    out = {}
    if not line:
        return out
    for g in line[len("Goals"):].split("/"):
        name, _, subs = g.partition(":")
        sublist = [s for s in subs.split(",") if s]
        if name == "":
            for s in sublist:
                base, dash, tgt = s.rpartition("-")
                if dash and tgt.isdigit():
                    out[base] = ("int", [], int(tgt))
                else:
                    out[s] = ("bool", [], None)
        elif sublist == ["COUNT"]:
            out[name] = ("multi", [], None)
        else:
            out[name] = ("multi", sublist, None)
    return out
