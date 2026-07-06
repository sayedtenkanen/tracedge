#!/usr/bin/env bash
# Run plan conformance tests only.
# Usage: bash scripts/test-plan.sh

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

echo "Running plan conformance tests..."
pytest tests/plan/ -v --tb=short "$@"

echo ""
echo "Done. 0 failures = plan matches reality."
echo "A failure means either code drifted or plan is stale — investigate."
