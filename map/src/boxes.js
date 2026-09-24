// BX|flags|x1,y1,x2,y2|color|give (Boxes.txt), give keeping its own pipes, as {type, extra, box, color, give}.
// No imports, so plain node can load it (test/box_lines_test.mjs).

// the first of these on a line is its type; every other flag rides in extra, in order
const TYPE_FLAGS = ["goal", "kill", "solid", "item", "ritem", "none", "tombstone"]
// what the client knows, by the name before any "="; it matches them case-insensitively
const KNOWN_FLAGS = [...TYPE_FLAGS, "once", "on", "damage", "unsafe", "renderdepth", "parallaxdepth"]
// a deleted box keeps its line, so the boxes after it keep the numbers BM|n names
const BOX_TOMBSTONE = "tombstone"
const BOX_TYPES = [
    {label: "Kill", value: "kill"},
    {label: "Item", value: "item"},
    {label: "Repeat item", value: "ritem"},
    {label: "Solid", value: "solid"},
    {label: "Plain", value: "none"},
    {label: "(no type)", value: ""},
]
// goal is shown but not offered: it only does anything in practice mode
const BOX_TYPE_OPTION = {goal: {label: "Goal", value: "goal"}}
BOX_TYPES.forEach(t => { BOX_TYPE_OPTION[t.value] = t })
const BOX_COLORS = {goal: "#8fe3a0", kill: "#ff6b6b", solid: "#9aa0aa", item: "#40c0ff", ritem: "#7fd8ff", none: "#808080"}
const BOXES_TXT = "https://github.com/sparkle-preference/OriDERandomizer/blob/4.3/Boxes.txt"
const HEX_COLOR = /^#?([0-9a-f]{6})([0-9a-f]{2})?$/i

const split_flags = (text) => text.split(",").map(f => f.trim()).filter(f => f)
const is_box_gone = (b) => b.type === BOX_TOMBSTONE
const box_hidden = (b) => b.color === "none" || b.color === "0"
let next_box_id = 1
const new_box = (type, box) => ({_id: next_box_id++, type: type, extra: "", box: box, color: "", give: "", locked: false})

function parse_box_line(line) {
    let f = line.trim().split("|")
    if(f[0] !== "BX" || f.length < 3)
        return null
    let box = f[2].split(",").map(parseFloat)
    if(box.length !== 4 || box.some(isNaN))
        return null
    let flags = split_flags(f[1])
    let t = flags.findIndex(flag => TYPE_FLAGS.includes(flag.toLowerCase()))
    let out = new_box(t < 0 ? "" : flags[t].toLowerCase(), box)
    out.extra = flags.filter((_, k) => k !== t).join(",")
    out.color = (f[3] || "").trim()
    out.give = f.slice(4).join("|")
    // what the builder wrote for a deleted box before tombstones; with a colour it is a plain box
    if(out.type === "none" && !out.extra && !out.color)
        out.type = BOX_TOMBSTONE
    return out
}

function box_line(b) {
    // a pipe would end the flags field
    let flags = split_flags([b.type, b.extra].join(",").replace(/\|/g, "")).join(",")
    let color = (b.color || "").trim()
    // a bare `none` with no colour reads back as a deleted box
    if(flags.toLowerCase() === "none" && !color)
        color = BOX_COLORS.none.slice(1)
    let fields = ["BX", flags, b.box.map(v => Math.round(v * 10) / 10).join(","), color, b.give || ""]
    while(fields.length > 3 && !fields[fields.length - 1])
        fields.pop()
    return fields.join("|")
}

function box_color(b) {
    let m = HEX_COLOR.exec(b.color || "")
    return m ? "#" + m[1].toLowerCase() : (BOX_COLORS[b.type] || BOX_COLORS.item)
}

const unknown_box_flags = (extra) => split_flags(extra || "").map(f => f.split("=")[0].trim())
    .filter(name => !KNOWN_FLAGS.includes(name.toLowerCase()))

export {
    BOX_TYPES, BOX_TYPE_OPTION, BOX_COLORS, BOX_TOMBSTONE, is_box_gone, box_hidden, new_box,
    parse_box_line, box_line, box_color, unknown_box_flags, BOXES_TXT
};
