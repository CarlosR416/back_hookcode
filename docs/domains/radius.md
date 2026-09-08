# Domain Specification: RADIUS Integration

* **Module:** `apps.radius`
* **Visibility:** Internal service only (No public REST API exposed).
* **Database Connection:** Secondary connection alias `"radius"` with `RadiusDatabaseRouter`.
* **Schema Control:** Strictly unmanaged (`managed = False`). Django does not run migrations against FreeRADIUS tables.
* **Responsibility:** Interfacing with the FreeRADIUS SQL database to manage user credentials, rate limits/attributes, active sessions, and historical accounting data.

---

## 1. Database Routing & Configuration

The application uses Django's multi-database router pattern via [RadiusDatabaseRouter](file:///home/carlos/Desktop/Personal/proyectos-personal/back_wifitickets/apps/radius/routers.py):
* **Read / Write Routing:** All models belonging to `apps.radius` are automatically routed to `DATABASES["radius"]`.
* **Migration Prevention:** `allow_migrate` returns `False` unconditionally for the `radius` app label, ensuring Django migrations will never create or alter tables on the external FreeRADIUS schema.

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `RADIUS_DB_ENGINE` | `django.db.backends.postgresql` | Database engine (e.g. postgresql or mysql). |
| `RADIUS_DB_NAME` | Value of `DB_NAME` (`wifitickets`) | Database name hosting FreeRADIUS tables. |
| `RADIUS_DB_USER` | Value of `DB_USER` (`wifitickets_user`)| Database username. |
| `RADIUS_DB_PASSWORD` | Value of `DB_PASSWORD` | Database password. |
| `RADIUS_DB_HOST` | Value of `DB_HOST` (`localhost`) | Database hostname/IP. |
| `RADIUS_DB_PORT` | Value of `DB_PORT` (`5432`) | Database port. |

---

## 2. Unmanaged FreeRADIUS Models ([apps/radius/models.py](file:///home/carlos/Desktop/Personal/proyectos-personal/back_wifitickets/apps/radius/models.py))

All models specify `managed = False` and map directly to standard FreeRADIUS SQL tables:

| Model | Table | Purpose |
|---|---|---|
| **`RadCheck`** | `radcheck` | User check attributes (e.g. `Cleartext-Password`, `Simultaneous-Use`). |
| **`RadReply`** | `radreply` | User reply attributes returned to NAS (e.g. `Mikrotik-Rate-Limit`, `Session-Timeout`). |
| **`RadUserGroup`** | `radusergroup` | Assigns users to profile groups. |
| **`RadGroupCheck`** | `radgroupcheck` | Check attributes applied at group level. |
| **`RadGroupReply`** | `radgroupreply` | Reply attributes applied at group level. |
| **`RadAcct`** | `radacct` | Accounting logs for sessions (start, stop, input/output octets, IP, MAC). |
| **`RadPostAuth`** | `radpostauth` | Authentication attempt history (`Accept` / `Reject`). |
| **`Nas`** | `nas` | MikroTik routers registered as Network Access Servers. |

---

## 3. Internal Python Service API ([RadiusService](file:///home/carlos/Desktop/Personal/proyectos-personal/back_wifitickets/apps/radius/services.py))

Other backend apps (such as `apps.tickets` or `apps.hotspot`) interact with RADIUS using the class methods of `RadiusService`.

### A. User Management

```python
from apps.radius.services import RadiusService

# 1. Create or overwrite a RADIUS user/voucher
RadiusService.add_user(
    username="ticket_1001",
    password="securepassword",
    group="Plan-1Hour",
    reply_attributes={
        "Mikrotik-Rate-Limit": "10M/10M",
        "Session-Timeout": "3600",
    },
    check_attributes={
        "Simultaneous-Use": "1",
    },
)

# 2. Update user password
RadiusService.update_user_password(
    username="ticket_1001",
    new_password="new_password_123",
)

# 3. Fetch user profile and current online status
user_info = RadiusService.get_user_info("ticket_1001")
# Returns:
# {
#     "username": "ticket_1001",
#     "group": "Plan-1Hour",
#     "check_attributes": {"Cleartext-Password": "...", "Simultaneous-Use": "1"},
#     "reply_attributes": {"Mikrotik-Rate-Limit": "10M/10M", "Session-Timeout": "3600"},
#     "is_online": False,
# }

# 4. Delete user across radcheck, radreply, and radusergroup
deleted = RadiusService.delete_user("ticket_1001")
```

### B. Sessions & Connection History

```python
# 1. Query currently active connections (acctstoptime IS NULL)
active_sessions = RadiusService.get_active_sessions(username="ticket_1001")
# Each session contains:
# session_id, unique_id, username, nas_ip, start_time, duration_seconds,
# upload_mb, download_mb, client_ip, client_mac

# 2. Check if user is currently connected
is_online = RadiusService.is_user_online("ticket_1001")

# 3. Connection history logs
history = RadiusService.get_connection_history(username="ticket_1001", limit=50)

# 4. Total bandwidth consumed across all sessions
bw = RadiusService.get_user_total_bandwidth("ticket_1001")
# Returns: {"total_upload_mb": 142.5, "total_download_mb": 850.2}
```

### C. Router / NAS Registration

```python
# Register or update a MikroTik router in the FreeRADIUS nas table
RadiusService.register_nas(
    nasname="192.168.88.1",
    secret="rad_shared_secret",
    shortname="Core-Mikrotik",
    description="Reception Hotspot Gateway",
)
```

---

## 4. Test Traceability

| Test Sub-Domain | File | Key Scenarios Verified |
|---|---|---|
| **Service Operations** | [apps/radius/tests/test_services.py](file:///home/carlos/Desktop/Personal/proyectos-personal/back_wifitickets/apps/radius/tests/test_services.py) | User creation with check/reply attributes, password update, cascade deletion, active session tracking, historical accounting, bandwidth calculation, NAS upsert, and migration block verification. |
