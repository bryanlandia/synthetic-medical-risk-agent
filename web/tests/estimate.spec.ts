import { expect, test, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { openAssistant } from "./helpers";

const CONTENT = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "content", "estimate.json"), "utf8"));
const LAB_KEYS: string[] = CONTENT.labs.map((l: { key: string }) => l.key);
const SYMPTOMS: string[] = CONTENT.symptoms;
const SYMPTOM_NAMES: Record<string, string> = { tremor: "Tremor", fatigue: "Fatigue", photophobia: "Light sensitivity", joint_stiffness: "Joint stiffness", dizziness: "Dizziness" };

const openEstimate = async (page: Page) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Estimate a risk" }).click();
  await expect(page.getByTestId("estimate-probability")).toBeVisible();
};
const percent = async (page: Page) => Number.parseInt((await page.getByTestId("estimate-probability").innerText()).replace("%", ""), 10);
const labName = (key: string): string => CONTENT.labs.find((l: { key: string }) => l.key === key).name;
const slider = (page: Page, key: string) => page.getByTestId(`lab-${key}`).getByRole("slider");

test("the committed opening estimate is what the service gives for the opening patient, and it is borderline", async ({ request }) => {
  const response = await request.post("/api/estimate", { data: CONTENT.start });
  expect(response.status()).toBe(200);
  const { estimate } = await response.json();
  expect(estimate.probability).toBeCloseTo(CONTENT.estimate.probability, 9);
  expect(estimate.message).toBe(CONTENT.estimate.message);
  expect(estimate.model_hash).toBe(CONTENT.model_hash);
  expect(CONTENT.estimate.probability).toBeGreaterThanOrEqual(0.4);
  expect(CONTENT.estimate.probability).toBeLessThanOrEqual(0.6);
});

test("the first view is borderline, needs no request, and says the patient is invented", async ({ page }) => {
  const requests: string[] = [];
  page.on("request", (r) => { if (r.url().includes("/api/estimate")) requests.push(r.url()); });
  await openEstimate(page);
  expect(await percent(page)).toBe(Math.round(CONTENT.estimate.probability * 100));
  await expect(page.getByTestId("estimate-band")).toHaveText("In the uncertain range (40% to 60%)");
  await expect(page.getByRole("heading", { name: "Invented patient" })).toBeVisible();
  expect(requests).toEqual([]);
});

test("there is one control for each lab and each symptom and nothing else that changes the estimate", async ({ page }) => {
  await openEstimate(page);
  await expect(page.getByRole("slider")).toHaveCount(8);
  await expect(page.getByRole("switch")).toHaveCount(8);
  for (const key of SYMPTOMS) {
    const group = page.getByTestId(`symptom-${key}`);
    await expect(group.getByRole("group", { name: SYMPTOM_NAMES[key] })).toBeVisible();
    await expect(group.getByRole("button")).toHaveText(["Absent", "Possible", "Present"]);
  }
  await expect(page.getByTestId("estimate-reset")).toBeVisible();
});

test("a lab slider cannot leave the plausible range", async ({ page }) => {
  await openEstimate(page);
  for (const lab of CONTENT.labs) {
    const s = slider(page, lab.key);
    await s.press("End");
    await expect(s).toHaveAttribute("aria-valuenow", String(lab.max));
    await s.press("Home");
    await expect(s).toHaveAttribute("aria-valuenow", String(lab.min));
    expect(Number(await s.getAttribute("aria-valuemin"))).toBe(lab.min);
    expect(Number(await s.getAttribute("aria-valuemax"))).toBe(lab.max);
  }
});

test("moving a lab changes the estimate and the band, and the bars add up to it", async ({ page }) => {
  await openEstimate(page);
  const before = await percent(page);
  await slider(page, "velorin_index").press("End");
  await expect.poll(() => percent(page)).toBeGreaterThan(before);
  await expect(page.getByTestId("estimate-band")).toHaveText("Above the uncertain range");
  await expect(page.getByTestId("estimate-status")).toHaveText("");
  const bars: number[] = await page.locator("[data-contribution]").evaluateAll((els) => els.map((e) => Number(e.getAttribute("data-contribution"))));
  const start = Number((await page.getByTestId("bar-start").innerText()).replace("−", "-").match(/[-+]\d\.\d\d/)![0]);
  const total = start + bars.reduce((a, b) => a + b, 0);
  expect(Math.round(100 / (1 + Math.exp(-total)))).toBeCloseTo(await percent(page), 0);
  expect(bars).toHaveLength(13);
});

