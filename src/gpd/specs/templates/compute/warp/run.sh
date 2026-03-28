#!/usr/bin/env bash
set -euo pipefail

IMAGE="${PROJECT_NAME:-warp-sim}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUTPUT_DIR="${SCRIPT_DIR}/output"
mkdir -p "${OUTPUT_DIR}"

DOCKERFILE="Dockerfile.cpu"
GPU_FLAG=""
if command -v nvidia-smi &>/dev/null && nvidia-smi &>/dev/null; then
    GPU_FLAG="--gpus all"
    DOCKERFILE="Dockerfile.gpu"
fi

docker build -t "${IMAGE}" -f "${SCRIPT_DIR}/${DOCKERFILE}" "${SCRIPT_DIR}"
docker run --rm ${GPU_FLAG} -v "${OUTPUT_DIR}:/app/output" "${IMAGE}"
