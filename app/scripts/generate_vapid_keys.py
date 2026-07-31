"""VAPID(웹푸시 서명용) 키쌍을 1회 생성하는 스크립트.

사용법:
    uv run python app/scripts/generate_vapid_keys.py

출력된 VAPID_PUBLIC_KEY / VAPID_PRIVATE_KEY를 .env에 그대로 붙여넣으면 된다.
한 번 생성한 뒤엔 계속 재사용할 것 - 키를 바꾸면 그 전에 만들어진 모든 브라우저 구독이
전부 무효화된다(사용자들이 다시 알림 권한을 허용해야 함).
"""

import base64

from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid02


def main() -> None:
    vapid = Vapid02()
    vapid.generate_keys()

    # 웹푸시 표준(RFC 8292)이 요구하는 형태: 공개키는 "비압축 EC 포인트"(0x04 + X + Y, 65바이트),
    # 개인키는 32바이트 raw scalar. 둘 다 base64url(패딩 없이)로 인코딩해서 .env에 넣는다 -
    # 프론트의 `pushManager.subscribe({ applicationServerKey: ... })`에 그대로 쓸 수 있는 형태.
    public_bytes = vapid.public_key.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    private_bytes = vapid.private_key.private_numbers().private_value.to_bytes(32, "big")

    public_key_b64url = base64.urlsafe_b64encode(public_bytes).decode("utf-8").rstrip("=")
    private_key_b64url = base64.urlsafe_b64encode(private_bytes).decode("utf-8").rstrip("=")

    print("아래 두 줄을 .env에 그대로 붙여넣으세요:\n")
    print(f"VAPID_PUBLIC_KEY={public_key_b64url}")
    print(f"VAPID_PRIVATE_KEY={private_key_b64url}")


if __name__ == "__main__":
    main()
