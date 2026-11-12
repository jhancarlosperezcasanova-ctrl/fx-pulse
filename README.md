# FX-Pulse 💱 — Radar Cuantitativo & Terminal de Divisas Globales

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Streamlit](https://img.shields.io/badge/UI-Streamlit-red.svg)](https://streamlit.io/)
[![Plotly](https://img.shields.io/badge/Charts-Plotly-brightgreen.svg)](https://plotly.com/)

**FX-Pulse** es una terminal cuantitativa de grado institucional y autocontenida para el análisis, procesamiento, ranking y visualización del comportamiento histórico y actual de más de **40 divisas globales** contra el Dólar Estadounidense (USD), el Euro (EUR) y la canasta de Derechos Especiales de Giro (**SDR**) del FMI.

---

## 🌟 Características Principales

1. **Cobertura de 41 Divisas**:
   - *G10 & Desarrolladas*: EUR, GBP, JPY, CHF, AUD, CAD, NZD, SEK, NOK, DKK, SGD, HKD.
   - *Mercados Emergentes & Exóticas*: MXN, BRL, CNY, INR, KRW, ZAR, TRY, PLN, HUF, CZK, ILS, THB, MYR, IDR, PHP, COP, CLP, PEN, ARS, UAH, VND, TWD, AED, SAR, QAR, KWD, EGP, KES, NGN.
2. **Motor Multi-fuente con Failover Automático y Backoff Exponencial**:
   - `exchangerate.host` (Diario)
   - `Alpha Vantage` (FX Daily/Intraday)
   - `FRED St. Louis` (DXY, Tasas Fed Funds y REER)
   - `yfinance` (Fallback ultra-robusto sin interrupciones)
   - Caché local en **SQLite** para optimizar peticiones y tiempos de carga.
3. **10 Métricas Financieras Avanzadas**:
   - Retornos acumulados multitemporales (7d, 30d, 90d, 180d, 1y, 3y, 5y).
   - Volatilidad anualizada de retornos logarítmicos ($\sigma \sqrt{252}$).
   - Máximo Drawdown (MDD) y duración de recuperación en días.
   - Momentum: cambio porcentual y pendiente de regresión lineal (20d, 60d, 120d).
   - Matriz de correlación cruzada completa y correlación contra el **DXY**.
   - Ratio de Sharpe con tasa libre de riesgo dinámica ($R_f$ Fed Funds).
   - Skewness (asimetría) y Kurtosis (colas pesadas/riesgo de cisne negro).
   - Comparativa relativa contra USD, EUR y canasta SDR del FMI.
   - Tipo de Cambio Real Efectivo (REER).
   - Detección de régimen de mercado con semáforo (🟢/🟡/🔴).
4. **Visualización y Reportes**:
   - Dashboard interactivo con **Streamlit** y **Plotly**.
   - Exportación de métricas a **CSV** e informe **HTML autocontenido** offline.
   - Resumen ejecutivo en terminal con rankings Top-5 y Bottom-5.

---

## 🛠️ Instalación y Requisitos

Requiere **Python 3.10+**.

```bash
# 1. Clonar el repositorio
git clone https://github.com/<TU_USUARIO>/fx-pulse.git
cd fx-pulse

# 2. Crear entorno virtual
python -m venv .venv
source .venv/bin/activate  # En Windows: .venv\Scripts\activate

# 3. Instalar dependencias
pip install -r requirements.txt
```

### Configuración de Claves de API (Opcional)
Copia o renombra el archivo `.env.example` a `.env` si posees claves gratuitas para Alpha Vantage, FRED o exchangerate.host:
```env
ALPHA_VANTAGE_API_KEY=tu_api_key
FRED_API_KEY=tu_api_key
EXCHANGERATE_HOST_API_KEY=tu_api_key
```
*(Si no configuras claves, el motor usará automáticamente el fallback de Yahoo Finance sin detenerse)*.

---

## 🚀 Uso

### 1. Interfaz Web (Dashboard Interactivo Streamlit)
```bash
streamlit run app.py
```

### 2. Modo Terminal / CLI (Pipeline Completo y Exportación)
```bash
python main.py --years 5 --export-all
```

### 3. Ejecutar Pruebas Unitarias
```bash
pytest tests/
```

---

## 📖 Guía para el Inversor Retail: "Cómo Interpretarlo"

### 1. ¿Qué significa un Ratio de Sharpe > 1 vs < 0?
* **Sharpe > 1.0**: Significa que la divisa ofreció un retorno superior a la tasa libre de riesgo del dólar (bonos del Tesoro de EE.UU.) compensando holgadamente la volatilidad asumida. Un Sharpe > 1.5 es excepcional en FX.
* **Sharpe entre 0 y 1.0**: La divisa superó la tasa libre de riesgo, pero con un nivel de oscilaciones que no compensa tan eficazmente el riesgo asumido.
* **Sharpe < 0**: Desempeño desfavorable. Mantener esa divisa rindió menos que tener dólares en un bono de la Fed sin riesgo, o sufrió una depreciación neta.

### 2. Cómo leer el Drawdown para Dimensionar el Riesgo
* El **Máximo Drawdown (MDD)** mide la pérdida porcentual máxima experimentada desde un pico hasta el punto más bajo del ciclo.
* En divisas de mercados emergentes o con inflación alta (como ARS, TRY, EGP), los drawdowns pueden superar el -40% o -60% y tardar años en recuperarse (o no recuperarse jamás).
* Si tu horizonte de inversión no tolera caídas del -15%, deberás evitar divisas con MDD severos o mitigar la exposición mediante coberturas cambiarias (*hedging*).

### 3. Qué hacer con el Heatmap de Correlación (Diversificación)
* **Correlación cercana a +1.0**: Dos divisas se mueven casi idénticas contra el dólar (ej. EUR y DKK, o AUD y NZD). Poseer ambas no aporta verdadera diversificación.
* **Correlación cercana a 0.0 o negativa**: Combinar divisas con baja o negativa correlación amortigua la volatilidad total de una cartera global. Si una divisa cae ante un shock regional, la otra tiende a resistir.
* **Carry Trade**: Ayuda a identificar divisas de fondeo (baja tasa, correlación estable) vs divisas de inversión (alta tasa).

### 4. Cómo usar el Semáforo de Señal (🟢 / 🟡 / 🔴)
* 🟢 **Alcista (Fortalecimiento)**: La media móvil rápida (20d) está por encima de la lenta (60d) y el momentum es claramente positivo. Indica fortaleza relativa frente al dólar.
* 🟡 **Lateral / Rango**: Las medias se cruzan o están convergentes y el precio fluctúa dentro de una banda estrecha. Ideal para estrategias de reversión a la media o rangos.
* 🔴 **Bajista (Depreciación)**: Medias en pendiente negativa y momentum vendedor. Sugiere precaución o reducción de exposición en activos denominados en dicha moneda.

---

> [!WARNING]
> ### ⚠️ Advertencia de Riesgo Regulatorio
> **Esto es una herramienta de análisis cuantitativo e ingeniería de datos con propósitos informativos y educativos, NO constituye recomendación de inversión ni asesoría financiera.** El mercado de divisas extranjeras (Forex) conlleva un alto nivel de riesgo y puede no ser adecuado para todos los inversores.

---

## 📄 Licencia

Este proyecto está bajo la Licencia **MIT**. Consulta el archivo [LICENSE](LICENSE) para más detalles.
