import {dev} from './common.js';

// The form keys a frame restores. Hand-authored: it is every key paramsJson reads,
// minus fassWorld and sspOwner, plus the display mirrors and preset chip fields that
// would otherwise lie after a restore.
const HIST_KEYS = [
    "keyMode", "fillAlg", "variations", "paths", "pathMode", "pathDiff", "expPool", "cellFreq",
    "selectedPool", "itemPool", "verboseSpoiler", "senseData",
    "goalModes", "fragCount", "fragReq", "relicCount",
    "bingoLines", "bingoDiff", "bingoGoal", "bingoSquares", "bingoMeta", "bingoDisc",
    "spawn", "spawnSKs", "spawnECs", "spawnHCs", "spawnWeights",
    "fassList",
    "tracking", "players", "playerNames", "coopGenMode", "coopGameMode", "dedupShared",
    "antiBkBias", "shared", "mwShared", "worldSettings", "worldPresets",
    "apMode", "apExport", "apDeathLink",
    "seed", "randomizedWith",
    "sspName", "sspLoaded", "sspLoadedOwner", "sspLoadedWorld", "sspLoadedDesc", "sspLoadedBlob",
]
const HIST_SET = new Set(HIST_KEYS)
const CAP = 200

// The Seed tab lives inside the Collapse that holds the undo buttons, so a frame must
// never send the user back to it.
const restorableTab = (tab) => tab === "seed" ? null : tab

// Positional, so key order is fixed by the const above and blobs compare as strings.
// An emptied number box parses to NaN, and no frame should be able to hold one.
const snap = (state) => {
    let bad = false
    let blob = JSON.stringify(HIST_KEYS.map(k => state[k]),
                              (k, v) => { if(typeof v === "number" && !isFinite(v)) bad = true; return v })
    return bad ? null : blob
}

class History {
    constructor(getState) {
        this.getState = getState
        this.stack = []
        this.index = -1
        // until the first user gesture every settle rewrites frame 0, so the page's own
        // load-time rewrites never become something to undo
        this.live = false
        this.queued = false
        this.suppress = false
        this.gesture = null
        this.pending = null
        this.focused = null
        this.onChange = () => {}
        // a read-only handle for poking at the stack; dev only covers cloudshell
        if(dev || window.location.hostname === "localhost")
            window.seedHistory = this
    }

    attach = () => {
        document.addEventListener("pointerdown", this.onGesture, true)
        document.addEventListener("keydown", this.onKey, true)
        document.addEventListener("focusin", this.onFocusIn, true)
        document.addEventListener("focusout", this.onFocusOut, true)
    }

    detach = () => {
        document.removeEventListener("pointerdown", this.onGesture, true)
        document.removeEventListener("keydown", this.onKey, true)
        document.removeEventListener("focusin", this.onFocusIn, true)
        document.removeEventListener("focusout", this.onFocusOut, true)
        clearTimeout(this.gestureTimer)
    }

    // A capture listener runs before the handler that will queue the settle, so the
    // clear has to be a macrotask or every frame loses its label.
    onGesture = (e) => {
        let anchor = e.target.closest && e.target.closest("[data-hist]")
        let state = this.getState()
        this.live = true
        this.gesture = {ctl: anchor ? anchor.dataset.hist : null,
                        tab: restorableTab(state.activeTab), world: state.fassWorld || 1}
        clearTimeout(this.gestureTimer)
        this.gestureTimer = setTimeout(() => { this.gesture = null }, 0)
        // a click outside the focused input commits whatever was typed into it
        if(this.focused && e.target !== this.focused)
            this.commitFocus()
    }

    onKey = (e) => {
        this.onGesture(e)
        if(e.key === "Enter" && this.focused)
            this.commitFocus()
    }

    // One focus session on one input is one frame, however many keystrokes it took.
    onFocusIn = (e) => {
        if(e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA")
            this.focused = e.target
    }

    onFocusOut = (e) => {
        if(e.target === this.focused)
            this.commitFocus()
    }

    commitFocus = () => {
        this.focused = null
        let blob = this.pending
        this.pending = null
        if(blob)
            this.record(blob)
    }

    touch = () => {
        if(this.queued)
            return
        this.queued = true
        Promise.resolve().then(this.settle)
    }

    // React 16 legacy mode runs a discrete event's whole batch synchronously inside the
    // dispatch, so this microtask reads committed state.
    settle = () => {
        this.queued = false
        if(this.suppress) {
            this.suppress = false
            return
        }
        let blob = snap(this.getState())
        if(blob === null)
            return
        if(this.focused) {
            this.pending = blob
            return
        }
        this.record(blob)
    }

    record = (blob) => {
        if(this.index >= 0 && this.stack[this.index].blob === blob)
            return
        let frame = {blob: blob, ...(this.gesture || {ctl: null, tab: null, world: 1})}
        if(!this.live && this.index >= 0) {
            this.stack[this.index] = frame
            this.onChange()
            return
        }
        this.stack.length = this.index + 1
        this.stack.push(frame)
        if(this.stack.length > CAP)
            this.stack.shift()
        this.index = this.stack.length - 1
        this.onChange()
    }

    canUndo = () => this.index > 0
    canRedo = () => this.index < this.stack.length - 1

    // The tab and control describe the EDGE, so undo and redo of the same edit agree.
    undo = () => {
        if(!this.canUndo())
            return null
        let edge = this.stack[this.index]
        this.index -= 1
        this.onChange()
        return {...this.stack[this.index], tab: edge.tab, world: edge.world, ctl: edge.ctl}
    }

    redo = () => {
        if(!this.canRedo())
            return null
        this.index += 1
        let edge = this.stack[this.index]
        this.onChange()
        return edge
    }
}

export {History, HIST_KEYS, HIST_SET, snap};
