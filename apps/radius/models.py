"""
FreeRADIUS standard SQL models.

All models in this file are unmanaged (managed = False). Django will not attempt
to create, alter, or drop tables for these models. The schema is owned and maintained
by the external FreeRADIUS database.
"""

from django.db import models


class RadCheck(models.Model):
    """
    User check attributes (credentials, authentication requirements).
    Table: radcheck
    """

    id = models.BigAutoField(primary_key=True)
    username = models.CharField(max_length=64, db_index=True, verbose_name="Username")
    attribute = models.CharField(
        max_length=64, default="Cleartext-Password", verbose_name="Attribute"
    )
    op = models.CharField(max_length=2, default=":=", verbose_name="Operator")
    value = models.CharField(max_length=253, verbose_name="Value")

    class Meta:
        managed = False
        db_table = "radcheck"
        verbose_name = "RADIUS Check Attribute"
        verbose_name_plural = "RADIUS Check Attributes"
        indexes = [
            models.Index(fields=["username"]),
        ]

    def __str__(self) -> str:
        return f"{self.username} ({self.attribute} {self.op} {self.value})"


class RadReply(models.Model):
    """
    User reply attributes returned to NAS upon successful auth.
    Table: radreply
    """

    id = models.BigAutoField(primary_key=True)
    username = models.CharField(max_length=64, db_index=True, verbose_name="Username")
    attribute = models.CharField(max_length=64, verbose_name="Attribute")
    op = models.CharField(max_length=2, default=":=", verbose_name="Operator")
    value = models.CharField(max_length=253, verbose_name="Value")

    class Meta:
        managed = False
        db_table = "radreply"
        verbose_name = "RADIUS Reply Attribute"
        verbose_name_plural = "RADIUS Reply Attributes"
        indexes = [
            models.Index(fields=["username"]),
        ]

    def __str__(self) -> str:
        return f"{self.username} -> {self.attribute}={self.value}"


class RadUserGroup(models.Model):
    """
    Mapping between a user and a profile group.
    Table: radusergroup
    """

    id = models.BigAutoField(primary_key=True)
    username = models.CharField(max_length=64, db_index=True, verbose_name="Username")
    groupname = models.CharField(max_length=64, verbose_name="Group Name")
    priority = models.IntegerField(default=1, verbose_name="Priority")

    class Meta:
        managed = False
        db_table = "radusergroup"
        verbose_name = "RADIUS User Group"
        verbose_name_plural = "RADIUS User Groups"
        indexes = [
            models.Index(fields=["username"]),
        ]

    def __str__(self) -> str:
        return f"{self.username} in {self.groupname}"


class RadGroupCheck(models.Model):
    """
    Group-level check attributes.
    Table: radgroupcheck
    """

    id = models.BigAutoField(primary_key=True)
    groupname = models.CharField(max_length=64, db_index=True, verbose_name="Group Name")
    attribute = models.CharField(max_length=64, verbose_name="Attribute")
    op = models.CharField(max_length=2, default=":=", verbose_name="Operator")
    value = models.CharField(max_length=253, verbose_name="Value")

    class Meta:
        managed = False
        db_table = "radgroupcheck"
        verbose_name = "RADIUS Group Check Attribute"
        verbose_name_plural = "RADIUS Group Check Attributes"


class RadGroupReply(models.Model):
    """
    Group-level reply attributes (e.g., rate-limits applied to a whole plan).
    Table: radgroupreply
    """

    id = models.BigAutoField(primary_key=True)
    groupname = models.CharField(max_length=64, db_index=True, verbose_name="Group Name")
    attribute = models.CharField(max_length=64, verbose_name="Attribute")
    op = models.CharField(max_length=2, default=":=", verbose_name="Operator")
    value = models.CharField(max_length=253, verbose_name="Value")

    class Meta:
        managed = False
        db_table = "radgroupreply"
        verbose_name = "RADIUS Group Reply Attribute"
        verbose_name_plural = "RADIUS Group Reply Attributes"


