# Internationalization (i18n) Guidelines

This guide establishes the architectural standards and implementation rules for internationalization across the **WiFi Tickets** REST API.

---

## 1. System Mechanism & Language Negotiation

The API is fully bilingual (**English by default**, with **Spanish supported**), driven by Django's native locale middleware (`django.middleware.locale.LocaleMiddleware` in `config/settings/base.py`).

### HTTP Language Negotiation
Frontend clients, mobile apps, and portal pages control the response language by transmitting the standard `Accept-Language` HTTP header:
* `Accept-Language: es` $\rightarrow$ Responses and errors returned in Spanish (`Content-Language: es`).
* `Accept-Language: en` $\rightarrow$ Responses and errors returned in English (`Content-Language: en`).
* When the header is omitted, the default project language is used (`LANGUAGE_CODE = "en"`).

---

## 2. Code Rules: `gettext_lazy` vs `gettext`

A common pitfall in Django REST Framework is evaluating translatable strings prematurely during Python module import time rather than during the request lifecycle.

| Context | Function to Use | Rationale |
|---|---|---|
| **Model Definitions** (`verbose_name`, `help_text`) | `gettext_lazy as _` | Defined at class import time; must evaluate dynamically per request. |
| **Serializer Fields & Validators** (`validators=[...]`, `error_messages={...}`) | `gettext_lazy as _` | Serializers are instantiated and cached at module/class scope. |
| **OpenAPI / Swagger Schemas** (`help_text`, `@extend_schema`) | `gettext_lazy as _` | Allows schema generators to parse definitions without fixing locale. |
| **Dynamic View / ViewSet Methods** | `gettext as _` or `gettext_lazy as _` | Executes inside request lifecycle where locale is already activated. |
| **Domain Services** | `gettext as _` | Invoked directly within endpoint execution flow. |

### Correct Implementation in Serializers ([apps/routers/serializers.py](file:///home/carlos/Desktop/Personal/proyectos-personal/back_wifitickets/apps/routers/serializers.py))
```python
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

class UserRouterWriteSerializer(serializers.ModelSerializer):
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

### Correct Implementation in Views with Parameterized Messages ([apps/tickets/views.py](file:///home/carlos/Desktop/Personal/proyectos-personal/back_wifitickets/apps/tickets/views.py))
```python
from django.utils.translation import gettext as _
from core.responses import error_response

# Parameterized dynamic message
if ticket.status != Ticket.Status.PENDING:
    return error_response(
        detail=_("Only PENDING tickets can be cancelled. Current status: %s") % ticket.status,
        code="invalid_status",
    )
```

> [!IMPORTANT]
> Never use raw Python f-strings with translatable strings (e.g., `f"{_('Error')}: {val}"`). Always use `%` formatting or `.format()` on the evaluated gettext string so `makemessages` extracts the exact template string.

---

## 3. Standardized Response Envelopes

To guarantee predictable frontend parsing across all localized responses:

### A. Success (`core.responses.success_response`)
```json
{
  "data": {
    "detail": "Password updated successfully."
  }
}
```

### B. Business / Validation Error (`core.responses.error_response`)
```json
{
  "error": {
    "code": "wrong_password",
    "detail": "Old password is incorrect."
  }
}
```

### C. DRF Field Validation Error (Intercepted by `custom_exception_handler`)
```json
{
  "error": {
    "email": ["Enter a valid email address."],
    "password_confirm": ["Passwords do not match."]
  }
}
```

---

## 4. Translation Catalog Workflow (`.po` / `.mo`)

The Spanish translation catalog is located at `locale/es/LC_MESSAGES/django.po`.

### Maintenance Flow

1. **Extract new strings marked with `_()` across Python files:**
   ```bash
   python manage.py makemessages -l es -i ".venv*"
   ```
2. **Edit translation entries:**  
   Open `locale/es/LC_MESSAGES/django.po` and populate `msgstr` for each `msgid`:
   ```po
   msgid "This user already has a role assigned for the selected router."
   msgstr "Este usuario ya tiene un rol asignado para el router seleccionado."
   ```
3. **Compile binary catalog (`django.mo`):**
   ```bash
   python manage.py compilemessages -i ".venv*"
   ```

---

## 5. Mandatory Automated i18n Tests

Every application **must** maintain a dedicated `test_i18n.py` file within its `tests/` package asserting:
1. `HTTP_ACCEPT_LANGUAGE="es"` returns `Content-Language: es` and translated Spanish text.
2. `HTTP_ACCEPT_LANGUAGE="en"` (or omitted) returns `Content-Language: en` and English text.

Reference implementations:
* [apps/users/tests/test_i18n.py](file:///home/carlos/Desktop/Personal/proyectos-personal/back_wifitickets/apps/users/tests/test_i18n.py)
* [apps/routers/tests/test_i18n.py](file:///home/carlos/Desktop/Personal/proyectos-personal/back_wifitickets/apps/routers/tests/test_i18n.py)
* [apps/tickets/tests/test_i18n.py](file:///home/carlos/Desktop/Personal/proyectos-personal/back_wifitickets/apps/tickets/tests/test_i18n.py)
* [apps/hotspot/tests/test_i18n.py](file:///home/carlos/Desktop/Personal/proyectos-personal/back_wifitickets/apps/hotspot/tests/test_i18n.py)
