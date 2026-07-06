from app.dtos.appointment import AppointmentCreate
from app.models.appointments import Appointment
from app.models.users import User


class AppointmentService:
    async def create_appointment(self, user: User, data: AppointmentCreate) -> Appointment:
        new_appt = await Appointment.create(user=user, **data.model_dump())
        return new_appt
