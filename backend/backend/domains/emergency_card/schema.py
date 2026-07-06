# backend/domains/emergency_card/schema.py
from typing import Optional
from pydantic import BaseModel


class EmergencyCardUpsert(BaseModel):
    blood_type: Optional[str] = None
    food_allergies: Optional[str] = None
    medication_allergies: Optional[str] = None
    past_history: Optional[str] = None
    present_history: Optional[str] = None
    family_history: Optional[str] = None
    emergency_contacts: Optional[str] = None


class EmergencyCardResponse(EmergencyCardUpsert):
    card_id: int
    user_id: int

    class Config:
        from_attributes = True
