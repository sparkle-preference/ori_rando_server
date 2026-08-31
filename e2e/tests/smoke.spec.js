// The behaviors nothing else can see: these run a real browser against the
// compose dev stack, so they catch the class of bug where the server is right,
// the bundle compiles, and the page still does the wrong thing.
const { test, expect } = require("@playwright/test");

test("the generator rolls a seed down to a download button", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "Generate Seed" }).click();
    // the seed tab is the payoff: a per-player row with a working main button
    await expect(
        page.getByRole("link", { name: /Download Seed|Open Bingo Board/ }).first()
    ).toBeVisible({ timeout: 150000 });
});

test("undo arms on a real change and takes it back", async ({ page }) => {
    await page.goto("/");
    // the last-seed auto-restore lands async and would swallow an early click
    await page.waitForLoadState("networkidle");
    const starved = page.getByRole("button", { name: "Starved", exact: true });
    const undo = page.locator('button[title="Undo"]');
    await expect(undo).toBeVisible();
    await expect(undo).toHaveClass(/btn-outline/); // fresh page: nothing to undo
    const wasActive = /(^| )active( |$)/.test(await starved.getAttribute("class"));
    await starved.click();
    await expect(undo).not.toHaveClass(/btn-outline/);
    await undo.click();
    // the click is taken back, and the stack is empty again
    const isActive = /(^| )active( |$)/.test(await starved.getAttribute("class"));
    expect(isActive).toBe(wasActive);
    await expect(undo).toHaveClass(/btn-outline/);
});

test("a bingo board's squares carry their help", async ({ page }) => {
    await page.goto("/?fromBingo=1");
    // the redirect opens the board in a new tab; follow it there
    const [board] = await Promise.all([
        page.waitForEvent("popup", { timeout: 150000 }),
        page.getByRole("button", { name: "Generate Seed" }).click(),
    ]);
    await board.waitForURL(/bingo\/board/, { timeout: 30000 });
    await board.getByRole("button", { name: "Create Game" }).click();
    const cards = board.locator(".card");
    await expect(cards).toHaveCount(25, { timeout: 60000 });
    // every square renders its "?" (the server-side sweep guarantees the text;
    // this guarantees the rendering path), and one actually opens
    await expect(board.locator(".card-footer button", { hasText: "?" })).toHaveCount(25);
    await board.locator(".card-footer button", { hasText: "?" }).first().click();
    await expect(board.locator(".popover-body")).not.toBeEmpty();
});
