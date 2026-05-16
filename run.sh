#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

uv run --project "$SCRIPT_DIR" python -m github_mcp_agent.cli
