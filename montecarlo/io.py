"""Data loading utilities for the Monte Carlo simulator."""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence


@dataclass(frozen=True)
class Task:
    task_id: str
    name: str
    optimistic: float
    most_likely: float
    pessimistic: float
    predecessors: Sequence[str]


@dataclass(frozen=True)
class Risk:
    risk_id: str
    description: str
    probability: float
    affected_tasks: Sequence[str]
    impact_min: float
    impact_mode: float
    impact_max: float


@dataclass(frozen=True)
class Calendar:
    working_days: Sequence[int]
    daily_capacity: float
    holidays: Sequence[str]


class DataError(RuntimeError):
    """Raised when input files cannot be processed."""


def load_tasks(path_like: Path | str) -> List[Task]:
    path = Path(path_like)
    if not path.exists():
        raise DataError(f"Task file not found: {path}")

    tasks: List[Task] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {"task_id", "name", "optimistic", "most_likely", "pessimistic"}
        missing = [field for field in required if field not in reader.fieldnames]
        if missing:
            raise DataError(f"Task file is missing columns: {', '.join(missing)}")

        for row in reader:
            predecessors = tuple(
                predecessor.strip()
                for predecessor in row.get("predecessors", "").split(";")
                if predecessor.strip()
            )
            tasks.append(
                Task(
                    task_id=row["task_id"].strip(),
                    name=row["name"].strip(),
                    optimistic=float(row["optimistic"]),
                    most_likely=float(row["most_likely"]),
                    pessimistic=float(row["pessimistic"]),
                    predecessors=predecessors,
                )
            )
    return tasks


def load_risks(path_like: Optional[Path | str]) -> List[Risk]:
    if path_like is None:
        return []
    path = Path(path_like)
    if not path.exists():
        raise DataError(f"Risk file not found: {path}")

    risks: List[Risk] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {
            "risk_id",
            "description",
            "probability",
            "affected_tasks",
            "impact_min",
            "impact_mode",
            "impact_max",
        }
        missing = [field for field in required if field not in reader.fieldnames]
        if missing:
            raise DataError(f"Risk file is missing columns: {', '.join(missing)}")

        for row in reader:
            affected = tuple(
                task.strip() for task in row["affected_tasks"].split(";") if task.strip()
            )
            risks.append(
                Risk(
                    risk_id=row["risk_id"].strip(),
                    description=row["description"].strip(),
                    probability=float(row["probability"]),
                    affected_tasks=affected,
                    impact_min=float(row["impact_min"]),
                    impact_mode=float(row["impact_mode"]),
                    impact_max=float(row["impact_max"]),
                )
            )
    return risks


def load_calendar(path_like: Optional[Path | str]) -> Optional[Calendar]:
    if path_like is None:
        return None
    path = Path(path_like)
    if not path.exists():
        raise DataError(f"Calendar file not found: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    try:
        working_days = tuple(int(day) for day in data.get("working_days", (0, 1, 2, 3, 4)))
        daily_capacity = float(data.get("daily_capacity", 1.0))
        holidays = tuple(data.get("holidays", ()))
    except (TypeError, ValueError) as exc:
        raise DataError("Calendar file has invalid fields.") from exc

    return Calendar(working_days=working_days, daily_capacity=daily_capacity, holidays=holidays)


def index_tasks(tasks: Iterable[Task]) -> Dict[str, Task]:
    mapping: Dict[str, Task] = {}
    for task in tasks:
        if task.task_id in mapping:
            raise DataError(f"Duplicate task id detected: {task.task_id}")
        mapping[task.task_id] = task
    return mapping


__all__ = [
    "Task",
    "Risk",
    "Calendar",
    "load_tasks",
    "load_risks",
    "load_calendar",
    "index_tasks",
    "DataError",
]
