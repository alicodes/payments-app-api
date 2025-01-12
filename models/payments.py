from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from datetime import datetime


class Payment(BaseModel):
    payee_first_name: str
    payee_last_name: str
    payee_payment_status: str = Field(..., pattern="^(completed|due_now|overdue|pending)$")
    payee_added_date_utc: datetime
    payee_due_date: datetime
    payee_address_line_1: str
    payee_address_line_2: Optional[str]
    payee_city: str
    payee_country: str = Field(..., pattern="^[A-Z]{2}$")  # ISO 3166-1 alpha-2
    payee_province_or_state: Optional[str]
    payee_postal_code: str
    payee_phone_number: str = Field(..., pattern="^\+?[1-9]\d{1,14}$")  # E.164 format
    payee_email: EmailStr
    currency: str = Field(..., pattern="^[A-Z]{3}$")  # ISO 4217
    discount_percent: Optional[float]
    tax_percent: Optional[float]
    due_amount: float
    total_due: Optional[float] = None  # Calculated field