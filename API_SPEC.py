"""High-level API description for the Monte Carlo scheduling simulator."""

from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Optional, Sequence


@dataclass
class SimulationRequest:
    """Container for CLI-provided simulation parameters."""

    tasks_path: str
    risks_path: Optional[str] = None
    calendar_path: Optional[str] = None
    iterations: int = 5000
    confidence_levels: Sequence[float] = (0.5, 0.75, 0.9)
    random_seed: Optional[int] = None


@dataclass
class SimulationStatistics:
    """Key statistics returned by the simulator."""

    mean: float
    median: float
    stdev: float
    percentiles: Mapping[str, float]


@dataclass
class SimulationResponse:
    """Structured response from a simulation run."""

    iterations: int
    statistics: SimulationStatistics
    critical_path: Sequence[str]


class SimulatorProtocol:
    """Protocol that concrete simulator implementations should follow."""

    def run(self, request: SimulationRequest) -> SimulationResponse:  # pragma: no cover - interface only
        """Execute the simulation and return structured statistics."""
        raise NotImplementedError


def asdict(response: SimulationResponse) -> Dict[str, object]:
    """Helper to convert a :class:`SimulationResponse` into a JSON-serialisable dictionary."""

    return {
        "iterations": response.iterations,
        "statistics": {
            "mean": response.statistics.mean,
            "median": response.statistics.median,
            "stdev": response.statistics.stdev,
            "percentiles": dict(response.statistics.percentiles),
        },
        "critical_path": list(response.critical_path),
    }


__all__ = [
    "SimulationRequest",
    "SimulationStatistics",
    "SimulationResponse",
    "SimulatorProtocol",
    "asdict",
]
