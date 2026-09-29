// The plando editor's local drafts (map/src/plando_draft.js). Run from the repo root: node --test test/plando_draft_test.mjs
import test from "node:test"
import assert from "node:assert/strict"
import {DRAFT_KEEP, draft_key, read_draft, write_draft, remove_draft, move_draft, draft_hash, draft_offer, draft_saved, time_ago} from "../map/src/plando_draft.js"

// localStorage as browsers behave, full past `limit` characters
class Storage {
    constructor(limit = Infinity) {
        this.items = new Map()
        this.limit = limit
    }
    get length() { return this.items.size }
    key(k) { return [...this.items.keys()][k] ?? null }
    getItem(k) { return this.items.has(k) ? this.items.get(k) : null }
    setItem(k, v) {
        v = String(v)
        let used = [...this.items].reduce((n, [key, val]) => key === k ? n : n + key.length + val.length, 0)
        if(used + k.length + v.length > this.limit)
            throw new DOMException("full", "QuotaExceededError")
        this.items.set(k, v)
    }
    removeItem(k) { this.items.delete(k) }
}
// storage the browser refuses outright, as with site data blocked
const REFUSED = new Proxy({}, {get() { throw new DOMException("denied", "SecurityError") }})

const draft = (at, data, extra) => ({v: 1, at: at, tab: "t1", base: "b", data: data, ...extra})

test("each user's plando has its own key", () => {
    let keys = [draft_key("lapis", "a"), draft_key("lapis", "b"), draft_key("other", "a"), draft_key(null, "a"), draft_key("lapis", "newSeed")]
    assert.equal(new Set(keys).size, keys.length)
    assert.equal(draft_key("lapis", "a"), draft_key("lapis", "a"))
})

test("a draft reads back as written; anything else reads as none", () => {
    let s = new Storage()
    let d = draft(5, {name: "a", boxes: [{player: "1", line: "BX|kill|1,2,3,4", locked: true}]})
    assert.equal(write_draft(s, "plando_draft:u/a", d), "ok")
    assert.deepEqual(read_draft(s, "plando_draft:u/a"), d)
    assert.equal(read_draft(s, "plando_draft:u/none"), null)
    for(let junk of ["{", "null", "3", '"x"', '{"at": 1}', '{"data": {}}', '{"at": "1", "data": {}}'])
        assert.equal(read_draft({getItem: () => junk}, "k"), null, junk)
})

test("storage that throws is never fatal", () => {
    for(let storage of [REFUSED, null, undefined]) {
        assert.equal(read_draft(storage, "k"), null)
        assert.equal(write_draft(storage, "k", draft(1, {})), "off")
        remove_draft(storage, "k")
    }
})

test("a full storage evicts other drafts, oldest first, and leaves everything else alone", () => {
    let s = new Storage(3000)
    s.setItem("dark", "true")
    let big = "x".repeat(700)
    write_draft(s, "plando_draft:u/old", draft(100, {big}))
    write_draft(s, "plando_draft:u/mid", draft(200, {big}))
    write_draft(s, "plando_draft:u/new", draft(300, {big}))
    assert.equal(write_draft(s, "plando_draft:u/mine", draft(400, {big: big + big})), "ok")
    assert.equal(s.getItem("dark"), "true")
    assert.equal(read_draft(s, "plando_draft:u/old"), null)
    assert.equal(read_draft(s, "plando_draft:u/mid"), null)
    assert.ok(read_draft(s, "plando_draft:u/new"))
    assert.equal(read_draft(s, "plando_draft:u/mine").at, 400)
})

test("when nothing is left to evict it says full, and the draft already there stays whole", () => {
    let s = new Storage(1000)
    assert.equal(write_draft(s, "plando_draft:u/mine", draft(1, {a: "small"})), "ok")
    assert.equal(write_draft(s, "plando_draft:u/mine", draft(2, {a: "x".repeat(2000)})), "full")
    assert.deepEqual(read_draft(s, "plando_draft:u/mine").data, {a: "small"})
})

test("past the cap the oldest drafts go, never the one being written", () => {
    let s = new Storage()
    s.setItem("box_colors", "[]")
    for(let k = 0; k < DRAFT_KEEP + 3; k++)
        assert.equal(write_draft(s, `plando_draft:u/p${k}`, draft(k, {k})), "ok")
    let left = [...s.items.keys()].filter(k => k.startsWith("plando_draft:"))
    assert.equal(left.length, DRAFT_KEEP)
    assert.deepEqual(["p0", "p1", "p2"].filter(p => left.includes("plando_draft:u/" + p)), [])
    assert.equal(s.getItem("box_colors"), "[]")
    assert.equal(write_draft(s, "plando_draft:u/stale", draft(-1, {})), "ok")
    assert.ok(read_draft(s, "plando_draft:u/stale"))
})

