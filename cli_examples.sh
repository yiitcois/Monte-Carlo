#!/usr/bin/env bash
# Example commands for running the Monte Carlo simulator.
set -euo pipefail

python -m montecarlo run --config examples/config.yaml
python -m montecarlo run --config examples/config.yaml --output simulation_summary.json
