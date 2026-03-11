#!/bin/bash
set -e

docker build -t opcualogger .

docker save opcualogger:latest -o opcualogger.tar
echo "Tar file generated successfully!"