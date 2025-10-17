"""Data loading utilities for the Monte Carlo simulator."""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence


_WEEKDAY_ALIASES = {
    "mon": 0,
    "monday": 0,
    "tue": 1,
    "tues": 1,
    "tuesday": 1,
    "wed": 2,
    "wednesday": 2,
    "thu": 3,
    "thur": 3,
    "thurs": 3,
    "thursday": 3,
    "fri": 4,
    "friday": 4,
    "sat": 5,
    "saturday": 5,
    "sun": 6,
    "sunday": 6,
}


@dataclass(frozen=True)
class Task:
    task_id: str
    name: str
    optimistic: float
    most_likely: float
    pessimistic: float
    predecessors: Sequence[str]
    work_package: Optional[str] = None
    milestone_flag: bool = False


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
            work_package = (row.get("work_package") or "").strip() or None
            milestone_raw = (row.get("milestone_flag") or "").strip().lower()
            milestone_flag = milestone_raw in {
                "1",
                "true",
                "yes",
                "y",
                "on",
                "milestone",
            }
            tasks.append(
                Task(
                    task_id=row["task_id"].strip(),
                    name=row["name"].strip(),
                    optimistic=float(row["optimistic"]),
                    most_likely=float(row["most_likely"]),
                    pessimistic=float(row["pessimistic"]),
                    predecessors=predecessors,
                    work_package=work_package,
                    milestone_flag=milestone_flag,
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
        fieldnames = reader.fieldnames or []
        rows = list(reader)
        required = {
            "risk_id",
            "description",
            "probability",
            "affected_tasks",
            "impact_min",
            "impact_mode",
            "impact_max",
        }
        missing = [field for field in required if field not in fieldnames]
        if missing:
            alternative = {
                "risk_id",
                "risk_name",
                "probability",
                "impact_type",
                "impact_target",
                "impact_model",
                "correlation_group",
                "activation_logic",
            }
            if not rows and set(fieldnames).issubset(alternative):
                return []
            raise DataError(f"Risk file is missing columns: {', '.join(missing)}")

        for row in rows:
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

    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        if not raw:
            raise DataError("Calendar file has invalid fields.")
        data = raw[0]
    else:
        data = raw

    try:
        if "working_days" in data:
            working_days = tuple(int(day) for day in data.get("working_days", (0, 1, 2, 3, 4)))
            daily_capacity = float(data.get("daily_capacity", 1.0))
        else:
            workdays_raw = data.get("workdays", ["Mon", "Tue", "Wed", "Thu", "Fri"])
            working_days = tuple(
                _WEEKDAY_ALIASES[str(day).strip().lower()] for day in workdays_raw
            )
            hours = float(data.get("work_hours_per_day", 8))
            daily_capacity = hours / 8 if hours > 0 else 1.0
        holidays = tuple(str(value) for value in data.get("holidays", ()))
    except (TypeError, ValueError, KeyError) as exc:
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
