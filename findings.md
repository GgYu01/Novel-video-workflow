# Findings

## 2026-04-03

- The repo already has deterministic planning, render normalization, TTS timing, audio mix planning, technical review, continuity review, API control-plane mutation endpoints, and remote module deployment.
- The remote module is deployed and the API container is healthy, but the current runtime is still control-plane oriented rather than true media-generation execution.
- The biggest remaining gap is not HTTP control; it is executable media production behind the contracts:
  - render adapters are still stub/interface level
  - compose currently builds plans/manifests, not real ffmpeg execution
  - no end-to-end job runner persists actual runtime outputs for a submitted story
- Current requirements and design docs already support a clean next slice:
  - keep adapter APIs stable
  - write runtime outputs under `runtime/jobs/<job_id>/...`
  - preserve image-first plus selective `Wan`
  - keep developer validation independent from real model pulls
- Both the local development container and the remote host currently lack `ffmpeg`.
- The local development container also lacks common image helper libraries such as `PIL`, `imageio`, `cv2`, and `numpy`.
- Therefore the next implementation must separate:
  - binary-independent unit tests and deterministic local file emitters
  - runtime packaging that installs `ffmpeg` inside the module image

## 2026-04-03 Follow-up Debug

- The remote demo job `demo-job-001` produces pure solid-color frames by design in the current local fallback renderer.
- Evidence from the remote `frame-001.ppm` files:
  - `shot-001` RGB `(136, 191, 110)`
  - `shot-002` RGB `(141, 170, 37)`
  - `shot-003` RGB `(252, 52, 200)`
  - every sampled pixel in the frame is identical, so the resulting mp4 is a color loop, not a real scene render.
- The technical review layer now flags placeholder render metadata with `placeholder_render_output` and recommends manual hold for those jobs.
- The workflow runner and job execution service now stop automatic completion when the review does not pass.
  - This prevents placeholder videos from being treated as deliverable outputs.
- Render payload normalization now tolerates `metadata: null`, and asset-manifest construction now tolerates missing `render_metadata` by normalizing to `{}`.
- The repository now has the first non-placeholder render integration surface:
  - endpoint-configured `image_endpoint` and `wan_endpoint`
  - `ApiRenderBackendAdapter` for HTTP provider submission
  - `RoutingRenderAdapter` for backend-specific dispatch
- That surface is not yet wired into runtime bootstrap, and there is still no packaged local image-model or Wan-model service in `docker-compose.yml`.

## 2026-04-04 Execution Wiring

- The repository now has a config-driven runtime bootstrap under `src/av_workflow/runtime/bootstrap.py`.
- `render.mode` is the new hard switch between placeholder contract-validation mode (`deterministic_local`) and real-provider routing mode (`routed_api`).
- The API now has a formal execution entrypoint: `POST /v1/jobs/{job_id}/execute`.
- The execution path is job-scoped rather than app-global because TTS output paths and runtime artifact trees are job-bound.
- `unsloth/Z-Image-Turbo-GGUF` exists as a Hugging Face GGUF model family candidate, and the model page currently lists low-bit GGUF variants including `Q2_K`; it is a viable first candidate to evaluate for the future `av-image-renderer` service, but it is not yet integrated in this repo.
- Remote sync to `/mnt/hdo/infra-core/modules/av-workflow` succeeded, and `modulectl.sh up av-workflow` left the existing container running.
- The remote container was still serving the old OpenAPI surface without `/v1/jobs/{job_id}/execute`, which confirmed that `modulectl.sh up` did not force a rebuild of the `av-api` image.
- A manual remote `docker compose build av-api && docker compose up -d av-api` started successfully, but rebuilding the image currently spends several minutes downloading Debian `ffmpeg` dependencies; this is an infra/package-fetch bottleneck, not an application trace error.

## 2026-04-04 Routed Render Services

- The remote `av-api` rebuild initially failed after image creation because `scripts/install_remote_module.sh` used `rsync --exclude=runtime`, which excluded the source package path `src/av_workflow/runtime/` in addition to the generated top-level `runtime/` directory.
- Tightening that rule to `--exclude=/runtime/` restored remote source parity and allowed the rebuilt API container to start successfully.
- Remote runtime validation now confirms:
  - `GET /health` returns `{"status":"ok"}`
  - `/v1/jobs/{job_id}/execute` is present in OpenAPI
  - executing a real excerpt from `xiaoshuo.txt` produces `manual_hold`
  - runtime artifacts include three shot clip files, per-shot subtitles, multiple TTS wav files, and `output/final.mp4`
- The repository now ships internal routed render-worker code under `src/av_workflow/render_service/` plus two compose services:
  - `av-image-renderer`
  - `av-wan-renderer`
- The first local real-image backend surface is now codified as an opt-in `sd_cpp` backend with environment-driven paths for:
  - the `stable-diffusion.cpp` binary
  - the `Z-Image-Turbo` diffusion GGUF path
  - the required `ae.safetensors` VAE path
  - the required Qwen LLM path
- `av-wan-renderer` remains placeholder-only for now; real `Wan2.2-TI2V-5B-GGUF` execution is still pending.

## 2026-04-04 Routed End-to-End Verification

