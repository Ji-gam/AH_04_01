"""REQ-DOC-003: 처방전/약봉투/진료기록 원본 이미지를 파일시스템에 암호화해서 저장/조회/삭제
하는 헬퍼. `app/core/db/encrypted_types.py`의 `EncryptedText`와 동일한 Fernet 키
(FIELD_ENCRYPTION_KEY)를 재사용하지만, 대상이 SQLAlchemy TEXT 컬럼이 아니라 디스크에 쓰는
바이너리(이미지) 파일이라 별도 모듈로 분리했다.

[EncryptedText와의 유일한 차이] 키가 없을 때 EncryptedText는 평문으로 저장하는 폴백을
쓰지만(자유서술 텍스트 컬럼 - 개발 편의 우선), 여기서는 그렇게 하지 않는다. 처방전/진료기록
원본 이미지를 평문으로 디스크에 남기는 것은 훨씬 파급력이 큰 실수라, 키가 없으면 그냥
저장 자체를 건너뛴다(경고 로그만 남기고 파일을 쓰지 않음) - 호출부(medication_service)는
`image_storage_key`를 None으로 둔 채로 OCR 인식 자체는 정상 진행한다."""

import logging
from pathlib import Path

from app.core.db.encrypted_types import get_fernet

logger = logging.getLogger("app.encrypted_file_storage")


def encrypt_and_write(path: Path, data: bytes) -> bool:
    """암호화해서 `path`에 쓴다. 키가 없으면 아무것도 쓰지 않고 False를 반환한다(호출부가
    저장이 스킵됐음을 알고 DB에 storage_key를 남기지 않도록)."""
    fernet = get_fernet()
    if fernet is None:
        logger.warning(
            "FIELD_ENCRYPTION_KEY 미설정 - 문서 이미지 저장을 건너뜁니다 (path=%s). "
            "OCR/약품인식은 정상 진행되지만 원본 이미지는 보관되지 않습니다.",
            path,
        )
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(fernet.encrypt(data))
    return True


def read_and_decrypt(path: Path) -> bytes:
    """복호화해서 원본 바이트를 반환한다. 키가 없거나 파일이 없으면 FileNotFoundError."""
    fernet = get_fernet()
    if fernet is None:
        raise FileNotFoundError(f"FIELD_ENCRYPTION_KEY 미설정으로 복호화 불가: {path}")
    return fernet.decrypt(path.read_bytes())


def delete_file(path: Path) -> None:
    """파일을 삭제한다. 이미 없어도 예외를 내지 않는다(멱등 삭제)."""
    path.unlink(missing_ok=True)
