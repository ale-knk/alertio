# src/alertio/cli.py
from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd

from alertio.config import load_settings
from alertio.fetcher import fetch_batch, compute_returns
from alertio.sqlite import SQLiteStore
from alertio.alerts import prepare_alerts, send_and_log_alerts

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser("alertio")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("scan", help="Fetch data and print latest market data")
    p_run.add_argument("-c", "--config", type=str, required=True)
    p_run.add_argument("--csv-out", type=str, default=None)

    p_alert = sub.add_parser("alert", help="Evaluate rules and send alerts via Telegram, with cooldown")
    p_alert.add_argument("-c", "--config", type=str, required=True)
    p_alert.add_argument("--db", type=str, default="data/alerts.sqlite3")

    p_daily = sub.add_parser("daily-run", help="Fetch → evaluate → alert (full pipeline)")
    p_daily.add_argument("-c", "--config", type=str, required=True)
    p_daily.add_argument("--db", type=str, default="data/alerts.sqlite3")
    p_daily.add_argument("--csv-out", type=str, default=None)
    p_daily.add_argument("--include-weekly", action="store_true", help="Incluir resumen semanal")
    
    p_weekly = sub.add_parser("weekly-summary", help="Generar solo resumen semanal")
    p_weekly.add_argument("-c", "--config", type=str, required=True)
    p_weekly.add_argument("--db", type=str, default="data/alerts.sqlite3")
    
    return p

def load_data(cfg_path: str, *, return_windows: list[int] | None = None) -> tuple:
    """
    Carga configuración y datos de mercado con retornos calculados.
    
    Args:
        cfg_path: Ruta al archivo de configuración
        return_windows: Ventanas de retorno a calcular. Si es None, usa las de configuración.
    
    Returns:
        Tupla (settings, current_data) donde current_data es dict[symbol, pd.Series]
    """
    settings = load_settings(cfg_path)
    symbols = [t.symbol for t in settings.tickers]
    batch = fetch_batch(symbols, lookback_days=settings.lookback_days)

    # Determinar ventanas de retorno a usar
    if return_windows is None:
        return_windows = settings.returns.windows
    
    current_data: dict[str, pd.Series] = {}
    for sym, pdata in batch.items():
        returns_df = compute_returns(
            pdata.ohlcv,
            return_windows=return_windows,
        )
        current_data[sym] = returns_df.dropna().iloc[-1]
    
    return settings, current_data

def cmd_scan(ns) -> int:
    settings, current_data = load_data(ns.config)
    rows = []
    for sym, row in current_data.items():
        entry = {
            "symbol": sym,
            "close": round(float(row["close"]), 4),
        }
        # Agregar retornos por ventana
        for window in settings.returns.windows:
            return_col = f"return_{window}d"
            if return_col in row.index:
                entry[f"ret_{window}d"] = round(float(row[return_col]) * 100, 2)
        rows.append(entry)

    df = pd.DataFrame(rows).set_index("symbol").sort_index()
    with pd.option_context("display.max_columns", None, "display.width", 150):
        print(df)
    return 0

def cmd_alert(ns) -> int:
    settings, current_data = load_data(ns.config)
    store = SQLiteStore.open(ns.db)
    alerts = prepare_alerts(settings, current_data)
    sent = send_and_log_alerts(settings, store, alerts)
    print(f"Sent {sent} alerts.")
    return 0

def cmd_daily_run(ns) -> int:
    # Optionally dump CSVs for inspection
    if ns.csv_out:
        Path(ns.csv_out).mkdir(parents=True, exist_ok=True)
    # Cargar datos con ventanas de configuración para alertas
    settings, current_data = load_data(ns.config)
    if ns.csv_out:
        # write per-symbol returns snapshot
        for sym, row in current_data.items():
            pd.DataFrame(row).to_csv(Path(ns.csv_out) / f"{sym.replace('^','')}_current.csv", header=False)
    store = SQLiteStore.open(ns.db)
    
    # Generar alertas normales
    alerts = prepare_alerts(settings, current_data)
    sent = send_and_log_alerts(settings, store, alerts)
    
    # Enviar resumen semanal si se solicita
    include_weekly = getattr(ns, 'include_weekly', False)
    if include_weekly:
        from alertio.alerts import send_weekly_summary
        summary_sent = send_weekly_summary(settings, current_data, store)
        if summary_sent:
            sent += 1  # Contar el resumen como enviado
    
    # Mostrar desglose por tipo de alerta
    if sent > 0:
        _print_alerts_summary(alerts, sent)
    
    print(f"Daily run: {len(current_data)} symbols, {sent} alerts sent.")
    return 0

def cmd_weekly_summary(ns) -> int:
    """Comando para generar solo resumen semanal"""
    # Usar ventanas estándar fijas para resúmenes
    settings, current_data = load_data(ns.config, return_windows=[1, 5, 10, 20])
    
    # Generar y enviar resumen semanal directamente (sin cooldown para comandos manuales)
    from alertio.alerts import send_weekly_summary
    summary_sent = send_weekly_summary(settings, current_data)
    
    if summary_sent:
        print("✅ Resumen semanal enviado correctamente")
        return 0
    else:
        print("❌ Error enviando resumen semanal o no hay datos suficientes")
        return 1

def _print_alerts_summary(alerts, sent_count):
    """Imprime resumen de alertas por tipo"""
    
    type_counts = {}
    for alert in alerts:
        alert_type = alert.alert_type.value
        type_counts[alert_type] = type_counts.get(alert_type, 0) + 1
    
    if type_counts:
        print("📊 Alertas por tipo:")
        type_names = {
            'drop': '📉 Caídas',
            'rise': '📈 Subidas'
        }
        for alert_type, count in type_counts.items():
            name = type_names.get(alert_type, f"⚠️ {alert_type}")
            print(f"  {name}: {count}")
        print()

def main(args: list[str] | None = None) -> int:
    parser = build_parser()
    ns = parser.parse_args(args=args)
    if ns.cmd == "scan":
        return cmd_scan(ns)
    if ns.cmd == "alert":
        return cmd_alert(ns)
    if ns.cmd == "daily-run":
        return cmd_daily_run(ns)
    if ns.cmd == "weekly-summary":
        return cmd_weekly_summary(ns)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())