- The first routed render rollout exposed a real config-layer bug: the operator profile `routed_api_local` was present in the container environment but was neutralized by `modules/render.yaml` because profiles loaded too early.
- After fixing the loader precedence and rebuilding `av-api`, remote runtime inspection now shows `render.mode=routed_api` inside the live container.
- The first routed execution against `xiaoshuo.txt` proved the control plane was calling `av-image-renderer`, but it also exposed a second root cause: Chinese action scenes never hit `WAN` because motion-tier inference only looked for English keywords.
- After extending heuristic motion detection with Chinese action cues and rebuilding again, a second real execution against the same Chinese excerpt produced mixed routing:
  - `shot-001` image path
  - `shot-002` Wan path
  - `shot-003` image path
- Remote evidence now confirms the full HTTP worker topology is live:
  - `av-api` logs `POST /v1/jobs/{job_id}/execute`
  - `av-image-renderer` logs `POST /v1/render/image`
  - `av-wan-renderer` logs `POST /v1/render/video`
- Output quality is still intentionally non-deliverable because both worker services remain on placeholder backends; the workflow is now topology-correct, not model-quality complete.

## 2026-04-04 Z-Image Contract Correction

- The original `sd_cpp` backend surface was structurally wrong for `Z-Image`: it assumed one main model plus one auxiliary model, but the official runtime surface is split across diffusion model, VAE, and LLM assets.
- The repository now encodes that split contract directly in the backend config and operator env names:
  - `AV_WORKFLOW_Z_IMAGE_DIFFUSION_MODEL_PATH`
  - `AV_WORKFLOW_Z_IMAGE_VAE_PATH`
  - `AV_WORKFLOW_Z_IMAGE_LLM_PATH`
- This fixes a root-cause class where routed mode could look “configured” in Compose and docs while still being incapable of launching a real image generation command.

## 2026-04-04 Remote Provisioning Constraints

- The target host can reach `github.com` and `hf-mirror.com`, but it cannot currently connect to `huggingface.co`.
- The host-side module directory already has a bound `models/` tree, but it is owned by `root:root`, so `gaoyx` cannot write there directly.
- The running `av-image-renderer` container is root inside the container and can write to `/models`, which provides a stable way to repair permissions without host-level package installs or sidecar containers.
- The repository now includes a formal provisioning script for the first real image backend:
  - `scripts/provision_z_image_backend.sh`
  - default binary source: GitHub Releases for `leejet/stable-diffusion.cpp`
  - default model source: `hf-mirror.com`
  - default asset set:
    - `unsloth/Z-Image-Turbo-GGUF` `z-image-turbo-Q2_K.gguf`
    - `black-forest-labs/FLUX.1-schnell` `ae.safetensors`
    - `unsloth/Qwen3-4B-Instruct-2507-GGUF` `Qwen3-4B-Instruct-2507-Q4_K_M.gguf`
- The remote module sync path must now exclude both `/runtime/` and `/models/`.
  - `runtime/` is generated job state
  - `models/` is generated/downloaded model state
  - syncing either as if it were source code creates deployment drift and permission failures
- The first provisioning run proved that `hf-mirror.com` is usable for `Z-Image` and `Qwen`, but not for the original `black-forest-labs/FLUX.1-schnell` VAE URL.
  - `z-image-turbo-Q2_K.gguf` downloaded successfully
  - the original `ae.safetensors` URL returned `403`
  - the script now defaults to a public `ae.safetensors` mirror repo so provisioning can resume without redownloading the 3.4G diffusion model

## 2026-04-04 Remote Real-Image Smoke

- A calm three-sentence Chinese excerpt now completes end to end on the remote CPU host through the real `sd_cpp` image path:
  - `job-0001`
  - final status: `completed`
  - review result: `pass`
- The generated runtime package is no longer placeholder media:
  - `shot-001`, `shot-002`, and `shot-003` each produced `frame-001.png` plus `clip.mp4`
  - `asset_manifest.json` records `content_source=image_model`
  - `placeholder_mode=null`
- Remote media evidence confirms the stitched output shape:
  - `final.mp4`
  - `h264` video
  - `aac` mono audio
  - `640x384`
  - `24 fps`
  - `9.0s`
- Routed backend selection behaved correctly for this static excerpt:
  - `av-image-renderer` handled three `POST /v1/render/image`
  - `av-wan-renderer` handled no `POST /v1/render/video`
- CPU timing is now observable and usable for planning:
  - `shot-001` image generation finished about 49 seconds after planning artifacts were written
  - `shot-002` finished about 51 seconds later
  - `shot-003` then completed and the final compose returned `completed`
- Visual inspection of the returned PNG frames shows the render path is real but quality is uneven:
  - `shot-002` and `shot-003` are broadly recognizable as two seated people by a window and a desk/book scene
  - `shot-001` is still noisy and abstract for the stadium-box prompt
- The current technical QA is therefore a false positive for delivery quality in real-image mode:
  - `evaluate_asset_manifest(...)` only checks streams, subtitles, and placeholder metadata
  - `job_execution.run(...)` marks semantic review passed implicitly after technical pass
- The current `sd_cpp` prompt surface is minimal:
  - `shot-001` prompt: `圣·莫伊斯球场的包厢里很安静。. Chapter 1`
  - `shot-002` prompt: raw narration sentence plus `Chapter 1`
  - `shot-003` prompt: raw narration sentence plus `Chapter 1`
- That prompt shape is a likely contributor to weak visual quality, but the confirmed architectural gap is broader: the workflow still lacks an explicit semantic image-review gate before auto-completion.
