"""Fixtures compartidas para pruebas funcionales."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def project_root() -> Path:
    """Retorna la raíz del proyecto."""

    return Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def configs_dir(project_root: Path) -> Path:
    """Directorio de archivos de configuración de tests."""

    return project_root / "tests" / "configs"


@pytest.fixture()
def temp_db_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Directorio temporal para bases de datos SQLite de tests funcionales."""

    return tmp_path_factory.mktemp("func_db")

