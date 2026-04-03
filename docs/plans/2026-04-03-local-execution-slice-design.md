# Local Execution Slice Design

## Status
Approved for implementation on 2026-04-03.

## Goal
Extend the current control-plane-complete workflow into a first real output-producing local execution slice that writes runtime artifacts, generates deterministic local shot/audio files, runs `ffmpeg`, and emits a stitched video package.

## Root Cause
The repository already covers:
- planning and shot contracts
- stage transitions and retry boundaries
- stage/artifact API control plane
- remote module packaging and deployment

But it still lacks the execution layer behind those contracts:
- render and TTS adapters normalize payloads but do not produce local files
- composition builds `ffmpeg` plans but does not execute them
- no runtime workspace owns `runtime/jobs/<job_id>/...`
- no end-to-end local job runner creates a real stitched output package

This means the system is operable as a workflow skeleton, but not yet as a real local-output generator.

## Selected Slice
Implement a deterministic local execution slice before wiring real model backends.

This slice adds:
1. `RuntimeWorkspace`
2. deterministic local render/TTS providers that write valid files
3. `ffmpeg` execution for shot concatenation and output generation
4. `LocalJobRunner` as the first true artifact-producing entrypoint

It intentionally does not yet add:
- real `Wan` CPU inference
- real local image model inference
- real local TTS inference
- persistent DB-backed orchestration

## Why This Is The Right Boundary
If real model providers are connected first, failures become mixed:
- provider failure
- file path failure
- compose failure
- runtime environment failure
- orchestration failure

By first adding deterministic file-producing execution, we get:
- reproducible regression tests
- stable runtime directory semantics
- a true mp4 output contract
- provider-swap safety later

## Architecture

### RuntimeWorkspace
Own all filesystem layout under `runtime/jobs/<job_id>/...`.

Responsibilities:
- create job root and phase directories
- allocate paths for source, planning, shot render, shot audio, mix, compose, output, and review
- translate local paths into stable artifact refs

### Deterministic Local Providers
Add two provider implementations:
- `DeterministicLocalRenderAdapter`
- `DeterministicLocalTTSAdapter`

These do not try to maximize realism. They prove the runtime can:
- emit clip and frame files per shot
- emit wav files per dialogue/narration segment
- feed those files into mix and compose

### Execution-Oriented Compose Layer
Keep the current plan-building functions, then add execution helpers that:
- write concat manifests
- prepare subtitle/audio inputs
- run `ffmpeg`
- return concrete generated output refs

### LocalJobRunner
This runner is the first real job executor.

It should:
- accept a `Job` plus raw text
- reuse current planning/stage logic
- allocate runtime paths
- call deterministic local providers
- execute compose
- emit a populated `OutputPackage`

## Runtime Layout
The slice should write into:
- `runtime/jobs/<job_id>/source/`
- `runtime/jobs/<job_id>/planning/`
- `runtime/jobs/<job_id>/shots/<shot_id>/render/`
- `runtime/jobs/<job_id>/shots/<shot_id>/audio/`
- `runtime/jobs/<job_id>/audio/`
- `runtime/jobs/<job_id>/compose/`
- `runtime/jobs/<job_id>/output/`

## Acceptance Criteria
- a local run creates real files under one runtime job directory
- a stitched mp4 is produced
- subtitle/audio refs point to generated local artifacts
- the workflow engine and control-plane API do not need redesign
- future real providers can replace deterministic providers without changing job-state semantics
