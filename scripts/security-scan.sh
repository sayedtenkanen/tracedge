#!/usr/bin/env bash
# Security scan script for Tracedge
# Usage: bash scripts/security-scan.sh [--verbose] [--quiet]
#
# Checks:
#   1. ShellCheck (self-lint)
#   2. Gitleaks (secrets detection)
#   3. Bandit (Python security analysis)
#   4. Safety (dependency vulnerabilities)
#   5. pip-audit (dependency vulnerabilities — alternative)
#   6. Hardcoded path check
#
# Severity policy:
#   - Gitleaks/Bandit: hard-fail on any finding. A secret in the repo or a
#     security vulnerability in application code is always unacceptable.
#   - Safety/pip-audit: warn-only. Third-party dependency advisories may be
#     false positives, unfixable upstream, or low-risk — we flag them for
#     human review rather than blocking CI.
#   - Hardcoded paths: warn-only. These are code-quality smells, not security
#     threats, and may exist legitimately in tests or documentation.

set -uo pipefail

# --- Configuration -----------------------------------------------------------

SOURCE_DIR="${SOURCE_DIR:-src/tracedge}"

# --- Argument parsing --------------------------------------------------------

VERBOSE=false
QUIET=false

for arg in "$@"; do
    case "$arg" in
        --verbose) VERBOSE=true ;;
        --quiet)   QUIET=true ;;
        --help|-h)
            echo "Usage: $0 [--verbose] [--quiet]"
            echo ""
            echo "Environment variables:"
            echo "  SOURCE_DIR  Source directory to scan (default: src/tracedge)"
            exit 0
            ;;
    esac
done

# --- Helpers -----------------------------------------------------------------

have() {
    command -v "$1" >/dev/null 2>&1
}

log() {
    $QUIET || echo "$@"
}

banner() {
    $QUIET || echo "=== $1 ==="
}

# --- Git root ----------------------------------------------------------------

if have git; then
    GIT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || {
        echo "ERROR: Not inside a Git repository."
        exit 1
    }
    cd "$GIT_ROOT" || exit
else
    echo "WARNING: git not found, running from current directory."
fi

# --- Main --------------------------------------------------------------------

banner "Tracedge Security Scan"
echo ""

PASSED=0
WARNED=0
SKIPPED=0
FAILED=0
start=$(date +%s)

# --- 1. ShellCheck (self-lint) ----------------------------------------------

log "[1/6] ShellCheck (script linting)..."
if have shellcheck; then
    if shellcheck "$0" 2>&1; then
        log "PASS: no shell issues"
        ((PASSED++))
    else
        echo "WARN: shellcheck found issues in $0"
        ((WARNED++))
    fi
else
    log "SKIP: shellcheck not installed"
    ((SKIPPED++))
fi
log ""

# --- 2. Gitleaks (secrets detection) -----------------------------------------

log "[2/6] Gitleaks (secrets detection)..."
if have gitleaks; then
    _g_exit=0
    if $VERBOSE; then
        (gitleaks detect --source . --verbose 2>&1) || _g_exit=$?
    else
        (gitleaks detect --source . 2>&1) || _g_exit=$?
    fi
    if [ "$_g_exit" -eq 0 ]; then
        log "PASS: no secrets found"
        ((PASSED++))
    else
        echo "FAIL: gitleaks detected secrets"
        ((FAILED++))
    fi
else
    log "SKIP: gitleaks not installed"
    ((SKIPPED++))
fi
log ""

# --- 3. Bandit (Python security analysis) ------------------------------------

log "[3/6] Bandit (Python security analysis)..."
if have bandit; then
    _b_exit=0
    if python3 -c "import toml" 2>/dev/null; then
        (bandit -r "$SOURCE_DIR" -c pyproject.toml 2>&1) || _b_exit=$?
    else
        echo "WARN: toml package not installed; bandit config (pyproject.toml) may be silently ignored"
        (bandit -r "$SOURCE_DIR" 2>&1) || _b_exit=$?
    fi
    if [ "$_b_exit" -eq 0 ]; then
        log "PASS: no security issues"
        ((PASSED++))
    else
        echo "FAIL: bandit found issues"
        ((FAILED++))
    fi
else
    log "SKIP: bandit not installed"
    ((SKIPPED++))
fi
log ""

