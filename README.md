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
The current internal API is intentionally minimal, schema-validated, and operator-facing:
- `GET /health`
- `POST /v1/jobs`
- `GET /v1/jobs/{job_id}`
- `PATCH /v1/jobs/{job_id}/stage`
- `GET /v1/jobs/{job_id}/stage`
- `PATCH /v1/jobs/{job_id}/artifacts`
- `GET /v1/jobs/{job_id}/artifacts`
- `PATCH /v1/jobs/{job_id}/shots/{shot_id}/artifacts`
- `GET /v1/jobs/{job_id}/shots/{shot_id}/artifacts`

Use the patch endpoints to advance stage state and record generated media refs; use the GET endpoints to inspect the job after each step.

Run the smoke test with:

```bash
PYTHONPATH=src ./.venv/bin/pytest tests/integration/test_api_smoke.py -v
```

## Local Execution Slice
The repository now includes a deterministic local execution path that materializes runtime artifacts under `runtime/jobs/<job_id>/...`.

- `RuntimeWorkspace` owns runtime paths and asset refs.
- `DeterministicLocalRenderAdapter` emits placeholder shot frames and clip files.
- `DeterministicLocalTTSAdapter` emits valid wav files for narration and dialogue segments.
- `DeterministicLocalJobExecutionService` runs ingest, planning, render, timeline, audio mix, and compose into a stitched output package.

Important limitation:
- The deterministic local render adapter is not a real scene generator. It exists to validate runtime/output contracts.
- Placeholder clips now carry explicit metadata and are expected to fail technical review with `placeholder_render_output`.
- A local stitched mp4 from this fallback path proves orchestration only, not final visual quality.

## Render Backend Replacement Slice
The repository now includes the first real-provider replacement surface for rendering:

- `RenderConfig.image_endpoint` and `RenderConfig.wan_endpoint` define the internal image and Wan API endpoints.
- `ApiRenderBackendAdapter` sends normalized render jobs to provider APIs.
- `RoutingRenderAdapter` dispatches `image` and `wan` jobs to different backends without changing workflow contracts.

Current limitation:
- These adapters prepare the real integration surface, but the repository still does not ship a local image-model container or a local Wan-model container.
- Until those services are deployed and wired into runtime bootstrap, deterministic placeholder rendering remains the only built-in execution fallback.

The fastest regression entry points are:

```bash
PYTHONPATH=src ./.venv/bin/pytest tests/unit/test_job_execution_service.py -v
PYTHONPATH=src ./.venv/bin/pytest tests/unit tests/integration -q
```

The current development container does not expose `docker` and does not ship host-level `ffmpeg`, so true media execution must happen either through the packaged API image or on the remote `infra-core` host. The local test suite validates the execution contract with deterministic media emitters and a fake ffmpeg executor.

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

The service is currently attached to the internal Docker and Traefik networks with `expose`, not host-level `ports`. Validate runtime health through the ingress host or with:

```bash
docker exec av-workflow-av-api-1 python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=3).read().decode())"
```

If the target host needs a different cached or mirrored Python base image, override:

```bash
AV_WORKFLOW_PYTHON_BASE_IMAGE=python:3.12-slim
```
