"""Core simulation logic for Monte Carlo schedule analysis."""
from __future__ import annotations

import math
import random
from collections import Counter, defaultdict, deque
from statistics import mean, median
from typing import Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence

from .io import Calendar, Risk, Task, index_tasks


class SimulationError(RuntimeError):
    """Raised when the simulation cannot be executed."""


class MonteCarloSimulator:
    """Run Monte Carlo simulations for a set of tasks."""

    def __init__(
        self,
        tasks: Sequence[Task],
        risks: Sequence[Risk] | None = None,
        calendar: Optional[Calendar] = None,
        iterations: int = 5000,
        confidence_levels: Sequence[float] = (0.5, 0.75, 0.9),
        random_seed: Optional[int] = None,
    ) -> None:
        if iterations <= 0:
            raise SimulationError("Iterations must be positive.")
        if not tasks:
            raise SimulationError("At least one task is required for simulation.")

        self.tasks = list(tasks)
        self.risks = list(risks or [])
        self.calendar = calendar
        self.iterations = iterations
        self.confidence_levels = tuple(sorted(confidence_levels))
        self._rng = random.Random(random_seed)

        self._task_map = index_tasks(self.tasks)
        self._order = self._topological_order()

    def _topological_order(self) -> List[str]:
        incoming: MutableMapping[str, int] = defaultdict(int)
        adjacency: MutableMapping[str, List[str]] = defaultdict(list)

        for task in self.tasks:
            for predecessor in task.predecessors:
                if predecessor not in self._task_map:
                    raise SimulationError(f"Task '{task.task_id}' depends on unknown task '{predecessor}'.")
                adjacency[predecessor].append(task.task_id)
                incoming[task.task_id] += 1
            incoming.setdefault(task.task_id, 0)

        queue: deque[str] = deque([task_id for task_id, count in incoming.items() if count == 0])
        order: List[str] = []

        while queue:
            current = queue.popleft()
            order.append(current)
            for successor in adjacency[current]:
                incoming[successor] -= 1
                if incoming[successor] == 0:
                    queue.append(successor)

        if len(order) != len(self.tasks):
            raise SimulationError("Circular dependency detected in tasks.")
        return order

    def run(self) -> Dict[str, object]:
        durations: List[float] = []
        critical_paths: Counter[tuple[str, ...]] = Counter()

        for _ in range(self.iterations):
            sampled = self._sample_durations()
            project_duration, critical_path = self._calculate_schedule(sampled)
            durations.append(project_duration)
            critical_paths[tuple(critical_path)] += 1

        stats = {
            "mean": mean(durations),
            "median": median(durations),
            "stdev": _safe_stdev(durations),
            "percentiles": {
                f"{level}": percentile(durations, level) for level in self.confidence_levels
            },
        }

        critical_path = []
        if critical_paths:
            critical_path = list(max(critical_paths.items(), key=lambda item: item[1])[0])

        return {
            "iterations": self.iterations,
            "statistics": stats,
            "critical_path": critical_path,
        }

    def _sample_durations(self) -> Mapping[str, float]:
        durations: Dict[str, float] = {}
        for task in self.tasks:
            value = triangular(
                self._rng,
                task.optimistic,
                task.most_likely,
                task.pessimistic,
            )
            durations[task.task_id] = max(value, 0.1)

        for risk in self.risks:
            if self._rng.random() <= risk.probability:
                factor = triangular(self._rng, risk.impact_min, risk.impact_mode, risk.impact_max)
                for task_id in risk.affected_tasks:
                    if task_id in durations:
                        durations[task_id] *= max(0.0, 1.0 + factor)
        return durations

    def _calculate_schedule(self, durations: Mapping[str, float]) -> tuple[float, List[str]]:
        start_times: Dict[str, float] = {}
        finish_times: Dict[str, float] = {}
        predecessors: Dict[str, Optional[str]] = {}

        for task_id in self._order:
            task = self._task_map[task_id]
            ready_time = 0.0
            critical_parent = None
            for predecessor in task.predecessors:
                finish = finish_times[predecessor]
                if finish > ready_time:
                    ready_time = finish
                    critical_parent = predecessor
            duration = durations[task_id]
            if self.calendar:
                duration = adjust_for_calendar(duration, self.calendar)
            start_times[task_id] = ready_time
            finish_times[task_id] = ready_time + duration
            predecessors[task_id] = critical_parent

        last_task = max(finish_times, key=finish_times.get)
        critical_path: List[str] = []
        current: Optional[str] = last_task
        while current is not None:
            critical_path.append(current)
            current = predecessors[current]
        critical_path.reverse()

        return finish_times[last_task], critical_path


def triangular(rng: random.Random, low: float, mode: float, high: float) -> float:
    """Sample a value from a triangular distribution."""
    if not (low <= mode <= high):
        raise SimulationError("Triangular distribution requires low <= mode <= high.")
    return rng.triangular(low, high, mode)


def adjust_for_calendar(duration: float, calendar: Calendar) -> float:
    """Adjust duration to respect working days and daily capacity."""
    if duration <= 0:
        return 0.0

    working_days = set(calendar.working_days)
    if not working_days:
        return duration

    effective_daily = calendar.daily_capacity if calendar.daily_capacity > 0 else 1.0
    days_needed = duration / effective_daily

    full_days = math.floor(days_needed)
    remaining = days_needed - full_days

    day_counter = 0
    days_elapsed = 0
    while full_days > 0:
        weekday = day_counter % 7
        if weekday in working_days and not _is_holiday(day_counter, calendar):
            full_days -= 1
        days_elapsed += 1
        day_counter += 1

    while remaining > 0:
        weekday = day_counter % 7
        if weekday in working_days and not _is_holiday(day_counter, calendar):
            days_elapsed += remaining
            break
        days_elapsed += 1
        day_counter += 1

    return max(duration, days_elapsed)


def _is_holiday(offset: int, calendar: Calendar) -> bool:
    if not calendar.holidays:
        return False
    return str(offset) in calendar.holidays


def percentile(values: Sequence[float], q: float) -> float:
    if not 0 <= q <= 1:
        raise SimulationError("Percentile must be between 0 and 1.")
    sorted_values = sorted(values)
    index = (len(sorted_values) - 1) * q
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return sorted_values[int(index)]
    lower_value = sorted_values[int(lower)]
    upper_value = sorted_values[int(upper)]
    return lower_value + (upper_value - lower_value) * (index - lower)


def _safe_stdev(values: Iterable[float]) -> float:
    seq = list(values)
    if len(seq) <= 1:
        return 0.0
    m = mean(seq)
    return math.sqrt(sum((value - m) ** 2 for value in seq) / (len(seq) - 1))


__all__ = ["MonteCarloSimulator", "SimulationError", "percentile", "triangular"]
