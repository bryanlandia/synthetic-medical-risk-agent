import { expect, test } from "@playwright/test";
import { contrast } from "../lib/contrast";
import { CONTRAST_PAIRS, STATUS_CHIPS } from "../lib/theme";

test("every text and chip colour pair meets 4.5:1", () => {
  expect(CONTRAST_PAIRS.length).toBeGreaterThan(15);
  for (const [name, fg, bg] of CONTRAST_PAIRS) expect(contrast(fg, bg), name).toBeGreaterThanOrEqual(4.5);
});

test("the contrast helper agrees with known values", () => {
  expect(contrast("#000000", "#FFFFFF")).toBeCloseTo(21, 0);
  expect(contrast("#777777", "#FFFFFF")).toBeLessThan(4.5);
  expect(contrast("#FFFFFF", "#FFFFFF")).toBeCloseTo(1, 5);
});

test("each status has its own words, so colour is never the only signal", () => {
  expect(Object.values(STATUS_CHIPS).map((s) => s.label)).toEqual(["New", "In review", "Returned", "Released", "Closed"]);
});
