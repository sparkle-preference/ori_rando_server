// BX|flags|shape|color|give (Boxes.txt), give keeping its own pipes, as {flags, box, shape, color, give}.
// Imports only pure modules, so plain node can load it (test/box_lines_test.mjs).
import {decompose_pickup, pack_piece} from './multipickup.js';

// what the client knows, by the name before any "="; it matches them case-insensitively
const KNOWN_FLAGS = ["goal", "kill", "solid", "item", "ritem", "tombstone", "once", "on", "damage", "unsafe",
                     "unlit", "renderdepth", "parallaxdepth"]
const VALUE_FLAGS = ["on", "damage", "renderdepth", "parallaxdepth"]
// the flags menu, presets first; goal loads and shows but isn't offered
const BOX_PRESETS = {kill: "box kills Ori", item: "grants an item once", solid: "box with collision",
                     ritem: "grants an item repeatedly"}
const BOX_FLAG_SUGGESTIONS = {...BOX_PRESETS, once: "box toggles off when collected", unsafe: "saves disabled inside box",
                              unlit: "box ignores lighting (prevents ghosting during movement)",
                              "on=Tick":"grant 60 times a second while inside box", "on=Tick/60/60": "grant once a second while inside box",
                              "on=Frame": "grant every frame while inside box",
                              "damage=1": "box damages entities touching it", "renderDepth=-99": "draw box over terrain",
                              "parallaxDepth=10": "box scrolls like background art"}
// a chip's tooltip; value flags build theirs from what is typed, in describe_flag
const FLAG_TEXT = {...BOX_PRESETS, once: BOX_FLAG_SUGGESTIONS.once, unsafe: BOX_FLAG_SUGGESTIONS.unsafe,
                   unlit: BOX_FLAG_SUGGESTIONS.unlit, goal: "ends a practice segment"}
const TRIGGER_TEXT = {Enter: "grants when Ori enters the box", Tick: "grants 60 times a second while Ori is inside",
                      Frame: "grants every frame while Ori is inside"}
// the game's DamageType names, which it matches case-insensitively
const DAMAGE_TYPES = ["Acid", "Bash", "Bat", "ChargeFlame", "Crush", "Drowning", "Enemy", "Explosion", "Grenade", "GrenadeSplatter",
                      "Heat", "HitSurface", "Ice", "Laser", "Lava", "LevelUp", "NightBerryDied", "Nova", "Projectile", "SlugSpike",
                      "Spikes", "SpiritFlame", "SpiritFlameSplatter", "Stomp", "StompBlast", "Water"]
const DEPTH_RANGES = {renderdepth: [-99, 399], parallaxdepth: [-19, 4979]}
// a deleted box keeps its line, so the boxes after it keep the numbers BM|n names
const BOX_TOMBSTONE = "tombstone"
const BOX_TOMBSTONE_LINE = "BX|tombstone|0,0,0,0"
const BOX_COLORS = {goal: "#8fe3a0", kill: "#ff6b6b", solid: "#9aa0aa", item: "#40c0ff", ritem: "#7fd8ff"}
const BOXES_TXT = "https://github.com/sparkle-preference/OriDERandomizer/blob/4.3/Boxes.txt"
const HEX_COLOR = /^#?([0-9a-f]{6})([0-9a-f]{2})?$/i

const split_flags = (text) => text.split(",").map(f => f.trim()).filter(f => f)
const box_flags = (b) => split_flags(b.flags || "")
const box_has_flag = (b, flag) => box_flags(b).some(f => f.toLowerCase() === flag)
// the game deletes a box with tombstone, or none (its old name), anywhere in its flags
const is_box_gone = (b) => box_has_flag(b, BOX_TOMBSTONE) || box_has_flag(b, "none")
const box_hidden = (b) => b.color === "none" || b.color === "0"
let next_box_id = 1
// flags is the field as written, so a line comes back byte for byte; shape is too, and empty for a rectangle
const new_box = (flags, box, shape) => ({_id: next_box_id++, flags: flags, box: box, shape: shape || "", color: "", give: "", locked: false})

// a plain decimal, as the game's float.TryParse with NumberStyles.Number reads one
const numeric = (text) => /^\s*[+-]?(\d+\.?\d*|\.\d+)\s*$/.test(text)
const hundredths = (v) => Math.round(v * 100) / 100

