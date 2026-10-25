# Note realism rating tool

**All data is synthetic and the disease is fictional.** This is a small local tool for rating pilot notes for the
realism gate. It is not for real patient data, and it is not for real medical use.

You will read short clinical notes about a made-up syndrome and say, for each one:

1. **Plausible?** Does it read like documentation a clinician or a documentation tool could really have written
   for a visit (yes), or does it read wrong, stilted or artificial (no)?
2. **For each of five symptoms** (tremor, fatigue, photophobia, joint stiffness, dizziness): how does the *note*
   describe it? **Present**, **Possible** (uncertain or hedged), **Absent** (denied), or **Not mentioned**.

You are not judging whether the note is medically correct for a real disease (there is none), only whether it
looks like real documentation and what it says about the symptoms. Notes are shuffled and do not say where they
came from. That is deliberate.

## Run it (clinician)

From a checkout, with the round directory the developer gives you (it holds `sheet.json`):

```
cd rating_ui
npm install            # once (if it hangs building fsevents, use: npm install --ignore-scripts)
REALISM_ROUND_DIR=../data_gen/realism/round0 npm run dev
```

Open <http://127.0.0.1:3100>, type your name, and rate. Everything saves as you go; to resume, open the page again
and type the same name. Your ratings are saved next to the sheet as `ratings.<your-name>.json`. When all notes
show as rated, tell the developer. Do not open `key.json` in that folder until you have finished.

Keyboard: `y` / `n` for plausible, then `1` present, `2` possible, `3` absent, `4` not mentioned for each symptom in
turn (arrow keys move between fields), `Enter` for the next note, `←` for the previous, `c` for a comment.

## Run the gate (developer)

```
cd data_gen
uv run data-gen gate          # counts only human ratings unless llm.gate_rater_kinds says otherwise
```

## Notes for the developer

- **Local only.** The server listens on `127.0.0.1` only, and no deployment target is configured. Hosting it
  publicly (authentication, shared storage, a deployment separate from `web/`) is out of scope for now.
- **It cannot show the key.** It reads only `sheet.json` and reads and writes only `ratings.<rater>.json` in the round
  directory. `key.json` is never read.
- **The rater kind is set at launch** (`RATER_KIND`, default `human`), not by the person rating. An LLM session also
  needs `RATER_NAME`, `RATER_MODEL_ID` and `RATER_PROMPT_VERSION`; the reviewer command sets these.
- Tests: `npm test` builds the app and runs Playwright against a throwaway round (`npx playwright install chromium`
  once).
