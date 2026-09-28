// The plando builder's box line helpers (map/src/boxes.js). Run from the repo root: node test/box_lines_test.mjs
import test from "node:test"
import assert from "node:assert/strict"
import {parse_box_line, box_line, is_box_gone, box_hidden, box_color, box_flag_ok, box_flag_warning, box_flag_choices,
    box_flags_from_chips, box_has_flag, describe_flag, flag_completions, flag_menu, new_box, BOX_COLORS, compact_boxes} from "../map/src/boxes.js"

const model = (b) => ({flags: b.flags, box: b.box, color: b.color, give: b.give})
const parsed = (line) => model(parse_box_line(line))
const rewrite = (line) => box_line(parse_box_line(line))

// Boxes.txt's examples, verbatim
const EXAMPLES = [
    "BX|kill|213,-242.7,221,-202.7",
    "BX|ritem|170,-240,175,-230||SH|jump here",
    "BX|solid,renderDepth=-99|190,-258.5,217,-258|ff6b6b",
    "BX|damage=1,solid|158.9,-220.4,164.9,-212.4",
    "BX|once,damage=36/Drowning/Player|185,-206,195,-204|00a2e8|SK|0",
    "BX|damage=1000/LevelUp,renderDepth=399|135,-220,136,-196|ffffffff",
    "BX|unsafe|400,-15,640,1000|none",
]

test("every Boxes.txt example round-trips", () => {
    for(let line of EXAMPLES) {
        let b = parse_box_line(line)
        assert.ok(b && !is_box_gone(b), line)
        assert.deepEqual(parsed(box_line(b)), model(b), line)
        assert.equal(box_line(b), line)
    }
})

test("the model keeps every field as written", () => {
    assert.deepEqual(parsed(EXAMPLES[1]), {flags: "ritem", box: [170, -240, 175, -230], color: "", give: "SH|jump here"})
    assert.deepEqual(parsed(EXAMPLES[2]), {flags: "solid,renderDepth=-99", box: [190, -258.5, 217, -258], color: "ff6b6b", give: ""})
    assert.deepEqual(parsed(EXAMPLES[4]), {flags: "once,damage=36/Drowning/Player", box: [185, -206, 195, -204], color: "00a2e8", give: "SK|0"})
    assert.deepEqual(parsed(EXAMPLES[6]), {flags: "unsafe", box: [400, -15, 640, 1000], color: "none", give: ""})
    assert.deepEqual(parsed("BX|ritem|1,2,3,4||SH|a|b"), {flags: "ritem", box: [1, 2, 3, 4], color: "", give: "SH|a|b"})
    assert.deepEqual(parsed("BX||1,2,3,4|ff0000"), {flags: "", box: [1, 2, 3, 4], color: "ff0000", give: ""})
})

test("flags keep their order, case and spacing, however many presets a box has", () => {
    for(let line of ["BX|once,kill,solid|1,2,3,4", "BX|solid,kill|1,2,3,4", "BX|damage=1,solid,item|1,2,3,4||SK|0",
                     "BX|once, KILL ,unsafe,item|1,2,3,4", "BX|Ritem|1,2,3,4"])
        assert.equal(rewrite(line), line)
    let b = parse_box_line("BX|once,kill,solid|1,2,3,4")
    assert.deepEqual(box_flag_choices(b.flags).chips.map(c => c.value), ["once", "kill", "solid"])
    assert.ok(box_has_flag(b, "once") && box_has_flag(b, "kill") && box_has_flag(b, "solid"))
    assert.ok(box_has_flag(parse_box_line("BX|Ritem|1,2,3,4"), "ritem"))
})

test("editing the chips writes the flags in chip order", () => {
    let b = parse_box_line("BX|solid,damage=1|1,2,3,4")
    assert.equal(box_line({...b, ...box_flags_from_chips(["damage=1", "item", "solid"])}), "BX|damage=1,item,solid|1,2,3,4")
    assert.equal(box_line({...b, ...box_flags_from_chips([])}), "BX||1,2,3,4")
})

test("give is written whenever present, whatever the flags", () => {
    for(let line of ["BX|kill|1,2,3,4||SK|0", "BX|solid|1,2,3,4|ff0000|EX|15", "BX|none|1,2,3,4|808080|SH|hi"])
        assert.equal(rewrite(line), line)
})