const SHAPE_WORDS = {convex: "convex", loop: "loop", orientedloop: "orientedLoop", previewloop: "previewLoop"}

// A shaped box's field as the game reads it, {kind, loops of [x, y]}, or null where the game throws:
// a convex is one loop, every loop needs three points (the editor's previewLoop any), a last x alone is dropped.
function parse_shape(text) {
    let parts = (text || "").split(","), kind = parts[0].toLowerCase()
    if(!SHAPE_WORDS.hasOwnProperty(kind))
        return null
    let loops = [[]]
    for(let k = 1; k < parts.length;) {
        if(kind !== "convex" && parts[k].toLowerCase() === "loop") {
            loops.push([])
            k++
        } else if(k === parts.length - 1)
            break
        else if(!numeric(parts[k]) || !numeric(parts[k + 1]))
            return null
        else {
            loops[loops.length - 1].push([Number(parts[k]), Number(parts[k + 1])])
            k += 2
        }
    }
    return kind !== "previewloop" && loops.some(l => l.length < 3) ? null : {kind: kind, loops: loops}
}

const write_shape = (read) => SHAPE_WORDS[read.kind] +
    read.loops.map(l => l.map(p => "," + hundredths(p[0]) + "," + hundredths(p[1])).join("")).join(",loop")

// the rectangle around every point, low corner first
function shape_bounds(read) {
    let points = read.loops.flat()
    if(!points.length)
        return [0, 0, 0, 0]
    let xs = points.map(p => p[0]), ys = points.map(p => p[1])
    return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)]
}

// "", "convex" or "loop"; an orientedLoop or previewLoop is a loop
const box_shape_kind = (b) => {
    let read = b.shape ? parse_shape(b.shape) : null
    return !read ? "" : read.kind === "convex" ? "convex" : "loop"
}

// an orientedLoop's loops fill as one, by nonzero winding, so a loop wound against another cuts a hole
const box_winds = (b) => !!b.shape && (parse_shape(b.shape) || {}).kind === "orientedloop"

// the hull's corners in order, by Andrew's monotone chain
function convex_hull(points) {
    let sorted = [...points].sort((a, b) => a[0] - b[0] || a[1] - b[1])
    let turn = (o, a, b) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    let half = (list) => {
        let out = []
        list.forEach(p => {
            while(out.length > 1 && turn(out[out.length - 2], out[out.length - 1], p) <= 0)
                out.pop()
            out.push(p)
        })
        return out.slice(0, -1)
    }
    return sorted.length < 3 ? sorted : [...half(sorted), ...half(sorted.reverse())]
}

// What a box covers, as outlines of [x, y]: its corners, a convex box's hull, or each loop. A loop fills
// even-odd and the game unions the loops, so they are drawn one apiece.
function box_rings(b) {
    let read = b.shape ? parse_shape(b.shape) : null
    if(read)
        return read.kind === "convex" ? [convex_hull(read.loops[0])] : read.loops.filter(l => l.length)
    let [x1, y1, x2, y2] = b.box
    return [[[x1, y1], [x2, y1], [x2, y2], [x1, y2]]]
}

// the ring's turns around the point: crossings to its right, up +1, down -1; odd is inside by even-odd
const winding = (ring, x, y) => ring.reduce((sum, p, k) => {
    let q = ring[(k + 1) % ring.length]
    return (p[1] > y) !== (q[1] > y) && x < p[0] + (y - p[1]) * (q[0] - p[0]) / (q[1] - p[1]) ? sum + (q[1] > p[1] ? 1 : -1) : sum
}, 0)
const box_holds = (b, x, y) => box_winds(b) ? box_rings(b).reduce((sum, ring) => sum + winding(ring, x, y), 0) !== 0
    : box_rings(b).some(ring => winding(ring, x, y) % 2 !== 0)
const signed_area = (ring) => ring.reduce((sum, p, k) => sum + p[0] * ring[(k + 1) % ring.length][1] - ring[(k + 1) % ring.length][0] * p[1], 0) / 2

// the box (dx, dy) over: a shaped one moves every point by whole hundredths, so it keeps its shape, and its bounds follow
function move_box(b, dx, dy) {
    let read = b.shape ? parse_shape(b.shape) : null
    if(!read)
        return {box: [b.box[0] + dx, b.box[1] + dy, b.box[2] + dx, b.box[3] + dy]}
    let [mx, my] = [hundredths(dx), hundredths(dy)]
    let shape = write_shape({kind: read.kind, loops: read.loops.map(l => l.map(p => [p[0] + mx, p[1] + my]))})
    return {box: shape_bounds(parse_shape(shape)), shape: shape}
}

