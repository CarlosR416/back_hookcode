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
* **Email Verification Status:** `is_email_verified` (boolean, defaults to `False`). Discouples email confirmation state from general account enablement (`is_active`), allowing accounts to be suspended or managed by administrators independently of email confirmation.

### Model `EmailVerificationCode` ([apps/users/models.py](file:///home/carlos/Desktop/Personal/proyectos-personal/back_wifitickets/apps/users/models.py))
* **Responsibility:** Stores and tracks 6-digit numeric OTP verification codes sent via email.
* **Fields:**
  - `user`: Foreign key to `User` (`related_name="verification_codes"`).
  - `code`: 6-digit numeric string (`secrets.randbelow(900000) + 100000`).
  - `created_at`: Timestamp of creation.
  - `expires_at`: Expiration timestamp (`now + 15 minutes`).
  - `attempts`: Counter tracking failed submission attempts (max 5).
  - `is_used`: Boolean flag marking whether the code has been consumed.

### Model `PasswordResetCode` ([apps/users/models.py](file:///home/carlos/Desktop/Personal/proyectos-personal/back_wifitickets/apps/users/models.py))
* **Responsibility:** Stores and tracks temporary 6-digit numeric OTP codes sent via email specifically for password recovery.
* **Fields:**
  - `user`: Foreign key to `User` (`related_name="password_reset_codes"`).
  - `code`: 6-digit numeric string (`secrets.randbelow(900000) + 100000`).
  - `created_at`: Timestamp of creation.
  - `expires_at`: Expiration timestamp (`now + 15 minutes`).
  - `attempts`: Counter tracking failed submission attempts (max 5).
  - `is_used`: Boolean flag marking whether the code has been consumed.

---

## 2. Invariants & Business Rules

1. **Email Uniqueness & Re-Registration for Unconfirmed Accounts:**
   - Accounts with `is_email_verified = True` are strictly unique; attempting to register again with an already verified email returns `HTTP 400 Bad Request` (`"A user with that email address already exists."`).
   - If a registration is submitted for an existing email that was never verified (`is_email_verified = False`), the system avoids locking the user out: it allows the registration to proceed, replaces the pending account's profile details (`first_name`, `last_name`, and password), keeps `is_active = False` and `is_email_verified = False`, invalidates previous codes, and dispatches a fresh 6-digit OTP code (`HTTP 201 Created`).
2. **Simplified User Registration:**
   - Standard user registration requires only `email`, `first_name`, `last_name`, `password`, and `password_confirm`.
   - Both `first_name` and `last_name` are mandatory fields.
   - The backend automatically assigns the `email` value to the internal `username` field, removing the need for users to enter a separate username.
3. **Mandatory Post-Registration Email Verification (6-Digit OTP):**
   - New standard registrations are created with `is_active = False` and `is_email_verified = False`.
   - An automated 6-digit numeric OTP code is generated and dispatched to the user's email via **Brevo SMTP Relay**.
   - Until the OTP code is submitted to `/api/auth/verify-otp/`, the user cannot authenticate via `/api/auth/token/` (SimpleJWT responds with standard HTTP 401 Unauthorized for inactive accounts).
4. **OTP Security & Anti-Brute-Force Rules:**
   - **Expiration:** Codes expire after 15 minutes (`EMAIL_OTP_EXPIRATION_MINUTES`).
   - **Attempt Limit:** A maximum of 5 failed attempts are allowed before the code is locked (`too_many_attempts`).
   - **Resend Cooldown:** Users must wait at least 60 seconds (`EMAIL_OTP_RESEND_COOLDOWN_SECONDS`) between resend requests to protect SMTP quotas.
   - **Immediate Session Initiation:** Upon successful OTP verification, both `is_email_verified = True` and `is_active = True` are set, and a fresh JWT keypair (`access` and `refresh`) is issued immediately.
5. **Password Reset via 6-Digit OTP:**
   - **Endpoint 1 (Request):** `POST /api/auth/password-reset/request/` accepts an `email`.
     - *Anti-Enumeration:* If the email is not found, a generic success message is returned (`"If an account with that email exists, a password reset code has been sent."`) without revealing whether the email is registered.
     - *Rate Limiting:* A 60-second cooldown is enforced between consecutive reset requests for the same account.
     - *Dispatch:* Sends a 6-digit OTP code to the user's email using HookCode branded templates.
   - **Endpoint 2 (Confirm):** `POST /api/auth/password-reset/confirm/` accepts `email`, `otp`, `password`, and `password_confirm`.
     - Validates that passwords match and meet security requirements.
     - Verifies that the OTP is valid, unexpired, and has not exceeded 5 attempts.
     - Upon success, marks the OTP as used (`is_used = True`), updates the password with `user.set_password()`, and marks `is_email_verified = True` and `is_active = True`.
