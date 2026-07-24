"""건강정보 텍스트 필드 암호화용 키를 1회 생성하는 스크립트.

사용법:
    uv run python app/scripts/generate_field_encryption_key.py

출력된 FIELD_ENCRYPTION_KEY를 .env에 그대로 붙여넣으면 된다.
[중요] 한 번 생성한 뒤엔 계속 재사용할 것 - 키를 바꾸면 그 전에 암호화해서 저장해둔
모든 건강정보 텍스트(특이사항/기타/진단병력 상세/가족력 상세)를 다시는 복호화할 수 없게
된다(영구 손실). VAPID_PRIVATE_KEY와 마찬가지로 절대 git에 커밋하지 말고, Slack DM 등
안전한 채널로만 팀원과 공유할 것.
"""

from cryptography.fernet import Fernet


def main() -> None:
    key = Fernet.generate_key().decode("utf-8")
    print("아래 한 줄을 .env에 그대로 붙여넣으세요:\n")
    print(f"FIELD_ENCRYPTION_KEY={key}")


if __name__ == "__main__":
    main()
