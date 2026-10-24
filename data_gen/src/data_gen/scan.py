"""Identifier scan: notes must not contain real-looking identifiers or real facility names."""

from __future__ import annotations

import re

_PATTERNS = {
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "mrn": re.compile(r"\bMRN\b[\s:#-]*\d{4,}", re.IGNORECASE),
    "phone": re.compile(r"(?<!\d)\(?\d{3}\)?[-. ]\d{3}[-. ]\d{4}(?!\d)"),
    "email": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b"),
}

FACILITY_DENYLIST = (
    "mayo clinic", "cleveland clinic", "kaiser", "johns hopkins", "mass general",
    "massachusetts general", "mount sinai", "cedars-sinai", "stanford health", "nhs",
)


def scan_text(text: str) -> list[str]:
    """Return a list of findings (empty = clean)."""
    findings = [name for name, pat in _PATTERNS.items() if pat.search(text)]
    lower = text.lower()
    findings += [f"facility:{f}" for f in FACILITY_DENYLIST if re.search(rf"\b{re.escape(f)}\b", lower)]
    return findings
