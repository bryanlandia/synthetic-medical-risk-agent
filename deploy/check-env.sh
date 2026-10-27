#!/usr/bin/env bash
# Check an agent project's Vercel environment variables by name (values are never read).
#   deploy/check-env.sh <project-name>
# Preview: the scripted model and no API key or store credential, so a preview URL cannot spend money.
# Production: the API key, the shared secret, the store and the daily cap, and not the scripted model.
set -u
project="${1:?usage: deploy/check-env.sh <vercel-project-name>}"
names() { vercel env ls --project "$project" -e "$1" 2>/dev/null | awk '$1 ~ /^[A-Z_]+$/ && $1 != "Environment" {print $1}'; }
preview="$(names preview)"; production="$(names production)"
bad=0
has() { grep -qx "$2" <<<"$1"; }
need() { has "$1" "$2" || { echo "FAIL ($3): $2 is not set"; bad=1; }; }
forbid() { has "$1" "$2" && { echo "FAIL ($3): $2 must not be set"; bad=1; }; }
need "$preview" AGENT_SCRIPTED_MODEL preview
need "$preview" AGENT_SHARED_SECRET preview
forbid "$preview" ANTHROPIC_API_KEY preview
forbid "$preview" AGENT_STORE_TOKEN preview
for v in ANTHROPIC_API_KEY AGENT_SHARED_SECRET AGENT_ENV AGENT_DAILY_BUDGET_USD AGENT_STORE_URL AGENT_STORE_TOKEN; do need "$production" "$v" production; done
forbid "$production" AGENT_SCRIPTED_MODEL production
forbid "$production" AGENT_RELAX_LIMITS production
[ "$bad" -eq 0 ] && echo "environment variables look right for $project"
exit "$bad"
