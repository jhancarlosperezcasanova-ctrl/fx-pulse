"""
fx_pulse CLI entry point.
Run with:
    python main.py
Options:
    --years: Number of years of history (default: 5)
    --export-all: Automatically triggers CSV and HTML export
"""

import sys
import argparse
import logging
from src.data_fetcher import FXDataFetcher, CURRENCIES
from src.metrics import compute_all_metrics, compute_correlation_matrix
from src.reporting import print_executive_summary, export_to_csv, export_to_html

logger = logging.getLogger("FXPulseMain")

def main():
    parser = argparse.ArgumentParser(description="FX-Pulse: Análisis Cuantitativo de Divisas Globales")
    parser.add_argument("--years", type=int, default=5, help="Años de histórico a analizar (defecto: 5)")
    parser.add_argument("--export-all", action="store_true", default=True, help="Exportar automáticamente CSV y HTML")
    args = parser.parse_args()

    print("\n" + "="*80)
    print(" 🚀 INICIANDO FX-PULSE :: MOTOR DE ANÁLISIS CUANTITATIVO DE DIVISAS")
    print(f" Analizando {len(CURRENCIES)} divisas sobre una ventana de {args.years} años...")
    print("="*80 + "\n")

    # 1. Fetch data
    fetcher = FXDataFetcher()
    all_data = fetcher.get_all_currencies_data(CURRENCIES, years=args.years)
    
    if all_data.empty:
        logger.error("❌ No se pudieron descargar datos de divisas. Finalizando proceso.")
        sys.exit(1)

    print(f"\n📊 Datos consolidados exitosamente: {all_data.shape[1]} divisas, {all_data.shape[0]} observaciones temporales.")

    # 2. Fetch DXY and Fed Funds
    dxy_df = fetcher.fetch_dxy_index((all_data.index[0]).strftime("%Y-%m-%d"))
    dxy_series = dxy_df["value"] if not dxy_df.empty else None
    rf_rate = fetcher.fetch_fed_funds_rate()
    print(f"💵 Tasa Libre de Riesgo utilizada (Fed Funds): {rf_rate * 100:.2f}%")

    # 3. Compute Metrics
    print("\n⚙️ Computando las 10 métricas financieras por divisa...")
    metrics_df = compute_all_metrics(all_data, dxy_series, rf_rate=rf_rate)
    corr_matrix = compute_correlation_matrix(all_data)

    # 4. Print Executive Summary
    print_executive_summary(metrics_df)

    # 5. Export results
    if args.export_all:
        csv_file = export_to_csv(metrics_df)
        html_file = export_to_html(all_data, metrics_df, corr_matrix, CURRENCIES[:10])
        print(f"📁 Reporte CSV generado en:  {csv_file}")
        print(f"🌐 Reporte HTML generado en: {html_file}")

    print("\n✨ Proceso finalizado. Para abrir el panel interactivo ejecuta:")
    print("   streamlit run app.py\n")

if __name__ == "__main__":
    main()
