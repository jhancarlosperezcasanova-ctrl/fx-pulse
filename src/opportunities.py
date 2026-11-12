"""
FX Opportunities Engine: calculates directional cross-currency opportunities (A -> B),
strength/weakness scores, regime convictions, and alert conditions.
"""

from typing import Dict, List, Tuple, Any, Optional
import pandas as pd
import numpy as np

# Liquid pairs pool for opportunity scanning (Majors & liquid crosses/EM)
LIQUID_UNIVERSE = [
    "EUR", "GBP", "JPY", "USD", "CHF", "AUD", "CAD", "NZD", "MXN", "BRL",
    "ZAR", "INR", "KRW", "TRY", "PLN", "CZK", "HUF", "ILS", "SGD", "SEK",
    "NOK", "DKK"
]

# Estimated retail spread in basis points (1 bps = 0.01% = 0.0001)
SPREAD_ESTIMATES_BPS = {
    # Majors (ultra-liquid)
    "EUR/USD": 1.2, "USD/JPY": 1.5, "GBP/USD": 2.0, "USD/CHF": 2.5,
    "AUD/USD": 2.2, "USD/CAD": 2.2, "NZD/USD": 3.0,
    # Liquid Crosses
    "EUR/GBP": 2.5, "EUR/JPY": 2.8, "GBP/JPY": 3.5, "EUR/CHF": 3.0,
    "AUD/JPY": 3.5, "CAD/JPY": 3.5, "EUR/AUD": 3.5, "GBP/AUD": 4.0,
    # High-liquidity EM & Exotics
    "USD/MXN": 8.0, "USD/BRL": 12.0, "USD/ZAR": 14.0, "USD/INR": 7.0,
    "USD/KRW": 9.0, "USD/SGD": 4.0, "USD/SEK": 6.0, "USD/NOK": 6.5,
    "USD/DKK": 4.5, "USD/PLN": 8.5, "USD/CZK": 9.0, "USD/HUF": 12.0,
    "USD/ILS": 8.0, "USD/TRY": 28.0,
    # Illiquid / Frontier
    "USD/COP": 35.0, "USD/CLP": 30.0, "USD/PEN": 25.0, "USD/ARS": 95.0,
    "USD/KES": 60.0, "USD/NGN": 80.0, "USD/VND": 45.0, "USD/UAH": 75.0,
    "USD/EGP": 55.0
}

MAJOR_CURRENCIES = {"USD", "EUR", "GBP", "JPY", "CHF", "AUD", "CAD", "NZD"}
CROSS_CURRENCIES = {"MXN", "BRL", "ZAR", "INR", "KRW", "PLN", "CZK", "HUF", "ILS", "SGD", "SEK", "NOK", "DKK"}


def get_pair_spread_and_rank(curr_a: str, curr_b: str) -> Tuple[float, str]:
    """Estimates spread in bps and liquidity rank category (major, cross, exotic)."""
    if curr_a in MAJOR_CURRENCIES and curr_b in MAJOR_CURRENCIES:
        rank = "major"
        spread = 2.5 if "USD" in (curr_a, curr_b) else 3.8
    elif (curr_a in MAJOR_CURRENCIES and curr_b in CROSS_CURRENCIES) or (curr_b in MAJOR_CURRENCIES and curr_a in CROSS_CURRENCIES):
        rank = "cross"
        spread = 9.5
    elif curr_a in CROSS_CURRENCIES and curr_b in CROSS_CURRENCIES:
        rank = "cross"
        spread = 14.0
    else:
        rank = "exotic"
        spread = 45.0

    # Custom lookup override if specified
    direct_key = f"{curr_a}/{curr_b}"
    rev_key = f"{curr_b}/{curr_a}"
    if direct_key in SPREAD_ESTIMATES_BPS:
        spread = SPREAD_ESTIMATES_BPS[direct_key]
    elif rev_key in SPREAD_ESTIMATES_BPS:
        spread = SPREAD_ESTIMATES_BPS[rev_key]

    return round(float(spread), 1), rank


