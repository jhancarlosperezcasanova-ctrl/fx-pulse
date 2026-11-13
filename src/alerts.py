"""
Email notification module for FX-Pulse high-conviction opportunities.
Uses standard library smtplib and email.mime for zero-dependency reliability.
"""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import Header
from datetime import datetime
from typing import Dict, Any, Tuple
from dotenv import load_dotenv

load_dotenv()

DEFAULT_SENDER = ""
DEFAULT_RECIPIENT = ""
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def send_high_conviction_alert(opportunity: Dict[str, Any], dashboard_url: str = "http://localhost:8501", override_password: str = None) -> Tuple[bool, str]:
    """
    Sends an automated HTML email alert for a high conviction directional FX opportunity.
    Reads SMTP_APP_PASSWORD from .env, Streamlit secrets, or in-memory override.
    """
    app_password = (override_password or os.getenv("SMTP_APP_PASSWORD", "")).strip()
    sender_email = os.getenv("SMTP_SENDER_EMAIL", DEFAULT_SENDER).strip()
    recipient_email = os.getenv("SMTP_RECIPIENT_EMAIL", DEFAULT_RECIPIENT).strip()

    # Check for Streamlit secrets if running inside Streamlit Cloud
    if not app_password:
        try:
            import streamlit as st
            if hasattr(st, "secrets") and "SMTP_APP_PASSWORD" in st.secrets:
                app_password = str(st.secrets["SMTP_APP_PASSWORD"]).strip()
        except Exception:
            pass

    if not app_password:
        return False, "⚠️ No se ha configurado la Contraseña de Aplicación de Gmail (16 letras). Ingrésala abajo o en tu archivo .env / Secrets."

    # Validate ASCII characters: Gmail app passwords are strictly 16 ascii lowercase letters (e.g. 'abcd efgh ijkl mnop')
    try:
        app_password.encode('ascii')
    except UnicodeEncodeError:
        return False, "❌ La contraseña ingresada contiene caracteres con tildes o la letra 'ñ'. Debe ser una 'Contraseña de Aplicación' de Google (16 letras en minúscula, ej: 'abcd efgh ijkl mnop'), NO tu clave normal de Gmail ni la palabra 'contraseña'."

    # Clean whitespace in password (often copied with spaces like 'xxxx xxxx xxxx xxxx')
    clean_password = app_password.replace(" ", "")

    origen = opportunity.get("origen", "DIV_A")
    destino = opportunity.get("destino", "DIV_B")
    score = opportunity.get("score_compuesto", 0.0)
    mom_60d = opportunity.get("momentum_60d_pct", 0.0)
    vol_30d = opportunity.get("vol_30d_pct", 0.0)
    sharpe = opportunity.get("sharpe_par", 0.0)
    spread = opportunity.get("spread_estimado_bps", 0.0)
    now_date = datetime.utcnow().strftime("%Y-%m-%d")

    subject = f"[FX PULSE 🟢] Oportunidad de alta convicción: {origen}→{destino} | Score {score:.2f} | {now_date}"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #0f141c; color: #e6edf3; padding: 20px; }}
            .container {{ max-width: 650px; margin: auto; background-color: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 25px; }}
            h2 {{ color: #2ea043; margin-top: 0; }}
            .tag {{ display: inline-block; background-color: #238636; color: white; padding: 4px 10px; border-radius: 4px; font-weight: bold; font-size: 14px; }}
            table {{ width: 100%; border-collapse: collapse; margin: 20px 0; background: #0d1117; }}
            th, td {{ border: 1px solid #30363d; padding: 10px 12px; text-align: left; font-size: 14px; }}
            th {{ background-color: #21262d; color: #58a6ff; }}
            .highlight {{ color: #7ee787; font-weight: bold; }}
            .card {{ background-color: #21262d; border-left: 4px solid #58a6ff; padding: 12px 15px; margin: 15px 0; border-radius: 0 6px 6px 0; }}
            .btn {{ display: inline-block; background-color: #1f6feb; color: #ffffff !important; padding: 10px 18px; text-decoration: none; border-radius: 6px; font-weight: bold; margin-top: 15px; }}
            .footer {{ font-size: 12px; color: #8b949e; border-top: 1px solid #30363d; margin-top: 25px; padding-top: 15px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <span class="tag">ALERTA CUANTITATIVA FX</span>
            <h2>🚀 Oportunidad Direccional Detectada: {origen} ➔ {destino}</h2>
            <p>El motor cuantitativo de <b>FX-Pulse</b> ha identificado una configuración técnica de alta convicción para rotar capital desde <b>{origen}</b> hacia <b>{destino}</b>.</p>
            
            <table>
                <tr><th>Métrica Cuantitativa</th><th>Valor Registrado</th><th>Condición / Estado</th></tr>
                <tr><td>Score Compuesto de Convicción</td><td class="highlight">{score:.3f}</td><td>≥ 0.75 (Muy Alto)</td></tr>
                <tr><td>Momentum Par (60 días)</td><td class="highlight">+{mom_60d:.2f}%</td><td>Tendencia sostenida</td></tr>
                <tr><td>Ratio de Sharpe del Par</td><td class="highlight">{sharpe:.2f}</td><td>≥ 1.5 (Retorno/Riesgo premium)</td></tr>
                <tr><td>Volatilidad Anualizada (30d)</td><td>{vol_30d:.2f}%</td><td>Bajo control (&lt; 25%)</td></tr>
                <tr><td>Spread Minorista Estimado</td><td>{spread:.1f} bps</td><td>Alta liquidez (&lt; 15 bps)</td></tr>
            </table>

            <div class="card">
                <h4 style="margin: 0 0 8px 0; color: #58a6ff;">💡 Justificación Cuantitativa:</h4>
                <p style="margin: 0; font-size: 13px; line-height: 1.5;">
                    {destino} presenta fortaleza relativa dominante con aceleración de tendencia frente a {origen}. 
                    El ratio de retorno ajustado por volatilidad (Sharpe {sharpe:.2f}) minimiza las pérdidas por oscilaciones intermedias.
                </p>
            </div>

            <div class="card" style="border-left-color: #d29922;">
                <h4 style="margin: 0 0 8px 0; color: #d29922;">🛑 Punto de Invalidación de la Tesis:</h4>
                <p style="margin: 0; font-size: 13px; line-height: 1.5;">
                    Deshacer la rotación de divisas si el momentum a 60 días cae por debajo de +1.0% o si el par quiebra a la baja un retroceso del 2.5% respecto a su cotización actual.
                </p>
            </div>

            <p style="text-align: center;">
                <a href="{dashboard_url}" class="btn">Abrir Panel Interactivo de Oportunidades</a>
            </p>

            <div class="footer">
                <p>Generado automáticamente por <b>fx_pulse</b> el {now_date}.<br>
                <i>Aviso legal: Esta notificación es producto de modelos cuantitativos y estadísticos. No es asesoría financiera personalizada ni recomendación de inversión.</i></p>
            </div>
        </div>
    </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = sender_email
    msg["To"] = recipient_email

    # Plain text alternative
    text_content = (
        f"ALERTA FX-PULSE: Oportunidad de alta conviccion {origen} -> {destino}\n"
        f"Score: {score:.2f} | Momentum 60d: {mom_60d:.2f}% | Sharpe: {sharpe:.2f} | Vol 30d: {vol_30d:.2f}%\n"
        f"Punto de invalidacion: Deshacer si retrocede > 2.5% o momentum < +1.0%.\n"
        f"Dashboard: {dashboard_url}\n\n"
        f"Generado automaticamente por fx_pulse. No es asesoria financiera."
    )

    msg.attach(MIMEText(text_content, "plain", "utf-8"))
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=12) as server:
            server.starttls()
            server.login(sender_email, clean_password)
            server.sendmail(sender_email, [recipient_email], msg.as_string())
        return True, f"✅ ¡Alerta enviada exitosamente a {recipient_email} vía Gmail SMTP!"
    except smtplib.SMTPAuthenticationError:
        return False, "❌ Error de autenticación SMTP (Gmail): La contraseña de aplicación fue rechazada. Asegúrate de generar una contraseña de aplicación en https://myaccount.google.com/apppasswords con verificación en dos pasos activa."
    except Exception as e:
        return False, f"Fallo en envío SMTP: {str(e)}"
