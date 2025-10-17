# Monte Carlo Schedule Simulator – Specification Brief

The goal of this project is to provide a reproducible command line tool that can perform Monte Carlo simulations for project schedules. The simulator consumes structured data sets describing tasks, risk events, and working calendars, and then returns statistics that help planners estimate completion likelihoods.

## Functional requirements
- Load activity definitions from a CSV file with optimistic/likely/pessimistic durations and precedence relationships.
- Support optional risk definitions that inflate task durations when triggered.
- Allow providing a calendar file to respect working days and non-working periods.
- Execute `N` Monte Carlo iterations (configurable) and output completion statistics.
- Return percentile metrics, critical-path insights, and base statistics.

## Non-functional requirements
- Deterministic behaviour when supplied with a random seed.
- Input validation with clear error messages for misconfigured datasets.
- Plain Python implementation without external system dependencies beyond PyYAML.
- Usable from Unix shells and Windows PowerShell alike.

## Interfaces
- CLI entry point: `python -m montecarlo run --config <path>`
- Optional `--output` flag to persist summary statistics to a JSON file.

## Sample outputs
Example console output:
```
Simulation complete
------------------
Iterations: 5000
Mean project duration: 42.18 days
Median project duration: 41.66 days
P 50: 41.66 days
P 75: 45.32 days
P 90: 49.84 days
Critical path (most frequent):
DESIGN -> BUILD -> TEST -> LAUNCH
```

## Acceptance criteria
- Running the CLI with the bundled examples produces a summary without errors.
- README contains permanent instructions for bash and PowerShell usage.
- Unit conversion assumptions (days) are documented alongside the data formats.
