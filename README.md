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
- `POST /v1/jobs/{job_id}/execute`
- `GET /v1/jobs/{job_id}`
- `PATCH /v1/jobs/{job_id}/stage`
- `GET /v1/jobs/{job_id}/stage`
- `PATCH /v1/jobs/{job_id}/artifacts`
- `GET /v1/jobs/{job_id}/artifacts`
- `PATCH /v1/jobs/{job_id}/shots/{shot_id}/artifacts`
- `GET /v1/jobs/{job_id}/shots/{shot_id}/artifacts`

Use `POST /v1/jobs/{job_id}/execute` to run the current deterministic execution path end-to-end for a submitted job. Use the patch endpoints only when an operator or an external worker needs to mutate stage/artifact state explicitly. Use the GET endpoints to inspect the job after each step.

Run the smoke test with:

```bash
PYTHONPATH=src ./.venv/bin/pytest tests/integration/test_api_smoke.py -v
```

## Local Execution Slice
The repository now includes a deterministic local execution path that materializes runtime artifacts under `runtime/jobs/<job_id>/...`.

- `RuntimeWorkspace` owns runtime paths and asset refs.
- `DeterministicLocalRenderAdapter` emits placeholder shot frames and clip files.
- `DeterministicLocalTTSAdapter` emits valid wav files for narration and dialogue segments.
- `DeterministicLocalJobExecutionService` runs ingest, planning, render, timeline, audio mix, compose, technical review, and semantic review into a stitched output package.

Important limitation:
- The deterministic local render adapter is not a real scene generator. It exists to validate runtime/output contracts.
- Placeholder clips now carry explicit metadata and are expected to fail technical review with `placeholder_render_output`.
- A local stitched mp4 from this fallback path proves orchestration only, not final visual quality.

## Render Backend Replacement Slice
The repository now includes the first real-provider replacement surface for rendering:

- `RenderConfig.mode` makes render execution explicit: `deterministic_local` for contract validation and `routed_api` for real image/Wan backends.
- `RenderConfig.image_endpoint` and `RenderConfig.wan_endpoint` define the internal image and Wan API endpoints.
- `ApiRenderBackendAdapter` sends normalized render jobs to provider APIs.
- `RoutingRenderAdapter` dispatches `image` and `wan` jobs to different backends without changing workflow contracts.
- `av-image-renderer` and `av-wan-renderer` now exist as internal worker services in [docker-compose.yml](/workspaces/auto_video_gen/docker-compose.yml).
- `config/profiles/routed_api_local.yaml` is the operator switch that flips API execution from `deterministic_local` to `routed_api`.
- Layered config precedence is `defaults -> modules -> profiles -> env -> runtime`, so `routed_api_local` overrides the module default without hand-editing `config/modules/render.yaml`.
- The heuristic planner now recognizes both English and Chinese action cues when selecting `wan_dynamic` shots.
- The routed semantic review profile uses one-shot `llama-mtmd-cli` review with Qwen3-VL 32B Q4_K_M and samples multiple frames per shot instead of only the first frame.

Current limitation:
- The renderer services now ship placeholder-safe internal APIs and an opt-in `sd_cpp` image backend surface, but the default backend remains placeholder mode until local model binaries and the full `Z-Image` split-model assets are mounted.
- `av-wan-renderer` is still placeholder-only; the true `Wan2.2-TI2V-5B-GGUF` backend is still a follow-up slice.
- Placeholder renderer outputs remain intentionally non-deliverable and are expected to fail technical review.
- The first remote real-image smoke now works through `sd_cpp`, and the workflow now fail-closes on semantic review. A weak real frame no longer auto-completes just because technical QA passed.

Semantic review is also on-demand rather than resident:
- `review.semantic.mode=llama_cpp_cli` launches the reviewer as a one-shot subprocess and releases memory when the review exits.
- The current shared-host default is `Qwen3-VL-32B-Instruct-Q4_K_M` with `mmproj Q8_0`.
- Keep `config/profiles/routed_api_local_shared_8b.yaml` as the lighter fallback profile when an operator wants a cheaper triage window.

To start the internal render services with the default lightweight placeholder backends:

```bash
docker compose up -d av-image-renderer av-wan-renderer
```

To switch the API onto routed render services:

```bash
AV_WORKFLOW_CONFIG_PROFILE=routed_api_local docker compose up -d av-api
```

To prepare the first local real image backend surface, populate the operator env vars in `.env`:

