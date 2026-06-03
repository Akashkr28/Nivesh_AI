"""
SQLite database setup using SQLAlchemy.
Single file DB stored in data/niveshai.db — zero configuration needed.
"""

from sqlalchemy import create_engine, Column, String, Boolean, DateTime, Float, Integer, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

# In production (Railway), set DATABASE_URL env var to a persistent volume path.
# Falls back to local data/ directory for development.
_db_url = os.environ.get("DATABASE_URL")

if _db_url and _db_url.startswith("sqlite"):
    # Explicit SQLite path from environment
    DB_PATH = _db_url.replace("sqlite:///", "")
    engine = create_engine(_db_url, connect_args={"check_same_thread": False})
elif _db_url and _db_url.startswith("postgres"):
    # PostgreSQL for Railway (future upgrade path)
    DB_PATH = None
    engine = create_engine(_db_url)
else:
    # Local development default
    DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "niveshai.db")
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ── ORM Models ─────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id              = Column(String, primary_key=True)           # UUID
    email           = Column(String, unique=True, nullable=False)
    full_name       = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_verified     = Column(Boolean, default=False)
    verification_token = Column(String, nullable=True)
    avatar_initials = Column(String, default="")                 # e.g. "AK"
    risk_profile    = Column(String, default="moderate")         # conservative / moderate / aggressive
    created_at      = Column(DateTime, default=datetime.utcnow)
    last_login      = Column(DateTime, nullable=True)


class Holding(Base):
    __tablename__ = "holdings"

    id           = Column(String, primary_key=True)
    user_id      = Column(String, nullable=False)
    ticker       = Column(String, nullable=False)
    resolved_ticker = Column(String, nullable=False)
    company_name = Column(String, default="")
    quantity     = Column(Float, nullable=False)
    buy_price    = Column(Float, nullable=False)
    buy_date     = Column(String, nullable=True)
    notes        = Column(Text, default="")
    currency     = Column(String, default="INR")
    added_at     = Column(DateTime, default=datetime.utcnow)


class Alert(Base):
    __tablename__ = "alerts"

    id               = Column(String, primary_key=True)
    user_id          = Column(String, nullable=False)
    ticker           = Column(String, nullable=False)
    resolved_ticker  = Column(String, nullable=False)
    alert_type       = Column(String, nullable=False)
    value            = Column(Float, nullable=True)
    notes            = Column(Text, default="")
    active           = Column(Boolean, default=True)
    triggered        = Column(Boolean, default=False)
    last_regime      = Column(String, nullable=True)
    created_at       = Column(DateTime, default=datetime.utcnow)
    triggered_at     = Column(DateTime, nullable=True)


def init_db():
    """Create all tables if they don't exist."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency — yields a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
