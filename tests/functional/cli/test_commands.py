"""Tests funcionales para comandos principales de la CLI."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.functional.utils import CommandResult, run_cli_command


CLI_TEST_CASES = (
    pytest.param(
        dict(
            subcommand="scan",
            config="test-scan.yaml",
            db=None,
            extra_args=tuple(),
        ),
        id="scan",
    ),
    pytest.param(
        dict(
            subcommand="alert",
            config="test-alert.yaml",
            db="alerts.sqlite3",
            extra_args=tuple(),
        ),
        id="alert",
    ),
    pytest.param(
        dict(
            subcommand="daily-run",
            config="test-daily.yaml",
            db="daily.sqlite3",
            extra_args=tuple(),
        ),
        id="daily-run",
    ),
    pytest.param(
        dict(
            subcommand="weekly-summary",
            config="test-weekly.yaml",
            db=None,
            extra_args=tuple(),
        ),
        id="weekly-summary",
    ),
    pytest.param(
        dict(
            subcommand="opportunity-scan",
            config="test-opportunity.yaml",
            db=None,
            extra_args=("--threshold", "-0.05", "--windows", "5", "10", "20"),
        ),
        id="opportunity-scan",
    ),
)


@pytest.mark.cli
@pytest.mark.parametrize("case", CLI_TEST_CASES)
def test_cli_commands(
    case: dict[str, object],
    configs_dir: Path,
    temp_db_dir: Path,
) -> None:
    """Ejecuta los comandos principales de la CLI y verifica que finalicen correctamente."""

    subcommand = case["subcommand"]
    config_filename = case["config"]
    db_name = case["db"]
    extra_args = case["extra_args"]

    config_path = configs_dir / config_filename
    db_path = temp_db_dir / db_name if db_name else None

    result: CommandResult = run_cli_command(
        subcommand,
        config=config_path,
        db=db_path,
        extra_args=extra_args,
    )

    assert result.success, result.output

