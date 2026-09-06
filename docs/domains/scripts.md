# Domain Specification: Scripts & Automation

* **Module:** `apps.scripts`
* **API Prefix:** `/api/scripts/`
* **Responsibility:** Parameterized RouterOS command templates, dynamic Jinja2 rendering, and execution auditing across remote MikroTik routers.

---

## 1. Data Models & Entities

### Model `ScriptTemplate` ([apps/scripts/models.py](file:///home/carlos/Desktop/Personal/proyectos-personal/back_wifitickets/apps/scripts/models.py))
Stores reusable RouterOS command templates containing Jinja2 template placeholders:
* **Example Content:**
  ```jinja2
  /ip address add address={{ ip_address }} interface={{ interface }}
  /ip hotspot user add name={{ username }} password={{ password }} profile={{ profile }}
  ```

### Model `RouterScriptExecution` ([apps/scripts/models.py](file:///home/carlos/Desktop/Personal/proyectos-personal/back_wifitickets/apps/scripts/models.py))
Immutable historical record of a script execution dispatched to a target router:
* **Parameters:** `router` (FK), `template` (Optional FK for ad-hoc scripts), `variables_used` (JSON).
* **Execution Statuses:** `PENDING`, `IN_PROGRESS`, `SUCCESS`, `FAILED`.
* **Console Output:** `output_log` (stdout/stderr stream returned by RouterOS).
* **Calculated Property `rendered_content`:** Compiles the final script string by interpolating variables into the Jinja2 template.

### Model `ScriptDownloadToken` ([apps/scripts/models.py](file:///home/carlos/Desktop/Personal/proyectos-personal/back_wifitickets/apps/scripts/models.py))
Cryptographically secure, single-use download token (Burn-on-Read) for remote RouterOS script provisioning:
* **Fields:** `router` (FK), `template` (FK, nullable), `execution` (FK, nullable), `token` (64 chars, unique indexed), `variables_used` (JSON), `created_at`, `expires_at`, `is_consumed`, `consumed_at`, `include_cleanup` (boolean), `filename` (e.g. `setup.rsc`).
* **Lifecycle Methods:**
  - `is_valid()`: Checks if token is not consumed and `now <= expires_at`.
  - `burn()`: Immediately marks `is_consumed=True` and sets `consumed_at=now`.
* **Dynamic Property `rendered_content`:**
  - Prepends an automated RouterOS metadata banner.
  - Compiles script content (from linked execution, or template + variables, or raw string).
  - Appends `:delay 2s; /file remove [find name="{filename}"];` when `include_cleanup=True` so the file automatically self-destructs from RouterOS flash storage upon `/import`.

---

## 2. Invariants & Business Rules

1. **Deterministic Script Rendering:**
   - When a template is associated, `rendered_content` renders the string using `Template(content).render(**variables_used)`.
   - If no template is linked, it safely evaluates to an empty string `""` without raising exceptions.
2. **Execution Initialization State:**
   - Every execution initiated via API (`perform_create`) is forced into the initial status `PENDING`.
3. **Remote Execution Audit Trail:**
   - Script completion updates `completed_at`, terminal status (`SUCCESS` or `FAILED`), and persists the full `output_log` for operational auditing and debugging.
4. **Burn-on-Read & Single-Use Semantics:**
   - Download tokens can only be fetched once. The endpoint `GET /api/scripts/download/{token}/` invokes `.burn()` immediately upon the first successful retrieval before returning the `.rsc` file.
   - Subsequent retrieval attempts (or requests after `expires_at`) immediately return `HTTP 410 Gone` with code `"token_invalid_or_expired"`.
5. **Flash Storage Self-Destruction:**
   - Because sensitive configuration files (e.g., WireGuard keys, system passwords) reside in plain text on RouterOS flash storage when downloaded via `/tool fetch`, scripts generated with `include_cleanup=True` append a delayed file deletion command to ensure the temporary file is wiped from disk after execution.

---

## 3. Endpoints Catalog

| Method | Path | Permission | Description |
|---|---|---|---|
| `GET` | `/api/scripts/templates/` | `IsAuthenticated` | Lists available script templates. |
| `GET` | `/api/scripts/templates/{id}/` | `IsAuthenticated` | Retrieves Jinja2 source of a specific template. |
| `GET` | `/api/scripts/executions/` | `IsAuthenticated` | History of script executions filtered by router. |
| `POST` | `/api/scripts/executions/` | `IsAuthenticated` | Dispatches a new execution initialized as `PENDING`. |
| `GET` | `/api/scripts/executions/{id}/`| `IsAuthenticated` | Retrieves output logs and execution status. |
| `POST` | `/api/scripts/executions/{id}/generate-token/` | `IsRouterOwner` | Generates single-use download token and RouterOS fetch command for an execution. |
| `GET` | `/api/scripts/download/{token}/` | `AllowAny` (Public) | Downloads `.rsc` script and burns token immediately (Burn-on-Read, returns `HTTP 410` on reuse). |

---

## 4. Test Traceability

| Test Sub-Domain | File | Key Scenarios Verified |
|---|---|---|
| **Jinja2 Rendering** | [apps/scripts/tests/test_rendering.py](file:///home/carlos/Desktop/Personal/proyectos-personal/back_wifitickets/apps/scripts/tests/test_rendering.py) | Accurate variable substitution, safe handling of null template (`""`), missing variable interpolation. |
| **Download Tokens & Burn-on-Read** | [apps/scripts/tests/test_download_tokens.py](file:///home/carlos/Desktop/Personal/proyectos-personal/back_wifitickets/apps/scripts/tests/test_download_tokens.py) | Token validity, owner permission enforcement, single-use burn-on-read (410 on second access), expired token rejection, self-cleanup command injection in `.rsc`. |