test("a symptom toggle changes the estimate in the direction of its bar", async ({ page }) => {
  await openEstimate(page);
  const before = await percent(page);
  await page.getByTestId("symptom-tremor").getByRole("button", { name: "Present" }).click();
  await expect.poll(() => percent(page)).toBeGreaterThan(before);
  await page.getByTestId("symptom-tremor").getByRole("button", { name: "Absent" }).click();
  await expect.poll(() => percent(page)).toBeLessThan(before);
});

test("a lab set to not done shows no value, says so, and its bar is the model's treatment of a missing lab", async ({ page }) => {
  await openEstimate(page);
  await page.getByRole("switch", { name: "Plexa count not done" }).check();
  const lab = page.getByTestId("lab-plexa_count");
  await expect(lab.getByTestId("lab-plexa_count-value")).toHaveText(/^Not done/);
  await expect(lab).not.toContainText(/\d+ x10\^9\/L/);
  await expect(lab.locator("input[type=range]")).toBeDisabled();
  await expect(lab.getByRole("slider")).toHaveCount(0); // the thumb is hidden: no position stands in for a value
  await expect(page.getByTestId("not-done-note")).toContainText("Plexa count");
  await expect.poll(async () => (await page.getByTestId("bar-plexa_count").getAttribute("data-contribution")) !== String(CONTENT.estimate.breakdown.find((r: { key: string }) => r.key === "plexa_count").contribution)).toBe(true);
  await page.getByRole("switch", { name: "Plexa count not done" }).uncheck();
  await expect(lab.getByTestId("lab-plexa_count-value")).toContainText("260 x10^9/L"); // the value it had comes back
});

test("Reset restores every input and the opening estimate", async ({ page }) => {
  await openEstimate(page);
  await slider(page, "tarnic_acid").press("Home");
  await page.getByRole("switch", { name: "Halvin titer not done" }).check();
  await page.getByTestId("symptom-dizziness").getByRole("button", { name: "Present" }).click();
  await expect.poll(() => percent(page)).not.toBe(Math.round(CONTENT.estimate.probability * 100));
  await page.getByTestId("estimate-reset").click();
  expect(await percent(page)).toBe(Math.round(CONTENT.estimate.probability * 100));
  for (const key of LAB_KEYS) {
    const lab = CONTENT.labs.find((l: { key: string }) => l.key === key);
    await expect(slider(page, key)).toHaveAttribute("aria-valuenow", String(CONTENT.start.labs[key]));
    await expect(page.getByTestId(`lab-${key}-value`)).toContainText(`${CONTENT.start.labs[key].toFixed(lab.decimals)} ${lab.unit}`);
  }
  await expect(page.getByRole("switch", { checked: true })).toHaveCount(0);
  for (const key of SYMPTOMS) {
    const pressed = page.getByTestId(`symptom-${key}`).getByRole("button", { pressed: true });
    await expect(pressed).toHaveText(CONTENT.start.symptoms[key][0].toUpperCase() + CONTENT.start.symptoms[key].slice(1));
  }
});

test("a burst of slider moves sends few requests and the page shows the last position's estimate", async ({ page }) => {
  await openEstimate(page);
  const sent: string[] = [];
  page.on("request", (r) => { if (r.url().endsWith("/api/estimate")) sent.push(r.postData() ?? ""); });
  const s = slider(page, "velorin_index");
  await s.focus();
  for (let i = 0; i < 40; i++) await page.keyboard.press("ArrowRight");
  await expect.poll(() => sent.length).toBeGreaterThan(0);
  await page.waitForTimeout(600);
  expect(sent.length).toBeLessThan(20);
  const last = JSON.parse(sent.at(-1)!);
  expect(last.labs.velorin_index).toBe(Number(await s.getAttribute("aria-valuenow")));
});