test("a draft is offered only when it differs from what loaded, and says if the plando was saved since", () => {
    let loaded = JSON.stringify({name: "a", boxes: []})
    assert.equal(draft_offer(null, loaded), null)
    assert.equal(draft_offer(draft(1, {name: "a", boxes: []}, {base: "zzz"}), loaded), null)
    let changed = {name: "a", boxes: [{player: "1", line: "BX|kill|1,2,3,4", locked: false}]}
    assert.deepEqual(draft_offer(draft(7, changed, {base: draft_hash(loaded)}), loaded), {at: 7, saved_since: false})
    assert.deepEqual(draft_offer(draft(7, changed, {base: draft_hash("older")}), loaded), {at: 7, saved_since: true})
})

test("after a save the draft goes if this tab wrote it or it matches the save, not another tab's edits", () => {
    let saved = JSON.stringify({name: "a"})
    assert.ok(draft_saved(draft(1, {name: "b"}, {tab: "me"}), saved, "me"))
    assert.ok(draft_saved(draft(1, {name: "a"}, {tab: "them"}), saved, "me"))
    assert.ok(!draft_saved(draft(1, {name: "b"}, {tab: "them"}), saved, "me"))
    assert.ok(!draft_saved(null, saved, "me"))
})

test("a rename takes the draft along, renamed, and still knows what it began from", () => {
    let s = new Storage()
    let saved = {flagLine: "OpenWorld|old", name: "old", placements: []}
    let edited = {...saved, placements: [{loc: "1"}]}
    write_draft(s, draft_key("u", "old"), draft(5, edited, {base: draft_hash(JSON.stringify(saved))}))
    write_draft(s, draft_key("u", "new"), draft(1, {name: "new"}))
    move_draft(s, "u", "old", "new")
    assert.equal(read_draft(s, draft_key("u", "old")), null)
    let moved = read_draft(s, draft_key("u", "new"))
    assert.deepEqual(moved.data, {flagLine: "OpenWorld|new", name: "new", placements: [{loc: "1"}]})
    // the server's copy of the plando under its new name
    let loaded = JSON.stringify({...saved, flagLine: "OpenWorld|new", name: "new"})
    assert.deepEqual(draft_offer(moved, loaded), {at: 5, saved_since: false})
    assert.equal(draft_offer(moved, JSON.stringify({...saved, flagLine: "OpenWorld|new", name: "new", desc: "x"})).saved_since, true)
    move_draft(s, "u", "new", "third")
    assert.equal(read_draft(s, draft_key("u", "third")).from, "old")
})

test("a rename with no draft clears a dead plando's under the new name, and storage that throws is no matter", () => {
    let s = new Storage()
    write_draft(s, draft_key("u", "new"), draft(1, {name: "new"}))
    move_draft(s, "u", "old", "new")
    assert.equal(read_draft(s, draft_key("u", "new")), null)
    move_draft(REFUSED, "u", "old", "new")
    move_draft(null, "u", "old", "new")
})

test("the hash tells versions apart and repeats for the same one", () => {
    assert.equal(draft_hash('{"a":1}'), draft_hash('{"a":1}'))
    assert.notEqual(draft_hash('{"a":1}'), draft_hash('{"a":2}'))
    assert.notEqual(draft_hash(""), draft_hash(" "))
})

test("how long ago, in words", () => {
    let now = 1_000_000_000_000, s = 1000, m = 60 * s, h = 60 * m, d = 24 * h
    let cases = [[0, "a moment ago"], [59 * s, "a moment ago"], [-5 * m, "a moment ago"], [m, "1 minute ago"], [59 * m, "59 minutes ago"],
                 [h, "1 hour ago"], [23 * h, "23 hours ago"], [25 * h, "yesterday"], [2 * d, "2 days ago"], [13 * d, "13 days ago"],
                 [14 * d, "2 weeks ago"], [59 * d, "8 weeks ago"], [60 * d, "2 months ago"], [400 * d, "13 months ago"]]
    for(let [ago, text] of cases)
        assert.equal(time_ago(now - ago, now), text, text)
})
