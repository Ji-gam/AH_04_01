from app.services.oauth_clients import parse_kakao_userinfo


def test_parse_kakao_userinfo_with_email():
    data = {
        "id": 123456789,
        "kakao_account": {"email": "realuser@kakao.com", "profile": {"nickname": "카카오유저"}},
    }
    result = parse_kakao_userinfo(data)
    assert result.sns_id == "123456789"
    assert result.email == "realuser@kakao.com"
    assert result.name == "카카오유저"


def test_parse_kakao_userinfo_without_email_uses_temp_email():
    data = {"id": 987654321, "kakao_account": {"profile": {"nickname": "이메일없는유저"}}}
    result = parse_kakao_userinfo(data)
    assert result.email == "kakao_987654321@social.local"
    assert result.name == "이메일없는유저"


def test_parse_kakao_userinfo_without_nickname_falls_back():
    data = {"id": 555, "kakao_account": {}}
    result = parse_kakao_userinfo(data)
    assert result.name == "카카오사용자"
    assert result.email == "kakao_555@social.local"
