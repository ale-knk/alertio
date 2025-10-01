# src/alertio/sqlite.py
from __future__ import annotations
import sqlite3
import json
import fcntl
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime, timedelta, timezone

# Esquema simplificado solo para alertas
SCHEMA = """
PRAGMA journal_mode=WAL;

-- Tabla para alertas de precio (DROP/RISE)
CREATE TABLE IF NOT EXISTS alerts_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    rule_key TEXT NOT NULL,
    triggered_at_utc TEXT NOT NULL,
    price REAL NOT NULL,
    message TEXT NOT NULL,
    alert_type TEXT NOT NULL,  -- 'drop', 'rise'
    metadata TEXT DEFAULT '{}',
    
    -- Campos útiles extraídos del metadata para consultas rápidas
    return_window INTEGER,     -- ventana de retorno (ej: 5, 10, 20)
    actual_return REAL,        -- retorno real que disparó la alerta
    threshold_return REAL      -- umbral configurado
);

-- Índices para alertas
CREATE INDEX IF NOT EXISTS idx_alerts_symbol_rule ON alerts_log(symbol, rule_key);
CREATE INDEX IF NOT EXISTS idx_alerts_type ON alerts_log(alert_type);
CREATE INDEX IF NOT EXISTS idx_alerts_date ON alerts_log(triggered_at_utc);
CREATE INDEX IF NOT EXISTS idx_alerts_symbol_type ON alerts_log(symbol, alert_type);
CREATE INDEX IF NOT EXISTS idx_alerts_window ON alerts_log(return_window);

-- Vista para estadísticas de alertas
CREATE VIEW IF NOT EXISTS alerts_stats AS
SELECT 
    alert_type,
    COUNT(*) as total_alerts,
    COUNT(DISTINCT symbol) as symbols_affected,
    AVG(ABS(actual_return)) as avg_return_magnitude,
    MIN(triggered_at_utc) as first_alert,
    MAX(triggered_at_utc) as last_alert
FROM alerts_log 
GROUP BY alert_type;
"""

@dataclass
class SQLiteStore:
    path: Path

    @classmethod
    def open(cls, path: str | Path) -> "SQLiteStore":
        """Abre o crea una base de datos SQLite con el esquema actualizado."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(p) as con:
            con.executescript(SCHEMA)
        return cls(path=p)

    def _conn(self) -> sqlite3.Connection:
        """Crea una conexión a la base de datos."""
        con = sqlite3.connect(self.path)
        con.row_factory = sqlite3.Row
        return con

    def _acquire_lock(self, timeout: int = 30) -> bool:
        """Adquiere un lock para operaciones de escritura."""
        lock_file = Path(f"{self.path}.lock")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                with open(lock_file, 'w') as f:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    return True
            except (IOError, OSError):
                time.sleep(0.1)
        return False

    def _release_lock(self) -> None:
        """Libera el lock de escritura."""
        lock_file = Path(f"{self.path}.lock")
        try:
            if lock_file.exists():
                lock_file.unlink()
        except (IOError, OSError):
            pass


    def insert_alert(self, symbol: str, rule_key: str, price: float, 
                     message: str, alert_type: str, metadata: Dict[str, Any] | None = None) -> None:
        """Inserta una alerta en la tabla alerts_log con control de concurrencia."""
        if not self._acquire_lock():
            raise RuntimeError("No se pudo adquirir lock para escribir en la base de datos")
        
        try:
            now = datetime.now(timezone.utc).isoformat()
            metadata = metadata or {}
            metadata_json = json.dumps(metadata)
            
            # Extraer campos útiles del metadata para consultas rápidas
            return_window = metadata.get('window')
            actual_return = metadata.get('actual_return')
            threshold_return = metadata.get('threshold')
            
            with self._conn() as con:
                con.execute(
                    "INSERT INTO alerts_log(symbol, rule_key, triggered_at_utc, price, message, alert_type, metadata, "
                    "return_window, actual_return, threshold_return) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (symbol, rule_key, now, price, message, alert_type, metadata_json, 
                     return_window, actual_return, threshold_return),
                )
        finally:
            self._release_lock()


    def get_alerts_by_type(self, alert_type: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Obtiene alertas por tipo."""
        with self._conn() as con:
            cur = con.execute(
                "SELECT * FROM alerts_log WHERE alert_type=? ORDER BY triggered_at_utc DESC LIMIT ?",
                (alert_type, limit)
            )
            return [dict(row) for row in cur.fetchall()]

    def get_alerts_by_symbol(self, symbol: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Obtiene alertas por símbolo."""
        with self._conn() as con:
            cur = con.execute(
                "SELECT * FROM alerts_log WHERE symbol=? ORDER BY triggered_at_utc DESC LIMIT ?",
                (symbol, limit)
            )
            return [dict(row) for row in cur.fetchall()]

    def get_recent_alerts(self, days: int = 7, limit: int = 100) -> List[Dict[str, Any]]:
        """Obtiene alertas recientes."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        with self._conn() as con:
            cur = con.execute(
                "SELECT * FROM alerts_log WHERE triggered_at_utc >= ? ORDER BY triggered_at_utc DESC LIMIT ?",
                (cutoff, limit)
            )
            return [dict(row) for row in cur.fetchall()]

    def get_alert_stats(self) -> List[Dict[str, Any]]:
        """Obtiene estadísticas de alertas usando la vista."""
        with self._conn() as con:
            cur = con.execute("SELECT * FROM alerts_stats ORDER BY total_alerts DESC")
            return [dict(row) for row in cur.fetchall()]

    def count_alerts_by_type(self, days: int = 30) -> Dict[str, int]:
        """Cuenta alertas por tipo en los últimos N días."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        with self._conn() as con:
            cur = con.execute(
                "SELECT alert_type, COUNT(*) as count FROM alerts_log "
                "WHERE triggered_at_utc >= ? GROUP BY alert_type",
                (cutoff,)
            )
            return {row["alert_type"]: row["count"] for row in cur.fetchall()}

    def count_consecutive_alerts(self, symbol: str, rule_key: str, days: int = 14) -> int:
        """Cuenta alertas consecutivas para un símbolo+regla en los últimos N días (default: 14)."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        with self._conn() as con:
            cur = con.execute(
                "SELECT COUNT(*) as count FROM alerts_log "
                "WHERE symbol=? AND rule_key=? AND triggered_at_utc >= ? "
                "ORDER BY triggered_at_utc DESC",
                (symbol, rule_key, cutoff)
            )
            return cur.fetchone()["count"]

    def get_alert_cooldown_info(self, symbol: str, rule_key: str) -> Dict[str, Any]:
        """Obtiene información completa de cooldown para un símbolo+regla."""
        with self._conn() as con:
            # Última alerta
            cur = con.execute(
                "SELECT * FROM alerts_log WHERE symbol=? AND rule_key=? "
                "ORDER BY triggered_at_utc DESC LIMIT 1",
                (symbol, rule_key)
            )
            last_alert = cur.fetchone()
            
            if not last_alert:
                return {
                    "last_alert_time": None,
                    "consecutive_alerts": 0,
                    "last_alert_data": None
                }
            
            # Contar alertas consecutivas en los últimos 14 días (reducido de 30 para ser menos agresivo)
            consecutive_count = self.count_consecutive_alerts(symbol, rule_key, 14)
            
            return {
                "last_alert_time": datetime.fromisoformat(
                    last_alert["triggered_at_utc"].replace("Z", "+00:00")
                ),
                "consecutive_alerts": consecutive_count,
                "last_alert_data": dict(last_alert)
            }

