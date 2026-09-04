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

---

## 2. Invariants & Business Rules

1. **Deterministic Script Rendering:**
   - When a template is associated, `rendered_content` renders the string using `Template(content).render(**variables_used)`.
   - If no template is linked, it safely evaluates to an empty string `""` without raising exceptions.
2. **Execution Initialization State:**
   - Every execution initiated via API (`perform_create`) is forced into the initial status `PENDING`.
3. **Remote Execution Audit Trail:**
   - Script completion updates `completed_at`, terminal status (`SUCCESS` or `FAILED`), and persists the full `output_log` for operational auditing and debugging.

---

## 3. Endpoints Catalog

| Method | Path | Permission | Description |
|---|---|---|---|
| `GET` | `/api/scripts/templates/` | `IsAuthenticated` | Lists available script templates. |
| `GET` | `/api/scripts/templates/{id}/` | `IsAuthenticated` | Retrieves Jinja2 source of a specific template. |
| `GET` | `/api/scripts/executions/` | `IsAuthenticated` | History of script executions filtered by router. |
| `POST` | `/api/scripts/executions/` | `IsAuthenticated` | Dispatches a new execution initialized as `PENDING`. |
| `GET` | `/api/scripts/executions/{id}/`| `IsAuthenticated` | Retrieves output logs and execution status. |

---

## 4. Test Traceability

| Test Sub-Domain | File | Key Scenarios Verified |
|---|---|---|
| **Jinja2 Rendering** | [apps/scripts/tests/test_rendering.py](file:///home/carlos/Desktop/Personal/proyectos-personal/back_wifitickets/apps/scripts/tests/test_rendering.py) | Accurate variable substitution, safe handling of null template (`""`), missing variable interpolation. |
