"""
Sub-domain tests: 6-digit OTP Password Reset Lifecycle.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.users.models import PasswordResetCode

User = get_user_model()


class PasswordResetOTPTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.request_url = reverse("auth:users-password-reset-request")
        cls.confirm_url = reverse("auth:users-password-reset-confirm")

    def setUp(self):
        mail.outbox.clear()
        self.user = User.objects.create_user(
            username="resetuser@example.com",
            email="resetuser@example.com",
            password="OldPassword123!",
            first_name="Reset",
            last_name="Tester",
            is_active=True,
            is_email_verified=True,
        )

    def test_password_reset_request_valid_email_dispatches_email_and_creates_otp(self):
        """A valid email request creates an OTP record and sends an email via Brevo SMTP."""
        payload = {"email": "resetuser@example.com"}
        response = self.client.post(self.request_url, data=payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("detail", response.data)

        # Check database record
        otp_records = PasswordResetCode.objects.filter(user=self.user, is_used=False)
        self.assertEqual(otp_records.count(), 1)
        otp = otp_records.first()
        self.assertEqual(len(otp.code), 6)
        self.assertTrue(otp.code.isdigit())

        # Check dispatched email
        self.assertEqual(len(mail.outbox), 1)
        sent_email = mail.outbox[0]
        self.assertIn("resetuser@example.com", sent_email.to)
        self.assertIn("HookCode", sent_email.subject)
        self.assertIn(otp.code, sent_email.subject)
        self.assertIn(otp.code, sent_email.body)

    def test_password_reset_request_nonexistent_email_returns_generic_success(self):
        """Nonexistent email returns generic success without creating OTP or sending email (anti-enumeration)."""
        payload = {"email": "nobody@example.com"}
        response = self.client.post(self.request_url, data=payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["detail"],
            "If an account with that email exists, a password reset code has been sent.",
        )
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(PasswordResetCode.objects.count(), 0)

    def test_password_reset_request_cooldown_enforced(self):
        """Rapid consecutive requests within 60s cooldown return 429 Too Many Requests."""
        payload = {"email": "resetuser@example.com"}
        first_resp = self.client.post(self.request_url, data=payload, format="json")
        self.assertEqual(first_resp.status_code, status.HTTP_200_OK)

        second_resp = self.client.post(self.request_url, data=payload, format="json")
        self.assertEqual(second_resp.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(second_resp.data["code"], "resend_cooldown")

    def test_password_reset_confirm_success(self):
        """Valid OTP and matching passwords successfully resets password and marks OTP as used."""
        otp = PasswordResetCode.objects.create(
            user=self.user,
            code="123456",
            expires_at=timezone.now() + timedelta(minutes=15),
        )

        payload = {
            "email": "resetuser@example.com",
            "otp": "123456",
            "password": "NewSecurePassword456!",
            "password_confirm": "NewSecurePassword456!",
        }
        response = self.client.post(self.confirm_url, data=payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["detail"], "Password has been reset successfully.")

        # Verify OTP is marked used
        otp.refresh_from_db()
        self.assertTrue(otp.is_used)

        # Verify password updated
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewSecurePassword456!"))
        self.assertFalse(self.user.check_password("OldPassword123!"))
        self.assertTrue(self.user.is_email_verified)
        self.assertTrue(self.user.is_active)

    def test_password_reset_confirm_invalid_otp_increments_attempts(self):
        """Submitting an incorrect OTP code increments attempt counter and returns 400."""
        otp = PasswordResetCode.objects.create(
            user=self.user,
            code="123456",
            expires_at=timezone.now() + timedelta(minutes=15),
        )

        payload = {
            "email": "resetuser@example.com",
            "otp": "999999",
            "password": "NewSecurePassword456!",
            "password_confirm": "NewSecurePassword456!",
        }
        response = self.client.post(self.confirm_url, data=payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "invalid_otp")

        otp.refresh_from_db()
        self.assertEqual(otp.attempts, 1)
        self.assertFalse(otp.is_used)

        # Password must remain unchanged
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("OldPassword123!"))

    def test_password_reset_confirm_too_many_attempts_locks_code(self):
        """Reaching max attempts (5) locks the OTP from further attempts."""
        PasswordResetCode.objects.create(
            user=self.user,
            code="123456",
            expires_at=timezone.now() + timedelta(minutes=15),
            attempts=5,
        )

        payload = {
            "email": "resetuser@example.com",
            "otp": "123456",
            "password": "NewSecurePassword456!",
            "password_confirm": "NewSecurePassword456!",
        }
        response = self.client.post(self.confirm_url, data=payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "too_many_attempts")

    def test_password_reset_confirm_expired_otp(self):
        """Expired OTP is rejected with expired_otp code."""
        PasswordResetCode.objects.create(
            user=self.user,
            code="123456",
            expires_at=timezone.now() - timedelta(minutes=1),
        )

        payload = {
            "email": "resetuser@example.com",
            "otp": "123456",
            "password": "NewSecurePassword456!",
            "password_confirm": "NewSecurePassword456!",
        }
        response = self.client.post(self.confirm_url, data=payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "expired_otp")

    def test_password_reset_confirm_password_mismatch(self):
        """Mismatched password and password_confirm returns validation error."""
        PasswordResetCode.objects.create(
            user=self.user,
            code="123456",
            expires_at=timezone.now() + timedelta(minutes=15),
        )

        payload = {
            "email": "resetuser@example.com",
            "otp": "123456",
            "password": "Password123!",
            "password_confirm": "DifferentPassword123!",
        }
        response = self.client.post(self.confirm_url, data=payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password_confirm", response.data)
