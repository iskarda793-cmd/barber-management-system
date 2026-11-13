#!/usr/bin/env bash
# Option 1 (Azure): build the image locally for linux/amd64 and push it to ACR.
# Usage: ./scripts/push-to-acr.sh <registry-name>      e.g. ./scripts/push-to-acr.sh barberacrarda
# You will be asked for the ACR admin username/password (Portal > ACR > Access keys).
set -euo pipefail

REGISTRY_NAME="${1:?Usage: $0 <acr-registry-name>}"
LOGIN_SERVER="${REGISTRY_NAME}.azurecr.io"
IMAGE="barber-app"
TAG="${2:-v1}"

cd "$(dirname "$0")/.."

echo ">> Logging in to ${LOGIN_SERVER}"
docker login "${LOGIN_SERVER}"

echo ">> Building ${IMAGE}:${TAG} for linux/amd64"
docker build --platform linux/amd64 -t "${IMAGE}:${TAG}" .

echo ">> Tagging"
docker tag "${IMAGE}:${TAG}" "${LOGIN_SERVER}/${IMAGE}:${TAG}"
docker tag "${IMAGE}:${TAG}" "${LOGIN_SERVER}/${IMAGE}:latest"

echo ">> Pushing"
docker push "${LOGIN_SERVER}/${IMAGE}:${TAG}"
docker push "${LOGIN_SERVER}/${IMAGE}:latest"

echo ">> Done: ${LOGIN_SERVER}/${IMAGE}:${TAG}"
