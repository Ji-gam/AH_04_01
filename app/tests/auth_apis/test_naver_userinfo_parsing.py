from app.services.oauth_clients import parse_naver_userinfo


def test_parse_naver_userinfo_prefers_nickname_over_name():
    # "이름칸=닉네임" 원칙 - 실명(name)과 닉네임(nickname)이 둘 다 오면 닉네임을 써야 한다.
    data = {
        "response": {
            "id": "naver-id-1",
            "email": "naveruser@naver.com",
            "name": "홍길동",
            "nickname": "길동이",
        }
    }
    result = parse_naver_userinfo(data)
    assert result.sns_id == "naver-id-1"
    assert result.email == "naveruser@naver.com"
    assert result.name == "길동이"


def test_parse_naver_userinfo_falls_back_to_name_when_no_nickname():
    # 닉네임 동의항목을 안 받았거나 값이 없는 경우 - 실명으로 대체
    data = {"response": {"id": "naver-id-2", "email": "noname@naver.com", "name": "홍길동"}}
    result = parse_naver_userinfo(data)
    assert result.name == "홍길동"


def test_parse_naver_userinfo_falls_back_to_default_when_neither_present():
    data = {"response": {"id": "naver-id-3", "email": "noname2@naver.com"}}
    result = parse_naver_userinfo(data)
    assert result.name == "네이버사용자"
