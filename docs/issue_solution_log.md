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

### Stage and artifact updates needed to stay on the HTTP contract
- Symptom: the hybrid job flow and smoke tests needed to advance job stage and record generated media refs through the API, rather than mutating the in-memory store directly.
- Root cause: the control plane already had read endpoints, but the stage/artifact write path was not documented as the operator contract and could drift into test-only store mutation patterns.
- Fix: expose `PATCH` endpoints for stage, job artifacts, and shot artifacts, keep the store internal, and update the integration tests and README to use the HTTP flow end-to-end.
- Regression check: run `PYTHONPATH=src ./.venv/bin/pytest tests/integration -v` and confirm both integration tests pass through `TestClient`.

### Deterministic stage runner needed compatibility helpers without forcing orchestration dependencies
- Symptom: workflow transition tests should validate state progression without requiring a fully wired planning/audio/render stack.
- Root cause: the stage runner constructor and its transition helpers were too tightly coupled to the end-to-end runtime path.
- Fix: default the workflow engine in `DeterministicStageRunner`, keep explicit state-transition helpers for unit tests, and require planning/audio/render services only when `run()` is invoked.
- Regression check: run `PYTHONPATH=src ./.venv/bin/pytest tests/unit/test_workflow_transitions.py tests/unit/test_stage_runner.py -v` and confirm the state machine remains green.

### Remote host curl to `127.0.0.1:8080` failed even though the container was healthy
- Symptom: after `scripts/modulectl.sh up av-workflow` reported success, `curl http://127.0.0.1:8080/health` on the remote host returned connection refused.
- Root cause: the compose service uses `expose` only and joins the internal Docker and Traefik networks, so the API is reachable from the container network and ingress path but is not published as a host port.
- Fix: verify health with the container healthcheck, `docker exec`, or the ingress hostname instead of assuming host-loopback access.
- Regression check: inspect `docker inspect ...State.Health`, run `docker exec av-workflow-av-api-1 ... http://127.0.0.1:8080/health`, and confirm the container stays `healthy`.

### Execution runtime could not produce a real stitched output because the workflow stopped at metadata-only mix/compose contracts
- Symptom: the repository could plan shots and normalize render/TTS requests, but it still could not produce a runtime job directory with wav assets, concat manifests, and a final stitched video package.
- Root cause: the control plane had no file-backed execution service, `AudioMixManifest` generation did not materialize a real mix file, and `ffmpeg` availability was not encoded into the module image contract.
- Fix: add deterministic local render/TTS providers, concatenate wav segments into `runtime/jobs/<job_id>/audio/final-mix.wav`, introduce `DeterministicLocalJobExecutionService` to materialize runtime artifacts, and require `ffmpeg` in `build/Dockerfile.api`.
- Regression check: run `PYTHONPATH=src ./.venv/bin/pytest tests/unit/test_job_execution_service.py tests/unit/test_audio_mix_service.py tests/unit/test_module_packaging.py -v`, then run `PYTHONPATH=src ./.venv/bin/pytest tests/unit tests/integration -q`.

### Remote validation initially failed because runtime support files were present locally but absent from git history
- Symptom: local tests passed, but the remote container still raised `ModuleNotFoundError: No module named 'av_workflow.runtime'` and `ModuleNotFoundError: No module named 'av_workflow.services.job_execution'` after source sync and hot-load attempts.
- Root cause: the execution-slice implementation used local `src/av_workflow/runtime/*.py` files that had not actually been added to git, and the repository-level `.gitignore` entry `runtime/` unintentionally matched the source directory `src/av_workflow/runtime/`.
- Fix: narrow the ignore rule with explicit allowlist entries for `src/av_workflow/runtime/`, add `src/av_workflow/runtime/__init__.py`, `src/av_workflow/runtime/workspace.py`, and `src/av_workflow/runtime/ffmpeg.py` to version control, then repush and resync before retrying remote execution.
- Regression check: run `git ls-files 'src/av_workflow/runtime/*'`, verify the runtime files are tracked, then rerun `PYTHONPATH=src ./.venv/bin/pytest tests/unit tests/integration -q`.

