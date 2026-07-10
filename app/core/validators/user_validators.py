import re


def validate_password(password: str) -> str:
    if len(password) < 8:
        raise ValueError("비밀번호는 8자 이상이어야 합니다.")

    # 소문자를 포함하고 있는지
    if not re.search(r"[a-z]", password):
        raise ValueError("비밀번호에는 소문자, 특수문자, 숫자가 각 하나씩 포함되어야 합니다.")

    # 숫자를 포함하고 있는지
    if not re.search(r"[0-9]", password):
        raise ValueError("비밀번호에는 소문자, 특수문자, 숫자가 각 하나씩 포함되어야 합니다.")

    # 특수문자를 포함하고 있는지
    if not re.search(r"[^a-zA-Z0-9]", password):
        raise ValueError("비밀번호에는 소문자, 특수문자, 숫자가 각 하나씩 포함되어야 합니다.")

    return password


def validate_phone_number(phone_number: str) -> str:
    patterns = [
        r"010-\d{4}-\d{4}",  # 010-1234-5678
        r"010\d{8}",  # 01012345678
        r"\+8210\d{8}",  # +821012345678
    ]

    if not any(re.fullmatch(p, phone_number) for p in patterns):
        raise ValueError("유효하지 않은 휴대폰 번호 형식입니다.")

    return phone_number


def validate_height_cm(height_cm: float) -> float:
    if not (30 <= height_cm <= 250):
        raise ValueError("키는 30cm 이상 250cm 이하로 입력해주세요.")
    return height_cm


def validate_weight_kg(weight_kg: float) -> float:
    if not (2 <= weight_kg <= 300):
        raise ValueError("체중은 2kg 이상 300kg 이하로 입력해주세요.")
    return weight_kg
