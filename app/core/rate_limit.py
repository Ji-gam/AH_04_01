# app/core/rate_limit.py
# [T-AUTH-6] 로그인/회원가입 무차별 대입(brute force) 공격 방어용 Rate Limiter.
# 같은 IP에서 signup/login을 1분에 5회 넘게 시도하면 429(Too Many Requests)로 막는다.
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
