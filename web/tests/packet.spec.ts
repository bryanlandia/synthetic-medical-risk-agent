import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const PATIENTS = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "content", "demo_patients.json"), "utf8")).patients as { slug: string; message: string }[];
const WEB_POLICY = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "content", "pet_ct_policy.json"), "utf8"));
const SOURCE_POLICY = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "..", "risk_model", "src", "risk_model", "policy", "pet_ct_k17.json"), "utf8"));
const FIRST = PATIENTS[0];

test("the page's criteria wording is the policy file's", () => {
  expect(WEB_POLICY).toEqual(SOURCE_POLICY);
});

test("answers start as not yet answered, and one press makes one request with the stored message and the controls", async ({ page }) => {
  const bodies: string[] = [];
  page.on("request", (r) => { if (r.url().endsWith("/api/packet")) bodies.push(r.postData() ?? ""); });
  await page.goto("/");
  for (const id of ["C3", "C4", "C5", "C6"]) await expect(page.getByLabel(new RegExp(`^${id}:`))).toHaveValue("unanswered");
  await page.getByRole("button", { name: "Prepare PET-CT packet" }).click();
  await expect(page.getByTestId("packet")).toBeVisible();
  expect(bodies).toHaveLength(1);
  expect(JSON.parse(bodies[0])).toEqual({ message: FIRST.message, attestations: { C3: "unanswered", C4: "unanswered", C5: "unanswered", C6: "unanswered" } });
  for (const id of ["C3", "C4", "C5", "C6"]) await expect(page.getByTestId(`status-${id}`)).toHaveText("Unknown");
  await expect(page.getByTestId("packet-gaps")).toContainText("Clinician to answer C3");
  await expect(page.getByTestId("summary-source")).toBeVisible();
});

test("a met criterion shows the chart's value beside it, and changing an answer clears the packet", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel(/^C3:/).selectOption("yes");
  await page.getByRole("button", { name: "Prepare PET-CT packet" }).click();
  await expect(page.getByTestId("status-C3")).toHaveText("Met");
  await expect(page.getByTestId("criterion-C3")).toContainText("The clinician answered yes for C3");
  await page.getByLabel(/^C4:/).selectOption("no");
  await expect(page.getByTestId("packet")).toHaveCount(0);
});

test("the rationale field is empty, labelled as the clinician's, and sign-off locks everything", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel(/^C5:/).selectOption("no");
  await page.getByRole("button", { name: "Prepare PET-CT packet" }).click();
  await expect(page.getByTestId("status-C5")).toHaveText("Unmet");
  const rationale = page.getByTestId("rationale");
  await expect(rationale).toHaveValue("");
  await expect(page.getByText("your own words; the tool never writes this")).toBeVisible();
  await rationale.fill("My own reason.");
  await page.getByRole("button", { name: /Demo sign-off/ }).click();
  await expect(page.getByTestId("signed")).toContainText("Drafted by tool, reviewed by clinician (demo)");
  await expect(rationale).toHaveAttribute("readonly", "");
  await expect(rationale).toHaveValue("My own reason.");
  await expect(page.getByLabel(/^C3:/)).toBeDisabled();
  await expect(page.getByRole("button", { name: "Copy" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Print" })).toBeVisible();
});

test("the synthetic-data notice is in the print view", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Prepare PET-CT packet" }).click();
  await expect(page.getByTestId("packet")).toBeVisible();
  await page.emulateMedia({ media: "print" });
  const notice = page.getByTestId("packet-notice");
  await expect(notice).toBeVisible();
  await expect(notice).toContainText(/synthetic/i);
  await expect(notice).toContainText("not medical advice");
});

test("no verdict wording and no control that edits a recorded value", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Prepare PET-CT packet" }).click();
  await expect(page.getByTestId("packet")).toBeVisible();
  const panel = page.getByRole("region", { name: "PET-CT readiness packet" });
  const text = (await panel.innerText()).toLowerCase();
  for (const word of ["approved", "denied", "eligible", "qualifies", "confidence interval", "saves", "savings"]) expect(text).not.toContain(word);
  expect(await page.locator("input[type=text], input[type=number], input:not([type])").count()).toBe(0);
  expect(await panel.locator("textarea").count()).toBeLessThanOrEqual(1);
});

test("a treatment question sent to the route is declined with no table", async ({ request }) => {
  const r = await request.post("/api/packet", { data: { message: "Which medication should the patient take for the tremor?", attestations: {} } });
  expect(r.status()).toBe(200);
  const body = await r.json();
  expect(body.packet).toMatchObject({ declined: true, decline_reason: "treatment_request" });
  expect(body.packet.criteria).toBeUndefined();
});

test("the route rejects malformed answers before the service", async ({ request }) => {
  for (const attestations of [{ C7: "yes" }, { C3: "maybe" }, { C1: "yes" }]) {
    expect((await request.post("/api/packet", { data: { message: FIRST.message, attestations } })).status()).toBe(422);
  }
});
