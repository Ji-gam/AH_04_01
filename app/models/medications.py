from tortoise import fields, models


class Medication(models.Model):
    id = fields.IntField(pk=True)
    standard_code = fields.CharField(max_length=50, null=True)
    medication_name = fields.CharField(max_length=150)
    form_type = fields.CharField(max_length=30, null=True)  # TABLET / INJECTION 등
    dosage_guideline = fields.TextField(null=True)
    side_effects = fields.TextField(null=True)
    precautions = fields.TextField(null=True)
    storage_method = fields.TextField(null=True)

    # 알약 외형 검색용
    shape = fields.CharField(max_length=30, null=True)
    color = fields.CharField(max_length=30, null=True)
    letters = fields.CharField(max_length=50, null=True)

    class Meta:
        table = "medications"
