"""Text intake: one free-text message becomes the record view the classifier reads.

The lab values come from the numbers the message writes next to a lab's name or abbreviation, read by pattern; nothing is
inferred, rounded or filled in, and no language model is involved. The note is the whole message, so the existing checks
(alternate unit, a later value that disagrees, an impossible value) work on it as they do on a note.
"""

from __future__ import annotations

from typing import Any

from . import labvalues
from .labs import LABS

MESSAGE_ID = "message"


def view_from_text(text: str, patient_id: str = MESSAGE_ID) -> dict[str, Any]:
    """The view for ``text``: eight panel entries (the first stated value of each lab in the usual unit, else null) and the
    note. The same text always gives the same view."""
    first: dict[str, labvalues.Stated] = {}
    for stated in labvalues.read(text):
        first.setdefault(stated.lab, stated)
    panel = []
    for lab in LABS:
        stated = first.get(lab.key)
        value = None if stated is None else labvalues.usual_value(lab, stated)
        panel.append({"lab": lab.key, "value": value, "unit": lab.unit})
    return {"patient_id": patient_id, "panel": panel, "note": text}