test("tombstones", () => {
    for(let line of ["BX|tombstone|1,2,3,4", "BX|none|1,2,3,4", "BX|none|1,2,3,4|", "BX|none|1,2,3,4||", "BX| NONE |1,2,3,4"]) {
        let b = parse_box_line(line)
        assert.ok(is_box_gone(b), line)
        assert.equal(box_line(b), "BX|tombstone|1,2,3,4", line)
    }
    for(let line of ["BX|none|1,2,3,4|808080", "BX|none|1,2,3,4|none", "BX|none,unsafe|1,2,3,4", "BX|none,none|1,2,3,4"]) {
        let b = parse_box_line(line)
        assert.ok(!is_box_gone(b), line)
        assert.equal(box_line(b), line)
    }
})

test("a tombstone flag anywhere deletes the box, as in game", () => {
    for(let line of ["BX|kill,tombstone|1,2,3,4", "BX|once,TombStone,solid|1,2,3,4", "BX|tombstone,kill|1,2,3,4||SK|0"]) {
        let b = parse_box_line(line)
        assert.ok(is_box_gone(b), line)
        assert.ok(is_box_gone(parse_box_line(box_line(b))), line)
        assert.equal(box_line(b), line)
    }
})

test("a bare none that gives something is a plain box", () => {
    let b = parse_box_line("BX|none|1,2,3,4||SK|0")
    assert.ok(!is_box_gone(b))
    assert.deepEqual(model(b), {flags: "none", box: [1, 2, 3, 4], color: "", give: "SK|0"})
    assert.equal(box_line(b), "BX|none|1,2,3,4||SK|0")
    // with the give gone, it takes a color so it isn't read back as deleted
    assert.equal(box_line({...b, give: ""}), "BX|none|1,2,3,4|808080")
})

test("a plain box never writes as a tombstone", () => {
    for(let flags of ["none", " NONE ", "none,"]) {
        let line = box_line(new_box(flags, [1, 2, 3, 4]))
        assert.ok(line.endsWith("|808080"), flags)
        assert.ok(!is_box_gone(parse_box_line(line)), flags)
    }
})

test("color 0 is none", () => {
    let b = parse_box_line("BX|kill|1,2,3,4|0")
    assert.ok(box_hidden(b) && !is_box_gone(b))
    assert.equal(box_color(b), BOX_COLORS.kill)
    assert.equal(box_line(b), "BX|kill|1,2,3,4|0")
    assert.ok(box_hidden(parse_box_line("BX|kill|1,2,3,4|none")))
    assert.equal(box_color(parse_box_line("BX|solid|1,2,3,4|FF6B6B80")), "#ff6b6b")
    assert.equal(box_color(parse_box_line("BX||1,2,3,4")), BOX_COLORS.item)
})

test("the last preset flag picks the default color, as in game", () => {
    assert.equal(box_color(parse_box_line("BX|solid,kill|1,2,3,4")), BOX_COLORS.kill)
    assert.equal(box_color(parse_box_line("BX|kill,once,Solid|1,2,3,4")), BOX_COLORS.solid)
    assert.equal(box_color(parse_box_line("BX|damage=1,unsafe|1,2,3,4")), BOX_COLORS.item)
})

test("writing rounds corners and keeps the flags field whole", () => {
    assert.equal(box_line(new_box("kill,once|,unsafe", [1.044, 2.056, -3.001, 4])), "BX|kill,once,unsafe|1.04,2.06,-3,4")
})

test("malformed lines are skipped", () => {
    for(let line of ["BX|kill|1,2,3", "XX|kill|1,2,3,4", "BX|kill|a,b,c,d", "BX|kill"])
        assert.equal(parse_box_line(line), null, line)
})

test("a flag chip with a comma or pipe is refused", () => {
    for(let flag of ["once", "damage=36/Drowning/Player", "parallaxDepth=40", "foo"])
        assert.ok(box_flag_ok(flag), flag)
    for(let flag of ["once,unsafe", "SK|0", "", "  "])
        assert.ok(!box_flag_ok(flag), flag)
})

test("unknown names and value flags without a value warn, the rest in any case do not", () => {
    for(let flag of ["once", "Damage=1", "renderDepth=3", "ON=Tick", "parallaxdepth=4", "kill", "tombstone"])
        assert.equal(box_flag_warning(flag), "", flag)
    for(let flag of ["foo", "bar=2", "damage", "damage=", "renderDepth", "parallaxDepth= ", "on"])
        assert.ok(box_flag_warning(flag), flag)
})

