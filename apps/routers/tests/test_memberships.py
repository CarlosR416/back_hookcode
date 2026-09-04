"""
Sub-domain tests: Router Memberships & User Associations.
"""

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.routers.models import Router, UserRouter

User = get_user_model()


class RouterMembershipsTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser(
            username="adminuser",
            email="admin@example.com",
            password="adminpassword123",
        )
        cls.member = User.objects.create_user(
            username="memberuser",
            email="member@example.com",
            password="memberpassword123",
        )
        cls.router = Router.objects.create(
            name="Main Branch Router",
            host="192.168.10.1",
            port=443,
            api_username="admin",
            api_password="password",
        )
        cls.memberships_url = reverse("routers:router-memberships-list")

    def setUp(self):
        self.client.force_authenticate(user=self.admin)

    def test_create_membership_success(self):
        """Admin can assign a router role to a user."""
        payload = {
            "user": self.member.pk,
            "router": self.router.pk,
            "role": UserRouter.RouterRole.VIEWER,
        }
        response = self.client.post(self.memberships_url, data=payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("data", response.data)
        self.assertEqual(response.data["data"]["user_email"], self.member.email)
        self.assertTrue(
            UserRouter.objects.filter(
                user=self.member, router=self.router, role=UserRouter.RouterRole.VIEWER
            ).exists()
        )

    def test_create_membership_default_to_requesting_user(self):
        """When user is not in payload, defaults to request.user (CurrentUserDefault)."""
        payload = {
            "router": self.router.pk,
            "role": UserRouter.RouterRole.OWNER,
        }
        response = self.client.post(self.memberships_url, data=payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("data", response.data)
        self.assertEqual(response.data["data"]["user_email"], self.admin.email)
        self.assertTrue(
            UserRouter.objects.filter(
                user=self.admin, router=self.router, role=UserRouter.RouterRole.OWNER
            ).exists()
        )

    def test_duplicate_membership_rejection(self):
        """Cannot assign multiple roles to the same user on the same router."""
        UserRouter.objects.create(
            user=self.member,
            router=self.router,
            role=UserRouter.RouterRole.OWNER,
        )
        payload = {
            "user": self.member.pk,
            "router": self.router.pk,
            "role": UserRouter.RouterRole.VIEWER,
        }
        response = self.client.post(self.memberships_url, data=payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
