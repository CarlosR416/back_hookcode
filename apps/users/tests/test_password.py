"""
Sub-domain tests: Password Management.
"""

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()


class PasswordManagementTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="pwduser",
            email="pwduser@example.com",
            password="InitialPassword123!",
        )
        cls.change_password_url = reverse("auth:users-change-password")

    def setUp(self):
        self.user.refresh_from_db()
        self.client.force_authenticate(user=self.user)

    def test_change_password_success(self):
        """Authenticated user can update their password with valid credentials."""
        payload = {
            "old_password": "InitialPassword123!",
            "new_password": "UpdatedPassword123!",
            "new_password_confirm": "UpdatedPassword123!",
        }
        response = self.client.post(self.change_password_url, data=payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("UpdatedPassword123!"))

    def test_change_password_wrong_old_password(self):
        """Fails when the provided old password does not match."""
        payload = {
            "old_password": "WrongInitialPassword!",
            "new_password": "UpdatedPassword123!",
            "new_password_confirm": "UpdatedPassword123!",
        }
        response = self.client.post(self.change_password_url, data=payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data.get("error", {}).get("code"), "wrong_password")

    def test_change_password_mismatched_confirmation(self):
        """Fails when new password and confirmation do not match."""
        payload = {
            "old_password": "InitialPassword123!",
            "new_password": "UpdatedPassword123!",
            "new_password_confirm": "MismatchPassword123!",
        }
        response = self.client.post(self.change_password_url, data=payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("new_password_confirm", response.data.get("error", {}))
