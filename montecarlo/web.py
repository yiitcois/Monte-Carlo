"""FastAPI application providing a simple web UI for the Monte Carlo simulator."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, validator

from .io import Calendar, Risk, Task
from .simulation import MonteCarloSimulator, SimulationError


class TaskPayload(BaseModel):
    """Pydantic model describing the task information supplied by the UI."""

    task_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    optimistic: float = Field(..., ge=0.0)
    most_likely: float = Field(..., ge=0.0)
    pessimistic: float = Field(..., ge=0.0)
    predecessors: List[str] = Field(default_factory=list)

    @validator("predecessors", pre=True)
    def _clean_predecessors(cls, value: Sequence[str] | str) -> List[str]:
        if isinstance(value, str):
            parts = [part.strip() for part in value.split(",")]
            return [part for part in parts if part]
        return [item.strip() for item in value if item]

    @validator("most_likely")
    def _check_triangle(cls, most_likely: float, values: Dict[str, Any]) -> float:
        optimistic = values.get("optimistic", most_likely)
        pessimistic = values.get("pessimistic", most_likely)
        if optimistic > most_likely or most_likely > pessimistic:
            raise ValueError("Durations must satisfy optimistic <= most likely <= pessimistic")
        return most_likely

    def to_task(self) -> Task:
        return Task(
            task_id=self.task_id,
            name=self.name,
            optimistic=self.optimistic,
            most_likely=self.most_likely,
            pessimistic=self.pessimistic,
            predecessors=tuple(self.predecessors),
        )


class RiskPayload(BaseModel):
    """Risk information accepted from the UI."""

    risk_id: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    probability: float = Field(..., ge=0.0, le=1.0)
    affected_tasks: List[str] = Field(default_factory=list)
    impact_min: float = Field(..., ge=0.0)
    impact_mode: float = Field(..., ge=0.0)
    impact_max: float = Field(..., ge=0.0)

    @validator("affected_tasks", pre=True)
    def _clean_affected(cls, value: Sequence[str] | str) -> List[str]:
        if isinstance(value, str):
            parts = [part.strip() for part in value.split(",")]
            return [part for part in parts if part]
        return [item.strip() for item in value if item]

    def to_risk(self) -> Risk:
        return Risk(
            risk_id=self.risk_id,
            description=self.description,
            probability=self.probability,
            affected_tasks=tuple(self.affected_tasks),
            impact_min=self.impact_min,
            impact_mode=self.impact_mode,
            impact_max=self.impact_max,
        )


class CalendarPayload(BaseModel):
    """Optional working calendar definition."""

    working_days: List[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4])
    daily_capacity: float = Field(1.0, gt=0.0)
    holidays: List[str] = Field(default_factory=list)

    def to_calendar(self) -> Calendar:
        return Calendar(
            working_days=tuple(self.working_days),
            daily_capacity=self.daily_capacity,
            holidays=tuple(self.holidays),
        )


class SimulationRequest(BaseModel):
    """Request body accepted by the ``/simulate`` endpoint."""

    tasks: List[TaskPayload] = Field(..., min_items=1)
    risks: List[RiskPayload] = Field(default_factory=list)
    iterations: int = Field(5000, ge=1)
    confidence_levels: List[float] = Field(default_factory=lambda: [0.5, 0.75, 0.9])
    random_seed: Optional[int] = None
    calendar: Optional[CalendarPayload] = None

    @validator("confidence_levels")
    def _validate_confidence(cls, values: Sequence[float]) -> List[float]:
        if not values:
            raise ValueError("At least one confidence level must be provided")
        result: List[float] = []
        for value in values:
            if not 0.0 < float(value) < 1.0:
                raise ValueError("Confidence levels must be between 0 and 1")
            result.append(float(value))
        return result


app = FastAPI(title="Monte Carlo Schedule Simulator")


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    """Serve the single-page application."""

    return _INDEX_HTML


@app.post("/simulate")
def simulate(payload: SimulationRequest) -> Dict[str, Any]:
    """Execute a simulation run and return the summary as JSON."""

    tasks = [task_payload.to_task() for task_payload in payload.tasks]
    risks = [risk_payload.to_risk() for risk_payload in payload.risks]
    calendar = payload.calendar.to_calendar() if payload.calendar else None

    try:
        simulator = MonteCarloSimulator(
            tasks=tasks,
            risks=risks,
            calendar=calendar,
            iterations=payload.iterations,
            confidence_levels=payload.confidence_levels,
            random_seed=payload.random_seed,
        )
        return simulator.run()
    except SimulationError as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=400, detail=str(exc)) from exc


_INDEX_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Monte Carlo Schedule Simulator</title>
  <style>
    :root {
      color-scheme: light dark;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background-color: #f4f6fb;
      color: #1f2933;
    }
    body {
      margin: 0;
      padding: 0;
      display: flex;
      justify-content: center;
      min-height: 100vh;
    }
    main {
      max-width: 960px;
      width: 100%;
      padding: 2rem;
      box-sizing: border-box;
    }
    h1 {
      margin-top: 0;
    }
    section {
      background: white;
      border-radius: 12px;
      box-shadow: 0 10px 30px rgba(15, 23, 42, 0.1);
      padding: 1.5rem;
      margin-bottom: 1.5rem;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      margin-bottom: 1rem;
    }
    th, td {
      border: 1px solid #d9e2ec;
      padding: 0.5rem;
      text-align: left;
    }
    th {
      background: #e4ebf5;
      font-weight: 600;
    }
    input, button, textarea {
      font: inherit;
    }
    input[type="number"] {
      width: 100%;
    }
    input[type="text"], input[type="number"] {
      padding: 0.35rem 0.45rem;
      border-radius: 6px;
      border: 1px solid #cbd2d9;
    }
    button.primary {
      background: #3b82f6;
      color: white;
      border: none;
      padding: 0.6rem 1.2rem;
      border-radius: 999px;
      cursor: pointer;
      font-weight: 600;
    }
    button.secondary {
      background: transparent;
      border: 1px dashed #cbd2d9;
      color: #3b82f6;
      padding: 0.4rem 0.8rem;
      border-radius: 999px;
      cursor: pointer;
      font-weight: 600;
    }
    .actions {
      display: flex;
      gap: 0.5rem;
      flex-wrap: wrap;
      margin-bottom: 1rem;
    }
    #results {
      white-space: pre-wrap;
      background: #0f172a;
      color: #f8fafc;
      border-radius: 12px;
      padding: 1rem;
      font-family: "Fira Code", "SFMono-Regular", ui-monospace, monospace;
      overflow-x: auto;
    }
    .error {
      color: #dc2626;
      font-weight: 600;
      margin-bottom: 1rem;
    }
    @media (max-width: 720px) {
      th, td {
        font-size: 0.85rem;
      }
      section {
        padding: 1rem;
      }
    }
  </style>
</head>
<body>
  <main>
    <h1>Monte Carlo Schedule Simulator</h1>
    <p>Define your project tasks, optional risk events, and simulation settings. Click <strong>Run simulation</strong> to see the results without touching the terminal.</p>

    <section>
      <h2>Tasks</h2>
      <p>Enter each activity with its optimistic, most likely, and pessimistic duration estimates. Predecessors should be comma separated.</p>
      <div class="actions">
        <button type="button" class="secondary" id="add-task">Add task</button>
      </div>
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Name</th>
            <th>Optimistic</th>
            <th>Most likely</th>
            <th>Pessimistic</th>
            <th>Predecessors</th>
            <th></th>
          </tr>
        </thead>
        <tbody id="tasks-body"></tbody>
      </table>
    </section>

    <section>
      <h2>Risk events (optional)</h2>
      <p>Include probabilistic events that inflate task durations. Leave this section empty if you have no risks.</p>
      <div class="actions">
        <button type="button" class="secondary" id="add-risk">Add risk</button>
      </div>
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Description</th>
            <th>Probability</th>
            <th>Affected tasks</th>
            <th>Impact min</th>
            <th>Impact mode</th>
            <th>Impact max</th>
            <th></th>
          </tr>
        </thead>
        <tbody id="risks-body"></tbody>
      </table>
    </section>

    <section>
      <h2>Simulation settings</h2>
      <div style="display:grid;gap:0.75rem;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));">
        <label>Iterations
          <input id="iterations" type="number" min="1" value="5000" />
        </label>
        <label>Confidence levels (comma separated)
          <input id="confidence-levels" type="text" value="0.5, 0.75, 0.9" />
        </label>
        <label>Random seed (optional)
          <input id="random-seed" type="number" />
        </label>
      </div>
      <details style="margin-top:1rem;">
        <summary>Calendar settings (optional)</summary>
        <div style="margin-top:0.75rem;display:grid;gap:0.75rem;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));">
          <label>Working days (0=Mon ... 6=Sun)
            <input id="calendar-working-days" type="text" placeholder="0,1,2,3,4" />
          </label>
          <label>Daily capacity multiplier
            <input id="calendar-capacity" type="number" min="0" step="0.1" placeholder="1.0" />
          </label>
          <label>Holidays (offset days)
            <input id="calendar-holidays" type="text" placeholder="10, 25" />
          </label>
        </div>
      </details>
      <div class="actions" style="margin-top:1.5rem;">
        <button type="button" class="primary" id="run-simulation">Run simulation</button>
      </div>
      <div class="error" id="error" role="alert" style="display:none;"></div>
      <pre id="results">Results will appear here.</pre>
    </section>
  </main>
  <template id="task-row">
    <tr>
      <td><input type="text" name="task_id" required /></td>
      <td><input type="text" name="name" required /></td>
      <td><input type="number" name="optimistic" step="0.1" min="0" required /></td>
      <td><input type="number" name="most_likely" step="0.1" min="0" required /></td>
      <td><input type="number" name="pessimistic" step="0.1" min="0" required /></td>
      <td><input type="text" name="predecessors" placeholder="e.g. TASK-1, TASK-2" /></td>
      <td style="text-align:center;"><button type="button" class="secondary remove-row">Remove</button></td>
    </tr>
  </template>
  <template id="risk-row">
    <tr>
      <td><input type="text" name="risk_id" required /></td>
      <td><input type="text" name="description" required /></td>
      <td><input type="number" name="probability" min="0" max="1" step="0.01" required /></td>
      <td><input type="text" name="affected_tasks" placeholder="TASK-1, TASK-2" /></td>
      <td><input type="number" name="impact_min" min="0" step="0.01" required /></td>
      <td><input type="number" name="impact_mode" min="0" step="0.01" required /></td>
      <td><input type="number" name="impact_max" min="0" step="0.01" required /></td>
      <td style="text-align:center;"><button type="button" class="secondary remove-row">Remove</button></td>
    </tr>
  </template>
  <script>
    const tasksBody = document.getElementById('tasks-body');
    const risksBody = document.getElementById('risks-body');

    function addRow(body, templateId, initial = []) {
      const template = document.getElementById(templateId);
      const clone = template.content.firstElementChild.cloneNode(true);
      const inputs = clone.querySelectorAll('input');
      inputs.forEach((input, index) => {
        if (initial[index] !== undefined) {
          input.value = initial[index];
        }
      });
      clone.querySelector('.remove-row').addEventListener('click', () => {
        body.removeChild(clone);
      });
      body.appendChild(clone);
    }

    document.getElementById('add-task').addEventListener('click', () => addRow(tasksBody, 'task-row'));
    document.getElementById('add-risk').addEventListener('click', () => addRow(risksBody, 'risk-row'));

    // Seed with two example tasks to help first-time users.
    addRow(tasksBody, 'task-row', ['DESIGN', 'Design', 3, 5, 8, '']);
    addRow(tasksBody, 'task-row', ['BUILD', 'Build prototype', 5, 7, 12, 'DESIGN']);

    const parseList = (value) => value.split(',').map(item => item.trim()).filter(Boolean);

    function collectTasks() {
      const rows = tasksBody.querySelectorAll('tr');
      const tasks = [];
      rows.forEach((row) => {
        const get = (name) => row.querySelector(`[name="${name}"]`).value.trim();
        if (!get('task_id')) {
          return;
        }
        const optimistic = Number(get('optimistic'));
        const mostLikely = Number(get('most_likely'));
        const pessimistic = Number(get('pessimistic'));
        if ([optimistic, mostLikely, pessimistic].some((value) => Number.isNaN(value))) {
          throw new Error('All duration fields must be valid numbers.');
        }
        tasks.push({
          task_id: get('task_id'),
          name: get('name') || get('task_id'),
          optimistic,
          most_likely: mostLikely,
          pessimistic,
          predecessors: parseList(get('predecessors')),
        });
      });
      return tasks;
    }

    function collectRisks() {
      const rows = risksBody.querySelectorAll('tr');
      const risks = [];
      rows.forEach((row) => {
        const get = (name) => row.querySelector(`[name="${name}"]`).value.trim();
        if (!get('risk_id')) {
          return;
        }
        const probability = Number(get('probability'));
        const impactMin = Number(get('impact_min'));
        const impactMode = Number(get('impact_mode'));
        const impactMax = Number(get('impact_max'));
        if ([probability, impactMin, impactMode, impactMax].some((value) => Number.isNaN(value))) {
          throw new Error('All risk fields must be valid numbers.');
        }
        risks.push({
          risk_id: get('risk_id'),
          description: get('description'),
          probability,
          affected_tasks: parseList(get('affected_tasks')),
          impact_min: impactMin,
          impact_mode: impactMode,
          impact_max: impactMax,
        });
      });
      return risks;
    }

    function collectCalendar() {
      const workingDays = document.getElementById('calendar-working-days').value.trim();
      const capacity = document.getElementById('calendar-capacity').value.trim();
      const holidays = document.getElementById('calendar-holidays').value.trim();
      if (!workingDays && !capacity && !holidays) {
        return null;
      }
      const payload = {};
      if (workingDays) {
        payload.working_days = parseList(workingDays).map((value) => Number(value));
      }
      if (capacity) {
        const parsed = Number(capacity);
        if (Number.isNaN(parsed) || parsed <= 0) {
          throw new Error('Daily capacity must be a positive number.');
        }
        payload.daily_capacity = parsed;
      }
      if (holidays) {
        payload.holidays = parseList(holidays);
      }
      return payload;
    }

    async function runSimulation() {
      const errorBox = document.getElementById('error');
      errorBox.style.display = 'none';
      errorBox.textContent = '';
      const resultsBox = document.getElementById('results');
      resultsBox.textContent = 'Running simulation...';
      try {
        const tasks = collectTasks();
        if (!tasks.length) {
          throw new Error('Add at least one task before running the simulation.');
        }
        const risks = collectRisks();
        const iterations = Number(document.getElementById('iterations').value || 0);
        if (!Number.isInteger(iterations) || iterations < 1) {
          throw new Error('Iterations must be a positive integer.');
        }
        const confidenceLevels = parseList(document.getElementById('confidence-levels').value)
          .map((value) => Number(value));
        if (!confidenceLevels.length || confidenceLevels.some((value) => Number.isNaN(value))) {
          throw new Error('Confidence levels must contain at least one valid number between 0 and 1.');
        }
        const randomSeedValue = document.getElementById('random-seed').value;
        const calendar = collectCalendar();
        const payload = {
          tasks,
          risks,
          iterations,
          confidence_levels: confidenceLevels,
        };
        if (randomSeedValue) {
          const parsedSeed = Number(randomSeedValue);
          if (!Number.isInteger(parsedSeed)) {
            throw new Error('Random seed must be an integer.');
          }
          payload.random_seed = parsedSeed;
        }
        if (calendar) {
          payload.calendar = calendar;
        }

        const response = await fetch('/simulate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.detail || 'Simulation failed.');
        }
        resultsBox.textContent = JSON.stringify(data, null, 2);
      } catch (error) {
        console.error(error);
        errorBox.textContent = error.message || 'Unexpected error occurred.';
        errorBox.style.display = 'block';
        resultsBox.textContent = 'No results yet.';
      }
    }

    document.getElementById('run-simulation').addEventListener('click', runSimulation);
  </script>
</body>
</html>
"""


__all__ = ["app"]
