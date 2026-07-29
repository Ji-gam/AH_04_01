"""민감정보(자유서술형 텍스트) 컬럼을 저장/조회 시 투명하게 암호화/복호화하는 SQLAlchemy
타입. 모델 정의에서 컬럼 타입만 `EncryptedText`로 바꾸면, 나머지 코드(서비스/리포지토리/
라우터)는 전혀 안 건드리고도 자동으로 암호화된다 - 파이썬 코드 입장에서는 여전히 평문
문자열을 다루는 것처럼 보인다(예: `profile.special_notes = "땅콩 알레르기"`처럼 그대로 대입/
읽기 가능).

[중요 - 이 타입을 쓰면 안 되는 경우] DB에는 암호문만 저장되므로, 이 컬럼으로 SQL
WHERE절에서 값 비교/검색을 하면 절대 안 된다(항상 매치 실패). 이 프로젝트에서 실제로
`DiagnosisEntry.disease`(라이프스타일 알림 발송 대상을 SQL로 직접 필터링 - T-MED 콘텐츠
알림)와 `Profile.phone_number`(회원가입 시 중복확인 SQL 조회)가 이런 이유로 암호화 대상에서
제외됐다(2026-07-21 확인, app/repositories/disease_entry_repository.py:
list_profile_ids_by_disease / app/repositories/profile_repository.py: exists_by_phone_number).
자유서술 텍스트라 SQL 검색/필터링/정렬에 안 쓰이는 컬럼에만 적용할 것.
"""

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import Text
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator

from app.core import config


def _get_fernet() -> Fernet | None:
    """FIELD_ENCRYPTION_KEY가 .env에 없으면 None을 반환해서, 로컬 개발 중 키를 아직 안
    만든 사람도 평문 그대로 개발을 계속할 수 있게 한다 - 단, 배포 전엔 반드시 키를
    설정해야 한다(설정 안 하면 민감정보가 평문으로 저장됨).

    [주의] 일부러 캐싱을 안 한다. 처음엔 "키가 있을 때만 Fernet 인스턴스를 한 번 만들어
    재사용"하는 방식으로 캐싱했는데, 테스트에서 "이전 테스트가 키를 설정해 캐싱된 인스턴스가
    남아있는 상태에서, 다음 테스트가 키를 해제해도 옛 인스턴스를 계속 써버리는" 버그가
    실제로 발견됐다(2026-07-21, pytest로 실제 검증하다 찾음). `Fernet(key)` 생성 자체가
    가벼운 연산(base64 디코딩 정도)이라, 매번 새로 만들어도 성능에 영향이 없고, 이런
    종류의 "캐시가 최신 설정을 못 따라가는" 버그를 아예 원천 차단하는 게 더 안전하다."""
    if not config.FIELD_ENCRYPTION_KEY:
        return None
    return Fernet(config.FIELD_ENCRYPTION_KEY.encode("utf-8"))


# REQ-DOC-003: app/core/storage/encrypted_file_storage.py가 문서 이미지(바이너리) 암호화에
# 이 키 관리 로직을 그대로 재사용한다 - 위의 "일부러 캐싱 안 함" 이유가 여기도 동일하게
# 적용되므로 별도 구현 대신 이 함수를 공개해서 import한다.
get_fernet = _get_fernet


class EncryptedText(TypeDecorator):
    """DB 컬럼 타입은 그대로 TEXT를 쓰되(암호문도 결국 문자열이라 마이그레이션으로 컬럼
    타입을 바꿀 필요가 없다), 저장 직전(`process_bind_param`)에 암호화하고 조회 직후
    (`process_result_value`)에 복호화한다."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect: Dialect) -> str | None:
        if value is None or value == "":
            return value
        fernet = _get_fernet()
        if fernet is None:
            return value
        return fernet.encrypt(value.encode("utf-8")).decode("utf-8")

    def process_result_value(self, value: str | None, dialect: Dialect) -> str | None:
        if value is None or value == "":
            return value
        fernet = _get_fernet()
        if fernet is None:
            return value
        try:
            return fernet.decrypt(value.encode("utf-8")).decode("utf-8")
        except InvalidToken:
            # 키 설정 전에 이미 저장돼있던 평문 데이터, 또는 아직 암호화 마이그레이션
            # (app/scripts/encrypt_existing_health_text.py) 전인 기존 데이터 - 복호화에
            # 실패해도 요청 전체가 500 에러로 죽지 않도록, 저장된 값을 그대로 반환한다
            # (하위호환 목적의 안전장치 - 마이그레이션 완료 후엔 이 경로를 탈 일이 없다).
            return value
