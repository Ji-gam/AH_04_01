"""REQ-DOC-003: app/core/storage/encrypted_file_storage.py 단위 테스트 - 키 설정/미설정
각각에서 encrypt_and_write/read_and_decrypt/delete_file이 기대대로 동작하는지 확인한다."""

import pytest
from cryptography.fernet import Fernet

from app.core import config
from app.core.storage.encrypted_file_storage import delete_file, encrypt_and_write, read_and_decrypt

pytestmark = pytest.mark.asyncio


async def test_encrypt_and_write_then_read_and_decrypt_roundtrips(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "FIELD_ENCRYPTION_KEY", Fernet.generate_key().decode("utf-8"))
    path = tmp_path / "doc.enc"
    data = b"prescription photo bytes"

    stored = encrypt_and_write(path, data)

    assert stored is True
    assert path.exists()
    assert path.read_bytes() != data
    assert read_and_decrypt(path) == data


async def test_encrypt_and_write_skips_when_key_not_configured(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "FIELD_ENCRYPTION_KEY", None)
    path = tmp_path / "doc.enc"

    stored = encrypt_and_write(path, b"prescription photo bytes")

    assert stored is False
    assert not path.exists()


async def test_read_and_decrypt_raises_file_not_found_when_key_not_configured(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "FIELD_ENCRYPTION_KEY", Fernet.generate_key().decode("utf-8"))
    path = tmp_path / "doc.enc"
    encrypt_and_write(path, b"prescription photo bytes")

    monkeypatch.setattr(config, "FIELD_ENCRYPTION_KEY", None)
    with pytest.raises(FileNotFoundError):
        read_and_decrypt(path)


async def test_delete_file_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "FIELD_ENCRYPTION_KEY", Fernet.generate_key().decode("utf-8"))
    path = tmp_path / "doc.enc"
    encrypt_and_write(path, b"prescription photo bytes")
    assert path.exists()

    delete_file(path)
    assert not path.exists()

    delete_file(path)  # 두 번째 호출도 예외 없이 통과해야 함
