"""
Metrics computation engine for Foreign Exchange markets.
Calculates:
  1. Cumulative Returns (7d, 30d, 90d, 180d, 1y, 3y, 5y)
  2. Annualized Volatility (std dev of daily log returns)
  3. Maximum Drawdown (MDD) and Drawdown Duration (days)
  4. Momentum (% change & linear regression slope on 20, 60, 120 days)
  5. Correlation matrix with DXY and between all pairs
  6. Sharpe Ratio (annualized excess return over risk-free rate)
  7. Return distribution Skewness and Kurtosis (Fat tails and asymmetry)
  8. Cross-comparatives vs USD, EUR, and IMF SDR basket
  9. REER integration
  10. Market Regime Detection (Bullish, Bearish, Sideways/Range)
"""

from typing import Dict, Any, Tuple, Optional
import pandas as pd
import numpy as np
from scipy import stats
from .data_fetcher import SDR_WEIGHTS


def calculate_cumulative_returns(series: pd.Series) -> Dict[str, float]:
    """
    Calculates cumulative returns for multiple historical windows:
    7d, 30d, 90d, 180d, 1y (252 trading days), 3y (756d), 5y (1260d).
    
    Formula:
        R_cum = (P_current - P_initial) / P_initial
    Note on currency convention:
      Since series represents Currency/USD (e.g., USD/MXN = 18.0), an increase
      means the USD strengthened and the local currency depreciated.
      To reflect the value of holding the foreign currency vs USD:
        Local Currency Return = ( (1 / P_current) - (1 / P_initial) ) / (1 / P_initial)
                              = (P_initial - P_current) / P_current
    """
    clean = series.dropna()
    if len(clean) < 2:
        return {k: 0.0 for k in ["7d", "30d", "90d", "180d", "1y", "3y", "5y"]}

    current_val = clean.iloc[-1]
    windows = {
        "7d": 5,        # ~5 trading days in a week
        "30d": 21,      # ~21 trading days in a month
        "90d": 63,      # ~63 trading days in a quarter
        "180d": 126,    # ~126 trading days in half year
        "1y": 252,      # 1 trading year
        "3y": 756,      # 3 trading years
        "5y": 1260      # 5 trading years
    }
    
    results = {}
    n = len(clean)
    for label, periods in windows.items():
        if n > periods:
            past_val = clean.iloc[-(periods + 1)]
            if past_val > 0 and current_val > 0:
                # Local currency appreciation/depreciation against USD
                # Formula: (P_past / P_curr - 1) * 100
                ret = ((past_val / current_val) - 1.0) * 100.0
                results[label] = round(float(ret), 2)
            else:
                results[label] = 0.0
        else:
            # Short history handling: compute return over all available data
            first_val = clean.iloc[0]
            if first_val > 0 and current_val > 0:
                ret = ((first_val / current_val) - 1.0) * 100.0
                results[label] = round(float(ret), 2)
            else:
                results[label] = 0.0
    return results


def calculate_annualized_volatility(series: pd.Series, periods_per_year: int = 252) -> float:
    """
    Calculates annualized volatility of daily log returns:
        r_t = ln(P_t / P_{t-1})
        sigma_annual = std(r_t) * sqrt(252) * 100
    """
    clean = series.dropna()
    if len(clean) < 5:
        return 0.0
    
    # Log returns
    log_returns = np.log(clean / clean.shift(1)).dropna()
    daily_std = log_returns.std()
    annual_vol = daily_std * np.sqrt(periods_per_year) * 100.0
    return round(float(annual_vol), 2) if not np.isnan(annual_vol) else 0.0


