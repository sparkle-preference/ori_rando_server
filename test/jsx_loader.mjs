// node --import ./test/jsx_loader.mjs: map/src modules load in plain node, JSX compiled by the map's own swc
import {register} from "node:module"

register("./jsx_hooks.mjs", import.meta.url, {data: {mapPkg: new URL("../map/package.json", import.meta.url).href}})

// any property, call or construction answers itself, so module-level browser code runs inert
const inert = new Proxy(function () {}, {
    get: (t, k) => k === Symbol.toPrimitive ? () => "" : k === "prototype" ? {} : inert,
    apply: () => inert,
    construct: () => ({}),
})
class Component { constructor(props) { this.props = props } setState() {} }
globalThis.__stub = new Proxy({Component, PureComponent: Component, Fragment: "frag", createRef: () => ({current: null}),
                               createElement: () => null}, {get: (t, k) => k in t ? t[k] : inert})
globalThis.window = globalThis.window || {location: {hostname: "node", search: "", href: "http://node/"}, document: {URL: "http://node/"},
                                          addEventListener() {}, matchMedia: () => ({matches: false})}
// synchronous XHRs at module level answer from globalThis.__xhr, which js_bridge.py fills from the real routes
globalThis.__xhr = {}
globalThis.XMLHttpRequest = class {
    open(method, url) { this.url = url }
    send() { const body = globalThis.__xhr[this.url]; this.status = body === undefined ? 404 : 200; this.responseText = body }
    setRequestHeader() {}
    addEventListener() {}
}
globalThis.alert = globalThis.confirm = () => {}
globalThis.fetch = () => new Promise(() => {})
const element = () => new Proxy({dataset: {}}, {get: (t, k) => k in t ? t[k] : inert})
globalThis.document = globalThis.document || {URL: "http://node/", cookie: "", getElementById: element, querySelector: element}
