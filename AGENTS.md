# AutoHarness

Probabilistic program compiler that searches over a unified intermediate representation (UPIR), executes it in sandboxed environments, and compiles successful behaviors into reusable executable subprograms.

## Quick reference

- **Plan:** `PLAN.md` (full spec, 1100+ lines)
- **Blueprint:** `BLUEPRINT.md` (original v4 reference)
- **Python:** 3.12+
- **LLM:** Ollama local (`gemma4:12b-mlx`) at `http://localhost:11434/v1`

## Commands

```bash
# Install dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/

# Run tests for a specific slice
pytest tests/ir/           # Slice 1 IR types
pytest tests/runtime/      # Slice 1 VM
pytest tests/sandbox/      # Slice 2
pytest tests/trace/        # Slice 3
pytest tests/reward/       # Slice 4
pytest tests/search/       # Slice 5
pytest tests/intelligence/ # Slice 6+

# Lint
ruff check src/ tests/

# Format
ruff format src/ tests/

# Type check
mypy src/

# Violation tracking — run all checks, output JSON
bash scripts/check-violations.sh

# Violation tracking — update violations.json with results
bash scripts/update-violations.sh

# Coverage
pytest --cov=tracedge --cov-report=term-missing

# Security — full scan
bash scripts/security-scan.sh

# Security — secrets detection
gitleaks detect --source .

# Security — Python static analysis
bandit -r src/tracedge -c pyproject.toml

# Security — dependency vulnerabilities
safety check

# CI status
bash scripts/ci-status.sh

# Push with CI polling (replaces git push)
source scripts/ci-poll.sh
gpush
```

## TDD workflow

1. **Red:** Write a failing test
2. **Green:** Write minimum code to pass
3. **Refactor:** Clean up while green

Two commits per cycle:
```
test(scope): add failing tests for X
feat(scope): implement X to pass tests
```

## Project structure

```
src/tracedge/
├── ir/           # UPIR + Harness IR types (Slice 1)
├── runtime/      # VM execution engine (Slice 1)
├── environment/  # Pluggable env protocol (Slice 1)
├── sandbox/      # Safety + isolation (Slice 2)
├── trace/        # Trace IR system (Slice 3)
├── reward/       # Reward engine (Slice 4)
├── search/       # Thompson tree search (Slice 5)
├── intelligence/ # LLM integration (Slice 6)
├── skills/       # Skill system (Slice 7-9)
├── memory/       # Persistence (Slice 10)
└── compiler/     # Compiler passes (Slice 12-15)
```

## Current status

- [x] Plan complete (PLAN.md)
- [x] Slice 1: UPIR VM + Environment Protocol
- [x] Slice 2: Sandbox + Safety
- [x] Slice 3: Trace IR
- [x] Slice 4: Reward Engine
- [x] Slice 5: Thompson Tree Search
- [x] Slice 6: Refiner + Critic Loop
- [x] Slice 7: Skill Extraction
- [x] Slice 8-10: Skill Execution, Pruning, Memory
- [ ] Slice 11-16: Compiler layer

## CI/CD

GitHub Actions runs on every push to `main`:
- **lint** — `ruff check`, `ruff format --check`, `mypy src/`
- **test** — `pytest` with coverage
- **security** — `gitleaks`, `shellcheck`, `bandit[toml]`, `safety`

Workflow: `.github/workflows/ci.yml`

## Branching

Branch per slice. Never merge directly to main.

**Workflow:**
1. Create a feature branch: `git checkout -b slice/N-name`
2. Implement with TDD (red → green → refactor)
3. Push the branch: `git push origin slice/N-name`
4. Create a PR on GitHub — CI must pass (lint, test, security)
5. Merge via GitHub after checks pass

```
git checkout -b slice/3-trace-ir
# ... TDD cycle ...
pytest tests/  # all green
git push origin slice/3-trace-ir
# → open PR on GitHub → CI runs → merge after green
```

**Ground rule:** Direct pushes to `main` are prohibited. All changes go through a PR with passing CI.

## Conventions

- **Test naming:** `test_<thing>_<scenario>`
- **Lint:** ruff (line-length 100)
- **Types:** mypy strict mode
- **Pre-commit:** ruff + mypy + gitleaks + bandit hooks enabled

## Security

**gitleaks version: 8.18.4** — both CI (`.github/workflows/ci.yml`) and local (`~/bin/gitleaks`) must match. Update both when upgrading.

Pre-commit hooks run automatically on every commit:
- **gitleaks** — detects secrets, API keys, tokens in code
- **bandit** — Python static security analysis (finds common vulnerabilities)

Run full security scan manually:
```bash
bash scripts/security-scan.sh
```

**Security rules:**
- Never commit API keys, tokens, or passwords
- All harness code runs sandboxed (no network, no filesystem outside workspace)
- Harness code cannot use try/except (must surface errors explicitly)
- All tool calls have timeouts (10s default)
- Path traversal blocked via `os.path.realpath()` check
