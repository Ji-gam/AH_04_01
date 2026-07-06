import datetime

from app.dtos.base import BaseSerializerModel


class AppointmentCreate(BaseSerializerModel):
    hospital_name: str
    doctor_name: str | None = None
    doctor_contact: str | None = None
    appointment_at: datetime.datetime
    memo: str | None = None


class AppointmentResponse(AppointmentCreate):
    id: int
