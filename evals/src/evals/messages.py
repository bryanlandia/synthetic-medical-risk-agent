"""How a record becomes one chat message: the single place that says what a "message" is.

A "Labs:" list (lab name, abbreviation, value, usual unit; labs with no value are left out) followed by a "Note:" section with
the note text. Nothing but the input view is used, so a message contains no ground-truth field.
"""

from __future__ import annotations

from typing import Any

from data_gen.labs import LAB_BY_KEY

from .records import assert_clean_view


def render_message(view: dict[str, Any]) -> str:
    assert_clean_view(view)
    lines = ["Labs:"]
    for entry in view["panel"]:
        if entry["value"] is None:
            continue
        lab = LAB_BY_KEY[entry["lab"]]
        lines.append(f"- {lab.name} ({lab.abbr}): {entry['value']:g} {entry['unit']}")
    return "\n".join([*lines, "", "Note:", view["note"]])
