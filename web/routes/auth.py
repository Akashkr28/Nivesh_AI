"""
Authentication routes — signup, signin, verify, profile, logout.
"""

from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel, EmailStr, validator
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import asyncio

_email_executor = ThreadPoolExecutor(max_workers=2)


async def send_email_async(to_email, full_name, otp):
    """Run email sending in a background thread with a 10-second timeout.
    Never blocks the HTTP response — fire and forget."""
    loop = asyncio.get_event_loop()
    try:
        await asyncio.wait_for(
            loop.run_in_executor(_email_executor, send_verification_email, to_email, full_name, otp),
            timeout=10.0
        )
    except asyncio.TimeoutError:
        print(f"[NiveshAI] Email send timed out for {to_email}")
    except Exception as e:
        print(f"[NiveshAI] Email send error: {e}")

from web.auth.database import get_db, User
from web.auth.security import (
    hash_password, verify_password,
    create_access_token, decode_token,
    generate_verification_token, generate_uuid,
)
from web.auth.email_service import send_verification_email, send_welcome_email

router = APIRouter(prefix="/api/auth", tags=["Auth"])


# ── Request Models ──────────────────────────────────────────────────────────────

class SignUpRequest(BaseModel):
    email: str
    full_name: str
    password: str

    @validator("email")
    def validate_email(cls, v):
        v = v.strip().lower()
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Invalid email address")
        return v

    @validator("full_name")
    def validate_name(cls, v):
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Name must be at least 2 characters")
        return v

    @validator("password")
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        return v


class SignInRequest(BaseModel):
    email: str
    password: str

    @validator("email")
    def clean_email(cls, v):
        return v.strip().lower()


class VerifyOTPRequest(BaseModel):
    email: str
    otp: str

    @validator("email")
    def clean_email(cls, v):
        return v.strip().lower()


class UpdateProfileRequest(BaseModel):
    full_name: Optional[str] = None
    risk_profile: Optional[str] = None

    @validator("risk_profile")
    def validate_risk(cls, v):
        if v and v not in {"conservative", "moderate", "aggressive"}:
            raise ValueError("risk_profile must be conservative, moderate, or aggressive")
        return v


# ── Auth Dependency ──────────────────────────────────────────────────────────────

