"""나이 계산 로직.

[재설계] 처음엔 생년(연도)을 안 받고 "나이 직접입력 + 생일(월/일)"로 가상 생년을 역산해서
계산했으나, 카카오 비즈앱 전환 후 실제 생년월일을 받아올 가능성이 생겨서 실제 생년월일
(birth_date)을 그대로 받는 표준 방식으로 단순화했다. 나이는 항상 이 함수로 그 자리에서
계산되고, DB에 별도로 저장/갱신하지 않는다(그래서 "나이를 마지막으로 입력한 날짜" 같은
기준점 관리가 아예 필요 없어졌다).
"""

from datetime import date


def compute_age(birth_date: date, today: date | None = None) -> int:
    """생년월일로 만 나이를 계산한다. 생일이 아직 안 지났으면 1살 덜 셈."""
    today = today or date.today()
    age = today.year - birth_date.year
    if (today.month, today.day) < (birth_date.month, birth_date.day):
        age -= 1
    return age


def resolve_display_age(birth_date: date | None, today: date | None = None) -> int | None:
    """화면/AI에 보여줄 나이. 생년월일 미입력이면 None(미입력 상태 그대로 보여줌)."""
    if birth_date is None:
        return None
    return compute_age(birth_date, today)


def age_group(birth_date: date | None, today: date | None = None) -> str | None:
    """탈퇴 시 익명화 통계용 - 정확한 나이 대신 10년 단위 나이대("30대" 등)로 뭉갠다.
    나이+성별+희귀질환 조합으로 개인이 간접 재식별되는 위험을 줄이기 위함
    (app/models/withdrawn_stats.py 참고)."""
    age = resolve_display_age(birth_date, today)
    if age is None:
        return None
    decade = (age // 10) * 10
    return f"{decade}대"
