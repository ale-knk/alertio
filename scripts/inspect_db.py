#!/usr/bin/env python3
"""
Script para inspeccionar bases de datos SQLite de alertas.
Detecta automáticamente si la base de datos tiene el esquema nuevo o legacy.
"""
import sys
import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

def check_schema_version(db_path: str) -> str:
    """Detecta la versión del esquema de la base de datos."""
    try:
        with sqlite3.connect(db_path) as con:
            cur = con.execute("PRAGMA table_info(alerts_log)")
            columns = [row[1] for row in cur.fetchall()]
            
            if 'alert_type' in columns and 'metadata' in columns:
                return "v2_typed"
            elif 'alert_type' in columns:
                return "v2_basic"
            else:
                return "v1_legacy"
    except Exception as e:
        return f"error: {e}"

def inspect_database(db_path: str) -> None:
    """Inspecciona una base de datos SQLite de alertas."""
    if not Path(db_path).exists():
        print(f"❌ Base de datos no encontrada: {db_path}")
        return
    
    schema_version = check_schema_version(db_path)
    print(f"🔍 Inspeccionando: {db_path}")
    print(f"📋 Esquema: {schema_version}")
    print()
    
    try:
        with sqlite3.connect(db_path) as con:
            con.row_factory = sqlite3.Row
            
            # Estadísticas generales
            cur = con.execute("SELECT COUNT(*) as total FROM alerts_log")
            total = cur.fetchone()["total"]
            print(f"📊 Total de alertas: {total}")
            
            if total == 0:
                print("   (Base de datos vacía)")
                return
            
            # Estadísticas por tipo (solo si existe la columna)
            if schema_version.startswith("v2"):
                print("\n📈 Por tipo de alerta:")
                cur = con.execute("""
                    SELECT alert_type, COUNT(*) as count 
                    FROM alerts_log 
                    GROUP BY alert_type 
                    ORDER BY count DESC
                """)
                for row in cur.fetchall():
                    emoji = {"drop": "📉", "rise": "📈", "weekly_summary": "📊"}.get(row["alert_type"], "⚠️")
                    print(f"   {emoji} {row['alert_type']}: {row['count']}")
            
            # Estadísticas por símbolo
            print("\n🏢 Por símbolo:")
            cur = con.execute("""
                SELECT symbol, COUNT(*) as count 
                FROM alerts_log 
                GROUP BY symbol 
                ORDER BY count DESC 
                LIMIT 10
            """)
            for row in cur.fetchall():
                print(f"   {row['symbol']}: {row['count']} alertas")
            
            # Últimas alertas
            print("\n🕐 Últimas 5 alertas:")
            if schema_version.startswith("v2"):
                cur = con.execute("""
                    SELECT datetime(triggered_at_utc) as fecha, 
                           symbol, alert_type, details, metadata
                    FROM alerts_log 
                    ORDER BY triggered_at_utc DESC 
                    LIMIT 5
                """)
                for row in cur.fetchall():
                    emoji = {"drop": "📉", "rise": "📈", "weekly_summary": "📊"}.get(row["alert_type"], "⚠️")
                    print(f"   {row['fecha']} | {emoji} {row['symbol']} ({row['alert_type']})")
                    
                    # Mostrar metadata si existe
                    if row["metadata"] and row["metadata"] != "{}":
                        try:
                            metadata = json.loads(row["metadata"])
                            if metadata:
                                print(f"     📝 Metadata: {metadata}")
                        except:
                            pass
                    
                    # Mostrar detalles truncados
                    details = row["details"][:80] + "..." if len(row["details"]) > 80 else row["details"]
                    print(f"     💬 {details}")
                    print()
            else:
                # Schema legacy
                cur = con.execute("""
                    SELECT datetime(triggered_at_utc) as fecha, 
                           symbol, rule_key, details
                    FROM alerts_log 
                    ORDER BY triggered_at_utc DESC 
                    LIMIT 5
                """)
                for row in cur.fetchall():
                    print(f"   {row['fecha']} | {row['symbol']} ({row['rule_key']})")
                    details = row["details"][:80] + "..." if len(row["details"]) > 80 else row["details"]
                    print(f"     💬 {details}")
                    print()
            
            # Estadísticas temporales
            print("📅 Actividad por fecha (últimos 7 días):")
            cur = con.execute("""
                SELECT DATE(triggered_at_utc) as fecha, COUNT(*) as count
                FROM alerts_log 
                WHERE triggered_at_utc >= datetime('now', '-7 days')
                GROUP BY DATE(triggered_at_utc)
                ORDER BY fecha DESC
            """)
            for row in cur.fetchall():
                print(f"   {row['fecha']}: {row['count']} alertas")
                
    except Exception as e:
        print(f"❌ Error al inspeccionar la base de datos: {e}")

def main():
    if len(sys.argv) != 2:
        print("Uso: python inspect_db.py <ruta_base_datos>")
        print("\nEjemplos:")
        print("  python inspect_db.py data/alerts.sqlite3")
        print("  python inspect_db.py data/typed_alerts.sqlite3")
        sys.exit(1)
    
    db_path = sys.argv[1]
    inspect_database(db_path)

if __name__ == "__main__":
    main()
