from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable
import pandas as pd
import yfinance as yf

@dataclass
class PriceData:
    ohlcv: pd.DataFrame  # columns: Open, High, Low, Close, Adj Close, Volume (index: Datetime)

def _utc_today() -> datetime:
    return datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

def fetch_yfinance(symbol: str, lookback_days: int = 400) -> PriceData:
    end = _utc_today() + timedelta(days=1)  # include current EOD if available
    start = end - timedelta(days=lookback_days + 10)  # margin for holidays
    df = yf.download(
        symbol,
        start=start.date().isoformat(),
        end=end.date().isoformat(),
        auto_adjust=False,
        progress=False,
        interval="1d",
        group_by="ticker",
        threads=True,
    )
    if df.empty:
        raise RuntimeError(f"No data returned for {symbol} from yfinance")
    df = df.tz_localize(None) if df.index.tz is not None else df
    
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(1)
    
    df = df.rename(columns=str.title) 
    
    # Ensure expected columns
    needed = {"Open", "High", "Low", "Close", "Adj Close", "Volume"}
    missing = needed.difference(df.columns)
    if missing:
        raise RuntimeError(f"Missing columns for {symbol}: {missing}")
    df = df.sort_index()
    return PriceData(ohlcv=df)

def fetch_batch(symbols: Iterable[str], lookback_days: int = 400) -> Dict[str, PriceData]:
    out: Dict[str, PriceData] = {}
    for s in symbols:
        out[s] = fetch_yfinance(s, lookback_days=lookback_days)
    return out


def compute_returns(ohlcv: pd.DataFrame, *,
                   return_windows: list[int] = [1, 5, 10, 20]) -> pd.DataFrame:
    """
    Calcula retornos por ventanas de tiempo para un DataFrame OHLCV.
    
    Args:
        ohlcv: DataFrame con datos OHLCV (debe tener columna 'Adj Close')
        return_windows: Lista de ventanas en días para calcular retornos
    
    Returns:
        DataFrame con precio de cierre y retornos por ventana
    """
    close = ohlcv["Adj Close"]
    out = pd.DataFrame(index=ohlcv.index)
    out["close"] = close
    
    # Calcular retornos para cada ventana
    for window in return_windows:
        out[f"return_{window}d"] = close.pct_change(window)
    
    return out