### Placeholder render output could look like a successful video and still auto-complete the workflow
- Symptom: the remote demo mp4 played as green/yellow/pink solid-color clips, even though the runtime emitted a stitched video package and the job advanced to completion.
- Root cause: `DeterministicLocalRenderAdapter` intentionally wrote a single pure-color `PPM` frame per shot and looped it into `clip.mp4`, but the shot metadata did not mark those outputs as placeholders, `AssetManifest` dropped render provenance, `evaluate_asset_manifest(...)` only validated stream/subtitle structure, and both stage-runner paths advanced to `completed` without actually applying review failure results.
- Fix: tag deterministic local render outputs with placeholder metadata, propagate per-shot `render_metadata` into `AssetManifest`, fail technical review with `placeholder_render_output`, and route non-passing reviews through `PolicyEngine` so placeholder jobs stop at `manual_hold` instead of `completed`.
- Regression check: run `PYTHONPATH=src ./.venv/bin/pytest tests/unit/test_local_provider_adapters.py tests/unit/test_compose_service.py tests/unit/test_technical_review.py tests/unit/test_stage_runner.py tests/unit/test_job_execution_service.py -q`, then run `PYTHONPATH=src ./.venv/bin/python - <<'PY' ...` against the deterministic runtime and confirm `final_status=manual_hold`.

### API control plane could create jobs but could not actually execute them through layered runtime wiring
- Symptom: the service could create jobs and expose stage/artifact mutation endpoints, but it still lacked a formal API entrypoint that built a real execution service from layered config and ran the workflow end-to-end.
- Root cause: runtime execution existed only as directly instantiated Python services in tests and ad hoc scripts, and render backend selection had no explicit config switch between placeholder local rendering and routed provider APIs.
- Fix: add `render.mode`, introduce a job-scoped execution-service factory under `av_workflow.runtime.bootstrap`, and expose `POST /v1/jobs/{job_id}/execute` so the API can run the workflow and persist resulting stage/artifact views through the same HTTP contract.
- Regression check: run `PYTHONPATH=src ./.venv/bin/pytest tests/unit/test_execution_runtime_factory.py tests/integration/test_execute_job_api.py -q`.

### Remote source sync silently skipped `bootstrap.py` even though local tests passed
- Symptom: the rebuilt remote `av-api` image started and immediately crashed with `ModuleNotFoundError: No module named 'av_workflow.runtime.bootstrap'`, even though the local source tree contained `src/av_workflow/runtime/bootstrap.py` and the local test suite was green.
- Root cause: `scripts/install_remote_module.sh` used `rsync --exclude=runtime`, which matched the repository root `runtime/` as intended but also matched the source package path `src/av_workflow/runtime/`, so new files under that package were never copied to `/mnt/hdo/infra-core/modules/av-workflow`.
- Fix: narrow the rsync filter to `--exclude=/runtime/`, add a regression test that rejects the broad `--exclude=runtime` pattern, resync the module, and rebuild the remote image.
- Regression check: run `PYTHONPATH=src ./.venv/bin/pytest tests/unit/test_module_packaging.py -q`, then confirm `ls /mnt/hdo/infra-core/modules/av-workflow/src/av_workflow/runtime/bootstrap.py` exists on the remote host before rebuilding.

### Routed profile switch could be silently cancelled by module defaults
- Symptom: the remote `.env` set `AV_WORKFLOW_CONFIG_PROFILE=routed_api_local`, `docker compose config` showed the variable, but the running API still loaded `render.mode=deterministic_local`.
- Root cause: `ConfigLoader.load(...)` merged `profiles/<name>.yaml` before `modules/render.yaml`, so the module default rewrote the operator-selected routed profile back to placeholder mode.
- Fix: change the merge order to `defaults -> modules -> profiles -> env -> runtime`, and add a regression test that asserts `routed_api_local` overrides `modules/render.yaml`.
- Regression check: run `PYTHONPATH=src ./.venv/bin/pytest tests/unit/test_config_loader.py -q`, then verify `docker exec av-workflow-av-api-1 python -c \"from av_workflow.runtime.bootstrap import build_job_execution_service_factory_from_env; print(build_job_execution_service_factory_from_env().config.render.mode)\"` prints `routed_api`.

### Chinese novel scenes could never trigger `wan_dynamic`
- Symptom: real execution against `xiaoshuo.txt` routed only to `av-image-renderer`, even though the source text included crowd celebration and action-heavy stadium scenes.
- Root cause: `_infer_motion_tier(...)` only matched English dynamic keywords such as `crowd`, `celebration`, and `chase`, so Chinese narration always degraded to `limited_motion`.
- Fix: extend heuristic motion inference with Chinese action and crowd-motion cues such as `欢呼`, `庆祝`, `追逐`, and `冲刺`, and add a regression test that requires Chinese action text to yield at least one `wan_dynamic` shot.
- Regression check: run `PYTHONPATH=src ./.venv/bin/pytest tests/unit/test_planning_service.py -q`, then execute a Chinese excerpt through `/v1/jobs/{job_id}/execute` and confirm `av-wan-renderer` logs `POST /v1/render/video`.

