#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd -P)"

DRY_RUN="${DRY_RUN:-1}"
FORCE_DOWNLOAD="${FORCE_DOWNLOAD:-0}"
UPDATE_ENV="${UPDATE_ENV:-1}"
ENV_FILE="${ENV_FILE:-${REPO_ROOT}/.env}"
CONTAINER_NAME="${CONTAINER_NAME:-av-workflow-av-image-renderer-1}"
IMAGE_NAME="${IMAGE_NAME:-av-workflow-renderer:${AV_WORKFLOW_IMAGE_TAG:-latest}}"
HF_BASE_URL="${HF_BASE_URL:-https://hf-mirror.com}"
SD_CPP_RELEASE_URL="${SD_CPP_RELEASE_URL:-https://github.com/leejet/stable-diffusion.cpp/releases/download/master-552-87ecb95/sd-master-87ecb95-bin-Linux-Ubuntu-24.04-x86_64.zip}"
Z_IMAGE_MODEL_URL="${Z_IMAGE_MODEL_URL:-${HF_BASE_URL}/unsloth/Z-Image-Turbo-GGUF/resolve/main/z-image-turbo-Q2_K.gguf?download=true}"
QWEN_LLM_URL="${QWEN_LLM_URL:-${HF_BASE_URL}/unsloth/Qwen3-4B-Instruct-2507-GGUF/resolve/main/Qwen3-4B-Instruct-2507-Q4_K_M.gguf?download=true}"
VAE_URL="${VAE_URL:-${HF_BASE_URL}/receptektas/black-forest-labs-ae_safetensors/resolve/main/ae.safetensors}"

HOST_UID="$(id -u)"
HOST_GID="$(id -g)"

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

