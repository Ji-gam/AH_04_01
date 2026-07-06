import datetime

from app.dtos.symptom_log import SymptomLogCreate
from app.models.symptom_logs import SymptomLog
from app.models.users import User


class SymptomLogService:
    async def create_symptom_log(self, user: User, data: SymptomLogCreate) -> SymptomLog:
        recorded_at = data.recorded_at or datetime.datetime.now()

        new_log = await SymptomLog.create(
            user=user, symptom_notes=data.symptom_notes, severity_level=data.severity_level, recorded_at=recorded_at
        )
        return new_log
