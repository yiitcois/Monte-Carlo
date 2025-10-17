"""Command line interface for the Monte Carlo scheduling simulator."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

from .config import load_config
from .simulation import MonteCarloSimulator
from .io import load_calendar, load_risks, load_tasks


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Monte Carlo simulations for project schedules.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser(
        "run", help="Execute a simulation run based on a configuration file."
    )
    run_parser.add_argument(
        "--config",
        type=Path,
        required=True,
        help="Path to the YAML configuration file.",
    )
    run_parser.add_argument(
        "--output",
        type=Path,
        help="Optional path to store the simulation summary as JSON.",
    )

    return parser


def run_cli(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "run":
        config = load_config(args.config)
        tasks = load_tasks(config["tasks"])  # type: ignore[arg-type]
        risks = load_risks(config.get("risks"))
        calendar = load_calendar(config.get("calendar"))

        simulator = MonteCarloSimulator(
            tasks=tasks,
            risks=risks,
            calendar=calendar,
            iterations=int(config.get("iterations", 5000)),
            confidence_levels=config.get("confidence_levels", [0.5, 0.75, 0.9]),
            random_seed=config.get("random_seed"),
        )

        summary = simulator.run()
        _print_summary(summary)

        if args.output:
            args.output.write_text(json.dumps(summary, indent=2))

    return 0


def _print_summary(summary: Dict[str, Any]) -> None:
    print("Simulation complete")
    print("------------------")
    print(f"Iterations: {summary['iterations']}")
    print(f"Mean project duration: {summary['statistics']['mean']:.2f} days")
    print(f"Median project duration: {summary['statistics']['median']:.2f} days")
    for level, value in summary["statistics"]["percentiles"].items():
        print(f"P{int(float(level) * 100):>3}: {value:.2f} days")
    if summary["critical_path"]:
        print("Critical path (most frequent):")
        print(" -> ".join(summary["critical_path"]))


__all__ = ["run_cli"]
