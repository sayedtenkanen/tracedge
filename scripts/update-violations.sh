#!/usr/bin/env bash
# update-violations.sh — Run checks, append to violations.json, report summary.
# Usage: bash scripts/update-violations.sh [--quiet]
# Called after each commit to track violation history.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
VIOLATIONS_FILE="$REPO_ROOT/violations.json"
QUIET=false

if [[ "${1:-}" == "--quiet" ]]; then
    QUIET=true
fi

# Run checks and capture JSON output
JSON_OUTPUT=$("$SCRIPT_DIR/check-violations.sh" --quiet 2>&1) || true

# If the script failed to produce JSON, create a fallback
if ! printf '%s\n' "$JSON_OUTPUT" | grep -q '"commit"'; then
    TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    COMMIT_SHA=$(git -C "$REPO_ROOT" rev-parse --short HEAD 2>/dev/null || echo "unknown")
    JSON_OUTPUT="{\"commit\":\"$COMMIT_SHA\",\"timestamp\":\"$TIMESTAMP\",\"ruff_check\":0,\"ruff_format\":0,\"mypy\":0,\"pytest_passed\":0,\"pytest_failed\":0,\"total_violations\":-1}"
fi

# Initialize violations.json if it doesn't exist
if [[ ! -f "$VIOLATIONS_FILE" ]]; then
    echo '{"history":[],"trends":{"total_commits":0,"clean_commits":0,"violation_rate":"0%"}}' > "$VIOLATIONS_FILE"
fi

# Append the new entry to history — pass JSON via stdin to avoid quoting issues
printf '%s\n' "$JSON_OUTPUT" | python3 -c "
import json, sys

with open('$VIOLATIONS_FILE') as f:
    data = json.load(f)

entry = json.load(sys.stdin)

# Avoid duplicates — skip if same commit already exists
if not any(h['commit'] == entry['commit'] for h in data['history']):
    data['history'].append(entry)

# Update trends
total = len(data['history'])
clean = sum(1 for h in data['history'] if h.get('total_violations', 0) == 0)
data['trends'] = {
    'total_commits': total,
    'clean_commits': clean,
    'violation_rate': f'{((total - clean) / total * 100):.0f}%' if total > 0 else '0%'
}

# Keep only last 100 entries
if len(data['history']) > 100:
    data['history'] = data['history'][-100:]

with open('$VIOLATIONS_FILE', 'w') as f:
    json.dump(data, f, indent=2)
    f.write('\n')
"

# Print summary
VIOLATIONS=$(printf '%s\n' "$JSON_OUTPUT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['total_violations'])")
COMMIT=$(printf '%s\n' "$JSON_OUTPUT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['commit'])")

if [[ "$VIOLATIONS" == "0" ]]; then
    if ! $QUIET; then
        echo "✅ [$COMMIT] Clean — violations.json updated"
    fi
else
    if ! $QUIET; then
        echo "❌ [$COMMIT] $VIOLATIONS violations — violations.json updated"
    fi
fi
