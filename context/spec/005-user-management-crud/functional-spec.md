# Functional Specification: User Management (CRUD)

- **Roadmap Item:** User Lookup (Phase 3) — expanded to full User Management CRUD with extended profile data
- **Status:** Completed
- **Author:** Pavel Boiko

---

## 1. Overview and Rationale (The "Why")

Today, the auth microservice can register users and authenticate them, but consuming services and admins have no way to retrieve, update, or remove user profiles. Backend developers ("Jordan") need to look up users by ID or email to display user info, verify identities, or build admin tooling. End users ("Alex") expect to manage their own profile — update their name, phone number, or avatar — without friction.

This specification defines the full user management lifecycle: listing, retrieving, updating, and soft-deleting users, along with extending the user profile to include first name, last name, phone number, and avatar URL. User creation remains exclusively through the existing auth/signup flow.

**Success looks like:** Consuming services can reliably retrieve and manage user data through clean REST endpoints, and end users can update their own profile information.

---

## 2. Functional Requirements (The "What")

### 2.1. Extended Profile Data

The user profile will be extended with the following fields:
- **first_name** — optional, text, max 100 characters
- **last_name** — optional, text, max 100 characters
- **phone_number** — optional, E.164 international format (e.g., `+14155552671`), max 15 digits
- **avatar_url** — optional, valid URL string pointing to an externally hosted image (no file upload in this service)
- **deleted_at** — nullable timestamp, used for soft deletion

**Acceptance Criteria:**
- [x] The user record includes first_name, last_name, phone_number, avatar_url, and deleted_at fields.
- [x] phone_number is validated against E.164 format; invalid formats are rejected with a clear error message.
- [x] avatar_url is validated as a well-formed URL; invalid URLs are rejected.
- [x] All new fields are optional and default to null.

---

### 2.2. List Users — `GET /api/v1/users`

- **As a** consuming service or admin, **I want to** list all users with pagination, **so that** I can build admin dashboards or browse user records.
- Supports offset/limit pagination via query parameters (`offset`, `limit`).
- Soft-deleted users are **excluded** by default. Admins can pass `?include_deleted=true` to include them.
- Requires a valid JWT token (authenticated users only).

**Acceptance Criteria:**
- [x] `GET /api/v1/users` returns a paginated list of active users.
- [x] Response includes `items` (list of user objects), `total` (total count), `offset`, and `limit`.
- [x] Default pagination: `offset=0`, `limit=20`.
- [x] `?include_deleted=true` includes soft-deleted users in the response (with `deleted_at` visible).
- [x] Unauthenticated requests receive a `401 Unauthorized` response.

---

### 2.3. Get User by ID — `GET /api/v1/users/{id}`

- **As a** consuming service or authenticated user, **I want to** retrieve a user by their internal UUID, **so that** I can display their profile or verify their identity.
- Soft-deleted users are **excluded** by default. Admins can pass `?include_deleted=true`.
- Requires a valid JWT token.

**Acceptance Criteria:**
- [x] `GET /api/v1/users/{valid-uuid}` returns the user's full profile (id, email, first_name, last_name, phone_number, avatar_url, role, created_at, updated_at).
- [x] `GET /api/v1/users/{non-existent-uuid}` returns `404 Not Found` with message "User not found."
- [x] `GET /api/v1/users/{invalid-format}` returns `422 Unprocessable Entity`.
- [x] A soft-deleted user returns `404 Not Found` by default.
- [x] `cognito_sub` is **not** included in the response (internal implementation detail).

---

### 2.4. Get User by Email — `GET /api/v1/users/by-email/{email}`

- **As a** consuming service, **I want to** look up a user by their email address, **so that** I can map external identifiers to internal user records.
- Soft-deleted users are **excluded** by default.
- Requires a valid JWT token.

**Acceptance Criteria:**
- [x] `GET /api/v1/users/by-email/valid@example.com` returns the user's full profile.
- [x] `GET /api/v1/users/by-email/unknown@example.com` returns `404 Not Found` with message "User not found."
- [x] The email parameter is case-insensitive (looking up `User@Example.com` finds `user@example.com`).

---

### 2.5. Update User Profile — `PUT /api/v1/users/{id}`

- **As a** user, **I want to** update my profile information (name, phone, avatar), **so that** my profile stays current.
- **Self-update:** Authenticated users can update **their own** profile. Updatable fields: `first_name`, `last_name`, `phone_number`, `avatar_url`.
- **Admin-update:** Admin users can update **any** user's profile, including role assignment.
- Users **cannot** change their own `email` or `role`.
- Only provided fields are updated (partial update semantics).
- If a non-admin user attempts to update disallowed fields (`email`, `role`), the API returns `403 Forbidden` with a message listing which fields the user is not allowed to update.

**Acceptance Criteria:**
- [x] `PUT /api/v1/users/{own-id}` with valid fields updates the profile and returns the updated user.
- [x] `PUT /api/v1/users/{other-id}` by a non-admin user returns `403 Forbidden`.
- [x] Submitting an invalid phone_number returns `422` with message specifying E.164 format requirement.
- [x] Submitting an invalid avatar_url returns `422` with message specifying valid URL requirement.
- [x] A non-admin user attempting to update `email` or `role` receives `403 Forbidden` with a message listing the disallowed fields.
- [x] `updated_at` timestamp is refreshed on successful update.
- [x] Updating a soft-deleted user returns `404 Not Found`.

---

### 2.6. Delete User (Soft Delete) — `DELETE /api/v1/users/{id}`

- **As an** admin, **I want to** soft-delete a user, **so that** their account is deactivated but the record is preserved for auditing.
- Sets `deleted_at` to the current timestamp.
- Disables the corresponding Cognito account.
- Only admin users can perform this action.

**Acceptance Criteria:**
- [x] `DELETE /api/v1/users/{id}` by an admin sets `deleted_at` and disables the Cognito account, returns `204 No Content`.
- [x] `DELETE /api/v1/users/{id}` by a non-admin returns `403 Forbidden`.
- [x] Deleting an already-deleted user returns `404 Not Found`.
- [x] After deletion, the user cannot log in via the auth flow.
- [x] The deleted user no longer appears in GET responses (unless `?include_deleted=true`).

---

## 3. Scope and Boundaries

### In-Scope

- Extending the user model with first_name, last_name, phone_number, avatar_url, deleted_at.
- `GET /api/v1/users` — paginated user list.
- `GET /api/v1/users/{id}` — get user by UUID.
- `GET /api/v1/users/by-email/{email}` — get user by email.
- `PUT /api/v1/users/{id}` — update user profile (self + admin).
- `DELETE /api/v1/users/{id}` — soft delete user (admin only).
- E.164 phone number validation.
- URL validation for avatar_url.
- Soft-delete filtering on all GET endpoints.
- Database migration for new profile fields.

### Out-of-Scope

- **Role Management** (List Roles, Create Role, Role Assignment) — separate roadmap item.
- **File upload / image hosting** — avatar_url is a URL string only; image storage is external.
- **Email change flow** — would require Cognito email verification; deferred.
- **User search / filtering** — no full-text search or filtering by name/role on the list endpoint.
- **Hard delete** — no permanent record removal.
- **Authorization logic (RBAC enforcement)** — consuming services handle permission checks.
- **Password reset / forgot password flows.**
- **Multi-factor authentication (MFA).**
- **OAuth2 social login providers.**
- **Admin UI or frontend.**
