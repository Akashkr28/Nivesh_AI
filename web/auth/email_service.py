"""
Email verification service.

Modes:
  1. SMTP (Gmail) — set SMTP_EMAIL and SMTP_PASSWORD env vars
  2. Console mode  — prints OTP to terminal (default, zero config)

Console mode is perfect for development and self-hosted use.
For production, set env vars and Gmail App Password.
"""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

SMTP_EMAIL    = os.environ.get("SMTP_EMAIL", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_HOST     = "smtp.gmail.com"
SMTP_PORT     = 587


def send_verification_email(to_email: str, full_name: str, otp: str) -> bool:
    """
    Send OTP verification email.
    Falls back to console print if SMTP not configured.
    Returns True on success.
    """
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        # Console mode — show OTP in terminal for dev use
        print("\n" + "="*50)
        print(f"  NiveshAI — Email Verification")
        print(f"  To: {to_email}")
        print(f"  Hi {full_name}, your OTP is: {otp}")
        print("="*50 + "\n")
        return True

    try:
        html = f"""
        <html><body style="font-family:Arial,sans-serif;background:#0d1117;color:#e6edf3;padding:40px;">
          <div style="max-width:480px;margin:auto;background:#161b22;border-radius:12px;padding:32px;border:1px solid #30363d;">
            <h1 style="color:#58a6ff;margin-bottom:8px;">NiveshAI</h1>
            <p style="color:#8b949e;font-size:13px;">AI-powered Market Analysis</p>
            <hr style="border:1px solid #30363d;margin:20px 0"/>
            <h2 style="font-size:18px;">Hi {full_name} 👋</h2>
            <p style="color:#8b949e;">Your email verification code:</p>
            <div style="background:#21262d;border-radius:8px;padding:20px;text-align:center;margin:20px 0;">
              <span style="font-size:36px;font-weight:800;letter-spacing:10px;color:#3fb950">{otp}</span>
            </div>
            <p style="color:#8b949e;font-size:13px;">This code expires in 10 minutes. If you didn't create a NiveshAI account, ignore this email.</p>
          </div>
        </body></html>
        """
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"NiveshAI — Your verification code is {otp}"
        msg["From"] = f"NiveshAI <{SMTP_EMAIL}>"
        msg["To"] = to_email
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.sendmail(SMTP_EMAIL, to_email, msg.as_string())

        return True
    except Exception as e:
        print(f"Email send failed: {e}")
        # Fallback to console
        print(f"\n[NiveshAI OTP for {to_email}]: {otp}\n")
        return True


def send_welcome_email(to_email: str, full_name: str) -> None:
    """Optional welcome email after successful verification."""
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        print(f"\n[NiveshAI] Welcome {full_name}! Account verified.\n")
        return

    try:
        html = f"""
        <html><body style="font-family:Arial,sans-serif;background:#0d1117;color:#e6edf3;padding:40px;">
          <div style="max-width:480px;margin:auto;background:#161b22;border-radius:12px;padding:32px;border:1px solid #30363d;">
            <h1 style="color:#58a6ff;">Welcome to NiveshAI 🎉</h1>
            <p>Hi {full_name},</p>
            <p>Your account is verified. Start analyzing markets — India &amp; Global.</p>
            <a href="http://localhost:8000/dashboard" style="display:inline-block;background:#58a6ff;color:#0d1117;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:700;margin-top:16px;">Open Dashboard</a>
          </div>
        </body></html>
        """
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Welcome to NiveshAI — Your account is ready"
        msg["From"] = f"NiveshAI <{SMTP_EMAIL}>"
        msg["To"] = to_email
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.sendmail(SMTP_EMAIL, to_email, msg.as_string())
    except Exception:
        pass
