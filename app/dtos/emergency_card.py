from app.dtos.base import BaseSerializerModel


class EmergencyCardUpsert(BaseSerializerModel):
    blood_type: str | None = None
    food_allergies: str | None = None
    medication_allergies: str | None = None
    past_history: str | None = None
    present_history: str | None = None
    family_history: str | None = None
    emergency_contacts: str | None = None


class EmergencyCardResponse(EmergencyCardUpsert):
    id: int
    user_id: int
