#!/bin/bash

set -e

source .venv/bin/activate

export $(grep -v '^#' .env | xargs)

python agent_local.py