const shape_patch = (read) => {
    let shape = write_shape(read)
    return {box: shape_bounds(parse_shape(shape)), shape: shape}
}

// a shaped box's own points as {loop, k, x, y}; a convex box's are the line's, in its order, not its hull's corners
function box_points(b) {
    let read = b.shape ? parse_shape(b.shape) : null
    return read ? read.loops.flatMap((l, loop) => l.map((p, k) => ({loop: loop, k: k, x: p[0], y: p[1]}))) : []
}

function set_point(b, loop, k, x, y) {
    let read = parse_shape(b.shape)
    read.loops[loop][k] = [x, y]
    return shape_patch(read)
}

// the spot on a segment nearest (x, y), and how far off that is
function onto(a, b, x, y) {
    let dx = b[0] - a[0], dy = b[1] - a[1], len = dx * dx + dy * dy
    let t = len ? Math.max(0, Math.min(1, ((x - a[0]) * dx + (y - a[1]) * dy) / len)) : 0
    return {x: a[0] + t * dx, y: a[1] + t * dy, d: Math.hypot(x - a[0] - t * dx, y - a[1] - t * dy)}
}

// The side of a shaped box nearest (x, y): the spot on it, how far off (d), and where a point there goes.
// A convex box's sides are its hull's and its points have no order, so a new one goes last.
function nearest_side(b, x, y) {
    let read = b.shape ? parse_shape(b.shape) : null
    if(!read)
        return null
    let convex = read.kind === "convex", best = null
    let rings = convex ? [convex_hull(read.loops[0])] : read.loops
    rings.forEach((ring, loop) => ring.forEach((p, k) => {
        let spot = onto(p, ring[(k + 1) % ring.length], x, y)
        if(!best || spot.d < best.d)
            best = {...spot, loop: loop, k: convex ? read.loops[0].length : k + 1}
    }))
    return best
}

function insert_point(b, loop, k, x, y) {
    let read = parse_shape(b.shape)
    read.loops[loop].splice(k, 0, [x, y])
    return shape_patch(read)
}

// a loop keeps three points: at three, removing one removes the loop, and a box's only loop stays (null)
function remove_point(b, loop, k) {
    let read = parse_shape(b.shape)
    if(read.loops[loop].length > 3)
        read.loops[loop].splice(k, 1)
    else if(read.loops.length > 1)
        read.loops.splice(loop, 1)
    else
        return null
    return shape_patch(read)
}

// a convex box's points on its hull's outline, to a hundredth: one inside moves nothing when dragged
function tidy_shape(b) {
    let read = b.shape ? parse_shape(b.shape) : null
    if(!read || read.kind !== "convex")
        return {}
    let hull = convex_hull(read.loops[0])
    let kept = read.loops[0].filter(p => hull.some((a, k) => onto(a, hull[(k + 1) % hull.length], p[0], p[1]).d <= 0.01))
    return kept.length < 3 || kept.length === read.loops[0].length ? {} : shape_patch({kind: "convex", loops: [kept]})
}

// The same ground as another kind: "" is the rectangle around it, a convex is the hull of every point,
// a loop is the outline it had. A box too flat to have a hull stays as it is.
function reshape_box(b, kind) {
    if(kind === box_shape_kind(b))
        return {}
    if(!kind)
        return {box: [...b.box], shape: ""}
    let [x1, y1, x2, y2] = [Math.min(b.box[0], b.box[2]), Math.min(b.box[1], b.box[3]), Math.max(b.box[0], b.box[2]), Math.max(b.box[1], b.box[3])]
    let rings = b.shape ? box_rings(b) : [[[x1, y1], [x2, y1], [x2, y2], [x1, y2]]]
    if(kind === "convex")
        rings = [convex_hull(rings.flat())]
    return rings.some(ring => ring.length < 3) ? {} : shape_patch({kind: kind, loops: rings})
}

