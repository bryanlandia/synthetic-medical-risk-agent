import type { ReactNode } from "react";

/** The estimated risk as one large, labelled figure. Teal, never a red-to-green scale: it must not read as a verdict. */
export function RiskFigure({ probability, testId, live, children }: { probability: number; testId: string; live?: boolean; children?: ReactNode }) {
  return (
    <div className="risk-figure">
      <p className="risk-figure-label">Estimated risk of Velorin-Kessler syndrome (fictional)</p>
      <p className="risk-figure-number" data-testid={testId} aria-live={live ? "polite" : undefined}>{Math.round(probability * 100)}%</p>
      {children}
    </div>
  );
}
