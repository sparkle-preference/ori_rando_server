// fast-check properties of the plando editor's box lines, box paste, compact_boxes, drafts, and the seed page's undo history.
// Run from the repo root: node --import ./test/jsx_loader.mjs --test test/frontend_props.mjs
import test from "node:test"
import assert from "node:assert/strict"
import {fc, runs} from "./props_base.mjs"
import {parse_box_line, box_line, is_box_gone, parse_box_paste, paste_boxes, compact_boxes} from "../map/src/boxes.js"
import {decompose_pickup, pack_piece} from "../map/src/multipickup.js"
import {draft_key, read_draft, write_draft, move_draft, draft_offer, time_ago} from "../map/src/plando_draft.js"
import {History, snap, HIST_KEYS} from "../map/src/history.js"

const check = (arbs, pred, n) => fc.assert(fc.property(...arbs, pred), {numRuns: runs(n)})
const model = (b) => ({flags: b.flags, box: b.box, color: b.color, give: b.give})

const KNOWN = ["goal", "kill", "solid", "item", "ritem", "once", "unsafe", "on=Tick/30/60", "damage=1/Lava", "renderDepth=-99", "parallaxDepth=10"]
const recase = (s) => fc.array(fc.boolean(), {minLength: s.length, maxLength: s.length})
    .map(bs => [...s].map((c, k) => bs[k] ? c.toUpperCase() : c).join(""))
const word = fc.stringMatching(/^[a-z][a-z0-9=\/]{0,8}$/)
const flag = fc.oneof({weight: 6, arbitrary: fc.constantFrom(...KNOWN).chain(recase)},
                      {weight: 1, arbitrary: fc.constantFrom("none", "tombstone", "Tombstone")},
                      {weight: 2, arbitrary: word})
const pad = fc.constantFrom("", " ", "  ")
const flags = fc.array(fc.tuple(pad, flag, pad).map(t => t.join("")), {maxLength: 4}).map(fs => fs.join(","))
const coord = fc.oneof(fc.integer({min: -5000, max: 5000}), fc.double({min: -5000, max: 5000, noNaN: true}),
                       fc.integer({min: -500000, max: 500000}).map(n => n / 100))
const coords = fc.tuple(coord, coord, coord, coord)
const hex = fc.stringMatching(/^[0-9a-fA-F]{6}([0-9a-fA-F]{2})?$/)
// what the color input and a parsed line can hold: a hex color, none, or nothing
const color = fc.oneof(fc.constant(""), fc.constantFrom("none", "0"), hex, hex.map(h => "#" + h))
const id_text = fc.stringMatching(/^[A-Za-z0-9 =@{}+\/]{0,8}$/)
const piece = fc.tuple(fc.constantFrom("SK", "EX", "SH", "BM", "RI", "HC"), id_text)
const give = fc.oneof(fc.constant(""), piece.map(([c, i]) => c + "|" + i),
                      fc.array(piece, {minLength: 1, maxLength: 3}).map(ps => "MU|" + ps.map(([c, i]) => pack_piece(c + "|" + i)).join("/")))
const box = fc.record({flags, box: coords, color, give: give.filter(g => g === g.trimEnd())})

test("box_line is a fixed point of parse_box_line", () => {
    check([box], b => {
        let line = box_line(b)
        let back = parse_box_line(line)
        assert.ok(back, line)
        assert.equal(box_line(back), line)
    }, 2000)
})

test("a live box reads back with its flags, color and give as written", () => {
    check([box.filter(b => !is_box_gone(b))], b => {
        let back = model(parse_box_line(box_line(b)))
        assert.deepEqual([back.flags, back.color, back.give], [b.flags.replace(/\|/g, ""), b.color.trim(), b.give])
    }, 1000)
})

