import { expect, test, type Page } from "@playwright/test";
import { ANALYTICS_PORT, STUB_PORT } from "../playwright.config";
import { CASES } from "./helpers";

// PostHog drops events from anything that looks like a bot, and automated Chromium says so three ways: the user agent, the
// client-hint brands ("HeadlessChrome") and navigator.webdriver. The tests present an ordinary browser instead.
const UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36";
test.use({ baseURL: `http://127.0.0.1:${ANALYTICS_PORT}`, userAgent: UA });
const STUB = `http://127.0.0.1:${STUB_PORT}`;

type Seen = { method: string; path: string; query: string; body: string };
type Ev = { event: string; properties: Record<string, unknown> };

async function seen(page: Page): Promise<Seen[]> {
  return (await page.request.get(`${STUB}/__requests`)).json();
}
function events(requests: Seen[]): Ev[] {
  const out: Ev[] = [];
  const take = (x: unknown) => {
    if (Array.isArray(x)) x.forEach(take);
    else if (x && typeof x === "object") {
      const o = x as Record<string, unknown>;
      if (typeof o.event === "string") out.push(o as unknown as Ev);
      else if (o.batch) take(o.batch);
    }
  };
  for (const r of requests) {
    if (!/\/(e|i\/v0\/e|batch|capture)\/?$/.test(r.path)) continue;
    try { take(JSON.parse(r.body)); } catch { /* not a JSON capture body */ }
  }
  return out;
}
async function until<T>(read: () => Promise<T>, ok: (v: T) => boolean, ms = 12_000): Promise<T> {
  const end = Date.now() + ms;
  let v = await read();
  while (!ok(v) && Date.now() < end) { await new Promise((r) => setTimeout(r, 400)); v = await read(); }
  return v;
}
async function reset(page: Page) { await page.request.post(`${STUB}/__reset`); }

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "webdriver", { get: () => false });
    Object.defineProperty(navigator, "userAgentData", { get: () => ({ brands: [{ brand: "Chromium", version: "140" }], mobile: false, platform: "macOS" }) });
  });
  await reset(page);
});

test("the notice is shown and every analytics request goes to the site's own address", async ({ page, baseURL }) => {
  const origins = new Set<string>();
  page.on("request", (r) => origins.add(new URL(r.url()).origin));
  await page.goto("/");
  await expect(page.getByTestId("analytics-notice")).toContainText("counted anonymously");
  await expect(page.getByTestId("analytics-notice")).toContainText("Nothing you type is collected");
  await expect(page.getByTestId("analytics-notice")).toContainText("your screen is not recorded");
  const got = await until(() => seen(page), (s) => events(s).length > 0);
  expect(events(got).length).toBeGreaterThan(0); // the control: something was sent, and all of it went to the site itself
  expect([...origins]).toEqual([new URL(baseURL!).origin]);
});

async function openBehind(page: Page, item: string) {
  await page.getByRole("button", { name: "Behind the demo" }).click();
  await page.getByRole("menuitem", { name: item }).click();
}
const openFirstCase = async (page: Page) => {
  await page.getByRole("button", { name: CASES[0].request_code }).click();
  await expect(page.getByTestId("packet-checklist")).toBeVisible();
};

test("one page view per load carries the ref, and switching views does not send another", async ({ page }) => {
  await page.goto("/?ref=Ode!!");
  await openBehind(page, "About this project");
  await openBehind(page, "Try the assistant");
  const all = events(await until(() => seen(page), (s) => events(s).some((e) => e.event === "ui_click")));
  const views = all.filter((e) => e.event === "$pageview");
  expect(views).toHaveLength(1);
  expect(views[0].properties.ref).toBe("ode");
});

