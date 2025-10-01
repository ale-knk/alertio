"""Fixtures específicas para tests de Telegram."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from alertio.telegram import TelegramNotifier


REQUIRED_ENV_VARS = ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")


def _get_missing_env_vars() -> list[str]:
    return [name for name in REQUIRED_ENV_VARS if not os.getenv(name)]


@pytest.fixture(scope="session")
def telegram_credentials() -> dict[str, str]:
    """Obtiene las credenciales de Telegram o salta los tests si faltan."""

    missing = _get_missing_env_vars()
    if missing:
        pytest.skip(
            "Variables de entorno faltantes para tests de Telegram: "
            + ", ".join(missing)
        )

    return {
        "bot_token": os.environ["TELEGRAM_BOT_TOKEN"],
        "chat_id": os.environ["TELEGRAM_CHAT_ID"],
    }


@pytest.fixture()
def telegram_notifier(telegram_credentials: dict[str, str]) -> TelegramNotifier:
    """Crea un `TelegramNotifier` listo para usarse en tests."""

    return TelegramNotifier(**telegram_credentials)

