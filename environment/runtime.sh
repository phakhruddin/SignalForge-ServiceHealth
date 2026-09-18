#!/bin/sh
set -eu
application_dir="${APPLICATION_DIR:-/application}"
config_dir="${CONFIG_DIR:-/config}"
mkdir -p "$config_dir"
/bin/sh "$application_dir/build.sh"
prefix="sf-$(od -An -N6 -tx1 /dev/urandom | tr -d ' \n')"
config_tmp="$config_dir/config.json.tmp"
cat > "$config_tmp" <<EOF
{
  "resource_prefix": "$prefix",
  "region": "us-east-1",
  "aws_endpoint_url": "http://aws:4566",
  "metric_namespace": "SignalForge/ServiceHealth",
  "api_image": "signalforge/api:1.0.0",
  "worker_image": "signalforge/worker:1.0.0",
  "canary_image": "signalforge/canary:1.0.0",
  "api_image_id": "$(docker image inspect --format '{{.Id}}' signalforge/api:1.0.0)",
  "worker_image_id": "$(docker image inspect --format '{{.Id}}' signalforge/worker:1.0.0)",
  "canary_image_id": "$(docker image inspect --format '{{.Id}}' signalforge/canary:1.0.0)"
}
EOF
chmod 0444 "$config_tmp"
mv "$config_tmp" "$config_dir/config.json"
