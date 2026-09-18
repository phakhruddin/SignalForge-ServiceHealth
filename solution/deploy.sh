#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
infra_dir="$script_dir/infra"
config_file=/workspace/config/config.json
manifest_file="$script_dir/manifest.json"

for command_name in terraform jq curl; do
  command -v "$command_name" >/dev/null || { echo "missing $command_name" >&2; exit 2; }
done
test -r "$config_file" || { echo "missing runtime configuration" >&2; exit 2; }
jq -e 'type == "object" and (.resource_prefix | type == "string") and
  (.region | type == "string") and (.aws_endpoint_url | type == "string") and
  (.metric_namespace | type == "string") and (.api_image | type == "string") and
  (.worker_image | type == "string") and (.canary_image | type == "string")' "$config_file" >/dev/null
: "${AWS_ACCESS_KEY_ID:?}"
: "${AWS_SECRET_ACCESS_KEY:?}"

umask 077
tfvars_tmp="$(mktemp "$infra_dir/config.auto.tfvars.json.tmp.XXXXXX")"
trap 'rm -f -- "$tfvars_tmp"' EXIT
jq --arg key "$AWS_ACCESS_KEY_ID" --arg secret "$AWS_SECRET_ACCESS_KEY" '{
  prefix: .resource_prefix, region: .region, endpoint: .aws_endpoint_url,
  metric_namespace, api_image, worker_image, canary_image,
  aws_access_key_id: $key, aws_secret_access_key: $secret
}' "$config_file" > "$tfvars_tmp"
mv "$tfvars_tmp" "$infra_dir/config.auto.tfvars.json"
trap - EXIT

export TF_IN_AUTOMATION=1 TF_INPUT=0
unset TF_PLUGIN_CACHE_DIR
terraform -chdir="$infra_dir" init -input=false -no-color
terraform -chdir="$infra_dir" apply -input=false -auto-approve -lock-timeout=60s -no-color

manifest_tmp="$(mktemp "$manifest_file.tmp.XXXXXX")"
trap 'rm -f -- "$manifest_tmp"' EXIT
terraform -chdir="$infra_dir" output -json manifest | jq -e '.' > "$manifest_tmp"
mv "$manifest_tmp" "$manifest_file"
chmod 0644 "$manifest_file"
trap - EXIT

api_url="$(jq -er '.api_url' "$manifest_file")"
deadline=$((SECONDS + 180))
until curl --silent --show-error --fail --max-time 3 "$api_url/health/ready" >/dev/null 2>&1; do
  if (( SECONDS >= deadline )); then
    echo "API did not become ready: $api_url" >&2
    exit 1
  fi
  sleep 2
done
printf 'SignalForge is ready: %s\n' "$api_url"
