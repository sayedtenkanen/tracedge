#!/usr/bin/env bash
# check-violations.sh — Run all checks and output structured JSON results.
# Usage: bash scripts/check-violations.sh [--quiet]
# Exit code: 0 if clean, 1 if any violations found.

set -uo pipefail

QUIET=false
if [[ "${1:-}" == "--quiet" ]]; then
    QUIET=true
fi

# Capture results
RUFF_CHECK=0
RUFF_FORMAT=0
MYPY=0
PYTEST_PASSED=0
PYTEST_FAILED=0

# --- ruff check (JSON output for reliable parsing) ---
ruff_json=$(ruff check --output-format json --exit-zero src/ tests/ examples/ 2>&1) || true
RUFF_CHECK=$(printf '%s\n' "$ruff_json" | jq 'length')

# --- ruff format (count files needing reformatting) ---
format_output=$(ruff format --check src/ tests/ examples/ 2>&1) || true
RUFF_FORMAT=$(printf '%s\n' "$format_output" | sed -n 's/Would reformat \([0-9][0-9]*\).*/\1/p' | head -1)
RUFF_FORMAT=${RUFF_FORMAT:-0}

# --- mypy ---
mypy_output=$(mypy src/ tests/ examples/ --strict 2>&1) || true
if printf '%s\n' "$mypy_output" | grep -q "Success: no issues"; then
    MYPY=0
else
    MYPY=$(printf '%s\n' "$mypy_output" | grep -c "error:" || true)
    MYPY=${MYPY:-0}
fi

# --- pytest ---
pytest_output=$(pytest tests/ --tb=no -q 2>&1) || true
PYTEST_PASSED=$(printf '%s\n' "$pytest_output" | sed -n 's/\([0-9]*\) passed.*/\1/p' | head -1)
PYTEST_PASSED=${PYTEST_PASSED:-0}
PYTEST_FAILED=$(printf '%s\n' "$pytest_output" | sed -n 's/\([0-9]*\) failed.*/\1/p' | head -1)
PYTEST_FAILED=${PYTEST_FAILED:-0}

# --- Total violations ---
TOTAL=$((RUFF_CHECK + RUFF_FORMAT + MYPY + PYTEST_FAILED))

# --- Commit info ---
COMMIT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
COMMIT_MSG=$(git log -1 --pretty=%s 2>/dev/null || echo "unknown")
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# --- Output JSON ---
cat <<EOF
{
  "commit": "$COMMIT_SHA",
  "commit_msg": "$COMMIT_MSG",
  "timestamp": "$TIMESTAMP",
  "ruff_check": $RUFF_CHECK,
  "ruff_format": $RUFF_FORMAT,
  "mypy": $MYPY,
  "pytest_passed": $PYTEST_PASSED,
  "pytest_failed": $PYTEST_FAILED,
  "total_violations": $TOTAL
}
EOF

# --- Summary line ---
if [[ "$TOTAL" -eq 0 ]]; then
    if ! $QUIET; then
        echo "✅ Clean — 0 violations (ruff: 0, format: 0, mypy: 0, tests: ${PYTEST_PASSED} passed)"
    fi
    exit 0
else
    if ! $QUIET; then
        echo "❌ $TOTAL violations — ruff: $RUFF_CHECK, format: $RUFF_FORMAT, mypy: $MYPY, test failures: $PYTEST_FAILED"
    fi
    exit 1
fi
