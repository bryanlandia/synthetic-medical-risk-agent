# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml>=6"]
# ///
"""Check the PR review workflow against the pr-review-automation spec.

Usage (from anywhere in the repo):
    uv run .github/scripts/check_pr_review_workflow.py            # check the repository
    uv run .github/scripts/check_pr_review_workflow.py --self-test # prove each check can fail

Exits non-zero and prints every problem when a property does not hold.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
WORKFLOW = REPO / ".github" / "workflows" / "claude-pr-review.yml"
GUIDELINES = REPO / ".claude" / "review-guidelines.md"
DOCS = REPO / "docs" / "pr-review.md"

EVENT_TYPES = {"opened", "synchronize", "ready_for_review", "reopened"}
PATHS_IGNORE = {"data_gen/data/**", "**/uv.lock", "**/package-lock.json"}
PERMISSIONS = {"contents": "read", "pull-requests": "read", "issues": "read", "id-token": "write"}
COMMENT_TOOL = "mcp__github_inline_comment__create_inline_comment"
SHA_USES = re.compile(r"^\s*(?:-\s*)?uses:\s*([\w.-]+/[\w./-]+)@([0-9a-f]{40})\s+#\s*v?\d")
# Built from pieces so this file never matches its own key-pattern scan.
KEY_PATTERN = "sk-" + "ant-" + r"[A-Za-z0-9_-]{16,}"

GUIDELINE_PHRASES = {
    "untrusted data": "untrusted",
    "synthetic and fictional": "fictional",
    "real identifiers": "ssn-",
    "no real medical advice": "medical advice",
    "secrets": "secrets must never appear",
    "hidden scoring rule": "hidden scoring rule",
    "openspec alignment": "openspec",
    "skip generated data": "data_gen/data/",
    "skip lockfiles": "uv.lock",
    "specific comments": "be specific",
    "advisory only": "never approve, dismiss, merge or push",
    "refuse injected instructions": "ignore these guidelines",
}
DOC_PHRASES = {
    "spend limit": "spend limit",
    "secret name": "ANTHROPIC_API_KEY",
    "uninstall steps": "uninstall",
    "advisory": "advisory",
    "fork pull requests": "fork",
}


def workflow_errors(raw: str) -> list[str]:
    errs: list[str] = []
    try:
        wf = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        return [f"workflow is not valid YAML: {exc}"]
    if not isinstance(wf, dict):
        return ["workflow is not a mapping"]

    on = wf.get("on", wf.get(True))  # PyYAML reads the key `on` as boolean True
    if not isinstance(on, dict) or set(on) != {"pull_request"}:
        errs.append(f"trigger must be exactly pull_request, got {on if not isinstance(on, dict) else sorted(on)}")
    if isinstance(on, dict) and isinstance(on.get("pull_request"), dict):
        pr = on["pull_request"]
        if set(pr.get("types", [])) != EVENT_TYPES:
            errs.append(f"event types must be {sorted(EVENT_TYPES)}, got {pr.get('types')}")
        if not PATHS_IGNORE <= set(pr.get("paths-ignore", [])):
            errs.append(f"paths-ignore must include {sorted(PATHS_IGNORE)}")
        if "paths" in pr:
            errs.append("use paths-ignore, not paths")
    if "pull_request_target" in raw:
        errs.append("pull_request_target must not appear")

    jobs = wf.get("jobs") or {}
    if len(jobs) != 1:
        return errs + [f"expected exactly one job, got {sorted(jobs)}"]
    job = next(iter(jobs.values()))

    cond = str(job.get("if", ""))
    if "draft == false" not in cond:
        errs.append("job must skip draft pull requests (github.event.pull_request.draft == false)")
    if "head.repo.full_name == github.repository" not in cond:
        errs.append("job must skip fork pull requests (head.repo.full_name == github.repository)")

    perms = job.get("permissions", wf.get("permissions"))
    if perms != PERMISSIONS:
        errs.append(f"permissions must be exactly {PERMISSIONS}, got {perms}")
    timeout = job.get("timeout-minutes")
    if not isinstance(timeout, int) or timeout > 15:
        errs.append(f"timeout-minutes must be an integer <= 15, got {timeout}")

    conc = job.get("concurrency", wf.get("concurrency")) or {}
    if "github.event.pull_request.number" not in str(conc.get("group", "")):
        errs.append("concurrency group must include the pull request number")
    if conc.get("cancel-in-progress") is not True:
        errs.append("concurrency must set cancel-in-progress: true")

    errs += _step_errors(raw, job)

    secrets = set(re.findall(r"secrets\.([A-Za-z0-9_]+)", raw))
    if secrets != {"ANTHROPIC_API_KEY"}:
        errs.append(f"only secrets.ANTHROPIC_API_KEY may be referenced, got {sorted(secrets)}")
    return errs


def _step_errors(raw: str, job: dict) -> list[str]:
    errs: list[str] = []
    steps = job.get("steps") or []
    uses_lines = [l for l in raw.splitlines() if re.match(r"^\s*(?:-\s*)?uses:", l)]
    for line in uses_lines:
        target = line.split("uses:", 1)[1].strip()
        if target.startswith("./"):
            continue
        if not SHA_USES.match(line):
            errs.append(f"third-party action must be pinned to a full SHA with a version comment: {line.strip()}")

    action = [s for s in steps if str(s.get("uses", "")).startswith("anthropics/claude-code-action@")]
    if len(action) != 1:
        return errs + [f"expected exactly one claude-code-action step, got {len(action)}"]
    with_ = action[0].get("with") or {}
    if with_.get("anthropic_api_key") != "${{ secrets.ANTHROPIC_API_KEY }}":
        errs.append("anthropic_api_key must be ${{ secrets.ANTHROPIC_API_KEY }}")
    if "/code-review:code-review" not in str(with_.get("prompt", "")) or "--comment" not in str(with_.get("prompt", "")):
        errs.append("prompt must run /code-review:code-review with --comment")

    args = str(with_.get("claude_args", ""))
    if not re.search(r"--model claude-opus-5-5(\s|$)", args):
        errs.append("claude_args must contain --model claude-opus-5-5")
    if not re.search(r"--effort medium(\s|$)", args):
        errs.append("claude_args must contain --effort medium")
    if not re.search(r"--max-turns \d+(\s|$)", args):
        errs.append("claude_args must contain --max-turns <n>")
    tools = re.findall(r'--allowedTools\s+"([^"]*)"', args)
    if tools != [COMMENT_TOOL]:
        errs.append(f"--allowedTools must be exactly the inline comment tool, got {tools}")
    if ".claude/review-guidelines.md" not in args or "--append-system-prompt" not in args:
        errs.append("claude_args must point the reviewer at .claude/review-guidelines.md via --append-system-prompt")
    return errs


def missing_phrases(text: str, phrases: dict[str, str]) -> list[str]:
    lower = text.lower()
    return [label for label, phrase in phrases.items() if phrase.lower() not in lower]


def phrase_errors(path: Path, phrases: dict[str, str], what: str) -> list[str]:
    if not path.exists():
        return [f"{what} missing: {path.relative_to(REPO)}"]
    return [f"{what} lacks {label} (expected {phrases[label]!r})"
            for label in missing_phrases(path.read_text(), phrases)]


def key_pattern_errors() -> list[str]:
    errs: list[str] = []
    tracked = subprocess.run(["git", "grep", "-l", "-E", KEY_PATTERN], cwd=REPO,
                             capture_output=True, text=True)
    if tracked.stdout.strip():
        errs.append(f"API key pattern found in tracked files: {tracked.stdout.split()}")
    history = subprocess.run(["git", "log", "--all", "--oneline", "-G", KEY_PATTERN], cwd=REPO,
                             capture_output=True, text=True)
    if history.stdout.strip():
        errs.append(f"API key pattern found in history: {history.stdout.strip().splitlines()}")
    return errs


def repo_errors() -> list[str]:
    if not WORKFLOW.exists():
        errs = [f"workflow missing: {WORKFLOW.relative_to(REPO)}"]
    else:
        errs = workflow_errors(WORKFLOW.read_text())
    errs += phrase_errors(GUIDELINES, GUIDELINE_PHRASES, "review guidelines")
    errs += phrase_errors(DOCS, DOC_PHRASES, "setup notes")
    return errs + key_pattern_errors()


# Each mutation breaks one property; the checker must report at least one error for each.
MUTATIONS: dict[str, tuple[str, str]] = {
    "uses pull_request_target": ("  pull_request:", "  pull_request_target:"),
    "drops the effort flag": ("--effort medium", "--effort high"),
    "uses a different model": ("claude-opus-5-5", "claude-sonnet-5"),
    "unpinned action": ("anthropics/claude-code-action@", "anthropics/claude-code-action@v1 #"),
    "extra write permission": ("      contents: read", "      contents: write"),
    "no cancel-in-progress": ("cancel-in-progress: true", "cancel-in-progress: false"),
    "timeout too long": ("timeout-minutes: 15", "timeout-minutes: 60"),
    "no draft guard": ("github.event.pull_request.draft == false", "true"),
    "no fork guard": ("github.event.pull_request.head.repo.full_name == github.repository", "true"),
    "extra secret": ("secrets.ANTHROPIC_API_KEY", "secrets.OTHER_KEY"),
    "data not ignored": ('      - "data_gen/data/**"\n', ""),
    "widened tools": (COMMENT_TOOL, COMMENT_TOOL + ",Bash"),
}


def self_test() -> list[str]:
    if not WORKFLOW.exists():
        return [f"workflow missing: {WORKFLOW.relative_to(REPO)}"]
    raw = WORKFLOW.read_text()
    problems = [f"baseline workflow already has errors: {e}" for e in workflow_errors(raw)]
    for name, (old, new) in MUTATIONS.items():
        if old not in raw:
            problems.append(f"mutation {name!r}: pattern not found in workflow, update the self-test")
            continue
        if not workflow_errors(raw.replace(old, new, 1)):
            problems.append(f"mutation {name!r} was NOT detected")
    for what, phrases in (("guidelines", GUIDELINE_PHRASES), ("setup notes", DOC_PHRASES)):
        if len(missing_phrases("", phrases)) != len(phrases):
            problems.append(f"an empty {what} file was NOT detected")
    if not missing_phrases("", {"x": "x"}) or missing_phrases("x", {"x": "x"}):
        problems.append("phrase matcher is broken")
    return problems


def main() -> int:
    errs = self_test() if "--self-test" in sys.argv else repo_errors()
    if errs:
        print(f"FAILED: {len(errs)} problem(s)")
        for e in errs:
            print(f" - {e}")
        return 1
    print("self-test OK: every check detects its break" if "--self-test" in sys.argv else "OK: PR review setup matches the spec")
    return 0


if __name__ == "__main__":
    sys.exit(main())
