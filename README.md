# auto_video_gen

This repository hosts the design, implementation, and operations artifacts for an internal single-tenant automated novel-to-video workflow.

## Repository Layout
- `src/`: application and worker code
- `tests/`: unit and integration coverage
- `docs/`: requirements, designs, plans, and operations evidence
- `scripts/`: operator and developer helper scripts
- `assets/`: reusable static assets and fixtures
- `runtime/`: ignored local outputs, caches, and generated media

## Development Baseline
The project is expected to stay git-managed, test-driven, and document-first. Stable contributor rules live in `AGENTS.md`. Architecture decisions and recurring issue evidence belong in `docs/`.

## Local Bootstrap
Create an isolated virtual environment before running local checks:

```bash
python3 -m venv .venv
./.venv/bin/pip install -e .[dev]
PYTHONPATH=src ./.venv/bin/pytest tests/unit -v
```

Use `.venv` for local development unless a CI container provides an equivalent interpreter and dependency set.

## API Smoke Flow
The current internal API is intentionally minimal and stub-backed:
- `GET /health`
- `POST /v1/jobs`
- `GET /v1/jobs/{job_id}`
- `GET /v1/jobs/{job_id}/artifacts`

Run the smoke test with:

```bash
PYTHONPATH=src ./.venv/bin/pytest tests/integration/test_api_smoke.py -v
```

## Packaging Helpers
- `scripts/doctor.sh`: validates Python compilation and `docker compose` syntax
- `scripts/deploy.sh`: validates the compose file and performs `docker compose up -d` when `DRY_RUN=0`
- `scripts/install_remote_module.sh`: syncs the repository root to the remote `infra-core` module path and registers `av-workflow` in `modules/registry.list`

For development containers without Docker, use:

```bash
SKIP_DOCKER_CHECK=1 ./scripts/doctor.sh
SKIP_DOCKER_CHECK=1 DRY_RUN=1 ./scripts/deploy.sh
```

## Remote Module Shape
This repository root is intended to become the remote module directory content at:

```text
/mnt/hdo/infra-core/modules/av-workflow
```

Registry line:

```text
av-workflow|/mnt/hdo/infra-core/modules/av-workflow|docker-compose.yml|Internal single-tenant automated novel-to-video workflow
```

Default remote sync stays in dry-run mode:

```bash
DRY_RUN=1 ./scripts/install_remote_module.sh
```

Apply mode requires explicit credentials in the shell environment:

```bash
REMOTE_PASSWORD=*** DRY_RUN=0 ./scripts/install_remote_module.sh
```

The compose stack in [docker-compose.yml](/workspaces/auto_video_gen/docker-compose.yml) now doubles as the local development baseline and the future `infra-core` module compose file.

If the target host needs a different cached or mirrored Python base image, override:

```bash
AV_WORKFLOW_PYTHON_BASE_IMAGE=python:3.12-slim
```
