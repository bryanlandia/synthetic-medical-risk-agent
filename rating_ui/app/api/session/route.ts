import { NextResponse } from "next/server";
import { NOTICE, config } from "@/lib/config";

export const dynamic = "force-dynamic";

export function GET() {
  const cfg = config();
  return NextResponse.json({ kind: cfg.kind, fixedRater: cfg.fixedRater, notice: NOTICE });
}
