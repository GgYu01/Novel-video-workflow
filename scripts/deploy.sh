#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-${ROOT_DIR}/docker-compose.yml}"
PROJECT_NAME="${PROJECT_NAME:-av-workflow}"
DRY_RUN="${DRY_RUN:-1}"
SKIP_DOCKER_CHECK="${SKIP_DOCKER_CHECK:-0}"

if [[ "${SKIP_DOCKER_CHECK}" != "1" ]]; then
  command -v docker >/dev/null 2>&1 || {
    echo "docker not found" >&2
    exit 1
  }
  docker compose -f "${COMPOSE_FILE}" config -q
fi

if [[ "${DRY_RUN}" == "1" ]]; then
  echo "validated compose file for project ${PROJECT_NAME}"
  echo "set DRY_RUN=0 to run docker compose up -d"
  exit 0
fi

docker compose -p "${PROJECT_NAME}" -f "${COMPOSE_FILE}" up -d
echo "deployment started for ${PROJECT_NAME}"
