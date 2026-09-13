"""
Email dispatch services for user verification and notifications.
"""

from datetime import timedelta
import secrets

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone, translation
from django.utils.translation import gettext as _

from .models import EmailVerificationCode, PasswordResetCode, User


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

    current_lang = translation.get_language() or "en"
    is_spanish = current_lang.lower().startswith("es")

    context = {
        "user": user,
        "code": code,
        "expiration_minutes": expiration_minutes,
        "is_spanish": is_spanish,
    }

    if is_spanish:
        subject = f"Tu código de verificación de HookCode: {code}"
    else:
        subject = _("Your HookCode Verification Code: %(code)s") % {"code": code}

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


def generate_and_send_password_reset_otp(user: User) -> PasswordResetCode:
    """
    Generate a 6-digit password reset OTP code, persist it to the database,
    and send it to the user's email address via the configured email transport (Brevo SMTP).
    """
    # Invalidate any existing unused password reset OTP codes for this user
    PasswordResetCode.objects.filter(user=user, is_used=False).update(is_used=True)

    expiration_minutes = getattr(settings, "EMAIL_OTP_EXPIRATION_MINUTES", 15)
    expires_at = timezone.now() + timedelta(minutes=expiration_minutes)
    code = generate_otp_code()

    reset_record = PasswordResetCode.objects.create(
        user=user,
        code=code,
        expires_at=expires_at,
    )

    current_lang = translation.get_language() or "en"
    is_spanish = current_lang.lower().startswith("es")

    context = {
        "user": user,
        "code": code,
        "expiration_minutes": expiration_minutes,
        "is_spanish": is_spanish,
    }


    if is_spanish:
        subject = f"Tu código de recuperación de contraseña de HookCode: {code}"
    else:
        subject = _("Your HookCode Password Reset Code: %(code)s") % {"code": code}

    html_content = render_to_string("users/emails/password_reset_otp.html", context)
    text_content = render_to_string("users/emails/password_reset_otp.txt", context)

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    msg.attach_alternative(html_content, "text/html")
    msg.send()

    return reset_record


