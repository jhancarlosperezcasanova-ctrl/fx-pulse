"""
Data fetcher module with multi-source fallback, exponential backoff, and SQLite caching.
Supports:
  1. exchangerate.host (Primary open FX API)
  2. Alpha Vantage (Intraday & Daily FX API)
  3. FRED St. Louis (Reference rates, DXY/DTWEXBGS, Real Effective Exchange Rates)
  4. yfinance (Ultra-robust fallback for all 40+ global tickers)
"""

import os
import time
import logging
import sqlite3
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import requests
from dotenv import load_dotenv

load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("FXDataFetcher")

# Global Currencies Catalog (41 FX pairs against USD)
# USD Base representation: Currency per 1 USD (or standard quotes: EUR, GBP, AUD, NZD)
CURRENCIES = [
    "EUR", "GBP", "JPY", "CHF", "AUD", "CAD", "NZD", "CNY", "MXN", "BRL",
    "ZAR", "INR", "KRW", "SGD", "NOK", "SEK", "DKK", "TRY", "PLN", "HUF",
    "CZK", "ILS", "THB", "MYR", "IDR", "PHP", "KES", "NGN", "COP", "CLP",
    "PEN", "ARS", "UAH", "VND", "TWD", "HKD", "AED", "SAR", "QAR", "KWD", "EGP"
]

# Tickers that are conventionally quoted as USD per Currency (indirect for USD)
INDIRECT_USD_PAIRS = {"EUR", "GBP", "AUD", "NZD"}

# IMF Special Drawing Rights (SDR) valuation basket weights (2022-2027 revision approx)
# USD: 43.38%, EUR: 29.31%, CNY: 12.28%, JPY: 7.59%, GBP: 7.44%
SDR_WEIGHTS = {
    "USD": 0.4338,
    "EUR": 0.2931,
    "CNY": 0.1228,
    "JPY": 0.0759,
    "GBP": 0.0744
}


