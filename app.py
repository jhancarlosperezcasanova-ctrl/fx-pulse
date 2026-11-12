"""
FX-Pulse Dashboard
Interactive Foreign Exchange Quantitative Radar built with Streamlit and Plotly.
Run with:
    streamlit run app.py
"""

import os
from datetime import datetime
import streamlit as st
import pandas as pd
import numpy as np

from src.data_fetcher import FXDataFetcher, CURRENCIES
from src.metrics import (
    compute_all_metrics,
    compute_correlation_matrix,
    compute_sdr_basket_series
)
from src.visualization import (
    plot_normalized_multiseries,
    plot_correlation_heatmap,
    plot_metrics_bars,
    plot_risk_return_scatter
)
from src.reporting import export_to_csv, export_to_html

# Page configuration
st.set_page_config(
    page_title="FX-Pulse | Radar Cuantitativo de Divisas",
    page_icon="💱",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .metric-card {
        background-color: #1e222d;
        border: 1px solid #2e3546;
        border-radius: 8px;
        padding: 15px;
        margin-bottom: 10px;
    }
    .stDataFrame {
        border-radius: 8px;
        overflow: hidden;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=3600, show_spinner=False)
def load_market_data(years: int):
    fetcher = FXDataFetcher()
    data = fetcher.get_all_currencies_data(CURRENCIES, years=years)
    dxy_df = fetcher.fetch_dxy_index((data.index[0]).strftime("%Y-%m-%d"))
    dxy_series = dxy_df["value"] if not dxy_df.empty else pd.Series(104.0, index=data.index)
    rf_rate = fetcher.fetch_fed_funds_rate()
    return data, dxy_series, rf_rate


def main():
    # Sidebar
    st.sidebar.image("https://img.icons8.com/color/96/exchange.png", width=64)
    st.sidebar.title("FX-Pulse Controls")
    st.sidebar.markdown("**Radar Cuantitativo de Mercado FX**")
    
    years_option = st.sidebar.slider("Años de Histórico", min_value=1, max_value=5, value=3)
    
    with st.spinner("Cargando y sincronizando cotizaciones de 41 divisas..."):
        all_data, dxy_series, rf_rate = load_market_data(years_option)

    if all_data.empty:
        st.error("Error al cargar datos de divisas. Verifique la conexión o revise logs.")
        return

    # Multiselect filter
    default_selection = ["EUR", "GBP", "JPY", "CHF", "MXN", "BRL", "CNY", "AUD", "CAD"]
    valid_defaults = [c for c in default_selection if c in all_data.columns]
    
    selected_currencies = st.sidebar.multiselect(
        "Divisas a Graficar / Analizar",
        options=list(all_data.columns),
        default=valid_defaults
    )

    st.sidebar.markdown(f"**Tasa Libre de Riesgo (Fed):** `{rf_rate * 100:.2f}%`")
    st.sidebar.markdown(f"**Divisas Disponibles:** `{len(all_data.columns)}`")
    st.sidebar.markdown(f"**Última Actualización:** `{all_data.index[-1].strftime('%Y-%m-%d')}`")

    # Header
    st.title("💱 FX-Pulse: Radar Cuantitativo de Divisas Globales")
    st.markdown(
        "Monitor macroeconómico y análisis estadístico en tiempo real de más de 40 divisas globales "
        "frente al Dólar Estadounidense (USD), el Euro (EUR) y la canasta de Derechos Especiales de Giro (SDR del FMI)."
    )

    # Compute Metrics
    metrics_df = compute_all_metrics(all_data, dxy_series, rf_rate=rf_rate)
    corr_matrix = compute_correlation_matrix(all_data[selected_currencies] if selected_currencies else all_data)

    # Quick summary KPI row
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        strongest = metrics_df["Ret_1y (%)"].idxmax()
        st.metric("🏆 Más Fuerte (1a vs USD)", strongest, f"+{metrics_df.loc[strongest, 'Ret_1y (%)']}%")
    with col2:
        weakest = metrics_df["Ret_1y (%)"].idxmin()
        st.metric("🔻 Más Débil (1a vs USD)", weakest, f"{metrics_df.loc[weakest, 'Ret_1y (%)']}%")
    with col3:
        best_sharpe = metrics_df["Sharpe_Ratio"].idxmax()
        st.metric("🎯 Mejor Sharpe Ratio", best_sharpe, f"{metrics_df.loc[best_sharpe, 'Sharpe_Ratio']}")
    with col4:
        lowest_vol = metrics_df["Volatilidad_Anual (%)"].idxmin()
        st.metric("🛡️ Menor Volatilidad", lowest_vol, f"{metrics_df.loc[lowest_vol, 'Volatilidad_Anual (%)']}%")

    # Tabs for structured navigation
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📈 Evolución Normalizada",
        "🚦 Semáforo de Regímenes",
        "📋 Ranking & Métricas",
        "🔗 Matriz de Correlación",
        "📊 Distribución de Riesgo"
    ])

    with tab1:
        st.subheader("Desempeño Relativo vs USD (Base 100)")
        st.markdown("Evolución del poder adquisitivo de la divisa extranjera respecto al dólar americano.")
        fig_multiseries = plot_normalized_multiseries(all_data, selected_currencies)
        st.plotly_chart(fig_multiseries, use_container_width=True)

    with tab2:
        st.subheader("🚦 Semáforo de Regímenes de Mercado (Ventana de 60 días)")
        st.markdown(
            "Detección de tendencia basada en medias móviles de 20/60 días, pendiente lineal y momentum."
        )
        
        # Filter for signals
        sig_col1, sig_col2, sig_col3 = st.columns(3)
        with sig_col1:
            st.markdown("### 🟢 Alcistas (Fortalecimiento)")
            bulls = metrics_df[metrics_df["Señal"] == "🟢"]
            for curr, row in bulls.iterrows():
                st.markdown(f"**{curr}**: Mom 60d: `{row['Momentum_60d (%)']}%` | Confianza: `{row['Confianza_Régimen']}%`")
        
        with sig_col2:
            st.markdown("### 🟡 Neutrales / Rango")
            neutrals = metrics_df[metrics_df["Señal"] == "🟡"]
            for curr, row in neutrals.iterrows():
                st.markdown(f"**{curr}**: Mom 60d: `{row['Momentum_60d (%)']}%` | Confianza: `{row['Confianza_Régimen']}%`")

        with sig_col3:
            st.markdown("### 🔴 Bajistas (Depreciación)")
            bears = metrics_df[metrics_df["Señal"] == "🔴"]
            for curr, row in bears.iterrows():
                st.markdown(f"**{curr}**: Mom 60d: `{row['Momentum_60d (%)']}%` | Confianza: `{row['Confianza_Régimen']}%`")

    with tab3:
        st.subheader("📋 Tabla Maestra de Métricas Cuantitativas")
        st.markdown("Haz clic en cualquier columna para ordenar según la métrica deseada.")
        
        # Display styled dataframe
        st.dataframe(
            metrics_df.style.background_gradient(subset=["Ret_1y (%)", "Sharpe_Ratio", "Momentum_60d (%)"], cmap="RdYlGn")
                            .background_gradient(subset=["Volatilidad_Anual (%)", "Max_Drawdown (%)"], cmap="Reds_r")
                            .format(precision=2),
            height=500,
            use_container_width=True
        )

        # Export Buttons
        col_exp1, col_exp2 = st.columns(2)
        with col_exp1:
            csv_path = export_to_csv(metrics_df)
            with open(csv_path, "rb") as f:
                st.download_button(
                    label="📥 Exportar Métricas a CSV",
                    data=f,
                    file_name=os.path.basename(csv_path),
                    mime="text/csv"
                )
        with col_exp2:
            html_path = export_to_html(all_data, metrics_df, corr_matrix, selected_currencies)
            with open(html_path, "rb") as f:
                st.download_button(
                    label="🌐 Exportar Informe HTML Autocontenido",
                    data=f,
                    file_name=os.path.basename(html_path),
                    mime="text/html"
                )

    with tab4:
        st.subheader("🔗 Matriz de Correlación Cruzada de Retornos Diarios")
        st.markdown("Evalúa qué divisas se mueven en sintonía (para carry trade o diversificación de cartera).")
        fig_corr = plot_correlation_heatmap(corr_matrix)
        st.plotly_chart(fig_corr, use_container_width=True)

    with tab5:
        st.subheader("📊 Distribución de Riesgo, Volatilidad y Drawdown")
        fig_scatter = plot_risk_return_scatter(metrics_df)
        st.plotly_chart(fig_scatter, use_container_width=True)

        col_b1, col_b2 = st.columns(2)
        with col_b1:
            fig_vol = plot_metrics_bars(metrics_df, "Volatilidad_Anual (%)", "Ranking de Volatilidad Anualizada", "Turbo")
            st.plotly_chart(fig_vol, use_container_width=True)
        with col_b2:
            fig_mdd = plot_metrics_bars(metrics_df, "Max_Drawdown (%)", "Máximo Drawdown Histórico", "Burg", ascending=True)
            st.plotly_chart(fig_mdd, use_container_width=True)

    # Footer
    st.markdown("---")
    st.caption("FX-Pulse Quantitative Terminal | Desarrollado para análisis macroeconómico y monitoreo de carteras FX.")


if __name__ == "__main__":
    main()
