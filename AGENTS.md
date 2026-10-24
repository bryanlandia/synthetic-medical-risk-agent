# Synthetic Medical Risk Agent

Portfolio demo. **All medical data is synthetic and the disease is fictional.** The agent must never give real medical advice. Specs, decisions and change proposals live in `openspec/`.

## Layout

- `data_gen/` seeded synthetic data generator
- `training/` classifier + LoRA training, MLflow tracking
- `agent/` FastAPI + Strands agent and tools
- `evals/` Inspect AI tasks, promptfoo configs, datasets, reports
- `web/` Next.js app (Vercel root dir)
- `rating_ui/` local-only Next.js tool for rating pilot notes (never deployed; loopback only; cannot read the answer key)
- `openspec/` specs and changes

## Workflow

- Spec-driven: each phase is an OpenSpec change (`/opsx:propose`, review, `/opsx:apply`, `/opsx:archive`).
- `openspec` is installed under nvm node v22.22.0 and may not be on PATH: `export PATH=~/.nvm/versions/node/v22.22.0/bin:$PATH`.

## Conventions

- Python for everything except `web/`. Pin versions; seed all randomness.
- Prefer code-graded eval scorers over model-graded.
- Use Haiku while developing evals; run the chosen model only for final numbers.
- Never put secrets or the Render URL in client code.

## Commands

Run from `data_gen/` (Python 3.12 via uv; the machine's default `python3` is a broken pyenv 3.6, so use `UV_PYTHON_PREFERENCE=only-managed uv ...`):

- `uv sync` install; `uv run pytest` tests
- `uv run data-gen generate` write the offline, deterministic dataset to `data/` (options: `--seed`, `--n-train`, `--n-test`, `--n-per-adversarial-type`, `--config file.json`)
- `uv run data-gen validate --regenerate` check `data/` against the specs and require byte-identical regeneration from the manifest

LLM-written notes (spend money; the API key is read only from the `ANTHROPIC_API_KEY` environment variable, so export it in your own shell and never put it in a file). Long runs print one progress line per note to stderr (`--quiet` hides it); `-v` also logs every paid API call with tokens, stop reason and duration, and `-vv` adds cache hits. A run stops by itself if a setting (pilot) or the whole run is mostly failing validation:

- `uv run data-gen estimate --note-source llm [--pilot]` dry-run the calls and cost; no API call, no key needed
- `uv run data-gen pilot --note-source llm --yes` write the small blind rating sample to `realism/round0/` (`sheet.md` to rate, `key.json` not to open until done); `--round N --setting S` re-rates a revised setting with fresh notes
- `uv run data-gen gate` check the saved ratings in `realism/round*/` (`ratings.<rater>.json` from the rating app or the reviewer, or a hand-filled `ratings.md`); exit 0 only if every setting is at least 80% plausible and the extractor agrees with the labels on at least 95% of notes. It counts only the rater kinds in `llm.gate_rater_kinds` (default `["human"]`; add `"llm"` to accept the LLM reviewer, which is then reported and recorded as "not a clinician"), and writes `realism/gate.json` for the manifest and dataset README
- `uv run data-gen review --estimate` dry-run the adversarial LLM reviewer (Sonnet 5.5, independent of the Haiku writer; no key needed); `review --yes` rates `realism/round0/sheet.json` from the note text (cached, capped); `review --mode browser --yes [--max-notes N]` has it operate the rating app and records `review.webm` plus `review-session.jsonl` (needs `uv sync --extra review`, `playwright install chromium` and a built `rating_ui/`). The gate fails a reviewer whose plausible rate for the old template controls is not 20 points below the LLM notes
- `uv run data-gen generate --note-source llm --yes` the full run into `data_llm/`; refuses to spend without `--yes`, stops at the call and spend caps with nothing written, and reuses `cache/llm_cache.jsonl`, so a rerun costs nothing

Rating app (from `rating_ui/`, Node via nvm, `npm install --ignore-scripts` avoids a node-gyp hang on this machine):

- `REALISM_ROUND_DIR=../data_gen/realism/round0 npm run dev` serve the rating tool on 127.0.0.1:3100 (a person types a name and rates; saves `ratings.<name>.json`)
- `npm run build && npm test` production build, then Playwright tests against a throwaway round

More commands are added as each capability lands.
