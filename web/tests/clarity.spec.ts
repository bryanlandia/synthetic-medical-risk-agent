import { expect, test } from "@playwright/test";
import { HINTS, formatReceived } from "../lib/copy";
import { CASES, classify, first, openAssistant, openCase, waitForPacket } from "./helpers";

let kinds: Awaited<ReturnType<typeof classify>>;
test.beforeAll(async ({ request }) => {
  kinds = await classify(request);
});

test("the estimate names what it estimates and stays context only", async ({ page }) => {
  await page.goto("/");
  await openCase(page, first(kinds, "unmet"));
  await waitForPacket(page);
  const est = page.getByTestId("estimate");
  await expect(est).toContainText("Estimated risk of Velorin-Kessler syndrome (fictional):");
  await expect(est).toContainText(/\d+%/);
  await expect(est).toContainText("Context only; it decides no criterion.");
});

test("the chart's note is headed Clinical note, and the preparer answers carry no Demo chip", async ({ page }) => {
  await page.goto("/");
  await openCase(page, first(kinds, "unmet"));
  await waitForPacket(page);
  await expect(page.getByTestId("chart").getByRole("heading", { name: "Clinical note" })).toBeVisible();
  await expect(page.getByTestId("answers")).toContainText(", simulated)");
  await expect(page.getByTestId("answers").getByText("Demo", { exact: true })).toHaveCount(0);
});

test("coverage criteria is plain text with no hint, and the other three terms keep theirs", async ({ page }) => {
  await page.goto("/");
  expect(Object.keys(HINTS).sort()).toEqual(["PET-CT", "packet", "prior authorization"]);
  await expect(page.getByTestId("intro-card")).toContainText("coverage criteria");
  await expect(page.getByTestId("intro-card").locator("span[tabindex='0']", { hasText: /criteria/ })).toHaveCount(0);
  await openCase(page, first(kinds, "unmet"));
  await waitForPacket(page);
  await expect(page.getByRole("heading", { name: "Checklist against the insurer's coverage criteria" })).toBeVisible();
});

test("the sent message opens from a labelled disclosure that works from the keyboard", async ({ page }) => {
  await page.goto("/");
  const c = first(kinds, "unmet");
  await openCase(page, c);
  await waitForPacket(page);
  const toggle = page.getByRole("button", { name: "Show the message sent to the service" });
  await expect(toggle).toHaveAttribute("aria-expanded", "false");
  await toggle.focus();
  await page.keyboard.press("Enter");
  const open = page.getByRole("button", { name: "Hide the message sent to the service" });
  await expect(open).toHaveAttribute("aria-expanded", "true");
  expect((await page.getByTestId("sent-message").innerText()).trim()).toBe(c.message.trim());
});

test("every queue row and the case header show the received date, time and zone, the same in any browser zone", async ({ browser }) => {
  const context = await browser.newContext({ timezoneId: "Asia/Tokyo" });
  const page = await context.newPage();
  await page.goto("/");
  const rows = page.getByTestId("queue").locator("tbody tr");
  await expect(rows).toHaveCount(30);
  for (const text of await rows.allInnerTexts()) expect(text).toMatch(/\b\d{1,2} (Nov) 2026, \d\d:\d\d ET\b/);
  const c = CASES[0];
  await expect(rows.first()).toContainText(formatReceived(c.received));
  await openCase(page, c);
  await expect(page.getByTestId("case-title")).toBeVisible();
  await expect(page.getByText(`received ${formatReceived(c.received)}`)).toBeVisible();
  await context.close();
});

// --- where models and code operate ----------------------------------------------------------------------------------

const BANNED = /\$|saving|auc\b|accuracy|\b(approved|denied|eligible|qualifies)\b/i;

test("each block of a case says what produced it", async ({ page }) => {
  await page.goto("/");
  await openCase(page, first(kinds, "unmet"));
  await waitForPacket(page);
  await expect(page.getByTestId("produced-estimate")).toHaveAttribute("data-produced", "classifier");
  await expect(page.getByTestId("produced-answers")).toHaveAttribute("data-produced", "preparer");
  await expect(page.getByTestId("produced-checklist")).toHaveAttribute("data-produced", "rules");
  await expect(page.getByTestId("produced-summary")).toHaveAttribute("data-produced", /^(llm|template)$/);
  await expect(page.getByTestId("produced-decision")).toHaveAttribute("data-produced", "you");
  for (const [id, kind] of [["C1", "rules"], ["C2", "reader"], ["C3", "preparer"], ["C4", "preparer"], ["C5", "preparer"], ["C6", "preparer"]]) {
    await expect(page.getByTestId(`produced-source-${id}`)).toHaveAttribute("data-produced", kind);
  }
  await expect(page.getByTestId("source-C1")).toContainText("Chart labs");
  await expect(page.getByTestId("source-C2")).toContainText("Clinical note");
  await expect(page.getByTestId("source-C5")).toContainText("Preparer's answer");
});

test("a template summary carries the Template label, not the Language model label", async ({ page }) => {
  await page.route("**/api/packet", async (route) => {
    const res = await route.fetch();
    const body = await res.json();
    body.packet.summary_source = "template";
    await route.fulfill({ response: res, json: body });
  });
  await page.goto("/");
  await openCase(page, first(kinds, "unmet"));
  await waitForPacket(page);
  await expect(page.getByTestId("produced-summary")).toHaveAttribute("data-produced", "template");
  await expect(page.getByTestId("produced-summary")).toContainText("Template");
});

test("the released packet labels the checklist, its sources, the summary and the supervisor's rationale", async ({ page }) => {
  await page.goto("/");
  await openCase(page, first(kinds, "releasable"));
  await waitForPacket(page);
  await page.getByRole("button", { name: "Release", exact: true }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Release", exact: true }).click();
  const packet = page.getByTestId("released-packet");
  await expect(packet.getByTestId("produced-checklist")).toHaveAttribute("data-produced", "rules");
  await expect(packet.getByTestId("produced-released-summary")).toHaveAttribute("data-produced", /^(llm|template)$/);
  await expect(packet.getByTestId("source-released-C2")).toContainText("Clinical note");
});

test("the key opens from the queue and from a case, closes with Escape and returns focus", async ({ page }) => {
  await page.goto("/");
  const open = page.getByRole("button", { name: "What produced this page?" });
  await open.focus();
  await page.keyboard.press("Enter");
  const key = page.getByTestId("produced-key");
  await expect(key).toBeVisible();
  for (const label of ["Classifier model", "Note reader", "Code", "Language model", "Template", "Agent", "Preparer (simulated)", "You"]) await expect(key).toContainText(label);
  await expect(key).toContainText("invented");
  expect((await key.innerText())).not.toMatch(BANNED);
  await page.keyboard.press("Escape");
  await expect(key).toBeHidden();
  await expect(open).toBeFocused();
  await openCase(page, first(kinds, "unmet"));
  await page.getByRole("button", { name: "What produced this page?" }).click();
  await expect(page.getByTestId("produced-key")).toBeVisible();
});

test("the free-text view names the guards, the agent and the classifier", async ({ page }) => {
  await page.goto("/");
  await openAssistant(page);
  const row = page.getByTestId("free-text-produced");
  await expect(row).toBeVisible();
  for (const id of ["free-guards", "free-agent", "free-classifier"]) await expect(page.getByTestId(`produced-${id}`)).toBeVisible();
  expect(await row.innerText()).not.toMatch(BANNED);
});