test("each countable element sends one named click, and empty space and typing send none", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("analytics-notice")).toBeVisible();
  await page.mouse.click(2, 300); // empty space
  await page.getByRole("button", { name: "Returned", exact: true }).click();
  await page.getByRole("button", { name: "All", exact: true }).click();
  await openFirstCase(page);
  await page.getByText("Show the message sent to the service").click();
  await page.getByRole("button", { name: "Back to the queue" }).click();
  await openBehind(page, "Try the assistant");
  await page.getByRole("button", { name: "A treatment question" }).click();
  await page.getByLabel("Message").pressSequentially("typing is not counted");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Declined" })).toBeVisible();
  await openBehind(page, "About this project");
  await page.locator("article.doc a").first().click({ modifiers: [] }).catch(() => {});
  const all = events(await until(() => seen(page), (s) => events(s).filter((e) => e.event === "ui_click").length >= 10));
  const clicks = all.filter((e) => e.event === "ui_click").map((e) => e.properties.element);
  expect(clicks).toEqual(expect.arrayContaining([
    "filter:returned", "filter:all", "case:01", "sent_message_expander", "menu:behind", "nav:free", "example:treatment-question", "send_free_text", "nav:about",
  ]));
  for (const c of clicks) expect(String(c)).toMatch(NAME);
  expect(all.some((e) => e.event === "$autocapture")).toBe(false);
});

const NAME = /^(sent_message_expander|send_free_text|release|return|close|confirm|reset_demo|help|intro_dismiss|menu:behind|packet_copy|packet_print|nav:[a-z]+|filter:[a-z-]+|case:\d{2}|example:[a-z-]+|link:[a-z0-9.-]+)$/;

test("no typed text, reply or probability is ever sent, and no screen recording is requested", async ({ page }) => {
  await page.goto("/");
  await openBehind(page, "Try the assistant");
  const typed = "ZXQ-typed-text-7731 Velorin index 128 mg/dL. Tremor present.";
  await page.getByLabel("Message").fill(typed);
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByTestId("probability")).toBeVisible();
  const reply = (await page.getByTestId("reply").innerText()).slice(0, 40);
  const prob = await page.getByTestId("probability").innerText();
  await page.getByRole("button", { name: "Back to the queue" }).click();
  const all = await until(() => seen(page), (s) => events(s).some((e) => e.event === "result_shown"));
  const bodies = all.map((r) => r.body + r.path + r.query).join("\n");
  expect(bodies).not.toContain("ZXQ-typed-text");
  expect(bodies).not.toContain("Tremor present");
  expect(bodies).not.toContain(reply);
  expect(bodies).not.toContain(prob);
  const results = events(all).filter((e) => e.event === "result_shown");
  expect(results.map((e) => e.properties)).toEqual([expect.objectContaining({ source: "free_text", kind: "scored" })]);
  expect(all.some((r) => /recorder|\/s\/?$|snapshot/i.test(r.path))).toBe(false);
});

test("a return note, a rationale, a patient id and a criterion status are never sent, and the decisions are counted by name only", async ({ page }) => {
  const NOTE = "ZXQ-return-note-5521 please recheck the imaging date";
  const WHY = "ZXQ-rationale-9913 reviewed the chart and the history supports it";
  await page.goto("/");
  // case 01: return it with a note
  await openFirstCase(page);
  await page.getByRole("button", { name: "Return with a note" }).click();
  await page.getByTestId("return-note").fill(NOTE);
  await page.getByRole("dialog").getByRole("button", { name: "Return", exact: true }).click();
  await page.getByRole("button", { name: "Back to the queue" }).click();
  // another case that can be released with a rationale (unmet only) or freely
  for (const c of CASES.slice(1)) {
    await page.getByRole("button", { name: c.request_code }).click();
    await expect(page.getByTestId("packet-checklist")).toBeVisible();
    const rationale = page.getByTestId("rationale");
    if (await rationale.count()) {
      await rationale.fill(WHY);
      await page.getByRole("button", { name: "Release", exact: true }).click();
      await page.getByRole("dialog").getByRole("button", { name: "Release", exact: true }).click();
      break;
    }
    await page.getByRole("button", { name: "Back to the queue" }).click();
  }
  const all = await until(() => seen(page), (s) => events(s).filter((e) => e.event === "ui_click").length >= 6);
  const sent = all.map((r) => r.body + r.path + r.query).join("\n");
  for (const secret of ["ZXQ-return-note", "ZXQ-rationale", "recheck the imaging", ...CASES.map((c) => c.patient_id), "Unmet", "Unknown", "above the policy threshold"]) {
    expect(sent, secret).not.toContain(secret);
  }
  const clicks = events(all).filter((e) => e.event === "ui_click").map((e) => e.properties.element);
  expect(clicks).toEqual(expect.arrayContaining(["return", "confirm", "release"]));
  for (const c of clicks) expect(String(c)).toMatch(NAME);
});

