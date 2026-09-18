#!/bin/sh
set -eu
app_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
for role in api worker canary; do
  docker buildx build --load --provenance=false --target "$role" -t "signalforge/$role:1.0.0" "$app_dir"
done
