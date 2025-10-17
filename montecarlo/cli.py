"""Command line interface for the Monte Carlo scheduling simulator."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

from .config import load_config
from .simulation import MonteCarloSimulator, SimulationError
from .io import Risk, Task, load_calendar, load_risks, load_tasks


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Monte Carlo simulations for project schedules.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser(
        "run", help="Execute a simulation run based on a configuration file or raw inputs."
    )
    run_parser.add_argument(
        "--config",
        type=Path,
        help="Path to the YAML configuration file.",
    )
    run_parser.add_argument(
        "--tasks",
        type=Path,
        help="Path to the task CSV file when not using --config.",
    )
    run_parser.add_argument(
        "--risks",
        type=Path,
        help="Optional path to the risks CSV file when not using --config.",
    )
    run_parser.add_argument(
        "--calendar",
        "--cal",
        dest="calendar",
        type=Path,
        help="Optional path to a calendar JSON file when not using --config.",
    )
    run_parser.add_argument(
        "--iterations",
        type=int,
        help="Number of Monte Carlo iterations to execute.",
    )
    run_parser.add_argument(
        "--confidence",
        "--confidence-level",
        "--confidence-levels",
        dest="confidence_levels",
        action="append",
        type=float,
        metavar="Q",
        help="Confidence level to report (0-1). May be supplied multiple times.",
    )
    run_parser.add_argument(
        "--random-seed",
        type=int,
        dest="random_seed",
        help="Seed value for the random number generator.",
    )
    run_parser.add_argument(
        "--output",
        type=Path,
        help="Optional path to store the simulation summary as JSON.",
    )
    run_parser.add_argument(
        "--out",
        dest="output_dir",
        type=Path,
        help="Directory where detailed output artifacts (histogram, S-curve, milestones) will be written.",
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
        output_dir: Optional[Path] = args.output_dir
        if args.config:
            config = load_config(args.config)
            tasks = load_tasks(config["tasks"])  # type: ignore[arg-type]
            risks = load_risks(config.get("risks"))
            calendar = load_calendar(config.get("calendar"))
            iterations = int(config.get("iterations", 5000))
            try:
                confidence_levels = _normalize_confidence_levels(
                    config.get("confidence_levels")
                )
            except ValueError as exc:
                parser.error(str(exc))
            random_seed = config.get("random_seed")
            if output_dir is None and config.get("output_dir"):
                output_dir = Path(str(config["output_dir"]))
        else:
            if not args.tasks:
                parser.error("run: provide --config or --tasks")
            tasks = load_tasks(args.tasks)
            risks = load_risks(args.risks)
            calendar = load_calendar(args.calendar)
            iterations = int(args.iterations or 5000)
            try:
                confidence_levels = _normalize_confidence_levels(args.confidence_levels)
            except ValueError as exc:
                parser.error(str(exc))
            random_seed = args.random_seed

        simulator = MonteCarloSimulator(
            tasks=tasks,
            risks=risks,
            calendar=calendar,
            iterations=iterations,
            confidence_levels=confidence_levels,
            random_seed=random_seed,
        )

        summary = simulator.run()
        _print_summary(summary)

        if args.output:
            args.output.write_text(json.dumps(summary, indent=2))
        if output_dir:
            _write_output_bundle(output_dir, summary)
            print(f"Detailed outputs saved to {output_dir.resolve()}")
    elif args.command == "interactive":
        _run_interactive()

    return 0


def _print_summary(summary: Dict[str, Any]) -> None:
    print("Simulation complete")
    print("------------------")
    print(f"Iterations: {summary['iterations']}")
    print(f"Mean project duration: {summary['statistics']['mean']:.2f} days")
    print(f"Median project duration: {summary['statistics']['median']:.2f} days")
    percentiles = summary["statistics"].get("percentiles", {})
    for level in sorted(percentiles, key=lambda item: float(item)):
        value = percentiles[level]
        print(f"P{int(float(level) * 100):>3}: {value:.2f} days")
    if summary["critical_path"]:
        print("Critical path (most frequent):")
        print(" -> ".join(summary["critical_path"]))
    milestones = summary.get("milestones") or {}
    if milestones:
        print("Milestone confidence levels:")
        for milestone_id, data in milestones.items():
            name = data.get("name", milestone_id)
            values = data.get("percentiles", {})
            if not values:
                continue
            formatted = " ".join(
                f"P{int(float(level) * 100)}={values[level]:.2f}d"
                for level in sorted(values, key=lambda item: float(item))
            )
            print(f"  {milestone_id} ({name}): {formatted}")


def _normalize_confidence_levels(levels: Optional[Sequence[float]]) -> Sequence[float]:
    base = {0.5, 0.8, 0.9}
    if levels:
        for raw in levels:
            value = float(raw)
            if not 0.0 < value < 1.0:
                raise ValueError(f"Confidence levels must be between 0 and 1: {raw!r}")
            base.add(value)
    return tuple(sorted(base))


def _write_output_bundle(directory: Path, summary: Dict[str, Any]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "summary.json").write_text(json.dumps(summary, indent=2))

    histogram = summary.get("histogram") or []
    if histogram:
        with (directory / "histogram.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle, fieldnames=["bin_start", "bin_end", "count", "probability"]
            )
            writer.writeheader()
            for entry in histogram:
                writer.writerow(
                    {
                        "bin_start": entry.get("bin_start"),
                        "bin_end": entry.get("bin_end"),
                        "count": entry.get("count"),
                        "probability": entry.get("probability"),
                    }
                )

    s_curve = summary.get("s_curve") or []
    if s_curve:
        with (directory / "s_curve.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["percentile", "duration"])
            writer.writeheader()
            for point in s_curve:
                writer.writerow(
                    {
                        "percentile": point.get("percentile"),
                        "duration": point.get("duration"),
                    }
                )

    milestones = summary.get("milestones") or {}
    if milestones:
        with (directory / "milestones.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle, fieldnames=["milestone_id", "name", "percentile", "duration"]
            )
            writer.writeheader()
            for milestone_id, data in milestones.items():
                name = data.get("name", milestone_id)
                for level, duration in sorted(
                    data.get("percentiles", {}).items(), key=lambda item: float(item[0])
                ):
                    writer.writerow(
                        {
                            "milestone_id": milestone_id,
                            "name": name,
                            "percentile": level,
                            "duration": duration,
                        }
                    )


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
        default=(0.5, 0.8, 0.9),
    )
    try:
        normalized_levels = _normalize_confidence_levels(confidence_levels)
    except ValueError as exc:
        print(f"Cannot run simulation: {exc}")
        return
    random_seed = _prompt_optional_int("Random seed (optional)", input)

    try:
        simulator = MonteCarloSimulator(
            tasks=tasks,
            risks=risks,
            calendar=None,
            iterations=iterations,
            confidence_levels=normalized_levels,
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
        work_package_raw = reader("  Work package (optional): ").strip()
        work_package = work_package_raw or None
        milestone_flag = _prompt_yes_no("  Mark as milestone?", reader, default=False)
        tasks.append(
            Task(
                task_id=task_id,
                name=name,
                optimistic=optimistic,
                most_likely=most_likely,
                pessimistic=pessimistic,
                predecessors=predecessors,
                work_package=work_package,
                milestone_flag=milestone_flag,
            )
        )
        print()
    return tasks


def _prompt_predecessors(reader: Callable[[str], str], tasks: Sequence[Task]) -> Sequence[str]:
    while True:
        raw = reader("  Predecessors (comma separated ids, leave blank if none): ").strip()
        if not raw:
            return ()
        cleaned = raw.replace(";", ",")
        entered = [value.strip() for value in cleaned.split(",") if value.strip()]
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
    default: Sequence[float] = (0.5, 0.8, 0.9),
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
