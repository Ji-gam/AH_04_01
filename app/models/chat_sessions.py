from tortoise import fields, models

from app.models.users import User


class ChatSession(models.Model):
    id = fields.IntField(pk=True)
    user: User = fields.ForeignKeyField("models.User", related_name="chat_sessions", on_delete=fields.CASCADE)  # type: ignore[assignment]
    user_id: int
    session_title = fields.CharField(max_length=150, null=True)
    session_intent_mode = fields.CharField(max_length=30, null=True)  # DIET_ASSIST / PARENT_MONITOR
    has_injected_context = fields.BooleanField(default=False)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "chat_sessions"


class ChatMessage(models.Model):
    id = fields.IntField(pk=True)
    session: ChatSession = fields.ForeignKeyField(
        "models.ChatSession", related_name="messages", on_delete=fields.CASCADE
    )  # type: ignore[assignment]
    session_id: int
    sender_type = fields.CharField(max_length=15)  # USER / ASSISTANT
    message_text = fields.TextField()
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "chat_messages"
