# backend/domains/appointment/schema.py
import datetime
from typing import Optional
from pydantic import BaseModel


class AppointmentCreate(BaseModel):
    hospital_name: str
    doctor_name: Optional[str] = None
    doctor_contact: Optional[str] = None
    appointment_at: datetime.datetime
    memo: Optional[str] = None


class AppointmentResponse(AppointmentCreate):
    appointment_id: int
