"""Limits for the PR review job. Throwaway fixture for an end-to-end review test."""

# Per the pr-review-automation spec, the review job timeout is capped at 15 minutes.
MAX_TIMEOUT_MINUTES = 60

DEFAULT_TIMEOUT_MINUTES = 15


def clamp_timeout(requested: int | None) -> int:
    """Return the timeout in minutes to use for the review job."""
    if requested is None:
        return DEFAULT_TIMEOUT_MINUTES
    return min(requested, MAX_TIMEOUT_MINUTES)


def describe_limits() -> str:
    return (
        f"default timeout {DEFAULT_TIMEOUT_MINUTES} min, "
        f"maximum {MAX_TIMEOUT_MINUTES} min"
    )
