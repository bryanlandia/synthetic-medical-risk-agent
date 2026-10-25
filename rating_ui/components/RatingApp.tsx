"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import glossary from "@/lib/glossary.json";
import {
  SYMPTOM_KEYS,
  isComplete,
  type NoteRating,
  type Session,
  type Sheet,
  type SymptomValue,
} from "@/lib/types";

const FIELDS = ["plausible", ...SYMPTOM_KEYS] as const;
const SYMPTOM_CHOICES: { value: SymptomValue; label: string; key: string }[] = [
  { value: "present", label: "Present", key: "1" },
  { value: "possible", label: "Possible", key: "2" },
  { value: "absent", label: "Absent", key: "3" },
  { value: "none", label: "Not mentioned", key: "4" },
];
const LABELS: Record<string, string> = {
  plausible: "Plausible as real documentation?",
  tremor: "Tremor",
  fatigue: "Fatigue",
  photophobia: "Photophobia",
  joint_stiffness: "Joint stiffness",
  dizziness: "Dizziness",
};

const blank = (): NoteRating => ({ plausible: null, symptoms: {}, comment: "", reason: "" });
type SaveState = "idle" | "saving" | "saved" | "error";

function storedName(): string {
  try {
    return window.localStorage.getItem("rater-name") ?? "";
  } catch {
    return "";
  }
}

