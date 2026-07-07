from app.services.user_health_context_service import UserHealthContextService


def test_get_context_returns_mock_history_for_known_profile():
    service = UserHealthContextService()

    context = service.get_context(profile_id=1)

    assert context["profile_id"] == 1
    assert context["conditions"] == ["당뇨"]
    assert context["family_history"] == ["암", "심장질환"]
    assert context["medications"] == [{"condition": "당뇨", "name": "메트포르민", "dose": "500mg", "times_per_day": 2}]


def test_get_context_differs_between_mock_profiles():
    service = UserHealthContextService()

    first = service.get_context(profile_id=1)
    second = service.get_context(profile_id=2)

    assert first["conditions"] != second["conditions"]


def test_get_context_returns_empty_history_for_unknown_profile():
    service = UserHealthContextService()

    context = service.get_context(profile_id=999)

    assert context == {
        "profile_id": 999,
        "conditions": [],
        "family_history": [],
        "medications": [],
        "goals": [],
    }


def test_get_context_returns_mock_history_for_profile_four():
    service = UserHealthContextService()

    context = service.get_context(profile_id=4)

    assert context["conditions"] == ["고혈압"]
    assert context["family_history"] == ["당뇨"]
    assert context["medications"] == [{"condition": "고혈압", "name": "발사르탄", "dose": "80mg", "times_per_day": 1}]