def get_current_user(authorization: str = Header(None), db: Session = Depends(get_db)) -> User:
    """Extract and validate JWT from Authorization header."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = authorization.split(" ", 1)[1]
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = db.query(User).filter(User.id == payload["sub"]).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user


# ── Routes ──────────────────────────────────────────────────────────────────────

@router.post("/signup", summary="Create a new account")
async def signup(req: SignUpRequest, db: Session = Depends(get_db)):
    # Check duplicate email
    if db.query(User).filter(User.email == req.email).first():
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    otp = generate_verification_token()
    user = User(
        id=generate_uuid(),
        email=req.email,
        full_name=req.full_name,
        hashed_password=hash_password(req.password),
        verification_token=otp,
        avatar_initials="".join(w[0].upper() for w in req.full_name.split()[:2]),
        is_verified=False,
    )
    db.add(user)
    db.commit()

    # Send email in background — never blocks the response
    asyncio.create_task(send_email_async(req.email, req.full_name, otp))

    # Check if email provider is configured to decide what to show
    import os
    has_email = bool(os.environ.get("RESEND_API_KEY") or
                     (os.environ.get("SMTP_EMAIL") and os.environ.get("SMTP_PASSWORD")))

    response = {
        "status": "otp_sent",
        "email": req.email,
    }
    if has_email:
        response["message"] = f"Verification code sent to {req.email}. Check your inbox (and spam folder)."
    else:
        response["message"] = "Use the verification code shown below to complete signup."
        response["otp_visible"] = otp

    return response


@router.post("/verify", summary="Verify email with OTP")
async def verify_otp(req: VerifyOTPRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="No account found with this email")
    if user.is_verified:
        raise HTTPException(status_code=400, detail="Account is already verified")
    if user.verification_token != req.otp.strip():
        raise HTTPException(status_code=400, detail="Incorrect verification code")

    user.is_verified = True
    user.verification_token = None
    db.commit()

    loop = asyncio.get_event_loop()
    loop.run_in_executor(_email_executor, send_welcome_email, user.email, user.full_name)
    token = create_access_token(user.id, user.email)

    return {
        "status": "verified",
        "token": token,
        "user": _user_response(user),
    }


@router.post("/signin", summary="Sign in to existing account")
async def signin(req: SignInRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    if not user.is_verified:
        otp = generate_verification_token()
        user.verification_token = otp
        db.commit()
        # Fire-and-forget — never blocks sign-in response
        asyncio.create_task(send_email_async(user.email, user.full_name, otp))
        raise HTTPException(
            status_code=403,
            detail="Email not verified. A new verification code has been sent to your inbox."
        )

    user.last_login = datetime.utcnow()
    db.commit()
    token = create_access_token(user.id, user.email)

    return {
        "status": "signed_in",
        "token": token,
        "user": _user_response(user),
    }


@router.get("/me", summary="Get current user profile")
async def get_me(current_user: User = Depends(get_current_user)):
    return _user_response(current_user)


@router.put("/profile", summary="Update user profile")
async def update_profile(
    req: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == current_user.id).first()
    if req.full_name:
        user.full_name = req.full_name.strip()
        user.avatar_initials = "".join(w[0].upper() for w in user.full_name.split()[:2])
    if req.risk_profile:
        user.risk_profile = req.risk_profile
    db.commit()
    return {"status": "updated", "user": _user_response(user)}


@router.put("/change-password", summary="Change account password")
async def change_password(
    current_password: str,
    new_password: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters")
    user = db.query(User).filter(User.id == current_user.id).first()
    if not verify_password(current_password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    user.hashed_password = hash_password(new_password)
    db.commit()
    return {"status": "password_changed"}


@router.delete("/account", summary="Permanently delete account and all user data")
async def delete_account(
    password: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Hard delete — removes user, all holdings, and all alerts.
    Requires password confirmation as final safety check.
    """
    from web.auth.database import Holding, Alert

    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect password. Account not deleted.")

    # Delete all associated data first (cascading manually)
    holdings_deleted = db.query(Holding).filter(Holding.user_id == user.id).delete()
    alerts_deleted   = db.query(Alert).filter(Alert.user_id == user.id).delete()
    db.delete(user)
    db.commit()

    return {
        "status": "deleted",
        "message": "Your account and all associated data have been permanently deleted.",
        "removed": {
            "holdings": holdings_deleted,
            "alerts": alerts_deleted,
        }
    }


@router.post("/resend-otp", summary="Resend verification OTP")
async def resend_otp(email: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email.strip().lower()).first()
    if not user:
        raise HTTPException(status_code=404, detail="No account found with this email")
    if user.is_verified:
        raise HTTPException(status_code=400, detail="Account is already verified")

    import os
    has_email = bool(os.environ.get("RESEND_API_KEY") or
                     (os.environ.get("SMTP_EMAIL") and os.environ.get("SMTP_PASSWORD")))
    otp = generate_verification_token()
    user.verification_token = otp
    db.commit()
    asyncio.create_task(send_email_async(user.email, user.full_name, otp))
    response = {"status": "otp_resent", "message": "New verification code sent"}
    if not has_email:
        response["otp_visible"] = otp
    return response


# ── Helper ──────────────────────────────────────────────────────────────────────

def _user_response(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "avatar_initials": user.avatar_initials,
        "risk_profile": user.risk_profile,
        "is_verified": user.is_verified,
        "created_at": str(user.created_at),
        "last_login": str(user.last_login) if user.last_login else None,
    }