export default function RatingApp() {
  const [session, setSession] = useState<Session | null>(null);
  const [sheet, setSheet] = useState<Sheet | null>(null);
  const [rater, setRater] = useState<string>("");
  const [nameDraft, setNameDraft] = useState("");
  const [ratings, setRatings] = useState<Record<string, NoteRating>>({});
  const [index, setIndex] = useState(0);
  const [cursor, setCursor] = useState(0);
  const [save, setSave] = useState<SaveState>("idle");
  const [error, setError] = useState<string | null>(null);
  const pending = useRef(0);
  const commentTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const commentRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    (async () => {
      try {
        const [s, sh] = await Promise.all([fetch("/api/session"), fetch("/api/sheet")]);
        if (!s.ok || !sh.ok) throw new Error("could not load the sheet; is REALISM_ROUND_DIR set?");
        const sess = (await s.json()) as Session;
        setSession(sess);
        setSheet((await sh.json()) as Sheet);
        const name = sess.fixedRater ?? storedName();
        setNameDraft(name);
        if (sess.fixedRater) setRater(sess.fixedRater);
      } catch (err) {
        setError((err as Error).message);
      }
    })();
  }, []);

  // Load this rater's earlier ratings and resume at the first note that is not finished.
  useEffect(() => {
    if (!rater || !sheet) return;
    (async () => {
      const res = await fetch(`/api/ratings?rater=${encodeURIComponent(rater)}`);
      if (!res.ok) {
        setError((await res.json()).error ?? "could not load ratings");
        return;
      }
      const loaded = ((await res.json()).ratings ?? {}) as Record<string, NoteRating>;
      setRatings(loaded);
      const first = sheet.notes.findIndex((n) => !isComplete(loaded[n.id]));
      setIndex(first === -1 ? sheet.notes.length - 1 : first);
      setCursor(0);
    })();
  }, [rater, sheet]);

  const note = sheet?.notes[index];
  const current = (note && ratings[note.id]) || blank();
  const total = sheet?.notes.length ?? 0;
  const done = useMemo(() => (sheet ? sheet.notes.filter((n) => isComplete(ratings[n.id])).length : 0), [sheet, ratings]);
  const finished = total > 0 && done === total;

  const persist = useCallback(
    async (noteId: string, rating: NoteRating) => {
      pending.current += 1;
      setSave("saving");
      try {
        const res = await fetch("/api/ratings", {
          method: "PUT",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ rater, noteId, rating }),
        });
        if (!res.ok) throw new Error((await res.json()).error ?? "save failed");
        pending.current -= 1;
        if (pending.current === 0) setSave("saved");
      } catch {
        pending.current -= 1;
        setSave("error");
      }
    },
    [rater],
  );

  const update = useCallback(
    (patch: (r: NoteRating) => NoteRating) => {
      if (!note) return;
      const next = patch(ratings[note.id] ?? blank());
      setRatings((prev) => ({ ...prev, [note.id]: next }));
      void persist(note.id, next);
    },
    [note, ratings, persist],
  );

  const setPlausible = useCallback(
    (v: "y" | "n") => {
      update((r) => ({ ...r, plausible: v }));
      setCursor(1);
    },
    [update],
  );
  const setSymptom = useCallback(
    (key: string, v: SymptomValue) => {
      update((r) => ({ ...r, symptoms: { ...r.symptoms, [key]: v } }));
      setCursor((c) => Math.min(FIELDS.indexOf(key as (typeof FIELDS)[number]) + 1, FIELDS.length));
    },
    [update],
  );
  const go = useCallback(
    (to: number) => {
      if (!sheet) return;
      setIndex(Math.max(0, Math.min(sheet.notes.length - 1, to)));
      setCursor(0);
    },
    [sheet],
  );
  const onComment = (text: string) => {
    if (!note) return;
    const next = { ...(ratings[note.id] ?? blank()), comment: text };
    setRatings((prev) => ({ ...prev, [note.id]: next }));
    if (commentTimer.current) clearTimeout(commentTimer.current);
    const id = note.id;
    commentTimer.current = setTimeout(() => void persist(id, next), 400);
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement;
      if (el.tagName === "SUMMARY") return; // Enter on the glossary toggle opens it; it must not move to the next note
      if (el.tagName === "TEXTAREA" || el.tagName === "INPUT") {
        if (e.key === "Escape") (el as HTMLElement).blur();
        return;
      }
      if (!note || e.metaKey || e.ctrlKey || e.altKey) return;
      const k = e.key.toLowerCase();
      let handled = true;
      if (k === "y" || k === "n") setPlausible(k);
      else if (["1", "2", "3", "4"].includes(k) && cursor >= 1 && cursor <= SYMPTOM_KEYS.length) {
        setSymptom(FIELDS[cursor], SYMPTOM_CHOICES[Number(k) - 1].value);
      } else if (k === "arrowdown") setCursor((c) => Math.min(c + 1, FIELDS.length));
      else if (k === "arrowup") setCursor((c) => Math.max(c - 1, 0));
      else if (k === "enter" || k === "arrowright" || k === "]") go(index + 1);
      else if (k === "arrowleft" || k === "[") go(index - 1);
      else if (k === "c") commentRef.current?.focus();
      else handled = false;
      if (handled) e.preventDefault();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [note, cursor, index, go, setPlausible, setSymptom]);

  if (error) return <main className="shell"><p role="alert" className="error" data-testid="load-error">{error}</p></main>;
  if (!session || !sheet) return <main className="shell"><p>Loading…</p></main>;

  if (!rater) {
    return (
      <main className="shell narrow">
        <Banner text={session.notice} />
        <h1>Note realism rating</h1>
        <p>
          You will read {total} short clinical notes about a <strong>fictional</strong> syndrome and say whether each reads
          like real documentation of the kind it is meant to be (each note says which kind: an AI-scribe draft, an EHR template, a quick shorthand note, and so on, and what is normal for it). Your answers save as you go, and you can stop and come back.
        </p>
        <Glossary />
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const name = nameDraft.trim();
            if (!name) return;
            try {
              window.localStorage.setItem("rater-name", name);
            } catch {
              /* private mode: the name just is not remembered */
            }
            setRater(name);
          }}
        >
          <label htmlFor="rater-name">Your name</label>
          <input id="rater-name" data-testid="rater-name-input" value={nameDraft} maxLength={80}
                 onChange={(e) => setNameDraft(e.target.value)} autoFocus />
          <button type="submit" data-testid="start" disabled={!nameDraft.trim()}>Start rating</button>
        </form>
      </main>
    );
  }

  return (
    <main className="shell">
      <Banner text={session.notice} />
      <header className="top">
        <h1>Note realism rating</h1>
        <div className="meta">
          <span data-testid="rater">{rater}{session.kind === "llm" ? " (LLM reviewer)" : ""}</span>
          <span data-testid="progress">{done} of {total} rated</span>
          <span data-testid="incomplete-count">{total - done} incomplete</span>
          <span className={`save ${save}`} data-testid="save-state" aria-live="polite">
            {save === "saving" ? "Saving…" : save === "saved" ? "Saved" : save === "error" ? "Save failed" : ""}
          </span>
        </div>
      </header>

      <Glossary />

      {finished && <p className="done" data-testid="finished" role="status">All {total} notes are rated. Thank you.</p>}

      {note && (
        <section className="work">
          <div className="note">
            <h2 data-testid="note-id">{note.id} <small>({index + 1} of {total})</small></h2>
            {note.kind && (
              <aside className="kind" data-testid="note-kind">
                <strong data-testid="note-kind-label">{note.kind.label}.</strong> {note.kind.expect}
              </aside>
            )}
            <pre data-testid="note-text" tabIndex={0}>{note.text}</pre>
          </div>

          <div className="form">
            <fieldset className={cursor === 0 ? "active" : ""}>
              <legend>{LABELS.plausible}</legend>
              <div className="choices">
                {(["y", "n"] as const).map((v) => (
                  <button key={v} type="button" aria-pressed={current.plausible === v} data-testid={`plausible-${v}`}
                          onClick={() => setPlausible(v)}>
                    {v === "y" ? "Yes" : "No"} <kbd>{v}</kbd>
                  </button>
                ))}
              </div>
            </fieldset>
            <p className="hint">How does the NOTE describe each symptom?</p>
            {SYMPTOM_KEYS.map((key, i) => (
              <fieldset key={key} className={cursor === i + 1 ? "active" : ""}>
                <legend>{LABELS[key]}</legend>
                <div className="choices">
                  {SYMPTOM_CHOICES.map((c) => (
                    <button key={c.value} type="button" aria-pressed={current.symptoms[key] === c.value}
                            data-testid={`symptom-${key}-${c.value}`} onClick={() => setSymptom(key, c.value)}>
                      {c.label} <kbd>{c.key}</kbd>
                    </button>
                  ))}
                </div>
              </fieldset>
            ))}
            <label htmlFor="comment">Comment (optional) <kbd>c</kbd></label>
            <textarea id="comment" ref={commentRef} data-testid="comment" rows={3} maxLength={2000}
                      value={current.comment} onChange={(e) => onComment(e.target.value)} />
            <div className="nav">
              <button type="button" data-testid="prev" onClick={() => go(index - 1)} disabled={index === 0}>Back <kbd>←</kbd></button>
              <button type="button" data-testid="next" onClick={() => go(index + 1)} disabled={index === total - 1}>Next <kbd>Enter</kbd></button>
            </div>
            <p className="hint keys">
              Keys: <kbd>y</kbd>/<kbd>n</kbd> plausible, then <kbd>1</kbd> present, <kbd>2</kbd> possible, <kbd>3</kbd> absent,
              <kbd>4</kbd> not mentioned for each symptom in turn. <kbd>↑</kbd>/<kbd>↓</kbd> move between fields.
            </p>
          </div>
        </section>
      )}

      <nav aria-label="Notes" className="chips" data-testid="chips">
        {sheet.notes.map((n, i) => {
          const complete = isComplete(ratings[n.id]);
          return (
            <button key={n.id} type="button" data-testid={`chip-${n.id}`} data-complete={complete}
                    aria-current={i === index} className={`${complete ? "complete" : "incomplete"} ${i === index ? "current" : ""}`}
                    onClick={() => go(i)} title={complete ? "rated" : "incomplete"}>
              {n.id.replace(/^n/, "")}
            </button>
          );
        })}
      </nav>
    </main>
  );
}

