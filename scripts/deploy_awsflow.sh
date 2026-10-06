#!/usr/bin/env bash
# Compatibility entrypoint: local packaging only under the $0 out-of-pocket policy.
set -euo pipefail

if [[ "$#" -ne 0 ]]; then
  echo "Cloud deployment options are disabled. This script only builds local files."
  exit 2
fi
python3 infra/build_awsflow.py
echo "Local template and Lambda ZIP built. No AWS calls or cloud resources created."
