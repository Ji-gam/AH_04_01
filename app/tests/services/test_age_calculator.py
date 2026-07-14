from datetime import date

from app.services.age_calculator import compute_age, resolve_display_age


def test_age_before_birthday_this_year():
    # 생일이 아직 안 지났으면 1살 덜 계산된다.
    age = compute_age(date(1996, 9, 15), today=date(2026, 7, 13))
    assert age == 29


def test_age_after_birthday_this_year():
    # 생일이 지났으면 정확히 그 나이.
    age = compute_age(date(1996, 7, 10), today=date(2026, 7, 13))
    assert age == 30


def test_age_on_exact_birthday():
    age = compute_age(date(1996, 7, 13), today=date(2026, 7, 13))
    assert age == 30


def test_leap_day_birthday_handled_safely():
    # 생일이 2/29인 경우도 문제없이 계산되어야 한다.
    age = compute_age(date(2000, 2, 29), today=date(2026, 7, 13))
    assert age == 26


def test_resolve_display_age_without_birth_date_returns_none():
    # 생년월일 미입력이면 나이도 알 수 없다(그냥 None).
    assert resolve_display_age(None) is None


def test_resolve_display_age_with_birth_date_computes_age():
    result = resolve_display_age(date(1996, 7, 10), today=date(2026, 7, 13))
    assert result == 30
