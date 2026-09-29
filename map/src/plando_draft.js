// The plando editor's unsaved edits, one entry per plando in this browser. Storage may be missing, full or
// throwing; nothing here throws, and a write says how it went. Pure, so plain node loads it (test/plando_draft_test.mjs).

const DRAFT_PREFIX = "plando_draft:"
// past this many, the oldest drafts go; a full storage evicts them sooner
const DRAFT_KEEP = 20

// plando names can't hold a slash, so user/name never collides
const draft_key = (user, name) => `${DRAFT_PREFIX}${user || ""}/${name || ""}`

function read_draft(storage, key) {
    try {
        let d = JSON.parse(storage.getItem(key))
        return d && typeof d === "object" && d.data && typeof d.data === "object" && typeof d.at === "number" ? d : null
    } catch(e) {
        return null
    }
}

function remove_draft(storage, key) {
    try {
        storage.removeItem(key)
    } catch(e) { /* storage off: nothing was kept */ }
}

function draft_keys(storage) {
    let found = []
    try {
        for(let k = 0; k < storage.length; k++) {
            let name = storage.key(k)
            if(name && name.startsWith(DRAFT_PREFIX))
                found.push(name)
        }
    } catch(e) {
        return []
    }
    return found
}

// every draft but this one, oldest first; an unreadable one counts as oldest
function older_drafts(storage, key) {
    let at = (name) => (read_draft(storage, name) || {at: 0}).at
    return draft_keys(storage).filter(name => name !== key).map(name => [at(name), name]).sort((x, y) => x[0] - y[0]).map(p => p[1])
}

const is_quota = (e) => !!e && (e.name === "QuotaExceededError" || e.name === "NS_ERROR_DOM_QUOTA_REACHED" || e.code === 22 || e.code === 1014)

// "ok"; "full" when even every other draft gone left no room, and the old one stays as it was; "off"
function write_draft(storage, key, draft, keep = DRAFT_KEEP) {
    let text = JSON.stringify(draft)
    let others = null
    for(;;) {
        try {
            storage.setItem(key, text)
            break
        } catch(e) {
            if(!is_quota(e))
                return "off"
            others = others || older_drafts(storage, key)
            if(!others.length)
                return "full"
            remove_draft(storage, others.shift())
        }
    }
    if(draft_keys(storage).length > keep)
        older_drafts(storage, key).slice(0, draft_keys(storage).length - keep).forEach(name => remove_draft(storage, name))
    return "ok"
}

// FNV-1a: which saved version a draft began from, without storing that version again
function draft_hash(text) {
    let h = 0x811c9dc5
    for(let k = 0; k < text.length; k++) {
        h ^= text.charCodeAt(k)
        h = Math.imul(h, 0x01000193) >>> 0
    }
    return h.toString(36)
}

// A stored draft against the plando as it loaded (loaded: its snapshot as JSON): null when there is nothing
// to offer, else when the draft was written and whether the plando has been saved since it began.
function draft_offer(draft, loaded) {
    if(!draft || JSON.stringify(draft.data) === loaded)
        return null
    // a renamed plando is compared under the name the draft began from
    let base = draft.from ? renamed(loaded, draft.from) : loaded
    return {at: draft.at, saved_since: draft.base !== draft_hash(base)}
}

// a snapshot as JSON under another name, as the server's rename copies a plando
function renamed(text, name) {
    try {
        let data = JSON.parse(text)
        data.name = name
        if(typeof data.flagLine === "string")
            data.flagLine = data.flagLine.slice(0, data.flagLine.lastIndexOf("|") + 1) + name
        return JSON.stringify(data)
    } catch(e) {
        return text
    }
}

// A renamed plando takes its draft along, and a draft already under the new name was a dead plando's.
function move_draft(storage, user, from, to) {
    let old_key = draft_key(user, from), new_key = draft_key(user, to)
    let draft = read_draft(storage, old_key)
    remove_draft(storage, new_key)
    if(!draft)
        return
    let data = JSON.parse(renamed(JSON.stringify(draft.data), to))
    if(write_draft(storage, new_key, {...draft, from: draft.from || from, data: data}) === "ok")
        remove_draft(storage, old_key)
}

// after a save, the stored draft goes if this tab wrote it or it holds just what was saved
const draft_saved = (draft, saved, tab) => !!draft && (draft.tab === tab || JSON.stringify(draft.data) === saved)

function time_ago(at, now) {
    let s = Math.max(0, (now - at) / 1000)
    let ago = (n, unit) => `${n} ${unit}${n === 1 ? "" : "s"} ago`
    if(s < 60)
        return "a moment ago"
    if(s < 3600)
        return ago(Math.floor(s / 60), "minute")
    if(s < 86400)
        return ago(Math.floor(s / 3600), "hour")
    if(s < 2 * 86400)
        return "yesterday"
    if(s < 14 * 86400)
        return ago(Math.floor(s / 86400), "day")
    if(s < 60 * 86400)
        return ago(Math.floor(s / (7 * 86400)), "week")
    return ago(Math.floor(s / (30 * 86400)), "month")
}

export {DRAFT_KEEP, draft_key, read_draft, write_draft, remove_draft, move_draft, draft_hash, draft_offer, draft_saved, time_ago};
