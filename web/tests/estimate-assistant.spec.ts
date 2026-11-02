import { expect, test, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { CASES, openCase, waitForPacket } from "./helpers";
import { GUARDS } from "../lib/copy";

const CONTENT = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "content", "estimate.json"), "utf8"));

const openEstimate = async (page: Page) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Estimate a risk" }).click();
  await expect(page.getByTestId("estimate-probability")).toBeVisible();
};
const percent = async (page: Page) => Number.parseInt((await page.getByTestId("estimate-probability").innerText()).replace("%", ""), 10);
const slider = (page: Page, key: string) => page.getByTestId(`lab-${key}`).getByRole("slider");
const settled = (page: Page) => expect(page.getByTestId("send-patient")).toBeEnabled();

async function lowPatient(page: Page) {
  await slider(page, "velorin_index").press("Home");
  await page.getByTestId("symptom-tremor").getByRole("button", { name: "Absent" }).click();
  await expect.poll(() => percent(page)).toBeLessThanOrEqual(5);
  await settled(page);
}

test("sending the patient shows the assistant's number beside the dial's, and they agree", async ({ page }) => {
  await openEstimate(page);
  await slider(page, "tarnic_acid").press("End");
  await expect.poll(() => percent(page)).toBeGreaterThan(Math.round(CONTENT.estimate.probability * 100));
  await settled(page);
  const dial = await percent(page);
  await page.getByTestId("send-patient").click();
  await expect(page.getByTestId("compare-assistant")).toBeVisible();
  await expect(page.getByTestId("compare-dial")).toHaveText(`${dial}%`);
  await expect(page.getByTestId("compare-assistant")).toHaveText(`${dial}%`);
  await expect(page.getByTestId("guard-callout")).toContainText("Same number");
});

test("the message the page sends is the message the service made, and the assistant's number is the service's to within 0.001", async ({ page, request }) => {
  await openEstimate(page);
  const sent: string[] = [];
  page.on("request", (r) => { if (r.url().endsWith("/api/analyze")) sent.push(JSON.parse(r.postData() ?? "{}").message); });
  await page.getByTestId("send-patient").click();
  await expect(page.getByTestId("compare-assistant")).toBeVisible();
  expect(sent).toEqual([CONTENT.estimate.message]);
  const said = await (await request.post("/api/analyze", { data: { message: sent[0] } })).json();
  expect(Math.abs(said.analysis.report.probability - CONTENT.estimate.probability)).toBeLessThan(0.001);
  await page.getByRole("button", { name: "Show the message sent to the assistant" }).click();
  await expect(page.getByTestId("patient-message")).toHaveText(CONTENT.estimate.message);
});

test("a hidden instruction leaves the assistant's number at the dial's, and the page says it was treated as text", async ({ page }) => {
  await openEstimate(page);
  const sent: string[] = [];
  page.on("request", (r) => { if (r.url().endsWith("/api/analyze")) sent.push(JSON.parse(r.postData() ?? "{}").message); });
  await page.getByTestId("guard-injection").click();
  await expect(page.getByTestId("compare-assistant")).toBeVisible();
  expect(sent[0]).toBe(`${CONTENT.estimate.message}\n${GUARDS.injection.text}`);
  await expect(page.getByTestId("compare-assistant")).toHaveText(await page.getByTestId("compare-dial").innerText());
  await expect(page.getByTestId("guard-callout")).toContainText("Instruction treated as text");
});

test("when the honest result is already low, the page says the run cannot show the instruction was ignored", async ({ page }) => {
  await openEstimate(page);
  await lowPatient(page);
  await page.getByTestId("guard-injection").click();
  await expect(page.getByTestId("compare-assistant")).toBeVisible();
  await expect(page.getByTestId("guard-callout")).toContainText("cannot show whether the instruction was ignored");
});

