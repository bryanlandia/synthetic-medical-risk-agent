import { expect, test, type Page } from "@playwright/test";
import { classify, dialogButton, first, openCase, waitForPacket } from "./helpers";

let kinds: Awaited<ReturnType<typeof classify>>;
test.beforeAll(async ({ request }) => {
  kinds = await classify(request);
});

const active = (page: Page) => page.evaluate(() => (document.activeElement as HTMLElement | null)?.innerText?.trim() ?? "");
async function tabTo(page: Page, name: string, limit = 40) {
  for (let i = 0; i < limit; i++) {
    if ((await active(page)) === name) return;
    await page.keyboard.press("Tab");
  }
  throw new Error(`never reached "${name}" by Tab`);
}

test("a case can be opened, returned and its dialog closed using only the keyboard", async ({ page }) => {
  await page.goto("/");
  const c = first(kinds, "blocked");
  await page.getByRole("button", { name: c.request_code }).focus();
  await page.keyboard.press("Enter");
  await waitForPacket(page);
  await tabTo(page, "Return with a note");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.type("Please add the missing result.");
  await tabTo(page, "Return");
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("case-status")).toHaveText("Returned");
  await expect(page.getByRole("dialog")).toHaveCount(0);
});

test("Escape closes a dialog and focus returns to the control that opened it", async ({ page }) => {
  await page.goto("/");
  await openCase(page, first(kinds, "unmet"));
  await waitForPacket(page);
  for (const name of ["Return with a note", "Close, criteria not met"]) {
    const opener = page.getByRole("button", { name, exact: true });
    await opener.focus();
    await page.keyboard.press("Enter");
    await expect(page.getByRole("dialog")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await expect(opener).toBeFocused();
  }
});

test("a rationale can be typed and a release confirmed with the keyboard alone", async ({ page }) => {
  await page.goto("/");
  await openCase(page, first(kinds, "unmet"));
  await waitForPacket(page);
  await page.getByTestId("rationale").focus();
  await page.keyboard.type("I have reviewed the chart and the history supports this request.");
  await tabTo(page, "Release");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("dialog")).toBeVisible();
  await dialogButton(page, "Release").focus();
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("case-status")).toHaveText("Released");
});

test("the controls have visible focus", async ({ page }) => {
  await page.goto("/");
  const button = page.getByRole("button", { name: "Reset demo" });
  await button.focus();
  const outline = await button.evaluate((el) => {
    const s = getComputedStyle(el);
    return `${s.outlineStyle}|${s.outlineWidth}|${s.boxShadow}|${s.backgroundColor}`;
  });
  expect(outline).not.toBe("none|0px|none|rgba(0, 0, 0, 0)");
});

test("no verdict or care-gating wording appears in the queue, a case in each state, or a released packet", async ({ page }) => {
  const banned = /\b(approved|denied|eligible|qualifies)\b|should not be scanned|do not scan|not recommended|withhold|deny care/i;
  await page.goto("/");
  const texts: string[] = [await page.locator("main").innerText()];
  for (const kind of ["releasable", "blocked", "unmet"] as const) {
    await openCase(page, first(kinds, kind));
    await waitForPacket(page);
    texts.push(await page.locator("main").innerText());
    await page.getByRole("button", { name: "Back to the queue" }).click();
  }
  const c = first(kinds, "releasable");
  await openCase(page, c);
  await page.getByRole("button", { name: "Release", exact: true }).click();
  await dialogButton(page, "Release").click();
  texts.push(await page.locator("main").innerText());
  for (const t of texts) expect(t).not.toMatch(banned);
});