resolve_models_root() {
  local configured_root="${AV_WORKFLOW_MODELS_ROOT:-./models}"
  if [[ "${configured_root}" = /* ]]; then
    printf '%s\n' "${configured_root}"
  else
    printf '%s\n' "${REPO_ROOT}/${configured_root#./}"
  fi
}

MODELS_ROOT="$(resolve_models_root)"
CACHE_DIR="${MODELS_ROOT}/cache"
BIN_DIR="${MODELS_ROOT}/bin"
Z_IMAGE_DIR="${MODELS_ROOT}/z-image"
QWEN_DIR="${MODELS_ROOT}/qwen3"

SD_CPP_ARCHIVE_PATH="${CACHE_DIR}/$(basename "${SD_CPP_RELEASE_URL%%\?*}")"
SD_CPP_BIN_PATH="${BIN_DIR}/sd-cli"
SD_CPP_REAL_BIN_PATH="${BIN_DIR}/sd-cli.bin"
SD_CPP_PRIMARY_LIB_NAME="libstable-diffusion.so"
Z_IMAGE_MODEL_PATH="${Z_IMAGE_DIR}/Z-Image-Turbo-Q2_K.gguf"
VAE_PATH="${Z_IMAGE_DIR}/ae.safetensors"
QWEN_LLM_PATH="${QWEN_DIR}/Qwen3-4B-Instruct-2507-Q4_K_M.gguf"

run() {
  if [[ "${DRY_RUN}" == "1" ]]; then
    log "dry-run cmd=$*"
    return 0
  fi
  "$@"
}

ensure_models_dir_writable() {
  mkdir -p "${REPO_ROOT}" || true
  if mkdir -p "${MODELS_ROOT}" "${CACHE_DIR}" "${BIN_DIR}" "${Z_IMAGE_DIR}" "${QWEN_DIR}" 2>/dev/null \
    && touch "${MODELS_ROOT}/.perm_test" 2>/dev/null; then
    rm -f "${MODELS_ROOT}/.perm_test"
    return 0
  fi

  require_tool docker

  local helper_cmd="mkdir -p /models/cache /models/bin /models/z-image /models/qwen3 && chown -R ${HOST_UID}:${HOST_GID} /models"
  if docker ps --format '{{.Names}}' | grep -qx "${CONTAINER_NAME}"; then
    run docker exec -u 0 "${CONTAINER_NAME}" sh -lc "${helper_cmd}"
  elif docker image inspect "${IMAGE_NAME}" >/dev/null 2>&1; then
    run docker run --rm -u 0 -v "${MODELS_ROOT}:/models" --entrypoint sh "${IMAGE_NAME}" -lc "${helper_cmd}"
  else
    log "models-dir-not-writable and no helper container/image available"
    log "checked container=${CONTAINER_NAME} image=${IMAGE_NAME}"
    exit 1
  fi

  if [[ "${DRY_RUN}" == "1" ]]; then
    return 0
  fi

  mkdir -p "${MODELS_ROOT}" "${CACHE_DIR}" "${BIN_DIR}" "${Z_IMAGE_DIR}" "${QWEN_DIR}"
  touch "${MODELS_ROOT}/.perm_test"
  rm -f "${MODELS_ROOT}/.perm_test"
}

download_with_resume() {
  local url="$1"
  local destination="$2"

  if [[ -s "${destination}" && "${FORCE_DOWNLOAD}" != "1" ]]; then
    log "download-skip exists=${destination}"
    return 0
  fi

  run wget -c -O "${destination}" "${url}"

  if [[ "${DRY_RUN}" != "1" && ! -s "${destination}" ]]; then
    log "download-empty path=${destination}"
    exit 1
  fi
}

extract_sd_cpp_binary() {
  local extract_dir="${CACHE_DIR}/sd_cpp_extract"
  local runtime_lib_count
  local primary_lib_path

  if [[ "${DRY_RUN}" == "1" ]]; then
    log "dry-run extract archive=${SD_CPP_ARCHIVE_PATH} to=${SD_CPP_BIN_PATH} and runtime libs under ${BIN_DIR}"
    return 0
  fi

  rm -rf "${extract_dir}"
  mkdir -p "${extract_dir}"

  python3 - "${SD_CPP_ARCHIVE_PATH}" "${extract_dir}" <<'PY'
import sys
import zipfile
archive, dest = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(archive) as zf:
    zf.extractall(dest)
PY

  local candidate
  candidate="$(find "${extract_dir}" -type f \( -name 'sd-cli' -o -name 'sd' \) | sort | head -1)"
  if [[ -z "${candidate}" ]]; then
    log "sd-cpp-binary-not-found archive=${SD_CPP_ARCHIVE_PATH}"
    exit 1
  fi

  runtime_lib_count="$(find "${extract_dir}" -type f -name '*.so*' | wc -l | tr -d '[:space:]')"
  if [[ "${runtime_lib_count}" == "0" ]]; then
    log "sd-cpp-runtime-lib-not-found archive=${SD_CPP_ARCHIVE_PATH}"
    exit 1
  fi
  primary_lib_path="$(find "${extract_dir}" -type f -name "${SD_CPP_PRIMARY_LIB_NAME}" | sort | head -1)"
  if [[ -z "${primary_lib_path}" ]]; then
    log "sd-cpp-primary-runtime-lib-not-found archive=${SD_CPP_ARCHIVE_PATH} library=${SD_CPP_PRIMARY_LIB_NAME}"
    exit 1
  fi

  install -m 0755 "${candidate}" "${SD_CPP_REAL_BIN_PATH}"
  while IFS= read -r runtime_lib; do
    install -m 0644 "${runtime_lib}" "${BIN_DIR}/$(basename "${runtime_lib}")"
  done < <(find "${extract_dir}" -type f -name '*.so*' | sort)

  cat > "${SD_CPP_BIN_PATH}" <<'EOF'
#!/usr/bin/env sh
set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)"
export LD_LIBRARY_PATH="${SCRIPT_DIR}${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"
exec "${SCRIPT_DIR}/sd-cli.bin" "$@"
EOF
  chmod 0755 "${SD_CPP_BIN_PATH}"
}

set_env_var() {
  local name="$1"
  local value="$2"

  if [[ "${DRY_RUN}" == "1" ]]; then
    log "dry-run env-set file=${ENV_FILE} key=${name} value=${value}"
    return 0
  fi

  mkdir -p "$(dirname -- "${ENV_FILE}")"
  touch "${ENV_FILE}"
  python3 - "${ENV_FILE}" "${name}" "${value}" <<'PY'
import pathlib
import sys

env_file = pathlib.Path(sys.argv[1])
key = sys.argv[2]
value = sys.argv[3]
lines = env_file.read_text(encoding="utf-8").splitlines()
prefix = f"{key}="
updated = False
result = []
for line in lines:
    if line.startswith(prefix):
        result.append(f"{key}={value}")
        updated = True
    else:
        result.append(line)
if not updated:
    result.append(f"{key}={value}")
env_file.write_text("\n".join(result).rstrip() + "\n", encoding="utf-8")
PY
}

update_env_file() {
  if [[ "${UPDATE_ENV}" != "1" ]]; then
    log "env-update-skip file=${ENV_FILE}"
    return 0
  fi

  set_env_var "AV_WORKFLOW_IMAGE_BACKEND_KIND" "sd_cpp"
  set_env_var "AV_WORKFLOW_SD_CPP_BIN" "/models/bin/sd-cli"
  set_env_var "AV_WORKFLOW_Z_IMAGE_DIFFUSION_MODEL_PATH" "/models/z-image/Z-Image-Turbo-Q2_K.gguf"
  set_env_var "AV_WORKFLOW_Z_IMAGE_VAE_PATH" "/models/z-image/ae.safetensors"
  set_env_var "AV_WORKFLOW_Z_IMAGE_LLM_PATH" "/models/qwen3/Qwen3-4B-Instruct-2507-Q4_K_M.gguf"
}

main() {
  require_tool python3
  require_tool wget

  ensure_models_dir_writable
  download_with_resume "${SD_CPP_RELEASE_URL}" "${SD_CPP_ARCHIVE_PATH}"
  extract_sd_cpp_binary
  download_with_resume "${Z_IMAGE_MODEL_URL}" "${Z_IMAGE_MODEL_PATH}"
  download_with_resume "${VAE_URL}" "${VAE_PATH}"
  download_with_resume "${QWEN_LLM_URL}" "${QWEN_LLM_PATH}"
  update_env_file

  log "z-image-backend-provisioned models_root=${MODELS_ROOT} env_file=${ENV_FILE} dry_run=${DRY_RUN}"
  log "recommended-next-step: docker compose up -d --build av-image-renderer"
}

main "$@"
