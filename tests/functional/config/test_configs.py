"""Validación funcional de archivos de configuración."""

from __future__ import annotations

from pathlib import Path

import pytest

from alertio.config import load_settings


CONFIG_FILES = (
    "test-scan.yaml",
    "test-alert.yaml",
    "test-daily.yaml",
    "test-weekly.yaml",
    "test-opportunity.yaml",
)


@pytest.mark.config
@pytest.mark.parametrize("filename", CONFIG_FILES)
def test_configs_load_successfully(configs_dir: Path, filename: str) -> None:
    """Todos los archivos de configuración deben cargarse sin errores."""

    config_path = configs_dir / filename
    settings = load_settings(config_path)

    assert settings.tickers, "La configuración debe incluir al menos un ticker"

