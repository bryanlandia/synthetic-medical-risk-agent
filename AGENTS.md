# Synthetic Medical Risk Agent

Portfolio demo. **All medical data is synthetic and the disease is fictional.** The agent must never give real medical advice. Specs, decisions and change proposals live in `openspec/`.

## Layout

- `data_gen/` seeded synthetic data generator
- `risk_model/` numpy-only inference (note reader, classifier, report assembly); no scikit-learn or MLflow, so a service image can carry it
- `training/` classifier + LoRA training, MLflow tracking (writes the model files `risk_model` loads)
- `agent/` FastAPI + Strands chat service: guards, a no-argument scoring tool, a reply check (depends on `risk_model` only)
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
- `uv run data-gen pilot --note-source llm --yes` write the small blind rating sample to `realism/round0/` (`sheet.md` to rate, `key.json` not to open until done); `--round N --setting S` re-rates a revised setting with fresh notes; the pilot also prints a variety report per setting (how often notes open the same way, how many style-trait combinations) and flags a setting that is too uniform
- `uv run data-gen gate` check the saved ratings in `realism/round*/` (`ratings.<rater>.json` from the rating app or the reviewer, or a hand-filled `ratings.md`); exit 0 only if every setting is at least 80% plausible and the extractor agrees with the labels on at least 95% of notes. It counts only the rater kinds in `llm.gate_rater_kinds` (default `["human"]`; `--config configs/llm_reviewer_gate.json` accepts the LLM reviewer, which is then reported and recorded as "not a clinician"; run it with `--rounds N` for the latest round, since an older round's reviewer file from an earlier prompt is not comparable), and writes `realism/gate.json` for the manifest and dataset README
- `uv run data-gen review --estimate` dry-run the adversarial LLM reviewer (Sonnet 5.5, independent of the Haiku writer; no key needed; every note is shown with its kind, such as AI-scribe draft or EHR template, and what is normal for it, in the app and in the reviewer's prompt, so each is judged against its own kind); `review --yes` rates the highest round's `sheet.json` from the note text (cached, capped; `--round N` picks another, and the recording, session log and ratings all go in that round's folder); `review --mode browser --yes [--max-notes N] [--pause SECONDS]` has it operate the rating app (`--max-notes N` rates a sample spread evenly over the four settings, so each shows on the recording) (pausing about 3 s on each finished note and comment so the recording is readable) and records `review.webm` plus `review-session.jsonl` (needs `uv sync --extra review`, `playwright install chromium` and a built `rating_ui/`). The gate fails a reviewer whose plausible rate for the old template controls is not 20 points below the LLM notes
- `uv run data-gen generate --note-source llm --yes` the full run into `data_llm/`; refuses to spend without `--yes`, stops at the call and spend caps with nothing written, and reuses `cache/llm_cache.jsonl`, so a rerun costs nothing

Evals (from `evals/`, same uv setup; see `evals/README.md`; the reference systems need no API key):

- `uv sync` install; `uv run pytest -q` harness tests
- `uv run evals run --system {oracle,floor,lab_only} --split dev [--limit N]` run a reference system through Inspect; `test` and `adversarial` need `--final` and are recorded in `results/ledger.json`
- `uv run evals baselines` regenerate the baseline summaries and `results/targets_v1.json`; `uv run evals regression` the fast key-free subset CI runs (fails if the oracle misses the ceiling, a grader is broken or a baseline drifts)
- `uv run evals failures runs/<system>/<split>/trials.jsonl --grader <name>` read a seeded sample of failing transcripts
- Iterate on the dev split only (`evals.devsplit.dev_ids`); training must use `train_ids`

Frontier baseline (from `evals/`; paid steps need `--yes` and `ANTHROPIC_API_KEY` exported in your own shell; see `evals/README.md`):

- `uv run evals estimate [--prompt v1] [--model haiku|sonnet] [--stage all|dev|test|adversarial|trials]` calls, tokens and cost per stage against its cap; no call, no key
- `uv run evals iterate --prompt vN [--model haiku] [--limit N] [--note "..."] --yes` score a prompt version on dev (at most 5 versions; `--limit` is an unrecorded smoke run); `uv run evals freeze --prompt vN` ends iteration
- `uv run evals run --system frontier --prompt vN --model haiku --split {dev,test,adversarial} [--suites consistency --trials 3] --final --yes` the stages; `test` and `adversarial` need a freeze and are one look each (`--force` repeats, warned)
- `uv run evals report` writes `results/frontier/report.md`; it is INCOMPLETE (exit 1) until `results/frontier/reading.json` records the failing transcripts read for each failed grader

Classifier (from `training/`, same uv setup; no API key and no spend; see `training/README.md` and `training/model/MODEL_CARD.md`):

- `uv sync` install; `uv run pytest -q` tests (about 1.5 minutes)
- `uv run training train` fit the note reader and the classifier on train **without dev**, choose the settings on dev, write `model/` (JSON files, manifest with the model hash, metrics, model card) and log an MLflow run to the local `mlruns/`; two runs with the same seed give byte-identical files. `training reader` fits only the reader; `training lexicon`, `training card` and `training latency` refresh the lexicon, the card and the speed/size file
- `uv run evals run --system classifier --split dev` score the committed model through the harness (run from `training/`: the classifier system lives there; results go to `evals/results/classifier/`)
- `uv run training freeze` records the model hash after a dev run; then `uv run evals run --system classifier --split {test,adversarial} --final` once each, and `--split test --suites consistency --trials 3 --final` once; a repeat needs `--force` (recorded and warned about)
- `uv run training report` writes `evals/results/classifier/report.md`; INCOMPLETE (exit 1) until `evals/results/classifier/reading.json` records the failing transcripts read for each missed target
- `uv run evals compare [--split {dev,test}] [--model haiku]` (from `evals/` or `training/`): classifier against the frontier baseline on the same patients, paired differences with patient-clustered intervals, written to `evals/results/classifier/comparison_<split>.md`
- Inference uses `risk_model` (its own project, numpy only: `risk_model.load().report(view)`, directory from `RISK_MODEL_DIR` or `training/model`; tests: `uv run pytest -q` from `risk_model/`); training code never imports from the agent, and `evals` does not import `training` except to run the `classifier` system

Agent (from `agent/`, same uv setup; see `agent/README.md`):

- `uv sync` install; `uv run pytest -q` tests (scripted model: no key, no network, no spend)
- `AGENT_SCRIPTED_MODEL=1 AGENT_LOCAL_DEV=1 uv run agent serve` run locally for free; with `ANTHROPIC_API_KEY` and `AGENT_SHARED_SECRET` exported in your own shell it uses Haiku 5.5. `uv run agent live-check` sends 5 hand-picked messages through the real model (a few cents)
- Evals (from `evals/`): `uv run evals estimate --system agent` (no key); `uv run evals run --system agent --split dev` starts the service itself with the scripted model, `--live --yes` uses the real one (the service's own daily cap is set to the stage cap), `--base-url URL --secret S` scores a running service; `uv run evals agent-scope` runs the 66-prompt scope set; `test` and `adversarial` need a dev run of the same system and `--final`, once each (`--force` repeats, warned). The agent's guard tests also run in `uv run evals regression`
- Inference is `risk_model`; `agent/` must not depend on `training`, `evals` or `data_gen` (their `anthropic` requirements conflict with Strands')

Rating app (from `rating_ui/`, Node via nvm, `npm install --ignore-scripts` avoids a node-gyp hang on this machine):

- `REALISM_ROUND_DIR=../data_gen/realism/round0 npm run dev` serve the rating tool on 127.0.0.1:3100 (a person types a name and rates; saves `ratings.<name>.json`)
- `npm run build && npm test` production build, then Playwright tests against a throwaway round

More commands are added as each capability lands.
