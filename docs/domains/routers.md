# Domain Specification: Routers & Memberships

* **Module:** `apps.routers`
* **API Prefix:** `/api/routers/`
* **Responsibility:** MikroTik RouterOS device registry, secure API credential storage, connectivity health checks, and multi-tenant Role-Based Access Control (RBAC).

---

## 1. Data Models & Entities

### Model `Router` ([apps/routers/models.py](file:///home/carlos/Desktop/Personal/proyectos-personal/back_wifitickets/apps/routers/models.py))
Represents a physical or virtual MikroTik RouterOS device:
* **Connectivity:** `host` (IP or hostname), `port` (HTTPS port, defaults to 443), `ssl_verify`.
* **API Credentials:** `api_username`, `api_password` (shielded as write-only in serializers).
* **RouterOS Version:** `v6` (SSH / legacy API) or `v7` (REST API over HTTPS).

### Model `UserRouter` ([apps/routers/models.py](file:///home/carlos/Desktop/Personal/proyectos-personal/back_wifitickets/apps/routers/models.py))
Associates a user with a specific router under an assigned permission role:
* **Available Roles:**
  - `OWNER` (`owner`): Full CRUD permissions and live remote action authorization.
  - `VIEWER` (`viewer`): Read-only visibility (status, metrics, and ping).
* **Uniqueness Invariant:** `UniqueConstraint(fields=["user", "router"], name="unique_user_router")`.

---

## 2. Invariants & Business Rules

1. **Role Uniqueness Invariant:** A user may only hold a single role per router. Duplicates are intercepted at the serializer layer via DRF's `UniqueTogetherValidator` before database execution.
2. **Multi-Tenant Queryset Isolation (`get_queryset`):**
   - Non-staff users only see routers where an active `UserRouter` record exists for their account.
   - Querying an unassigned router ID returns `HTTP 404 Not Found` (DRF standard for filtered querysets), never 403.
3. **Owner Assignment on Creation:**
   - When an authenticated user creates a `Router`, they are automatically assigned as `OWNER` via `UserRouter.objects.create(user=request.user, router=instance, role=OWNER)`.
4. **Credential Protection:**
   - `RouterSerializer` (read) completely omits `api_password`. Only `RouterWriteSerializer` accepts passwords (`write_only: True`).
5. **Admin-Only Membership Management:**
   - The `/api/routers/memberships/` endpoint requires `IsAdminUser`.
   - Allows assigning an explicit `user` ID or defaulting to the requesting user via `CurrentUserDefault()`.

---

## 3. Endpoints Catalog

| Method | Path | Permission | Description |
|---|---|---|---|
| `GET` | `/api/routers/` | `IsAuthenticated` | Lists routers accessible to the user (or all if staff). |
| `POST` | `/api/routers/` | `IsAuthenticated` | Creates a router and assigns creator as `OWNER`. |
| `GET` | `/api/routers/{id}/` | `IsAuthenticated` | Retrieves router details (requires active membership). |
| `PUT / PATCH`| `/api/routers/{id}/` | `IsRouterOwner` | Updates router configuration (Owner only). |
| `DELETE` | `/api/routers/{id}/` | `IsRouterOwner` | Deletes router and associations (Owner only). |
| `POST` | `/api/routers/{id}/ping/` | `IsAuthenticated` | Performs real-time connectivity health check with MikroTik. |
| `GET` | `/api/routers/memberships/` | `IsAdminUser` | Lists all user-router memberships. |
| `POST` | `/api/routers/memberships/` | `IsAdminUser` | Creates a membership with uniqueness validation. |

---

## 4. Test Traceability

| Test Sub-Domain | File | Key Scenarios Verified |
|---|---|---|
| **Memberships** | [apps/routers/tests/test_memberships.py](file:///home/carlos/Desktop/Personal/proyectos-personal/back_wifitickets/apps/routers/tests/test_memberships.py) | Successful admin assignment, automatic `CurrentUserDefault()` fallback, duplicate rejection. |
| **Permissions & RBAC** | [apps/routers/tests/test_permissions.py](file:///home/carlos/Desktop/Personal/proyectos-personal/back_wifitickets/apps/routers/tests/test_permissions.py) | Owner can update (`HTTP 200`), Viewer rejected from updating (`HTTP 403`), unassigned returns `HTTP 404`. |
| **Internationalization** | [apps/routers/tests/test_i18n.py](file:///home/carlos/Desktop/Personal/proyectos-personal/back_wifitickets/apps/routers/tests/test_i18n.py) | Spanish and English assertions for uniqueness validation and owner permission denial messages. |