// a loop box with one more loop: a small triangle past its right side, wound with the box's net turn so it adds ground
function add_loop(b) {
    let read = b.shape ? parse_shape(b.shape) : null
    if(!read || !["loop", "orientedloop"].includes(read.kind))
        return {}
    let [, y1, x2] = shape_bounds(read), triangle = [[x2 + 1, y1], [x2 + 3, y1], [x2 + 2, y1 + 2]]
    read.loops.push(read.loops.reduce((sum, l) => sum + signed_area(l), 0) < 0 ? triangle.reverse() : triangle)
    return shape_patch(read)
}

function parse_box_line(line) {
    let f = line.trim().split("|")
    if(f[0] !== "BX" || f.length < 3)
        return null
    let corners = f[2].split(","), box = corners.map(Number), shape = ""
    if(corners.length !== 4 || !corners.every(numeric)) {
        let read = parse_shape(f[2])
        if(!read)
            return null
        box = shape_bounds(read)
        shape = f[2]
    }
    let out = new_box(f[1], box, shape)
    out.color = (f[3] || "").trim()
    out.give = f.slice(4).join("|")
    return is_box_gone(out) ? {...out, flags: BOX_TOMBSTONE, box: [0, 0, 0, 0], shape: "", color: "", give: ""} : out
}

function box_line(b) {
    if(is_box_gone(b))
        return BOX_TOMBSTONE_LINE
    // a pipe would end the flags field
    let flags = (b.flags || "").replace(/\|/g, "")
    let color = (b.color || "").trim()
    let fields = ["BX", flags, b.shape || b.box.map(hundredths).join(","), color, b.give || ""]
    while(fields.length > 3 && !fields[fields.length - 1])
        fields.pop()
    return fields.join("|")
}

// Pasted text as boxes. A line whose first field is BX is a box, or a problem if it doesn't read; other
// lines (a seed's placements and flag line) are counted and skipped, blank ones silently.
function parse_box_paste(text) {
    let boxes = [], bad = [], ignored = 0
    ;(text || "").split(/\r\n|\r|\n/).forEach((line, k) => {
        if(!line.trim())
            return
        if(line.split("|")[0].trim().toUpperCase() !== "BX") {
            ignored++
            return
        }
        let box = parse_box_line(line)
        if(box)
            boxes.push(box)
        else
            bad.push({line: k + 1, text: line.trim()})
    })
    return {boxes: boxes, bad: bad, ignored: ignored}
}

// Pasted boxes in place of a world's own or into an empty one, deleted ones kept so every box keeps its
// number; or after them, less the deleted ones and the lines the world already has.
function paste_boxes(current, pasted, replace) {
    let live = pasted.filter(b => !is_box_gone(b))
    if(replace || current.every(is_box_gone))
        return {boxes: [...pasted], added: live.length, dupes: 0, gone: pasted.length - live.length}
    let known = new Set(current.map(box_line))
    let fresh = live.filter(b => !known.has(box_line(b)))
    return {boxes: [...current, ...fresh], added: fresh.length, dupes: live.length - fresh.length, gone: pasted.length - live.length}
}

const WORDY = /[a-z0-9]/
// a word typed has to start a word, so "kill" finds a kill box but not a bonus skill
function starts_a_word(hay, word) {
    if(!WORDY.test(word[0]))
        return hay.includes(word)
    for(let k = hay.indexOf(word); k >= 0; k = hay.indexOf(word, k + 1))
        if(k === 0 || !WORDY.test(hay[k - 1]))
            return true
    return false
}

// The box list's search, as a test on a box, or null with nothing typed: every word has to turn up in the
// give's name, the give as written, or the flags, in any case.
function box_search(text, give_name) {
    let words = (text || "").toLowerCase().split(/\s+/).filter(w => w)
    if(!words.length)
        return null
    return (b) => {
        let hay = [b.give ? give_name(b.give) : "", b.give || "", b.flags || ""].join("\n").toLowerCase()
        return words.every(w => starts_a_word(hay, w))
    }
}

// the game lets each preset flag set the color in turn, so the last one shows
function box_color(b) {
    let m = HEX_COLOR.exec(b.color || "")
    let preset = box_flags(b).map(f => f.toLowerCase()).filter(f => BOX_COLORS[f]).pop()
    return m ? "#" + m[1].toLowerCase() : (BOX_COLORS[preset] || BOX_COLORS.item)
}

// a comma or pipe would split the line
const box_flag_ok = (flag) => !!flag.trim() && !/[,|]/.test(flag)

