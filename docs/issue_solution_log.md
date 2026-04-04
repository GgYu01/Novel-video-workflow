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
