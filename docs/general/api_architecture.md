# API Architecture & DRF Standards

This guide defines the architectural standards, design conventions, and implementation patterns for **Django REST Framework (DRF)** across the **WiFi Tickets** platform.

---

## 1. REST Conventions & Routing Structure

All public API endpoints are namespaced under the `/api/` prefix and grouped by functional domain:

| Prefix | Domain | Responsibility |
|---|---|---|
| `/api/auth/` | `apps.users` | Registration, login, profile management, Google OAuth, and JWT tokens. |
| `/api/routers/` | `apps.routers` | MikroTik device registry, connectivity checks, and user memberships. |
| `/api/tickets/` | `apps.tickets` | Batch generation of WiFi access vouchers, status tracking, and activation. |
| `/api/hotspot/` | `apps.hotspot` | Bandwidth profiles, active network sessions, and captive portal templates. |
| `/api/scripts/` | `apps.scripts` | Jinja2 command templates and remote RouterOS script execution history. |

---

## 2. Standardized Response Envelopes

The API enforces a uniform JSON response contract to guarantee predictability for frontend and client integrations.

### A. Successful Responses (`core.responses`)
All 200/201 responses wrap payload data inside a root `"data"` key:

```json
{
  "data": {
    "id": 1,
    "name": "Main Router",
    "host": "192.168.1.1"
  }
}
```

```python
from core.responses import success_response, created_response

return success_response(serializer.data)
return created_response(serializer.data)
```

### B. Business Logic Error Responses
Errors produced by business rule violations utilize the `error_response` helper:

```json
{
  "error": {
    "code": "invalid_status",
    "detail": "Only PENDING tickets can be cancelled. Current status: active"
  }
}
```

```python
from core.responses import error_response

return error_response(detail=_("Message..."), code="invalid_status", status=400)
```

### C. Global Exception Handling (`core.exceptions.custom_exception_handler`)
Standard DRF exceptions (validation errors, 401 Unauthorized, 403 Forbidden, 404 Not Found) as well as low-level MikroTik network exceptions are intercepted by the global exception handler configured in `REST_FRAMEWORK["EXCEPTION_HANDLER"]`:

* **Serializer / Form Validation Error (HTTP 400):**
  ```json
  {
    "error": {
      "email": ["Enter a valid email address."],
      "password_confirm": ["This field is required."]
    }
  }
  ```

* **Hardware Unreachable / Timeout (HTTP 502 Bad Gateway):**
  ```json
  {
    "error": {
      "code": "mikrotik_unreachable",
      "detail": "Connection to 192.168.1.1:443 timed out after 5.0s"
    }
  }
  ```

---

## 3. Idiomatic Serializer Patterns

### Separation of Read vs Write Serializers
To safeguard sensitive credentials and optimize response payload shape:
* **Read Serializers (`Serializer`):** Present user-friendly, nested representations (e.g., `user_email`, router metadata). **Never** expose sensitive credentials like `api_password`.
* **Write Serializers (`WriteSerializer`):** Accept and validate incoming write-only fields (`write_only: True`).

### Automatic User Injection with `CurrentUserDefault()`
Do not manually extract `request.data.get("user")` or `request.user` in viewsets. Use DRF's native defaults:

```python
from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()

class UserRouterWriteSerializer(serializers.ModelSerializer):
    # When passed by admin, validates PK. When omitted, defaults to request.user.
    user = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        default=serializers.CurrentUserDefault(),
    )

    class Meta:
        model = UserRouter
        fields = ["user", "router", "role"]
```

### Uniqueness Enforcement via `UniqueTogetherValidator`
Instead of implementing ad-hoc `validate()` methods with manual ORM lookups:

```python
    class Meta:
        model = UserRouter
        fields = ["user", "router", "role"]
        validators = [
            serializers.UniqueTogetherValidator(
                queryset=UserRouter.objects.all(),
                fields=["user", "router"],
                message=_("This user already has a role assigned for the selected router."),
            )
        ]
```

### Clean, Delegated Views
Following these serializer patterns keeps viewsets concise and compliant with generic DRF conventions:

```python
    def create(self, request: Request) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        return Response(
            UserRouterSerializer(instance).data,
            status=status.HTTP_201_CREATED,
        )
```

---

## 4. OpenAPI / Swagger Documentation (`drf-spectacular`)

The API automatically compiles and serves an OpenAPI 3.0 specification:
* `/api/schema/` (Raw JSON / YAML specification)
* `/api/docs/` (Interactive Swagger UI)
* `/api/redoc/` (ReDoc schema viewer)

Custom actions (`@action`) must be decorated with `@extend_schema` to document parameter requirements, request bodies, and response shapes:

```python
from drf_spectacular.utils import extend_schema

@extend_schema(
    summary="Cancel a pending ticket",
    description="Transitions a ticket status from PENDING to CANCELLED.",
    responses={200: TicketSerializer, 400: OpenApiTypes.OBJECT},
)
@action(detail=True, methods=["post"])
def cancel(self, request, pk=None):
    ...
```
