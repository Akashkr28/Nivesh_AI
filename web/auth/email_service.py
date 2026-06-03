"""
Email Service — sends OTP verification emails via Gmail SMTP.

Setup (one-time):
1. Enable 2-Step Verification on your Google account
   → https://myaccount.google.com/security

2. Generate a Gmail App Password
   → https://myaccount.google.com/apppasswords
   → Select "Mail" + "Other (custom name)" → name it "NiveshAI"
   → Copy the 16-character password

3. Add to Railway environment variables:
   SMTP_EMAIL    = yourgmail@gmail.com
   SMTP_PASSWORD = xxxx xxxx xxxx xxxx  (the 16-char app password)

That's it — emails will be sent automatically on every signup.
"""

import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

SMTP_EMAIL    = os.environ.get("SMTP_EMAIL", "").strip()
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "").strip()
SMTP_HOST     = "smtp.gmail.com"
SMTP_PORT     = 587

is_email_configured = bool(SMTP_EMAIL and SMTP_PASSWORD)


def send_verification_email(to_email: str, full_name: str, otp: str) -> bool:
    """
    Send OTP verification email.
    Returns True on success, False on failure.
    Falls back to console print if SMTP is not configured.
    """
    if not is_email_configured:
        # Development / unconfigured mode — print to console only
        print("\n" + "="*52)
        print("  NiveshAI — Email Verification (Console Mode)")
        print(f"  To:   {to_email}")
        print(f"  Name: {full_name}")
        print(f"  OTP:  {otp}")
        print("="*52 + "\n")
        return False   # False = OTP should be shown on screen

    try:
        html_body = _build_otp_email(full_name, otp)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"{otp} is your NiveshAI verification code"
        msg["From"]    = f"NiveshAI <{SMTP_EMAIL}>"
        msg["To"]      = to_email

        msg.attach(MIMEText(html_body, "html"))

        context = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls(context=context)
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.sendmail(SMTP_EMAIL, to_email, msg.as_string())

        print(f"[NiveshAI] OTP email sent to {to_email}")
        return True

    except smtplib.SMTPAuthenticationError:
        print("[NiveshAI] Gmail authentication failed. Check SMTP_EMAIL and SMTP_PASSWORD.")
        return False
    except smtplib.SMTPException as e:
        print(f"[NiveshAI] SMTP error: {e}")
        return False
    except Exception as e:
        print(f"[NiveshAI] Email send failed: {e}")
        return False


