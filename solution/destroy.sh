#!/usr/bin/env bash
set -Eeuo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
infra_dir="$script_dir/infra"
test -f "$infra_dir/terraform.tfstate" || { echo "No local state; nothing to destroy"; exit 0; }
export TF_IN_AUTOMATION=1 TF_INPUT=0
unset TF_PLUGIN_CACHE_DIR
terraform -chdir="$infra_dir" init -input=false -no-color
terraform -chdir="$infra_dir" destroy -input=false -auto-approve -lock-timeout=60s -no-color
printf 'SignalForge resources destroyed.\n'
