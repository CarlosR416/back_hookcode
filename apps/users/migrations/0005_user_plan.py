# Generated for User.plan field on users app

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0004_passwordresetcode"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="plan",
            field=models.CharField(
                choices=[("free", "Free"), ("pro", "Pro")],
                default="free",
                help_text="Designates the subscription plan or tier for this user.",
                max_length=20,
                verbose_name="Plan",
            ),
        ),
    ]
