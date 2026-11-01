import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { CASES } from "./helpers";

const WEB_POLICY = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "content", "pet_ct_policy.json"), "utf8"));
const SOURCE_POLICY = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "..", "risk_model", "src", "risk_model", "policy", "pet_ct_k17.json"), "utf8"));

test("the page's copy of the policy is the source policy file", () => {
  expect(WEB_POLICY).toEqual(SOURCE_POLICY);
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
    expect((await request.post("/api/packet", { data: { message: CASES[0].message, attestations } })).status()).toBe(422);
  }
});

test("the route returns only the whitelisted packet fields for a real case", async ({ request }) => {
  const r = await request.post("/api/packet", { data: { message: CASES[0].message, attestations: CASES[0].answers } });
  expect(r.status()).toBe(200);
  const { packet } = await r.json();
  expect(Object.keys(packet).sort()).toEqual(["criteria", "declined", "disclaimer", "evidence", "gaps", "notice", "policy_id", "report", "request_id", "summary", "summary_source"]);
  expect(JSON.stringify(packet)).not.toMatch(/ground_truth|usage|summary_fallback/);
});