function Glossary() {
  return (
    <details className="glossary" data-testid="glossary">
      <summary data-testid="glossary-toggle">Lab panel used in these notes (fictional)</summary>
      <p>
        The lab names, abbreviations and units are made up on purpose. Please do not count them against a note: judge the
        writing, the layout and how the values are presented, and and whether a unit or range in a note disagrees with this list. Some tests are reported in either of two units, and both are normal. A value outside its range, or one a note does not comment on, is not by itself a sign of an artificial note.
      </p>
      <table>
        <thead>
          <tr><th scope="col">Test</th><th scope="col">Abbreviation</th><th scope="col">Unit</th><th scope="col">Reference range</th><th scope="col">Also reported in</th></tr>
        </thead>
        <tbody>
          {glossary.map((g) => (
            <tr key={g.abbr} data-testid={`glossary-row-${g.abbr}`}>
              <td>{g.name}</td><td>{g.abbr}</td><td>{g.unit || "none (a ratio)"}</td><td>{g.ref_lo}–{g.ref_hi}</td>
              <td>{"alt_unit" in g ? `${g.alt_unit} (${g.alt_ref_lo}–${g.alt_ref_hi})` : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  );
}

function Banner({ text }: { text: string }) {
  return <div className="banner" role="note" data-testid="notice">{text}</div>;
}