6. **Password Confirmation Enforcement:**
   - Registration (`RegisterSerializer`), password reset (`PasswordResetConfirmSerializer`), and in-place password change (`ChangePasswordSerializer`) strictly require matching `password` and `password_confirm` fields.
7. **Prior Password Verification on Change:**
   - `/api/auth/me/change-password/` validates that `old_password` matches the user's current password via `user.check_password()`.
   - On mismatch, it rejects the request with code `wrong_password` (HTTP 400).
8. **Automated User Provisioning via Google Sign-In:**
   - In `/api/auth/google/`, when a valid Firebase ID token is received, if the email does not exist in the database, a new user is created (`is_new_user = true`) with `is_active = True` and `is_email_verified = True` (pre-verified by Google) and `user.set_unusable_password()`.
   - If the user already exists but had `is_email_verified = False`, successful Google authentication marks `is_email_verified = True` and `is_active = True`.
   - If the token lacks an email payload, the request is immediately rejected with code `missing_email` (HTTP 400).
   - In all valid cases, standard JWT keypairs (`access` and `refresh`) are issued.

---

## 3. Endpoints Catalog

| Method | Path | Permission | Description |
|---|---|---|---|
| `POST` | `/api/auth/register/` | `AllowAny` | Registers a new account or replaces unverified registration details. Dispatches 6-digit OTP. Returns 201 Created. |
| `POST` | `/api/auth/verify-otp/` | `AllowAny` | Verifies 6-digit OTP code, activates user (`is_active=True`, `is_email_verified=True`), and returns JWT tokens. |
| `POST` | `/api/auth/resend-otp/` | `AllowAny` | Resends a fresh 6-digit OTP code for unverified accounts (with 60s cooldown). |
| `POST` | `/api/auth/password-reset/request/` | `AllowAny` | Requests a password reset OTP code. Protected by anti-enumeration and 60s cooldown. |
| `POST` | `/api/auth/password-reset/confirm/` | `AllowAny` | Verifies reset OTP, updates password, and activates verified status. |
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
| **Registration** | [apps/users/tests/test_registration.py](file:///home/carlos/Desktop/Personal/proyectos-personal/back_wifitickets/apps/users/tests/test_registration.py) | Successful user creation (201), re-registration replaces unconfirmed details (201), duplicate verified email rejection (400), password mismatch rejection, missing required fields. |
| **Email Verification** | [apps/users/tests/test_email_verification.py](file:///home/carlos/Desktop/Personal/proyectos-personal/back_wifitickets/apps/users/tests/test_email_verification.py) | Registration sets `is_active=False` & `is_email_verified=False` & sends email, correct OTP sets `is_active=True` & `is_email_verified=True` and returns JWT, already verified account rejection, invalid code attempts, max attempts lockout, expired code, resend cooldown, nonexistent email handling. |
| **Password Reset OTP** | [apps/users/tests/test_password_reset_otp.py](file:///home/carlos/Desktop/Personal/proyectos-personal/back_wifitickets/apps/users/tests/test_password_reset_otp.py) | Request creates OTP and dispatches email, nonexistent email anti-enumeration protection (200), 60s cooldown (429), confirm resets password and updates flags, invalid OTP increments attempts, max attempts lockout, expired code rejection, password mismatch validation. |
| **Password** | [apps/users/tests/test_password.py](file:///home/carlos/Desktop/Personal/proyectos-personal/back_wifitickets/apps/users/tests/test_password.py) | Successful password update, wrong old password rejection, mismatching confirmation. |
| **Google Auth** | [apps/users/tests/test_google_auth.py](file:///home/carlos/Desktop/Personal/proyectos-personal/back_wifitickets/apps/users/tests/test_google_auth.py) | New user provisioning, existing user login, missing email in token, invalid token rejection (401). |
| **Internationalization** | [apps/users/tests/test_i18n.py](file:///home/carlos/Desktop/Personal/proyectos-personal/back_wifitickets/apps/users/tests/test_i18n.py) | Spanish and English assertion of password mismatch, wrong password, and missing field errors. |

