"""
Visualization module providing interactive Plotly components for Streamlit and HTML reports:
  - Multi-series normalized chart (Base = 100)
  - Correlation Heatmap
  - Volatility, Momentum, and Drawdown bar charts
  - Signal Cards / Traffic Lights (🟢/🟡/🔴)
"""

from typing import List, Optional
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go


def plot_normalized_multiseries(all_data: pd.DataFrame, selected_currencies: List[str]) -> go.Figure:
    """
    Renders multi-currency performance normalized to Base 100 at the start date.
    Measures value of the foreign currency relative to USD (1 / rate).
    """
    if all_data.empty or not selected_currencies:
        fig = go.Figure()
        fig.update_layout(title="Sin datos suficientes")
        return fig

    # Currency value relative to USD
    inv_data = 1.0 / all_data[selected_currencies]
    # Normalize to 100 at the first valid point
    norm_data = (inv_data / inv_data.iloc[0]) * 100.0

    fig = go.Figure()
    for col in selected_currencies:
        fig.add_trace(go.Scatter(
            x=norm_data.index,
            y=norm_data[col],
            mode="lines",
            name=col,
            line=dict(width=1.8),
            hovertemplate=f"<b>{col}</b><br>Fecha: %{{x|%Y-%m-%d}}<br>Índice: %{{y:.2f}}<extra></extra>"
        ))

    fig.add_hline(y=100, line_dash="dash", line_color="gray", annotation_text="Base 100")
    fig.update_layout(
        title=dict(text="<b>Rendimiento Relativo Multidivisa vs USD (Normalizado Base = 100)</b>", font=dict(size=18)),
        xaxis_title="Fecha",
        yaxis_title="Índice Base (100 = Inicio del Periodo)",
        template="plotly_dark",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5),
        margin=dict(l=40, r=40, t=60, b=40),
        height=550
    )
    return fig


def plot_correlation_heatmap(corr_matrix: pd.DataFrame) -> go.Figure:
    """
    Interactive correlation heatmap for currency returns.
    """
    if corr_matrix.empty:
        return go.Figure()

    fig = go.Figure(data=go.Heatmap(
        z=corr_matrix.values,
        x=corr_matrix.columns,
        y=corr_matrix.index,
        colorscale="RdBu",
        zmid=0.0,
        zmin=-1.0,
        zmax=1.0,
        text=np.round(corr_matrix.values, 2),
        texttemplate="%{text}",
        textfont={"size": 10},
        hoverongaps=False
    ))

    fig.update_layout(
        title=dict(text="<b>Matriz de Correlación de Retornos Diarios (Pares FX)</b>", font=dict(size=18)),
        template="plotly_dark",
        height=700,
        margin=dict(l=50, r=50, t=60, b=50)
    )
    return fig


def plot_metrics_bars(metrics_df: pd.DataFrame, metric_col: str, title: str, color_scale: str = "Viridis", ascending: bool = False) -> go.Figure:
    """
    Sorted bar chart for key metrics (Volatility, Momentum, Drawdown).
    """
    if metrics_df.empty or metric_col not in metrics_df.columns:
        return go.Figure()

    df_sorted = metrics_df.sort_values(by=metric_col, ascending=ascending)

    fig = px.bar(
        df_sorted.reset_index(),
        x="Currency",
        y=metric_col,
        color=metric_col,
        color_continuous_scale=color_scale,
        title=f"<b>{title}</b>",
        labels={"Currency": "Divisa", metric_col: metric_col},
        template="plotly_dark"
    )
    fig.update_layout(
        height=420,
        margin=dict(l=30, r=30, t=50, b=30),
        coloraxis_showscale=False
    )
    return fig


def plot_risk_return_scatter(metrics_df: pd.DataFrame) -> go.Figure:
    """
    Risk vs Return scatter plot (Volatility vs 1y Return) with Sharpe as bubble size/color.
    """
    if metrics_df.empty or "Volatilidad_Anual (%)" not in metrics_df.columns:
        return go.Figure()

    fig = px.scatter(
        metrics_df.reset_index(),
        x="Volatilidad_Anual (%)",
        y="Ret_1y (%)",
        text="Currency",
        color="Sharpe_Ratio",
        color_continuous_scale="RdYlGn",
        title="<b>Mapa Riesgo vs. Retorno a 1 Año (Sharpe Ratio en Color)</b>",
        template="plotly_dark",
        size=np.abs(metrics_df["Sharpe_Ratio"].values) + 1.0,
        hover_data=["Max_Drawdown (%)", "Momentum_60d (%)", "Régimen"]
    )
    fig.update_traces(textposition="top center")
    fig.add_hline(y=0, line_dash="dash", line_color="gray")
    fig.update_layout(
        height=500,
        margin=dict(l=30, r=30, t=50, b=30),
        xaxis_title="Volatilidad Anualizada (%)",
        yaxis_title="Rendimiento Anual vs USD (%)"
    )
    return fig