class RadAcct(models.Model):
    """
    Accounting session history and active connection records.
    Table: radacct
    """

    radacctid = models.BigAutoField(primary_key=True)
    acctsessionid = models.CharField(
        max_length=64, db_index=True, verbose_name="Session ID"
    )
    acctuniqueid = models.CharField(
        max_length=32, unique=True, verbose_name="Unique Session ID"
    )
    username = models.CharField(max_length=64, db_index=True, verbose_name="Username")
    realm = models.CharField(max_length=64, blank=True, default="", verbose_name="Realm")
    nasipaddress = models.GenericIPAddressField(db_index=True, verbose_name="NAS IP Address")
    nasportid = models.CharField(
        max_length=32, blank=True, null=True, verbose_name="NAS Port ID"
    )
    nasporttype = models.CharField(
        max_length=32, blank=True, null=True, verbose_name="NAS Port Type"
    )
    acctstarttime = models.DateTimeField(
        null=True, blank=True, db_index=True, verbose_name="Session Start Time"
    )
    acctupdatetime = models.DateTimeField(
        null=True, blank=True, verbose_name="Session Update Time"
    )
    acctstoptime = models.DateTimeField(
        null=True, blank=True, db_index=True, verbose_name="Session Stop Time"
    )
    acctinterval = models.IntegerField(
        null=True, blank=True, verbose_name="Accounting Interval (s)"
    )
    acctsessiontime = models.BigIntegerField(
        null=True, blank=True, default=0, verbose_name="Session Duration (s)"
    )
    acctauthentic = models.CharField(
        max_length=32, blank=True, default="", verbose_name="Authentication Type"
    )
    connectinfo_start = models.CharField(
        max_length=128, blank=True, default="", verbose_name="Connect Info Start"
    )
    connectinfo_stop = models.CharField(
        max_length=128, blank=True, default="", verbose_name="Connect Info Stop"
    )
    acctinputoctets = models.BigIntegerField(
        null=True, blank=True, default=0, verbose_name="Upload Bytes"
    )
    acctoutputoctets = models.BigIntegerField(
        null=True, blank=True, default=0, verbose_name="Download Bytes"
    )
    calledstationid = models.CharField(
        max_length=50, blank=True, default="", verbose_name="Called Station ID (SSID/AP MAC)"
    )
    callingstationid = models.CharField(
        max_length=50, blank=True, default="", verbose_name="Calling Station ID (Client MAC)"
    )
    acctterminatecause = models.CharField(
        max_length=32, blank=True, default="", verbose_name="Termination Cause"
    )
    servicetype = models.CharField(
        max_length=32, blank=True, default="", verbose_name="Service Type"
    )
    framedprotocol = models.CharField(
        max_length=32, blank=True, default="", verbose_name="Framed Protocol"
    )
    framedipaddress = models.GenericIPAddressField(
        null=True, blank=True, verbose_name="Assigned Client IP"
    )

    class Meta:
        managed = False
        db_table = "radacct"
        verbose_name = "RADIUS Accounting Record"
        verbose_name_plural = "RADIUS Accounting Records"
        indexes = [
            models.Index(fields=["username"]),
            models.Index(fields=["acctstarttime"]),
            models.Index(fields=["acctstoptime"]),
            models.Index(fields=["nasipaddress"]),
        ]

    @property
    def is_active(self) -> bool:
        """A session is active when no stop time has been recorded."""
        return self.acctstoptime is None

    @property
    def upload_mb(self) -> float:
        """Return total uploaded megabytes."""
        return round((self.acctinputoctets or 0) / (1024 * 1024), 2)

    @property
    def download_mb(self) -> float:
        """Return total downloaded megabytes."""
        return round((self.acctoutputoctets or 0) / (1024 * 1024), 2)

    def __str__(self) -> str:
        status = "ONLINE" if self.is_active else f"STOPPED ({self.acctterminatecause or 'Normal'})"
        return f"{self.username} on {self.nasipaddress} [{status}]"


class RadPostAuth(models.Model):
    """
    Log of authentication attempts (Accept / Reject).
    Table: radpostauth
    """

    id = models.BigAutoField(primary_key=True)
    username = models.CharField(max_length=64, db_index=True, verbose_name="Username")
    pass_field = models.CharField(
        max_length=64, db_column="pass", blank=True, default="", verbose_name="Password"
    )
    reply = models.CharField(max_length=32, verbose_name="Auth Reply")
    authdate = models.DateTimeField(
        auto_now_add=True, db_index=True, verbose_name="Auth Timestamp"
    )

    class Meta:
        managed = False
        db_table = "radpostauth"
        verbose_name = "RADIUS Post-Auth Log"
        verbose_name_plural = "RADIUS Post-Auth Logs"
        indexes = [
            models.Index(fields=["username"]),
            models.Index(fields=["authdate"]),
        ]

    def __str__(self) -> str:
        return f"{self.username} -> {self.reply} at {self.authdate}"


class Nas(models.Model):
    """
    Network Access Server table (MikroTik routers).
    Table: nas
    """

    id = models.BigAutoField(primary_key=True)
    nasname = models.CharField(
        max_length=128, db_index=True, verbose_name="NAS Host/IP"
    )
    shortname = models.CharField(max_length=32, verbose_name="Short Name")
    type = models.CharField(max_length=30, default="other", verbose_name="NAS Type")
    ports = models.IntegerField(null=True, blank=True, verbose_name="Ports")
    secret = models.CharField(max_length=60, verbose_name="Shared Secret")
    server = models.CharField(
        max_length=64, blank=True, null=True, verbose_name="Server"
    )
    community = models.CharField(
        max_length=50, blank=True, null=True, verbose_name="SNMP Community"
    )
    description = models.CharField(
        max_length=200, blank=True, default="", verbose_name="Description"
    )

    class Meta:
        managed = False
        db_table = "nas"
        verbose_name = "Network Access Server (NAS)"
        verbose_name_plural = "Network Access Servers (NAS)"

    def __str__(self) -> str:
        return f"{self.shortname} ({self.nasname})"
