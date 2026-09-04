"""
Sub-domain tests: Google Authentication & Firebase Integration.
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.test import APITestCase

User = get_user_model()


class GoogleAuthenticationTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.google_auth_url = reverse("auth:users-google")
        cls.existing_user = User.objects.create_user(
            username="existinguser",
            email="existing@example.com",
            password="somepassword",
        )

    @patch("apps.users.firebase.verify_google_token")
    def test_google_login_new_user_provisioning(self, mock_verify):
        """Valid Firebase token for a new email automatically provisions a user and returns JWT tokens."""
        mock_verify.return_value = {
            "uid": "firebase-uid-999",
            "email": "newgoogleuser@example.com",
        }
        response = self.client.post(
            self.google_auth_url,
            data={"firebase_token": "valid-firebase-jwt"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["data"]["is_new_user"])
        self.assertIn("access", response.data["data"])
        self.assertIn("refresh", response.data["data"])
        self.assertTrue(User.objects.filter(email="newgoogleuser@example.com").exists())

    @patch("apps.users.firebase.verify_google_token")
    def test_google_login_existing_user(self, mock_verify):
        """Valid Firebase token for an existing email logs in the user."""
        mock_verify.return_value = {
            "uid": "firebase-uid-existing",
            "email": "existing@example.com",
        }
        response = self.client.post(
            self.google_auth_url,
            data={"firebase_token": "valid-firebase-jwt"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["data"]["is_new_user"])
        self.assertEqual(response.data["data"]["user"]["email"], "existing@example.com")

    @patch("apps.users.firebase.verify_google_token")
    def test_google_login_missing_email_in_token(self, mock_verify):
        """Returns 400 bad request if decoded token does not include email."""
        mock_verify.return_value = {"uid": "uid-without-email"}
        response = self.client.post(
            self.google_auth_url,
            data={"firebase_token": "token-missing-email"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data.get("error", {}).get("code"), "missing_email")

    @patch("apps.users.firebase.verify_google_token")
    def test_google_login_invalid_token(self, mock_verify):
        """Returns 401 when verify_google_token raises AuthenticationFailed."""
        mock_verify.side_effect = AuthenticationFailed("Invalid Firebase ID token.")
        response = self.client.post(
            self.google_auth_url,
            data={"firebase_token": "invalid-garbage-token"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
