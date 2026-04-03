# Issue Solution Log

Use this file to record recurring failures, root cause evidence, fixes, and regression checks.

## 2026-04-03

### YAML test fixture parsing failed in configuration-loader tests
- Symptom: `tests/unit/test_config_loader.py` failed with `yaml.parser.ParserError` while loading `defaults/system.yaml`.
- Root cause: test fixtures wrote triple-quoted YAML with preserved Python indentation, so the stored YAML structure was invalid before the loader logic ran.
- Fix: normalize fixture content with `textwrap.dedent(...).strip() + "\n"` inside the shared `write_yaml` helper.
- Regression check: run `PYTHONPATH=src ./.venv/bin/pytest tests/unit/test_config_loader.py -v` and confirm all config-loader tests pass.

### Preface text could be dropped before the first detected chapter heading
- Symptom: normalized source parsing kept only heading-bound chapter bodies and discarded leading prose before the first `Chapter` heading.
- Root cause: the chapter splitter started accumulating content only after the first heading match and ignored pre-heading lines.
- Fix: preserve leading prose and merge it into the first detected chapter body during deterministic chapter splitting.
- Regression check: run `PYTHONPATH=src ./.venv/bin/pytest tests/unit/test_ingest_service.py -v` and confirm the preface-preservation test passes.

### Agent proposal mutation filter could be bypassed through list-wrapped payloads
- Symptom: the agent gateway rejected direct `{ "status": "completed" }` payloads but accepted the same forbidden key when it was nested inside a list of operations.
- Root cause: `contains_forbidden_mutation` only recursed into nested dictionaries and skipped dictionaries stored inside lists.
- Fix: normalize the recursive scan to walk both dictionaries and lists before deciding whether a proposal attempts forbidden state mutation.
- Regression check: run `PYTHONPATH=src ./.venv/bin/pytest tests/unit/test_agent_gateway.py -v` and confirm the nested-list mutation test passes.

### Remote module packaging validation drifted from the real install contract
- Symptom: `tests/unit/test_module_packaging.py` failed even though `scripts/install_remote_module.sh` correctly derived its module path from `REMOTE_ROOT`, and direct dry-run execution initially failed with `Permission denied`.
- Root cause: the test asserted a fully expanded hard-coded path literal instead of the layered `REMOTE_ROOT` plus `REMOTE_MODULE_PATH` contract, and the new script was added without the executable bit required for direct invocation.
- Fix: tighten the packaging regression test around the real config semantics, add an executable-bit assertion for `scripts/install_remote_module.sh`, and keep the script mode aligned with other operator entry points in `scripts/`.
- Regression check: run `PYTHONPATH=src ./.venv/bin/pytest tests/unit/test_module_packaging.py -v` and `DRY_RUN=1 ./scripts/install_remote_module.sh`.

### API port overrides could silently desynchronize startup and health checks
- Symptom: `docker-compose.yml` exposed and labeled `AV_WORKFLOW_API_PORT`, but the image command and healthcheck still hard-coded port `8080`, so changing the configured port would leave the service unhealthy or unreachable behind the gateway.
- Root cause: runtime packaging split the bind-port configuration across compose metadata and container entry logic instead of resolving both from the same layered environment contract.
- Fix: make the image entrypoint resolve `AV_WORKFLOW_API_HOST` and `AV_WORKFLOW_API_PORT` at runtime, and make the compose healthcheck probe the same environment-driven port.
- Regression check: run `PYTHONPATH=src ./.venv/bin/pytest tests/unit/test_module_packaging.py -v` and confirm the packaging tests assert the layered host/port contract.

### Remote build could stall while pulling an uncached Python base image
- Symptom: the first real `modulectl.sh up av-workflow` attempt hung during `docker compose up -d`, `av-workflow-api` never appeared in `docker images`, and a direct `timeout 30 docker pull python:3.11-slim` exited with `rc=124`.
- Root cause: the module image hard-coded `python:3.11-slim`, while the target host only had `python:3.12-slim` cached and the configured registry mirror path could not complete the `3.11` pull in time.
- Fix: externalize the Python base image as a build argument, default it to `python:3.12-slim`, and expose the override through `.env.example` so operators can switch to a cached or mirrored base without editing the Dockerfile.
- Regression check: run `PYTHONPATH=src ./.venv/bin/pytest tests/unit/test_module_packaging.py -v` and confirm the packaging tests assert the layered Python base image contract.
