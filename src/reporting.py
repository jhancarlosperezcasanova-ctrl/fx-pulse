"""
Reporting module for generating CSV exports, self-contained interactive HTML dossiers,
and executive CLI terminal summaries (Top-5 / Bottom-5).
"""

import os
from datetime import datetime
from typing import Dict, Any, List
import pandas as pd
import plotly.io as pio

from .visualization import (
    plot_normalized_multiseries,
    plot_correlation_heatmap,
    plot_metrics_bars,
    plot_risk_return_scatter
)


def export_to_csv(metrics_df: pd.DataFrame, output_dir: str = "output") -> str:
    """Exports full metrics table to timestamped CSV."""
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    file_path = os.path.join(output_dir, f"fx_metrics_{timestamp}.csv")
    metrics_df.to_csv(file_path)
    return file_path


def export_to_html(
    all_data: pd.DataFrame,
    metrics_df: pd.DataFrame,
    corr_matrix: pd.DataFrame,
    selected_currencies: List[str],
    output_dir: str = "output"
) -> str:
    """
    Exports a 100% self-contained offline interactive HTML report with Plotly figures and tables.
    """
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    file_path = os.path.join(output_dir, f"fx_pulse_report_{timestamp}.html")

    # Generate figures
    fig_norm = plot_normalized_multiseries(all_data, selected_currencies)
    fig_corr = plot_correlation_heatmap(corr_matrix)
    fig_vol = plot_metrics_bars(metrics_df, "Volatilidad_Anual (%)", "Volatilidad Anualizada", "Turbo")
    fig_mom = plot_metrics_bars(metrics_df, "Momentum_60d (%)", "Momentum a 60 días", "Tealgrn")
    fig_mdd = plot_metrics_bars(metrics_df, "Max_Drawdown (%)", "Máximo Drawdown Histórico", "Burg", ascending=True)
    fig_scatter = plot_risk_return_scatter(metrics_df)

    # Convert to HTML divs
    div_norm = pio.to_html(fig_norm, full_html=False, include_plotlyjs="cdn")
    div_corr = pio.to_html(fig_corr, full_html=False, include_plotlyjs=False)
    div_scatter = pio.to_html(fig_scatter, full_html=False, include_plotlyjs=False)
    div_vol = pio.to_html(fig_vol, full_html=False, include_plotlyjs=False)
    div_mom = pio.to_html(fig_mom, full_html=False, include_plotlyjs=False)
    div_mdd = pio.to_html(fig_mdd, full_html=False, include_plotlyjs=False)

    table_html = metrics_df.to_html(classes="styled-table", border=0)

    html_template = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FX-Pulse | Informe Cuantitativo de Divisas</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: #0d1117;
            color: #c9d1d9;
            margin: 0;
            padding: 24px;
        }}
        h1, h2, h3 {{
            color: #58a6ff;
        }}
        .header {{
            border-bottom: 1px solid #30363d;
            padding-bottom: 16px;
            margin-bottom: 24px;
        }}
        .card {{
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 24px;
        }}
        .styled-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9em;
            color: #c9d1d9;
        }}
        .styled-table th {{
            background-color: #21262d;
            color: #58a6ff;
            text-align: left;
            padding: 10px 12px;
            border-bottom: 2px solid #30363d;
        }}
        .styled-table td {{
            padding: 8px 12px;
            border-bottom: 1px solid #21262d;
        }}
        .styled-table tr:hover {{
            background-color: #1f242c;
        }}
        .badge {{
            padding: 4px 8px;
            border-radius: 4px;
            font-weight: bold;
        }}
        footer {{
            text-align: center;
            font-size: 0.8em;
            color: #8b949e;
            margin-top: 40px;
            border-top: 1px solid #30363d;
            padding-top: 15px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 FX-Pulse: Radar Cuantitativo de Divisas Globales</h1>
        <p>Generado automáticamente el {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')} | Cobertura: 41 pares vs USD</p>
    </div>

    <div class="card">
        <h2>📈 Dinámica Multidivisa Normalizada</h2>
        {div_norm}
    </div>

    <div class="card">
        <h2>🎯 Mapa Riesgo vs. Retorno y Sharpe Ratio</h2>
        {div_scatter}
    </div>

    <div class="card">
        <h2>📊 Ranking de Métricas Clave</h2>
        <div style="display: grid; grid-template-columns: 1fr; gap: 20px;">
            {div_mom}
            {div_vol}
            {div_mdd}
        </div>
    </div>

    <div class="card">
        <h2>🔗 Matriz de Correlación Cruzada</h2>
        {div_corr}
    </div>

    <div class="card" style="overflow-x: auto;">
        <h2>📋 Matriz Cuantitativa Completa</h2>
        {table_html}
    </div>

    <footer>
        <p>FX-Pulse — Diseñado para investigación macroeconómica y análisis cuantitativo. No constituye recomendación de inversión.</p>
    </footer>
</body>
</html>
"""
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(html_template)

    return file_path


def print_executive_summary(metrics_df: pd.DataFrame):
    """
    Prints a rich executive summary in the console showing Top-5 and Bottom-5 across key metrics.
    """
    if metrics_df.empty:
        print("⚠️ No hay métricas suficientes para imprimir el resumen.")
        return

    separator = "=" * 80
    sub_sep = "-" * 80

    print("\n" + separator)
    print(" 🌍  FX-PULSE :: RESUMEN EJECUTIVO DE MERCADO DE DIVISAS")
    print(f" Fecha de corte: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')} | Total Divisas: {len(metrics_df)}")
    print(separator)

    # 1. Rendimiento 1 Año
    if "Ret_1y (%)" in metrics_df.columns:
        ret_sorted = metrics_df["Ret_1y (%)"].sort_values()
        print("\n📈 RENDIMIENTO ACUMULADO A 1 AÑO (vs USD)")
        print(sub_sep)
        print("  🟢 TOP 5 MÁS FUERTES:")
        for curr, val in ret_sorted.tail(5)[::-1].items():
            print(f"     {curr:<5} : +{val:.2f}%")
        print("  🔴 BOTTOM 5 MÁS DÉBILES:")
        for curr, val in ret_sorted.head(5).items():
            print(f"     {curr:<5} : {val:.2f}%")

    # 2. Volatilidad Anualizada
    if "Volatilidad_Anual (%)" in metrics_df.columns:
        vol_sorted = metrics_df["Volatilidad_Anual (%)"].sort_values()
        print("\n⚡ VOLATILIDAD ANUALIZADA")
        print(sub_sep)
        print("  🔥 TOP 5 MÁS VOLÁTILES (Mayor Riesgo):")
        for curr, val in vol_sorted.tail(5)[::-1].items():
            print(f"     {curr:<5} : {val:.2f}%")
        print("  🛡️ TOP 5 MENOS VOLÁTILES (Más Estables):")
        for curr, val in vol_sorted.head(5).items():
            print(f"     {curr:<5} : {val:.2f}%")

    # 3. Ratio de Sharpe
    if "Sharpe_Ratio" in metrics_df.columns:
        sharpe_sorted = metrics_df["Sharpe_Ratio"].sort_values()
        print("\n🎯 RATIO DE SHARPE (Retorno ajustado por riesgo, Rf = Fed Funds)")
        print(sub_sep)
        print("  🏆 TOP 5 MEJOR RELACIÓN RIESGO/RETORNO:")
        for curr, val in sharpe_sorted.tail(5)[::-1].items():
            print(f"     {curr:<5} : Sharpe = {val:.2f}")
        print("  ⚠️ BOTTOM 5 PEOR RENDIMIENTO:")
        for curr, val in sharpe_sorted.head(5).items():
            print(f"     {curr:<5} : Sharpe = {val:.2f}")

    # 4. Máximo Drawdown
    if "Max_Drawdown (%)" in metrics_df.columns:
        mdd_sorted = metrics_df["Max_Drawdown (%)"].sort_values()
        print("\n📉 MÁXIMO DRAWDOWN HISTÓRICO")
        print(sub_sep)
        print("  💥 TOP 5 CAÍDAS MÁS SEVERAS:")
        for curr, val in mdd_sorted.head(5).items():
            dur = metrics_df.loc[curr, "Drawdown_Dias"] if "Drawdown_Dias" in metrics_df.columns else 0
            print(f"     {curr:<5} : {val:.2f}% (Duración: {dur} días)")

    # 5. Señales y Regímenes
    if "Señal" in metrics_df.columns and "Régimen" in metrics_df.columns:
        print("\n🚦 SEMÁFORO DE REGÍMENES DE MERCADO (Últimos 60 días)")
        print(sub_sep)
        bulls = metrics_df[metrics_df["Señal"] == "🟢"].index.tolist()
        neutrals = metrics_df[metrics_df["Señal"] == "🟡"].index.tolist()
        bears = metrics_df[metrics_df["Señal"] == "🔴"].index.tolist()
        print(f"  🟢 ALCISTAS ({len(bulls)}): {', '.join(bulls) if bulls else 'Ninguna'}")
        print(f"  🟡 LATERALES ({len(neutrals)}): {', '.join(neutrals) if neutrals else 'Ninguna'}")
        print(f"  🔴 BAJISTAS ({len(bears)}): {', '.join(bears) if bears else 'Ninguna'}")

    print("\n" + separator + "\n")
