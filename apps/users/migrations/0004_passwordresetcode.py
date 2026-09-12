# Generated for PasswordResetCode model on users app

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0003_user_is_email_verified"),
    ]

    operations = [
        migrations.CreateModel(
            name="PasswordResetCode",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=6, verbose_name="OTP Code")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Created at")),
                ("expires_at", models.DateTimeField(verbose_name="Expires at")),
                ("attempts", models.PositiveIntegerField(default=0, verbose_name="Failed attempts")),
                ("is_used", models.BooleanField(default=False, verbose_name="Is used")),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="password_reset_codes",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="User",
                    ),
                ),
            ],
            options={
                "verbose_name": "Password Reset Code",
                "verbose_name_plural": "Password Reset Codes",
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["user", "-created_at"], name="users_pwd_user_id_created_idx"),
                    models.Index(fields=["code"], name="users_pwd_code_idx"),
                ],
            },
        ),
    ]
