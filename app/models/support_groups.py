from tortoise import fields, models

from app.models.users import User


class SupportGroup(models.Model):
    id = fields.IntField(pk=True)
    group_name = fields.CharField(max_length=100)
    invite_code = fields.CharField(max_length=50, unique=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "support_groups"


class GroupMember(models.Model):
    id = fields.IntField(pk=True)
    group: SupportGroup = fields.ForeignKeyField(
        "models.SupportGroup", related_name="members", on_delete=fields.CASCADE
    )  # type: ignore[assignment]
    group_id: int
    user: User = fields.ForeignKeyField("models.User", related_name="group_memberships", on_delete=fields.CASCADE)  # type: ignore[assignment]
    user_id: int
    leaderboard_score = fields.IntField(default=0)
    joined_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "group_members"