const junk = fc.string({unit: fc.constantFrom("|", ",", " ", "\t", "1", "-", ".", "e", "k", "#", "f", "x"), maxLength: 6})
const numtext = fc.oneof(coord.map(String), fc.constantFrom("1e3", "1abc", " 2", "0x10", "Infinity", "-0", ".5", "5."))
const anyline = fc.tuple(junk, fc.array(numtext, {minLength: 4, maxLength: 4}), junk, junk)
    .map(([f, c, col, g]) => `BX|${f}|${c.join(",")}|${col}|${g}`)

test("one rewrite of any line that parses is stable", () => {
    check([anyline], line => {
        let b = parse_box_line(line)
        fc.pre(b !== null)
        let once = box_line(b)
        assert.equal(box_line(parse_box_line(once)), once)
    }, 2000)
})

const pasted_line = fc.oneof({weight: 4, arbitrary: box.map(box_line)}, {weight: 1, arbitrary: fc.constant("")},
                             {weight: 1, arbitrary: fc.constant("   ")}, {weight: 1, arbitrary: fc.constant("Flags|ForceTrees|Seed")},
                             {weight: 1, arbitrary: fc.constant("BX|kill|1,2")}, {weight: 1, arbitrary: fc.constant(" bx|kill|1,2,3,4")})

test("a paste counts every non-blank line as a box, a problem or ignored", () => {
    check([fc.array(pasted_line, {maxLength: 12}), fc.constantFrom("\n", "\r\n", "\r")], (lines, eol) => {
        let out = parse_box_paste(lines.join(eol))
        assert.equal(out.boxes.length + out.bad.length + out.ignored, lines.filter(l => l.trim()).length)
    }, 1000)
})

const world = fc.array(box, {maxLength: 6}).map(bs => bs.map(b => parse_box_line(box_line(b))))

test("pasting adds, skips as a dupe or drops as deleted every box, and keeps the world's own first", () => {
    check([world, world, fc.boolean()], (cur, pasted, replace) => {
        let out = paste_boxes(cur, pasted, replace)
        assert.equal(out.added + out.dupes + out.gone, pasted.length)
        if(replace || cur.every(is_box_gone))
            assert.equal(out.boxes.length, pasted.length)
        else
            assert.ok(out.boxes.slice(0, cur.length).every((b, k) => b === cur[k]))
    }, 1000)
})

test("appending a paste never repeats a line the world has", () => {
    check([world.filter(cur => !cur.every(is_box_gone)), world], (cur, pasted) => {
        let known = new Set(cur.map(box_line))
        assert.ok(paste_boxes(cur, pasted, false).boxes.slice(cur.length).every(b => !known.has(box_line(b))))
    }, 1000)
})

// a pipe in a piece id is the open bug the two tests below pin
const pipe_free = ([, id]) => !id.includes("|")
const sibling = fc.tuple(fc.constantFrom("SK", "EX", "SH", "HC"), fc.stringMatching(/^[A-Za-z0-9 =@+|\/]{0,8}$/)).filter(pipe_free)
const rest = fc.constantFrom("", "=1", "=12")
const lead = (id) => id.startsWith("/") ? " " + id : id
const live_box = box.filter(b => !is_box_gone(b)).map(b => ({...b, give: ""}))

// boxes in up to three worlds, world 1's first one deleted so later numbers move; each ref names a live box
const compact_case = fc.integer({min: 1, max: 3}).chain(nw => fc.record({
    worlds: fc.tuple(...Array.from({length: nw}, () => fc.array(fc.record({gone: fc.boolean(), b: live_box}), {minLength: 1, maxLength: 6}))),
    refs: fc.array(fc.record({world: fc.integer({min: 1, max: nw}), at: fc.nat(), holder: fc.option(fc.nat(), {nil: null}),
                              sib: fc.option(sibling, {nil: null}), multi: fc.boolean(), rest}), {minLength: 1, maxLength: 6}),
}))