### The first `sd_cpp` image backend surface used the wrong `Z-Image` command contract
- Symptom: the repository exposed an opt-in `sd_cpp` backend, but its command builder treated the `Z-Image` GGUF as a single `-m` model, treated the Qwen model as `--diffusion-model`, and omitted the required `--vae` and `--llm` flags.
- Root cause: the initial implementation copied a generic single-model `stable-diffusion.cpp` assumption instead of the official split-model `Z-Image` invocation contract.
- Fix: redefine the backend config around `diffusion_model_path`, `vae_path`, and `llm_path`, build the command with `--diffusion-model`, `--vae`, `--llm`, `-o`, `-W`, `-H`, and `-p`, and update `.env.example`, `README.md`, and backend tests to match.
- Regression check: run `PYTHONPATH=src ./.venv/bin/pytest tests/unit/test_render_service_backends.py -q`.

### Remote real-image provisioning was blocked by host permissions and Hugging Face reachability
- Symptom: the remote module had a mounted `models/` directory, but `gaoyx` could not write to it, and direct access to `huggingface.co` failed even though GitHub and `hf-mirror.com` were reachable.
- Root cause: the existing renderer container created `/mnt/hdo/infra-core/modules/av-workflow/models` as `root:root`, and the target host network could not connect to `huggingface.co:443`.
- Fix: add `scripts/provision_z_image_backend.sh` as the canonical provisioning entrypoint. The script uses the already-running renderer container to repair ownership when needed, downloads the Linux `stable-diffusion.cpp` binary from GitHub Releases, downloads model assets from `hf-mirror.com`, and updates `.env` to the normalized `sd_cpp` paths.
- Regression check: run `bash -n scripts/provision_z_image_backend.sh`, `PYTHONPATH=src ./.venv/bin/pytest tests/unit/test_module_packaging.py -q`, then run `DRY_RUN=0 ./scripts/provision_z_image_backend.sh` inside the module directory on the target host.

### Remote module sync must treat `models/` as runtime state, not source payload
- Symptom: after adding the provisioning script, a local dry-run created an ignored `models/` tree under the repository root, and the next `scripts/install_remote_module.sh` run failed with `rsync` permission errors against `/mnt/hdo/infra-core/modules/av-workflow/models`.
- Root cause: `install_remote_module.sh` excluded `/runtime/` but not `/models/`, so local model-cache directories were still treated as syncable source content.
- Fix: exclude `/models/` from remote module sync the same way `/runtime/` is excluded, and add a regression test that requires the anchored `--exclude=/models/` rule.
- Regression check: run `PYTHONPATH=src ./.venv/bin/pytest tests/unit/test_module_packaging.py -q`, then rerun `REMOTE_PASSWORD=*** DRY_RUN=0 ./scripts/install_remote_module.sh`.

### The original VAE download source returned `403 Forbidden` through `hf-mirror`
- Symptom: `scripts/provision_z_image_backend.sh` successfully downloaded the Linux `stable-diffusion.cpp` release and `z-image-turbo-Q2_K.gguf`, but failed immediately when requesting `https://hf-mirror.com/black-forest-labs/FLUX.1-schnell/resolve/main/ae.safetensors`.
- Root cause: the target host could reach `hf-mirror.com`, but that particular mirrored `black-forest-labs/FLUX.1-schnell` file route returned `403`, so the provisioning script stopped before downloading Qwen and before updating `.env`.
- Fix: switch the default `VAE_URL` to a public mirror repo that serves the same `ae.safetensors` artifact through `hf-mirror`: `receptektas/black-forest-labs-ae_safetensors`.
- Regression check: run `PYTHONPATH=src ./.venv/bin/pytest tests/unit/test_module_packaging.py -q`, then rerun `DRY_RUN=0 ./scripts/provision_z_image_backend.sh` on the remote host.

### Real image outputs can still bypass semantic QA and auto-complete
- Symptom: remote `job-0001` completed with `review_result=pass` after generating real `Z-Image` PNG frames, but local visual inspection of the returned artifacts showed at least one shot (`shot-001`) was still noisy and semantically weak.
- Root cause: `evaluate_asset_manifest(...)` validates only stream/subtitle structure and placeholder provenance, while `DeterministicLocalJobExecutionService.run(...)` immediately calls `mark_semantic_review_passed(...)` after a technical pass without executing a real semantic image-review stage.
- Planned fix: add an explicit semantic image-review service for real-render jobs and fail closed when that review is missing or non-passing, instead of synthesizing semantic approval from technical approval.
- Pending regression check: rerun the remote calm-smoke workflow after semantic review integration and confirm weak real-image outputs no longer reach `completed` without an explicit semantic pass.
