"""
Sub-domain tests: Router Plan Limits & Free Mode Enforcement.
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.routers.models import Router, UserRouter

User = get_user_model()


class RouterPlanLimitsTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.routers_url = reverse("routers:routers-list")
        cls.me_url = reverse("auth:users-me")

    def setUp(self):
        self.user = User.objects.create_user(
            username="freeuser@example.com",
            email="freeuser@example.com",
            password="Password123!",
            first_name="Free",
            last_name="User",
            is_active=True,
            is_email_verified=True,
        )

    def test_new_user_default_plan_is_free(self):
        """New users must have plan='free', max_routers=3, and can_add_router=True by default."""
        self.assertEqual(self.user.plan, User.Plan.FREE)
        self.assertEqual(self.user.max_routers, 3)
        self.assertEqual(self.user.owned_routers_count, 0)
        self.assertTrue(self.user.can_add_router)

    @patch("apps.routers.views.sync_router_radius_user")
    def test_free_user_can_create_up_to_three_routers(self, mock_sync_radius):
        """A user on the free plan can successfully create up to 3 active routers."""
        self.client.force_authenticate(user=self.user)

        for i in range(1, 4):
            response = self.client.post(
                self.routers_url,
                data={"name": f"Free Router {i}", "description": f"Router number {i}"},
                format="json",
            )
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            self.assertEqual(response.data["data"]["name"], f"Free Router {i}")

        self.assertEqual(self.user.owned_routers_count, 3)
        self.assertFalse(self.user.can_add_router)

    @patch("apps.routers.views.sync_router_radius_user")
    def test_free_user_fourth_router_is_rejected_with_limit_error(self, mock_sync_radius):
        """Creating a 4th router on the free plan returns 400 Bad Request with code router_limit_reached."""
        self.client.force_authenticate(user=self.user)

        # Create 3 routers
        for i in range(1, 4):
            resp = self.client.post(
                self.routers_url,
                data={"name": f"Router {i}"},
                format="json",
            )
            self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

        # 4th router attempt
        fourth_resp = self.client.post(
            self.routers_url,
            data={"name": "Router 4 (Should Fail)"},
            format="json",
        )
        self.assertEqual(fourth_resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", fourth_resp.data)
        self.assertEqual(fourth_resp.data["error"]["code"], "router_limit_reached")
        self.assertIn("3", fourth_resp.data["error"]["detail"])

        # Count in database remains 3
        self.assertEqual(self.user.owned_routers_count, 3)

    @patch("apps.routers.views.sync_router_radius_user")
    @patch("apps.routers.models.delete_router_radius_user")
    def test_soft_deleting_router_frees_slot(self, mock_delete_radius, mock_sync_radius):
        """Soft-deleting an active router decrements the owned count and frees a slot for a new router."""
        self.client.force_authenticate(user=self.user)

        router_ids = []
        for i in range(1, 4):
            resp = self.client.post(self.routers_url, data={"name": f"Router {i}"}, format="json")
            router_ids.append(resp.data["data"]["id"])

        self.assertFalse(self.user.can_add_router)

        # Delete the first router
        delete_url = reverse("routers:routers-detail", kwargs={"pk": router_ids[0]})
        del_resp = self.client.delete(delete_url)
        self.assertEqual(del_resp.status_code, status.HTTP_204_NO_CONTENT)

        # Verify active owned count is now 2
        self.assertEqual(self.user.owned_routers_count, 2)
        self.assertTrue(self.user.can_add_router)

        # Now creating a new 3rd router succeeds
        new_resp = self.client.post(self.routers_url, data={"name": "Replacement Router"}, format="json")
        self.assertEqual(new_resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.user.owned_routers_count, 3)
        self.assertFalse(self.user.can_add_router)

    @patch("apps.routers.views.sync_router_radius_user")
    def test_pro_user_not_restricted_by_limit(self, mock_sync_radius):
        """Users on pro plan have unlimited routers and can create more than 3."""
        self.user.plan = User.Plan.PRO
        self.user.save(update_fields=["plan"])

        self.assertIsNone(self.user.max_routers)
        self.assertTrue(self.user.can_add_router)

        self.client.force_authenticate(user=self.user)
        for i in range(1, 5):
            resp = self.client.post(self.routers_url, data={"name": f"Pro Router {i}"}, format="json")
            self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

        self.assertEqual(self.user.owned_routers_count, 4)
        self.assertTrue(self.user.can_add_router)

    @patch("apps.routers.views.sync_router_radius_user")
    def test_staff_user_not_restricted_by_limit(self, mock_sync_radius):
        """Staff users are exempt from the 3-router limit even with plan='free'."""
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])

        self.assertIsNone(self.user.max_routers)
        self.assertTrue(self.user.can_add_router)

        self.client.force_authenticate(user=self.user)
        for i in range(1, 5):
            resp = self.client.post(self.routers_url, data={"name": f"Staff Router {i}"}, format="json")
            self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

        self.assertEqual(self.user.owned_routers_count, 4)

    def test_viewer_role_does_not_consume_slot(self):
        """Being assigned as a VIEWER to another user's router does not increment owned_routers_count."""
        other_user = User.objects.create_user(
            username="other@example.com",
            email="other@example.com",
            password="Password123!",
        )
        other_router = Router.objects.create(
            name="Other's Router",
            host="10.0.0.1",
            port=12345,
            api_username="U12345",
            api_password="pwd",
        )
        UserRouter.objects.create(
            user=other_user,
            router=other_router,
            role=UserRouter.RouterRole.OWNER,
        )
        # Assign free user as VIEWER
        UserRouter.objects.create(
            user=self.user,
            router=other_router,
            role=UserRouter.RouterRole.VIEWER,
        )

        self.assertEqual(self.user.owned_routers_count, 0)
        self.assertTrue(self.user.can_add_router)

    def test_user_profile_me_exposes_plan_and_limits(self):
        """The /api/auth/me/ endpoint returns plan, max_routers, owned_routers_count, and can_add_router."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.me_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data["data"]
        self.assertEqual(data["plan"], "free")
        self.assertEqual(data["max_routers"], 3)
        self.assertEqual(data["owned_routers_count"], 0)
        self.assertTrue(data["can_add_router"])

    def test_user_cannot_escalate_plan_via_me_endpoint(self):
        """Users cannot change their own plan via PATCH /api/auth/me/ (plan is read-only)."""
        self.client.force_authenticate(user=self.user)
        response = self.client.patch(
            self.me_url,
            data={"plan": "pro"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.plan, "free")