function compact_world(c) {
    let worlds = {}, tags = {}
    c.worlds.forEach((bs, k) => {
        let w = String(k + 1)
        let rows = k === 0 ? [{gone: true}, ...bs] : bs
        worlds[w] = rows.map((x, j) => {
            let b = x.gone ? parse_box_line("BX|tombstone|0,0,0,0") : parse_box_line(box_line(x.b))
            tags[b._id] = w + ":" + j
            return b
        })
    })
    let pickups = [], held = []
    c.refs.forEach(r => {
        let w = worlds[r.world] && worlds[r.world].some(b => !is_box_gone(b)) ? String(r.world) : "1"
        let live = worlds[w].map((b, j) => j).filter(j => !is_box_gone(worlds[w][j]))
        if(!live.length)
            return
        let n = live[r.at % live.length]
        let value = r.multi || r.sib ? "MU|" + [pack_piece("BM|" + n + r.rest), ...(r.sib ? [pack_piece(r.sib.join("|"))] : [])].join("/")
                                     : "BM|" + n + r.rest
        let holder = r.holder === null ? null : live[r.holder % live.length]
        if(holder !== null && !worlds[w][holder].give)
            worlds[w][holder] = {...worlds[w][holder], give: value}
        else
            holder = null
        let ref = {w, n, rest: r.rest, sib: r.sib, holder: holder === null ? null : worlds[w][holder]._id}
        ;(holder === null ? pickups : held).push(ref)
        if(holder === null)
            ref.value = value
    })
    return {worlds, tags, pickups, held}
}

const pieces_of = (v) => v.startsWith("MU|") ? decompose_pickup("MU", v.slice(3)) : [[v.slice(0, v.indexOf("|")), v.slice(v.indexOf("|") + 1)]]

function still_names(out, tags, ref, value) {
    let ps = pieces_of(value)
    let bm = ps.find(p => p[0] === "BM")
    let num = parseInt(bm[1], 10)
    assert.equal(bm[1], num + ref.rest, value)
    assert.equal(tags[out.worlds[ref.w][num]._id], ref.w + ":" + ref.n, value)
    assert.deepEqual(ps.filter(p => p[0] !== "BM"), ref.sib ? [[ref.sib[0], lead(ref.sib[1])]] : [], value)
}

test("compact_boxes keeps every BM naming the box it named, and its siblings intact", () => {
    check([compact_case], c => {
        let {worlds, tags, pickups, held} = compact_world(c)
        fc.pre(pickups.length + held.length > 0)
        let out = compact_boxes(worlds, pickups.map((p, k) => ({value: p.value, world: p.w, where: "P" + k})))
        assert.deepEqual(out.problems, [])
        pickups.forEach((p, k) => still_names(out, tags, p, out.pickups[k]))
        held.forEach(h => still_names(out, tags, h, out.worlds[h.w].find(b => b._id === h.holder).give))
    }, 2000)
})

// open bug: these pin today's output, so a fix fails them; delete them with the pipe_free filter above
test("open bug: compact_boxes turns a pipe in a sibling's id into a slash", () => {
    let worlds = {1: ["BX|kill|0,0,1,1", "BX|tombstone|0,0,0,0", "BX|item|2,0,3,1"].map(parse_box_line)}
    assert.equal(compact_boxes(worlds, [{value: "MU|BM/2/SH/a|b", world: "1", where: "A"}]).pickups[0], "MU|BM/1/SH/a/b")
})

test("open bug: compact_boxes turns a pipe in a box's own give into a slash", () => {
    let worlds = {1: ["BX|kill|0,0,1,1", "BX|tombstone|0,0,0,0", "BX|item|2,0,3,1||MU|BM/2/SH/hi|there"].map(parse_box_line)}
    assert.equal(compact_boxes(worlds, []).worlds[1][1].give, "MU|BM/1/SH/hi/there")
})

