import { expect, test, type Page } from "@playwright/test";
import { WEB_PORT } from "../playwright.config";

const BEHIND = ["Try the assistant", "Model card", "About this project"];

async function openBehind(page: Page, item: string) {
  await page.getByRole("button", { name: "Behind the demo" }).click();
  await page.getByRole("menuitem", { name: item }).click();
}

test("the built pages make no request to another site", async ({ page }) => {
  const foreign: string[] = [];
  page.on("request", (r) => {
    const url = new URL(r.url());
    if (!["127.0.0.1", "localhost"].includes(url.hostname) || url.port !== String(WEB_PORT)) foreign.push(r.url());
  });
  await page.goto("/");
  await page.getByRole("button", { name: /^VK-PET-/ }).first().click();
  await expect(page.getByTestId("case-title")).toBeVisible();
  for (const item of BEHIND) await openBehind(page, item);
  expect(foreign).toEqual([]);
});

test("the strip, the fictional title and the funder footer are on every screen", async ({ page }) => {
  await page.goto("/");
  const check = async () => {
    await expect(page.getByTestId("demo-strip")).toBeVisible();
    await expect(page.getByTestId("demo-strip")).toContainText("invented");
    await expect(page.getByRole("banner").getByRole("heading", { level: 1 })).toContainText("Supervisor review");
    await expect(page.getByText("Decision support for Velorin-Kessler Syndrome diagnosis (fictional disease)")).toBeVisible();
    const footer = page.getByTestId("funder-footer");
    await expect(footer).toContainText("Kessler Family Foundation");
    await expect(footer).toContainText("fictional");
    const text = (await page.locator("body").innerText()).toLowerCase();
    for (const word of ["hl7", "fhir", "epic systems"]) expect(text).not.toContain(word);
  };
  await check();
  await page.getByRole("button", { name: /^VK-PET-/ }).first().click();
  await expect(page.getByTestId("case-title")).toBeVisible();
  await check();
  for (const item of BEHIND) {
    await openBehind(page, item);
    await check();
  }
});

test("the navigation reaches every view and returns to the queue", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("queue")).toBeVisible();
  for (const item of BEHIND) {
    await openBehind(page, item);
    await expect(page.getByRole("heading", { name: new RegExp(`Behind the demo: ${item}`) })).toBeVisible();
    await page.getByRole("button", { name: "Back to the queue" }).click();
    await expect(page.getByTestId("queue")).toBeVisible();
  }
});
