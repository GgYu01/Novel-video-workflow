# Progress Log

## 2026-04-03

### New Phase Start
- Starting the next slice after finishing control-plane, docs, push, remote sync, and remote container startup.
- Re-read skill guidance for brainstorming, planning-with-files, TDD, and parallel-agent usage.
- Confirmed the repo is clean except for user-owned `xiaoshuo.txt`.

### Current Focus
- Inspect the existing compose/adapters/runtime layer and propose the next implementation slice before changing code.

### Exploration Result
- `compose.py` currently produces `AssetManifest`, `OutputPackage`, and `build_ffmpeg_compose_plan`, but does not execute `ffmpeg`.
- `adapters/render.py` and `adapters/tts.py` define normalized contracts only; they do not yet provide file-producing local adapter implementations.
- The most coherent next slice is to add execution adapters and a deterministic local job-run service rather than expanding API surface again.
- Verified environment constraint: `ffmpeg` is absent both locally and on the remote host, so runtime packaging must bring it in via the container image instead of assuming host binaries.

### Implementation Result
- Added deterministic local runtime components:
  - `RuntimeWorkspace`
  - `DeterministicLocalRenderAdapter`
  - `DeterministicLocalTTSAdapter`
  - `SubprocessFfmpegExecutor`
  - `DeterministicLocalJobExecutionService`
- The execution service now materializes:
  - shot clips and frame files
  - per-segment wav files
  - runtime subtitle files
  - `audio/final-mix.wav`
  - concat manifest and stitched `output/final.mp4`
  - persisted runtime JSON artifacts for source, planning, compose, review, and output package
- Fixed a real runtime bug before completion:
  - root cause: audio mix duration could be shorter than stitched shot duration, and `ffmpeg -shortest` would truncate the final video
  - resolution: `materialize_audio_mix(...)` now pads silence to the target video duration, and job execution sets mix duration from total shot duration

### Verification Result
- `PYTHONPATH=src ./.venv/bin/pytest tests/unit -q` → passed (`82 passed`)
- `PYTHONPATH=src ./.venv/bin/pytest tests/integration -q` → passed (`2 passed`)
- `./.venv/bin/python -m compileall src tests` → passed
- Local real-media execution remains blocked in this development container because `docker` is unavailable and host-level `ffmpeg` is absent.

### Root Cause Debug
- Confirmed the user-visible green/yellow/pink output is not a stitching defect.
- The root cause is the deterministic placeholder renderer in `src/av_workflow/adapters/render.py`, which writes one solid-color PPM frame per shot and loops it into `clip.mp4`.
- Remote frame sampling confirmed that each shot frame is fully uniform color.
- Added a technical-review guard for placeholder render metadata and wired job execution/stage runner to stop automatic completion when review fails.

### Latest Verification
- `PYTHONPATH=src ./.venv/bin/pytest tests/unit/test_technical_review.py tests/unit/test_stage_runner.py tests/unit/test_job_execution_service.py tests/unit/test_compose_service.py tests/unit/test_local_provider_adapters.py -q` → passed (`13 passed`)
- `PYTHONPATH=src ./.venv/bin/pytest tests/integration/test_hybrid_job_flow.py -q` → passed (`1 passed`)
- `PYTHONPATH=src ./.venv/bin/pytest -q` → passed (`86 passed`)

### Pending Follow-Up
- The repository no longer allows deterministic placeholder outputs to pass as completed jobs.
- The next unfinished engineering slice is still real provider replacement:
  - image model adapter for the default shot path
  - selective local video adapter for dynamic shots
  - frame-level semantic review fed from actual generated frames rather than placeholder metadata
  - provider payload normalization hardening for sparse or null metadata from real backends

## 2026-04-04 Real Provider Replacement Start

### Implementation Result
- Added nested render endpoint config for the default image path and the selective Wan path.
- Added `ApiRenderBackendAdapter` to send normalized render jobs to provider APIs.
- Added `RoutingRenderAdapter` so image and Wan requests can be dispatched to different backends without changing `DeterministicRenderJobService`.
- Hardened render-result normalization and asset-manifest construction against providers that omit or null out metadata fields.