// localStorage with a byte budget; "off" throws on every touch, as a blocked storage does
class FakeStorage {
    constructor(budget, mode = "on") { this.m = new Map(); this.budget = budget; this.mode = mode }
    guard() { if(this.mode === "off") throw Object.assign(new Error("SecurityError"), {name: "SecurityError"}) }
    get length() { this.guard(); return this.m.size }
    key(k) { this.guard(); return [...this.m.keys()][k] ?? null }
    getItem(k) { this.guard(); return this.m.has(k) ? this.m.get(k) : null }
    removeItem(k) { this.guard(); this.m.delete(k) }
    used(skip) { let n = 0; for(let [k, v] of this.m) if(k !== skip) n += k.length + v.length; return n }
    setItem(k, v) {
        this.guard()
        if(this.used(k) + k.length + String(v).length > this.budget)
            throw Object.assign(new Error("quota"), {name: "QuotaExceededError", code: 22})
        this.m.set(k, String(v))
    }
}

const name = fc.stringMatching(/^[a-z]{1,4}$/)
const draft = fc.record({at: fc.integer({min: 0, max: 2e12}), base: fc.string({maxLength: 4}), tab: fc.string({maxLength: 3}),
                         data: fc.record({name, flagLine: fc.constant("Flags|x"), blob: fc.string({maxLength: 120})})})
const op = fc.oneof(
    fc.record({kind: fc.constant("write"), user: fc.constantFrom("u", "v"), name, draft, keep: fc.integer({min: 1, max: 5})}),
    fc.record({kind: fc.constant("other"), key: fc.constantFrom("theme", "box_colors", "seed_link"), value: fc.string({maxLength: 40})}),
    fc.record({kind: fc.constant("move"), user: fc.constantFrom("u", "v"), from: name, to: name}))
const storage = fc.record({budget: fc.integer({min: 50, max: 2000}), mode: fc.constantFrom("on", "on", "on", "off")})
const drafts_in = (s) => [...s.m.keys()].filter(k => k.startsWith("plando_draft:"))

test("drafts never throw: ok reads back as written, keep is honored, full keeps the old draft, other keys survive", () => {
    check([storage, fc.array(op, {maxLength: 25})], (st, ops) => {
        let s = new FakeStorage(st.budget, st.mode)
        let others = {}
        for(let o of ops) {
            if(o.kind === "other") {
                try { s.setItem(o.key, o.value); others[o.key] = o.value } catch(e) { /* full or off */ }
                continue
            }
            if(o.kind === "move") {
                move_draft(s, o.user, o.from, o.to)
                continue
            }
            let key = draft_key(o.user, o.name)
            let before = s.mode === "off" ? null : s.m.get(key)
            let res = write_draft(s, key, o.draft, o.keep)
            if(s.mode === "off") {
                assert.equal(res, "off")
                continue
            }
            assert.ok(res === "ok" || res === "full", res)
            if(res === "ok") {
                assert.equal(JSON.stringify(read_draft(s, key)), JSON.stringify(o.draft))
                assert.ok(drafts_in(s).length <= o.keep)
            } else
                assert.equal(s.m.get(key), before)
            for(let k in others)
                assert.equal(s.m.get(k), others[k], k)
        }
    }, 1000)
})

test("a moved draft lands under the new name, renamed, and leaves the old one", () => {
    check([draft, name, name], (d, from, to) => {
        fc.pre(from !== to)
        let s = new FakeStorage(1e6)
        write_draft(s, draft_key("u", from), {...d, data: {...d.data, name: from, flagLine: "Flags|" + from}})
        move_draft(s, "u", from, to)
        let moved = read_draft(s, draft_key("u", to))
        assert.equal(read_draft(s, draft_key("u", from)), null)
        assert.deepEqual([moved.data.name, moved.data.flagLine, moved.from], [to, "Flags|" + to, from])
    }, 500)
})

