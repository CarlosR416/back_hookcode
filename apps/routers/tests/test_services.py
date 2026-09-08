"""
Unit tests for Router provisioning services:
- Sequential identifier generation starting at U10001 / port 10001
- Password uniqueness and collision avoidance
- Range exhaustion handling
- Complete provisioning defaults
"""

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.routers.models import Router
from apps.routers.services import (
    generate_unique_router_password,
    get_next_router_identifier,
    provision_router_defaults,
)


class RouterProvisioningServicesTests(TestCase):
    def test_first_router_identifier_is_10001(self):
        """When no routers exist in the 10001-15000 range, next identifier is 10001."""
        self.assertEqual(get_next_router_identifier(), 10001)

    def test_sequential_identifier_allocation(self):
        """Identifiers advance sequentially (10001 -> 10002 -> 10003)."""
        defaults1 = provision_router_defaults()
        Router.objects.create(name="Router 1", **defaults1)
        self.assertEqual(defaults1["port"], 10001)
        self.assertEqual(defaults1["api_username"], "U10001")

        defaults2 = provision_router_defaults()
        Router.objects.create(name="Router 2", **defaults2)
        self.assertEqual(defaults2["port"], 10002)
        self.assertEqual(defaults2["api_username"], "U10002")

        defaults3 = provision_router_defaults()
        self.assertEqual(defaults3["port"], 10003)
        self.assertEqual(defaults3["api_username"], "U10003")

    def test_reclaims_lowest_available_gap(self):
        """If 10001 and 10003 are allocated, identifier 10002 is selected."""
        Router.objects.create(
            name="Router 10001",
            host="0.0.0.0",
            port=10001,
            api_username="U10001",
            api_password="password_alpha_1",
        )
        Router.objects.create(
            name="Router 10003",
            host="0.0.0.0",
            port=10003,
            api_username="U10003",
            api_password="password_alpha_2",
        )
        next_id = get_next_router_identifier()
        self.assertEqual(next_id, 10002)

    def test_range_exhaustion_raises_validation_error(self):
        """Raises ValidationError when the range min_val to max_val is completely full."""
        # Test on a small sub-range [10001, 10002]
        Router.objects.create(
            name="Router A",
            host="0.0.0.0",
            port=10001,
            api_username="U10001",
            api_password="pwd_1",
        )
        Router.objects.create(
            name="Router B",
            host="0.0.0.0",
            port=10002,
            api_username="U10002",
            api_password="pwd_2",
        )
        with self.assertRaises(ValidationError):
            get_next_router_identifier(min_val=10001, max_val=10002)

    def test_password_generation_uniqueness(self):
        """Passwords generated across multiple iterations are unique."""
        passwords = set()
        for i in range(50):
            pwd = generate_unique_router_password()
            self.assertNotIn(pwd, passwords)
            self.assertEqual(len(pwd), 24)
            passwords.add(pwd)

    def test_provision_router_defaults_structure(self):
        """provision_router_defaults returns expected keys and default values."""
        defaults = provision_router_defaults()
        self.assertEqual(defaults["host"], "0.0.0.0")
        self.assertEqual(defaults["port"], 10001)
        self.assertEqual(defaults["api_username"], "U10001")
        self.assertTrue(len(defaults["api_password"]) >= 20)
        self.assertTrue(defaults["is_active"])
        self.assertIsNone(defaults["routeros_version"])
