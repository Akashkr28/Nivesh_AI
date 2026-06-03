"""
Pydantic request/response models for the API.
All models live here — imported by route files, never defined inline.
"""

from pydantic import BaseModel, Field, validator
from typing import Optional


class AnalyzeRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=20, description="Stock ticker symbol")
    period_years: int = Field(default=3, ge=1, le=10, description="Historical data period in years")

    @validator("ticker")
    def clean_ticker(cls, v):
        return v.strip().upper()


class HoldingRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=20)
    quantity: float = Field(..., gt=0, description="Number of shares")
    buy_price: float = Field(..., gt=0, description="Purchase price per share")
    buy_date: Optional[str] = Field(default=None, description="Date of purchase (YYYY-MM-DD)")
    notes: Optional[str] = Field(default="", max_length=200)

    @validator("ticker")
    def clean_ticker(cls, v):
        return v.strip().upper()


class AlertRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=20)
    alert_type: str = Field(..., description="One of: price_above, price_below, rsi_above, rsi_below, regime_change, momentum_above, momentum_below")
    value: Optional[float] = Field(default=None, description="Threshold value (not needed for regime_change)")
    notes: Optional[str] = Field(default="", max_length=200)

    @validator("ticker")
    def clean_ticker(cls, v):
        return v.strip().upper()

    @validator("alert_type")
    def validate_type(cls, v):
        valid = {"price_above", "price_below", "rsi_above", "rsi_below",
                 "regime_change", "momentum_above", "momentum_below"}
        if v not in valid:
            raise ValueError(f"alert_type must be one of: {', '.join(sorted(valid))}")
        return v
