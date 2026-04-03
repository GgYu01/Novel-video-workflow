# Hybrid Shot Pipeline Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extend the current skeleton into a chapter-capable, shot-based video workflow with hybrid rendering, multi-role TTS, subtitle timing, audio mixing, deterministic review, and scoped retries.

**Architecture:** Keep the workflow engine as production truth and add modular adapters for image rendering, `Wan` rendering, TTS, review, composition, and agent proposals. Implement the new path contract-first, then add deterministic local execution around those contracts, and only then connect remote module deployment.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, pytest, `ffmpeg`/`ffprobe`, Docker Compose, local model adapter APIs, structured YAML config.

---

### Task 1: Expand Core Contracts For Planning And Execution

**Files:**
- Modify: `src/av_workflow/contracts/models.py`
- Modify: `src/av_workflow/contracts/enums.py`
- Test: `tests/unit/test_contract_models.py`

**Step 1: Write the failing test**

Add tests for `CharacterBible`, `SceneBible`, `ShotPlanSet`, `VoiceCast`, `DialogueTimeline`, `ShotRenderJob`, and `ShotRenderResult`.

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src ./.venv/bin/pytest tests/unit/test_contract_models.py -v`
Expected: FAIL because the new contracts and enums do not exist.

**Step 3: Write minimal implementation**

Add immutable models and enums that represent planning, rendering, audio, and review boundaries without adding runtime behavior yet.

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src ./.venv/bin/pytest tests/unit/test_contract_models.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/av_workflow/contracts tests/unit/test_contract_models.py
git commit -m "feat: expand workflow contracts for hybrid shot execution"
```

### Task 2: Add Layered Config Branches For Render, Voice, And Review

**Files:**
- Modify: `src/av_workflow/config/models.py`
- Modify: `src/av_workflow/config/loader.py`
- Modify: `config/defaults/system.yaml`
- Create: `config/modules/render.yaml`
- Create: `config/modules/audio.yaml`
- Modify: `config/modules/review.yaml`
- Test: `tests/unit/test_config_loader.py`

**Step 1: Write the failing test**

Add tests for `render.*`, `audio.*`, `review.*`, and `agents.*` merge precedence plus forbidden runtime overrides.

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src ./.venv/bin/pytest tests/unit/test_config_loader.py -v`
Expected: FAIL because the new config schema does not validate.

**Step 3: Write minimal implementation**

Add typed config branches for local image rendering, `Wan` routing, voice casting, subtitle policy, mix policy, review thresholds, and agent-gateway controls.

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src ./.venv/bin/pytest tests/unit/test_config_loader.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/av_workflow/config config tests/unit/test_config_loader.py
git commit -m "feat: add layered config for render audio and review"
```

### Task 3: Build Story And Shot Planning Services

**Files:**
- Modify: `src/av_workflow/services/planning.py`
- Create: `src/av_workflow/services/story_bible.py`
- Create: `tests/unit/test_story_bible_service.py`
- Modify: `tests/unit/test_planning_service.py`

**Step 1: Write the failing test**

Add tests for character extraction, scene extraction, motion-tier assignment, and generation of a `ShotPlanSet` from the demo novel structure.

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src ./.venv/bin/pytest tests/unit/test_planning_service.py tests/unit/test_story_bible_service.py -v`
Expected: FAIL because the new services do not exist.

**Step 3: Write minimal implementation**

Implement deterministic planning services that can accept future agent proposals but still produce a valid default planning result without external models.

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src ./.venv/bin/pytest tests/unit/test_planning_service.py tests/unit/test_story_bible_service.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/av_workflow/services tests/unit/test_planning_service.py tests/unit/test_story_bible_service.py
git commit -m "feat: add story bible and shot planning services"
```

### Task 4: Add Render Adapter Contracts And Local Job Normalization

**Files:**
- Create: `src/av_workflow/adapters/render.py`
- Create: `src/av_workflow/services/render_jobs.py`
- Create: `tests/unit/test_render_adapter.py`
- Create: `tests/unit/test_render_jobs_service.py`

**Step 1: Write the failing test**