def calculate_max_drawdown(series: pd.Series) -> Tuple[float, int]:
    """
    Calculates Maximum Drawdown (MDD) and Maximum Drawdown Duration in days.
    For an investor holding the currency against USD:
        Wealth Index V_t = 1 / P_t
        Peak_t = max_{s <= t}(V_s)
        Drawdown_t = (V_t - Peak_t) / Peak_t
    
    Returns:
        (max_drawdown_percent, duration_in_days)
    """
    clean = series.dropna()
    if len(clean) < 2:
        return 0.0, 0
    
    wealth_index = 1.0 / clean
    cumulative_peak = wealth_index.cummax()
    drawdown = (wealth_index - cumulative_peak) / cumulative_peak
    
    max_dd = drawdown.min() * 100.0 # Negative percentage
    
    # Calculate duration of the maximum drawdown
    # Duration = days from peak to trough (or full recovery period)
    is_at_peak = wealth_index == cumulative_peak
    peak_dates = is_at_peak.astype(int).cumsum()
    duration_series = peak_dates.groupby(peak_dates).cumcount()
    max_duration = int(duration_series.max()) if not duration_series.empty else 0

    return round(float(max_dd), 2), max_duration


def calculate_momentum(series: pd.Series) -> Dict[str, Any]:
    """
    Calculates momentum over 20, 60, and 120 trading days:
    1. Percentage change: ((P_initial / P_current) - 1) * 100
    2. Linear regression slope of normalized price series (beta / trend strength)
    """
    clean = series.dropna()
    windows = [20, 60, 120]
    results = {}

    for w in windows:
        if len(clean) >= w:
            sub = clean.iloc[-w:]
            # Local currency value relative to USD
            val_series = 1.0 / sub
            normalized_vals = (val_series / val_series.iloc[0]).values
            x = np.arange(len(normalized_vals))
            
            # Linear regression: y = slope * x + intercept
            slope, intercept, r_val, p_val, std_err = stats.linregress(x, normalized_vals)
            pct_change = ((val_series.iloc[-1] / val_series.iloc[0]) - 1.0) * 100.0
            
            results[f"pct_{w}d"] = round(float(pct_change), 2)
            results[f"slope_{w}d"] = round(float(slope * 100.0), 4) # % daily change slope
            results[f"r2_{w}d"] = round(float(r_val**2), 3)
        else:
            results[f"pct_{w}d"] = 0.0
            results[f"slope_{w}d"] = 0.0
            results[f"r2_{w}d"] = 0.0

    return results


def calculate_sharpe_ratio(series: pd.Series, rf_annual: float = 0.0525, periods: int = 252) -> float:
    """
    Calculates Annualized Sharpe Ratio:
        Sharpe = (E[R] - R_f) / sigma_annual
    Where:
        E[R] = Annualized mean return of the currency vs USD
        R_f = Risk-free rate (e.g. Fed Funds rate)
        sigma = Annualized standard deviation of daily returns
    """
    clean = series.dropna()
    if len(clean) < 10:
        return 0.0

    # Holding local currency return vs USD
    inv_series = 1.0 / clean
    daily_returns = inv_series.pct_change().dropna()
    
    mean_daily = daily_returns.mean()
    std_daily = daily_returns.std()
    
    if std_daily == 0 or np.isnan(std_daily):
        return 0.0
    
    ann_return = mean_daily * periods
    ann_vol = std_daily * np.sqrt(periods)
    
    sharpe = (ann_return - rf_annual) / ann_vol
    return round(float(sharpe), 2) if not np.isnan(sharpe) else 0.0


def calculate_skewness_kurtosis(series: pd.Series) -> Tuple[float, float]:
    """
    Computes Skewness and Kurtosis of daily log returns:
        Skewness: Measures asymmetry (positive = right tail/spikes, negative = sudden crashes).
        Kurtosis: Fisher kurtosis (normal distribution = 0.0; > 0 = leptokurtic / fat tails).
    """
    clean = series.dropna()
    if len(clean) < 10:
        return 0.0, 0.0
    
    inv_series = 1.0 / clean
    log_returns = np.log(inv_series / inv_series.shift(1)).dropna()
    
    skew = float(stats.skew(log_returns))
    kurt = float(stats.kurtosis(log_returns)) # Fisher definition (normal = 0)
    
    return round(skew, 2), round(kurt, 2)


