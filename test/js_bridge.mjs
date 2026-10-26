// one JSON call per stdin line, {mod, fn, args} with mod relative to map/src, or {xhr: {url: body}}; answers {ok} or {err}
import {createInterface} from "node:readline"

const SRC = new URL("../map/src/", import.meta.url)
const mods = {}
for await (const line of createInterface({input: process.stdin})) {
    let out
    try {
        const {mod, fn, args, xhr} = JSON.parse(line)
        if(xhr) {
            Object.assign(globalThis.__xhr, xhr)
            out = {ok: null}
        } else {
            mods[mod] = mods[mod] || await import(new URL(mod, SRC).href)
            const target = fn in mods[mod] ? mods[mod][fn] : (mods[mod].__private__ || {})[fn]
            if(target === undefined)
                throw new Error(mod + " has no " + fn)
            const ok = typeof target === "function" ? target(...(args || [])) : target
            out = {ok: ok === undefined ? null : ok}
        }
    } catch(e) {
        out = {err: String(e)}
    }
    process.stdout.write(JSON.stringify(out) + "\n")
}
