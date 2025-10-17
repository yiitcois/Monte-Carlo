"""Tests for helper functions used by the interactive CLI."""
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from montecarlo.cli import (
    _is_valid_triangle,
    _prompt_confidence_levels,
    _prompt_float,
    _prompt_int,
    _prompt_optional_int,
    _prompt_predecessors,
)
from montecarlo.io import Task


def make_reader(responses: list[str]):
    values = iter(responses)

    def reader(prompt: str) -> str:  # pragma: no cover - executed via helper functions
        return next(values)

    return reader


def test_prompt_confidence_levels_default():
    reader = make_reader([""])
    assert _prompt_confidence_levels("Confidence", reader) == (0.5, 0.75, 0.9)


def test_prompt_confidence_levels_custom_sorted_unique():
    reader = make_reader(["0.8, 0.8, 0.6"])
    assert _prompt_confidence_levels("Confidence", reader) == (0.6, 0.8)


def test_prompt_int_uses_default_and_validates_minimum():
    reader = make_reader(["", "0", "10"])
    assert _prompt_int("Iterations", reader, default=5, minimum=1) == 5

    # Second call uses remaining responses and enforces the minimum.
    assert _prompt_int("Iterations", reader, minimum=1) == 10


def test_prompt_float_respects_bounds():
    reader = make_reader(["-1", "2"])
    assert _prompt_float("Value", reader, minimum=0.0, maximum=5.0) == 2.0


def test_prompt_optional_int_returns_none_on_invalid():
    reader = make_reader(["", "abc", "42"])
    assert _prompt_optional_int("Seed", reader) is None
    assert _prompt_optional_int("Seed", reader) is None
    assert _prompt_optional_int("Seed", reader) == 42


def test_prompt_predecessors_rejects_unknown_ids():
    tasks = [
        Task("A", "Task A", 1.0, 2.0, 3.0, ()),
        Task("B", "Task B", 1.0, 2.0, 3.0, ()),
    ]
    reader = make_reader(["C", "A, B"])
    assert _prompt_predecessors(reader, tasks) == ("A", "B")


def test_is_valid_triangle_checks_ordering():
    assert _is_valid_triangle(1.0, 2.0, 3.0)
    assert not _is_valid_triangle(2.0, 1.0, 3.0)
