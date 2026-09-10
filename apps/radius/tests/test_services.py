"""
Unit tests for RadiusService and RadiusDatabaseRouter.
"""

from datetime import timedelta
from django.db import connections
from django.test import TestCase
from django.utils import timezone

from apps.radius.models import (
    Nas,
    RadAcct,
    RadCheck,
    RadGroupCheck,
    RadGroupReply,
    RadPostAuth,
    RadReply,
    RadUserGroup,
)
from apps.radius.routers import RadiusDatabaseRouter
from apps.radius.services import RadiusService


class RadiusServiceTests(TestCase):
    databases = {"default", "radius"}

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._models = [
            RadCheck,
            RadReply,
            RadUserGroup,
            RadGroupCheck,
            RadGroupReply,
            RadAcct,
            RadPostAuth,
            Nas,
        ]
        # Dynamically create unmanaged schema in test database
        with connections["radius"].schema_editor() as editor:
            for model in cls._models:
                editor.create_model(model)

    @classmethod
    def tearDownClass(cls):
        with connections["radius"].schema_editor() as editor:
            for model in reversed(cls._models):
                editor.delete_model(model)
        super().tearDownClass()

    def test_database_router_routing_and_migrations(self):
        """Verify RadiusDatabaseRouter routes to 'radius' and forbids migrations."""
        router = RadiusDatabaseRouter()

        self.assertEqual(router.db_for_read(RadCheck), "radius")
        self.assertEqual(router.db_for_write(RadCheck), "radius")
        self.assertFalse(router.allow_migrate("radius", "radius"))
        self.assertFalse(router.allow_migrate("default", "radius"))

    def test_add_radius_user_with_attributes_and_group(self):
        """Verify adding a user creates radcheck, radreply, and radusergroup records."""
        result = RadiusService.add_user(
            username="ticket_user_1",
            password="secret_pass_123",
            group="VIP-Plan",
            reply_attributes={"Mikrotik-Rate-Limit": "20M/20M", "Session-Timeout": "7200"},
            check_attributes={"Simultaneous-Use": "1"},
        )

        self.assertEqual(result["username"], "ticket_user_1")
        self.assertEqual(result["group"], "VIP-Plan")
        self.assertEqual(result["reply_attributes"]["Mikrotik-Rate-Limit"], "20M/20M")

        # Verify DB records (automatically routed to 'radius' database)
        check_pass = RadCheck.objects.get(
            username="ticket_user_1", attribute="Cleartext-Password"
        )
        self.assertEqual(check_pass.value, "secret_pass_123")

        check_sim = RadCheck.objects.get(
            username="ticket_user_1", attribute="Simultaneous-Use"
        )
        self.assertEqual(check_sim.value, "1")

        reply_rate = RadReply.objects.get(
            username="ticket_user_1", attribute="Mikrotik-Rate-Limit"
        )
        self.assertEqual(reply_rate.value, "20M/20M")

        user_group = RadUserGroup.objects.get(username="ticket_user_1")
        self.assertEqual(user_group.groupname, "VIP-Plan")

    def test_add_radius_user_with_client_id(self):
        """Verify client_id is correctly persisted to RadCheck records."""
        result = RadiusService.add_user(
            username="client_id_user",
            password="client_pass_123",
            client_id=42,
            check_attributes={"Simultaneous-Use": "1"},
        )
        self.assertEqual(result["client_id"], 42)

        check_pass = RadCheck.objects.get(
            username="client_id_user", attribute="Cleartext-Password"
        )
        self.assertEqual(check_pass.client_id, 42)

        check_sim = RadCheck.objects.get(
            username="client_id_user", attribute="Simultaneous-Use"
        )
        self.assertEqual(check_sim.client_id, 42)

    def test_add_radius_user_negative_client_id_raises_error(self):
        """Verify client_id < 0 raises ValueError."""
        with self.assertRaises(ValueError):
            RadiusService.add_user(
                username="invalid_client_user",
                password="password",
                client_id=-1,
            )

    def test_get_user_info(self):
        """Verify retrieving user info returns aggregated details."""
        RadiusService.add_user(
            username="info_user",
            password="test_password",
            group="Basic",
            reply_attributes={"Session-Timeout": "3600"},
        )

        info = RadiusService.get_user_info("info_user")
        self.assertIsNotNone(info)
        self.assertEqual(info["username"], "info_user")
        self.assertEqual(info["group"], "Basic")
        self.assertEqual(info["check_attributes"]["Cleartext-Password"], "test_password")
        self.assertEqual(info["reply_attributes"]["Session-Timeout"], "3600")
        self.assertFalse(info["is_online"])

        # Nonexistent user
        self.assertIsNone(RadiusService.get_user_info("nonexistent_user"))

    def test_update_user_password(self):
        """Verify updating user password updates Cleartext-Password."""
        RadiusService.add_user(username="pwd_user", password="initial_password")
        self.assertTrue(RadiusService.update_user_password("pwd_user", "updated_password_456"))

        check = RadCheck.objects.get(
            username="pwd_user", attribute="Cleartext-Password"
        )
        self.assertEqual(check.value, "updated_password_456")

        # Nonexistent user
        self.assertFalse(RadiusService.update_user_password("ghost_user", "some_password"))

    def test_delete_user(self):
        """Verify delete_user cleans up checks, replies, and group memberships."""
        RadiusService.add_user(
            username="del_user",
            password="temp",
            group="G1",
            reply_attributes={"Attr": "Val"},
        )
        self.assertTrue(RadiusService.delete_user("del_user"))

        self.assertFalse(RadCheck.objects.filter(username="del_user").exists())
        self.assertFalse(RadReply.objects.filter(username="del_user").exists())
        self.assertFalse(RadUserGroup.objects.filter(username="del_user").exists())

        # Calling again returns False
        self.assertFalse(RadiusService.delete_user("del_user"))

    def test_active_sessions_and_connection_history(self):
        """Verify querying active sessions and historical records from radacct."""
        now = timezone.now()

        # 1. Active session
        RadAcct.objects.create(
            acctsessionid="sess_active_01",
            acctuniqueid="uniq_active_01",
            username="session_user",
            nasipaddress="192.168.88.1",
            nasportid="ether1",
            acctstarttime=now - timedelta(minutes=15),
            acctstoptime=None,
            acctsessiontime=900,
            acctinputoctets=10 * 1024 * 1024,  # 10 MB
            acctoutputoctets=25 * 1024 * 1024,  # 25 MB
            callingstationid="AA:BB:CC:DD:EE:FF",
            framedipaddress="10.5.50.25",
        )

        # 2. Completed session
        RadAcct.objects.create(
            acctsessionid="sess_stopped_01",
            acctuniqueid="uniq_stopped_01",
            username="session_user",
            nasipaddress="192.168.88.1",
            nasportid="ether1",
            acctstarttime=now - timedelta(hours=2),
            acctstoptime=now - timedelta(hours=1),
            acctsessiontime=3600,
            acctinputoctets=5 * 1024 * 1024,
            acctoutputoctets=10 * 1024 * 1024,
            callingstationid="AA:BB:CC:DD:EE:FF",
            framedipaddress="10.5.50.20",
            acctterminatecause="User-Request",
        )

        # Active sessions
        active = RadiusService.get_active_sessions(username="session_user")
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["session_id"], "sess_active_01")
        self.assertEqual(active[0]["upload_mb"], 10.0)
        self.assertEqual(active[0]["download_mb"], 25.0)
        self.assertEqual(active[0]["client_mac"], "AA:BB:CC:DD:EE:FF")
        self.assertTrue(RadiusService.is_user_online("session_user"))

        # History
        history = RadiusService.get_connection_history(username="session_user")
        self.assertEqual(len(history), 2)

        # Total bandwidth
        bw = RadiusService.get_user_total_bandwidth("session_user")
        self.assertEqual(bw["total_upload_mb"], 15.0)
        self.assertEqual(bw["total_download_mb"], 35.0)

    def test_register_nas(self):
        """Verify registering a Network Access Server in the nas table."""
        nas = RadiusService.register_nas(
            nasname="192.168.88.1",
            secret="radius_secret_key",
            shortname="Core-Mikrotik",
            description="Main hotspot gateway",
        )
        self.assertEqual(nas.nasname, "192.168.88.1")
        self.assertEqual(nas.secret, "radius_secret_key")
        self.assertEqual(nas.shortname, "Core-Mikrotik")

        # Update existing
        updated_nas = RadiusService.register_nas(
            nasname="192.168.88.1",
            secret="new_secret_key",
            shortname="Core-Mikrotik-Updated",
        )
        self.assertEqual(updated_nas.secret, "new_secret_key")
        self.assertEqual(Nas.objects.filter(nasname="192.168.88.1").count(), 1)