Cover image-render job submission, `Wan` render-job submission, status polling normalization, artifact extraction, and downgrade-ready error mapping.

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src ./.venv/bin/pytest tests/unit/test_render_adapter.py tests/unit/test_render_jobs_service.py -v`
Expected: FAIL because the render adapter layer is missing.

**Step 3: Write minimal implementation**

Implement pure adapter interfaces plus a render-job service that turns `ShotPlan` items into normalized internal `ShotRenderJob` requests.

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src ./.venv/bin/pytest tests/unit/test_render_adapter.py tests/unit/test_render_jobs_service.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/av_workflow/adapters src/av_workflow/services tests/unit/test_render_adapter.py tests/unit/test_render_jobs_service.py
git commit -m "feat: add render adapter contracts and job normalization"
```

### Task 5: Implement Voice Casting, Dialogue Timeline, And Subtitle Timing

**Files:**
- Create: `src/av_workflow/services/audio_timeline.py`
- Create: `src/av_workflow/adapters/tts.py`
- Create: `tests/unit/test_audio_timeline_service.py`
- Create: `tests/unit/test_tts_adapter.py`

**Step 1: Write the failing test**

Add tests for narrator/role voice assignment, segment splitting, stable `voice_id` mapping, and subtitle timing derived from synthetic TTS durations.

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src ./.venv/bin/pytest tests/unit/test_audio_timeline_service.py tests/unit/test_tts_adapter.py -v`
Expected: FAIL because the audio timeline and TTS adapter do not exist.

**Step 3: Write minimal implementation**

Implement stable multi-role voice casting and timeline construction without reference voice cloning.

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src ./.venv/bin/pytest tests/unit/test_audio_timeline_service.py tests/unit/test_tts_adapter.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/av_workflow/adapters src/av_workflow/services tests/unit/test_audio_timeline_service.py tests/unit/test_tts_adapter.py
git commit -m "feat: add multi-role audio timeline services"
```

### Task 6: Build Deterministic Audio Mix Support

**Files:**
- Create: `src/av_workflow/services/audio_mix.py`
- Create: `tests/unit/test_audio_mix_service.py`
- Modify: `src/av_workflow/services/compose.py`
- Modify: `tests/unit/test_compose_service.py`

**Step 1: Write the failing test**

Cover mix manifests, narrator/dialogue layering, optional BGM ducking, and composition inputs that reference the audio mix output.

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src ./.venv/bin/pytest tests/unit/test_audio_mix_service.py tests/unit/test_compose_service.py -v`
Expected: FAIL because mix services and compose integration are missing.

**Step 3: Write minimal implementation**

Implement deterministic mix planning and update composition models so the final package knows which audio artifact is authoritative.

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src ./.venv/bin/pytest tests/unit/test_audio_mix_service.py tests/unit/test_compose_service.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/av_workflow/services tests/unit/test_audio_mix_service.py tests/unit/test_compose_service.py
git commit -m "feat: add deterministic audio mix planning"
```

### Task 7: Add `ffmpeg` Stitch Planning And Media QA Inputs

**Files:**
- Modify: `src/av_workflow/services/compose.py`
- Modify: `src/av_workflow/services/review/technical.py`
- Create: `tests/unit/test_ffmpeg_compose_paths.py`
- Modify: `tests/unit/test_technical_review.py`

**Step 1: Write the failing test**

Add tests for concat manifests, subtitle packaging refs, preview variant refs, and `ffprobe`-style media metadata validation inputs.

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src ./.venv/bin/pytest tests/unit/test_ffmpeg_compose_paths.py tests/unit/test_technical_review.py -v`
Expected: FAIL because the enriched composition path is not implemented.

**Step 3: Write minimal implementation**

Extend the compose layer so it can plan deterministic final stitching from shot clips, subtitle refs, and audio mix refs.

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src ./.venv/bin/pytest tests/unit/test_ffmpeg_compose_paths.py tests/unit/test_technical_review.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/av_workflow/services tests/unit/test_ffmpeg_compose_paths.py tests/unit/test_technical_review.py
git commit -m "feat: add ffmpeg stitch planning and technical qa inputs"
```

### Task 8: Add Continuity Review And Scoped Retry Decisions

**Files:**
- Modify: `src/av_workflow/adapters/review.py`
- Modify: `src/av_workflow/policy/engine.py`
- Create: `src/av_workflow/services/review/continuity.py`
- Create: `tests/unit/test_continuity_review.py`
- Modify: `tests/unit/test_policy_engine.py`

**Step 1: Write the failing test**

