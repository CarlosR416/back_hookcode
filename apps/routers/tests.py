"""
Tests for the routers application, including membership validation and role permissions.
"""

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Router, UserRouter

User = get_user_model()


class RouterDomainTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="adminuser",
            email="admin@example.com",
            password="adminpassword123",
        )
        self.regular_user = User.objects.create_user(
            username="regularuser",
            email="regular@example.com",
            password="userpassword123",
        )
        self.router = Router.objects.create(
            name="Test Router",
            host="192.168.88.1",
            port=443,
            api_username="admin",
            api_password="password",
        )
        self.memberships_url = reverse("routers:router-memberships-list")
        self.router_detail_url = reverse("routers:routers-detail", kwargs={"pk": self.router.pk})

    def test_duplicate_membership_validation_in_spanish(self):
        """Serializer unique validation message should be in Spanish."""
        self.client.force_authenticate(user=self.admin)
        UserRouter.objects.create(
            user=self.admin,
            router=self.router,
            role=UserRouter.RouterRole.OWNER,
        )
        payload = {
            "router": self.router.pk,
            "role": UserRouter.RouterRole.VIEWER,
        }
        response = self.client.post(
            self.memberships_url,
            data=payload,
            format="json",
            HTTP_ACCEPT_LANGUAGE="es",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.headers.get("Content-Language"), "es")
        self.assertIn(
            "Este usuario ya tiene un rol asignado para el router seleccionado.",
            str(response.data["error"]),
        )

    def test_duplicate_membership_validation_in_english(self):
        """Serializer unique validation message should be in English."""
        self.client.force_authenticate(user=self.admin)
        UserRouter.objects.create(
            user=self.admin,
            router=self.router,
            role=UserRouter.RouterRole.OWNER,
        )
        payload = {
            "router": self.router.pk,
            "role": UserRouter.RouterRole.VIEWER,
        }
        response = self.client.post(
            self.memberships_url,
            data=payload,
            format="json",
            HTTP_ACCEPT_LANGUAGE="en",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.headers.get("Content-Language"), "en")
        self.assertIn(
            "This user already has a role assigned for the selected router.",
            str(response.data["error"]),
        )

    def test_router_owner_permission_denied_in_spanish(self):
        """Permission denied error should be translated to Spanish."""
        # regular_user is a viewer, not owner
        UserRouter.objects.create(
            user=self.regular_user,
            router=self.router,
            role=UserRouter.RouterRole.VIEWER,
        )
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.patch(
            self.router_detail_url,
            data={"name": "New Name"},
            format="json",
            HTTP_ACCEPT_LANGUAGE="es",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.headers.get("Content-Language"), "es")
        self.assertEqual(
            response.data.get("error", {}).get("detail"),
            "Debes ser el propietario de este router para realizar esta acción.",
        )

    def test_router_owner_permission_denied_in_english(self):
        """Permission denied error should be in English."""
        UserRouter.objects.create(
            user=self.regular_user,
            router=self.router,
            role=UserRouter.RouterRole.VIEWER,
        )
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.patch(
            self.router_detail_url,
            data={"name": "New Name"},
            format="json",
            HTTP_ACCEPT_LANGUAGE="en",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.headers.get("Content-Language"), "en")
        self.assertEqual(
            response.data.get("error", {}).get("detail"),
            "You must be the owner of this router to perform this action.",
        )
