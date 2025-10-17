# Monte Carlo Schedule Simulator

This project implements a Monte Carlo simulation engine that analyses project schedules using activity duration uncertainty and risk events. It consumes CSV/JSON/YAML inputs and produces summary statistics for completion times and critical paths.

## Features
- Triangular duration sampling for each task, respecting task precedence.
- Optional risk events that inflate task durations when they occur.
- Calendar adjustment to account for working days and daily capacity.
- Command line interface for running simulations and exporting summaries.

## Quick start
1. Create a virtual environment (recommended) and install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
   The only runtime dependency is [`PyYAML`](https://pyyaml.org/). If you prefer not to maintain a requirements file, run `pip install pyyaml` manually.

2. Run the simulator with the sample configuration:
   ```bash
   python -m montecarlo run --config examples/config.yaml
   ```

   You can also launch an interactive prompt and enter the tasks manually:

   ```bash
   python -m montecarlo interactive
   ```
   The wizard will guide you through entering task durations, optional risk events, and the simulation settings.

## PowerShell usage
The CLI can be executed from PowerShell without any changes. Activate your virtual environment (if you created one) and invoke the module just like in bash:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install pyyaml
python -m montecarlo run --config examples/config.yaml --output summary.json
```
The `summary.json` file will contain the simulation statistics as machine-readable JSON. Keep these commands in mind—they are intended to remain part of this README for future reference.

## Configuration file
The configuration file declares the paths of the input datasets and the simulation settings. The provided sample (`examples/config.yaml`) exposes the following keys:

| Key | Type | Description |
| --- | ---- | ----------- |
| `tasks` | path | CSV file describing each scheduled activity. |
| `risks` | path | Optional CSV file describing risk events. |
| `calendar` | path | Optional JSON file defining working-day rules. |
| `iterations` | int | Number of Monte Carlo iterations to run. |
| `confidence_levels` | list[float] | Percentile values to report (0–1). |
| `random_seed` | int | Optional seed for reproducible runs. |

## Data format
### Tasks (`examples/tasks.csv`)
| Column | Description |
| ------ | ----------- |
| `task_id` | Unique identifier used for dependencies. |
| `name` | Human-readable name. |
| `optimistic` | Minimum plausible duration (days). |
| `most_likely` | Most probable duration (days). |
| `pessimistic` | Maximum plausible duration (days). |
| `predecessors` | Semicolon-separated list of task IDs that must finish first. |

### Risks (`examples/risks.csv`)
| Column | Description |
| ------ | ----------- |
| `risk_id` | Identifier of the risk. |
| `description` | Brief explanation. |
| `probability` | Probability (0–1) that the risk occurs during a simulation iteration. |
| `affected_tasks` | Semicolon-separated task IDs impacted by the risk. |
| `impact_min`/`impact_mode`/`impact_max` | Triangular distribution of the *percentage* impact applied to the duration (e.g., `0.15` adds 15%). |

### Calendar (`examples/calendars.json`)
| Key | Description |
| --- | ----------- |
| `working_days` | Integers 0–6 representing Monday–Sunday working days. |
| `daily_capacity` | Workdays consumed per calendar day (1.0 = standard eight-hour day). |
| `holidays` | Optional list of offsets (in days) where work is not allowed. |

## Development
- Run the provided CLI examples in `cli_examples.sh` for quick sanity checks.
- Use the checklist in `tests/checklist.md` as a guide when extending the engine.

## License
This project is released under the MIT License. See [LICENSE](LICENSE) for details.
