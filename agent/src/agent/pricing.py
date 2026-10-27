"""Dollars per million tokens (input, output), pinned. A model not listed is refused rather than priced at zero."""

PRICES_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.0, 10.0),
    "scripted": (0.0, 0.0),
}


def cost_usd(model_id: str, input_tokens: int, output_tokens: int) -> float:
    if model_id not in PRICES_PER_MTOK:
        raise KeyError(f"no price pinned for model {model_id!r}")
    p_in, p_out = PRICES_PER_MTOK[model_id]
    return (input_tokens * p_in + output_tokens * p_out) / 1_000_000
