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

### Model `EmailVerificationCode` ([apps/users/models.py](file:///home/carlos/Desktop/Personal/proyectos-personal/back_wifitickets/apps/users/models.py))
* **Responsibility:** Stores and tracks 6-digit numeric OTP verification codes sent via email.
* **Fields:**
  - `user`: Foreign key to `User` (`related_name="verification_codes"`).
  - `code`: 6-digit numeric string (`secrets.randbelow(900000) + 100000`).
  - `created_at`: Timestamp of creation.
  - `expires_at`: Expiration timestamp (`now + 15 minutes`).
  - `attempts`: Counter tracking failed submission attempts (max 5).
  - `is_used`: Boolean flag marking whether the code has been consumed.

---

## 2. Invariants & Business Rules

1. **Email Uniqueness:** Two accounts cannot share the same `email` address.
2. **Simplified User Registration:**
   - Standard user registration requires only `email`, `first_name`, `last_name`, `password`, and `password_confirm`.
   - Both `first_name` and `last_name` are mandatory fields.
   - The backend automatically assigns the `email` value to the internal `username` field, removing the need for users to enter a separate username.
3. **Mandatory Post-Registration Email Verification (6-Digit OTP):**
   - New standard registrations are created with `is_active = False`.
   - An automated 6-digit numeric OTP code is generated and dispatched to the user's email via **Brevo SMTP Relay**.
   - Until the OTP code is submitted to `/api/auth/verify-otp/`, the user cannot authenticate via `/api/auth/token/`.
4. **OTP Security & Anti-Brute-Force Rules:**
   - **Expiration:** Codes expire after 15 minutes (`EMAIL_OTP_EXPIRATION_MINUTES`).
   - **Attempt Limit:** A maximum of 5 failed attempts are allowed before the code is locked (`too_many_attempts`).
   - **Resend Cooldown:** Users must wait at least 60 seconds (`EMAIL_OTP_RESEND_COOLDOWN_SECONDS`) between resend requests to protect SMTP quotas.
   - **Immediate Session Initiation:** Upon successful OTP verification, the user account is activated (`is_active = True`) and a fresh JWT keypair (`access` and `refresh`) is issued immediately.
5. **Password Confirmation Enforcement:**
   - Both registration (`RegisterSerializer`) and password changes (`ChangePasswordSerializer`) strictly require matching `password` and `password_confirm` fields.
6. **Prior Password Verification on Change:**
   - `/api/auth/me/change-password/` validates that `old_password` matches the user's current password via `user.check_password()`.
   - On mismatch, it rejects the request with code `wrong_password` (HTTP 400).
7. **Automated User Provisioning via Google Sign-In:**
   - In `/api/auth/google/`, when a valid Firebase ID token is received, if the email does not exist in the database, a new user is created (`is_new_user = true`) with `is_active = True` (pre-verified by Google) and `user.set_unusable_password()`.
   - If the token lacks an email payload, the request is immediately rejected with code `missing_email` (HTTP 400).
   - In all valid cases, standard JWT keypairs (`access` and `refresh`) are issued.

---

## 3. Endpoints Catalog

| Method | Path | Permission | Description |
|---|---|---|---|
| `POST` | `/api/auth/register/` | `AllowAny` | Registers a new account as unverified. Dispatches 6-digit OTP. Returns 201 Created. |
| `POST` | `/api/auth/verify-otp/` | `AllowAny` | Verifies 6-digit OTP code, activates user, and returns JWT tokens. |
| `POST` | `/api/auth/resend-otp/` | `AllowAny` | Resends a fresh 6-digit OTP code (with 60s cooldown). |
| `POST` | `/api/auth/token/` | `AllowAny` | Obtains a JWT access/refresh token pair (SimpleJWT, active accounts only). |
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
| **Email Verification** | [apps/users/tests/test_email_verification.py](file:///home/carlos/Desktop/Personal/proyectos-personal/back_wifitickets/apps/users/tests/test_email_verification.py) | Registration sets `is_active=False` & sends email, correct OTP activates user and returns JWT, invalid code attempts, max attempts lockout, expired code, resend cooldown, nonexistent email handling. |
| **Password** | [apps/users/tests/test_password.py](file:///home/carlos/Desktop/Personal/proyectos-personal/back_wifitickets/apps/users/tests/test_password.py) | Successful password update, wrong old password rejection, mismatching confirmation. |
| **Google Auth** | [apps/users/tests/test_google_auth.py](file:///home/carlos/Desktop/Personal/proyectos-personal/back_wifitickets/apps/users/tests/test_google_auth.py) | New user provisioning, existing user login, missing email in token, invalid token rejection (401). |
| **Internationalization** | [apps/users/tests/test_i18n.py](file:///home/carlos/Desktop/Personal/proyectos-personal/back_wifitickets/apps/users/tests/test_i18n.py) | Spanish and English assertion of password mismatch, wrong password, and missing field errors. |
