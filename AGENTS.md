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

More commands are added as each capability lands.
