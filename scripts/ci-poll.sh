#!/usr/bin/env bash
# CI polling function — source this in your shell rc (.zshrc/.bashrc)
# Usage: gpush [args]    (replaces git push)
#
# Pushes, then polls GitHub Actions until CI completes.

gpush() {
    # Push (pass all args through)
    git push "$@" || return 1

    local REPO="sayedtenkanen/auto-harnessessing"
    local BRANCH
    BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "main")

    # Wait for CI to start
    sleep 3

    # Poll for completion (max 5 minutes)
    local MAX_WAIT=300
    local ELAPSED=0
    local INTERVAL=5

    echo "⏳ Waiting for CI on ${BRANCH}..."

    while [ $ELAPSED -lt $MAX_WAIT ]; do
        local RUN_INFO
        RUN_INFO=$(curl -s "https://api.github.com/repos/${REPO}/actions/runs?branch=${BRANCH}&per_page=1" 2>/dev/null)

        local STATUS
        STATUS=$(echo "$RUN_INFO" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    for r in d['workflow_runs']:
        if r['name'] == 'CI':
            print(r['conclusion'] or 'in_progress')
            break
    else:
        print('not_found')
except:
    print('error')
" 2>/dev/null)

        case "$STATUS" in
            success)
                echo "✅ CI passed"
                return 0
                ;;
            failure)
                echo "❌ CI failed"
                # Show which jobs failed
                local RUN_ID
                RUN_ID=$(echo "$RUN_INFO" | python3 -c "
import sys, json
d = json.load(sys.stdin)
for r in d['workflow_runs']:
    if r['name'] == 'CI':
        print(r['id'])
        break
" 2>/dev/null)

                if [ -n "$RUN_ID" ]; then
                    curl -s "https://api.github.com/repos/${REPO}/actions/runs/${RUN_ID}/jobs" 2>/dev/null | python3 -c "
import sys, json
d = json.load(sys.stdin)
for j in d['jobs']:
    status = j['conclusion'] or j['status']
    icon = '✓' if status == 'success' else '✗' if status == 'failure' else '●'
    print(f'  {icon} {j[\"name\"]}: {status}')
" 2>/dev/null
                fi
                return 1
                ;;
            in_progress|queued|waiting)
                printf "\r  ⏳ %ds elapsed..." $ELAPSED
                ;;
            *)
                printf "\r  ⏳ %ds (waiting for CI to start)..." $ELAPSED
                ;;
        esac

        sleep $INTERVAL
        ELAPSED=$((ELAPSED + INTERVAL))
    done

    echo ""
    echo "⏰ Timed out after ${MAX_WAIT}s — check manually: https://github.com/${REPO}/actions"
    return 1
}
