"""Tests funcionales para integración con Telegram."""

from __future__ import annotations

import pytest

from tests.functional.utils import CommandResult, run_cli_command


@pytest.mark.telegram
def test_telegram_connection(telegram_notifier) -> None:
    """El notificador debe poder validar la conexión con Telegram."""

    assert telegram_notifier.test_connection()


@pytest.mark.telegram
def test_telegram_bot_info(telegram_notifier) -> None:
    """Recupera información básica del bot."""

    info = telegram_notifier.get_bot_info()
    assert info and "username" in info


@pytest.mark.telegram
@pytest.mark.cli
def test_cli_alert_with_telegram(configs_dir, temp_db_dir) -> None:
    """Ejecuta el comando alert con la configuración específica de Telegram."""

    config_path = configs_dir / "test-telegram.yaml"

    db_path = temp_db_dir / "telegram.sqlite3"

    result: CommandResult = run_cli_command(
        "alert",
        config=config_path,
        db=db_path,
    )

    assert result.success, result.output

