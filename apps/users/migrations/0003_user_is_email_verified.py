# Generated manually for is_email_verified field on User model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0002_emailverificationcode"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="is_email_verified",
            field=models.BooleanField(
                default=False,
                help_text="Designates whether this user has verified their email address.",
                verbose_name="Is email verified",
            ),
        ),
    ]
