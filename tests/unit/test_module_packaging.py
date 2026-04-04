from __future__ import annotations

import os
from pathlib import Path

import yaml


def test_module_packaging_files_exist() -> None:
    remote_install_script = Path("scripts/install_remote_module.sh")
    z_image_provision_script = Path("scripts/provision_z_image_backend.sh")

    assert Path(".env.example").is_file()
    assert Path(".env.secrets.example").is_file()
    assert Path("build/Dockerfile.api").is_file()
    assert Path("config/profiles/routed_api_local.yaml").is_file()
    assert remote_install_script.is_file()
    assert os.access(remote_install_script, os.X_OK)
    assert z_image_provision_script.is_file()
    assert os.access(z_image_provision_script, os.X_OK)


def test_root_compose_is_ready_for_infra_core_module_use() -> None:
    compose = yaml.safe_load(Path("docker-compose.yml").read_text(encoding="utf-8"))

    av_api = compose["services"]["av-api"]
    image_renderer = compose["services"]["av-image-renderer"]
    wan_renderer = compose["services"]["av-wan-renderer"]

    assert av_api["build"]["dockerfile"] == "./build/Dockerfile.api"
    assert av_api["build"]["args"]["PYTHON_BASE_IMAGE"] == "${AV_WORKFLOW_PYTHON_BASE_IMAGE:-python:3.12-slim}"
    assert av_api["build"]["args"]["APT_MIRROR"] == "${AV_WORKFLOW_APT_MIRROR:-}"
    assert "./.env" in av_api["env_file"]
    assert "./.env.secrets" in av_api["env_file"]
    assert "infra_gateway_net" in av_api["networks"]
    assert compose["networks"]["infra_gateway_net"]["external"] is True
    assert av_api["healthcheck"]["test"][0] == "CMD-SHELL"
    assert "AV_WORKFLOW_API_PORT" in av_api["healthcheck"]["test"][1]
    assert image_renderer["build"]["dockerfile"] == "./build/Dockerfile.api"
    assert "uvicorn av_workflow.render_service.app:app" in image_renderer["command"]
    assert image_renderer["environment"]["AV_WORKFLOW_RENDERER_ROLE"] == "image"
    assert "${AV_WORKFLOW_MODELS_ROOT:-./models}:/models" in image_renderer["volumes"]
    assert wan_renderer["build"]["dockerfile"] == "./build/Dockerfile.api"
    assert "uvicorn av_workflow.render_service.app:app" in wan_renderer["command"]
    assert wan_renderer["environment"]["AV_WORKFLOW_RENDERER_ROLE"] == "wan"
    assert wan_renderer["environment"]["AV_WORKFLOW_WAN_BACKEND_KIND"] == "${AV_WORKFLOW_WAN_BACKEND_KIND:-placeholder}"


def test_remote_install_script_defaults_to_dry_run() -> None:
    script = Path("scripts/install_remote_module.sh").read_text(encoding="utf-8")

    assert 'DRY_RUN="${DRY_RUN:-1}"' in script
    assert 'REMOTE_ROOT="${REMOTE_ROOT:-/mnt/hdo/infra-core}"' in script
    assert 'REMOTE_MODULE_PATH="${REMOTE_MODULE_PATH:-${REMOTE_ROOT}/modules/av-workflow}"' in script
    assert "modules/registry.list" in script
    assert 'ssh -o StrictHostKeyChecking=no -o ConnectTimeout=8 -p ${REMOTE_PORT}' in script


def test_remote_install_script_only_excludes_runtime_state_root() -> None:
    script = Path("scripts/install_remote_module.sh").read_text(encoding="utf-8")

    assert '--exclude=/runtime/' in script
    assert '--exclude=/models/' in script
    assert "--exclude=runtime" not in script


def test_api_image_runtime_uses_layered_host_and_port_defaults() -> None:
    dockerfile = Path("build/Dockerfile.api").read_text(encoding="utf-8")
    env_example = Path(".env.example").read_text(encoding="utf-8")

    assert "AV_WORKFLOW_API_HOST" in dockerfile
    assert "AV_WORKFLOW_API_PORT" in dockerfile
    assert "ffmpeg" in dockerfile
    assert "ARG PYTHON_BASE_IMAGE=python:3.12-slim" in dockerfile
    assert 'ARG APT_MIRROR=""' in dockerfile
    assert "deb.debian.org" in dockerfile
    assert "FROM ${PYTHON_BASE_IMAGE}" in dockerfile
    assert "AV_WORKFLOW_PYTHON_BASE_IMAGE=python:3.12-slim" in env_example
    assert "AV_WORKFLOW_APT_MIRROR=" in env_example
    assert "AV_WORKFLOW_CONFIG_ROOT=/app/config" in env_example
    assert "AV_WORKFLOW_RUNTIME_ROOT=/app/runtime" in env_example
    assert "AV_WORKFLOW_CONFIG_MODULES=render,audio,review" in env_example
    assert "AV_WORKFLOW_IMAGE_RENDERER_PORT=8091" in env_example
    assert "AV_WORKFLOW_WAN_RENDERER_PORT=8092" in env_example
    assert "AV_WORKFLOW_IMAGE_BACKEND_KIND=placeholder" in env_example
    assert "AV_WORKFLOW_WAN_BACKEND_KIND=placeholder" in env_example
    assert "AV_WORKFLOW_MODELS_ROOT=./models" in env_example
    assert "AV_WORKFLOW_Z_IMAGE_DIFFUSION_MODEL_PATH=/models/z-image/Z-Image-Turbo-Q2_K.gguf" in env_example
    assert "AV_WORKFLOW_Z_IMAGE_VAE_PATH=/models/z-image/ae.safetensors" in env_example
    assert "AV_WORKFLOW_Z_IMAGE_LLM_PATH=/models/qwen3/Qwen3-4B-Instruct-2507-Q4_K_M.gguf" in env_example


def test_z_image_provision_script_defaults_to_mirror_and_release_binary() -> None:
    script = Path("scripts/provision_z_image_backend.sh").read_text(encoding="utf-8")

    assert 'HF_BASE_URL="${HF_BASE_URL:-https://hf-mirror.com}"' in script
    assert 'SD_CPP_RELEASE_URL="${SD_CPP_RELEASE_URL:-https://github.com/leejet/stable-diffusion.cpp/releases/download/' in script
    assert 'Z_IMAGE_MODEL_URL="${Z_IMAGE_MODEL_URL:-${HF_BASE_URL}/unsloth/Z-Image-Turbo-GGUF/resolve/main/z-image-turbo-Q2_K.gguf?download=true}"' in script
    assert 'QWEN_LLM_URL="${QWEN_LLM_URL:-${HF_BASE_URL}/unsloth/Qwen3-4B-Instruct-2507-GGUF/resolve/main/Qwen3-4B-Instruct-2507-Q4_K_M.gguf?download=true}"' in script
    assert 'VAE_URL="${VAE_URL:-${HF_BASE_URL}/receptektas/black-forest-labs-ae_safetensors/resolve/main/ae.safetensors}"' in script
    assert 'docker exec -u 0 "${CONTAINER_NAME}"' in script
    assert "libstable-diffusion.so" in script
    assert "LD_LIBRARY_PATH" in script


def test_z_image_provision_script_dry_run_short_circuits_after_permission_fix_plan() -> None:
    script = Path("scripts/provision_z_image_backend.sh").read_text(encoding="utf-8")

    assert 'if [[ "${DRY_RUN}" == "1" ]]; then' in script
    assert 'return 0' in script
