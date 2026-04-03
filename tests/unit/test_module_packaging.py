from __future__ import annotations

import os
from pathlib import Path

import yaml


def test_module_packaging_files_exist() -> None:
    remote_install_script = Path("scripts/install_remote_module.sh")

    assert Path(".env.example").is_file()
    assert Path(".env.secrets.example").is_file()
    assert Path("build/Dockerfile.api").is_file()
    assert remote_install_script.is_file()
    assert os.access(remote_install_script, os.X_OK)


def test_root_compose_is_ready_for_infra_core_module_use() -> None:
    compose = yaml.safe_load(Path("docker-compose.yml").read_text(encoding="utf-8"))

    av_api = compose["services"]["av-api"]

    assert av_api["build"]["dockerfile"] == "./build/Dockerfile.api"
    assert av_api["build"]["args"]["PYTHON_BASE_IMAGE"] == "${AV_WORKFLOW_PYTHON_BASE_IMAGE:-python:3.12-slim}"
    assert "./.env" in av_api["env_file"]
    assert "./.env.secrets" in av_api["env_file"]
    assert "infra_gateway_net" in av_api["networks"]
    assert compose["networks"]["infra_gateway_net"]["external"] is True
    assert av_api["healthcheck"]["test"][0] == "CMD-SHELL"
    assert "AV_WORKFLOW_API_PORT" in av_api["healthcheck"]["test"][1]


def test_remote_install_script_defaults_to_dry_run() -> None:
    script = Path("scripts/install_remote_module.sh").read_text(encoding="utf-8")

    assert 'DRY_RUN="${DRY_RUN:-1}"' in script
    assert 'REMOTE_ROOT="${REMOTE_ROOT:-/mnt/hdo/infra-core}"' in script
    assert 'REMOTE_MODULE_PATH="${REMOTE_MODULE_PATH:-${REMOTE_ROOT}/modules/av-workflow}"' in script
    assert "modules/registry.list" in script
    assert 'ssh -o StrictHostKeyChecking=no -o ConnectTimeout=8 -p ${REMOTE_PORT}' in script


def test_api_image_runtime_uses_layered_host_and_port_defaults() -> None:
    dockerfile = Path("build/Dockerfile.api").read_text(encoding="utf-8")
    env_example = Path(".env.example").read_text(encoding="utf-8")

    assert "AV_WORKFLOW_API_HOST" in dockerfile
    assert "AV_WORKFLOW_API_PORT" in dockerfile
    assert "ARG PYTHON_BASE_IMAGE=python:3.12-slim" in dockerfile
    assert "FROM ${PYTHON_BASE_IMAGE}" in dockerfile
    assert "AV_WORKFLOW_PYTHON_BASE_IMAGE=python:3.12-slim" in env_example