class SQLiteCache:
    """Manages local SQLite database for caching historical FX timeseries."""
    
    def __init__(self, db_path: str = "cache/fx_cache.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS fx_history (
                    date TEXT,
                    currency TEXT,
                    close REAL,
                    source TEXT,
                    updated_at TEXT,
                    PRIMARY KEY (date, currency)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS macro_series (
                    date TEXT,
                    series_id TEXT,
                    value REAL,
                    updated_at TEXT,
                    PRIMARY KEY (date, series_id)
                )
            """)
            conn.commit()

    def get_currency_history(self, currency: str, start_date: str) -> pd.DataFrame:
        query = """
            SELECT date, close FROM fx_history 
            WHERE currency = ? AND date >= ? 
            ORDER BY date ASC
        """
        with self._get_connection() as conn:
            df = pd.read_sql_query(query, conn, params=(currency, start_date))
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"])
            df.set_index("date", inplace=True)
        return df

    def save_currency_history(self, currency: str, df: pd.DataFrame, source: str):
        if df.empty:
            return
        now_str = datetime.utcnow().isoformat()
        records = []
        for idx, row in df.iterrows():
            d_str = idx.strftime("%Y-%m-%d") if isinstance(idx, (pd.Timestamp, datetime)) else str(idx)
            val = float(row["close"])
            if not np.isnan(val):
                records.append((d_str, currency, val, source, now_str))

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany("""
                INSERT OR REPLACE INTO fx_history (date, currency, close, source, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, records)
            conn.commit()

    def get_macro(self, series_id: str, start_date: str) -> pd.DataFrame:
        query = "SELECT date, value FROM macro_series WHERE series_id = ? AND date >= ? ORDER BY date ASC"
        with self._get_connection() as conn:
            df = pd.read_sql_query(query, conn, params=(series_id, start_date))
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"])
            df.set_index("date", inplace=True)
        return df

    def save_macro(self, series_id: str, df: pd.DataFrame):
        if df.empty:
            return
        now_str = datetime.utcnow().isoformat()
        records = []
        for idx, row in df.iterrows():
            d_str = idx.strftime("%Y-%m-%d") if isinstance(idx, (pd.Timestamp, datetime)) else str(idx)
            val = float(row["value"])
            if not np.isnan(val):
                records.append((d_str, series_id, val, now_str))
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany("""
                INSERT OR REPLACE INTO macro_series (date, series_id, value, updated_at)
                VALUES (?, ?, ?, ?)
            """, records)
            conn.commit()


class FXDataFetcher:
    """
    Robust multi-source FX data provider with automatic failover, backoff, and caching.
    Ensures normalized representation: 1 USD = X Currency (e.g. USD/MXN = 18.0)
    """

    def __init__(self, db_path: str = "cache/fx_cache.db", cache_ttl_days: int = 1):
        self.cache = SQLiteCache(db_path)
        self.cache_ttl_days = cache_ttl_days
        self.alpha_vantage_key = os.getenv("ALPHA_VANTAGE_API_KEY", "")
        self.fred_api_key = os.getenv("FRED_API_KEY", "")
        self.exchangerate_host_key = os.getenv("EXCHANGERATE_HOST_API_KEY", "")

    def _fetch_with_backoff(self, url: str, params: dict, max_retries: int = 3) -> Optional[requests.Response]:
        """Executes GET request with exponential backoff strategy."""
        delay = 1.0
        for attempt in range(1, max_retries + 1):
            try:
                resp = requests.get(url, params=params, timeout=10)
                if resp.status_code == 200:
                    return resp
                elif resp.status_code in [429, 500, 502, 503, 504]:
                    logger.warning(f"HTTP {resp.status_code} received from {url}. Retrying in {delay}s...")
                    time.sleep(delay)
                    delay *= 2
                else:
                    logger.error(f"HTTP {resp.status_code} non-retryable for {url}.")
                    return None
            except requests.exceptions.RequestException as e:
                logger.warning(f"Request error: {e}. Retrying ({attempt}/{max_retries}) in {delay}s...")
                time.sleep(delay)
                delay *= 2
        return None

    def fetch_from_exchangerate_host(self, currency: str, start_date: str) -> Optional[pd.DataFrame]:
        """Attempt to fetch from exchangerate.host."""
        try:
            logger.info(f"[Primary 1] Intentando descargar {currency} desde exchangerate.host...")
            url = "https://api.exchangerate.host/timeframe"
            today_str = datetime.utcnow().strftime("%Y-%m-%d")
            params = {
                "start_date": start_date,
                "end_date": today_str,
                "source": "USD",
                "currencies": currency,
            }
            if self.exchangerate_host_key:
                params["access_key"] = self.exchangerate_host_key

            resp = self._fetch_with_backoff(url, params)
            if resp:
                data = resp.json()
                if data.get("success") and "quotes" in data:
                    records = []
                    pair_key = f"USD{currency}"
                    for d_str, rates in data["quotes"].items():
                        if pair_key in rates:
                            records.append({"date": pd.to_datetime(d_str), "close": float(rates[pair_key])})
                    if records:
                        df = pd.DataFrame(records).set_index("date").sort_index()
                        logger.info(f"✅ [SUCCESS] {currency} obtenido de exchangerate.host ({len(df)} registros)")
                        return df
            logger.warning(f"❌ [FAIL] exchangerate.host falló o requiere API key de pago para {currency}")
            return None
        except Exception as e:
            logger.warning(f"❌ [FAIL] Error en exchangerate.host para {currency}: {e}")
            return None

    def fetch_from_alphavantage(self, currency: str) -> Optional[pd.DataFrame]:
        """Attempt to fetch from Alpha Vantage FX_DAILY."""
        if not self.alpha_vantage_key:
            logger.info(f"ℹ️ [SKIP] Alpha Vantage omitido para {currency} (no se configuró ALPHA_VANTAGE_API_KEY en .env)")
            return None
        try:
            logger.info(f"[Primary 2] Intentando descargar {currency} desde Alpha Vantage...")
            url = "https://www.alphavantage.co/query"
            params = {
                "function": "FX_DAILY",
                "from_symbol": "USD",
                "to_symbol": currency,
                "outputsize": "full",
                "apikey": self.alpha_vantage_key
            }
            resp = self._fetch_with_backoff(url, params)
            if resp:
                data = resp.json()
                ts_key = "Time Series FX (Daily)"
                if ts_key in data:
                    records = []
                    for d_str, vals in data[ts_key].items():
                        records.append({"date": pd.to_datetime(d_str), "close": float(vals["4. close"])})
                    if records:
                        df = pd.DataFrame(records).set_index("date").sort_index()
                        logger.info(f"✅ [SUCCESS] {currency} obtenido de Alpha Vantage ({len(df)} registros)")
                        return df
            logger.warning(f"❌ [FAIL] Alpha Vantage falló para {currency} (rate limit o clave no válida)")
            return None
        except Exception as e:
            logger.warning(f"❌ [FAIL] Error en Alpha Vantage para {currency}: {e}")
            return None

    def fetch_from_yfinance(self, currency: str, start_date: str) -> Optional[pd.DataFrame]:
        """Fallback final: yfinance con ticker FX."""
        try:
            import yfinance as yf
            ticker_symbol = f"{currency}=X" if currency in ["EUR", "GBP", "AUD", "NZD", "JPY", "CAD", "CHF"] else f"USD{currency}=X"
            logger.info(f"[Fallback Final] Intentando descargar {currency} desde yfinance ({ticker_symbol})...")
            
            ticker = yf.Ticker(ticker_symbol)
            hist = ticker.history(start=start_date, auto_adjust=True)
            if hist.empty or "Close" not in hist:
                alt_symbol = f"{currency}USD=X" if not ticker_symbol.startswith("USD") else f"{currency}=X"
                ticker = yf.Ticker(alt_symbol)
                hist = ticker.history(start=start_date, auto_adjust=True)
            
            if not hist.empty and "Close" in hist:
                df = pd.DataFrame(index=pd.to_datetime(hist.index.date))
                raw_close = hist["Close"].values
                
                # Check quote convention: if ticker was EURUSD=X (1.08), convert to USD/EUR (Currency per 1 USD)
                # or standardize consistently: USD/Currency = 1 / (Currency/USD)
                # Standard convention for this dashboard: value = Units of Currency per 1 USD
                # Example: USD/EUR = 0.92, USD/MXN = 18.0, USD/JPY = 150.0
                first_val = float(raw_close[0])
                if currency in INDIRECT_USD_PAIRS and first_val < 5.0 and ("EUR=X" in ticker_symbol or "GBP=X" in ticker_symbol or "AUD=X" in ticker_symbol or "NZD=X" in ticker_symbol or "USD=X" in ticker_symbol):
                    # Quote is EUR per USD or USD per EUR? yfinance 'EUR=X' gives EUR per USD (~0.92) or USD per EUR (~1.08)
                    # For EUR=X, close is ~0.92 (EUR per USD).
                    # If ticker had EURUSD=X, close is ~1.08 (USD per EUR). Let's detect and standardize to:
                    # CURRENCY PER 1 USD (Units of local currency for 1 dollar)
                    if first_val > 1.0 and currency in ["EUR", "GBP"]:
                        # Ticker is GBP/USD (1.27), invert to USD/GBP (0.78)
                        df["close"] = 1.0 / raw_close
                    else:
                        df["close"] = raw_close
                else:
                    df["close"] = raw_close

                df.index.name = "date"
                df = df[~df.index.duplicated(keep="last")].sort_index()
                logger.info(f"✅ [SUCCESS] {currency} obtenido de yfinance ({len(df)} registros)")
                return df
            logger.warning(f"❌ [FAIL] yfinance no devolvió datos para {currency}")
            return None
        except Exception as e:
            logger.error(f"❌ [FAIL] Error en yfinance para {currency}: {e}")
            return None

    def fetch_dxy_index(self, start_date: str) -> pd.DataFrame:
        """
        Fetches the US Dollar Index (DXY).
        Attempts FRED series 'DTWEXBGS' (Trade Weighted U.S. Dollar Index: Broad, Goods and Services).
        Fallback to yfinance 'DX-Y.NYB' or 'UUP'.
        """
        # Check SQLite
        cached = self.cache.get_macro("DXY", start_date)
        if not cached.empty and (datetime.utcnow() - cached.index[-1]).days <= self.cache_ttl_days:
            logger.info("⚡ [CACHE] Índice DXY cargado desde SQLite")
            return cached

        # Try FRED
        if self.fred_api_key:
            try:
                logger.info("[FRED] Intentando descargar DTWEXBGS (Trade-Weighted Dollar) desde FRED...")
                url = "https://api.stlouisfed.org/fred/series/observations"
                params = {
                    "series_id": "DTWEXBGS",
                    "api_key": self.fred_api_key,
                    "file_type": "json",
                    "observation_start": start_date
                }
                resp = self._fetch_with_backoff(url, params)
                if resp:
                    obs = resp.json().get("observations", [])
                    records = []
                    for o in obs:
                        if o["value"] != ".":
                            records.append({"date": pd.to_datetime(o["date"]), "value": float(o["value"])})
                    if records:
                        df = pd.DataFrame(records).set_index("date").sort_index()
                        self.cache.save_macro("DXY", df)
                        logger.info(f"✅ [SUCCESS] DXY obtenido desde FRED ({len(df)} obs)")
                        return df
            except Exception as e:
                logger.warning(f"❌ [FAIL] FRED API DXY error: {e}")

        # Fallback yfinance
        try:
            import yfinance as yf
            logger.info("[Fallback Final] Descargando DXY desde yfinance ('DX-Y.NYB')...")
            t = yf.Ticker("DX-Y.NYB")
            h = t.history(start=start_date, auto_adjust=True)
            if h.empty:
                t = yf.Ticker("UUP")
                h = t.history(start=start_date, auto_adjust=True)
            if not h.empty and "Close" in h:
                df = pd.DataFrame({"value": h["Close"].values}, index=pd.to_datetime(h.index.date))
                df.index.name = "date"
                df = df[~df.index.duplicated(keep="last")].sort_index()
                self.cache.save_macro("DXY", df)
                logger.info(f"✅ [SUCCESS] DXY obtenido desde yfinance ({len(df)} obs)")
                return df
        except Exception as e:
            logger.error(f"❌ [FAIL] Error descargando DXY: {e}")

        # Synthetic fallback
        idx = pd.date_range(start=start_date, end=datetime.utcnow(), freq="B")
        return pd.DataFrame({"value": 104.0}, index=idx)

    def fetch_fed_funds_rate(self) -> float:
        """Fetches the current Federal Reserve effective funds rate (risk-free rate)."""
        cached = self.cache.get_macro("FED_FUNDS", (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d"))
        if not cached.empty:
            return float(cached["value"].iloc[-1]) / 100.0

        if self.fred_api_key:
            try:
                url = "https://api.stlouisfed.org/fred/series/observations"
                params = {
                    "series_id": "FEDFUNDS",
                    "api_key": self.fred_api_key,
                    "file_type": "json",
                    "sort_order": "desc",
                    "limit": 1
                }
                resp = requests.get(url, params=params, timeout=5)
                if resp.status_code == 200:
                    val = float(resp.json()["observations"][0]["value"])
                    df = pd.DataFrame({"value": [val]}, index=[pd.to_datetime(datetime.utcnow().date())])
                    self.cache.save_macro("FED_FUNDS", df)
                    logger.info(f"✅ Tasa Fed Funds obtenida de FRED: {val}%")
                    return val / 100.0
            except Exception as e:
                logger.warning(f"Error obteniendo tasa de FRED: {e}")

        # Default fallback to realistic current Fed policy rate
        return 0.0525

    def fetch_reer(self, currency: str, start_date: str) -> Optional[pd.DataFrame]:
        """
        Fetches Real Effective Exchange Rate (REER) if available via FRED or BIS series.
        Series mapping e.g. FRED: RB<CountryCode>BIS (Real Broad Effective Exchange Rate).
        """
        country_bis_map = {
            "EUR": "RBEUBIS", "GBP": "RBUKBIS", "JPY": "RBJPBIS", "CHF": "RBCHBIS",
            "CAD": "RBCABIS", "AUD": "RBAUBIS", "MXN": "RBMXBIS", "BRL": "RBBRBIS",
            "CNY": "RBCNBIS", "ZAR": "RBZABIS", "INR": "RBINBIS", "KRW": "RBKRBIS"
        }
        series_id = country_bis_map.get(currency)
        if not series_id or not self.fred_api_key:
            return None

        cached = self.cache.get_macro(f"REER_{currency}", start_date)
        if not cached.empty:
            return cached

        try:
            url = "https://api.stlouisfed.org/fred/series/observations"
            params = {
                "series_id": series_id,
                "api_key": self.fred_api_key,
                "file_type": "json",
                "observation_start": start_date
            }
            resp = self._fetch_with_backoff(url, params)
            if resp:
                obs = resp.json().get("observations", [])
                records = [{"date": pd.to_datetime(o["date"]), "value": float(o["value"])} for o in obs if o["value"] != "."]
                if records:
                    df = pd.DataFrame(records).set_index("date").sort_index()
                    self.cache.save_macro(f"REER_{currency}", df)
                    return df
        except Exception as e:
            logger.debug(f"REER lookup failed for {currency}: {e}")
        return None

    def get_currency_data(self, currency: str, years: int = 5) -> pd.DataFrame:
        """
        Unified method to retrieve currency timeseries with multi-level fallback:
        Cache -> exchangerate.host -> Alpha Vantage -> yfinance
        """
        start_date = (datetime.utcnow() - timedelta(days=years * 365 + 30)).strftime("%Y-%m-%d")

        # 1. Check local SQLite cache
        cached_df = self.cache.get_currency_history(currency, start_date)
        if not cached_df.empty:
            last_date = cached_df.index[-1]
            if (datetime.utcnow() - last_date).days <= self.cache_ttl_days:
                logger.info(f"⚡ [CACHE] {currency} cargado desde SQLite ({len(cached_df)} filas)")
                return cached_df

        # 2. Try Primary 1: exchangerate.host
        df = self.fetch_from_exchangerate_host(currency, start_date)
        source = "exchangerate.host"

        # 3. Try Primary 2: Alpha Vantage
        if df is None or df.empty:
            df = self.fetch_from_alphavantage(currency)
            source = "Alpha Vantage"

        # 4. Fallback: yfinance
        if df is None or df.empty:
            df = self.fetch_from_yfinance(currency, start_date)
            source = "yfinance"

        # 5. Save to Cache if successful
        if df is not None and not df.empty:
            self.cache.save_currency_history(currency, df, source)
            return df

        # If all failed, return empty DataFrame or cached stale data
        if not cached_df.empty:
            logger.warning(f"⚠️ [WARN] Todas las fuentes online fallaron. Utilizando caché antiguo de {currency}")
            return cached_df

        logger.error(f"❌ [CRITICAL] No se pudo obtener datos para la divisa: {currency}")
        return pd.DataFrame(columns=["close"])

    def get_all_currencies_data(self, currencies: List[str] = None, years: int = 5) -> pd.DataFrame:
        """
        Downloads and aggregates all currencies into a single wide DataFrame.
        Columns: Currency codes. Index: Datetime.
        Values: Units of currency per 1 USD (Standard base rate).
        """
        if currencies is None:
            currencies = CURRENCIES

        combined_series = {}
        for c in currencies:
            df = self.get_currency_data(c, years=years)
            if not df.empty and "close" in df:
                # Filter out zeroes and negative rates
                s = df["close"].replace(0, np.nan).dropna()
                combined_series[c] = s

        wide_df = pd.DataFrame(combined_series)
        # Forward-fill gaps for holidays/weekends, then backfill initial rows
        wide_df.ffill(inplace=True)
        wide_df.bfill(inplace=True)
        return wide_df
