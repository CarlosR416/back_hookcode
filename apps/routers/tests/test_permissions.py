"""
Sub-domain tests: Router Permissions & Role-Based Access Control.
"""

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.routers.models import Router, UserRouter

User = get_user_model()


class RouterPermissionsTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(
            username="routerowner",
            email="owner@example.com",
            password="password123",
        )
        cls.viewer = User.objects.create_user(
            username="routerviewer",
            email="viewer@example.com",
            password="password123",
        )
        cls.unrelated = User.objects.create_user(
            username="unrelateduser",
            email="unrelated@example.com",
            password="password123",
        )
        cls.router = Router.objects.create(
            name="Protected Router",
            host="192.168.1.1",
            port=443,
            api_username="admin",
            api_password="password",
        )
        UserRouter.objects.create(
            user=cls.owner,
            router=cls.router,
            role=UserRouter.RouterRole.OWNER,
        )
        UserRouter.objects.create(
            user=cls.viewer,
            router=cls.router,
            role=UserRouter.RouterRole.VIEWER,
        )
        cls.router_detail_url = reverse("routers:routers-detail", kwargs={"pk": cls.router.pk})

    def setUp(self):
        self.router.refresh_from_db()

    def test_owner_can_update_router(self):
        """Router owner can perform write operations on the router."""
        self.client.force_authenticate(user=self.owner)
        response = self.client.patch(
            self.router_detail_url,
            data={"name": "Owner Updated Router"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("data", response.data)
        self.assertEqual(response.data["data"]["name"], "Owner Updated Router")
        self.router.refresh_from_db()
        self.assertEqual(self.router.name, "Owner Updated Router")

    def test_viewer_cannot_update_router(self):
        """Viewer role has read-only access and cannot perform write operations."""
        self.client.force_authenticate(user=self.viewer)
        response = self.client.patch(
            self.router_detail_url,
            data={"name": "Viewer Hack"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unrelated_user_cannot_access_router(self):
        """Users with no assigned role cannot access the router."""
        self.client.force_authenticate(user=self.unrelated)
        response = self.client.get(self.router_detail_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_router_envelope(self):
        """Router retrieve endpoint wraps representation in a data envelope."""
        self.client.force_authenticate(user=self.owner)
        response = self.client.get(self.router_detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("data", response.data)
        self.assertEqual(response.data["data"]["id"], self.router.pk)

    def test_create_router_auto_owner_and_envelope(self):
        """Creating a router returns data envelope with id/name/description and assigns user as OWNER."""
        self.client.force_authenticate(user=self.unrelated)
        payload = {
            "name": "New Router by Unrelated",
            "description": "Branch office router",
        }
        create_url = reverse("routers:routers-list")
        response = self.client.post(create_url, data=payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("data", response.data)
        data = response.data["data"]
        self.assertEqual(data["name"], "New Router by Unrelated")
        self.assertEqual(data["description"], "Branch office router")
        # Ensure only id, name, description are returned in response data
        self.assertEqual(set(data.keys()), {"id", "name", "description"})

        new_router_id = data["id"]
        created_router = Router.objects.get(pk=new_router_id)
        self.assertEqual(created_router.host, "0.0.0.0")
        self.assertEqual(created_router.port, 10001)
        self.assertEqual(created_router.api_username, "U10001")
        self.assertTrue(len(created_router.api_password) >= 20)
        self.assertTrue(created_router.is_active)
        self.assertIsNone(created_router.routeros_version)

        self.assertTrue(
            UserRouter.objects.filter(
                user=self.unrelated,
                router_id=new_router_id,
                role=UserRouter.RouterRole.OWNER,
            ).exists()
        )