### Verification Result
- `PYTHONPATH=src ./.venv/bin/pytest tests/unit/test_config_loader.py tests/unit/test_render_adapter.py -q` → passed (`8 passed`)

### Current Slice: Runtime Bootstrap And Execute API
- Added `render.mode` to make placeholder local rendering and routed real-provider rendering mutually explicit.
- Added `HeuristicChapterShotPlanner` so the runtime can build default shot plans without injecting a test-only planner.
- Added `av_workflow.runtime.bootstrap` to build a job-scoped execution service from layered config, runtime root, and a job-specific TTS adapter.
- Added `POST /v1/jobs/{job_id}/execute` so the API can run the deterministic workflow and persist stage/artifact summaries through the same control-plane store.

### Verification Result
- `PYTHONPATH=src ./.venv/bin/pytest tests/unit/test_config_loader.py tests/unit/test_execution_runtime_factory.py tests/integration/test_execute_job_api.py tests/integration/test_api_smoke.py tests/integration/test_hybrid_job_flow.py -q` → passed (`8 passed`)

### Remote Validation Attempt
- `REMOTE_PASSWORD='666666' DRY_RUN=0 ./scripts/install_remote_module.sh` → succeeded; new source synced to `/mnt/hdo/infra-core/modules/av-workflow`.
- `scripts/modulectl.sh status av-workflow` → existing `av-workflow-av-api-1` container stayed healthy.
- Remote OpenAPI probe showed `/v1/jobs/{job_id}/execute` was still absent, so `modulectl.sh up av-workflow` did not rebuild the image.
- Manual remote `docker compose build av-api && docker compose up -d av-api` began successfully, but the rebuild is currently dominated by slow Debian package downloads for `ffmpeg` and its dependency tree.

### Remote Validation Resolution
- Root cause of the remote restart loop was not Python packaging; it was module sync drift. `scripts/install_remote_module.sh` excluded `src/av_workflow/runtime/` because the rsync rule used `--exclude=runtime` instead of anchoring the exclude to the repository root.
- Added a packaging regression test that rejects the broad exclude pattern.
- Narrowed the sync rule to `--exclude=/runtime/`, resynced the remote module, and rebuilt `av-api`.
- Remote verification after the fix:
  - `docker logs av-workflow-av-api-1` shows a clean Uvicorn startup
  - `GET /health` returns `{"status":"ok"}`
  - OpenAPI now includes `/v1/jobs/{job_id}/execute`
  - Executing the first 3500 characters of `xiaoshuo.txt` created `job-0001`
  - `job-0001` reached `manual_hold:composed`
  - runtime artifacts include `output/final.mp4`, `audio/final-mix.wav`, three shot clip files, and three shot subtitle files
  - concat manifest confirms three-shot stitching

### Current Slice: Routed Render Worker Surface
- Added a new package `av_workflow.render_service` with:
  - HTTP worker app
  - placeholder image backend
  - placeholder wan backend
  - opt-in `sd_cpp` image backend command builder
- Added `av-image-renderer` and `av-wan-renderer` services to `docker-compose.yml`.
- Added `.env.example` variables and `config/profiles/routed_api_local.yaml` so operators can switch the API into routed render mode without editing module YAML directly.

### Verification Result
- `PYTHONPATH=src ./.venv/bin/pytest tests/unit/test_module_packaging.py tests/unit/test_render_service_backends.py tests/integration/test_render_service_api.py -q` → passed (`9 passed`)
- `PYTHONPATH=src ./.venv/bin/pytest tests/unit tests/integration -q` → passed (`97 passed`)
- `./.venv/bin/python -m compileall src tests` → passed

### Routed Runtime Debug And Resolution
- Found a live remote config bug after deployment:
  - symptom: `.env` and `docker compose config` both showed `AV_WORKFLOW_CONFIG_PROFILE=routed_api_local`
  - real behavior: live container still loaded `render.mode=deterministic_local`
  - root cause: `ConfigLoader` merged profiles before modules, so `modules/render.yaml` overwrote the routed profile back to placeholder mode
