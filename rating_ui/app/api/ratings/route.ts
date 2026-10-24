import { NextResponse } from "next/server";
import { config } from "@/lib/config";
import { GuardError } from "@/lib/guard";
import { BadRequest, readRatings, saveRating } from "@/lib/store";

export const dynamic = "force-dynamic";

function fail(err: unknown) {
  if (err instanceof GuardError || err instanceof BadRequest) {
    return NextResponse.json({ error: err.message }, { status: 400 });
  }
  throw err;
}

export async function GET(req: Request) {
  try {
    const cfg = config();
    const rater = cfg.fixedRater ?? new URL(req.url).searchParams.get("rater") ?? "";
    const file = rater ? await readRatings(rater) : null;
    return NextResponse.json({ ratings: file?.ratings ?? {} });
  } catch (err) {
    return fail(err);
  }
}

/** Body: { rater, noteId, rating }. Any "kind" field in the body is ignored on purpose. */
export async function PUT(req: Request) {
  try {
    const body = (await req.json()) as { rater?: string; noteId?: string; rating?: unknown };
    if (typeof body.noteId !== "string") throw new BadRequest("noteId is required");
    const cfg = config();
    const rater = cfg.fixedRater ?? body.rater;
    if (typeof rater !== "string" || !rater.trim()) throw new BadRequest("rater is required");
    const file = await saveRating(rater, body.noteId, body.rating);
    return NextResponse.json({ saved: body.noteId, count: Object.keys(file.ratings).length });
  } catch (err) {
    return fail(err);
  }
}
