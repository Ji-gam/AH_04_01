from app.services.ai_worker_gateway import AIWorkerUnavailableError
from app.services.exercise_service import _FALLBACK_MET, ExerciseMetEstimate, ExerciseService


class FakeGateway:
    def __init__(self, result: ExerciseMetEstimate | None = None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.call_count = 0

    async def call_structured(self, system_prompt: str, user_input: str, schema: type) -> ExerciseMetEstimate:
        self.call_count += 1
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


async def test_estimate_met_uses_ai_result_within_valid_range():
    gateway = FakeGateway(result=ExerciseMetEstimate(met_value=7.5))
    service = ExerciseService(gateway=gateway)

    result = await service.estimate_met("클라이밍")

    assert result.exercise_name == "클라이밍"
    assert result.met_value == 7.5
    assert gateway.call_count == 1


async def test_estimate_met_falls_back_when_gateway_unavailable():
    gateway = FakeGateway(error=AIWorkerUnavailableError("ai_worker 연결 실패"))
    service = ExerciseService(gateway=gateway)

    result = await service.estimate_met("클라이밍")

    assert result.met_value == _FALLBACK_MET


async def test_estimate_met_falls_back_when_ai_returns_out_of_range_value():
    """AI가 환각으로 비정상적인 값(예: 음수, 100)을 주면 폴백으로 대체해야 한다."""
    gateway = FakeGateway(result=ExerciseMetEstimate(met_value=999.0))
    service = ExerciseService(gateway=gateway)

    result = await service.estimate_met("이상한운동")

    assert result.met_value == _FALLBACK_MET


async def test_estimate_met_trims_whitespace_from_exercise_name():
    gateway = FakeGateway(result=ExerciseMetEstimate(met_value=5.0))
    service = ExerciseService(gateway=gateway)

    result = await service.estimate_met("  클라이밍  ")

    assert result.exercise_name == "클라이밍"
