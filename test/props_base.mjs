// fast-check runs for test/*_props.mjs, scaled by the same HYPOTHESIS_PROFILE as the python suite
import * as fcmod from "fast-check"

const PROFILE = process.env.HYPOTHESIS_PROFILE || "dev"
const SCALE = {dev: 0.2, ci: 1, deep: 5}[PROFILE]
if(SCALE === undefined)
    throw new Error("unknown HYPOTHESIS_PROFILE " + PROFILE)

export const fc = fcmod.default || fcmod
export const runs = (n) => Math.max(1, Math.round(n * SCALE))
// ci draws the same inputs every run, as the python suite's ci profile does
if(PROFILE === "ci")
    fc.configureGlobal({seed: 20261026})