test("chips are the flags as written; the menu offers presets first, then suggestions and the box's own flags", () => {
    let {chips, options} = box_flag_choices("solid,foo,once,kill")
    assert.deepEqual(chips.map(c => c.value), ["solid", "foo", "once", "kill"])
    assert.ok(!chips[0].warn && chips[1].warn && !chips[2].warn && !chips[3].warn)
    assert.equal(chips[0].color, BOX_COLORS.solid)
    assert.equal(chips[2].color, undefined)
    let offered = options.map(o => o.value)
    assert.deepEqual(offered.slice(0, 4), ["kill", "item", "solid", "ritem"])
    assert.ok(offered.includes("unsafe") && offered.includes("foo") && !offered.includes("none") && !offered.includes("goal"))
    assert.equal(offered.filter(v => v === "once").length, 1)
    assert.ok(options.every(o => o.value === "foo" || o.desc))
    assert.deepEqual(box_flag_choices("").chips, [])
})

test("a flag describes itself from its values, and warns where the game would log a parse error", () => {
    assert.equal(describe_flag("damage=36/Drowning/Player").text, "Does 36 Drowning damage to Ori and grenades inside the box")
    assert.equal(describe_flag("DAMAGE=5/lava/all/normal").text, "Does 5 Lava damage to anything inside the box, by normal hitboxes")
    assert.equal(describe_flag("damage=1").text, "Does 1 Spikes damage to anything inside the box")
    assert.ok(describe_flag("On=tick").text && !describe_flag("On=tick").warn)
    for(let flag of ["damage=x", "damage=1/Foo", "damage=1/Spikes/Enemies", "damage=1/Spikes/All/Big", "damage=1/Spikes/All/Normal/x",
                     "on=Update", "renderDepth=400", "renderDepth=deep", "parallaxDepth=-20", "foo", "damage"])
        assert.ok(describe_flag(flag).warn, flag)
    for(let flag of ["kill", "once", "unsafe", "renderDepth=-99", "parallaxDepth=4979"])
        assert.ok(describe_flag(flag).text && !describe_flag(flag).warn, flag)
})

test("numbers are plain decimals, as the game reads them", () => {
    for(let flag of ["renderDepth=1e2", "renderDepth=0x10", "renderDepth=.", "renderDepth=-", "renderDepth=1.2.3", "damage=1e2",
                     "damage=0x10/Lava", "damage=Infinity"])
        assert.ok(describe_flag(flag).warn, flag)
    for(let flag of ["renderDepth=-5", "renderDepth=+5", "renderDepth=.5", "renderDepth=5.", "renderDepth=-0.25", "damage=1.5",
                     "damage= 2 /Lava"])
        assert.ok(!describe_flag(flag).warn, flag)
    assert.deepEqual(flag_completions("damage=1e2").map(c => c.value), [])
})

test("a value flag being typed offers its names, then its next part", () => {
    let values = (text) => flag_completions(text).map(c => c.value)
    assert.deepEqual(values("on="), ["on=Enter", "on=Tick", "on=Frame"])
    assert.deepEqual(values("ON=t"), ["ON=Tick", "ON=Enter"])
    assert.deepEqual(flag_completions("on=T").map(c => c.fill), [false, false])
    assert.deepEqual(values("on=Tick"), [])
    assert.deepEqual(values("damage=1"), ["damage=1/"])
    assert.equal(flag_completions("damage=1")[0].next.hint, "damage type")
    assert.equal(values("damage=1/").length, 26)
    assert.deepEqual(values("damage=1/").slice(0, 3), ["damage=1/Acid", "damage=1/Bash", "damage=1/Bat"])
    assert.deepEqual(values("damage=1/s").slice(0, 6), ["damage=1/SlugSpike", "damage=1/Spikes", "damage=1/SpiritFlame",
                                                        "damage=1/SpiritFlameSplatter", "damage=1/Stomp", "damage=1/StompBlast"])
    assert.equal(values("damage=1/s").length, 12)
    assert.deepEqual(values("damage=1/pik"), ["damage=1/SlugSpike", "damage=1/Spikes"])
    assert.ok(flag_completions("damage=1/pik")[0].fill)
    assert.deepEqual(values("damage=1/lava"), ["damage=1/lava/"])
    assert.deepEqual(values("damage=1/Grenade"), ["damage=1/GrenadeSplatter", "damage=1/Grenade/"])
    assert.deepEqual(values("damage=1/spiritflame"), ["damage=1/SpiritFlameSplatter", "damage=1/spiritflame/"])
    assert.deepEqual(values("damage=1/Stomp"), ["damage=1/StompBlast", "damage=1/Stomp/"])
    assert.ok(flag_completions("damage=1/Stomp")[0].fill)
    assert.deepEqual(values("damage=1/Lava/p"), ["damage=1/Lava/Player"])
    assert.deepEqual(values("damage=1/Lava/All/"), ["damage=1/Lava/All/Normal", "damage=1/Lava/All/Extended"])
    assert.deepEqual(flag_completions("damage=1/Lava/All/n").map(c => c.fill), [false, false])
    for(let text of ["damage=x", "damage=1/Lava/All/Normal", "damage=1/Lava/All/Normal/", "once", "renderDepth=5", "foo="])
        assert.deepEqual(values(text), [], text)
})