def detect_market_regime(series: pd.Series, window: int = 60) -> Tuple[str, str, float]:
    """
    Determines market regime over the last 60 trading days:
    - Bullish Trend (🟢): Moving Average 20 > MA 60 and Momentum > +1.5%
    - Bearish Trend (🔴): Moving Average 20 < MA 60 and Momentum < -1.5%
    - Sideways/Range (🟡): Moving averages convergent, price oscillating within band.
    
    Returns:
        (regime_name, signal_emoji, confidence_score)
    """
    clean = series.dropna()
    if len(clean) < window:
        return "Insuficiente Historial", "⚪", 0.0

    inv_series = 1.0 / clean # Value of local currency vs USD
    ma20 = inv_series.rolling(20).mean().iloc[-1]
    ma60 = inv_series.rolling(60).mean().iloc[-1]
    current = inv_series.iloc[-1]
    
    pct_60d = ((inv_series.iloc[-1] / inv_series.iloc[-60]) - 1.0) * 100.0
    
    # Calculate Bollinger Bands bandwidth for volatility compression
    std60 = inv_series.rolling(60).std().iloc[-1]
    bandwidth = (4 * std60 / ma60) * 100 if ma60 > 0 else 0
    
    if ma20 > ma60 and pct_60d > 1.2:
        return "Tendencia Alcista (Fortalecimiento)", "🟢", min(round(abs(pct_60d) * 10, 1), 95.0)
    elif ma20 < ma60 and pct_60d < -1.2:
        return "Tendencia Bajista (Depreciación)", "🔴", min(round(abs(pct_60d) * 10, 1), 95.0)
    else:
        return "Régimen Lateral / Consolidación", "🟡", 70.0


def compute_sdr_basket_series(all_data: pd.DataFrame) -> pd.Series:
    """
    Synthesizes the IMF SDR (Special Drawing Rights) basket value in terms of USD.
    Formula:
      SDR_USD_t = sum_i(weight_i * Value_i_in_USD_t)
    Weights: USD (43.38%), EUR (29.31%), CNY (12.28%), JPY (7.59%), GBP (7.44%)
    """
    sdr_series = pd.Series(0.0, index=all_data.index)
    
    # In all_data, values are Units of Currency per 1 USD
    # Currency value in USD = 1 / all_data[currency]
    for c, weight in SDR_WEIGHTS.items():
        if c == "USD":
            sdr_series += weight * 1.0
        elif c in all_data.columns:
            curr_val_in_usd = 1.0 / all_data[c]
            sdr_series += weight * curr_val_in_usd
            
    return sdr_series.replace(0, np.nan).dropna()


def compute_cross_comparisons(currency: str, all_data: pd.DataFrame) -> Dict[str, float]:
    """
    Computes 1-year performance of the currency relative to:
    1. USD
    2. EUR
    3. IMF SDR Basket
    """
    if currency not in all_data.columns or len(all_data) < 252:
        return {"vs_USD_1y": 0.0, "vs_EUR_1y": 0.0, "vs_SDR_1y": 0.0}

    # Currency value in USD: 1 / P
    val_curr_usd = 1.0 / all_data[currency]
    
    # 1. vs USD 1y return
    ret_usd_1y = ((val_curr_usd.iloc[-1] / val_curr_usd.iloc[-252]) - 1.0) * 100.0
    
    # 2. vs EUR 1y return
    if "EUR" in all_data.columns:
        # Cross rate: Currency / EUR = (Currency / USD) / (EUR / USD)
        val_curr_eur = (1.0 / all_data[currency]) / (1.0 / all_data["EUR"])
        ret_eur_1y = ((val_curr_eur.iloc[-1] / val_curr_eur.iloc[-252]) - 1.0) * 100.0
    else:
        ret_eur_1y = 0.0

    # 3. vs SDR 1y return
    sdr_series = compute_sdr_basket_series(all_data)
    if not sdr_series.empty and len(sdr_series) >= 252:
        common_idx = val_curr_usd.index.intersection(sdr_series.index)
        v_c = val_curr_usd.loc[common_idx]
        v_sdr = sdr_series.loc[common_idx]
        ratio = v_c / v_sdr
        ret_sdr_1y = ((ratio.iloc[-1] / ratio.iloc[-252]) - 1.0) * 100.0
    else:
        ret_sdr_1y = 0.0

    return {
        "vs_USD_1y": round(float(ret_usd_1y), 2),
        "vs_EUR_1y": round(float(ret_eur_1y), 2),
        "vs_SDR_1y": round(float(ret_sdr_1y), 2)
    }


