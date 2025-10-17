"""Tests for the FastAPI interface."""
import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from montecarlo.web import app


def test_simulation_endpoint_returns_summary() -> None:
    client = TestClient(app)
    response = client.post(
        "/simulate",
        json={
            "tasks": [
                {
                    "task_id": "A",
                    "name": "Task A",
                    "optimistic": 1.0,
                    "most_likely": 2.0,
                    "pessimistic": 3.0,
                    "predecessors": [],
                }
            ],
            "iterations": 200,
            "confidence_levels": [0.5, 0.9],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["iterations"] == 200
    assert "statistics" in payload
    assert "critical_path" in payload


def test_invalid_confidence_levels_return_error() -> None:
    client = TestClient(app)
    response = client.post(
        "/simulate",
        json={
            "tasks": [
                {
                    "task_id": "A",
                    "name": "Task A",
                    "optimistic": 1.0,
                    "most_likely": 2.0,
                    "pessimistic": 3.0,
                    "predecessors": [],
                }
            ],
            "iterations": 50,
            "confidence_levels": [1.5],
        },
    )
    assert response.status_code == 422
