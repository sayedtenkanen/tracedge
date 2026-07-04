#!/usr/bin/env bash
# Check CI status for the latest workflow run
# Usage: bash scripts/ci-status.sh [branch]

set -uo pipefail

REPO="sayedtenkanen/auto-harnessessing"
BRANCH="${1:-main}"

# Fetch latest CI run for branch
RUN_JSON=$(curl -s "https://api.github.com/repos/${REPO}/actions/runs?branch=${BRANCH}&per_page=5" 2>/dev/null)

if [ -z "$RUN_JSON" ] || echo "$RUN_JSON" | python3 -c "import sys,json; sys.exit(0 if json.load(sys.stdin).get('workflow_runs') else 1)" 2>/dev/null; then
    # Find latest CI run
    RUN_INFO=$(echo "$RUN_JSON" | python3 -c "
import sys, json
d = json.load(sys.stdin)
for r in d['workflow_runs']:
    if r['name'] == 'CI':
        print(f'{r[\"id\"]}|{r[\"run_number\"]}|{r[\"conclusion\"]}|{r[\"head_sha\"][:7]}|{r[\"updated_at\"]}')
        break
")
fi

if [ -z "$RUN_INFO" ]; then
    echo "No CI runs found for branch: $BRANCH"
    exit 1
fi

IFS='|' read -r RUN_ID RUN_NUM CONCLUSION SHA _ <<< "$RUN_INFO"

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m'

case "$CONCLUSION" in
    success)   COLOR=$GREEN; ICON="✓" ;;
    failure)   COLOR=$RED;   ICON="✗" ;;
    pending)   COLOR=$YELLOW; ICON="●" ;;
    *)         COLOR=$NC;    ICON="?" ;;
esac

echo -e "CI #${RUN_NUM}: ${COLOR}${ICON} ${CONCLUSION}${NC} (sha: ${SHA})"

# Fetch job details if failed
if [ "$CONCLUSION" = "failure" ]; then
    JOBS_JSON=$(curl -s "https://api.github.com/repos/${REPO}/actions/runs/${RUN_ID}/jobs" 2>/dev/null)
    echo "$JOBS_JSON" | python3 -c "
import sys, json
d = json.load(sys.stdin)
for j in d['jobs']:
    status = j['conclusion'] or j['status']
    icon = '✓' if status == 'success' else '✗' if status == 'failure' else '●'
    print(f'  {icon} {j[\"name\"]}: {status}')
" 2>/dev/null
fi