def calculate_currency_strength_score(currency: str, all_data: pd.DataFrame) -> Tuple[float, str]:
    """
    Computes an absolute strength/weakness score (0.0 to 1.0) for a currency:
    - 40% Momentum 60d vs USD
    - 30% Moving average positioning (Price vs MA20 and MA60)
    - 20% Drawdown penalty (low drawdown = strong)
    - 10% Volatility penalty (controlled vol = better strength)
    """
    if currency == "USD":
        # USD strength evaluated against broad basket
        # When all other currencies fall vs USD, USD score is high
        pct_changes = []
        for c in ["EUR", "GBP", "JPY", "CAD", "AUD", "CHF"]:
            if c in all_data.columns and len(all_data[c]) >= 60:
                # 1/all_data[c] is currency value in USD. If it falls, USD gained.
                val = 1.0 / all_data[c]
                pct = ((val.iloc[-1] / val.iloc[-60]) - 1.0)
                pct_changes.append(-pct) # Invert for USD
        avg_usd_mom = np.mean(pct_changes) if pct_changes else 0.0
        score = 0.5 + (avg_usd_mom * 3.0)
        score = max(0.05, min(0.95, score))
        regime = "Fuerte" if score >= 0.60 else ("Débil" if score <= 0.40 else "Neutral")
        return round(float(score), 3), regime

    if currency not in all_data.columns or len(all_data[currency]) < 60:
        return 0.5, "Neutral"

    # Holding foreign currency value in USD: 1 / P
    val_series = 1.0 / all_data[currency].dropna()
    if len(val_series) < 60:
        return 0.5, "Neutral"

    curr_val = val_series.iloc[-1]
    mom60 = (curr_val / val_series.iloc[-60]) - 1.0 # fractional
    ma20 = val_series.iloc[-20:].mean()
    ma60 = val_series.iloc[-60:].mean()

    # Trend component: +1 if above MA20, +1 if above MA60
    trend_comp = (1.0 if curr_val > ma20 else -1.0) + (1.0 if curr_val > ma60 else -1.0) # -2 to +2

    # Drawdown component
    cum_peak = val_series.cummax()
    dd = (val_series - cum_peak) / cum_peak
    mdd = abs(float(dd.iloc[-120:].min())) # 0 to 1

    # Raw composite score centered at 0.5
    raw_score = 0.50 + (mom60 * 2.5) + (trend_comp * 0.075) - (mdd * 0.25)
    final_score = max(0.05, min(0.98, raw_score))

    regime = "Fuerte" if final_score >= 0.58 else ("Débil" if final_score <= 0.42 else "Neutral")
    return round(float(final_score), 3), regime


def get_directional_pair_timeseries(curr_a: str, curr_b: str, all_data: pd.DataFrame) -> pd.Series:
    """
    Returns the exchange price series of Unit of B per 1 Unit of A.
    If you hold A and want to exchange to B, you monitor the relative price of B in terms of A:
      Value_B_in_terms_of_A = (USD per B) / (USD per A)
    """
    # Price of A in USD:
    # If A == USD, value_in_usd = 1.0. If A in all_data, value_in_usd = 1.0 / all_data[A]
    if curr_a == "USD":
        val_a = pd.Series(1.0, index=all_data.index)
    else:
        val_a = 1.0 / all_data[curr_a]

    if curr_b == "USD":
        val_b = pd.Series(1.0, index=all_data.index)
    else:
        val_b = 1.0 / all_data[curr_b]

    # Holding B relative to A: Ratio = val_b / val_a
    # If Ratio rises, B is appreciating against A (favorable to move from A to B)
    ratio = val_b / val_a
    return ratio.replace(0, np.nan).dropna()


