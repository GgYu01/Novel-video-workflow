#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-${ROOT_DIR}/docker-compose.yml}"
SKIP_DOCKER_CHECK="${SKIP_DOCKER_CHECK:-0}"

command -v python3 >/dev/null 2>&1 || {
  echo "python3 not found" >&2
  exit 1
}

python3 -m compileall "${ROOT_DIR}/src" "${ROOT_DIR}/tests" >/dev/null

if [[ "${SKIP_DOCKER_CHECK}" == "1" ]]; then
  echo "skipping docker compose validation"
  echo "doctor checks passed"
  exit 0
fi

command -v docker >/dev/null 2>&1 || {
  echo "docker not found" >&2
  exit 1
}

docker compose -f "${COMPOSE_FILE}" config -q

echo "doctor checks passed"