test("a rate-limited estimate keeps the last number and tells the visitor to slow down", async ({ page }) => {
  await openEstimate(page);
  await page.route("**/api/estimate", (route) => route.fulfill({ status: 429, contentType: "application/json", headers: { "retry-after": "20" }, body: JSON.stringify({ error: { code: "rate_limited", message: "wait", retry_after: 20 } }) }));
  const before = await percent(page);
  await slider(page, "velorin_index").press("End");
  await expect(page.getByTestId("estimate-status")).toContainText("slow down");
  expect(await percent(page)).toBe(before);
});

test("the scenario's text is plain: invented patient, fictional disease, no advice and no treatment", async ({ page }) => {
  await openEstimate(page);
  const text = (await page.getByRole("main").innerText()).toLowerCase();
  expect(text).toContain("invented");
  expect(text).toContain("fictional");
  for (const phrase of ["diagnosis of", "you have", "your risk"]) expect(text).not.toContain(phrase);
  const doses = /\b\d+\s?(mg|mcg|ml)\b\s*(daily|twice|per day)|\b(take|prescribe|dose)\b/;
  expect(text).not.toMatch(doses);
  expect(text).not.toMatch(/\b(order|schedule)\b.*\b(pet|scan|test)\b/);
  for (const lab of CONTENT.labs) expect(text).toContain(lab.name.toLowerCase());
});

test("the free-text box is collapsed on open and sends nothing", async ({ page }) => {
  const sent: string[] = [];
  page.on("request", (r) => { if (r.url().endsWith("/api/analyze")) sent.push(r.url()); });
  await openEstimate(page);
  await expect(page.getByRole("textbox", { name: "Message" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Type your own text for the assistant" })).toHaveAttribute("aria-expanded", "false");
  expect(sent).toEqual([]);
  await page.getByRole("button", { name: "Type your own text for the assistant" }).click();
  await expect(page.getByRole("textbox", { name: "Message" })).toBeVisible();
});

test("the free-text box is only in Estimate a risk, and sends one independent message", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "How it works" }).click();
  for (const name of ["Model card", "About this project"]) {
    await page.getByRole("menuitem", { name }).click();
    await expect(page.getByRole("textbox", { name: "Message" })).toHaveCount(0);
    await page.getByRole("button", { name: "How it works" }).click();
  }
  await page.keyboard.press("Escape");
  await openAssistant(page);
  const bodies: string[] = [];
  page.on("request", (r) => { if (r.url().endsWith("/api/analyze")) bodies.push(r.postData() ?? ""); });
  for (const text of ["first note: tremor present", "second note: tremor absent"]) {
    await page.getByRole("textbox", { name: "Message" }).fill(text);
    await page.getByRole("button", { name: "Send", exact: true }).click();
    await expect(page.getByTestId("probability")).toBeVisible();
  }
  expect(bodies.map((b) => JSON.parse(b))).toEqual([{ message: "first note: tremor present" }, { message: "second note: tremor absent" }]);
});

test("the estimate is a large labelled figure, the largest text in its block, and not a verdict colour", async ({ page }) => {
  await openEstimate(page);
  const f = await page.getByTestId("estimate-probability").evaluate((el) => {
    const px = (e: Element) => parseFloat(getComputedStyle(e).fontSize);
    const block = el.closest(".risk-figure")!.parentElement!;
    const others = Array.from(block.querySelectorAll("*")).filter((e) => e !== el && e.childElementCount === 0 && e.textContent?.trim()).map(px);
    return { size: px(el), rem: px(document.documentElement), largest: Math.max(...others), color: getComputedStyle(el).color };
  });
  expect(f.size).toBeGreaterThanOrEqual(3.5 * f.rem);
  expect(f.size).toBeGreaterThan(f.largest);
  expect(f.color).toBe("rgb(0, 105, 107)");
  await expect(page.getByLabel("Estimate", { exact: true })).toContainText("Estimated risk of Velorin-Kessler syndrome (fictional)");
});