test("a draft is offered exactly when it differs from the plando as loaded", () => {
    check([draft, fc.boolean()], (d, match) => {
        let loaded = match ? JSON.stringify(d.data) : JSON.stringify({...d.data, blob: d.data.blob + "!"})
        assert.equal(draft_offer(d, loaded) === null, match)
    }, 500)
})

const UNITS = ["a moment ago", "minute", "hour", "yesterday", "day", "week", "month"]
const age_rank = (text) => [UNITS.findIndex(w => text.includes(w)), parseInt(text, 10) || 0]

test("an older draft never reads younger", () => {
    check([fc.integer({min: 0, max: 4e10}), fc.integer({min: 0, max: 4e10})], (a, b) => {
        let [x, y] = [age_rank(time_ago(0, Math.min(a, b))), age_rank(time_ago(0, Math.max(a, b)))]
        assert.ok(x[0] < y[0] || (x[0] === y[0] && x[1] <= y[1]), `${time_ago(0, Math.min(a, b))} / ${time_ago(0, Math.max(a, b))}`)
    }, 1000)
})

const hist_op = fc.oneof({weight: 5, arbitrary: fc.record({kind: fc.constant("record"), blob: fc.constantFrom("a", "b", "c", "d", "e")})},
                         {weight: 1, arbitrary: fc.record({kind: fc.constant("live")})},
                         {weight: 3, arbitrary: fc.record({kind: fc.constant("undo")})},
                         {weight: 2, arbitrary: fc.record({kind: fc.constant("redo")})})

test("the undo history keeps its index in range and its cap, never stacks a frame twice, and undo then redo is the identity", () => {
    check([fc.oneof(fc.array(hist_op, {maxLength: 30}), fc.array(hist_op, {minLength: 200, maxLength: 400}))], ops => {
        let h = new History(() => ({}))
        for(let o of ops) {
            let before = h.index >= 0 ? h.stack[h.index] : null
            if(o.kind === "live")
                h.live = true
            else if(o.kind === "record") {
                h.gesture = {ctl: o.blob + "-ctl", tab: "t", world: 1}
                h.record(o.blob)
                assert.equal(h.stack[h.index].blob, o.blob)
            } else if(o.kind === "undo") {
                let u = h.undo()
                if(u) {
                    assert.equal(u.blob, h.stack[h.index].blob)
                    assert.equal(u.ctl, before.ctl)
                    assert.equal(h.redo(), before)
                    h.undo()
                }
            } else
                h.redo()
            assert.ok(h.stack.length <= 200 && h.index >= -1 && h.index < h.stack.length && (!h.stack.length || h.index >= 0))
            assert.ok(h.stack.every((f, k) => k === 0 || f.blob !== h.stack[k - 1].blob))
        }
    }, 500)
})

test("n distinct live edits leave min(n, 200) - 1 undos", () => {
    check([fc.integer({min: 1, max: 260})], n => {
        let h = new History(() => ({}))
        h.live = true
        for(let k = 0; k < n; k++)
            h.record("s" + k)
        let undos = 0
        while(h.undo())
            undos++
        assert.equal(undos, Math.min(n, 200) - 1)
    }, 100)
})

const val = fc.oneof(fc.integer(), fc.double(), fc.string({maxLength: 3}), fc.boolean(), fc.constant(null), fc.array(fc.integer(), {maxLength: 2}))
const form_state = fc.dictionary(fc.constantFrom(...HIST_KEYS.filter(k => k !== "worldPresets")),
                                 fc.oneof(val, fc.dictionary(fc.constantFrom("1", "2"), fc.record({fragCount: val}))))
const non_finite = (state) => JSON.stringify(state, (k, v) => typeof v === "number" && !isFinite(v) ? "BAD" : v).includes("\"BAD\"")

test("a form state snaps to a frame exactly when it holds no non-finite number", () => {
    check([form_state], state => assert.equal(snap(state) === null, non_finite(state)), 1000)
})