test("an empty part without names offers its hint, which the menu line shows", () => {
    for(let [text, hint] of [["renderDepth=", "-99 to 399"], ["PARALLAXDEPTH=", "-19 to 4979"], ["damage=", "amount"]]) {
        let c = flag_completions(text)
        assert.deepEqual(c.map(x => [x.value, x.fill, x.next.hint]), [[text, true, hint]], text)
    }
    assert.deepEqual(flag_completions("parallaxDepth=40"), [])
    let {options} = box_flag_choices("")
    let menu = flag_menu(options, flag_completions("renderDepth=").map(c => ({value: c.value, completion: true})), false)
    assert.equal(menu[0].value, "renderDepth=")
})

test("the menu offers both depth flags", () => {
    let offered = box_flag_choices("").options
    assert.ok(offered.some(o => o.value === "parallaxDepth=10" && o.desc && !o.warn))
    assert.ok(offered.some(o => o.value === "renderDepth=-99" && !o.warn))
})

test("a completion the menu already has stands in its place, once", () => {
    let {options} = box_flag_choices("")
    let menu = (text) => flag_menu(options, flag_completions(text).map(c => ({value: c.value, completion: true})), !describe_flag(text).warn)
    let values = (text) => menu(text).map(o => o.value)
    assert.deepEqual(values("on=T").slice(0, 2), ["on=Tick", "on=Enter"])
    assert.deepEqual(values("ON=t").slice(0, 2), ["on=Tick", "ON=Enter"])
    assert.equal(values("on=T").filter(v => v === "on=Tick").length, 1)
    assert.equal(values("on=T").length, options.length + 1)
    let tick = menu("on=T")[0]
    assert.equal(tick.desc, options.find(o => o.value === "on=Tick").desc)
    assert.ok(tick.completion)
    // whole as typed, the usual lines stay first
    assert.deepEqual(values("damage=1"), [...options.map(o => o.value), "damage=1/"])
    assert.equal(menu("once"), options)
    assert.equal(menu("foo"), options)
})

test("a kill anywhere on a box that gives something warns; an empty give does not", () => {
    assert.ok(box_flag_choices("kill", "SK|0").chips[0].warn)
    assert.ok(box_flag_choices("once,solid,Kill", "SK|0").chips[2].warn)
    assert.ok(!box_flag_choices("kill", "").chips[0].warn && !box_flag_choices("kill", "NO|1").chips[0].warn)
    assert.ok(!box_flag_choices("solid,once", "SK|0").chips.some(c => c.warn))
})

test("chips back to the model: joined in order, as typed", () => {
    assert.deepEqual(box_flags_from_chips(["once", "Kill", "solid"]), {flags: "once,Kill,solid"})
    assert.deepEqual(box_flags_from_chips([]), {flags: ""})
    let b = {...new_box("", [1, 2, 3, 4]), ...box_flags_from_chips(["solid", "kill"])}
    assert.equal(box_line(b), "BX|solid,kill|1,2,3,4")
    assert.ok(box_has_flag(b, "kill") && box_has_flag(b, "solid") && !box_has_flag(b, "item"))
})

const world = (...lines) => lines.map(parse_box_line)
const lines_of = (out) => Object.fromEntries(Object.entries(out.worlds).map(([w, bs]) => [w, bs.map(box_line)]))
const here = (value, extra) => ({value: value, world: "1", where: value, ...extra})

// 0 kill, 1 hole, 2 solid, 3 hole, 4 item naming box 2, 5 and 6 holes at the end
const HOLEY = () => ({1: world("BX|kill|0,0,1,1", "BX|tombstone|1,0,2,1", "BX|solid|2,0,3,1", "BX|tombstone|3,0,4,1",
                           "BX|item|4,0,5,1||BM|2=1", "BX|tombstone|5,0,6,1", "BX|tombstone|6,0,7,1")})

