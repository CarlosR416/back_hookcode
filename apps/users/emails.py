"""
Email dispatch services for user verification and notifications.
"""

from datetime import timedelta
import secrets

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.translation import gettext as _

from .models import EmailVerificationCode, User


def generate_otp_code() -> str:
    """Generate a cryptographically secure 6-digit numeric OTP code."""
    return f"{secrets.randbelow(900000) + 100000}"


def generate_and_send_otp(user: User) -> EmailVerificationCode:
    """
    Generate a 6-digit OTP code, persist it to the database, and send it
    to the user's email address via the configured email transport (Brevo SMTP).
    """
    # Invalidate any existing unused OTP codes for this user
    EmailVerificationCode.objects.filter(user=user, is_used=False).update(is_used=True)

    expiration_minutes = getattr(settings, "EMAIL_OTP_EXPIRATION_MINUTES", 15)
    expires_at = timezone.now() + timedelta(minutes=expiration_minutes)
    code = generate_otp_code()

    otp_record = EmailVerificationCode.objects.create(
        user=user,
        code=code,
        expires_at=expires_at,
    )

    context = {
        "user": user,
        "code": code,
        "expiration_minutes": expiration_minutes,
    }

    subject = _("Your WiFi Tickets Verification Code: %(code)s") % {"code": code}
    html_content = render_to_string("users/emails/verify_otp.html", context)
    text_content = render_to_string("users/emails/verify_otp.txt", context)

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    msg.attach_alternative(html_content, "text/html")
    msg.send()

    return otp_record
