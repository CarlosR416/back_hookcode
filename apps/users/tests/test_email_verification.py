"""
Sub-domain tests: 6-digit OTP Email Verification & Resend Lifecycle.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.users.models import EmailVerificationCode

User = get_user_model()


class EmailVerificationOTPTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.register_url = reverse("auth:users-register")
        cls.verify_otp_url = reverse("auth:users-verify-otp")
        cls.resend_otp_url = reverse("auth:users-resend-otp")

    def setUp(self):
        mail.outbox.clear()

    def test_registration_creates_inactive_user_and_sends_otp_email(self):
        """Standard registration must set is_active=False and dispatch an OTP email."""
        payload = {
            "email": "otptest@example.com",
            "first_name": "Alice",
            "last_name": "Smith",
            "password": "Password123!",
            "password_confirm": "Password123!",
        }
        response = self.client.post(self.register_url, data=payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        user = User.objects.get(email="otptest@example.com")
        self.assertFalse(user.is_active)

        # Ensure OTP record created
        otp_records = EmailVerificationCode.objects.filter(user=user, is_used=False)
        self.assertEqual(otp_records.count(), 1)
        otp = otp_records.first()
        self.assertEqual(len(otp.code), 6)
        self.assertTrue(otp.code.isdigit())

        # Ensure email sent via outbox
        self.assertEqual(len(mail.outbox), 1)
        sent_email = mail.outbox[0]
        self.assertIn("otptest@example.com", sent_email.to)
        self.assertIn(otp.code, sent_email.subject)
        self.assertIn(otp.code, sent_email.body)

    def test_verify_otp_success_activates_user_and_issues_jwt(self):
        """Submitting the correct OTP activates the user and returns access/refresh JWTs."""
        user = User.objects.create_user(
            username="verifyuser@example.com",
            email="verifyuser@example.com",
            password="Password123!",
            is_active=False,
        )
        otp = EmailVerificationCode.objects.create(
            user=user,
            code="654321",
            expires_at=timezone.now() + timedelta(minutes=15),
        )

        payload = {
            "email": "verifyuser@example.com",
            "otp": "654321",
        }
        response = self.client.post(self.verify_otp_url, data=payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertTrue(user.is_email_verified)

        otp.refresh_from_db()
        self.assertTrue(otp.is_used)

        data = response.data.get("data", {})
        self.assertIn("access", data)
        self.assertIn("refresh", data)
        self.assertEqual(data["user"]["email"], "verifyuser@example.com")

    def test_verify_otp_invalid_code_increments_attempts(self):
        """Submitting an incorrect OTP code increments failed attempts and returns 400."""
        user = User.objects.create_user(
            username="invalidcode@example.com",
            email="invalidcode@example.com",
            password="Password123!",
            is_active=False,
        )
        otp = EmailVerificationCode.objects.create(
            user=user,
            code="111222",
            expires_at=timezone.now() + timedelta(minutes=15),
        )

        payload = {
            "email": "invalidcode@example.com",
            "otp": "999888",
        }
        response = self.client.post(self.verify_otp_url, data=payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data.get("error", {}).get("code"), "invalid_otp")

        otp.refresh_from_db()
        self.assertEqual(otp.attempts, 1)

        user.refresh_from_db()
        self.assertFalse(user.is_active)

    def test_verify_otp_max_attempts_locks_code(self):
        """An OTP code with 5 failed attempts is locked against further verification."""
        user = User.objects.create_user(
            username="lockeduser@example.com",
            email="lockeduser@example.com",
            password="Password123!",
            is_active=False,
        )
        EmailVerificationCode.objects.create(
            user=user,
            code="123456",
            expires_at=timezone.now() + timedelta(minutes=15),
            attempts=5,
        )

        payload = {
            "email": "lockeduser@example.com",
            "otp": "123456",
        }
        response = self.client.post(self.verify_otp_url, data=payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data.get("error", {}).get("code"), "too_many_attempts")

    def test_verify_otp_expired_code_rejected(self):
        """Expired OTP code returns 400 expired_otp."""
        user = User.objects.create_user(
            username="expireduser@example.com",
            email="expireduser@example.com",
            password="Password123!",
            is_active=False,
        )
        EmailVerificationCode.objects.create(
            user=user,
            code="123456",
            expires_at=timezone.now() - timedelta(minutes=1),
        )

        payload = {
            "email": "expireduser@example.com",
            "otp": "123456",
        }
        response = self.client.post(self.verify_otp_url, data=payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data.get("error", {}).get("code"), "expired_otp")

    def test_verify_otp_nonexistent_user(self):
        """Attempting to verify an email not registered returns 404."""
        payload = {
            "email": "ghost@example.com",
            "otp": "123456",
        }
        response = self.client.post(self.verify_otp_url, data=payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data.get("error", {}).get("code"), "user_not_found")

    def test_verify_otp_already_verified_user(self):
        """Attempting to verify an already verified user returns 400 already_verified."""
        user = User.objects.create_user(
            username="alreadyactive@example.com",
            email="alreadyactive@example.com",
            password="Password123!",
            is_active=True,
            is_email_verified=True,
        )
        payload = {
            "email": "alreadyactive@example.com",
            "otp": "123456",
        }
        response = self.client.post(self.verify_otp_url, data=payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data.get("error", {}).get("code"), "already_verified")

    def test_resend_otp_already_verified_user(self):
        """Requesting resend for an already verified user returns 400 already_verified."""
        User.objects.create_user(
            username="verifiedresend@example.com",
            email="verifiedresend@example.com",
            password="Password123!",
            is_active=True,
            is_email_verified=True,
        )
        payload = {"email": "verifiedresend@example.com"}
        response = self.client.post(self.resend_otp_url, data=payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data.get("error", {}).get("code"), "already_verified")

    def test_resend_otp_cooldown_enforced(self):
        """Requesting resend within the 60s cooldown window returns 429."""
        user = User.objects.create_user(
            username="cooldown@example.com",
            email="cooldown@example.com",
            password="Password123!",
            is_active=False,
        )
        # Existing OTP created 10 seconds ago
        EmailVerificationCode.objects.create(
            user=user,
            code="111111",
            expires_at=timezone.now() + timedelta(minutes=15),
        )

        payload = {"email": "cooldown@example.com"}
        response = self.client.post(self.resend_otp_url, data=payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(response.data.get("error", {}).get("code"), "resend_cooldown")

    def test_resend_otp_success_after_cooldown(self):
        """Requesting resend after cooldown creates a new OTP and invalidates the previous."""
        user = User.objects.create_user(
            username="resendok@example.com",
            email="resendok@example.com",
            password="Password123!",
            is_active=False,
        )
        # Create old OTP and mock created_at to 70 seconds in the past
        old_otp = EmailVerificationCode.objects.create(
            user=user,
            code="000000",
            expires_at=timezone.now() + timedelta(minutes=15),
        )
        EmailVerificationCode.objects.filter(pk=old_otp.pk).update(
            created_at=timezone.now() - timedelta(seconds=70)
        )

        payload = {"email": "resendok@example.com"}
        response = self.client.post(self.resend_otp_url, data=payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Old OTP must be marked used/invalidated
        old_otp.refresh_from_db()
        self.assertTrue(old_otp.is_used)

        # New OTP should exist
        new_otp = (
            EmailVerificationCode.objects.filter(user=user, is_used=False)
            .order_by("-created_at")
            .first()
        )
        self.assertIsNotNone(new_otp)
        self.assertNotEqual(new_otp.code, "000000")
        self.assertEqual(len(mail.outbox), 1)

    def test_resend_otp_nonexistent_email_generic_success(self):
        """Requesting resend for a non-existent email returns generic success to avoid enumeration."""
        payload = {"email": "nobody@example.com"}
        response = self.client.post(self.resend_otp_url, data=payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 0)
