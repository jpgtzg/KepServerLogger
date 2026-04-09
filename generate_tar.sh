#!/bin/sh
set -e

DOCKERFILE_PATH="$1"
IMAGE_NAME="$2"

if [ -z "$DOCKERFILE_PATH" ] || [ -z "$IMAGE_NAME" ]; then
    echo "Usage: $0 <Dockerfile_path> <image_name>"
    exit 1
fi

docker build -f $DOCKERFILE_PATH -t $IMAGE_NAME . 2>&1 | tail -5
docker save $IMAGE_NAME | gzip > $IMAGE_NAME.tar.gz && echo "done"