```bash
AV_WORKFLOW_IMAGE_BACKEND_KIND=sd_cpp
AV_WORKFLOW_MODELS_ROOT=./models
AV_WORKFLOW_SD_CPP_BIN=/models/bin/sd-cli
AV_WORKFLOW_Z_IMAGE_DIFFUSION_MODEL_PATH=/models/z-image/Z-Image-Turbo-Q2_K.gguf
AV_WORKFLOW_Z_IMAGE_VAE_PATH=/models/z-image/ae.safetensors
AV_WORKFLOW_Z_IMAGE_LLM_PATH=/models/qwen3/Qwen3-4B-Instruct-2507-Q4_K_M.gguf
```

Those values wire `av-image-renderer` to the official split `stable-diffusion.cpp` `Z-Image` surface: diffusion model, VAE, and LLM are configured independently, which avoids a false “configured but not runnable” state in routed mode.

To provision those assets automatically inside the module without writing ad hoc host commands:

```bash
DRY_RUN=0 ./scripts/provision_z_image_backend.sh
docker compose up -d --build av-image-renderer
```

`scripts/provision_z_image_backend.sh` does the following:
- ensures the host-side `models/` tree is writable, even if a previous container created it as `root:root`
- downloads the Linux `stable-diffusion.cpp` release binary from GitHub Releases
- downloads the default `Z-Image-Turbo Q2_K`, mirrored `ae.safetensors`, and `Qwen3-4B-Instruct-2507-Q4_K_M.gguf` assets from `hf-mirror.com`
- updates `.env` to point `av-image-renderer` at the provisioned paths

The script defaults to `DRY_RUN=1`. Set `FORCE_DOWNLOAD=1` to redownload assets, `UPDATE_ENV=0` to skip `.env` mutation, or override the asset URLs through environment variables if the operator wants a different quantization or mirror.

The current runtime bootstrap now builds a job-scoped execution service from layered config:
- `AV_WORKFLOW_CONFIG_ROOT` selects the config tree.
- `AV_WORKFLOW_RUNTIME_ROOT` selects the runtime artifact root.
- `AV_WORKFLOW_CONFIG_MODULES` selects which module layers to merge.

Remote evidence from the first real-image CPU smoke on `2026-04-04`:
- three-shot calm excerpt completed end to end on the remote host
- each shot produced a real `frame-001.png` and `clip.mp4`
- final output was `640x384`, `24 fps`, `9.0s`, with `h264` video and `aac` mono audio
- static excerpt routing stayed image-only, with three successful `POST /v1/render/image` and no `POST /v1/render/video`

The fastest regression entry points are:

```bash
PYTHONPATH=src ./.venv/bin/pytest tests/integration/test_execute_job_api.py -v
PYTHONPATH=src ./.venv/bin/pytest tests/unit/test_job_execution_service.py -v
PYTHONPATH=src ./.venv/bin/pytest tests/unit tests/integration -q
```

The current development container does not expose `docker` and does not ship host-level `ffmpeg`, so true media execution must happen either through the packaged API image or on the remote `infra-core` host. The local test suite validates the execution contract with deterministic media emitters and a fake ffmpeg executor.

## Packaging Helpers
- `scripts/doctor.sh`: validates Python compilation and `docker compose` syntax
- `scripts/deploy.sh`: validates the compose file and performs `docker compose up -d` when `DRY_RUN=0`
- `scripts/install_remote_module.sh`: syncs the repository root to the remote `infra-core` module path and registers `av-workflow` in `modules/registry.list`
- `scripts/provision_z_image_backend.sh`: provisions the first real local image backend assets and normalizes `.env` for `sd_cpp`

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

If remote image rebuilds are dominated by Debian package downloads, set an APT mirror in the module `.env` before rebuilding:

```bash
AV_WORKFLOW_APT_MIRROR=http://mirrors.ustc.edu.cn
```

The Docker build rewrites `deb.debian.org` and `security.debian.org` to that mirror before `apt-get update`, so the same setting will accelerate future `av-api`, `av-image-renderer`, and `av-wan-renderer` images.

If the operator wants the API service to switch from placeholder local rendering to real backend routing after `av-image-renderer` and `av-wan-renderer` are deployed, update the layered render config:

```yaml
render:
  mode: routed_api
```

The repository now also ships [config/profiles/routed_api_local.yaml](/workspaces/auto_video_gen/config/profiles/routed_api_local.yaml), so operators can prefer a profile switch over hand-editing module YAML.
Because the loader applies profiles after module defaults, `AV_WORKFLOW_CONFIG_PROFILE=routed_api_local` is sufficient to override `render.mode` on the API service.
That same profile keeps semantic review on-demand, so no resident reviewer process needs to sit in memory between jobs.
