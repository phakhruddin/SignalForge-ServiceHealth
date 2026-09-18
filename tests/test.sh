#!/usr/bin/env bash
set -Eeuo pipefail
mkdir -p /logs/verifier
write_fallback_reward() {
  if [[ ! -s /logs/verifier/reward.json ]]; then
    printf '{"score":0,"reward":0}\n' > /logs/verifier/reward.json
    printf '0\n' > /logs/verifier/reward.txt
  fi
}
trap write_fallback_reward EXIT
python3 /tests/verify.py
