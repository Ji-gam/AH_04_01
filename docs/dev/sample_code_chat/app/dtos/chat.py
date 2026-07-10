from pydantic import BaseModel


class ChatMessageRequest(BaseModel):
    message: str
