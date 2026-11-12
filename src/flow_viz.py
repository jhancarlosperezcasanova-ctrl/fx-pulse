"""
Interactive Sankey / Flow diagram and Gauge visualizations for FX Opportunities.
"""

from typing import List, Dict, Any
import pandas as pd
import plotly.graph_objects as go


def plot_fx_flow_sankey(opportunities_df: pd.DataFrame, max_links: int = 12) -> go.Figure:
    """
    Renders an interactive Flow diagram (Sankey) displaying directional capital rotation:
    From Weaker / Source currencies -> To Stronger / Destination currencies.
    Flow thickness corresponds to Composite Conviction Score.
    """
    if opportunities_df.empty:
        fig = go.Figure()
        fig.update_layout(title="Sin oportunidades suficientes para graficar flujo")
        return fig

    sub_df = opportunities_df.head(max_links)
    
    # Extract unique nodes
    sources = list(sub_df["origen"].unique())
    targets = list(sub_df["destino"].unique())
    all_nodes = list(dict.fromkeys(sources + targets))
    node_map = {node: idx for idx, node in enumerate(all_nodes)}

    link_source = [node_map[row["origen"]] for _, row in sub_df.iterrows()]
    link_target = [node_map[row["destino"]] for _, row in sub_df.iterrows()]
    # Flow thickness scaled by conviction score
    link_value = [float(row["score_compuesto"]) * 10.0 for _, row in sub_df.iterrows()]
    link_color = [
        "rgba(46, 160, 67, 0.45)" if row["señal"] == "🟢" else "rgba(210, 153, 34, 0.35)"
        for _, row in sub_df.iterrows()
    ]

    fig = go.Figure(data=[go.Sankey(
        node=dict(
            pad=18,
            thickness=20,
            line=dict(color="#30363d", width=0.8),
            label=all_nodes,
            color=["#f85149" if n in sources and n not in targets else ("#2ea043" if n in targets and n not in sources else "#58a6ff") for n in all_nodes]
        ),
        link=dict(
            source=link_source,
            target=link_target,
            value=link_value,
            color=link_color,
            hovertemplate="De: %{source.label}<br>Hacia: %{target.label}<br>Score Convicción: %{value}<extra></extra>"
        )
    )])

    fig.update_layout(
        title=dict(text="<b>Flujo Direccional de Rotación Óptima (Origen ➔ Destino)</b>", font=dict(size=17, color="#58a6ff")),
        font=dict(size=12, color="#c9d1d9"),
        template="plotly_dark",
        height=480,
        margin=dict(l=20, r=20, t=50, b=20)
    )
    return fig


def plot_currency_strength_gauge(score: float, currency: str) -> go.Figure:
    """Renders a modern semicircular gauge for a single currency's strength."""
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=round(score * 100.0, 1),
        number={'suffix': "/100", 'font': {'size': 20, 'color': '#ffffff'}},
        title={'text': f"<b>Fuerza {currency}</b>", 'font': {'size': 14, 'color': '#58a6ff'}},
        gauge={
            'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "#8b949e"},
            'bar': {'color': "#58a6ff", 'thickness': 0.28},
            'bgcolor': "#161b22",
            'borderwidth': 1,
            'bordercolor': "#30363d",
            'steps': [
                {'range': [0, 42], 'color': 'rgba(248, 81, 73, 0.5)'},
                {'range': [42, 58], 'color': 'rgba(210, 153, 34, 0.4)'},
                {'range': [58, 100], 'color': 'rgba(46, 160, 67, 0.5)'}
            ],
            'threshold': {
                'line': {'color': "white", 'width': 3},
                'thickness': 0.8,
                'value': round(score * 100.0, 1)
            }
        }
    ))
    fig.update_layout(
        height=220,
        margin=dict(l=15, r=15, t=35, b=15),
        template="plotly_dark"
    )
    return fig
