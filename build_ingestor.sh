#!/bin/sh
set -e

TIMESCALE_IMAGE="timescale/timescaledb:latest-pg16"
BUILD_TIMESCALE=0

# Parse optional --timescale flag
if [ "$1" = "--timescale" ]; then
    BUILD_TIMESCALE=1
    shift
fi

DOCKERFILE_PATH="$1"
IMAGE_NAME="$2"

if [ "$BUILD_TIMESCALE" = "0" ] && { [ -z "$DOCKERFILE_PATH" ] || [ -z "$IMAGE_NAME" ]; }; then
    echo "Usage: $0 [--timescale] [<Dockerfile_path> <image_name>]"
    exit 1
fi

if [ "$BUILD_TIMESCALE" = "1" ]; then
    docker pull "$TIMESCALE_IMAGE"
    docker save "$TIMESCALE_IMAGE" | gzip > timescaledb.tar.gz && echo "timescaledb done at $(date +"%H:%M:%S")"
fi

if [ -n "$DOCKERFILE_PATH" ] && [ -n "$IMAGE_NAME" ]; then
    docker build -f "$DOCKERFILE_PATH" -t "$IMAGE_NAME" . 2>&1 | tail -5
    docker save "$IMAGE_NAME" | gzip > "$IMAGE_NAME.tar.gz" && echo "done at $(date +"%H:%M:%S")"
fi
