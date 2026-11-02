import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { C5_SHOWN, criterionText } from "../lib/copy";
import { dialogButton, first, openCase, classify, waitForPacket } from "./helpers";

const POLICY = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "content", "pet_ct_policy.json"), "utf8"));
let kinds: Awaited<ReturnType<typeof classify>>;
test.beforeAll(async ({ request }) => {
  kinds = await classify(request);
});

test("only C5 is reworded, and it still exists in the policy", () => {
  const c5 = POLICY.criteria.find((c: { id: string }) => c.id === "C5");
  expect(c5).toBeTruthy();
  expect(criterionText("C5", c5.text)).toBe(C5_SHOWN);
  for (const c of POLICY.criteria.filter((x: { id: string }) => x.id !== "C5")) expect(criterionText(c.id, c.text)).toBe(c.text);
});

test("C5 reads positively in the answers and the checklist, and a Yes shows it met", async ({ page }) => {
  await page.goto("/");
  const c = first(kinds, "releasable");
  await openCase(page, c);
  await waitForPacket(page);
  await expect(page.getByTestId("answers")).toContainText(C5_SHOWN);
  await expect(page.getByTestId("answer-C5")).toHaveText("Yes");
  await expect(page.getByTestId("criterion-C5")).toContainText(C5_SHOWN);
  await expect(page.getByTestId("crit-status-C5")).toContainText(/met/i);
  await expect(page.locator("body")).not.toContainText("No PET-CT");
  for (const id of ["C1", "C2", "C3", "C4", "C6"]) {
    const text = POLICY.criteria.find((x: { id: string }) => x.id === id).text;
    await expect(page.getByTestId(`criterion-${id}`)).toContainText(text);
  }
});

test("the released packet and its copied text use the positive wording", async ({ page, context }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.goto("/");
  const c = first(kinds, "releasable");
  await openCase(page, c);
  await waitForPacket(page);
  await page.getByRole("button", { name: "Release", exact: true }).click();
  await dialogButton(page, "Release").click();
  await expect(page.getByTestId("released-packet")).toContainText(C5_SHOWN);
  await page.getByRole("button", { name: "Copy" }).click();
  const copied = await page.evaluate(() => navigator.clipboard.readText());
  expect(copied).toContain(C5_SHOWN);
  expect(copied).not.toContain("No PET-CT");
});