# --- 4. Safety (dependency vulnerabilities) ----------------------------------
# Safety exit codes:
#   0 = clean scan (no vulnerabilities)
#   1 = vulnerabilities found
#   Non-zero (other) = auth errors, network failures, invalid API key, etc.
# We distinguish "clean" from "broken" by capturing stderr separately.

log "[4/6] Safety (dependency vulnerabilities)..."
SAFETY_CMD=""
if have safety; then
    SAFETY_CMD="safety"
elif python3 -m safety --version >/dev/null 2>&1; then
    SAFETY_CMD="python3 -m safety"
fi

if [ -n "$SAFETY_CMD" ]; then
    SAFETY_STDERR=$(mktemp)
    SAFETY_STDOUT=$(mktemp)
    SAFETY_EXIT=0
    $SAFETY_CMD check --output text 2>"$SAFETY_STDERR" | tee "$SAFETY_STDOUT" || SAFETY_EXIT=$?

    # Determine outcome: exit 0 = clean, exit 1 = vulnerabilities, else = broken
    # Safety's deprecated `check` may exit non-1 on errors; also check output
    # for "VULNERABILITIES FOUND" to catch cases where exit code is unreliable.
    if [ "$SAFETY_EXIT" -eq 0 ]; then
        log "PASS: no known vulnerabilities"
        ((PASSED++))
    elif [ "$SAFETY_EXIT" -eq 1 ] || grep -q "VULNERABILITIES FOUND" "$SAFETY_STDOUT" 2>/dev/null; then
        echo "WARN: safety found vulnerabilities (check output above)"
        ((WARNED++))
    else
        echo "WARN: safety check failed (exit $SAFETY_EXIT — auth error, network issue, or deprecated command)"
        if [ -s "$SAFETY_STDERR" ]; then
            echo "  stderr: $(tail -1 "$SAFETY_STDERR")"
        fi
        ((WARNED++))
    fi
    rm -f "$SAFETY_STDERR" "$SAFETY_STDOUT"
else
    log "SKIP: safety not installed"
    ((SKIPPED++))
fi
log ""

# --- 5. pip-audit (dependency vulnerabilities — alternative) -------------------

log "[5/6] pip-audit (dependency vulnerabilities)..."
if have pip-audit; then
    _pa_exit=0
    (pip-audit 2>&1) || _pa_exit=$?
    if [ "$_pa_exit" -eq 0 ]; then
        log "PASS: no known vulnerabilities"
        ((PASSED++))
    else
        echo "WARN: pip-audit found vulnerabilities (check output above)"
        ((WARNED++))
    fi
else
    log "SKIP: pip-audit not installed"
    ((SKIPPED++))
fi
log ""

# --- 6. Hardcoded path check -------------------------------------------------

log "[6/6] Hardcoded path check..."
if [ -d "src" ]; then
    HARDCODED=$(grep -REn \
        --exclude-dir=__pycache__ \
        --exclude-dir=.venv \
        --exclude-dir=.mypy_cache \
        --exclude-dir=.pytest_cache \
        --exclude-dir=node_modules \
        --exclude-dir=tests \
        --exclude-dir=test \
        --exclude-dir=fixtures \
        --exclude-dir=mocks \
        --exclude-dir=mock \
        --exclude-dir=conftest \
        --exclude='*.pyc' \
        '(/Users/|/home/|/root/|/opt/|/var/|/etc/|C:\\)' \
        src/ 2>/dev/null || true)

    if [ -n "$HARDCODED" ]; then
        echo "FAIL: hardcoded paths found:"
        echo "$HARDCODED"
        ((FAILED++))
    else
        log "PASS: no hardcoded paths"
        ((PASSED++))
    fi
else
    log "SKIP: src/ directory not found"
    ((SKIPPED++))
fi
log ""

# --- Summary -----------------------------------------------------------------

elapsed=$(( $(date +%s) - start ))

banner "Summary"
echo "  Passed:  $PASSED"
echo "  Warned:  $WARNED"
echo "  Skipped: $SKIPPED"
echo "  Failed:  $FAILED"
echo "  Time:    ${elapsed}s"
echo ""

if (( FAILED > 0 )); then
    echo "Security scan FAILED ($FAILED issue(s))."
    exit 1
fi

if (( WARNED > 0 )); then
    echo "Security scan passed with $WARNED warning(s)."
    exit 0
fi

echo "All security checks passed."
exit 0
