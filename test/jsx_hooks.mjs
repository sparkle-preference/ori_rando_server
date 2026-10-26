// module hooks for jsx_loader.mjs; module-private top-level bindings are reachable as __private__
import {readFileSync} from "node:fs"
import {fileURLToPath} from "node:url"
import {createRequire} from "node:module"

let swc
const STUBBED = /^(react|react-dom|leaflet|he|react-.*|reactstrap.*)$/
const IMPORT = /import\s+(?:([\w$]+)\s*,?\s*)?(?:\{([^}]*)\}\s*)?(?:\*\s+as\s+([\w$]+)\s*)?from\s*["']([^"']+)["'];?/g
const TOP = /^(?:export\s+)?(?:const|let|var|class|(?:async\s+)?function\*?)\s+([A-Za-z_$][\w$]*)/gm
const inMap = (url) => url && url.startsWith("file:") && url.includes("/map/src/")

export function initialize({mapPkg}) {
    swc = createRequire(mapPkg)("@swc/core")
}

function unstub(code) {
    return code.replace(IMPORT, (all, def, named, star, spec) => {
        if(!STUBBED.test(spec))
            return all
        let out = []
        if(def) out.push("const " + def + " = globalThis.__stub;")
        if(star) out.push("const " + star + " = globalThis.__stub;")
        if(named) out.push("const {" + named.replace(/\s+as\s+/g, ": ") + "} = globalThis.__stub;")
        return out.join(" ")
    }).replace(/import\s+["'][^"']+\.css["'];?/g, "")
}

export async function resolve(spec, ctx, next) {
    if(inMap(ctx.parentURL) && /^\.\.?\//.test(spec) && !/\.\w+$/.test(spec))
        spec += ".js"
    return next(spec, ctx)
}

export async function load(url, ctx, next) {
    if(inMap(url) && url.endsWith(".json"))
        return {format: "module", source: "export default " + readFileSync(fileURLToPath(url), "utf8"), shortCircuit: true}
    if(inMap(url) && url.endsWith(".js")) {
        let src = readFileSync(fileURLToPath(url), "utf8")
        let code = unstub(swc.transformSync(src, {jsc: {parser: {syntax: "ecmascript", jsx: true}, target: "es2022"},
                                                  module: {type: "es6"}}).code)
        let names = [...new Set([...code.matchAll(TOP)].map(m => m[1]))]
        return {format: "module", source: code + "\nexport const __private__ = {" + names.join(", ") + "};\n", shortCircuit: true}
    }
    return next(url, ctx)
}
