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
    work_package: Optional[str] = None
    milestone_flag: bool = False

    @validator("predecessors", pre=True)
    def _clean_predecessors(cls, value: Sequence[str] | str) -> List[str]:
        if isinstance(value, str):
            parts = [part.strip() for part in value.split(",")]
            return [part for part in parts if part]
        return [item.strip() for item in value if item]

    @validator("work_package", pre=True)
    def _clean_work_package(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None

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
            work_package=self.work_package,
            milestone_flag=self.milestone_flag,
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
    confidence_levels: List[float] = Field(default_factory=lambda: [0.5, 0.8, 0.9])
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
    .plan-view {
      display: grid;
      gap: 1.5rem;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    }
    .plan-grid,
    .plan-gantt {
      display: grid;
      gap: 1rem;
    }
    .plan-grid-section {
      background: #f8fafc;
      border: 1px solid #d9e2ec;
      border-radius: 10px;
      padding: 0.75rem 1rem;
    }
    .plan-grid-section h3 {
      margin-top: 0;
      margin-bottom: 0.5rem;
      display: flex;
      align-items: center;
      gap: 0.4rem;
    }
    .plan-grid-section table {
      margin-bottom: 0;
    }
    .plan-grid-section td {
      border: none;
      border-bottom: 1px solid #e4ebf5;
      padding-left: 0;
      padding-right: 0;
    }
    .plan-grid-section tr:last-child td {
      border-bottom: none;
    }
    .gantt-group {
      background: #f1f5f9;
      border: 1px solid #d9e2ec;
      border-radius: 10px;
      padding: 0.75rem 1rem;
    }
    .gantt-group-title {
      font-weight: 600;
      margin-bottom: 0.5rem;
    }
    .gantt-row {
      display: grid;
      grid-template-columns: 160px 1fr;
      align-items: center;
      gap: 0.75rem;
      margin-bottom: 0.45rem;
    }
    .gantt-label {
      font-weight: 500;
      display: flex;
      align-items: center;
      gap: 0.35rem;
    }
    .gantt-bar {
      position: relative;
      background: linear-gradient(90deg, #60a5fa, #3b82f6);
      height: 16px;
      border-radius: 999px;
      min-width: 6px;
    }
    .gantt-bar::after {
      content: attr(data-duration) " d";
      position: absolute;
      right: -3.4rem;
      top: -0.35rem;
      font-size: 0.7rem;
      color: #475569;
    }
    .gantt-bar--milestone {
      background: transparent;
      display: flex;
      justify-content: flex-start;
      align-items: center;
      color: #f97316;
      min-width: unset;
    }
    .gantt-bar--milestone::after {
      content: "";
    }
    .milestone-icon {
      color: #f97316;
      font-size: 0.9rem;
    }
    .placeholder {
      color: #64748b;
      font-style: italic;
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
            <th>Work package</th>
            <th>Optimistic</th>
            <th>Most likely</th>
            <th>Pessimistic</th>
            <th>Predecessors</th>
            <th>Milestone</th>
            <th></th>
          </tr>
        </thead>
        <tbody id="tasks-body"></tbody>
      </table>
    </section>

    <section>
      <h2>Plan preview</h2>
      <p>Review grouped activities and a quick Gantt projection based on the durations above. Use work packages to segment the view and mark milestones to highlight them in both grids.</p>
      <div class="plan-view">
        <div class="plan-grid" id="plan-grid">
          <p class="placeholder">Add tasks to populate the grid.</p>
        </div>
        <div class="plan-gantt" id="plan-gantt">
          <p class="placeholder">Add tasks to visualize the Gantt chart.</p>
        </div>
      </div>
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
          <input id="confidence-levels" type="text" value="0.5, 0.8, 0.9" />
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
      <td><input type="text" name="work_package" placeholder="e.g. WP-1" /></td>
      <td><input type="number" name="optimistic" step="0.1" min="0" required /></td>
      <td><input type="number" name="most_likely" step="0.1" min="0" required /></td>
      <td><input type="number" name="pessimistic" step="0.1" min="0" required /></td>
      <td><input type="text" name="predecessors" placeholder="e.g. TASK-1, TASK-2" /></td>
      <td style="text-align:center;"><input type="checkbox" name="milestone_flag" aria-label="Milestone" /></td>
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
    const planGrid = document.getElementById('plan-grid');
    const planGantt = document.getElementById('plan-gantt');

    function parseList(value) {
      return (value || '')
        .split(/[,;]/)
        .map((item) => item.trim())
        .filter(Boolean);
    }

    function computeSchedule(tasks) {
      const map = new Map(tasks.map((task) => [task.task_id, task]));
      const inDegree = new Map();
      const dependents = new Map();

      tasks.forEach((task) => {
        inDegree.set(task.task_id, inDegree.get(task.task_id) || 0);
      });

      tasks.forEach((task) => {
        (task.predecessors || []).forEach((pred) => {
          if (!map.has(pred)) {
            return;
          }
          inDegree.set(task.task_id, (inDegree.get(task.task_id) || 0) + 1);
          if (!dependents.has(pred)) {
            dependents.set(pred, []);
          }
          dependents.get(pred).push(task.task_id);
        });
      });

      const queue = Array.from(inDegree.entries())
        .filter(([, degree]) => degree === 0)
        .map(([taskId]) => taskId)
        .sort();

      const order = [];
      while (queue.length) {
        const current = queue.shift();
        order.push(current);
        const next = dependents.get(current) || [];
        next.forEach((child) => {
          const updated = (inDegree.get(child) || 0) - 1;
          inDegree.set(child, updated);
          if (updated === 0) {
            queue.push(child);
            queue.sort();
          }
        });
      }

      if (order.length !== tasks.length) {
        tasks.forEach((task) => {
          if (!order.includes(task.task_id)) {
            order.push(task.task_id);
          }
        });
      }

      const startTimes = new Map();
      const finishTimes = new Map();
      order.forEach((taskId) => {
        const task = map.get(taskId);
        if (!task) {
          return;
        }
        let start = 0;
        (task.predecessors || []).forEach((pred) => {
          if (!finishTimes.has(pred)) {
            return;
          }
          const finish = finishTimes.get(pred);
          if (finish > start) {
            start = finish;
          }
        });
        const duration = Number(task.most_likely) || 0;
        startTimes.set(taskId, start);
        finishTimes.set(taskId, start + duration);
      });

      return { order, startTimes, finishTimes };
    }

    function readTasksForPreview() {
      const rows = tasksBody.querySelectorAll('tr');
      const tasks = [];
      rows.forEach((row) => {
        const getInput = (name) => row.querySelector(`[name="${name}"]`);
        const idInput = getInput('task_id');
        if (!idInput) {
          return;
        }
        const taskId = idInput.value.trim();
        if (!taskId) {
          return;
        }
        const optimistic = Number(getInput('optimistic').value);
        const mostLikely = Number(getInput('most_likely').value);
        const pessimistic = Number(getInput('pessimistic').value);
        if ([optimistic, mostLikely, pessimistic].some((value) => Number.isNaN(value))) {
          return;
        }
        tasks.push({
          task_id: taskId,
          name: (getInput('name').value || '').trim() || taskId,
          work_package: (getInput('work_package').value || '').trim(),
          optimistic,
          most_likely: mostLikely,
          pessimistic,
          predecessors: parseList(getInput('predecessors').value),
          milestone_flag: Boolean(getInput('milestone_flag')?.checked),
        });
      });
      return tasks;
    }

    function renderPlanPreview() {
      if (!planGrid || !planGantt) {
        return;
      }
      const previewTasks = readTasksForPreview();
      if (!previewTasks.length) {
        planGrid.innerHTML = '<p class="placeholder">Add tasks to populate the grid.</p>';
        planGantt.innerHTML = '<p class="placeholder">Add tasks to visualize the Gantt chart.</p>';
        return;
      }

      const groups = new Map();
      previewTasks.forEach((task) => {
        const key = task.work_package || 'Ungrouped';
        if (!groups.has(key)) {
          groups.set(key, []);
        }
        groups.get(key).push(task);
      });

      const { startTimes, finishTimes } = computeSchedule(previewTasks);
      const finishValues = Array.from(finishTimes.values());
      const totalDuration = finishValues.length ? Math.max(...finishValues) : 0;
      const scale = totalDuration > 0 ? totalDuration : 1;

      planGrid.innerHTML = '';
      planGantt.innerHTML = '';

      const sortedGroups = Array.from(groups.entries()).sort((a, b) => a[0].localeCompare(b[0]));
      sortedGroups.forEach(([groupName, tasks]) => {
        const sortedTasks = [...tasks].sort(
          (a, b) => (startTimes.get(a.task_id) || 0) - (startTimes.get(b.task_id) || 0),
        );

        const gridSection = document.createElement('div');
        gridSection.className = 'plan-grid-section';
        const gridTitle = document.createElement('h3');
        gridTitle.textContent = groupName;
        gridSection.appendChild(gridTitle);

        const gridTable = document.createElement('table');
        const gridBody = document.createElement('tbody');
        sortedTasks.forEach((task) => {
          const row = document.createElement('tr');
          const nameCell = document.createElement('td');
          nameCell.innerHTML = `${task.name}${task.milestone_flag ? ' <span class="milestone-icon" title="Milestone">◆</span>' : ''}`;
          row.appendChild(nameCell);
          const durationCell = document.createElement('td');
          durationCell.style.textAlign = 'right';
          durationCell.textContent = `${Number(task.most_likely).toFixed(1)} d`;
          row.appendChild(durationCell);
          gridBody.appendChild(row);
        });
        if (!gridBody.children.length) {
          const emptyRow = document.createElement('tr');
          const cell = document.createElement('td');
          cell.colSpan = 2;
          cell.className = 'placeholder';
          cell.textContent = 'Add durations to include this work package.';
          emptyRow.appendChild(cell);
          gridBody.appendChild(emptyRow);
        }
        gridTable.appendChild(gridBody);
        gridSection.appendChild(gridTable);
        planGrid.appendChild(gridSection);

        const ganttGroup = document.createElement('div');
        ganttGroup.className = 'gantt-group';
        const ganttTitle = document.createElement('div');
        ganttTitle.className = 'gantt-group-title';
        ganttTitle.textContent = groupName;
        ganttGroup.appendChild(ganttTitle);

        sortedTasks.forEach((task) => {
          const row = document.createElement('div');
          row.className = 'gantt-row';

          const label = document.createElement('span');
          label.className = 'gantt-label';
          label.textContent = task.name;
          if (task.milestone_flag) {
            const icon = document.createElement('span');
            icon.className = 'milestone-icon';
            icon.title = 'Milestone';
            icon.textContent = '◆';
            label.appendChild(icon);
          }
          row.appendChild(label);

          const bar = document.createElement('div');
          const start = startTimes.get(task.task_id) || 0;
          const finish = finishTimes.get(task.task_id) || start;
          const duration = Math.max(finish - start, 0);
          bar.style.marginLeft = `${(start / scale) * 100}%`;
          if (duration <= 0) {
            bar.className = 'gantt-bar gantt-bar--milestone';
            bar.innerHTML = '<span class="milestone-icon" title="Milestone">◆</span>';
          } else {
            bar.className = 'gantt-bar';
            bar.style.width = `${(duration / scale) * 100}%`;
            bar.dataset.duration = duration.toFixed(1);
          }
          row.appendChild(bar);
          ganttGroup.appendChild(row);
        });

        planGantt.appendChild(ganttGroup);
      });
    }

    function addRow(body, templateId, initial = []) {
      const template = document.getElementById(templateId);
      const clone = template.content.firstElementChild.cloneNode(true);
      const inputs = clone.querySelectorAll('input');
      inputs.forEach((input, index) => {
        if (initial[index] !== undefined) {
          if (input.type === 'checkbox') {
            input.checked = Boolean(initial[index]);
          } else {
            input.value = initial[index];
          }
        }
        input.addEventListener('input', renderPlanPreview);
        if (input.type === 'checkbox') {
          input.addEventListener('change', renderPlanPreview);
        }
      });
      const removeButton = clone.querySelector('.remove-row');
      if (removeButton) {
        removeButton.addEventListener('click', () => {
          body.removeChild(clone);
          renderPlanPreview();
        });
      }
      body.appendChild(clone);
      renderPlanPreview();
    }

    document.getElementById('add-task').addEventListener('click', () => addRow(tasksBody, 'task-row'));
    document.getElementById('add-risk').addEventListener('click', () => addRow(risksBody, 'risk-row'));

    // Seed with two example tasks to help first-time users.
    addRow(tasksBody, 'task-row', ['DESIGN', 'Design', 'Concept', 3, 5, 8, '', false]);
    addRow(tasksBody, 'task-row', ['BUILD', 'Build prototype', 'Delivery', 5, 7, 12, 'DESIGN', false]);

    function collectTasks() {
      const rows = tasksBody.querySelectorAll('tr');
      const tasks = [];
      rows.forEach((row) => {
        const getInput = (name) => row.querySelector(`[name="${name}"]`);
        const idInput = getInput('task_id');
        if (!idInput) {
          return;
        }
        const taskId = idInput.value.trim();
        if (!taskId) {
          return;
        }
        const optimistic = Number(getInput('optimistic').value);
        const mostLikely = Number(getInput('most_likely').value);
        const pessimistic = Number(getInput('pessimistic').value);
        if ([optimistic, mostLikely, pessimistic].some((value) => Number.isNaN(value))) {
          throw new Error('All duration fields must be valid numbers.');
        }
        tasks.push({
          task_id: taskId,
          name: (getInput('name').value || '').trim() || taskId,
          work_package: (getInput('work_package').value || '').trim(),
          optimistic,
          most_likely: mostLikely,
          pessimistic,
          predecessors: parseList(getInput('predecessors').value),
          milestone_flag: Boolean(getInput('milestone_flag')?.checked),
        });
      });
      return tasks;
    }

    function collectRisks() {
      const rows = risksBody.querySelectorAll('tr');
      const risks = [];
      rows.forEach((row) => {
        const get = (name) => row.querySelector(`[name="${name}"]`);
        const idInput = get('risk_id');
        if (!idInput) {
          return;
        }
        const riskId = idInput.value.trim();
        if (!riskId) {
          return;
        }
        const probability = Number(get('probability').value);
        const impactMin = Number(get('impact_min').value);
        const impactMode = Number(get('impact_mode').value);
        const impactMax = Number(get('impact_max').value);
        if ([probability, impactMin, impactMode, impactMax].some((value) => Number.isNaN(value))) {
          throw new Error('All risk fields must be valid numbers.');
        }
        risks.push({
          risk_id: riskId,
          description: (get('description').value || '').trim(),
          probability,
          affected_tasks: parseList(get('affected_tasks').value),
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