test("nothing is written to cookies or browser storage by a visit that only looks around", async ({ page, context }) => {
  await page.goto("/");
  await openBehind(page, "About this project");
  const got = await until(() => seen(page), (s) => events(s).length > 0);
  expect(events(got).length).toBeGreaterThan(0); // the control: events were sent, and still nothing was stored
  expect(await context.cookies()).toEqual([]);
  expect(await page.evaluate(() => [localStorage.length, sessionStorage.length])).toEqual([0, 0]);
});

test("pressing the opt-out control stops counting for the rest of the visit", async ({ page }) => {
  await page.goto("/");
  const before = await until(() => seen(page), (s) => events(s).length > 0);
  expect(events(before).length).toBeGreaterThan(0); // the control: counting works until the visitor opts out
  await page.getByRole("button", { name: "Don't count my visit" }).click();
  await expect(page.getByTestId("analytics-notice")).toContainText("Counting is off");
  await reset(page);
  await openFirstCase(page);
  await page.waitForTimeout(5000);
  expect(await seen(page)).toEqual([]);
  // the choice outlasts the visit: a reload starts nothing and shows no notice
  await page.reload();
  await page.waitForTimeout(4000);
  await expect(page.getByTestId("analytics-notice")).toHaveCount(0);
  expect(await seen(page)).toEqual([]);
});

for (const [name, script] of [
  ["Do Not Track", () => Object.defineProperty(navigator, "doNotTrack", { get: () => "1" })],
  ["Global Privacy Control", () => Object.defineProperty(navigator, "globalPrivacyControl", { get: () => true })],
] as const) {
  test(`${name} starts nothing and shows no notice`, async ({ page }) => {
    await page.addInitScript(script);
    await page.goto("/");
    await openFirstCase(page);
    await page.waitForTimeout(5000);
    await expect(page.getByTestId("analytics-notice")).toHaveCount(0);
    expect(await seen(page)).toEqual([]);
  });
}

test("every element that must be counted carries a name", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator('[data-track="nav:queue"]')).toHaveCount(1);
  await expect(page.locator('[data-track="menu:behind"]')).toHaveCount(1);
  await expect(page.locator('[data-track^="filter:"]')).toHaveCount(6);
  await expect(page.locator('[data-track^="case:"]')).toHaveCount(30);
  for (const name of ["intro_dismiss", "reset_demo"]) await expect(page.locator(`[data-track="${name}"]`)).toHaveCount(1);
  await openFirstCase(page);
  for (const name of ["sent_message_expander", "release", "return", "close"]) await expect(page.locator(`[data-track="${name}"]`)).toHaveCount(1);
  await expect(page.locator(`[data-track="help"]`)).toHaveCount(2); // the packet help and the "What produced this page?" key share the name
  await page.getByRole("button", { name: "Back to the queue" }).click();
  await page.getByRole("button", { name: "Behind the demo" }).click();
  for (const nav of ["free", "card", "about"]) await expect(page.locator(`[data-track="nav:${nav}"]`)).toHaveCount(1);
  await page.getByRole("menuitem", { name: "Try the assistant" }).click();
  await expect(page.locator('[data-track^="example:"]')).toHaveCount(4);
  await expect(page.locator('[data-track="send_free_text"]')).toHaveCount(1);
  await openBehind(page, "About this project");
  await expect(page.locator('article.doc a[data-track^="link:"]').first()).toBeVisible();
});
