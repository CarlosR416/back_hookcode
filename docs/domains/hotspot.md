# Domain Specification: Hotspot & Captive Portals

* **Module:** `apps.hotspot`
* **API Prefix:** `/api/hotspot/`
* **Responsibility:** Synchronization of MikroTik hotspot profiles/users, real-time active session monitoring, and custom captive portal template authoring and bundle export.

---

## 1. Data Models & Entities

### A. Network Synchronization Models
* **`HotspotProfile`:** Local mirror of `/ip/hotspot/user/profile` in RouterOS (`rate_limit`, `session_timeout`, concurrency `shared_users`).
* **`HotspotUser`:** Local mirror of `/ip/hotspot/user` in RouterOS (`username`, `comment`, state `is_disabled`).

### B. Captive Portal Template Engine
* **`HotspotTemplate`:** Template metadata (name, `vendor` MikroTik/Cisco/Ubiquiti, `variables` JSON with branding, logo, colors).
* **`HotspotTemplateFile`:** Individual Jinja2 template files (`login.html`, `alogin.html`, `error.html`, CSS, JS).

---

## 2. Invariants & Security Rules

1. **Mandatory Router Query Parameter for Active Sessions:**
   - The `/api/hotspot/users/sessions/` endpoint queries real-time sessions from the MikroTik hardware.
   - Strictly requires the `?router=<id>` query parameter.
   - Missing query parameter results in `HTTP 400 Bad Request` with code `missing_param`:
     ```json
     {
       "error": {
         "code": "missing_param",
         "detail": "'router' query param is required."
       }
     }
     ```
2. **Strict Path Traversal Mitigation in Template Files:**
   - Filenames in `HotspotTemplateFile` (`filename`) are validated to prevent directory traversal vulnerabilities.
   - Any filename containing path separators (`/` or `\`, e.g., `../../etc/passwd`) is rejected at the serializer layer with HTTP 400 and localized error detail.
3. **Dual Rendering Modes:**
   - **Preview Mode (`preview`):** Renders the portal in the browser, injecting mock values for MikroTik vendor variables (such as `$(username)` or `$(link-login)`).
   - **Export Mode (`export`):** Produces a ready-to-deploy `.zip` archive structured for direct upload to `/flash/hotspot/` on the router.

---

## 3. Endpoints Catalog

| Method | Path | Permission | Description |
|---|---|---|---|
| `GET` | `/api/hotspot/profiles/` | `IsAuthenticated` | Lists hotspot user profiles per router. |
| `POST` | `/api/hotspot/profiles/sync/` | `IsAuthenticated` | Syncs user profiles from MikroTik hardware into local database. |
| `GET` | `/api/hotspot/users/` | `IsAuthenticated` | Lists local hotspot users. |
| `GET` | `/api/hotspot/users/sessions/?router={id}` | `IsAuthenticated` | Real-time query of active user sessions on the MikroTik router. |
| `GET` | `/api/hotspot/templates/` | `IsAuthenticated` | Lists registered captive portal templates. |
| `POST` | `/api/hotspot/templates/` | `IsAuthenticated` | Creates a captive portal template. |
| `POST` | `/api/hotspot/template-files/` | `IsAuthenticated` | Uploads template file with anti-path-traversal validation. |
| `GET` | `/api/hotspot/templates/{id}/preview/` | `IsAuthenticated` | Live browser preview of the captive portal. |
| `GET` | `/api/hotspot/templates/{id}/export/` | `IsAuthenticated` | Downloads ready-to-upload ZIP bundle for MikroTik. |

---

## 4. Test Traceability

| Test Sub-Domain | File | Key Scenarios Verified |
|---|---|---|
| **Active Sessions** | [apps/hotspot/tests/test_sessions.py](file:///home/carlos/Desktop/Personal/proyectos-personal/back_wifitickets/apps/hotspot/tests/test_sessions.py) | Rejection with 400 and `missing_param` when `?router=` is omitted. |
| **Templates & Files** | [apps/hotspot/tests/test_templates.py](file:///home/carlos/Desktop/Personal/proyectos-personal/back_wifitickets/apps/hotspot/tests/test_templates.py) | Successful template file creation, rejection of path traversal (`../../etc/passwd`). |
| **Internationalization** | [apps/hotspot/tests/test_i18n.py](file:///home/carlos/Desktop/Personal/proyectos-personal/back_wifitickets/apps/hotspot/tests/test_i18n.py) | Spanish and English assertion of missing parameter and path traversal error messages. |
