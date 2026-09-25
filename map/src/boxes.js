// BX|flags|x1,y1,x2,y2|color|give (Boxes.txt), give keeping its own pipes, as {type, extra, box, color, give}.
// Imports only pure modules, so plain node can load it (test/box_lines_test.mjs).
import {decompose_pickup, pack_piece} from './multipickup.js';

// the first of these on a line is its type; every other flag rides in extra, in order
const TYPE_FLAGS = ["goal", "kill", "solid", "item", "ritem", "none", "tombstone"]
// what the client knows, by the name before any "="; it matches them case-insensitively
const KNOWN_FLAGS = [...TYPE_FLAGS, "once", "on", "damage", "unsafe", "renderdepth", "parallaxdepth"]
const VALUE_FLAGS = ["on", "damage", "renderdepth", "parallaxdepth"]
// the flags menu, presets first; a line's other type flags (goal, none) load and show but aren't offered
const BOX_PRESETS = {kill: "box kills Ori", item: "grants an item once", solid: "box with collision",
                     ritem: "grants an item repeatedly"}
const BOX_FLAG_SUGGESTIONS = {...BOX_PRESETS, once: "box toggles off when collected", unsafe: "saves disabled inside box",
                              "on=Tick": "grant 60 times a second while inside box", "on=Frame": "grant every frame while inside box",
                              "damage=1": "box damages entities touching it", "renderDepth=-99": "draw box over terrain"}
// a chip's tooltip; value flags build theirs from what is typed, in describe_flag
const FLAG_TEXT = {...BOX_PRESETS, once: BOX_FLAG_SUGGESTIONS.once, unsafe: BOX_FLAG_SUGGESTIONS.unsafe,
                   goal: "ends a practice segment", none: "plain gray"}
const TRIGGER_TEXT = {Enter: "grants when Ori enters the box", Tick: "grants 60 times a second while Ori is inside",
                      Frame: "grants every frame while Ori is inside"}
// the game's DamageType names, which it matches case-insensitively
const DAMAGE_TYPES = ["Acid", "Bash", "Bat", "ChargeFlame", "Crush", "Drowning", "Enemy", "Explosion", "Grenade", "GrenadeSplatter",
                      "Heat", "HitSurface", "Ice", "Laser", "Lava", "LevelUp", "NightBerryDied", "Nova", "Projectile", "SlugSpike",
                      "Spikes", "SpiritFlame", "SpiritFlameSplatter", "Stomp", "StompBlast", "Water"]
// a deleted box keeps its line, so the boxes after it keep the numbers BM|n names
const BOX_TOMBSTONE = "tombstone"
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
    // what the builder wrote for a deleted box before tombstones; with a color it is a plain box
    if(out.type === "none" && !out.extra && !out.color)
        out.type = BOX_TOMBSTONE
    return out
}

function box_line(b) {
    // a pipe would end the flags field
    let flags = split_flags([b.type, b.extra].join(",").replace(/\|/g, "")).join(",")
    let color = (b.color || "").trim()
    // a bare `none` with no color reads back as a deleted box
    if(flags.toLowerCase() === "none" && !color)
        color = BOX_COLORS.none.slice(1)
    let fields = ["BX", flags, b.box.map(v => Math.round(v * 100) / 100).join(","), color, b.give || ""]
    while(fields.length > 3 && !fields[fields.length - 1])
        fields.pop()
    return fields.join("|")
}

const box_flags = (b) => split_flags([b.type, b.extra].join(","))
const box_has_flag = (b, flag) => box_flags(b).some(f => f.toLowerCase() === flag)

// the game lets each type flag set the color in turn, so the last one shows
function box_color(b) {
    let m = HEX_COLOR.exec(b.color || "")
    let preset = box_flags(b).map(f => f.toLowerCase()).filter(f => BOX_COLORS[f]).pop()
    return m ? "#" + m[1].toLowerCase() : (BOX_COLORS[preset] || BOX_COLORS.item)
}

// a comma or pipe would split the line
const box_flag_ok = (flag) => !!flag.trim() && !/[,|]/.test(flag)

const capital = (text) => text.charAt(0).toUpperCase() + text.slice(1)
const one_of = (names, text) => names.find(n => n.toLowerCase() === text.trim().toLowerCase())
const numeric = (text) => text.trim() !== "" && isFinite(Number(text))

