"""
FX-Pulse Dashboard
Interactive Foreign Exchange Quantitative Radar built with Streamlit and Plotly.
Includes the dedicated "Oportunidades de Cambio" (FX Opportunities Board) with
cross-directional matrix, buy/sell rankings, holdings advisor, flow charts,
PDF exports, and Gmail SMTP alerts.
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
from src.opportunities import (
    scan_top_opportunities,
    get_top_buy_sell_rankings,
    get_recommendations_for_holding,
    calculate_currency_strength_score,
    is_high_conviction
)
from src.flow_viz import plot_fx_flow_sankey, plot_currency_strength_gauge
from src.alerts import send_high_conviction_alert
from src.pdf_exporter import export_opportunities_to_pdf

# Page configuration
st.set_page_config(
    page_title="FX-Pulse | Radar Cuantitativo & Oportunidades FX",
    page_icon="💱",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .metric-card {
        background-color: #161b22;
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 15px;
        margin-bottom: 12px;
    }
    .opportunity-card {
        background-color: #1c2128;
        border-left: 4px solid #2ea043;
        border-radius: 4px;
        padding: 14px 18px;
        margin-bottom: 12px;
    }
    .warning-card {
        background-color: #211c1d;
        border-left: 4px solid #f85149;
        border-radius: 4px;
        padding: 12px 16px;
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
    
    with st.spinner("Sincronizando cotizaciones y calculando oportunidades..."):
        all_data, dxy_series, rf_rate = load_market_data(years_option)

    if all_data.empty:
        st.error("Error al cargar datos de divisas. Verifique la conexión o revise logs.")
        return

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
    st.title("💱 FX-Pulse: Radar Cuantitativo & Tablero de Oportunidades")
    st.markdown(
        "Herramienta integral de análisis técnico y cuantitativo para el mercado de divisas. "
        "Responde de forma accionable: *¿Hacia qué divisa conviene rotar capital y por qué?*"
    )

    # Master tabs: Include dedicated "Oportunidades de Cambio" as primary focus
    main_tab_opp, main_tab_market, main_tab_regimes, main_tab_metrics, main_tab_corr, main_tab_risk = st.tabs([
        "🎯 Oportunidades de Cambio (FX Board)",
        "📈 Evolución Normalizada",
        "🚦 Semáforo de Regímenes",
        "📋 Ranking & Métricas",
        "🔗 Matriz de Correlación",
        "📊 Distribución de Riesgo"
    ])

    # -------------------------------------------------------------------------
    # TAB: OPORTUNIDADES DE CAMBIO (APARTADO DEDICADO)
    # -------------------------------------------------------------------------
    with main_tab_opp:
        st.subheader("🎯 Tablero de Oportunidades de Cambio de Divisas")
        st.markdown(
            "Análisis direccional cruzado entre pares de alta y media liquidez. "
            "Priorizado por **Score de Convicción Compuesto** (40% Momentum 60d + 25% Sharpe del Par + 20% Baja Volatilidad + 15% Liquidez/Spread)."
        )

        # 1. Scanned Opportunities
        opportunities_df = scan_top_opportunities(all_data, max_pairs=15)

        # Quick Scan Banner (10s Read)
        if not opportunities_df.empty:
            top_opp = opportunities_df.iloc[0]
            st.markdown(f"""
            <div class="opportunity-card">
                <h4 style="margin:0; color:#58a6ff;">💡 Top Oportunidad del Mercado: <b>{top_opp['origen']} ➔ {top_opp['destino']}</b> ({top_opp['señal']})</h4>
                <p style="margin:4px 0 0 0; font-size:14px;">
                    Score de Convicción: <b>{top_opp['score_compuesto']}</b> | Momentum 60d: <b>+{top_opp['momentum_60d_pct']}%</b> | 
                    Sharpe del par: <b>{top_opp['sharpe_par']}</b> | Spread est: <b>{top_opp['spread_estimado_bps']} bps</b>.
                </p>
            </div>
            """, unsafe_allow_html=True)

        # Section 1: Directional Matrix Table
        st.markdown("### 1. Matriz de Oportunidad Direccional (Top 15 Pares)")
        if not opportunities_df.empty:
            display_cols = [
                "origen", "destino", "chg_30d_pct", "vol_30d_pct", 
                "sharpe_par", "momentum_60d_pct", "spread_estimado_bps", 
                "score_compuesto", "señal"
            ]
            renamed_cols = {
                "origen": "Divisa origen",
                "destino": "Divisa destino",
                "chg_30d_pct": "Cambio % (30d)",
                "vol_30d_pct": "Vol. (30d)",
                "sharpe_par": "Sharpe del par",
                "momentum_60d_pct": "Momentum 60d (%)",
                "spread_estimado_bps": "Liquidez (spread est. bps)",
                "score_compuesto": "Convicción (Score)",
                "señal": "Señal"
            }
            sub_table = opportunities_df[display_cols].rename(columns=renamed_cols)
            st.dataframe(sub_table, use_container_width=True, height=450)
        else:
            st.info("Calculando matriz de oportunidades...")

        # Section 2: Flow Visualization & Gauges
        st.markdown("### 2. Flujo Direccional de Rotación de Capital")
        col_flow, col_gauge = st.columns([2, 1])
        with col_flow:
            fig_sankey = plot_fx_flow_sankey(opportunities_df, max_links=12)
            st.plotly_chart(fig_sankey, use_container_width=True)
        with col_gauge:
            st.markdown("#### Medidores de Fortaleza Individual")
            g_curr = st.selectbox("Seleccionar divisa para evaluar fuerza:", ["USD", "EUR", "GBP", "JPY", "MXN", "BRL", "CHF"], index=0)
            score_val, regime_val = calculate_currency_strength_score(g_curr, all_data)
            fig_gauge = plot_currency_strength_gauge(score_val, g_curr)
            st.plotly_chart(fig_gauge, use_container_width=True)
            st.caption(f"Régimen Actual: **{regime_val}** (Score: {score_val})")

        # Section 3: Rankings "De dónde salir / A dónde entrar"
        st.markdown("### 3. Ranking «De dónde salir / A dónde entrar»")
        to_sell, to_buy = get_top_buy_sell_rankings(all_data)
        col_sell, col_buy = st.columns(2)

        with col_sell:
            st.markdown("#### 🔴 Top 5 Divisas para VENDER / REDUCIR")
            for item in to_sell:
                st.markdown(f"""
                <div class="warning-card">
                    <b>{item['currency']}</b> (Score: {item['score']} | {item['regime']})<br/>
                    <small>{item['justification']}</small>
                </div>
                """, unsafe_allow_html=True)

        with col_buy:
            st.markdown("#### 🟢 Top 5 Divisas para COMPRAR / ROTAR")
            for item in to_buy:
                st.markdown(f"""
                <div class="opportunity-card">
                    <b>{item['currency']}</b> (Score: {item['score']} | {item['regime']})<br/>
                    <small>{item['justification']}</small>
                </div>
                """, unsafe_allow_html=True)

        # Section 4: Advisor "Si yo tengo [DIVISA], ¿a dónde cambio?"
        st.markdown("### 4. Asesor Interactivo: «Si yo tengo [DIVISA], ¿a dónde cambio?»")
        hold_curr = st.selectbox(
            "Selecciona la divisa que actualmente posees:",
            options=["USD", "EUR", "MXN", "COP", "ARS", "CLP", "PEN", "BRL", "GBP", "JPY"],
            index=0
        )

        recs = get_recommendations_for_holding(hold_curr, all_data)
        if recs:
            for idx, r in enumerate(recs, 1):
                p = r["pair_info"]
                with st.expander(f"Opción #{idx}: Rotar {hold_curr} ➔ {r['destino']} | Convicción: {r['score']} ({p['señal']})", expanded=(idx==1)):
                    c_info1, c_info2 = st.columns(2)
                    with c_info1:
                        st.markdown(f"**¿Qué estás protegiendo?:** {r['protection_goal']}")
                        st.markdown(f"**Umbral de tolerancia sugerido:** `{r['capital_pct']}`")
                        st.markdown(f"**Spread minorista estimado:** `{r['spread_bps']} bps`")
                    with c_info2:
                        st.markdown(f"**Momentum 60d del par:** `+{r['momentum']}%`")
                        st.markdown(f"**Volatilidad 30d:** `{r['volatilidad']}%`")
                        st.markdown(f"**Punto de invalidación:** 🛑 *{r['invalidation_point']}*")
        else:
            st.warning(f"No hay suficientes datos cruzados para {hold_curr}.")

        # Section 5: Riesgos y Advertencias
        st.markdown("### 5. Riesgos y Advertencias del Mercado Cambiario")
        with st.expander("⚠️ Ver detalle de riesgos operativos, spreads y correlaciones ocultas"):
            st.markdown("""
            * **Spreads y comisiones minoristas:** A diferencia de terminales interbancarias, casas de cambio y bancos aplican márgenes del 0.5% al 2.5% sobre la tasa spot. Los cálculos asumen spreads estimados de mercado.
            * **Riesgo de Gap de fin de semana:** Los mercados de FX cierran los viernes a las 5:00 PM EST. Anuncios geopolíticos o de bancos centrales durante el fin de semana pueden abrir con saltos abruptos de precio (*gaps*).
            * **Liquidez reducida en divisas emergentes/exóticas:** Pares como COP, ARS, KES, NGN, VND o UAH presentan riesgo de iliquidez, controles cambiarios o spreads amplios. Prioriza majors y liquid crosses.
            * **Correlación Oculta:** Pares que parecen diversos (ej. EUR/USD y DKK/USD) tienen correlación superior al 0.95. Rotar entre ellos no aporta diversificación real.
            * **Aviso Legal:** *Este módulo es exclusivamente para análisis cuantitativo e investigación de mercados. No constituye asesoría financiera ni recomendación personalizada de inversión.*
            """)

        # Section 6: Exportables y Copiar recomendación
        st.markdown("### 6. Exportar Oportunidades y Recomendaciones")
        col_c1, col_c2, col_c3 = st.columns(3)

        with col_c1:
            if not opportunities_df.empty:
                top_p = opportunities_df.iloc[0]
                text_memo = (
                    f"MEMO FX-PULSE ({datetime.utcnow().strftime('%Y-%m-%d')}):\n"
                    f"Oportunidad de Convicción: {top_p['origen']} -> {top_p['destino']} ({top_p['señal']})\n"
                    f"Score Convicción: {top_p['score_compuesto']} | Momentum 60d: +{top_p['momentum_60d_pct']}%\n"
                    f"Sharpe Par: {top_p['sharpe_par']} | Spread Est: {top_p['spread_estimado_bps']} bps\n"
                    f"Tesis: Rotación de capital orientada a preservación y apreciación con baja volatilidad.\n"
                    f"Invalidación: Deshacer si retroceso supera 2.5% o momentum < +1.0%.\n"
                    f"Generado por fx_pulse. No es asesoría financiera."
                )
                st.text_area("📋 Texto de recomendación para compartir:", value=text_memo, height=120)

        with col_c2:
            if not opportunities_df.empty:
                csv_bytes = opportunities_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Descargar Matriz en CSV",
                    data=csv_bytes,
                    file_name=f"fx_opportunities_{datetime.utcnow().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )

        with col_c3:
            if not opportunities_df.empty:
                pdf_path = export_opportunities_to_pdf(opportunities_df)
                with open(pdf_path, "rb") as f:
                    st.download_button(
                        label="📄 Descargar Informe en PDF",
                        data=f,
                        file_name=os.path.basename(pdf_path),
                        mime="application/pdf"
                    )

        # Section 7: Alertas Automáticas por Correo (Gmail SMTP)
        st.markdown("### 7. ⚡ Alertas por Correo Electrónico (Gmail SMTP)")
        st.markdown(
            "Envío automático a `jhancarlosperezcasanova@gmail.com` mediante `smtplib`. "
            "La alerta se dispara **SOLO** si se cumplen simultáneamente: Score ≥ 0.75, Momentum ≥ 2%, Sharpe ≥ 1.5, Vol 30d < 25%, Spread < 15 bps y Liquidez 'major' o 'cross'."
        )

        col_mail1, col_mail2 = st.columns([2, 1])
        with col_mail1:
            qualifying = [row.to_dict() for _, row in opportunities_df.iterrows() if is_high_conviction(row.to_dict())]
            st.info(f"Oportunidades de muy alta convicción detectadas hoy: **{len(qualifying)}**")
            if qualifying:
                st.write(f"Candidato principal: `{qualifying[0]['origen']} ➔ {qualifying[0]['destino']}` (Score: {qualifying[0]['score_compuesto']})")

        with col_mail2:
            if st.button("📧 Probar / Disparar Alerta por Correo"):
                target_alert = qualifying[0] if qualifying else opportunities_df.iloc[0].to_dict()
                success, msg = send_high_conviction_alert(target_alert)
                if success:
                    st.success(msg)
                else:
                    st.warning(msg)
                    st.caption("Configura tu contraseña de aplicación de Gmail en `.env` (variable `SMTP_APP_PASSWORD`).")

    # -------------------------------------------------------------------------
    # TAB: EVOLUCIÓN NORMALIZADA
    # -------------------------------------------------------------------------
    with main_tab_market:
        st.subheader("Desempeño Relativo vs USD (Base 100)")
        st.markdown("Evolución del poder adquisitivo de la divisa extranjera respecto al dólar americano.")
        fig_multiseries = plot_normalized_multiseries(all_data, selected_currencies)
        st.plotly_chart(fig_multiseries, use_container_width=True)

    # -------------------------------------------------------------------------
    # TAB: SEMÁFORO DE REGÍMENES
    # -------------------------------------------------------------------------
    with main_tab_regimes:
        metrics_df = compute_all_metrics(all_data, dxy_series, rf_rate=rf_rate)
        st.subheader("🚦 Semáforo de Regímenes de Mercado (Ventana de 60 días)")
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

    # -------------------------------------------------------------------------
    # TAB: RANKING & MÉTRICAS
    # -------------------------------------------------------------------------
    with main_tab_metrics:
        metrics_df = compute_all_metrics(all_data, dxy_series, rf_rate=rf_rate)
        corr_matrix = compute_correlation_matrix(all_data[selected_currencies] if selected_currencies else all_data)
        st.subheader("📋 Tabla Maestra de Métricas Cuantitativas")
        try:
            styled_df = (
                metrics_df.style.background_gradient(subset=["Ret_1y (%)", "Sharpe_Ratio", "Momentum_60d (%)"], cmap="RdYlGn")
                                .background_gradient(subset=["Volatilidad_Anual (%)", "Max_Drawdown (%)"], cmap="Reds_r")
                                .format(precision=2)
            )
            st.dataframe(styled_df, height=500, use_container_width=True)
        except Exception:
            st.dataframe(metrics_df.round(2), height=500, use_container_width=True)

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

    # -------------------------------------------------------------------------
    # TAB: MATRIZ DE CORRELACIÓN
    # -------------------------------------------------------------------------
    with main_tab_corr:
        corr_matrix = compute_correlation_matrix(all_data[selected_currencies] if selected_currencies else all_data)
        st.subheader("🔗 Matriz de Correlación Cruzada de Retornos Diarios")
        fig_corr = plot_correlation_heatmap(corr_matrix)
        st.plotly_chart(fig_corr, use_container_width=True)

    # -------------------------------------------------------------------------
    # TAB: DISTRIBUCIÓN DE RIESGO
    # -------------------------------------------------------------------------
    with main_tab_risk:
        metrics_df = compute_all_metrics(all_data, dxy_series, rf_rate=rf_rate)
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
    st.caption("FX-Pulse Quantitative Terminal | Módulo de Oportunidades y Arbitraje Cuantitativo de Divisas.")


if __name__ == "__main__":
    main()
