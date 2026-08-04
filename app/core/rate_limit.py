# app/core/rate_limit.py
# [T-AUTH-6] 로그인/회원가입 무차별 대입(brute force) 공격 방어용 Rate Limiter.
# 같은 IP에서 signup/login을 1분에 5회 넘게 시도하면 429(Too Many Requests)로 막는다.
#
# [2026-08-03 복원] 원래 이 파일이 있었는데(feature 브랜치 히스토리 중간 커밋
# `44a1999`), 이후 어느 시점에 코드베이스에서 빠졌다 - 로그인 실패 5회 잠금(계정
# 단위, app/services/auth.py)은 그대로 살아있어서 겉으로는 문제가 없어 보였지만,
# 이건 계정 단위 방어라 IP 단위로 여러 이메일을 훑는 공격이나 회원가입 어뷰징은
# 못 막고 있었다. 원래 코드 구조(Limiter 정의만 여기, 라우터에서 @limiter.limit로
# 사용, main.py에 미들웨어 등록)를 그대로 복원한다.
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