// What a flag does, or with warn, why the game won't do what it says. Bad values are the
// game's own parse errors, which it only logs.
function describe_flag(flag) {
    let eq = flag.indexOf("=")
    let name = (eq < 0 ? flag : flag.slice(0, eq)).trim(), value = eq < 0 ? "" : flag.slice(eq + 1).trim()
    let key = name.toLowerCase()
    let bad = (text) => ({text: text, warn: true})
    if(!KNOWN_FLAGS.includes(key))
        return bad("Unknown flag (will be ignored)")
    if(VALUE_FLAGS.includes(key) && !value)
        return bad(`Needs a value: ${name}=...`)
    if(key === "on") {
        let when = one_of(Object.keys(TRIGGER_TEXT), value)
        return when ? {text: capital(TRIGGER_TEXT[when])} : bad("One of: Enter, Tick, Frame")
    }
    if(key === "renderdepth" || key === "parallaxdepth") {
        let [low, high] = key === "renderdepth" ? [-99, 399] : [-19, 4979]
        if(!numeric(value) || Number(value) < low || Number(value) > high)
            return bad(`${name} takes a number from ${low} to ${high}`)
        return {text: key === "renderdepth" ? `Draws the box at depth ${value}; lower is further in front`
                                            : `Box moves as if it was at depth ${value} (lower is nearer)`}
    }
    if(key === "damage") {
        let [amount, type, target, hits, ...rest] = value.split("/")
        if(!numeric(amount))
            return bad(`Damage needs an amount first: ${name}=1`)
        let kind = type === undefined ? "Spikes" : one_of(DAMAGE_TYPES, type)
        if(!kind)
            return bad(`Not a damage type: ${type}`)
        let who = target === undefined ? "All" : one_of(["All", "Player"], target)
        if(!who)
            return bad("Target must be All or Player")
        let box = hits === undefined ? "Extended" : one_of(["Normal", "Extended"], hits)
        if(!box || rest.length)
            return bad("The hitboxes are Normal or Extended")
        return {text: `Does ${amount} ${kind} damage to ${who === "All" ? "anything" : "Ori and grenades"} inside the box` +
                      (box === "Normal" ? ", by normal hitboxes" : "")}
    }
    return {text: FLAG_TEXT[key] ? capital(FLAG_TEXT[key]) : ""}
}

const box_flag_warning = (flag) => describe_flag(flag).warn ? describe_flag(flag).text : ""

// the parts after a value flag's "=", in order, and what the game uses for one left out
const FLAG_PARTS = {
    on: [{names: Object.keys(TRIGGER_TEXT)}],
    damage: [{hint: "amount"}, {names: DAMAGE_TYPES, hint: "damage type", fallback: "Spikes"},
             {names: ["All", "Player"], hint: "target", fallback: "All"},
             {names: ["Normal", "Extended"], hint: "hitboxes", fallback: "Extended"}],
}

// Ways to go on with a value flag being typed: the names its current part can take, those starting
// with what's typed first, then the next part once this one is whole. A pick that more can follow
// fills the text box (fill); one that ends the flag is added as it is.
function flag_completions(text) {
    let eq = text.indexOf("=")
    let parts = eq < 0 ? null : FLAG_PARTS[text.slice(0, eq).trim().toLowerCase()]
    let typed = text.slice(eq + 1).split("/")
    let at = typed.length - 1
    if(!parts || !parts[at])
        return []
    let part = parts[at], partial = typed[at].trim().toLowerCase()
    let head = text.slice(0, text.length - typed[at].length)
    let whole = part.names ? part.names.some(n => n.toLowerCase() === partial) : numeric(typed[at])
    let out = []
    if(part.names && !whole) {
        let hits = [...part.names.filter(n => n.toLowerCase().startsWith(partial)),
                    ...part.names.filter(n => !n.toLowerCase().startsWith(partial) && n.toLowerCase().includes(partial))]
        out = hits.map(n => ({value: head + n, fill: at < parts.length - 1}))
    }
    if(whole && parts[at + 1])
        out.push({value: text + "/", fill: true, next: parts[at + 1]})
    return out
}

// the chip or menu line for a flag; a kill on a box that gives something is overridden, so it warns
function flag_option(flag, give) {
    let {text, warn} = describe_flag(flag)
    if(flag.toLowerCase() === "kill" && give && give !== "NO|1")
        [text, warn] = ["Won't kill Ori (grants an item)", true]
    return {label: flag, value: flag, warn: !!warn, tip: text, desc: BOX_FLAG_SUGGESTIONS[flag], color: BOX_COLORS[flag.toLowerCase()]}
}
const SUGGESTED = Object.keys(BOX_FLAG_SUGGESTIONS).map(flag => flag_option(flag))

// the flags select's chips (type first) and menu: the suggestions plus the box's own flags
function box_flag_choices(type, extra, give) {
    let chips = split_flags([type, extra || ""].join(",")).map(flag => flag_option(flag, give))
    let own = chips.filter(c => !BOX_FLAG_SUGGESTIONS[c.value])
    return {chips: chips, options: own.length ? [...SUGGESTED, ...own] : SUGGESTED}
}

// a chip list back to the model: the first type flag is the type, the rest stay in order
function box_flags_from_chips(flags) {
    let t = flags.findIndex(flag => TYPE_FLAGS.includes(flag.toLowerCase()))
    return {type: t < 0 ? "" : flags[t].toLowerCase(), extra: flags.filter((_, k) => k !== t).join(",")}
}

const MULTI_CODES = ["MU", "RP", "RG"]
// the client keeps box state in these slots by box number: off bits, then contact bits
const BOX_STATE_SLOTS = [[1700, 1999], [2651, 2950]]

