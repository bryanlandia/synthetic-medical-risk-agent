# data_gen

Seeded generator for a **fictional** disease.

> **ALL DATA IS SYNTHETIC. The disease is fictional. Nothing here is real patient data, and nothing here may be used for real medical purposes.**

Patients, lab values, symptoms, labels and clinical notes are all invented. The disease ("Velorin-Kessler syndrome") is defined by a hidden scoring rule over made-up lab values and symptom flags, so the ground truth of every example is known exactly.

## Datasets

- `data/` holds **template-rendered test fixtures** (two note styles, `terse` and `templated`). Their wording is deliberately simple and repetitive, so they are useful for fast tests and CI but are **not realistic documentation and must not be used for published results**.
- `data_llm/` holds the **LLM-written dataset** in four clinician-authored documentation settings (`shorthand`, `ehr_template`, `ai_scribe`, `copy_forward`), with matched-pair groups in the test split. Results should come from this dataset. It is produced only after the realism gate passes (see AGENTS.md for the `estimate`, `pilot`, `review`, `gate` and `generate` commands). The gate is passed by a human rater by default, using the `rating_ui/` tool; a run that accepts the adversarial LLM reviewer instead says so in the manifest and in the dataset `README.md` ("an LLM review, not a clinician"). Either way this is a plausibility check, not a clinical validation.

Commands are documented as they land (see AGENTS.md).
