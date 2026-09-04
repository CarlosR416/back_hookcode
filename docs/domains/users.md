# Domain Specification: Users & Authentication

* **Module:** `apps.users`
* **API Prefix:** `/api/auth/`
* **Responsibility:** User account registration, profile management, password lifecycle, JWT authentication, and Google Sign-In federation (via Firebase).

---

## 1. Data Models & Entities

### Model `User` ([apps/users/models.py](file:///home/carlos/Desktop/Personal/proyectos-personal/back_wifitickets/apps/users/models.py))
Extends Django's `AbstractUser` with the following customizations:
* **Primary Identifier:** `email` is unique and designated as `USERNAME_FIELD`.
* **Admin Compatibility:** `username` is preserved for compatibility with standard tooling and Django Admin.

---

## 2. Invariants & Business Rules

1. **Email Uniqueness:** Two accounts cannot share the same `email` address.
2. **Password Confirmation Enforcement:**
   - Both registration (`RegisterSerializer`) and password changes (`ChangePasswordSerializer`) strictly require matching `password` and `password_confirm` fields.
3. **Prior Password Verification on Change:**
   - `/api/auth/me/change-password/` validates that `old_password` matches the user's current password via `user.check_password()`.
   - On mismatch, it rejects the request with code `wrong_password` (HTTP 400).
4. **Automated User Provisioning via Google Sign-In:**
   - In `/api/auth/google/`, when a valid Firebase ID token is received, if the email does not exist in the database, a new user is created (`is_new_user = true`) with `user.set_unusable_password()`.
   - If the token lacks an email payload, the request is immediately rejected with code `missing_email` (HTTP 400).
   - In all valid cases, standard JWT keypairs (`access` and `refresh`) are issued.

---

## 3. Endpoints Catalog

| Method | Path | Permission | Description |
|---|---|---|---|
| `POST` | `/api/auth/register/` | `AllowAny` | Registers a new account. Returns 201 Created. |
| `POST` | `/api/auth/token/` | `AllowAny` | Obtains a JWT access/refresh token pair (SimpleJWT). |
| `POST` | `/api/auth/token/refresh/` | `AllowAny` | Refreshes an expired access token using a refresh token. |
| `GET` | `/api/auth/me/` | `IsAuthenticated` | Retrieves the profile of the authenticated user. |
| `PUT / PATCH` | `/api/auth/me/` | `IsAuthenticated` | Updates profile information for the authenticated user. |
| `POST` | `/api/auth/me/change-password/` | `IsAuthenticated` | Updates password with prior credential validation. |
| `POST` | `/api/auth/google/` | `AllowAny` | Authenticates / provisions users via Firebase ID token. |

---

## 4. Test Traceability

| Test Sub-Domain | File | Key Scenarios Verified |
|---|---|---|
| **Registration** | [apps/users/tests/test_registration.py](file:///home/carlos/Desktop/Personal/proyectos-personal/back_wifitickets/apps/users/tests/test_registration.py) | Successful user creation (201), password mismatch rejection, missing required fields. |
| **Password** | [apps/users/tests/test_password.py](file:///home/carlos/Desktop/Personal/proyectos-personal/back_wifitickets/apps/users/tests/test_password.py) | Successful password update, wrong old password rejection, mismatching confirmation. |
| **Google Auth** | [apps/users/tests/test_google_auth.py](file:///home/carlos/Desktop/Personal/proyectos-personal/back_wifitickets/apps/users/tests/test_google_auth.py) | New user provisioning, existing user login, missing email in token, invalid token rejection (401). |
| **Internationalization** | [apps/users/tests/test_i18n.py](file:///home/carlos/Desktop/Personal/proyectos-personal/back_wifitickets/apps/users/tests/test_i18n.py) | Spanish and English assertion of password mismatch, wrong password, and missing field errors. |
