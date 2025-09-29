# src/alertio/sqlite.py
from __future__ import annotations
import sqlite3
import json
import fcntl
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta, timezone

# Esquema con tablas separadas para alertas y summaries
SCHEMA = """
PRAGMA journal_mode=WAL;

-- Tabla específica para alertas de precio (DROP/RISE)
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

-- Tabla específica para resúmenes de mercado
CREATE TABLE IF NOT EXISTS summaries_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    summary_type TEXT NOT NULL,        -- 'weekly', 'monthly'
    generated_at_utc TEXT NOT NULL,
    symbols_analyzed INTEGER NOT NULL,
    best_performer_symbol TEXT,
    best_performer_return REAL,
    worst_performer_symbol TEXT,
    worst_performer_return REAL,
    average_return REAL,
    period_days INTEGER NOT NULL,
    summary_data TEXT NOT NULL,        -- JSON completo del resumen
    sent_successfully BOOLEAN DEFAULT 1
);

-- Índices para alertas
CREATE INDEX IF NOT EXISTS idx_alerts_symbol_rule ON alerts_log(symbol, rule_key);
CREATE INDEX IF NOT EXISTS idx_alerts_type ON alerts_log(alert_type);
CREATE INDEX IF NOT EXISTS idx_alerts_date ON alerts_log(triggered_at_utc);
CREATE INDEX IF NOT EXISTS idx_alerts_symbol_type ON alerts_log(symbol, alert_type);
CREATE INDEX IF NOT EXISTS idx_alerts_window ON alerts_log(return_window);

-- Índices para summaries
CREATE INDEX IF NOT EXISTS idx_summaries_type ON summaries_log(summary_type);
CREATE INDEX IF NOT EXISTS idx_summaries_date ON summaries_log(generated_at_utc);
CREATE INDEX IF NOT EXISTS idx_summaries_type_date ON summaries_log(summary_type, generated_at_utc);

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

-- Vista para estadísticas de summaries
CREATE VIEW IF NOT EXISTS summaries_stats AS
SELECT 
    summary_type,
    COUNT(*) as total_summaries,
    AVG(symbols_analyzed) as avg_symbols_analyzed,
    AVG(average_return) as avg_market_return,
    MIN(generated_at_utc) as first_summary,
    MAX(generated_at_utc) as last_summary
FROM summaries_log 
GROUP BY summary_type;
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

    def last_alert_time(self, symbol: str, rule_key: str) -> Optional[datetime]:
        """Obtiene la última vez que se disparó una alerta específica."""
        with self._conn() as con:
            cur = con.execute(
                "SELECT triggered_at_utc FROM alerts_log WHERE symbol=? AND rule_key=? "
                "ORDER BY id DESC LIMIT 1",
                (symbol, rule_key),
            )
            row = cur.fetchone()
            if not row:
                return None
            return datetime.fromisoformat(row["triggered_at_utc"].replace("Z", "+00:00"))

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

    # ========== MÉTODOS PARA SUMMARIES ==========
    
    def last_summary_time(self, summary_type: str) -> Optional[datetime]:
        """Obtiene la última vez que se generó un resumen de un tipo específico."""
        with self._conn() as con:
            cur = con.execute(
                "SELECT generated_at_utc FROM summaries_log WHERE summary_type=? "
                "ORDER BY id DESC LIMIT 1",
                (summary_type,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return datetime.fromisoformat(row["generated_at_utc"].replace("Z", "+00:00"))
    
    def insert_summary(self, summary_type: str, market_summary, sent_successfully: bool = True) -> None:
        """Inserta un resumen de mercado en la tabla summaries_log con control de concurrencia."""
        if not self._acquire_lock():
            raise RuntimeError("No se pudo adquirir lock para escribir en la base de datos")
        
        try:
            now = datetime.now(timezone.utc).isoformat()
            
            # Extraer datos del MarketSummary
            best = market_summary.best_performer
            worst = market_summary.worst_performer
            
            summary_data_json = json.dumps({
                'period_name': market_summary.period_name,
                'symbols_analyzed': market_summary.symbols_analyzed,
                'best_performer': best,
                'worst_performer': worst,
                'average_return': market_summary.average_return,
                'period_days': market_summary.period_days,
                'summary_data': market_summary.summary_data,
                'timestamp': market_summary.timestamp.isoformat()
            })
            
            with self._conn() as con:
                con.execute(
                    "INSERT INTO summaries_log(summary_type, generated_at_utc, symbols_analyzed, "
                    "best_performer_symbol, best_performer_return, worst_performer_symbol, "
                    "worst_performer_return, average_return, period_days, summary_data, sent_successfully) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        summary_type, now, market_summary.symbols_analyzed,
                        best.get('symbol'), best.get(f'return_{market_summary.period_days}d'),
                        worst.get('symbol'), worst.get(f'return_{market_summary.period_days}d'),
                        market_summary.average_return, market_summary.period_days,
                        summary_data_json, sent_successfully
                    ),
                )
        finally:
            self._release_lock()
    
    def get_summaries_by_type(self, summary_type: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Obtiene resúmenes por tipo."""
        with self._conn() as con:
            cur = con.execute(
                "SELECT * FROM summaries_log WHERE summary_type=? ORDER BY generated_at_utc DESC LIMIT ?",
                (summary_type, limit)
            )
            return [dict(row) for row in cur.fetchall()]
    
    def get_recent_summaries(self, days: int = 30, limit: int = 50) -> List[Dict[str, Any]]:
        """Obtiene resúmenes recientes."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        with self._conn() as con:
            cur = con.execute(
                "SELECT * FROM summaries_log WHERE generated_at_utc >= ? ORDER BY generated_at_utc DESC LIMIT ?",
                (cutoff, limit)
            )
            return [dict(row) for row in cur.fetchall()]
    
    def get_summary_stats(self) -> List[Dict[str, Any]]:
        """Obtiene estadísticas de resúmenes usando la vista."""
        with self._conn() as con:
            cur = con.execute("SELECT * FROM summaries_stats ORDER BY total_summaries DESC")
            return [dict(row) for row in cur.fetchall()]

    # ========== MÉTODOS DE COOLDOWN ==========

    @staticmethod
    def is_in_cooldown(last_ts: Optional[datetime], cooldown_days: int) -> bool:
        """Verifica si una alerta está en período de cooldown."""
        if last_ts is None:
            return False
        return datetime.now(timezone.utc) - last_ts < timedelta(days=cooldown_days)