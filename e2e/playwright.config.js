// One worker: the tests share a dev server and a datastore, and seedgen is
// CPU-bound enough that parallel rolls would just trade timeouts around.
const { defineConfig } = require("@playwright/test");

module.exports = defineConfig({
    testDir: "./tests",
    workers: 1,
    retries: 0,
    timeout: 180000,
    use: {
        baseURL: process.env.E2E_BASE_URL || "http://localhost:8080",
        trace: "retain-on-failure",
    },
    reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
});
