"""Seeded style traits for LLM-written notes: the habits that make one clinician's note differ from another's.

Without sampling controls the model settles on one house style per prompt. Variety therefore comes from the
inputs: for every note, code draws a few traits for the setting from the note's render seed (so the draw is
reproducible and independent of every other plan field) and the prompt turns them into instructions. The traits
are stored in the plan, so evaluations can slice results by them. Quick settings get fewer traits, so they vary
less, as real quick notes do.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Trait:
    key: str
    choices: dict[str, str]  # value -> the instruction shown to the writer


def _t(key: str, **choices: str) -> Trait:
    return Trait(key, dict(choices))


EXEMPLAR_COUNT = 6  # exemplar notes per setting (prompts/exemplars/<setting>.txt)

TRAITS: dict[str, tuple[Trait, ...]] = {
    "shorthand": (
        _t("labs",
           pairs='Write each lab as its abbreviation and value only, for example "ABC 123", with no unit (except labs marked to write the unit).',
           units='Write each lab as abbreviation, value and unit, for example "ABC 123 mg/dL".',
           words='Write each lab with its short name, a colon and the value, for example "Name: 123".'),
        _t("order",
           labs_first="Put the labs before the symptoms.",
           symptoms_first="Put the symptoms before the labs."),
        _t("negatives",
           grouped='Fold the denied symptoms into one fragment, for example "denies A, B".',
           separate='Write each denied symptom on its own, for example "no A. no B."'),
        _t("closing",
           rtc='End with a return-to-clinic fragment such as "RTC 6 wks".',
           fu='End with a follow-up fragment such as "f/u if worse".',
           none="Add no closing fragment."),
    ),
    "ehr_template": (
        _t("labels",
           caps='Write the section headings in capitals with a colon, for example "ROS:" and "RESULTS:".',
           title='Write the section headings in title case with a colon, for example "Review of Systems:" and "Results:".',
           bracket='Write the section headings in square brackets, for example "[ROS]" and "[Results]".'),
        _t("order",
           history_ros_results_plan="Order: history, review of systems, results, plan.",
           results_first="Order: results first, then history, review of systems, plan.",
           history_results_ros_plan="Order: history, results, review of systems, plan."),
        _t("ros",
           by_system="Group the review of systems on separate lines by body system.",
           one_line='Write the review of systems as one or two lines, for example "Positive for A. Negative for B, C."'),
        _t("results",
           list="List each lab on its own line.",
           inline="Put the results on one line separated by semicolons.",
           dashes="List each lab on its own line starting with a dash."),
        _t("plan",
           numbered="Write the plan as a short numbered list of one or two items.",
           one_line="Write the plan as a single line."),
        _t("filler",
           reviewed='Include the stock line "Medications and allergies reviewed." once, near the top.',
           chart='Include the stock line "Chart reviewed prior to visit." once, near the top.',
           none="Include no stock filler lines."),
    ),
    "ai_scribe": (
        _t("layout",
           soap='Use the headings "Subjective:", "Objective:" and "Assessment and Plan:".',
           hpi='Use the headings "History of Present Illness:" and "Assessment and Plan:".',
           summary='Use one heading, "Visit Summary:", followed by short paragraphs.',
           plain="Use no headings: two short paragraphs."),
        _t("length",
           brief="Keep it to about 90 words.",
           full="Make it about 150 words."),
        _t("verb",
           reports='Attribute statements with "reports" and "notes".',
           states='Attribute statements with "states" and "mentions".',
           says='Attribute statements with "describes" and "says".'),
        _t("labs",
           data="Put the lab values in the objective or data part, as results that were reviewed with the patient.",
           inline="Mention the lab values inside a sentence about reviewing the results with the patient."),
        _t("closer",
           weeks="End with one sentence about a return visit in a few weeks.",
           schedule="End with one sentence saying the next visit is already scheduled.",
           no_changes="End with one sentence saying nothing is being changed for now."),
        _t("filler",
           understanding='Include the stock sentence "The patient verbalized understanding." near the end.',
           questions='Include the stock sentence "All questions were answered." near the end.',
           none="Include no stock closing sentence."),
    ),
    "copy_forward": (
        _t("opener",
           seen='Open with the stock line "Seen in clinic for follow-up."',
           returned='Open with the stock line "Return visit."',
           note='Open with the stock line "Follow-up note."',
           interval='Open with the stock line "Interval visit."'),
        _t("boilerplate",
           history='Include the stock line "Past history reviewed, unchanged." as carried-over text.',
           family='Include the stock line "Family history reviewed, no changes." as carried-over text.',
           meds='Include the stock line "Medications reviewed with patient." as carried-over text.'),
        _t("marker",
           updated='Introduce the new information with "Updated:".',
           today='Introduce the new information with "Today:".',
           interval='Introduce the new information with "Interval:".',
           none="Do not mark the new information; just let it follow the carried-over lines."),
        _t("layout",
           lists="Use short dash lists for the symptoms and the results.",
           compact="Use compact lines, one for the symptoms and one for the results."),
        _t("plan",
           continue_="End by saying to continue the current monitoring plan.",
           recheck="End with a line about rechecking at the next scheduled visit."),
    ),
}


def choose_traits(setting: str, seed: int) -> dict[str, str]:
    """One value per trait, drawn from a stream that depends only on the note's render seed."""
    rng = np.random.default_rng([seed, 17])
    return {t.key: list(t.choices)[int(rng.integers(0, len(t.choices)))] for t in TRAITS[setting]}


def exemplar_picks(setting: str, seed: int, n_available: int, k: int = 2) -> list[int]:
    """Which exemplar notes to show (indices), drawn from another seeded stream."""
    rng = np.random.default_rng([seed, 29])
    return sorted(int(i) for i in rng.choice(n_available, size=min(k, n_available), replace=False))


def stock_lines(setting: str, traits: dict[str, str]) -> list[str]:
    """Stock lines the traits ask the writer to include verbatim; they are not copying."""
    import re

    return [m for line in trait_lines(setting, traits) for m in re.findall(r'stock (?:line|sentence) "([^"]+)"', line)]


def trait_lines(setting: str, traits: dict[str, str]) -> list[str]:
    by_key = {t.key: t for t in TRAITS[setting]}
    return [by_key[k].choices[v] for k, v in traits.items() if k in by_key and v in by_key[k].choices]
