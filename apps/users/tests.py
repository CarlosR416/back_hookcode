"""
Tests for the users application, including i18n and authentication flows.
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()


class UserAuthenticationI18nTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="testuser@example.com",
            password="oldpassword123",
        )
        self.register_url = reverse("auth:users-register")
        self.change_password_url = reverse("auth:users-change-password")

    def test_register_password_mismatch_in_spanish(self):
        """When Accept-Language is 'es', validation messages should be in Spanish."""
        payload = {
            "email": "newuser@example.com",
            "username": "newuser",
            "password": "Password123!",
            "password_confirm": "MismatchPassword123!",
        }
        response = self.client.post(
            self.register_url,
            data=payload,
            format="json",
            HTTP_ACCEPT_LANGUAGE="es",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.headers.get("Content-Language"), "es")
        self.assertIn("error", response.data)
        self.assertIn("password_confirm", response.data["error"])
        self.assertIn("Las contraseñas no coinciden.", response.data["error"]["password_confirm"])

    def test_register_password_mismatch_in_english(self):
        """When Accept-Language is 'en', validation messages should be in English."""
        payload = {
            "email": "newuser@example.com",
            "username": "newuser",
            "password": "Password123!",
            "password_confirm": "MismatchPassword123!",
        }
        response = self.client.post(
            self.register_url,
            data=payload,
            format="json",
            HTTP_ACCEPT_LANGUAGE="en",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.headers.get("Content-Language"), "en")
        self.assertIn("error", response.data)
        self.assertIn("password_confirm", response.data["error"])
        self.assertIn("Passwords do not match.", response.data["error"]["password_confirm"])

    def test_change_password_wrong_old_password_in_spanish(self):
        """Custom endpoint error messages should be localized to Spanish."""
        self.client.force_authenticate(user=self.user)
        payload = {
            "old_password": "WrongPassword123!",
            "new_password": "NewSecretPassword123!",
            "new_password_confirm": "NewSecretPassword123!",
        }
        response = self.client.post(
            self.change_password_url,
            data=payload,
            format="json",
            HTTP_ACCEPT_LANGUAGE="es",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.headers.get("Content-Language"), "es")
        self.assertEqual(
            response.data.get("error", {}).get("detail"),
            "La contraseña anterior es incorrecta.",
        )

    def test_change_password_success_in_spanish(self):
        """Custom endpoint success messages should be localized to Spanish."""
        self.client.force_authenticate(user=self.user)
        payload = {
            "old_password": "oldpassword123",
            "new_password": "NewSecretPassword123!",
            "new_password_confirm": "NewSecretPassword123!",
        }
        response = self.client.post(
            self.change_password_url,
            data=payload,
            format="json",
            HTTP_ACCEPT_LANGUAGE="es",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.headers.get("Content-Language"), "es")
        self.assertEqual(
            response.data.get("data", {}).get("detail"),
            "Contraseña actualizada exitosamente.",
        )

    def test_change_password_success_in_english(self):
        """Custom endpoint success messages should be in English by default or when requested."""
        self.client.force_authenticate(user=self.user)
        payload = {
            "old_password": "oldpassword123",
            "new_password": "NewSecretPassword123!",
            "new_password_confirm": "NewSecretPassword123!",
        }
        response = self.client.post(
            self.change_password_url,
            data=payload,
            format="json",
            HTTP_ACCEPT_LANGUAGE="en",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.headers.get("Content-Language"), "en")
        self.assertEqual(
            response.data.get("data", {}).get("detail"),
            "Password updated successfully.",
        )

    def test_drf_built_in_validation_translated_to_spanish(self):
        """DRF built-in validation messages (e.g. required field) should also be localized."""
        payload = {
            "username": "incompleteuser",
        }
        response = self.client.post(
            self.register_url,
            data=payload,
            format="json",
            HTTP_ACCEPT_LANGUAGE="es",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.headers.get("Content-Language"), "es")
        self.assertIn("error", response.data)
        self.assertIn("email", response.data["error"])
        self.assertIn("Este campo es requerido.", response.data["error"]["email"])

    @patch("apps.users.firebase.verify_google_token")
    def test_google_login_missing_email_in_spanish(self, mock_verify):
        """Google login missing email message should be in Spanish."""
        mock_verify.return_value = {"uid": "google-user-123"}
        url = reverse("auth:users-google")
        response = self.client.post(
            url,
            data={"firebase_token": "valid-token-no-email"},
            format="json",
            HTTP_ACCEPT_LANGUAGE="es",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.headers.get("Content-Language"), "es")
        self.assertEqual(
            response.data.get("error", {}).get("detail"),
            "El correo electrónico no está presente en el token de Google.",
        )

    @patch("apps.users.firebase.verify_google_token")
    def test_google_login_missing_email_in_english(self, mock_verify):
        """Google login missing email message should be in English."""
        mock_verify.return_value = {"uid": "google-user-123"}
        url = reverse("auth:users-google")
        response = self.client.post(
            url,
            data={"firebase_token": "valid-token-no-email"},
            format="json",
            HTTP_ACCEPT_LANGUAGE="en",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.headers.get("Content-Language"), "en")
        self.assertEqual(
            response.data.get("error", {}).get("detail"),
            "Email is missing from the Google token.",
        )
