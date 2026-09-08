"""
RADIUS Service Layer.

Provides a unified Python API for internal project components (Hotspot, Tickets,
Routers) to interact with FreeRADIUS database records:
- User credential provisioning and teardown (radcheck, radreply, radusergroup)
- Active connection inspection and history reporting (radacct)
- Network Access Server (NAS) registration
"""

from typing import Any
from django.db import transaction
from django.db.models import Sum

from .models import Nas, RadAcct, RadCheck, RadReply, RadUserGroup


class RadiusService:
    """
    High-level service interface for managing FreeRADIUS records.
    All operations are automatically routed to the 'radius' database connection
    by RadiusDatabaseRouter.
    """

    @classmethod
    def _atomic(cls):
        """Context manager for atomic transactions on the RADIUS database."""
        return transaction.atomic(using="radius")

    @classmethod
    def add_user(
        cls,
        username: str,
        password: str,
        group: str | None = None,
        reply_attributes: dict[str, str] | None = None,
        check_attributes: dict[str, str] | None = None,
        client_id: int | None = None,
    ) -> dict[str, Any]:
        """
        Create or overwrite a RADIUS user credentials and authorization profile.

        :param username: Identifier for the RADIUS user / voucher code.
        :param password: Password for authentication (Cleartext-Password).
        :param group: Optional profile group (e.g. 'Standard-1h').
        :param reply_attributes: Optional dictionary of RADIUS reply attributes
                                 (e.g., {'Mikrotik-Rate-Limit': '10M/10M', 'Session-Timeout': '3600'}).
        :param check_attributes: Optional additional check attributes
                                 (e.g., {'Simultaneous-Use': '1'}).
        :param client_id: Optional integer identifier for the client / router.
        :return: Dictionary summary of the created user records.
        """
        if client_id is not None and client_id < 0:
            raise ValueError("client_id cannot be less than zero.")

        with cls._atomic():
            # Clean up existing records for idempotency
            RadCheck.objects.filter(username=username).delete()
            RadReply.objects.filter(username=username).delete()
            RadUserGroup.objects.filter(username=username).delete()

            # 1. Primary password check attribute
            RadCheck.objects.create(
                username=username,
                attribute="Cleartext-Password",
                op=":=",
                value=password,
                client_id=client_id,
            )

            # 2. Additional check attributes
            if check_attributes:
                for attr, val in check_attributes.items():
                    RadCheck.objects.create(
                        username=username,
                        attribute=attr,
                        op=":=",
                        value=val,
                        client_id=client_id,
                    )

            # 3. Reply attributes (rate limits, session timeouts, etc.)
            created_replies: dict[str, str] = {}
            if reply_attributes:
                for attr, val in reply_attributes.items():
                    RadReply.objects.create(
                        username=username,
                        attribute=attr,
                        op=":=",
                        value=val,
                    )
                    created_replies[attr] = val

            # 4. Group assignment
            if group:
                RadUserGroup.objects.create(
                    username=username,
                    groupname=group,
                    priority=1,
                )

        return {
            "username": username,
            "group": group,
            "reply_attributes": created_replies,
            "client_id": client_id,
        }

    @classmethod
    def delete_user(cls, username: str) -> bool:
        """
        Delete all RADIUS records associated with a username
        (radcheck, radreply, radusergroup).

        :param username: The username to delete.
        :return: True if records were deleted, False if no user was found.
        """
        with cls._atomic():
            checks_deleted, _ = RadCheck.objects.filter(username=username).delete()
            RadReply.objects.filter(username=username).delete()
            RadUserGroup.objects.filter(username=username).delete()

        return checks_deleted > 0

    @classmethod
    def update_user_password(cls, username: str, new_password: str) -> bool:
        """
        Update the Cleartext-Password attribute for an existing user.

        :param username: The username whose password to update.
        :param new_password: The new password string.
        :return: True if updated, False if user does not exist.
        """
        updated = RadCheck.objects.filter(
            username=username, attribute="Cleartext-Password"
        ).update(value=new_password)

        if updated == 0:
            if RadCheck.objects.filter(username=username).exists():
                RadCheck.objects.create(
                    username=username,
                    attribute="Cleartext-Password",
                    op=":=",
                    value=new_password,
                )
                return True
            return False
        return True

    @classmethod
    def get_user_info(cls, username: str) -> dict[str, Any] | None:
        """
        Fetch complete profile info for a RADIUS user.

        :param username: The username to query.
        :return: Dict containing checks, replies, group, and online status, or None.
        """
        checks = list(
            RadCheck.objects.filter(username=username).values("attribute", "op", "value")
        )
        if not checks:
            return None

        replies = {
            r["attribute"]: r["value"]
            for r in RadReply.objects.filter(username=username).values("attribute", "value")
        }

        group_obj = RadUserGroup.objects.filter(username=username).order_by("priority").first()
        group_name = group_obj.groupname if group_obj else None

        return {
            "username": username,
            "group": group_name,
            "check_attributes": {c["attribute"]: c["value"] for c in checks},
            "reply_attributes": replies,
            "is_online": cls.is_user_online(username),
        }

    @classmethod
    def get_active_sessions(
        cls, username: str | None = None, nas_ip: str | None = None
    ) -> list[dict[str, Any]]:
        """
        List all currently active sessions (acctstoptime IS NULL) from radacct.

        :param username: Optional username filter.
        :param nas_ip: Optional NAS IP address filter.
        :return: List of active session dictionaries.
        """
        qs = RadAcct.objects.filter(acctstoptime__isnull=True)
        if username:
            qs = qs.filter(username=username)
        if nas_ip:
            qs = qs.filter(nasipaddress=nas_ip)

        sessions: list[dict[str, Any]] = []
        for record in qs.order_by("-acctstarttime"):
            sessions.append(
                {
                    "session_id": record.acctsessionid,
                    "unique_id": record.acctuniqueid,
                    "username": record.username,
                    "nas_ip": record.nasipaddress,
                    "nas_port": record.nasportid,
                    "start_time": record.acctstarttime,
                    "duration_seconds": record.acctsessiontime or 0,
                    "upload_mb": record.upload_mb,
                    "download_mb": record.download_mb,
                    "client_ip": record.framedipaddress,
                    "client_mac": record.callingstationid,
                }
            )
        return sessions

    @classmethod
    def get_connection_history(
        cls,
        username: str | None = None,
        nas_ip: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Retrieve historical session accounting logs from radacct.

        :param username: Optional username filter.
        :param nas_ip: Optional NAS IP filter.
        :param limit: Maximum records to return.
        :return: List of historical session log dictionaries.
        """
        qs = RadAcct.objects.all()
        if username:
            qs = qs.filter(username=username)
        if nas_ip:
            qs = qs.filter(nasipaddress=nas_ip)

        history: list[dict[str, Any]] = []
        for record in qs.order_by("-acctstarttime")[:limit]:
            history.append(
                {
                    "session_id": record.acctsessionid,
                    "username": record.username,
                    "nas_ip": record.nasipaddress,
                    "start_time": record.acctstarttime,
                    "stop_time": record.acctstoptime,
                    "duration_seconds": record.acctsessiontime or 0,
                    "upload_mb": record.upload_mb,
                    "download_mb": record.download_mb,
                    "terminate_cause": record.acctterminatecause,
                    "client_ip": record.framedipaddress,
                    "client_mac": record.callingstationid,
                    "is_active": record.is_active,
                }
            )
        return history

    @classmethod
    def is_user_online(cls, username: str) -> bool:
        """Check whether a user currently has an active connection in radacct."""
        return RadAcct.objects.filter(username=username, acctstoptime__isnull=True).exists()

    @classmethod
    def get_user_total_bandwidth(cls, username: str) -> dict[str, float]:
        """
        Aggregate total historical uploaded and downloaded megabytes for a user.

        :param username: Target username.
        :return: Dict with 'total_upload_mb' and 'total_download_mb'.
        """
        result = RadAcct.objects.filter(username=username).aggregate(
            total_up=Sum("acctinputoctets"), total_down=Sum("acctoutputoctets")
        )
        total_up_bytes = result.get("total_up") or 0
        total_down_bytes = result.get("total_down") or 0

        return {
            "total_upload_mb": round(total_up_bytes / (1024 * 1024), 2),
            "total_download_mb": round(total_down_bytes / (1024 * 1024), 2),
        }

    @classmethod
    def register_nas(
        cls,
        nasname: str,
        secret: str,
        shortname: str = "",
        nas_type: str = "other",
        description: str = "",
    ) -> Nas:
        """
        Register or update a Network Access Server (MikroTik router) in the nas table.

        :param nasname: IP or hostname of the router.
        :param secret: Shared secret for RADIUS communication.
        :param shortname: Descriptive short label.
        :param nas_type: FreeRADIUS NAS type (defaults to 'other').
        :param description: Optional description.
        :return: The Nas model instance.
        """
        nas, _ = Nas.objects.update_or_create(
            nasname=nasname,
            defaults={
                "shortname": shortname or nasname,
                "secret": secret,
                "type": nas_type,
                "description": description,
            },
        )
        return nas
