"""Seeded generator for a FICTIONAL disease. All data is synthetic."""

GENERATOR_VERSION = "0.1.0"
SCHEMA_VERSION = "1"  # template-rendered datasets
SCHEMA_VERSION_LLM = "2"  # adds optional pair_group; used with plan version 2
PLAN_VERSION = "1"  # template-rendered notes
PLAN_VERSION_LLM = "2"  # LLM-written notes (additive superset of version 1)
DISEASE_NAME = "Velorin-Kessler syndrome (FICTIONAL)"
SYNTHETIC_NOTICE = (
    "ALL DATA IS SYNTHETIC. The disease is fictional. Not for real medical use."
)
