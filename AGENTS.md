# Repository Guidelines

## Project Structure & Module Organization
This repository is git-managed and intended for an automated novel-to-video platform. Keep implementation code under `src/`, tests under `tests/`, operator scripts under `scripts/`, reusable assets under `assets/`, and long-lived documentation under `docs/`. Use `runtime/` only for generated media, caches, logs, and local state; it should remain untracked.

## Build, Test, and Development Commands
Standardize all local workflows behind stable entry points.
- `make fmt`: format source files
- `make lint`: run static checks
- `make test`: run the default unit and contract suite
- `make test-integration`: run workflow or media-pipeline integration tests
- `python -m src.<module>`: direct module debugging only
If `make` is not present yet, keep equivalent commands documented in `README.md` and avoid ad-hoc one-off command drift. Shell entry points under `scripts/` are expected to remain directly executable; validate new operator scripts with at least `bash -n <script>` and one documented dry-run path.

## Coding Style & Naming Conventions
Use 4-space indentation. Prefer Python with typed interfaces and schema-validated payloads. Use `snake_case` for modules, functions, variables, and file names; use `PascalCase` for data models and DTO-style classes; use `kebab-case` for scripts and design document file names. Favor deterministic modules, structured logs, and small explicit adapters over hidden global state.

## Testing Guidelines
Default to test-driven changes when practical. Keep unit tests in `tests/unit/` and workflow, contract, or media-pipeline tests in `tests/integration/`. Name files `test_<feature>.py` and name test cases after behavior, for example `test_retries_failed_review_case`. Cover schema validation, state transitions, retry behavior, and quality-gate decisions.

## Commit & Pull Request Guidelines
Use Conventional Commits such as `feat: add review contract schema` or `docs: define workflow state model`. Each pull request should state the goal, affected paths, validation performed, and residual risks. For workflow, media, or UI changes, attach evidence such as logs, screenshots, sample manifests, or output snippets.

## Security & Configuration
Do not commit secrets, tokens, or host-specific paths. Keep documented variables in `.env.example` and store machine-local overrides outside version control. Treat external model credentials, API keys, and review endpoints as runtime configuration only.

## Documentation & AGENTS Maintenance
Keep stable repository rules in `AGENTS.md`, operator guidance in `README.md`, architecture rationale in `docs/decision-log.md`, recurring failure evidence in `docs/issue_solution_log.md`, formal requirements in `docs/requirements/`, and approved designs in `docs/design/`. Update `AGENTS.md` only for rules that should survive future sessions; do not store one-off incidents, temporary ports, or single-run workarounds here.
