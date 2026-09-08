# Domain Specification: Routers & Memberships

* **Module:** `apps.routers`
* **API Prefix:** `/api/routers/`
* **Responsibility:** MikroTik RouterOS device registry, secure API credential storage, connectivity health checks, and multi-tenant Role-Based Access Control (RBAC).

---

## 1. Data Models & Entities

### Model `Router` ([apps/routers/models.py](file:///home/carlos/Desktop/Personal/proyectos-personal/back_wifitickets/apps/routers/models.py))
Represents a physical or virtual MikroTik RouterOS device:
* **Connectivity:** `host` (defaults to `0.0.0.0`), `port` (unique base port, sequentially assigned in range `10001`–`15000`), `ssl_verify`.
* **Computed Ports:**
  - `winbox_port`: MikroTik Winbox remote management port (identical to base `port`, e.g., `10001`).
  - `api_port`: MikroTik REST API HTTPS port (base `port + 5000`, e.g., `15001`).
* **API Credentials:** `api_username` (unique, sequentially assigned starting at `U10001` matching port), `api_password` (unique 24-character cryptographic alphanumeric string, shielded as write-only).
* **RouterOS Version:** Nullable (`null=True, default=None`), or set to `v6` / `v7`.

### Model `UserRouter` ([apps/routers/models.py](file:///home/carlos/Desktop/Personal/proyectos-personal/back_wifitickets/apps/routers/models.py))
Associates a user with a specific router under an assigned permission role:
* **Available Roles:**
  - `OWNER` (`owner`): Full CRUD permissions and live remote action authorization.
  - `VIEWER` (`viewer`): Read-only visibility (status, metrics, and ping).
* **Uniqueness Invariant:** `UniqueConstraint(fields=["user", "router"], name="unique_user_router")`.

---

## 2. Invariants & Business Rules

1. **Role Uniqueness Invariant:** A user may only hold a single role per router. Duplicates are intercepted at the serializer layer via DRF's `UniqueTogetherValidator` before database execution.
2. **Simplified Client Registration:**
   - On `POST /api/routers/`, clients submit only `name` (required) and `description` (optional).
   - Response envelope exposes only `id`, `name`, and `description`.
3. **Sequential & Collision-Free Provisioning (`apps/routers/services.py`):**
   - Identifier begins at `10001` and increments in lockstep up to `15000`.
   - `port` is set to the integer identifier (e.g., `10001`).
   - `api_username` is set to `U<identifier>` (e.g., `"U10001"`).
   - `api_password` is generated as a collision-free 24-character random password.
   - `host` defaults to `"0.0.0.0"`, `is_active` to `True`, and `routeros_version` to `None`.
4. **Multi-Tenant Queryset Isolation (`get_queryset`):**
   - Non-staff users only see active routers (`is_active=True`) where an active `UserRouter` record exists for their account.
   - Staff users see all active routers by default, with optional inclusion of inactive routers via `?include_inactive=true`.
   - Querying an unassigned or inactive router ID returns `HTTP 404 Not Found` (DRF standard for filtered querysets), never 403.
5. **Owner Assignment on Creation:**
   - When an authenticated user creates a `Router`, they are automatically assigned as `OWNER` via `UserRouter.objects.create(user=request.user, router=instance, role=OWNER)`.
6. **Credential Protection:**
   - `RouterSerializer` (read) completely omits `api_password`. Only `RouterWriteSerializer` accepts passwords (`write_only: True`).
7. **Admin-Only Membership Management:**
   - The `/api/routers/memberships/` endpoint requires `IsAdminUser`.
   - Allows assigning an explicit `user` ID or defaulting to the requesting user via `CurrentUserDefault()`.
8. **FreeRADIUS Synchronization & Atomic Provisioning:**
   - On registration (`POST /api/routers/`), router creation, owner membership assignment, and FreeRADIUS user provisioning are executed within an atomic transaction (`@transaction.atomic`). If FreeRADIUS user creation fails, the entire transaction is rolled back and no router or membership is created.
   - A corresponding FreeRADIUS user is created with `api_username` and an independent, cryptographically secure random password (distinct from `api_password`) via `RadiusService.add_user()`.
   - On deletion (`DELETE /api/routers/{id}/` or `router.soft_delete()`), the corresponding RADIUS user records (`radcheck`, `radreply`, `radusergroup`) are purged via `RadiusService.delete_user()`.
