import { expect, test } from "@playwright/test";
import { DEMO_NOTES, STRIP_TEXT } from "../lib/copy";
import { backToQueue, classify, dialogButton, first, openCase, waitForPacket } from "./helpers";

let kinds: Awaited<ReturnType<typeof classify>>;
test.beforeAll(async ({ request }) => {
  kinds = await classify(request);
});

const RATIONALE = "I have reviewed the chart and the history supports this request.";

test("a released packet opens with a cover sheet, and every invented item is marked fictional", async ({ page }) => {
  await page.goto("/");
  const c = first(kinds, "releasable");
  await openCase(page, c);
  await waitForPacket(page);
  await page.getByRole("button", { name: "Release", exact: true }).click();
  await expect(page.getByRole("dialog").getByTestId("demo-note-release")).toContainText(DEMO_NOTES.release);
  await dialogButton(page, "Release").click();
  const cover = page.getByTestId("cover-sheet");
  await expect(cover).toContainText(`${c.insurer}`);
  await expect(cover).toContainText("Insurer (fictional)");
  await expect(cover).toContainText(c.request_code);
  await expect(cover).toContainText("Request code (fictional)");
  await expect(cover).toContainText(c.patient_id);
  await expect(cover).toContainText("K-17 tracer PET-CT (fictional)");
  await expect(cover).toContainText(`${c.preparer} (simulated)`);
  await expect(page.getByTestId("demo-note-cover")).toContainText(DEMO_NOTES.cover);
  await expect(page.getByTestId("demo-note-next")).toContainText(DEMO_NOTES.next);
  await expect(page.getByTestId("released-packet")).toContainText("In real life");
  const text = (await page.getByTestId("released-packet").innerText()).toLowerCase();
  expect(text).not.toMatch(/\b(approved|denied|eligible|qualifies)\b/);
});

test("the audit timeline lists the preparer and each supervisor action in order across a return and a reopen", async ({ page }) => {
  await page.goto("/");
  const c = first(kinds, "unmet");
  await openCase(page, c);
  await waitForPacket(page);
  await page.getByRole("button", { name: "Return with a note" }).click();
  await page.getByTestId("return-note").fill("Please check the imaging history.");
  await dialogButton(page, "Return").click();
  await backToQueue(page);
  await openCase(page, c);
  await expect(page.getByTestId("case-status")).toHaveText("Returned");
  await page.getByRole("button", { name: "Reopen this request" }).click();
  await expect(page.getByTestId("case-status")).toHaveText("In review");
  await page.getByTestId("rationale").fill(RATIONALE);
  await page.getByRole("button", { name: "Release", exact: true }).click();
  await dialogButton(page, "Release").click();
  const items = page.getByTestId("audit-timeline").locator("li");
  await expect(items).toHaveCount(5);
  const lines = await items.allInnerTexts();
  expect(lines[0]).toContain(`Prepared by ${c.preparer} (simulated)`);
  expect(lines[0]).toContain(c.received);
  expect(lines.slice(1).map((l) => l.replace(/^\d{1,2}:\d{2}(\s?[AP]M)?\s+/i, "").trim())).toEqual(["Opened by you", "Returned by you", "Reopened by you", "Released by you"]);
  for (const l of lines.slice(1)) expect(l).toMatch(/^\d{1,2}:\d{2}/);
  await expect(page.getByTestId("released-rationale")).toHaveText(RATIONALE);
});

test("the printed view holds the packet and the notice, and omits the strip, the queue and the controls", async ({ page }) => {
  await page.goto("/");
  await openCase(page, first(kinds, "releasable"));
  await waitForPacket(page);
  await page.getByRole("button", { name: "Release", exact: true }).click();
  await dialogButton(page, "Release").click();
  await expect(page.getByTestId("released-packet")).toBeVisible();
  await page.emulateMedia({ media: "print" });
  await expect(page.getByTestId("cover-sheet")).toBeVisible();
  await expect(page.getByTestId("print-notice")).toBeVisible();
  await expect(page.getByTestId("print-notice")).toContainText(STRIP_TEXT);
  await expect(page.getByTestId("print-notice")).toContainText("not medical advice");
  await expect(page.getByTestId("demo-strip")).toBeHidden();
  await expect(page.getByRole("button", { name: "Print" })).toBeHidden();
  await expect(page.getByRole("button", { name: "Copy" })).toBeHidden();
  await expect(page.getByRole("button", { name: "Back to the queue" })).toBeHidden();
  await expect(page.getByTestId("queue")).toHaveCount(0);
});

test("Copy puts the packet, the rationale and the audit trail on the clipboard", async ({ page, context }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.goto("/");
  const c = first(kinds, "unmet");
  await openCase(page, c);
  await waitForPacket(page);
  await page.getByTestId("rationale").fill(RATIONALE);
  await page.getByRole("button", { name: "Release", exact: true }).click();
  await dialogButton(page, "Release").click();
  await page.getByRole("button", { name: "Copy" }).click();
  const copied = await page.evaluate(() => navigator.clipboard.readText());
  for (const part of [c.request_code, c.patient_id, c.insurer, "Audit trail", RATIONALE, "not medical advice"]) expect(copied).toContain(part);
});

test("a released case stays released after a reload and shows no decision controls", async ({ page }) => {
  await page.goto("/");
  const c = first(kinds, "releasable");
  await openCase(page, c);
  await waitForPacket(page);
  await page.getByRole("button", { name: "Release", exact: true }).click();
  await dialogButton(page, "Release").click();
  await page.reload();
  await expect(page.getByTestId(`chip-${c.ordinal}`)).toHaveText("Released");
  await openCase(page, c);
  await expect(page.getByTestId("cover-sheet")).toBeVisible();
  await expect(page.getByTestId("decision-bar")).toHaveCount(0);
});
