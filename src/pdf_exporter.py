"""
PDF Export Module for FX Opportunities using reportlab.
Generates an institutional, executive PDF dossier.
"""

import os
from datetime import datetime
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors


def export_opportunities_to_pdf(opportunities_df: pd.DataFrame, output_dir: str = "output") -> str:
    """Generates a clean, professional PDF report of directional FX opportunities."""
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    file_path = os.path.join(output_dir, f"fx_opportunities_{timestamp}.pdf")

    doc = SimpleDocTemplate(
        file_path,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#0f2b48'),
        spaceAfter=6
    )
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#555555'),
        spaceAfter=15
    )
    h2_style = ParagraphStyle(
        'Heading2Style',
        parent=styles['Heading2'],
        fontSize=13,
        leading=16,
        textColor=colors.HexColor('#1f6feb'),
        spaceBefore=10,
        spaceAfter=8
    )
    cell_style = ParagraphStyle(
        'CellText',
        parent=styles['Normal'],
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#222222')
    )
    cell_header = ParagraphStyle(
        'CellHeader',
        parent=styles['Normal'],
        fontSize=8,
        leading=10,
        fontName='Helvetica-Bold',
        textColor=colors.white
    )
    disclaimer_style = ParagraphStyle(
        'DisclaimerText',
        parent=styles['Italic'],
        fontSize=7,
        leading=9,
        textColor=colors.HexColor('#777777')
    )

    story = []

    # Title & Header
    story.append(Paragraph("<b>FX-PULSE :: TABLERO DE OPORTUNIDADES DE CAMBIO</b>", title_style))
    story.append(Paragraph(
        f"Informe Cuantitativo Direccional | Generado el {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')} | Cobertura de Pares Líquidos",
        subtitle_style
    ))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#1f6feb'), spaceAfter=15))

    # Executive Overview
    story.append(Paragraph("<b>1. Resumen de la Matriz Direccional (Top Convicción)</b>", h2_style))
    story.append(Paragraph(
        "Esta matriz analiza la conveniencia de rotar tenencias desde una divisa de origen hacia una de destino, "
        "optimizando el ratio de Sharpe del par, el momentum relativo a 60 días y penalizando la volatilidad y el spread.",
        styles['Normal']
    ))
    story.append(Spacer(1, 10))

    # Table of Opportunities
    table_data = [
        [
            Paragraph("<b>Par (A ➔ B)</b>", cell_header),
            Paragraph("<b>Cambio 30d</b>", cell_header),
            Paragraph("<b>Vol. 30d</b>", cell_header),
            Paragraph("<b>Sharpe</b>", cell_header),
            Paragraph("<b>Mom. 60d</b>", cell_header),
            Paragraph("<b>Spread (bps)</b>", cell_header),
            Paragraph("<b>Convicción</b>", cell_header),
            Paragraph("<b>Señal</b>", cell_header),
        ]
    ]

    for _, row in opportunities_df.head(15).iterrows():
        table_data.append([
            Paragraph(f"<b>{row['par']}</b>", cell_style),
            Paragraph(f"{row['chg_30d_pct']}%", cell_style),
            Paragraph(f"{row['vol_30d_pct']}%", cell_style),
            Paragraph(f"{row['sharpe_par']}", cell_style),
            Paragraph(f"{row['momentum_60d_pct']}%", cell_style),
            Paragraph(f"{row['spread_estimado_bps']} bps", cell_style),
            Paragraph(f"<b>{row['score_compuesto']}</b>", cell_style),
            Paragraph(str(row['señal']), cell_style),
        ])

    opp_table = Table(table_data, colWidths=[90, 60, 60, 50, 65, 75, 75, 45])
    opp_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f2b48')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e1e4e8')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#0f2b48')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f6f8fa')])
    ]))
    story.append(opp_table)
    story.append(Spacer(1, 15))

    # Risk and Rules Section
    story.append(Paragraph("<b>2. Protocolo de Gestión de Riesgo e Invalidación</b>", h2_style))
    story.append(Paragraph(
        "• <b>Punto de Invalidación General:</b> Deshacer cualquier posición si el momentum a 60 días cae por debajo de +1.0% "
        "o si el ratio del par sufre una corrección superior al 2.5% respecto al momento de entrada.<br/>"
        "• <b>Umbral de Tolerancia:</b> Asignar entre el 10% y el 30% del capital según el perfil de riesgo (nunca rotar el 100% en un solo par).<br/>"
        "• <b>Riesgo de Gap y Noticias:</b> Mantener precaución ante reuniones de bancos centrales (FOMC, BCE) y publicaciones de IPC.",
        styles['Normal']
    ))
    story.append(Spacer(1, 15))

    # Disclaimer
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#d0d7de'), spaceAfter=10))
    story.append(Paragraph(
        "<b>ADVERTENCIA:</b> Este reporte es generado mediante modelos cuantitativos y algoritmos de ingeniería de datos. "
        "No constituye asesoramiento financiero ni recomendación de inversión personalizada.",
        disclaimer_style
    ))

    doc.build(story)
    return file_path
