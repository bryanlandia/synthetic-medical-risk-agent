"""Repository-level guarantees: the hidden rule stays inside data_gen/, and datasets stay small."""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "data_gen" / "data"
OTHER_DIRS = ("training", "agent", "evals", "web")
SKIP = {"node_modules", ".venv", ".next", "__pycache__", ".git"}
RULE_IMPORT = re.compile(
    r"data_gen[./]rule\b|from\s+data_gen\s+import\s+[^\n]*\brule\b|\bLAB_WEIGHTS\b|\bFLAG_WEIGHTS\b"
    r"|\bcalibrated_intercept\b|\btrue_probability\s*\("
)
MAX_DATASET_BYTES = 15 * 1024 * 1024  # generous cap; the committed default dataset is ~10 MB


def source_files(root: Path):
    for path in root.rglob("*"):
        if path.is_file() and not (set(path.parts) & SKIP) and path.suffix in {".py", ".ts", ".tsx", ".js", ".json", ".md", ".yaml", ".yml", ".toml"}:
            yield path


def test_scoring_rule_not_used_outside_data_gen():
    offenders = []
    for name in OTHER_DIRS:
        base = REPO / name
        if not base.exists():
            continue
        for path in source_files(base):
            if RULE_IMPORT.search(path.read_text(errors="ignore")):
                offenders.append(str(path.relative_to(REPO)))
    assert offenders == []


def test_dataset_files_do_not_leak_the_rule():
    if not DATA.exists():
        return
    for path in DATA.glob("*"):
        text = path.read_text()
        for word in ("LAB_WEIGHTS", "FLAG_WEIGHTS", "intercept", "coefficient", "interaction"):
            assert word not in text, (path.name, word)


def test_dataset_size_within_limit():
    if not DATA.exists():
        return
    total = sum(p.stat().st_size for p in DATA.glob("*") if p.is_file())
    assert total <= MAX_DATASET_BYTES, total
