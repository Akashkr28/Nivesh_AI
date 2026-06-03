"""
Email Service — Priority order:
  1. Resend API  (set RESEND_API_KEY in Railway — one time, done forever)
  2. Gmail SMTP  (set SMTP_EMAIL + SMTP_PASSWORD in Railway — alternative)
  3. Console     (no env vars — OTP shown on screen as fallback)

Resend setup (recommended — 5 minutes, one time only):
  1. Go to https://resend.com → Sign Up (free, no credit card)
  2. Dashboard → API Keys → Create API Key → copy it
  3. Railway → Nivesh_AI → Variables → add:
       RESEND_API_KEY = re_xxxxxxxxxxxxxxxx
  That's it. Every user gets their OTP by email from that point on.
  Free tier: 3,000 emails/month, 100/day — more than enough.
"""

import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "").strip()
SMTP_EMAIL     = os.environ.get("SMTP_EMAIL", "").strip()
SMTP_PASSWORD  = os.environ.get("SMTP_PASSWORD", "").strip()

# Sender name/address shown in user's inbox
FROM_NAME    = "NiveshAI"
FROM_ADDRESS = "onboarding@resend.dev"   # Resend sandbox — works without domain verification


def send_verification_email(to_email: str, full_name: str, otp: str) -> bool:
    """
    Send OTP verification email.
    Returns True if email was delivered, False if shown on screen instead.
    Tries Resend → Gmail SMTP → console fallback in that order.
    """
    html = _build_otp_html(full_name, otp)
    subject = f"{otp} is your NiveshAI verification code"

    # ── Priority 1: Resend ──────────────────────────────────────────
    if RESEND_API_KEY:
        try:
            import resend
            resend.api_key = RESEND_API_KEY
            resend.Emails.send({
                "from":    f"{FROM_NAME} <{FROM_ADDRESS}>",
                "to":      [to_email],
                "subject": subject,
                "html":    html,
            })
            print(f"[NiveshAI] OTP sent via Resend to {to_email}")
            return True
        except Exception as e:
            print(f"[NiveshAI] Resend failed: {e} — falling back to SMTP")

    # ── Priority 2: Gmail SMTP ──────────────────────────────────────
    if SMTP_EMAIL and SMTP_PASSWORD:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"]    = f"{FROM_NAME} <{SMTP_EMAIL}>"
            msg["To"]      = to_email
            msg.attach(MIMEText(html, "html"))

            ctx = ssl.create_default_context()
            with smtplib.SMTP("smtp.gmail.com", 587) as server:
                server.ehlo()
                server.starttls(context=ctx)
                server.login(SMTP_EMAIL, SMTP_PASSWORD)
                server.sendmail(SMTP_EMAIL, to_email, msg.as_string())

            print(f"[NiveshAI] OTP sent via Gmail to {to_email}")
            return True
        except Exception as e:
            print(f"[NiveshAI] Gmail SMTP failed: {e} — showing OTP on screen")

    # ── Priority 3: Console fallback (dev mode) ─────────────────────
    print("\n" + "="*52)
    print("  NiveshAI OTP (no email provider configured)")
    print(f"  To:  {to_email}")
    print(f"  OTP: {otp}")
    print("="*52 + "\n")
    return False   # False = frontend should show OTP on screen