Cover adjacent-shot drift scoring, uncertain-case escalation, shot-neighborhood retry scoping, and downgrade from `wan_dynamic` to `limited_motion`.

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src ./.venv/bin/pytest tests/unit/test_continuity_review.py tests/unit/test_policy_engine.py -v`
Expected: FAIL because continuity review and the new retry behavior do not exist.

**Step 3: Write minimal implementation**

Add continuity review services and update policy decisions so failures can target one shot, adjacent shots, or a whole scene.

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src ./.venv/bin/pytest tests/unit/test_continuity_review.py tests/unit/test_policy_engine.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/av_workflow/adapters src/av_workflow/policy src/av_workflow/services tests/unit/test_continuity_review.py tests/unit/test_policy_engine.py
git commit -m "feat: add continuity review and scoped retry policy"
```

### Task 9: Implement Director-Level Stage Orchestration

**Files:**
- Modify: `src/av_workflow/workflow/engine.py`
- Modify: `src/av_workflow/workflow/states.py`
- Modify: `src/av_workflow/workflow/transitions.py`
- Create: `src/av_workflow/workflow/stage_runner.py`
- Modify: `tests/unit/test_workflow_transitions.py`

**Step 1: Write the failing test**

Add tests for stage progression across planning, render, audio, compose, review, retry, and output publication boundaries.

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src ./.venv/bin/pytest tests/unit/test_workflow_transitions.py -v`
Expected: FAIL because the stage runner and new states do not exist.

**Step 3: Write minimal implementation**

Implement a deterministic stage runner that can coordinate the newly added services while keeping the workflow engine testable without Temporal.

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src ./.venv/bin/pytest tests/unit/test_workflow_transitions.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/av_workflow/workflow tests/unit/test_workflow_transitions.py
git commit -m "feat: add hybrid shot stage orchestration"
```

### Task 10: Expose Operator-Facing APIs For Job Launch And Artifact Inspection

**Files:**
- Modify: `src/av_workflow/api/routes.py`
- Modify: `src/av_workflow/api/app.py`
- Create: `tests/integration/test_hybrid_job_flow.py`
- Modify: `tests/integration/test_api_smoke.py`

**Step 1: Write the failing test**

Add API tests for submitting a novel job, listing stage status, reading shot-level artifacts, and retrieving subtitle/audio/final video refs.

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src ./.venv/bin/pytest tests/integration/test_api_smoke.py tests/integration/test_hybrid_job_flow.py -v`
Expected: FAIL because the enriched API surface does not exist.

**Step 3: Write minimal implementation**

Expose the new artifact surfaces and stage summaries without coupling the API layer to specific model providers.

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src ./.venv/bin/pytest tests/integration/test_api_smoke.py tests/integration/test_hybrid_job_flow.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/av_workflow/api tests/integration/test_api_smoke.py tests/integration/test_hybrid_job_flow.py
git commit -m "feat: expose hybrid job orchestration api"
```

### Task 11: Package Local Adapter Runtime And Remote Module Wiring

**Files:**
- Modify: `build/Dockerfile.api`
- Modify: `docker-compose.yml`
- Modify: `scripts/doctor.sh`
- Modify: `scripts/deploy.sh`
- Modify: `README.md`
- Create: `.env.example`
- Create: `.env.secrets.example`
- Test: `tests/unit/test_module_packaging.py`

**Step 1: Write the failing test**

Add tests for environment contract coverage and module packaging of the render/audio/review adapter endpoints.

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src ./.venv/bin/pytest tests/unit/test_module_packaging.py -v`
Expected: FAIL because the new runtime env contract is incomplete.

**Step 3: Write minimal implementation**

Add `ffmpeg` requirements, adapter endpoint env vars, local runtime defaults, and remote deployment notes without forcing real model pulls inside dev containers.

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src ./.venv/bin/pytest tests/unit/test_module_packaging.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add build docker-compose.yml scripts README.md .env.example .env.secrets.example tests/unit/test_module_packaging.py
git commit -m "feat: package hybrid workflow adapter runtime"
```

### Task 12: Run Full Verification And Capture Evidence

**Files:**
- Modify: `docs/decision-log.md`
- Modify: `docs/issue_solution_log.md`
- Modify: `README.md`

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

**Step 4: Run shell validation**

Run:

```bash
bash -n scripts/doctor.sh
bash -n scripts/deploy.sh
```

Expected: PASS

**Step 5: Commit**

```bash
git add docs README.md
git commit -m "docs: record hybrid workflow verification evidence"
```

Plan complete and saved to `docs/plans/2026-04-03-hybrid-shot-pipeline-implementation.md`. Two execution options:

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**
