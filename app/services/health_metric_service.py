import datetime

from app.dtos.health_metric import HealthMetricCreate
from app.models.health_metrics import HealthMetric
from app.models.users import User


class HealthMetricService:
    async def create_metric(self, user: User, data: HealthMetricCreate) -> HealthMetric:
        # recorded_at 이 제공되지 않은 경우 현지 시간 적용
        recorded_at = data.recorded_at or datetime.datetime.now()
        metric_data = data.model_dump(exclude={"recorded_at"})

        new_metric = await HealthMetric.create(user=user, recorded_at=recorded_at, **metric_data)
        return new_metric
