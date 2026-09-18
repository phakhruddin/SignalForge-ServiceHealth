#!/usr/bin/env bash
set -Eeuo pipefail
source_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
destination=/workspace/submission
mkdir -p "$destination/infra"
cp "$source_dir/deploy.sh" "$source_dir/destroy.sh" "$destination/"
find "$source_dir/infra" -maxdepth 1 -type f \( -name '*.tf' -o -name '.terraform.lock.hcl' \) -exec cp '{}' "$destination/infra/" \;
chmod +x "$destination/deploy.sh" "$destination/destroy.sh"
"$destination/deploy.sh"
