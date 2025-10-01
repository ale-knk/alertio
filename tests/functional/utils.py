"""Utilidades compartidas para pruebas funcionales."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(slots=True)
class CommandResult:
    """Resultado de ejecutar un comando CLI."""

    command: Sequence[str]
    exit_code: int
    stdout: str
    stderr: str
    duration: float

    @property
    def success(self) -> bool:
        return self.exit_code == 0

    @property
    def output(self) -> str:
        return self.stdout + self.stderr


def build_cli_command(
    subcommand: str,
    *,
    config: Path | None = None,
    db: Path | None = None,
    extra_args: Iterable[str] | None = None,
) -> list[str]:
    """Construye el comando para invocar la CLI de Alertio."""

    cmd = [sys.executable, "-m", "alertio.cli", subcommand]

    if config is not None:
        cmd.extend(["-c", str(config)])

    if db is not None:
        cmd.extend(["--db", str(db)])

    if extra_args:
        cmd.extend(list(extra_args))

    return cmd


def run_cli_command(
    subcommand: str,
    *,
    config: Path | None = None,
    db: Path | None = None,
    extra_args: Iterable[str] | None = None,
    timeout: int = 120,
    env: dict[str, str] | None = None,
) -> CommandResult:
    """Ejecuta la CLI de Alertio y retorna el resultado."""

    command = build_cli_command(subcommand, config=config, db=db, extra_args=extra_args)

    full_env = os.environ.copy()
    if env:
        full_env.update(env)

    start = time.time()
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=full_env,
    )

    duration = time.time() - start
    return CommandResult(
        command=command,
        exit_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        duration=duration,
    )

