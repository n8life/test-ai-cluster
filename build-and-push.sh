#!/usr/bin/env bash
set -euo pipefail

DOCKERFILE="${1:-Dockerfile}"
TAG="${2:-latest}"

# Derive image name from the Dockerfile name
case "${DOCKERFILE}" in
    Dockerfile)           IMAGE="nsmith2100/langchain-langfuse-test" ;;
    Dockerfile.dependabot) IMAGE="nsmith2100/dependabot-fix-agent"   ;;
    *)                     IMAGE="nsmith2100/${DOCKERFILE##*.}"      ;;
esac

echo "Building ${IMAGE}:${TAG} (from ${DOCKERFILE}) ..."
docker build -f "${DOCKERFILE}" -t "${IMAGE}:${TAG}" .

echo "Pushing ${IMAGE}:${TAG} ..."
docker push "${IMAGE}:${TAG}"

echo "Done — ${IMAGE}:${TAG} pushed to Docker Hub."
