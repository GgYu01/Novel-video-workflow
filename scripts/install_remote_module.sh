#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd -P)"

REMOTE_HOST="${REMOTE_HOST:-112.28.134.53}"
REMOTE_USER="${REMOTE_USER:-gaoyx}"
REMOTE_PORT="${REMOTE_PORT:-52117}"
REMOTE_PASSWORD="${REMOTE_PASSWORD:-}"
REMOTE_ROOT="${REMOTE_ROOT:-/mnt/hdo/infra-core}"
REMOTE_MODULE_PATH="${REMOTE_MODULE_PATH:-${REMOTE_ROOT}/modules/av-workflow}"
REMOTE_REGISTRY_FILE="${REMOTE_REGISTRY_FILE:-${REMOTE_ROOT}/modules/registry.list}"
REGISTRY_LINE="av-workflow|${REMOTE_MODULE_PATH}|docker-compose.yml|Internal single-tenant automated novel-to-video workflow"
DRY_RUN="${DRY_RUN:-1}"
SYNC_DELETE="${SYNC_DELETE:-0}"

log() {
  printf '[%s] %s\n' "$(date '+%F %T')" "$*"
}

require_tool() {
  local tool_name="$1"
  command -v "${tool_name}" >/dev/null 2>&1 || {
    log "missing-tool name=${tool_name}"
    exit 1
  }
}

run_remote() {
  local remote_cmd="$1"
  if [[ "${DRY_RUN}" == "1" ]]; then
    log "dry-run remote=${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PORT} cmd=${remote_cmd}"
    return 0
  fi

  : "${REMOTE_PASSWORD:?REMOTE_PASSWORD is required when DRY_RUN=0}"

  sshpass -p "${REMOTE_PASSWORD}" ssh \
    -o StrictHostKeyChecking=no \
    -o ConnectTimeout=8 \
    -p "${REMOTE_PORT}" \
    "${REMOTE_USER}@${REMOTE_HOST}" \
    "${remote_cmd}"
}

run_rsync() {
  local -a delete_flags=()
  local ssh_transport="ssh -o StrictHostKeyChecking=no -o ConnectTimeout=8 -p ${REMOTE_PORT}"
  if [[ "${SYNC_DELETE}" == "1" ]]; then
    delete_flags=(--delete)
  fi

  local -a cmd=(
    rsync -az
    -e "${ssh_transport}"
    "${delete_flags[@]}"
    --exclude=.git
    --exclude=.venv
    --exclude=/runtime/
    --exclude=/models/
    --exclude=.env
    --exclude=.env.secrets
    --exclude=__pycache__
    --exclude=.pytest_cache
    --exclude=.mypy_cache
    --exclude=*.log
    --exclude=*.tmp
    "${REPO_ROOT}/"
    "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_MODULE_PATH}/"
  )

  if [[ "${DRY_RUN}" == "1" ]]; then
    log "dry-run rsync=${cmd[*]}"
    return 0
  fi

  : "${REMOTE_PASSWORD:?REMOTE_PASSWORD is required when DRY_RUN=0}"

  sshpass -p "${REMOTE_PASSWORD}" "${cmd[@]}"
}

main() {
  require_tool rsync
  require_tool ssh
  require_tool sshpass

  run_remote "mkdir -p '${REMOTE_MODULE_PATH}' '${REMOTE_MODULE_PATH}/runtime'"
  run_rsync
  run_remote "[ -f '${REMOTE_MODULE_PATH}/.env' ] || cp '${REMOTE_MODULE_PATH}/.env.example' '${REMOTE_MODULE_PATH}/.env'"
  run_remote "[ -f '${REMOTE_MODULE_PATH}/.env.secrets' ] || cp '${REMOTE_MODULE_PATH}/.env.secrets.example' '${REMOTE_MODULE_PATH}/.env.secrets'"
  run_remote "grep -qxF '${REGISTRY_LINE}' '${REMOTE_REGISTRY_FILE}' || printf '%s\n' '${REGISTRY_LINE}' >> '${REMOTE_REGISTRY_FILE}'"
  run_remote "cd '${REMOTE_ROOT}' && scripts/modulectl.sh config av-workflow"
  log "remote-module-sync-finished path=${REMOTE_MODULE_PATH} dry_run=${DRY_RUN}"
}

main "$@"