- Fixed the loader precedence and added a regression test that requires profile overrides to survive module defaults.
- Found a second workflow logic bug after the first routed execution:
  - symptom: Chinese `xiaoshuo.txt` excerpts only routed to `av-image-renderer`
  - root cause: `_infer_motion_tier(...)` only matched English dynamic keywords
- Extended heuristic motion detection with Chinese action keywords and added a regression test that requires Chinese action text to yield `wan_dynamic`.

### Latest Remote Verification
- `docker exec av-workflow-av-api-1 python -c "from av_workflow.runtime.bootstrap import build_job_execution_service_factory_from_env; print(build_job_execution_service_factory_from_env().config.render.mode)"` → `routed_api`
- Real routed execution against a Chinese excerpt from `xiaoshuo.txt` now produces mixed backend usage:
  - `shot-001` image frame loop
  - `shot-002` Wan placeholder sequence (`frame-001.ppm`..`frame-003.ppm`)
  - `shot-003` image frame loop
- Remote logs confirm real HTTP worker dispatch during job execution:
  - `av-image-renderer` logged `POST /v1/render/image`
  - `av-wan-renderer` logged `POST /v1/render/video`
  - `av-api` logged `POST /v1/jobs/job-0001/execute`
- The job still correctly ends in `manual_hold` because placeholder render outputs remain blocked by review with `placeholder_render_output`.

### Verification Result
- `PYTHONPATH=src ./.venv/bin/pytest tests/unit/test_config_loader.py -q` → passed (`4 passed`)
- `PYTHONPATH=src ./.venv/bin/pytest tests/unit/test_planning_service.py -q` → passed (`4 passed`)
- `PYTHONPATH=src ./.venv/bin/pytest tests/unit/test_execution_runtime_factory.py tests/integration/test_execute_job_api.py tests/integration/test_render_service_api.py tests/unit/test_render_service_backends.py tests/unit/test_module_packaging.py -q` → passed (`12 passed`)
- `PYTHONPATH=src ./.venv/bin/pytest tests/unit/test_job_execution_service.py tests/unit/test_stage_runner.py tests/unit/test_render_jobs_service.py tests/integration/test_execute_job_api.py -q` → passed (`5 passed`)
- `PYTHONPATH=src ./.venv/bin/pytest tests/unit tests/integration -q` → passed (`99 passed`)
- `./.venv/bin/python -m compileall src tests` → passed

### Current Slice: Z-Image Backend Contract Correction
- Reopened the first real-image backend surface because the `sd_cpp` command contract did not match the official `stable-diffusion.cpp` `Z-Image` invocation shape.
- Wrote a failing regression test first that requires a split-model command:
  - `--diffusion-model`
  - `--vae`
  - `--llm`
  - `-o`
  - `-W`
  - `-H`
  - `-p`
- Updated the backend config and env mapping so routed image execution now models:
  - diffusion GGUF
  - VAE
  - Qwen LLM
- Synchronized operator-facing examples in `.env.example` and `README.md` with the corrected contract.

### Verification Result
- `PYTHONPATH=src ./.venv/bin/pytest tests/unit/test_render_service_backends.py -q` → passed (`2 passed`)

### Current Slice: Remote Z-Image Provisioning
- Verified remote deployment blockers before attempting any real model download:
  - `/mnt/hdo/infra-core/modules/av-workflow/models` exists but is `root:root`
  - `gaoyx` cannot write to that directory directly
  - the running `av-image-renderer` container can write to `/models` as root
  - `huggingface.co` is unreachable from the remote host, but `hf-mirror.com` and GitHub Releases are reachable
- Added `scripts/provision_z_image_backend.sh` as the canonical operator entrypoint for first real-image backend provisioning.
- The script is designed to:
  - repair model-directory ownership through Docker when needed
  - download the Linux `stable-diffusion.cpp` release archive
  - extract and normalize `sd-cli` under `models/bin/sd-cli`
  - download `Z-Image`, `ae.safetensors`, and Qwen GGUF assets with resume support
  - update `.env` to `AV_WORKFLOW_IMAGE_BACKEND_KIND=sd_cpp` plus normalized in-container paths