const capital = (text) => text.charAt(0).toUpperCase() + text.slice(1)
const one_of = (names, text) => names.find(n => n.toLowerCase() === text.trim().toLowerCase())
// a whole number that fits an int, as int.TryParse takes one
const integer = (text) => /^\s*[+-]?\d+\s*$/.test(text) && Math.abs(Number(text)) <= 2147483647

// a count of physics ticks, with the seconds it comes to
const ticks = (n) => `${n} tick${n === 1 ? "" : "s"} (${Math.round(n / 60 * 100) / 100} s)`

// on=Enter, on=Frame, or on=Tick/<delay>/<repeat>: a delay and repeat are ticks or never, 1 when left out
function describe_trigger(value, bad) {
    let parts = value.split("/")
    let when = one_of(Object.keys(TRIGGER_TEXT), parts[0])
    if(!when)
        return bad("One of: Enter, Tick, Frame")
    if(when !== "Tick")
        return parts.length > 1 ? bad(`${when} takes no delay or repeat`) : {text: capital(TRIGGER_TEXT[when])}
    if(parts.length > 3)
        return bad("Tick takes a delay and a repeat at most: Tick/30/60")
    // the game collects once its countdown is at or below 0, so 0 and below act as 1
    let count = (p) => p === undefined ? 1 : /^\s*never\s*$/i.test(p) ? Infinity : integer(p) ? Math.max(1, Number(p)) : NaN
    let [delay, repeat] = [count(parts[1]), count(parts[2])]
    if(isNaN(delay))
        return bad(`The delay is a whole number of ticks, or never: ${parts[1]}`)
    if(isNaN(repeat))
        return bad(`The repeat is a whole number of ticks, or never: ${parts[2]}`)
    if(delay === Infinity)
        return {text: "Never grants"}
    if(delay === 1 && repeat === 1)
        return {text: capital(TRIGGER_TEXT.Tick)}
    let first = delay === 1 ? "Grants as soon as Ori is inside" : `Grants after ${ticks(delay)} inside`
    let then = repeat === Infinity ? "then not again until Ori leaves and comes back" : repeat === 1 ? "then every tick" : `then every ${ticks(repeat)}`
    return {text: `${first}, ${then}`}
}

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
    if(key === "on")
        return describe_trigger(value, bad)
    if(DEPTH_RANGES[key]) {
        let [low, high] = DEPTH_RANGES[key]
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

// the parts after a value flag's "=", in order, and what the game uses for one left out; more: the names that
// take the parts after them, where not every name does; whole: a whole number counts as a finished part
const FLAG_PARTS = {
    on: [{names: Object.keys(TRIGGER_TEXT), more: ["Tick"]}, {hint: "delay in ticks", fallback: "1", whole: integer},
         {names: ["never"], hint: "repeat in ticks, or never", fallback: "1", whole: integer}],
    damage: [{hint: "amount"}, {names: DAMAGE_TYPES, hint: "damage type", fallback: "Spikes"},
             {names: ["All", "Player"], hint: "target", fallback: "All"},
             {names: ["Normal", "Extended"], hint: "hitboxes", fallback: "Extended"}],
    renderdepth: [{hint: DEPTH_RANGES.renderdepth.join(" to ")}],
    parallaxdepth: [{hint: DEPTH_RANGES.parallaxdepth.join(" to ")}],
}

// Completions for a value flag being typed: its current part's names, prefix matches first (longer names too
// once it is whole), then the next part. A pick more can follow fills the text box (fill); a final one is added.
// A value waiting on a part names it (next), which is how an empty part without names shows its hint.
function flag_completions(text) {
    let eq = text.indexOf("=")
    let parts = eq < 0 ? null : FLAG_PARTS[text.slice(0, eq).trim().toLowerCase()]
    let typed = text.slice(eq + 1).split("/")
    let at = typed.length - 1
    if(!parts || !parts[at])
        return []
    let part = parts[at], partial = typed[at].trim().toLowerCase()
    if(!part.names && !partial)
        return [{value: text, fill: true, next: part}]
    let head = text.slice(0, text.length - typed[at].length)
    let named = part.names ? part.names.find(n => n.toLowerCase() === partial) : undefined
    let whole = !!named || (part.whole ? part.whole(typed[at]) : !part.names && numeric(typed[at]))
    let goesOn = (name) => !!parts[at + 1] && (!part.more || part.more.includes(name))
    let out = []
    if(part.names) {
        let hits = whole ? part.names.filter(n => n.toLowerCase().startsWith(partial) && n.toLowerCase() !== partial)
                         : [...part.names.filter(n => n.toLowerCase().startsWith(partial)),
                            ...part.names.filter(n => !n.toLowerCase().startsWith(partial) && n.toLowerCase().includes(partial))]
        out = hits.map(n => ({value: head + n, fill: goesOn(n)}))
    }
    if(whole && goesOn(named))
        out.push({value: text + "/", fill: true, next: parts[at + 1]})
    return out
}

// The flags menu for what's typed, its completions given as menu lines: after the usual lines when the flag is
// whole as typed, so Enter adds it, else first, with a usual line taking the place of a completion it matches.
function flag_menu(options, completions, whole) {
    let known = options.map(o => o.value.toLowerCase())
    let at = completions.map(c => known.indexOf(c.value.toLowerCase()))
    let fresh = completions.filter((_, k) => at[k] < 0)
    if(whole || !completions.length)
        return fresh.length ? [...options, ...fresh] : options
    // marked, so the menu's filter keeps it like the completion it stands for
    return [...completions.map((c, k) => at[k] < 0 ? c : {...options[at[k]], completion: true}),
            ...options.filter((_, k) => !at.includes(k))]
}

// what only a rectangle does, and what a loop box does only when solid: it has no inside to touch
const RECT_ONLY = {unsafe: "Unsafe boxes must be rectangular", goal: "Goal boxes must be rectangular"}
const NEEDS_INSIDE = ["kill", "damage", "once", "item", "ritem"]

// The chip or menu line for a flag. It warns where the box can't honor it: a kill on a box that gives
// something, or a flag its shape (kind, and whether it is solid) rules out.
function flag_option(flag, give, kind, solid) {
    let {text, warn} = describe_flag(flag)
    let key = flag.split("=")[0].trim().toLowerCase(), gives = !!give && give !== "NO|1"
    if(key === "kill" && gives)
        [text, warn] = ["Won't kill Ori (grants an item)", true]
    if(kind && RECT_ONLY[key])
        [text, warn] = [RECT_ONLY[key], true]
    else if(kind === "loop" && !solid && NEEDS_INSIDE.includes(key) && (gives || !key.endsWith("item")))
        [text, warn] = ["Loop boxes must be solid", true]
    return {label: flag, value: flag, warn: !!warn, tip: text, desc: BOX_FLAG_SUGGESTIONS[flag], color: BOX_COLORS[flag.toLowerCase()]}
}
const SUGGESTED = Object.keys(BOX_FLAG_SUGGESTIONS).map(flag => flag_option(flag))

// the flags select's chips, in written order, and menu: the suggestions plus the box's own flags
function box_flag_choices(flags, give, kind) {
    let solid = split_flags(flags || "").some(f => f.toLowerCase() === "solid")
    let chips = split_flags(flags || "").map(flag => flag_option(flag, give, kind, solid))
    let own = chips.filter(c => !BOX_FLAG_SUGGESTIONS[c.value])
    return {chips: chips, options: own.length ? [...SUGGESTED, ...own] : SUGGESTED}
}

const box_flags_from_chips = (flags) => ({flags: flags.join(",")})

const MULTI_CODES = ["MU", "RP", "RG"]
// the client keeps box state in these slots by box number: off bits, then contact bits
const BOX_STATE_SLOTS = [[1700, 1999], [2700, 2999]]
// {Bn}, {Bn.x} and {Bn.y} read box n wherever a slot read goes
const BOX_READ = /(\{\s*[Bb])([0-9]+)((?:\.[XxYy])?\s*\})/g
const BOX_CODES = ["BM", "BR"]

function renumber_reads(text, map) {
    return text.replace(BOX_READ, (m, open, n, close) => {
        let k = map[parseInt(n, 10)]
        return k === undefined || k === parseInt(n, 10) ? m : open + k + close
    })
}

// a pickup as pieces, each with the world it runs in; a BM or BR names its box first, and any piece may read boxes
function read_pickup(value, world, owner, where, spawn, box_item, problems) {
    let bar = (value || "").indexOf("|")
    if(bar < 0)
        return null
    let code = value.slice(0, bar), id = value.slice(bar + 1)
    let home = owner && String(owner) !== String(world) ? String(owner) : String(world)
    // seedgen sends an MU piece marked "@n" to world n and keeps the rest with the holder, owner or not
    let by_piece = code === "MU" && id.includes("@") && !box_item
    let pieces = (MULTI_CODES.includes(code) ? decompose_pickup(code, id) : [[code, id]]).map(([c, i]) => {
        let piece = {code: c, id: i, world: by_piece ? String(world) : home,
                     reads: [...i.matchAll(BOX_READ)].map(m => parseInt(m[2], 10))}
        let slots = [...i.matchAll(/\{\s*(\d+)\s*\}/g)].map(m => parseInt(m[1], 10))
        if(c === "RI")
            slots.push(parseInt(i, 10))
        slots.filter(n => BOX_STATE_SLOTS.some(([lo, hi]) => n >= lo && n <= hi)).forEach(n =>
            problems.push(`${where}: ${c}|${i} uses slot ${n}, which holds box state by box number`))
        if(!BOX_CODES.includes(c))
            return piece
        let at = i.indexOf("@")
        let tag = at < 0 ? "" : i.slice(at)
        if(tag && !(by_piece && /^@\d+$/.test(tag)))
            problems.push(`${where}: ${c}|${i}: only a piece of a placed MU can name a world`)
        else if(tag)
            piece.world = tag.slice(1)
        let body = at < 0 ? i : i.slice(0, at)
        let eq = body.indexOf("=")
        let head = /^\s*(\d+)\s*([+-]?)\s*$/.exec(eq < 0 ? body : body.slice(0, eq))
        if(!head || (head[2] && (c !== "BR" || eq < 0))) {
            problems.push(`${where}: ${c}|${i} names no box number`)
            return piece
        }
        return {...piece, box: parseInt(head[1], 10), rest: head[2] + (eq < 0 ? "" : body.slice(eq)) + tag}
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
        let map = renumber[p.world] || {}
        let n = p.box === undefined ? undefined : map[p.box]
        let id = renumber_reads(n === undefined || n === p.box ? p.id : n + p.rest, map)
        if(id === p.id)
            return [p.code, p.id]
        changed = true
        return [p.code, id]
    }) : []
    if(!changed)
        return value
    return read.code + "|" + (read.multi ? parts.map(([c, i]) => pack_piece(c + "|" + i)).join("/") : parts[0][1])
}

// Drops deleted boxes without reordering the rest (same-tick items go in line order) and renumbers BM|n, BR|n
// and {Bn} reads. pickups: [{value, world holding it, owner it is for, spawn, where}]; a reference to a deleted
// box is a problem and keeps its tombstone.
function compact_boxes(worlds, pickups) {
    let problems = []
    let reads = pickups.map(p => read_pickup(p.value, p.world, p.owner, p.where, p.spawn, false, problems))
    let gives = {}
    Object.keys(worlds).forEach(w => {
        gives[w] = worlds[w].map((b, k) => is_box_gone(b) ? null : read_pickup(b.give, w, null, `P${w} box #${k}`, false, true, problems))
    })
    let named = {}
    ;[...reads, ...Object.values(gives).flat()].forEach(r => r && r.pieces.forEach(p => {
        let boxes = worlds[p.world] || []
        ;(p.box === undefined ? p.reads : [p.box, ...p.reads]).forEach(n => {
            if(n >= boxes.length)
                problems.push(`${r.where}: ${p.code}|${p.id}: world ${p.world} has no box ${n}`)
            else if(is_box_gone(boxes[n])) {
                problems.push(`${r.where}: ${p.code}|${p.id} names box ${n}, which is deleted`)
                named[p.world + ":" + n] = true
            }
        })
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
    BOX_PRESETS, BOX_COLORS, BOX_TOMBSTONE, is_box_gone, box_hidden, new_box, box_flags, box_has_flag, box_flags_from_chips,
    parse_box_line, box_line, box_color, box_flag_ok, box_flag_warning, describe_flag, flag_completions, flag_menu, box_flag_choices, BOXES_TXT,
    compact_boxes, parse_box_paste, paste_boxes, box_search,
    parse_shape, box_shape_kind, box_winds, convex_hull, box_rings, box_holds, move_box,
    box_points, set_point, nearest_side, insert_point, remove_point, tidy_shape, reshape_box, add_loop
};
