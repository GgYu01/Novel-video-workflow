# Execution Runtime Slice Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Turn the current hybrid workflow contracts into a runnable local-output pipeline that writes job artifacts under `runtime/jobs/<job_id>/...`, synthesizes placeholder media through local adapters, and stitches final video files with an executable ffmpeg layer.

**Architecture:** Keep the workflow engine and API as control-plane truth, but add a file-backed runtime workspace plus local provider adapters that can be swapped for real image, TTS, and Wan APIs later. The execution slice should stay modular: one layer for runtime paths and artifact writing, one layer for media provider adapters, one layer for ffmpeg execution, and one orchestration service that drives the full job run deterministically.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, pytest, subprocess-based ffmpeg execution, standard-library audio/image fallback generation, Docker Compose, layered YAML config.

---

### Task 1: Add Runtime Workspace And Artifact Path Utilities

**Files:**
- Create: `src/av_workflow/runtime/__init__.py`
- Create: `src/av_workflow/runtime/workspace.py`
- Create: `tests/unit/test_runtime_workspace.py`

**Step 1: Write the failing test**

Add tests that assert a job workspace is created under `runtime/jobs/<job_id>/`, that shot subdirectories are stable, and that text/JSON artifacts are written to predictable paths without mutating the contracts layer.

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src ./.venv/bin/pytest tests/unit/test_runtime_workspace.py -v`
Expected: FAIL because the runtime workspace module does not exist.

**Step 3: Write minimal implementation**

Implement a small runtime workspace helper that creates directories, writes text/JSON payloads, and returns canonical file paths for job, shot, audio, and compose artifacts.

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src ./.venv/bin/pytest tests/unit/test_runtime_workspace.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/av_workflow/runtime tests/unit/test_runtime_workspace.py
git commit -m "feat: add runtime workspace artifact utilities"
```

### Task 2: Add Local Provider Adapters For Deterministic Media Fallback

**Files:**
- Modify: `src/av_workflow/adapters/render.py`
- Modify: `src/av_workflow/adapters/tts.py`
- Create: `tests/unit/test_local_provider_adapters.py`

**Step 1: Write the failing test**

Add tests for a local render adapter that produces a shot clip file and frame refs, and a local TTS adapter that writes a timed audio file while preserving the existing normalized response contracts.

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src ./.venv/bin/pytest tests/unit/test_local_provider_adapters.py -v`
Expected: FAIL because the local provider implementations do not exist.

**Step 3: Write minimal implementation**

Implement deterministic local fallback adapters that materialize placeholder media on disk while keeping the existing adapter interfaces intact for future real provider replacement.

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src ./.venv/bin/pytest tests/unit/test_local_provider_adapters.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/av_workflow/adapters tests/unit/test_local_provider_adapters.py
git commit -m "feat: add deterministic local media provider adapters"
```

### Task 3: Add ffmpeg Execution And Compose Materialization

**Files:**
- Modify: `src/av_workflow/services/compose.py`
- Create: `src/av_workflow/runtime/ffmpeg.py`
- Create: `tests/unit/test_ffmpeg_executor.py`
- Modify: `tests/unit/test_ffmpeg_compose_paths.py`

**Step 1: Write the failing test**

Add tests for command generation, concat manifest materialization, and final muxing plan output. Keep the tests independent from a real ffmpeg binary by using a fake executor.

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src ./.venv/bin/pytest tests/unit/test_ffmpeg_executor.py tests/unit/test_ffmpeg_compose_paths.py -v`
Expected: FAIL because the execution wrapper does not exist.

**Step 3: Write minimal implementation**

Implement a subprocess-based ffmpeg executor and update compose helpers so they can materialize concat lists, subtitle packaging refs, and final mux targets under the runtime workspace.

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src ./.venv/bin/pytest tests/unit/test_ffmpeg_executor.py tests/unit/test_ffmpeg_compose_paths.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/av_workflow/runtime src/av_workflow/services tests/unit/test_ffmpeg_executor.py tests/unit/test_ffmpeg_compose_paths.py
git commit -m "feat: add executable ffmpeg composition layer"
```

### Task 4: Add End-To-End Job Execution Service

**Files:**
- Create: `src/av_workflow/services/job_execution.py`
- Create: `tests/unit/test_job_execution_service.py`
- Modify: `src/av_workflow/workflow/stage_runner.py`
- Modify: `tests/unit/test_stage_runner.py`

**Step 1: Write the failing test**

Add a test that runs a sample job through the execution service and asserts it writes a final job package, shot artifacts, audio artifacts, and final video refs into the runtime workspace.

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src ./.venv/bin/pytest tests/unit/test_job_execution_service.py tests/unit/test_stage_runner.py -v`
Expected: FAIL because the execution service does not exist.

**Step 3: Write minimal implementation**

Implement the orchestration service that binds together ingest, planning, render, audio, mix, and compose execution while preserving the existing deterministic stage runner contract.

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src ./.venv/bin/pytest tests/unit/test_job_execution_service.py tests/unit/test_stage_runner.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/av_workflow/services src/av_workflow/workflow tests/unit/test_job_execution_service.py tests/unit/test_stage_runner.py
git commit -m "feat: add end-to-end job execution service"
```

### Task 5: Package Runtime Dependencies And Document Execution

**Files:**
- Modify: `build/Dockerfile.api`
- Modify: `docker-compose.yml`
- Modify: `README.md`
- Modify: `docs/decision-log.md`
- Modify: `docs/issue_solution_log.md`
- Test: `tests/unit/test_module_packaging.py`

**Step 1: Write the failing test**

Add packaging assertions for runtime dependencies needed by the execution slice, including `ffmpeg` availability in the container image and any new runtime environment contract.

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src ./.venv/bin/pytest tests/unit/test_module_packaging.py -v`
Expected: FAIL because the runtime package contract is incomplete.

**Step 3: Write minimal implementation**

Update the container packaging and docs so the runtime execution path is reproducible on the remote module and clearly documented for operators.

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src ./.venv/bin/pytest tests/unit/test_module_packaging.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add build/Dockerfile.api docker-compose.yml README.md docs tests/unit/test_module_packaging.py
git commit -m "docs: package execution runtime slice"
```

### Task 6: Run Verification And Capture Evidence

**Files:**
- Modify: `docs/decision-log.md`
- Modify: `docs/issue_solution_log.md`

**Step 1: Run the focused unit suite**

Run:

```bash
PYTHONPATH=src ./.venv/bin/pytest tests/unit -v
```

Expected: PASS

**Step 2: Run the integration suite**

Run:

```bash
PYTHONPATH=src ./.venv/bin/pytest tests/integration -v
```

Expected: PASS

**Step 3: Run Python compilation**

Run:

```bash
./.venv/bin/python -m compileall src tests
```

Expected: PASS

**Step 4: Commit**

```bash
git add docs README.md
git commit -m "docs: record execution runtime verification evidence"
```

Plan complete and saved to `docs/plans/2026-04-03-execution-runtime-slice.md`. Two execution options:

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**