### Verification Result
- `PYTHONPATH=src ./.venv/bin/pytest tests/unit/test_module_packaging.py -q` → passed (`6 passed`)

### Remote Sync Regression And Fix
- Found a new packaging regression while pushing the provisioning changes:
  - local dry-run created a repository-root `models/` tree
  - `scripts/install_remote_module.sh` then tried to `rsync` that tree into the remote module
  - remote sync failed because `/mnt/hdo/infra-core/modules/av-workflow/models` is runtime-owned model state, not source-owned sync state
- Fixed the module sync contract by excluding `/models/` alongside `/runtime/`.

### Verification Result
- `PYTHONPATH=src ./.venv/bin/pytest tests/unit/test_module_packaging.py -q` → passed (`7 passed`)
- `REMOTE_PASSWORD='666666' DRY_RUN=0 ./scripts/install_remote_module.sh` → passed

### Live Remote Provisioning
- Remote dry-run of `scripts/provision_z_image_backend.sh` now succeeds and prints the expected GitHub + `hf-mirror.com` download plan.
- Real remote provisioning has started:
  - `stable-diffusion.cpp` Linux release archive downloaded successfully
  - `z-image-turbo-Q2_K.gguf` download is in progress on the target host

### Live Remote Provisioning Failure And Correction
- The first real provisioning run completed the binary and `Z-Image` diffusion download, then failed on the VAE source with `403 Forbidden`.
- Root cause: the default `black-forest-labs/FLUX.1-schnell` mirror route for `ae.safetensors` is not fetchable from the target host through `hf-mirror`.
- Corrective action:
  - switched `VAE_URL` to `receptektas/black-forest-labs-ae_safetensors`
  - kept the already downloaded binary and 3.4G diffusion model in place
  - prepared to rerun provisioning so only the missing assets are fetched

### Remote Real-Image Verification
- Rebuilt and verified the live remote API/runtime path after the latest planning/workspace/cover fixes:
  - `render.image_endpoint.timeout_sec=300.0`
  - `render.wan_endpoint.timeout_sec=1800.0`
  - `render.mode=routed_api`
- Executed a calm three-sentence Chinese smoke excerpt through `POST /v1/jobs/{job_id}/execute`.
- Confirmed the earlier root causes are closed on the remote host:
  - Chinese punctuation now splits into three shots
  - rerunning `job-0001` cleared the old runtime tree before writing new artifacts
  - preview/cover now preserve the real `png` suffix from the first rendered frame
- Remote runtime evidence for `job-0001`:
  - `output/final.mp4` created
  - `output/asset_manifest.json` created
  - `output/review_case.json` created
  - three `frame-001.png` files created under `shots/shot-00{1,2,3}/render/`
  - three narration wav files plus `audio/final-mix.wav` created
- Remote result:
  - `job-0001`
  - `status=completed`
  - `review_result=pass`
  - `reason_codes=[]`
- Remote media metadata:
  - video: `h264`, `640x384`, `24 fps`
  - audio: `aac`, `24000 Hz`, mono
  - duration: `9.0s`
- Routed backend usage for this smoke:
  - `av-image-renderer`: three successful `POST /v1/render/image`
  - `av-wan-renderer`: no `POST /v1/render/video`
- Observed throughput on the shared 5950X CPU:
  - roughly one static image shot every 50 seconds with `Z-Image-Turbo Q2_K + Qwen3-4B Q4_K_M`

### New Quality Gap Identified
- Copied the remote `job-0001` artifacts back to `.tmp/remote_verify_20260404/job-0001` for local inspection.
- Visual inspection confirms the pipeline is using real generated imagery rather than placeholder colors:
  - `shot-002` shows two seated figures by a window
  - `shot-003` shows a desk/book composition
  - `shot-001` remains noisy and semantically weak
- This exposed a new completion bug at the product level:
  - the workflow can reach `completed` based on technical QA only
  - no explicit semantic image review is executed before `mark_semantic_review_passed(...)`
- Next implementation priority is therefore semantic image review and fail-closed delivery gating for real-image runs.
