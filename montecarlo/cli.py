"""Command line interface for the Monte Carlo scheduling simulator."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Sequence

from .config import load_config
from .simulation import MonteCarloSimulator, SimulationError
from .io import Risk, Task, load_calendar, load_risks, load_tasks


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

    subparsers.add_parser(
        "interactive",
        help="Launch an interactive prompt to enter schedule data manually.",
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
    elif args.command == "interactive":
        _run_interactive()

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


def _run_interactive() -> None:
    print("Interactive Monte Carlo simulation")
    print("Enter your task information. Leave the task id blank to finish.")
    print()

    tasks = _prompt_tasks(input)
    if not tasks:
        print("No tasks entered. Exiting without running the simulation.")
        return

    risks: List[Risk] = []
    if _prompt_yes_no("Do you want to add risk events?", input, default=False):
        risks = _prompt_risks(input, tasks)

    iterations = _prompt_int("Number of iterations", input, default=5000, minimum=1)
    confidence_levels = _prompt_confidence_levels(
        "Confidence levels (comma separated between 0 and 1)",
        input,
        default=(0.5, 0.75, 0.9),
    )
    random_seed = _prompt_optional_int("Random seed (optional)", input)

    try:
        simulator = MonteCarloSimulator(
            tasks=tasks,
            risks=risks,
            calendar=None,
            iterations=iterations,
            confidence_levels=confidence_levels,
            random_seed=random_seed,
        )
        summary = simulator.run()
    except SimulationError as exc:
        print(f"Cannot run simulation: {exc}")
        return

    print()
    _print_summary(summary)


def _prompt_tasks(reader: Callable[[str], str]) -> List[Task]:
    tasks: List[Task] = []
    while True:
        task_id = reader("Task id: ").strip()
        if not task_id:
            break

        if any(task.task_id == task_id for task in tasks):
            print(f"Task id '{task_id}' already exists. Please enter a different id.")
            continue

        name = reader("Task name (optional): ").strip() or task_id
        optimistic = _prompt_float("  Optimistic duration (days)", reader, minimum=0.0)
        most_likely = _prompt_float("  Most likely duration (days)", reader, minimum=0.0)
        pessimistic = _prompt_float("  Pessimistic duration (days)", reader, minimum=0.0)

        if not _is_valid_triangle(optimistic, most_likely, pessimistic):
            print("  Durations must satisfy optimistic <= most likely <= pessimistic. Please re-enter the task.")
            continue

        predecessors = _prompt_predecessors(reader, tasks)
        tasks.append(
            Task(
                task_id=task_id,
                name=name,
                optimistic=optimistic,
                most_likely=most_likely,
                pessimistic=pessimistic,
                predecessors=predecessors,
            )
        )
        print()
    return tasks


def _prompt_predecessors(reader: Callable[[str], str], tasks: Sequence[Task]) -> Sequence[str]:
    while True:
        raw = reader("  Predecessors (comma separated ids, leave blank if none): ").strip()
        if not raw:
            return ()
        entered = [value.strip() for value in raw.split(",") if value.strip()]
        unknown = [value for value in entered if value not in {task.task_id for task in tasks}]
        if unknown:
            print(f"  Unknown predecessor ids: {', '.join(unknown)}. Please enter existing task ids.")
            continue
        return tuple(entered)


def _prompt_risks(reader: Callable[[str], str], tasks: Sequence[Task]) -> List[Risk]:
    risks: List[Risk] = []
    task_ids = {task.task_id for task in tasks}
    print("Enter risk information. Leave the risk id blank to finish.")
    while True:
        risk_id = reader("Risk id: ").strip()
        if not risk_id:
            break
        if any(risk.risk_id == risk_id for risk in risks):
            print(f"Risk id '{risk_id}' already exists. Please enter a different id.")
            continue

        description = reader("  Description: ").strip() or risk_id
        probability = _prompt_float(
            "  Probability (0-1)",
            reader,
            minimum=0.0,
            maximum=1.0,
        )
        affected = _prompt_affected_tasks(reader, task_ids)
        impact_min = _prompt_float("  Impact min (e.g. 0.1 for +10%)", reader)
        impact_mode = _prompt_float("  Impact mode", reader)
        impact_max = _prompt_float("  Impact max", reader)

        if not _is_valid_triangle(impact_min, impact_mode, impact_max):
            print("  Impact values must satisfy min <= mode <= max. Please re-enter the risk.")
            continue

        risks.append(
            Risk(
                risk_id=risk_id,
                description=description,
                probability=probability,
                affected_tasks=affected,
                impact_min=impact_min,
                impact_mode=impact_mode,
                impact_max=impact_max,
            )
        )
        print()
    return risks


def _prompt_affected_tasks(reader: Callable[[str], str], task_ids: Iterable[str]) -> Sequence[str]:
    ids = set(task_ids)
    while True:
        raw = reader("  Affected task ids (comma separated): ").strip()
        entered = [value.strip() for value in raw.split(",") if value.strip()]
        if not entered:
            print("  At least one affected task is required.")
            continue
        unknown = [value for value in entered if value not in ids]
        if unknown:
            print(f"  Unknown task ids: {', '.join(unknown)}. Please enter ids defined earlier.")
            continue
        return tuple(entered)


def _prompt_float(
    prompt: str,
    reader: Callable[[str], str],
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    while True:
        raw = reader(f"{prompt}: ").strip()
        try:
            value = float(raw)
        except ValueError:
            print("  Please enter a numeric value.")
            continue
        if minimum is not None and value < minimum:
            print(f"  Value must be greater than or equal to {minimum}.")
            continue
        if maximum is not None and value > maximum:
            print(f"  Value must be less than or equal to {maximum}.")
            continue
        return value


def _prompt_int(
    prompt: str,
    reader: Callable[[str], str],
    *,
    default: int | None = None,
    minimum: int | None = None,
) -> int:
    suffix = f" [{default}]" if default is not None else ""
    while True:
        raw = reader(f"{prompt}{suffix}: ").strip()
        if not raw and default is not None:
            value = default
        else:
            try:
                value = int(raw)
            except ValueError:
                print("  Please enter an integer value.")
                continue
        if minimum is not None and value < minimum:
            print(f"  Value must be greater than or equal to {minimum}.")
            continue
        return value


def _prompt_optional_int(prompt: str, reader: Callable[[str], str]) -> int | None:
    raw = reader(f"{prompt}: ").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        print("  Invalid integer; ignoring value.")
        return None


def _prompt_confidence_levels(
    prompt: str,
    reader: Callable[[str], str],
    *,
    default: Sequence[float] = (0.5, 0.75, 0.9),
) -> Sequence[float]:
    default_display = ",".join(str(value) for value in default)
    while True:
        raw = reader(f"{prompt} [{default_display}]: ").strip()
        if not raw:
            return tuple(default)
        pieces = [part.strip() for part in raw.split(",") if part.strip()]
        try:
            values = [float(part) for part in pieces]
        except ValueError:
            print("  Please enter numeric values separated by commas.")
            continue
        if not values:
            print("  Please enter at least one confidence level.")
            continue
        if any(value < 0 or value > 1 for value in values):
            print("  Confidence levels must be between 0 and 1.")
            continue
        return tuple(sorted(set(values)))


def _prompt_yes_no(
    prompt: str,
    reader: Callable[[str], str],
    *,
    default: bool = False,
) -> bool:
    suffix = " [Y/n]" if default else " [y/N]"
    while True:
        raw = reader(f"{prompt}{suffix}: ").strip().lower()
        if not raw:
            return default
        if raw in {"y", "yes"}:
            return True
        if raw in {"n", "no"}:
            return False
        print("  Please answer 'y' or 'n'.")


def _is_valid_triangle(low: float, mode: float, high: float) -> bool:
    return low <= mode <= high


__all__ = ["run_cli"]
