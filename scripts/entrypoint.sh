#!/bin/bash
EXTRA_ARGS=""
if ! command -v nvidia-smi &>/dev/null || ! nvidia-smi &>/dev/null; then
  EXTRA_ARGS="--cpu"
fi
exec python3 main.py --listen 0.0.0.0 --port 8188 $EXTRA_ARGS "$@"