def compute_directional_pair_metrics(curr_a: str, curr_b: str, all_data: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """
    Computes pair performance when moving FROM A TO B:
    - Change % 30d
    - Annualized Volatility 30d
    - Pair Sharpe Ratio (annualized excess return over 0% or Rf)
    - Momentum 60d
    - Spread and liquidity tier
    - Composite Conviction Score (0 to 1.0)
    """
    if curr_a == curr_b:
        return None

    pair_series = get_directional_pair_timeseries(curr_a, curr_b, all_data)
    if len(pair_series) < 65:
        return None

    # Performance of B relative to A (investor holds A and buys B)
    curr_ratio = pair_series.iloc[-1]
    ratio_30d = pair_series.iloc[-22]
    ratio_60d = pair_series.iloc[-61]

    chg_30d_pct = ((curr_ratio / ratio_30d) - 1.0) * 100.0
    mom_60d_pct = ((curr_ratio / ratio_60d) - 1.0) * 100.0

    # Volatility of daily returns over last 30 trading days
    daily_returns_30d = pair_series.iloc[-30:].pct_change().dropna()
    vol_30d_annual = float(daily_returns_30d.std() * np.sqrt(252) * 100.0)

    # Sharpe of the pair over the last 120 trading days (relative to 0 risk-free spread)
    daily_returns_120d = pair_series.iloc[-120:].pct_change().dropna()
    ret_mean = daily_returns_120d.mean() * 252
    vol_120d = daily_returns_120d.std() * np.sqrt(252)
    sharpe_par = round(float(ret_mean / vol_120d), 2) if vol_120d > 0.0001 else 0.0

    spread_bps, liq_rank = get_pair_spread_and_rank(curr_a, curr_b)

    # =========================================================================
    # COMPOSITE CONVICTION SCORE (0.0 to 1.0):
    # Ponderaciones:
    #   * 40% Momentum a 60 días del par B vs A (direccionalidad sostenida)
    #   * 25% Ratio de Sharpe del par (calidad del retorno ajustado por riesgo)
    #   * 20% Penalización por volatilidad a 30 días (mayor certidumbre / menor vaivén)
    #   * 15% Calidad de liquidez / spread (menor fricción de entrada y salida)
    # =========================================================================
    mom_norm = np.clip((mom_60d_pct + 10.0) / 20.0, 0.0, 1.0) # -10% to +10% mapped to [0, 1]
    sharpe_norm = np.clip((sharpe_par + 1.0) / 3.5, 0.0, 1.0) # -1 to +2.5 mapped to [0, 1]
    vol_norm = np.clip(1.0 - (vol_30d_annual / 35.0), 0.0, 1.0) # 0 to 35% vol mapped to [1, 0]
    liq_norm = 1.0 if liq_rank == "major" else (0.75 if liq_rank == "cross" else 0.30)

    score_compuesto = (
        0.40 * mom_norm +
        0.25 * sharpe_norm +
        0.20 * vol_norm +
        0.15 * liq_norm
    )
    score_compuesto = round(float(np.clip(score_compuesto, 0.01, 0.99)), 3)

    # Signal Traffic light
    if score_compuesto >= 0.70 and mom_60d_pct > 1.5:
        signal = "🟢"
    elif score_compuesto <= 0.45 or mom_60d_pct < -1.5:
        signal = "🔴"
    else:
        signal = "🟡"

    return {
        "origen": curr_a,
        "destino": curr_b,
        "par": f"{curr_a} → {curr_b}",
        "chg_30d_pct": round(chg_30d_pct, 2),
        "vol_30d_pct": round(vol_30d_annual, 2),
        "volatilidad_30d": vol_30d_annual / 100.0, # decimal for rule verification
        "sharpe_par": sharpe_par,
        "momentum_60d": round(mom_60d_pct / 100.0, 4), # decimal fraction
        "momentum_60d_pct": round(mom_60d_pct, 2),
        "spread_estimado_bps": spread_bps,
        "liquidez_rank": liq_rank,
        "score_compuesto": score_compuesto,
        "señal": signal,
        "ultimo_ratio": round(float(curr_ratio), 4)
    }


def scan_top_opportunities(all_data: pd.DataFrame, max_pairs: int = 15) -> pd.DataFrame:
    """Scans all liquid combinations (A -> B) and ranks by composite conviction."""
    records = []
    active_universe = [c for c in LIQUID_UNIVERSE if c == "USD" or c in all_data.columns]

    for curr_a in active_universe:
        for curr_b in active_universe:
            if curr_a != curr_b:
                m = compute_directional_pair_metrics(curr_a, curr_b, all_data)
                if m is not None:
                    records.append(m)

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    # Sort by conviction score descending
    df_sorted = df.sort_values(by="score_compuesto", ascending=False).reset_index(drop=True)
    return df_sorted.head(max_pairs)


def is_high_conviction(opportunity: dict) -> bool:
    """
    Mandatory condition rule check:
    Alerta se envía SOLO si cumple TODAS las condiciones simultáneamente.
    """
    score = opportunity.get("score_compuesto", 0.0)
    momentum = opportunity.get("momentum_60d", 0.0)
    sharpe = opportunity.get("sharpe_par", 0.0)
    vol_30d = opportunity.get("volatilidad_30d", 1.0)
    spread = opportunity.get("spread_estimado_bps", 999.0)
    liquidez_rank = opportunity.get("liquidez_rank", "exotic")

    return (
        score >= 0.75
        and abs(momentum) >= 0.02
        and sharpe >= 1.5
        and vol_30d < 0.25
        and spread < 15
        and liquidez_rank in ("major", "cross")
    )


def get_top_buy_sell_rankings(all_data: pd.DataFrame) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Generates Top-5 currencies to SELL and Top-5 to BUY with plain-language rationales."""
    scores = []
    target_universe = [c for c in LIQUID_UNIVERSE if c == "USD" or c in all_data.columns]
    
    for c in target_universe:
        score, regime = calculate_currency_strength_score(c, all_data)
        scores.append({"currency": c, "score": score, "regime": regime})

    df = pd.DataFrame(scores).sort_values(by="score", ascending=True)

    # Bottom 5 (To Sell)
    sell_candidates = df.head(5).to_dict("records")
    to_sell = []
    for item in sell_candidates:
        c = item["currency"]
        sc = item["score"]
        justification = (
            f"{c} sufre de pérdida de momentum y debilidad estructural frente al resto de la canasta, "
            f"con caídas continuas y volatilidad descompensada. Conviene reducir o rotar exposición."
        )
        to_sell.append({
            "currency": c,
            "score": sc,
            "regime": item["regime"],
            "justification": justification
        })

    # Top 5 (To Buy)
    buy_candidates = df.tail(5)[::-1].to_dict("records")
    to_buy = []
    for item in buy_candidates:
        c = item["currency"]
        sc = item["score"]
        justification = (
            f"{c} exhibe sólido momentum alcista respaldado por baja volatilidad y estabilidad macro. "
            f"Ofrece excelente preservación de valor y ratio de retorno frente a pares rezagados."
        )
        to_buy.append({
            "currency": c,
            "score": sc,
            "regime": item["regime"],
            "justification": justification
        })

    return to_sell, to_buy


def get_recommendations_for_holding(currency: str, all_data: pd.DataFrame) -> List[Dict[str, Any]]:
    """Generates actionable advice if the user currently holds a specific currency."""
    active_universe = [c for c in LIQUID_UNIVERSE if c == "USD" or c in all_data.columns]
    results = []

    for dest in active_universe:
        if dest != currency:
            m = compute_directional_pair_metrics(currency, dest, all_data)
            if m:
                results.append(m)

    if not results:
        return []

    sorted_res = sorted(results, key=lambda x: x["score_compuesto"], reverse=True)
    top_3 = sorted_res[:3]

    recs = []
    for rank_idx, opp in enumerate(top_3, 1):
        dest = opp["destino"]
        score = opp["score_compuesto"]
        mom = opp["momentum_60d_pct"]
        vol = opp["vol_30d_pct"]
        spread = opp["spread_estimado_bps"]

        if rank_idx == 1:
            protection = "Poder de compra y apreciación patrimonial en divisa con alto momentum."
            capital_pct = "20% - 30% del capital disponible."
            invalidation = f"Si el par retrocede más de 2.5% de su nivel actual ({opp['ultimo_ratio']}) o el Sharpe cae por debajo de 1.0."
        elif rank_idx == 2:
            protection = "Ahorro defensivo y diversificación ante riesgo inflacionario o cambiario local."
            capital_pct = "15% - 25% del capital disponible."
            invalidation = f"Si la volatilidad a 30 días supera 18% o la media móvil de 20 días cruza a la baja."
        else:
            protection = "Preservación para viajes, compromisos internacionales o comercio exterior."
            capital_pct = "10% - 15% del capital disponible."
            invalidation = f"Si se rompe el soporte técnico de 60 días o surge un shock macroeconómico imprevisto."

        recs.append({
            "destino": dest,
            "score": score,
            "momentum": mom,
            "volatilidad": vol,
            "spread_bps": spread,
            "protection_goal": protection,
            "capital_pct": capital_pct,
            "invalidation_point": invalidation,
            "pair_info": opp
        })

    return recs
