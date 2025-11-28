#!/bin/bash
# Wrapper script to run the Agentic CI Orchestrator

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Activate virtual environment
source "$SCRIPT_DIR/venv/bin/activate"

# Set PYTHONPATH
export PYTHONPATH="$SCRIPT_DIR"

# Run the main script with all arguments
python3 "$SCRIPT_DIR/src/main.py" "$@"