def send_welcome_email(to_email: str, full_name: str) -> None:
    """Welcome email after successful verification."""
    if not RESEND_API_KEY and not (SMTP_EMAIL and SMTP_PASSWORD):
        print(f"[NiveshAI] Welcome {full_name}! ({to_email}) — no email provider configured")
        return

    html = f"""<!DOCTYPE html>
    <html><body style="margin:0;padding:0;background:#04060e;font-family:-apple-system,sans-serif">
    <table width="100%" cellpadding="0" cellspacing="0" style="background:#04060e;padding:40px 20px">
      <tr><td align="center">
        <table width="520" cellpadding="0" cellspacing="0"
               style="background:#0d1020;border:1px solid rgba(255,255,255,.08);border-radius:16px;overflow:hidden">
          <tr><td style="background:linear-gradient(135deg,#4f9eff22,#22d3a022);padding:28px;text-align:center;border-bottom:1px solid rgba(255,255,255,.08)">
            <div style="font-size:1.8rem;margin-bottom:6px">📈</div>
            <div style="font-size:1.3rem;font-weight:800">
              <span style="color:#4f9eff">Nivesh</span><span style="color:#22d3a0">AI</span>
            </div>
          </td></tr>
          <tr><td style="padding:36px 40px;color:#f0f4ff">
            <h2 style="font-size:1.2rem;margin-bottom:10px">Welcome, {full_name}! 🎉</h2>
            <p style="color:rgba(240,244,255,.55);line-height:1.7;margin-bottom:24px;font-size:.9rem">
              Your account is verified. Start analyzing Indian and global stocks — plain English, no jargon.
            </p>
            <a href="https://niveshai-production-3635.up.railway.app/dashboard"
               style="display:inline-block;background:linear-gradient(135deg,#4f9eff,#22d3a0);color:#04060e;font-weight:700;padding:13px 28px;border-radius:10px;text-decoration:none;font-size:.95rem">
              Open Dashboard →
            </a>
            <hr style="border:none;border-top:1px solid rgba(255,255,255,.06);margin:28px 0">
            <p style="font-size:.75rem;color:rgba(240,244,255,.25)">Educational purposes only — not financial advice.</p>
          </td></tr>
        </table>
      </td></tr>
    </table>
    </body></html>"""

    subject = f"Welcome to NiveshAI, {full_name}! 🚀"

    if RESEND_API_KEY:
        try:
            import resend
            resend.api_key = RESEND_API_KEY
            resend.Emails.send({
                "from": f"{FROM_NAME} <{FROM_ADDRESS}>",
                "to": [to_email],
                "subject": subject,
                "html": html,
            })
        except Exception as e:
            print(f"[NiveshAI] Welcome email failed (Resend): {e}")
    elif SMTP_EMAIL and SMTP_PASSWORD:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"]    = f"{FROM_NAME} <{SMTP_EMAIL}>"
            msg["To"]      = to_email
            msg.attach(MIMEText(html, "html"))
            ctx = ssl.create_default_context()
            with smtplib.SMTP("smtp.gmail.com", 587) as server:
                server.ehlo(); server.starttls(context=ctx)
                server.login(SMTP_EMAIL, SMTP_PASSWORD)
                server.sendmail(SMTP_EMAIL, to_email, msg.as_string())
        except Exception as e:
            print(f"[NiveshAI] Welcome email failed (SMTP): {e}")


def _build_otp_html(full_name: str, otp: str) -> str:
    digits = "".join(
        f'<td style="padding:4px"><div style="width:46px;height:56px;background:#1a1f3a;border:2px solid rgba(79,158,255,.4);border-radius:10px;font-size:1.6rem;font-weight:900;color:#4f9eff;text-align:center;line-height:56px;font-family:monospace">{d}</div></td>'
        for d in otp
    )
    return f"""<!DOCTYPE html>
    <html><body style="margin:0;padding:0;background:#04060e;font-family:-apple-system,sans-serif">
    <table width="100%" cellpadding="0" cellspacing="0" style="background:#04060e;padding:40px 20px">
      <tr><td align="center">
        <table width="520" cellpadding="0" cellspacing="0"
               style="background:#0d1020;border:1px solid rgba(255,255,255,.08);border-radius:16px;overflow:hidden">
          <tr><td style="background:linear-gradient(135deg,#4f9eff22,#22d3a022);padding:24px 40px;text-align:center;border-bottom:1px solid rgba(255,255,255,.08)">
            <div style="font-size:1.6rem;margin-bottom:5px">📈</div>
            <div style="font-size:1.2rem;font-weight:800">
              <span style="color:#4f9eff">Nivesh</span><span style="color:#22d3a0">AI</span>
            </div>
          </td></tr>
          <tr><td style="padding:36px 40px;color:#f0f4ff">
            <h2 style="font-size:1.2rem;font-weight:800;margin-bottom:10px">Hi {full_name}, verify your email</h2>
            <p style="color:rgba(240,244,255,.55);font-size:.88rem;line-height:1.7;margin-bottom:28px">
              Enter this 6-digit code to activate your NiveshAI account.
              It expires in <strong style="color:#f0f4ff">10 minutes</strong>.
            </p>
            <table cellpadding="0" cellspacing="0" style="margin:0 auto 28px"><tr>{digits}</tr></table>
            <p style="color:rgba(240,244,255,.3);font-size:.8rem;line-height:1.6">
              If you didn't request this, ignore this email. No action needed.
            </p>
            <hr style="border:none;border-top:1px solid rgba(255,255,255,.06);margin:24px 0">
            <p style="font-size:.72rem;color:rgba(240,244,255,.2)">
              NiveshAI · Educational purposes only · Not financial advice
            </p>
          </td></tr>
        </table>
      </td></tr>
    </table>
    </body></html>"""