9. **Owner-Only Logical Deletion:**
   - Deletion of a router (`DELETE /api/routers/{id}/`) performs **logical deletion** (soft delete: sets `is_active = False`) and purges its FreeRADIUS user credentials.
   - The operation strictly requires the requesting user to be the `OWNER` of the router (`UserRouter.role == 'owner'`).
   - Viewers attempting deletion receive `HTTP 403 Forbidden`.
   - Non-owner staff users attempting deletion receive `HTTP 403 Forbidden`.
   - Users without an associated membership receive `HTTP 404 Not Found`.
   - Database records (`Router`, `UserRouter`) are preserved for auditing and historical associations.

---

## 3. Endpoints Catalog

| Method | Path | Permission | Description |
|---|---|---|---|
| `GET` | `/api/routers/` | `IsAuthenticated` | Lists routers accessible to the user (or all if staff). |
| `POST` | `/api/routers/` | `IsAuthenticated` | Creates a router with dynamic U10001/port provisioning, assigns creator as `OWNER`, and creates RADIUS user. |
| `GET` | `/api/routers/{id}/` | `IsAuthenticated` | Retrieves router details (requires active membership). |
| `PUT / PATCH`| `/api/routers/{id}/` | `IsRouterOwner` | Updates router configuration (Owner only). |
| `DELETE` | `/api/routers/{id}/` | `IsRouterOwner` | Performs logical deletion (soft delete, `is_active=False`) and cleans up RADIUS user credentials (Owner only). |
| `POST` | `/api/routers/{id}/ping/` | `IsAuthenticated` | Performs real-time connectivity health check with MikroTik. |
| `POST` | `/api/routers/{id}/generate-bootstrap-token/` | `IsRouterOwner` | Generates a single-use (Burn-on-Read) download token and RouterOS fetch command for initial provisioning. |
| `GET` | `/api/routers/memberships/` | `IsAdminUser` | Lists all user-router memberships. |
| `POST` | `/api/routers/memberships/` | `IsAdminUser` | Creates a membership with uniqueness validation. |

---

## 4. Test Traceability

| Test Sub-Domain | File | Key Scenarios Verified |
|---|---|---|
| **Provisioning Services** | [apps/routers/tests/test_services.py](file:///home/carlos/Desktop/Personal/proyectos-personal/back_wifitickets/apps/routers/tests/test_services.py) | Sequential identifier allocation starting at `U10001`/`10001`, password uniqueness, and range exhaustion. |
| **Memberships** | [apps/routers/tests/test_memberships.py](file:///home/carlos/Desktop/Personal/proyectos-personal/back_wifitickets/apps/routers/tests/test_memberships.py) | Successful admin assignment, automatic `CurrentUserDefault()` fallback, duplicate rejection. |
| **Permissions & RBAC** | [apps/routers/tests/test_permissions.py](file:///home/carlos/Desktop/Personal/proyectos-personal/back_wifitickets/apps/routers/tests/test_permissions.py) | Router creation envelope (only id, name, description), Owner update (`HTTP 200`), Viewer update denial (`HTTP 403`), Owner soft-delete (`HTTP 204`), Viewer delete denial (`HTTP 403`), Non-owner staff delete denial (`HTTP 403`). |
| **Internationalization** | [apps/routers/tests/test_i18n.py](file:///home/carlos/Desktop/Personal/proyectos-personal/back_wifitickets/apps/routers/tests/test_i18n.py) | Spanish and English assertions for uniqueness validation and owner permission denial messages. |
| **RADIUS Integration** | [apps/routers/tests/test_radius_integration.py](file:///home/carlos/Desktop/Personal/proyectos-personal/back_wifitickets/apps/routers/tests/test_radius_integration.py) | FreeRADIUS user credential creation on router registration, and complete cleanup on router logical deletion. |