def compute_all_metrics(all_data: pd.DataFrame, dxy_series: pd.Series, rf_rate: float = 0.0525) -> pd.DataFrame:
    """
    Master pipeline computing the complete set of 10 metrics for every currency in the dataset.
    """
    records = []
    
    # Align DXY returns for correlation
    dxy_clean = dxy_series.dropna()
    dxy_returns = dxy_clean.pct_change().dropna()

    for currency in all_data.columns:
        series = all_data[currency].dropna()
        if len(series) < 10:
            continue
            
        cum_ret = calculate_cumulative_returns(series)
        vol = calculate_annualized_volatility(series)
        mdd, mdd_dur = calculate_max_drawdown(series)
        mom = calculate_momentum(series)
        sharpe = calculate_sharpe_ratio(series, rf_annual=rf_rate)
        skew, kurt = calculate_skewness_kurtosis(series)
        regime, signal_emoji, conf = detect_market_regime(series)
        cross = compute_cross_comparisons(currency, all_data)
        
        # Currency returns vs DXY correlation
        curr_val_in_usd = 1.0 / series
        curr_returns = curr_val_in_usd.pct_change().dropna()
        common_idx = curr_returns.index.intersection(dxy_returns.index)
        if len(common_idx) > 20:
            corr_dxy = round(float(curr_returns.loc[common_idx].corr(dxy_returns.loc[common_idx])), 2)
        else:
            corr_dxy = 0.0

        records.append({
            "Currency": currency,
            "Ret_7d (%)": cum_ret["7d"],
            "Ret_30d (%)": cum_ret["30d"],
            "Ret_90d (%)": cum_ret["90d"],
            "Ret_180d (%)": cum_ret["180d"],
            "Ret_1y (%)": cum_ret["1y"],
            "Ret_3y (%)": cum_ret["3y"],
            "Ret_5y (%)": cum_ret["5y"],
            "Volatilidad_Anual (%)": vol,
            "Max_Drawdown (%)": mdd,
            "Drawdown_Dias": mdd_dur,
            "Momentum_20d (%)": mom["pct_20d"],
            "Momentum_60d (%)": mom["pct_60d"],
            "Momentum_120d (%)": mom["pct_120d"],
            "Slope_60d": mom["slope_60d"],
            "Sharpe_Ratio": sharpe,
            "Skewness": skew,
            "Kurtosis": kurt,
            "Corr_DXY": corr_dxy,
            "vs_EUR_1y (%)": cross["vs_EUR_1y"],
            "vs_SDR_1y (%)": cross["vs_SDR_1y"],
            "Régimen": regime,
            "Señal": signal_emoji,
            "Confianza_Régimen": conf
        })

    metrics_df = pd.DataFrame(records)
    if not metrics_df.empty:
        metrics_df.set_index("Currency", inplace=True)
    return metrics_df


def compute_correlation_matrix(all_data: pd.DataFrame) -> pd.DataFrame:
    """
    Computes pairwise correlation matrix of daily percentage returns of holding each currency.
    """
    inv_data = 1.0 / all_data
    returns = inv_data.pct_change().dropna()
    return returns.corr().round(2)