test("compacting drops holes in the middle and at the end and renumbers before, between and after them", () => {
    let out = compact_boxes(HOLEY(), [here("BM|0"), here("BM|2=0"), here("BM|4"), here("SK|0")])
    assert.deepEqual(out.problems, [])
    assert.deepEqual(lines_of(out), {1: ["BX|kill|0,0,1,1", "BX|solid|2,0,3,1", "BX|item|4,0,5,1||BM|1=1"]})
    assert.deepEqual(out.renumber, {1: {0: 0, 2: 1, 4: 2}})
    assert.deepEqual(out.pickups, ["BM|0", "BM|1=0", "BM|2", "SK|0"])
})

test("multipickup pieces are renumbered and repacked with their escapes", () => {
    let out = compact_boxes(HOLEY(), [here("MU|SK/0/BM/4=1/EX/15"), here("RP|BM/2/SH/a//b"), here("RG|EX/1/BM/0")])
    assert.deepEqual(out.problems, [])
    assert.deepEqual(out.pickups, ["MU|SK/0/BM/2=1/EX/15", "RP|BM/1/SH/a//b", "RG|EX/1/BM/0"])
})

test("only the box number moves: {slot} and comparisons after = are slots", () => {
    let out = compact_boxes(HOLEY(), [here("BM|4={8000}"), here("BM|2=({8000} >= 3)"), here("MU|BM/4={8000}/RI/8000+=1")])
    assert.deepEqual(out.pickups, ["BM|2={8000}", "BM|1=({8000} >= 3)", "MU|BM/2={8000}/RI/8000+=1"])
})

test("a reference to a deleted box or past the end is a problem, and that tombstone stays", () => {
    let out = compact_boxes(HOLEY(), [here("BM|1", {where: "A"}), here("BM|9", {where: "B"}), here("BM|4")])
    assert.equal(out.problems.length, 2)
    assert.ok(out.problems[0].startsWith("A: ") && out.problems[1].startsWith("B: "))
    assert.deepEqual(lines_of(out)[1], ["BX|kill|0,0,1,1", "BX|tombstone|1,0,2,1", "BX|solid|2,0,3,1", "BX|item|4,0,5,1||BM|2=1"])
    assert.deepEqual(out.pickups, ["BM|1", "BM|9", "BM|3"])
})

test("a pickup runs in its owner's world, and an MU piece in the world its @ names", () => {
    let worlds = {1: world("BX|tombstone|0,0,1,1", "BX|kill|1,0,2,1"), 2: world("BX|kill|0,0,1,1", "BX|tombstone|1,0,2,1", "BX|kill|2,0,3,1")}
    let out = compact_boxes(worlds, [here("BM|1"), here("BM|2", {owner: "2"}), here("BM|1", {owner: "1"}),
                                     here("MU|BM/2@2/BM/1"), {value: "BM|2", world: "2", where: "P2"}])
    assert.deepEqual(out.problems, [])
    assert.deepEqual(out.pickups, ["BM|0", "BM|1", "BM|0", "MU|BM/1@2/BM/0", "BM|1"])
})

test("owners it can't settle are problems", () => {
    let worlds = {1: world("BX|tombstone|0,0,1,1", "BX|kill|1,0,2,1"), 2: world("BX|kill|0,0,1,1")}
    for(let pickup of [here("MU|BM/0@2/SK/0", {owner: "2"}), here("BM|0", {owner: "2", spawn: true}), here("BM|1@2"),
                       here("RP|BM/1@2/SK/0"), here("BM|x=1")])
        assert.equal(compact_boxes(worlds, [pickup]).problems.length, 1, pickup.value)
    assert.deepEqual(compact_boxes(worlds, [here("BM|1", {spawn: true})]).problems, [])
})

test("box state read or written by slot is a problem", () => {
    for(let value of ["RI|1700=0", "SH|{2700}", "BM|0={1999}", "MU|EX/1/RI/2999+=1"])
        assert.equal(compact_boxes(HOLEY(), [here(value)]).problems.length, 1, value)
    assert.deepEqual(compact_boxes(HOLEY(), [here("RI|8000=1"), here("SH|{2000}"), here("SH|{2651}")]).problems, [])
})

test("compacting twice changes nothing the second time", () => {
    let first = compact_boxes(HOLEY(), [here("BM|4"), here("MU|BM/2/SK/0")])
    let second = compact_boxes(first.worlds, first.pickups.map(v => here(v)))
    assert.deepEqual(second.problems, [])
    assert.deepEqual(lines_of(second), lines_of(first))
    assert.deepEqual(second.pickups, first.pickups)
    assert.deepEqual(second.renumber, {1: {0: 0, 1: 1, 2: 2}})
})