def send_welcome_email(to_email: str, full_name: str) -> None:
    """Send a welcome email after successful verification."""
    if not is_email_configured:
        print(f"[NiveshAI] Welcome {full_name}! Account verified: {to_email}")
        return

    try:
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head><meta charset="UTF-8"></head>
        <body style="margin:0;padding:0;background:#04060e;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
          <table width="100%" cellpadding="0" cellspacing="0" style="background:#04060e;padding:40px 20px">
            <tr><td align="center">
              <table width="520" cellpadding="0" cellspacing="0" style="background:#0d1020;border:1px solid rgba(255,255,255,.08);border-radius:16px;overflow:hidden">
                <tr>
                  <td style="background:linear-gradient(135deg,#4f9eff22,#22d3a022);padding:32px;text-align:center;border-bottom:1px solid rgba(255,255,255,.08)">
                    <div style="font-size:2rem;margin-bottom:8px">📈</div>
                    <div style="font-size:1.4rem;font-weight:800;background:linear-gradient(90deg,#4f9eff,#22d3a0);-webkit-background-clip:text;-webkit-text-fill-color:transparent">NiveshAI</div>
                  </td>
                </tr>
                <tr>
                  <td style="padding:36px 40px;color:#f0f4ff">
                    <h2 style="font-size:1.4rem;font-weight:800;margin-bottom:12px;color:#f0f4ff">Welcome, {full_name}! 🎉</h2>
                    <p style="color:rgba(240,244,255,.6);line-height:1.7;margin-bottom:24px">
                      Your NiveshAI account is verified and ready. Start analyzing Indian and global stocks — plain English, no jargon.
                    </p>
                    <a href="https://niveshai-production-3635.up.railway.app/dashboard"
                       style="display:inline-block;background:linear-gradient(135deg,#4f9eff,#22d3a0);color:#04060e;font-weight:700;font-size:.95rem;padding:13px 28px;border-radius:10px;text-decoration:none">
                      Open Dashboard →
                    </a>
                    <hr style="border:none;border-top:1px solid rgba(255,255,255,.06);margin:32px 0">
                    <p style="font-size:.78rem;color:rgba(240,244,255,.3);line-height:1.6">
                      NiveshAI is for educational purposes only and does not constitute financial advice.
                    </p>
                  </td>
                </tr>
              </table>
            </td></tr>
          </table>
        </body>
        </html>
        """
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Welcome to NiveshAI, {full_name}! 🚀"
        msg["From"]    = f"NiveshAI <{SMTP_EMAIL}>"
        msg["To"]      = to_email
        msg.attach(MIMEText(html_body, "html"))

        context = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls(context=context)
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.sendmail(SMTP_EMAIL, to_email, msg.as_string())

    except Exception as e:
        print(f"[NiveshAI] Welcome email failed: {e}")


def _build_otp_email(full_name: str, otp: str) -> str:
    """Build the HTML email body for OTP verification."""
    digits = "".join(
        f'<td style="padding:6px;"><div style="width:44px;height:54px;background:#1a1f3a;border:2px solid rgba(79,158,255,.4);border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:1.6rem;font-weight:900;color:#4f9eff;text-align:center;line-height:54px;font-family:monospace">{d}</div></td>'
        for d in otp
    )
    return f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"></head>
    <body style="margin:0;padding:0;background:#04060e;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
      <table width="100%" cellpadding="0" cellspacing="0" style="background:#04060e;padding:40px 20px">
        <tr><td align="center">
          <table width="520" cellpadding="0" cellspacing="0" style="background:#0d1020;border:1px solid rgba(255,255,255,.08);border-radius:16px;overflow:hidden">

            <!-- Header -->
            <tr>
              <td style="background:linear-gradient(135deg,#4f9eff22,#22d3a022);padding:28px 40px;text-align:center;border-bottom:1px solid rgba(255,255,255,.08)">
                <div style="font-size:1.8rem;margin-bottom:6px">📈</div>
                <div style="font-size:1.3rem;font-weight:800;letter-spacing:-.02em">
                  <span style="color:#4f9eff">Nivesh</span><span style="color:#22d3a0">AI</span>
                </div>
              </td>
            </tr>

            <!-- Body -->
            <tr>
              <td style="padding:36px 40px;color:#f0f4ff">
                <h2 style="font-size:1.25rem;font-weight:800;margin-bottom:10px;color:#f0f4ff">
                  Hi {full_name}, verify your email
                </h2>
                <p style="color:rgba(240,244,255,.55);line-height:1.7;margin-bottom:28px;font-size:.9rem">
                  Enter this 6-digit code to complete your NiveshAI account setup.
                  The code expires in <strong style="color:#f0f4ff">10 minutes</strong>.
                </p>

                <!-- OTP Digits -->
                <table cellpadding="0" cellspacing="0" style="margin:0 auto 28px">
                  <tr>{digits}</tr>
                </table>

                <p style="color:rgba(240,244,255,.35);font-size:.82rem;line-height:1.65;margin-bottom:0">
                  If you didn't create a NiveshAI account, ignore this email. No action needed.
                </p>

                <hr style="border:none;border-top:1px solid rgba(255,255,255,.06);margin:28px 0">
                <p style="font-size:.75rem;color:rgba(240,244,255,.25);line-height:1.6;margin:0">
                  This email was sent by NiveshAI · For educational purposes only · Not financial advice
                </p>
              </td>
            </tr>

          </table>
        </td></tr>
      </table>
    </body>
    </html>
    """