// a pickup as pieces, each with the world it runs in; after a BM's box number come slots and values, never boxes
function read_pickup(value, world, owner, where, spawn, box_item, problems) {
    let bar = (value || "").indexOf("|")
    if(bar < 0)
        return null
    let code = value.slice(0, bar), id = value.slice(bar + 1)
    let home = owner && String(owner) !== String(world) ? String(owner) : String(world)
    // seedgen sends an MU piece marked "@n" to world n and keeps the rest with the holder, owner or not
    let by_piece = code === "MU" && id.includes("@") && !box_item
    let pieces = (MULTI_CODES.includes(code) ? decompose_pickup(code, id) : [[code, id]]).map(([c, i]) => {
        let piece = {code: c, id: i, world: by_piece ? String(world) : home}
        let slots = [...i.matchAll(/\{\s*(\d+)\s*\}/g)].map(m => parseInt(m[1], 10))
        if(c === "RI")
            slots.push(parseInt(i, 10))
        slots.filter(n => BOX_STATE_SLOTS.some(([lo, hi]) => n >= lo && n <= hi)).forEach(n =>
            problems.push(`${where}: ${c}|${i} uses slot ${n}, which holds box state by box number`))
        if(c !== "BM")
            return piece
        let at = i.indexOf("@")
        let tag = at < 0 ? "" : i.slice(at)
        if(tag && !(by_piece && /^@\d+$/.test(tag)))
            problems.push(`${where}: BM|${i}: only a piece of a placed MU can name a world`)
        else if(tag)
            piece.world = tag.slice(1)
        let body = at < 0 ? i : i.slice(0, at)
        let eq = body.indexOf("=")
        let num = (eq < 0 ? body : body.slice(0, eq)).trim()
        if(!/^\d+$/.test(num)) {
            problems.push(`${where}: BM|${i} names no box number`)
            return piece
        }
        return {...piece, box: parseInt(num, 10), rest: (eq < 0 ? "" : body.slice(eq)) + tag}
    })
    if(pieces.some(p => p.box !== undefined) && home !== String(world)) {
        if(by_piece)
            problems.push(`${where}: its pieces name worlds and so does its owner`)
        else if(spawn)
            problems.push(`${where}: a spawn item for another player stays home in seedgen but not in the plando seed`)
    }
    return {code: code, multi: MULTI_CODES.includes(code), pieces: pieces, where: where}
}

function write_pickup(value, read, renumber) {
    let changed = false
    let parts = read ? read.pieces.map(p => {
        let n = p.box === undefined ? undefined : (renumber[p.world] || {})[p.box]
        if(n === undefined || n === p.box)
            return [p.code, p.id]
        changed = true
        return [p.code, n + p.rest]
    }) : []
    if(!changed)
        return value
    return read.code + "|" + (read.multi ? parts.map(([c, i]) => pack_piece(c + "|" + i)).join("/") : parts[0][1])
}

// Drops deleted boxes without reordering the rest (same-tick items go in line order) and renumbers BM|n.
// pickups: [{value, world holding it, owner it is for, spawn, where}]; a bad BM is a problem and keeps its tombstone.
function compact_boxes(worlds, pickups) {
    let problems = []
    let reads = pickups.map(p => read_pickup(p.value, p.world, p.owner, p.where, p.spawn, false, problems))
    let gives = {}
    Object.keys(worlds).forEach(w => {
        gives[w] = worlds[w].map((b, k) => is_box_gone(b) ? null : read_pickup(b.give, w, null, `P${w} box #${k}`, false, true, problems))
    })
    let named = {}
    ;[...reads, ...Object.values(gives).flat()].forEach(r => r && r.pieces.forEach(p => {
        if(p.box === undefined)
            return
        let boxes = worlds[p.world] || []
        if(p.box >= boxes.length)
            problems.push(`${r.where}: BM|${p.id}: world ${p.world} has no box ${p.box}`)
        else if(is_box_gone(boxes[p.box])) {
            problems.push(`${r.where}: BM|${p.id} names box ${p.box}, which is deleted`)
            named[p.world + ":" + p.box] = true
        }
    }))
    let renumber = {}, kept = {}
    Object.keys(worlds).forEach(w => {
        renumber[w] = {}
        kept[w] = []
        worlds[w].forEach((b, k) => {
            if(!is_box_gone(b) || named[w + ":" + k]) {
                renumber[w][k] = kept[w].length
                kept[w].push(k)
            }
        })
    })
    let out = {}
    Object.keys(worlds).forEach(w => {
        out[w] = kept[w].map(k => {
            let b = worlds[w][k]
            let give = write_pickup(b.give, gives[w][k], renumber)
            return give === b.give ? b : {...b, give: give}
        })
    })
    return {worlds: out, renumber: renumber, pickups: pickups.map((p, k) => write_pickup(p.value, reads[k], renumber)), problems: problems}
}

export {
    BOX_PRESETS, BOX_COLORS, BOX_TOMBSTONE, is_box_gone, box_hidden, new_box, box_has_flag, box_flags_from_chips,
    parse_box_line, box_line, box_color, box_flag_ok, box_flag_warning, describe_flag, flag_completions, box_flag_choices, BOXES_TXT,
    compact_boxes
};
