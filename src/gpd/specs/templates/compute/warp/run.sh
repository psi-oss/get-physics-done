#!/usr/bin/env bash
set -euo pipefail

IMAGE="${PROJECT_NAME:-warp-sim}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUTPUT_DIR="${SCRIPT_DIR}/output"

mkdir -p "${OUTPUT_DIR}"

# Select Dockerfile: GPU if nvidia-smi is available, CPU otherwise
DOCKER_GPU_FLAG=""
DOCKERFILE="Dockerfile.cpu"
if command -v nvidia-smi &>/dev/null && nvidia-smi &>/dev/null; then
    DOCKER_GPU_FLAG="--gpus all"
    DOCKERFILE="Dockerfile.gpu"
    echo "GPU detected — using ${DOCKERFILE} with CUDA acceleration"
else
    echo "No GPU detected — using ${DOCKERFILE} (CPU only)"
fi

echo "Building ${IMAGE}..."
docker build -t "${IMAGE}" -f "${SCRIPT_DIR}/${DOCKERFILE}" "${SCRIPT_DIR}"

echo "Running ${IMAGE}..."
docker run --rm \
    ${DOCKER_GPU_FLAG} \
    -v "${OUTPUT_DIR}:/app/output" \
    -e OUTPUT_DIR=/app/output \
    -e WARP_DEVICE="${WARP_DEVICE:-cpu}" \
    "${@}" \
    "${IMAGE}"

echo ""
echo "Outputs: ${OUTPUT_DIR}/"
