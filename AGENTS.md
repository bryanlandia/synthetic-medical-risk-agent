# Synthetic Medical Risk Agent

Portfolio demo. **All medical data is synthetic and the disease is fictional.** The agent must never give real medical advice. Specs, decisions and change proposals live in `openspec/`.

## Layout

- `data_gen/` seeded synthetic data generator
- `training/` classifier + LoRA training, MLflow tracking
- `agent/` FastAPI + Strands agent and tools
- `evals/` Inspect AI tasks, promptfoo configs, datasets, reports
- `web/` Next.js app (Vercel root dir)
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
- `uv run data-gen gate` check the saved `realism/round*/ratings.md`; exit 0 only if every setting is at least 80% plausible and the extractor agrees with the hand labels on at least 95% of notes
- `uv run data-gen generate --note-source llm --yes` the full run into `data_llm/`; refuses to spend without `--yes`, stops at the call and spend caps with nothing written, and reuses `cache/llm_cache.jsonl`, so a rerun costs nothing

More commands are added as each capability lands.
