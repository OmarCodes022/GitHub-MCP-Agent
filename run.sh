#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

source "$SCRIPT_DIR/.venv/bin/activate"

export $(grep -v '^#' "$SCRIPT_DIR/.env" | xargs)

python "$SCRIPT_DIR/agent_local.py"