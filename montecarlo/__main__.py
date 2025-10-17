"""Module entry point for running the CLI with ``python -m montecarlo``."""
from .cli import run_cli


def main() -> int:
    return run_cli()


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