test("a treatment question added to the patient is declined, with its reason and no number", async ({ page }) => {
  await openEstimate(page);
  await page.getByTestId("guard-treatment").click();
  await expect(page.getByTestId("patient-result").getByRole("heading", { name: "Declined" })).toBeVisible();
  await expect(page.getByTestId("guard-callout")).toContainText("Declined, as it should be");
  await expect(page.getByTestId("patient-result")).toContainText("a treatment request");
  await expect(page.getByTestId("compare-assistant")).toHaveCount(0);
  await expect(page.getByTestId("probability")).toHaveCount(0);
});

test("an off-topic question is declined with no number", async ({ page }) => {
  await openEstimate(page);
  await page.getByTestId("guard-offtopic").click();
  await expect(page.getByTestId("patient-result").getByRole("heading", { name: "Declined" })).toBeVisible();
  await expect(page.getByTestId("compare-assistant")).toHaveCount(0);
  await expect(page.getByTestId("probability")).toHaveCount(0);
});

test("the buttons wait while the estimate is updating, so a stale patient is never sent", async ({ page }) => {
  await openEstimate(page);
  await page.route("**/api/estimate", async (route) => { await new Promise((r) => setTimeout(r, 800)); await route.continue(); });
  await slider(page, "velorin_index").press("End");
  await expect(page.getByTestId("send-patient")).toBeDisabled();
  await expect(page.getByTestId("guard-injection")).toBeDisabled();
  await expect(page.getByTestId("not-ready")).toBeVisible();
  await expect(page.getByTestId("send-patient")).toBeEnabled();
});

test("the newest answer replaces the last, and the free-text box and the patient panel never show two cards", async ({ page }) => {
  await openEstimate(page);
  await page.getByTestId("send-patient").click();
  await expect(page.getByTestId("probability")).toHaveCount(1);
  await page.getByRole("button", { name: "Type your own text for the assistant" }).click();
  await expect(page.getByTestId("probability")).toHaveCount(1); // the free-text card is empty until something is sent there
  await page.getByRole("textbox", { name: "Message" }).fill("Velorin index 128 mg/dL. Tremor present.");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByTestId("probability")).toHaveCount(1);
  await expect(page.getByTestId("compare-assistant")).toHaveCount(0); // the patient's answer was replaced
  await page.getByTestId("guard-treatment").click();
  await expect(page.getByTestId("probability")).toHaveCount(0);
});

test("using the scenario leaves saved queue progress as it was, writes nothing, and loads no queue case", async ({ page, context }) => {
  await page.goto("/");
  await openCase(page, CASES[5]);
  await waitForPacket(page);
  await page.getByRole("button", { name: "Back to the queue" }).click();
  const saved = await page.evaluate(() => Object.fromEntries(Object.entries(localStorage)));
  expect(Object.keys(saved).length).toBe(1);
  await page.getByRole("button", { name: "Estimate a risk" }).click();
  await slider(page, "tarnic_acid").press("End");
  await page.getByTestId("symptom-fatigue").getByRole("button", { name: "Present" }).click();
  await page.getByTestId("estimate-reset").click();
  await settled(page);
  await page.getByTestId("send-patient").click();
  await expect(page.getByTestId("compare-assistant")).toBeVisible();
  await page.getByTestId("guard-injection").click();
  await expect(page.getByTestId("compare-assistant")).toBeVisible();
  expect(await page.evaluate(() => Object.fromEntries(Object.entries(localStorage)))).toEqual(saved);
  expect(await page.evaluate(() => sessionStorage.length)).toBe(0);
  expect(await context.cookies()).toEqual([]);
  await page.getByRole("button", { name: "Review queue" }).click();
  expect(await page.evaluate(() => Object.fromEntries(Object.entries(localStorage)))).toEqual(saved);
  await expect(page.getByTestId("queue")).toBeVisible();
});

test("a visit to Estimate a risk alone writes nothing to storage", async ({ page, context }) => {
  await openEstimate(page);
  await slider(page, "velorin_index").press("End");
  await page.getByTestId("send-patient").click();
  expect(await page.evaluate(() => [localStorage.length, sessionStorage.length])).toEqual([0, 0]);
  expect(await context.cookies()).toEqual([]);
});
