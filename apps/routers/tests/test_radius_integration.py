"""
Sub-domain tests: Router FreeRADIUS synchronization on registration and deletion.
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connections
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.radius.models import RadCheck, RadReply, RadUserGroup
from apps.routers.models import Router, UserRouter
from apps.routers.services import (
    delete_router_radius_user,
    provision_router_defaults,
    sync_router_radius_user,
)

User = get_user_model()


class RouterRadiusIntegrationTests(APITestCase):
    databases = {"default", "radius"}

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._radius_models = [RadCheck, RadReply, RadUserGroup]
        with connections["radius"].schema_editor() as editor:
            for model in cls._radius_models:
                editor.create_model(model)

    @classmethod
    def tearDownClass(cls):
        with connections["radius"].schema_editor() as editor:
            for model in reversed(cls._radius_models):
                editor.delete_model(model)
        super().tearDownClass()

    def setUp(self):
        self.user = User.objects.create_user(
            username="radius_router_owner",
            email="router_owner@example.com",
            password="securepassword123",
        )
        self.client.force_authenticate(user=self.user)

    def test_sync_router_radius_user_creates_radcheck_record(self):
        """sync_router_radius_user correctly creates a Cleartext-Password with an independent random password."""
        defaults = provision_router_defaults()
        router = Router.objects.create(name="Lab Router", **defaults)

        result = sync_router_radius_user(router)
        self.assertIsNotNone(result)
        self.assertEqual(result["username"], router.api_username)
        self.assertIn("password", result)
        self.assertNotEqual(result["password"], router.api_password)

        check_entry = RadCheck.objects.get(
            username=router.api_username, attribute="Cleartext-Password"
        )
        self.assertEqual(check_entry.value, result["password"])
        self.assertNotEqual(check_entry.value, router.api_password)
        self.assertEqual(check_entry.op, ":=")
        self.assertEqual(check_entry.client_id, router.port - 10000)

    def test_sync_router_radius_user_custom_password(self):
        """sync_router_radius_user respects an explicitly provided password."""
        defaults = provision_router_defaults()
        router = Router.objects.create(name="Custom Pass Router", **defaults)

        result = sync_router_radius_user(router, password="custom_radius_secret_999")
        self.assertEqual(result["password"], "custom_radius_secret_999")

        check_entry = RadCheck.objects.get(
            username=router.api_username, attribute="Cleartext-Password"
        )
        self.assertEqual(check_entry.value, "custom_radius_secret_999")
        self.assertEqual(check_entry.client_id, router.port - 10000)

    def test_sync_router_radius_user_raises_error_if_port_minus_10000_is_negative(self):
        """sync_router_radius_user raises ValueError if router.port - 10000 < 0."""
        router = Router.objects.create(
            name="Low Port Router",
            port=8080,
            api_username="lowport",
            api_password="password123",
        )
        with self.assertRaises(ValueError):
            sync_router_radius_user(router)

    def test_delete_router_radius_user_removes_radcheck_record(self):
        """delete_router_radius_user cleanly removes the user from RadCheck."""
        defaults = provision_router_defaults()
        router = Router.objects.create(name="Deletable Router", **defaults)
        sync_router_radius_user(router)

        self.assertTrue(
            RadCheck.objects.filter(username=router.api_username).exists()
        )

        deleted = delete_router_radius_user(router)
        self.assertTrue(deleted)
        self.assertFalse(
            RadCheck.objects.filter(username=router.api_username).exists()
        )

    def test_api_register_router_creates_radius_user(self):
        """POST /api/routers/ provisions a new router and creates its RADIUS user credentials with an independent password."""
        create_url = reverse("routers:routers-list")
        payload = {
            "name": "Branch Office Router",
            "description": "Auto-registered with RADIUS sync",
        }

        response = self.client.post(create_url, data=payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("data", response.data)

        router_id = response.data["data"]["id"]
        router = Router.objects.get(pk=router_id)

        # Verify RADIUS entry was created with a random password different from api_password
        rad_entry = RadCheck.objects.get(username=router.api_username)
        self.assertEqual(rad_entry.attribute, "Cleartext-Password")
        self.assertNotEqual(rad_entry.value, router.api_password)
        self.assertTrue(len(rad_entry.value) >= 20)
        self.assertEqual(rad_entry.client_id, router.port - 10000)

    def test_api_delete_router_removes_radius_user(self):
        """DELETE /api/routers/{id}/ performs logical deletion (is_active=False) and removes associated RADIUS user credentials."""
        create_url = reverse("routers:routers-list")
        response = self.client.post(
            create_url,
            data={"name": "Temporary Router", "description": "Will be deleted"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        router_id = response.data["data"]["id"]
        router = Router.objects.get(pk=router_id)
        api_username = router.api_username

        # Confirm RADIUS user exists
        self.assertTrue(RadCheck.objects.filter(username=api_username).exists())

        # Delete router via API
        detail_url = reverse("routers:routers-detail", kwargs={"pk": router_id})
        delete_response = self.client.delete(detail_url)
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)

        # Confirm Router is logically deleted (record preserved, is_active=False)
        router.refresh_from_db()
        self.assertFalse(router.is_active)
        self.assertTrue(Router.objects.filter(pk=router_id).exists())

        # Confirm RADIUS user is purged
        self.assertFalse(RadCheck.objects.filter(username=api_username).exists())

    @patch("apps.routers.views.sync_router_radius_user")
    def test_router_creation_rolls_back_if_radius_sync_fails(self, mock_sync):
        """If FreeRADIUS user provisioning fails, the router and owner membership are rolled back."""
        mock_sync.side_effect = RuntimeError("FreeRADIUS service is unreachable")

        create_url = reverse("routers:routers-list")
        payload = {
            "name": "Failed Atomic Router",
            "description": "Should not exist in database",
        }

        response = self.client.post(create_url, data=payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Verify Router was completely rolled back from the default database
        self.assertFalse(
            Router.objects.filter(name="Failed Atomic Router").exists()
        )
        # Verify no orphan UserRouter associations remain
        self.assertFalse(
            UserRouter.objects.filter(router__name="Failed Atomic Router").exists()
        )

