from pydantic import BaseModel


class NicknameCheckResponse(BaseModel):
    available: bool
