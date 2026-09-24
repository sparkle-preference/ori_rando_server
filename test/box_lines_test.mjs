// The plando builder's box line helpers (map/src/boxes.js). Run from the repo root: node test/box_lines_test.mjs
import test from "node:test"
import assert from "node:assert/strict"
import {parse_box_line, box_line, is_box_gone, box_hidden, box_color, unknown_box_flags, new_box, BOX_COLORS}
    from "../map/src/boxes.js"

const model = (b) => ({type: b.type, extra: b.extra, box: b.box, color: b.color, give: b.give})
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
        // the type flag is written first; only a line that had another flag before it changes
        let expected = line === EXAMPLES[3] ? "BX|solid,damage=1|158.9,-220.4,164.9,-212.4" : line
        assert.equal(box_line(b), expected)
    }
})

test("the model splits type from extra and keeps fields as written", () => {
    assert.deepEqual(parsed(EXAMPLES[1]), {type: "ritem", extra: "", box: [170, -240, 175, -230], color: "", give: "SH|jump here"})
    assert.deepEqual(parsed(EXAMPLES[2]), {type: "solid", extra: "renderDepth=-99", box: [190, -258.5, 217, -258], color: "ff6b6b", give: ""})
    assert.deepEqual(parsed(EXAMPLES[4]), {type: "", extra: "once,damage=36/Drowning/Player", box: [185, -206, 195, -204], color: "00a2e8", give: "SK|0"})
    assert.deepEqual(parsed(EXAMPLES[6]), {type: "", extra: "unsafe", box: [400, -15, 640, 1000], color: "none", give: ""})
    assert.deepEqual(parsed("BX|ritem|1,2,3,4||SH|a|b"), {type: "ritem", extra: "", box: [1, 2, 3, 4], color: "", give: "SH|a|b"})
    assert.deepEqual(parsed("BX||1,2,3,4|ff0000"), {type: "", extra: "", box: [1, 2, 3, 4], color: "ff0000", give: ""})
})

test("the order rule: the first type flag is the type, the rest keep their order", () => {
    assert.deepEqual(parsed("BX|solid,kill|1,2,3,4"), {type: "solid", extra: "kill", box: [1, 2, 3, 4], color: "", give: ""})
    assert.equal(rewrite("BX|solid,kill|1,2,3,4"), "BX|solid,kill|1,2,3,4")
    assert.equal(rewrite("BX|once, KILL ,unsafe,item|1,2,3,4"), "BX|kill,once,unsafe,item|1,2,3,4")
    assert.equal(parse_box_line("BX|Ritem|1,2,3,4").type, "ritem")
})

test("changing the type keeps extra", () => {
    let b = parse_box_line("BX|solid,damage=1|1,2,3,4")
    assert.equal(box_line({...b, type: "item"}), "BX|item,damage=1|1,2,3,4")
    assert.equal(box_line({...b, type: ""}), "BX|damage=1|1,2,3,4")
})

test("give is written whenever present, for any type", () => {
    for(let line of ["BX|kill|1,2,3,4||SK|0", "BX|solid|1,2,3,4|ff0000|EX|15", "BX|none|1,2,3,4|808080|SH|hi"])
        assert.equal(rewrite(line), line)
})

test("tombstones", () => {
    for(let line of ["BX|tombstone|1,2,3,4", "BX|none|1,2,3,4", "BX|none|1,2,3,4|", "BX| NONE |1,2,3,4"]) {
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

test("a plain box never writes as a tombstone", () => {
    let plain = {...new_box("none", [1, 2, 3, 4])}
    assert.equal(box_line(plain), "BX|none|1,2,3,4|808080")
    assert.ok(!is_box_gone(parse_box_line(box_line(plain))))
    assert.ok(!is_box_gone(parse_box_line(box_line({...new_box("", [1, 2, 3, 4]), extra: "none"}))))
})

test("colour 0 is none", () => {
    let b = parse_box_line("BX|kill|1,2,3,4|0")
    assert.ok(box_hidden(b) && !is_box_gone(b))
    assert.equal(box_color(b), BOX_COLORS.kill)
    assert.equal(box_line(b), "BX|kill|1,2,3,4|0")
    assert.ok(box_hidden(parse_box_line("BX|kill|1,2,3,4|none")))
    assert.equal(box_color(parse_box_line("BX|solid|1,2,3,4|FF6B6B80")), "#ff6b6b")
    assert.equal(box_color(parse_box_line("BX||1,2,3,4")), BOX_COLORS.item)
})

test("writing rounds corners and keeps the flags field whole", () => {
    let b = {...new_box("kill", [1.04, 2.06, -3.01, 4]), extra: " once, | unsafe ,"}
    assert.equal(box_line(b), "BX|kill,once,unsafe|1,2.1,-3,4")
})

test("malformed lines are skipped", () => {
    for(let line of ["BX|kill|1,2,3", "XX|kill|1,2,3,4", "BX|kill|a,b,c,d", "BX|kill"])
        assert.equal(parse_box_line(line), null, line)
})

test("unknown flag names are reported, known ones in any case are not", () => {
    assert.deepEqual(unknown_box_flags("once, Damage=1, foo=2,bar,renderDepth=3,ON=Tick,parallaxdepth=4"), ["foo", "bar"])
    assert.deepEqual(unknown_box_flags(""), [])
})
