# AV Workflow Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the first production-grade skeleton of the internal single-tenant novel-to-video workflow with schema contracts, layered configuration, workflow state handling, deterministic media QA, and controlled agent proposals.

**Architecture:** The implementation starts with stable contracts and configuration, then adds workflow state management, stubbed adapters, deterministic composition/review, and finally deployment packaging for the remote `infra-core` module. External model calls remain behind adapter interfaces so the core workflow stays deterministic and testable.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, Temporal Python SDK, PostgreSQL, MinIO, pytest, ffmpeg/ffprobe, Docker Compose.

---

### Task 1: Package Skeleton And Shared Contracts

**Files:**
- Create: `src/av_workflow/__init__.py`
- Create: `src/av_workflow/contracts/__init__.py`
- Create: `src/av_workflow/contracts/enums.py`
- Create: `src/av_workflow/contracts/models.py`
- Test: `tests/unit/test_contract_models.py`

**Step 1: Write the failing test**

Create contract tests that validate required fields, enum boundaries, and immutable snapshot version behavior.

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_contract_models.py -v`
Expected: FAIL because contract models do not exist yet.

**Step 3: Write minimal implementation**

Implement the first Pydantic models for `Job`, `StorySpec`, `ShotPlan`, `ReviewCase`, and `OutputPackage`.

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_contract_models.py -v`
Expected: PASS

**Step 5: Commit**

Run:

```bash
git add src/av_workflow/contracts tests/unit/test_contract_models.py
git commit -m "feat: add initial workflow contracts"
```

### Task 2: Layered Configuration Loader

**Files:**
- Create: `src/av_workflow/config/__init__.py`
- Create: `src/av_workflow/config/models.py`
- Create: `src/av_workflow/config/loader.py`
- Create: `config/defaults/system.yaml`
- Create: `config/profiles/dev.yaml`
- Create: `config/modules/review.yaml`
- Test: `tests/unit/test_config_loader.py`

**Step 1: Write the failing test**

Add tests for merge precedence, forbidden override rejection, and schema validation of module settings.

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_config_loader.py -v`
Expected: FAIL because the loader and schemas do not exist.

**Step 3: Write minimal implementation**

Implement typed config models and a loader that merges defaults, profile, module, environment, and runtime overrides in a controlled order.

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_config_loader.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/av_workflow/config config tests/unit/test_config_loader.py
git commit -m "feat: add layered configuration loader"
```

### Task 3: Workflow State Machine Skeleton

**Files:**
- Create: `src/av_workflow/workflow/__init__.py`
- Create: `src/av_workflow/workflow/states.py`
- Create: `src/av_workflow/workflow/transitions.py`
- Create: `src/av_workflow/workflow/engine.py`
- Test: `tests/unit/test_workflow_transitions.py`

**Step 1: Write the failing test**

Cover legal transitions, illegal transitions, retry scheduling, and quarantine behavior.

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_workflow_transitions.py -v`
Expected: FAIL because the transition engine does not exist.

**Step 3: Write minimal implementation**

Implement a deterministic workflow transition layer that can run without Temporal to keep state logic testable in isolation.

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_workflow_transitions.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/av_workflow/workflow tests/unit/test_workflow_transitions.py
git commit -m "feat: add workflow state machine skeleton"
```

### Task 4: Ingest And Planning Services

**Files:**
- Create: `src/av_workflow/services/ingest.py`
- Create: `src/av_workflow/services/planning.py`
- Test: `tests/unit/test_ingest_service.py`
- Test: `tests/unit/test_planning_service.py`

**Step 1: Write the failing test**

Define fixtures for text normalization, chapter splitting, and `ShotPlan` generation from a stub planner.

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_ingest_service.py tests/unit/test_planning_service.py -v`
Expected: FAIL because service functions do not exist.

**Step 3: Write minimal implementation**

Implement deterministic ingest and planning services with adapter boundaries for future model-backed generation.

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_ingest_service.py tests/unit/test_planning_service.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/av_workflow/services tests/unit/test_ingest_service.py tests/unit/test_planning_service.py
git commit -m "feat: add ingest and planning services"
```

### Task 5: Composition And Technical QA

**Files:**
- Create: `src/av_workflow/services/compose.py`
- Create: `src/av_workflow/services/review/technical.py`
- Test: `tests/unit/test_compose_service.py`
- Test: `tests/unit/test_technical_review.py`

**Step 1: Write the failing test**

Cover manifest creation, output package assembly, media metadata checks, and technical QA verdict generation using fixtures.

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_compose_service.py tests/unit/test_technical_review.py -v`
Expected: FAIL because composition and technical review services do not exist.

**Step 3: Write minimal implementation**

Implement composition contracts first, then shell-safe `ffprobe`/fixture-based technical QA helpers.

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_compose_service.py tests/unit/test_technical_review.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/av_workflow/services tests/unit/test_compose_service.py tests/unit/test_technical_review.py
git commit -m "feat: add composition and technical review services"
```

### Task 6: Semantic Review Adapter And Policy Engine

**Files:**
- Create: `src/av_workflow/adapters/review.py`
- Create: `src/av_workflow/policy/engine.py`
- Test: `tests/unit/test_review_adapter.py`
- Test: `tests/unit/test_policy_engine.py`

**Step 1: Write the failing test**

Cover provider response normalization, malformed response fallback, threshold handling, and scoped retry decisions.

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_review_adapter.py tests/unit/test_policy_engine.py -v`
Expected: FAIL because adapter and policy engine do not exist.

**Step 3: Write minimal implementation**

Implement the image-review adapter interface and a policy engine that emits `PolicyDecision` objects only from validated review results.

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_review_adapter.py tests/unit/test_policy_engine.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/av_workflow/adapters src/av_workflow/policy tests/unit/test_review_adapter.py tests/unit/test_policy_engine.py
git commit -m "feat: add semantic review adapter and policy engine"
```

### Task 7: Agent Gateway And Permission Controls

**Files:**
- Create: `src/av_workflow/agents/gateway.py`
- Create: `src/av_workflow/agents/permissions.py`
- Test: `tests/unit/test_agent_gateway.py`

**Step 1: Write the failing test**

Cover proposal acceptance, forbidden direct state mutation, and circuit-breaker behavior for repeated low-quality proposals.

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_agent_gateway.py -v`
Expected: FAIL because the gateway does not exist.

**Step 3: Write minimal implementation**

Implement a proposal-only gateway for `OpenClaw`, `Codex`, and `Claude Code` with explicit permission checks.

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_agent_gateway.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/av_workflow/agents tests/unit/test_agent_gateway.py
git commit -m "feat: add agent proposal gateway"
```

### Task 8: API Surface And Deployment Packaging

**Files:**
- Create: `src/av_workflow/api/app.py`
- Create: `src/av_workflow/api/routes.py`
- Create: `scripts/doctor.sh`
- Create: `scripts/deploy.sh`
- Create: `docker-compose.yml`
- Modify: `README.md`
- Test: `tests/integration/test_api_smoke.py`

**Step 1: Write the failing test**

Define an integration smoke test for job creation, state lookup, and artifact summary retrieval using stub dependencies.

**Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_api_smoke.py -v`
Expected: FAIL because the API and deployment packaging do not exist.

**Step 3: Write minimal implementation**

Implement a minimal FastAPI surface, health endpoints, and deployment scripts that validate compose configuration and service readiness.

**Step 4: Run test to verify it passes**

Run: `pytest tests/integration/test_api_smoke.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/av_workflow/api scripts docker-compose.yml README.md tests/integration/test_api_smoke.py
git commit -m "feat: add api surface and deployment packaging"
```
