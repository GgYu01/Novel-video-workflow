from __future__ import annotations

from pathlib import Path

import pytest

from av_workflow.render_service.backends import (
    SdCppImageBackendConfig,
    StableDiffusionCppImageBackend,
    build_image_backend_from_env,
    build_sd_cpp_image_command,
)


def test_build_sd_cpp_image_command_uses_z_image_split_model_contract() -> None:
    config = SdCppImageBackendConfig(
        binary_path="/opt/stable-diffusion.cpp/sd",
        diffusion_model_path="/models/z-image/Z-Image-Turbo-Q2_K.gguf",
        vae_path="/models/z-image/ae.safetensors",
        llm_path="/models/qwen3/Qwen3-4B-Instruct-2507-Q4_K_M.gguf",
        width=1024,
        height=1024,
        steps=4,
        cfg_scale=1.0,
        sampling_method="euler",
        extra_args=("--seed", "7"),
    )

    command = build_sd_cpp_image_command(
        prompt="A football stadium at sunset",
        output_path=Path("/tmp/render/frame-001.png"),
        config=config,
    )

    assert command == [
        "/opt/stable-diffusion.cpp/sd",
        "--diffusion-model",
        "/models/z-image/Z-Image-Turbo-Q2_K.gguf",
        "--vae",
        "/models/z-image/ae.safetensors",
        "--llm",
        "/models/qwen3/Qwen3-4B-Instruct-2507-Q4_K_M.gguf",
        "-o",
        "/tmp/render/frame-001.png",
        "-W",
        "1024",
        "-H",
        "1024",
        "--steps",
        "4",
        "--cfg-scale",
        "1.0",
        "--sampling-method",
        "euler",
        "-p",
        "A football stadium at sunset",
        "--seed",
        "7",
    ]


def test_build_image_backend_from_env_reads_split_z_image_paths(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("AV_WORKFLOW_IMAGE_BACKEND_KIND", "sd_cpp")
    monkeypatch.setenv("AV_WORKFLOW_SD_CPP_BIN", "/opt/stable-diffusion.cpp/sd")
    monkeypatch.setenv(
        "AV_WORKFLOW_Z_IMAGE_DIFFUSION_MODEL_PATH",
        "/models/z-image/Z-Image-Turbo-Q2_K.gguf",
    )
    monkeypatch.setenv("AV_WORKFLOW_Z_IMAGE_VAE_PATH", "/models/z-image/ae.safetensors")
    monkeypatch.setenv(
        "AV_WORKFLOW_Z_IMAGE_LLM_PATH",
        "/models/qwen3/Qwen3-4B-Instruct-2507-Q4_K_M.gguf",
    )
    monkeypatch.setenv("AV_WORKFLOW_Z_IMAGE_STEPS", "6")
    monkeypatch.setenv("AV_WORKFLOW_Z_IMAGE_CFG_SCALE", "1.5")
    monkeypatch.setenv("AV_WORKFLOW_Z_IMAGE_SAMPLING_METHOD", "heun")
    monkeypatch.setenv("AV_WORKFLOW_Z_IMAGE_EXTRA_ARGS", "--seed 11")

    class DummyFfmpegExecutor:
        def run(self, args: list[str], *, cwd: Path | None = None, output_path: Path) -> None:
            raise AssertionError("ffmpeg should not run during backend construction")

    backend = build_image_backend_from_env(
        runtime_root=tmp_path,
        ffmpeg_executor=DummyFfmpegExecutor(),
    )

    assert isinstance(backend, StableDiffusionCppImageBackend)
    assert backend.config == SdCppImageBackendConfig(
        binary_path="/opt/stable-diffusion.cpp/sd",
        diffusion_model_path="/models/z-image/Z-Image-Turbo-Q2_K.gguf",
        vae_path="/models/z-image/ae.safetensors",
        llm_path="/models/qwen3/Qwen3-4B-Instruct-2507-Q4_K_M.gguf",
        width=1280,
        height=720,
        steps=6,
        cfg_scale=1.5,
        sampling_method="heun",
        extra_args=("--seed", "11"),
    )
