# Task List: User Management (CRUD)

**Specification:** `context/spec/005-user-management-crud/`

---

- [x] **Slice 1: Retrieve a single user by UUID with extended profile data**
  - [x] Add `first_name`, `last_name`, `phone_number`, `avatar_url`, `deleted_at` columns to the `User` ORM model in `src/app/models/user.py` **[Agent: postgres-database]**
  - [x] Create Alembic migration for the new columns **[Agent: postgres-database]**
  - [x] Create `UserProfileResponse` schema in `src/app/schemas/user.py` (no `cognito_sub`, includes profile fields + role as string) **[Agent: python-backend]**
  - [x] Modify `get_by_id()` in `UserRepository` to add `include_deleted` parameter with `WHERE deleted_at IS NULL` filter by default **[Agent: postgres-database]**
  - [x] Create `UserService` in `src/app/services/user_service.py` with `get_by_id()` method **[Agent: python-backend]**
  - [x] Create `users` router in `src/app/routers/users.py` with `GET /api/v1/users/{id}` endpoint **[Agent: python-backend]**
  - [x] Add `get_user_service` dependency to `src/app/core/dependencies.py` and include users router in `main.py` **[Agent: python-backend]**
  - [x] Write route-level tests for `GET /users/{id}`: valid UUID returns 200 with profile, non-existent UUID returns 404, invalid UUID returns 422 **[Agent: test-writer]**
  - [x] Verify: run `pytest` and confirm all tests pass; run the app and confirm `GET /api/v1/users/{id}` returns the extended profile **[Agent: python-backend]**

---

- [x] **Slice 2: Retrieve a user by email address (case-insensitive)**
  - [x] Modify `get_by_email()` in `UserRepository` to add `include_deleted` parameter and case-insensitive matching via `func.lower()` **[Agent: postgres-database]**
  - [x] Add `get_by_email()` method to `UserService` **[Agent: python-backend]**
  - [x] Add `GET /api/v1/users/by-email/{email}` endpoint to users router **[Agent: python-backend]**
  - [x] Write route-level tests: valid email returns 200, unknown email returns 404, case-insensitive matching works **[Agent: test-writer]**
  - [x] Verify: run `pytest` and confirm all tests pass **[Agent: python-backend]**

---

- [x] **Slice 3: List all users with offset/limit pagination**
  - [x] Create `PaginatedUserResponse` schema in `src/app/schemas/user.py` **[Agent: python-backend]**
  - [x] Add `list_users(offset, limit, include_deleted)` method to `UserRepository` with total count **[Agent: postgres-database]**
  - [x] Add `list_users()` method to `UserService` **[Agent: python-backend]**
  - [x] Add `GET /api/v1/users` endpoint to users router with `offset`, `limit` query params (defaults: 0, 20; max limit: 100) **[Agent: python-backend]**
  - [x] Write route-level tests: default pagination returns items/total/offset/limit, custom offset/limit work, unauthenticated returns 401 **[Agent: test-writer]**
  - [x] Verify: run `pytest` and confirm all tests pass **[Agent: python-backend]**

---

- [x] **Slice 4: Authenticated user can update their own profile (name, phone, avatar)**
  - [x] Create `UserUpdateRequest` schema in `src/app/schemas/user.py` with E.164 regex validation for `phone_number` and URL validation for `avatar_url` **[Agent: python-backend]**
  - [x] Add `update(user, **fields)` method to `UserRepository` **[Agent: postgres-database]**
  - [x] Add `update_user()` method to `UserService` with self-only permission check (non-admin can only update own profile, cannot set `email` or `role_id`) **[Agent: python-backend]**
  - [x] Add `PATCH /api/v1/users/{id}` endpoint to users router **[Agent: python-backend]**
  - [x] Write route-level tests: self-update returns 200 with updated profile, updating another user returns 403, invalid phone returns 422, invalid avatar_url returns 422, sending `email` field returns 403, soft-deleted user returns 404 **[Agent: test-writer]**
  - [x] Verify: run `pytest` and confirm all tests pass **[Agent: python-backend]**

---

- [x] **Slice 5: Admin users can update any profile and view soft-deleted users**
  - [x] Add `require_role()` factory dependency to `src/app/core/dependencies.py` — returns a dependency that checks `user.role.name` against provided roles, raises 403 if no match **[Agent: auth-security]**
  - [x] Extend `update_user()` in `UserService` to allow admins to update any user's profile including `role_id` **[Agent: python-backend]**
  - [x] Add `include_deleted` query param support to `GET /users/{id}`, `GET /users/by-email/{email}`, and `GET /users` — enforce admin-only at service layer **[Agent: python-backend]**
  - [x] Write route-level tests: admin can update another user, admin can pass `include_deleted=true`, non-admin `include_deleted` is silently ignored, `require_role` returns 403 for wrong role **[Agent: test-writer]**
  - [x] Verify: run `pytest` and confirm all tests pass **[Agent: python-backend]**

---

- [x] **Slice 6: Admin can soft-delete a user, disabling their Cognito account and blocking login**
  - [x] Add `admin_disable_user(cognito_sub)` method to `CognitoService` using boto3 `AdminDisableUser` wrapped in `asyncio.to_thread()` **[Agent: auth-security]**
  - [x] Add `soft_delete(user)` method to `UserRepository` **[Agent: postgres-database]**
  - [x] Add `delete_user()` method to `UserService` — admin-only enforcement, soft-delete in DB, disable Cognito account, optionally revoke Redis tokens **[Agent: python-backend]**
  - [x] Add `DELETE /api/v1/users/{id}` endpoint to users router with `Depends(require_role("admin"))`, returns 204 **[Agent: python-backend]**
  - [x] Update `get_current_user` dependency in `src/app/core/dependencies.py` to reject tokens for users where `deleted_at IS NOT NULL` **[Agent: auth-security]**
  - [x] Write route-level tests: admin delete returns 204, non-admin returns 403, already-deleted returns 404, deleted user's token is rejected by `get_current_user`, deleted user excluded from GET endpoints **[Agent: test-writer]**
  - [x] Verify: run full `pytest` suite to ensure no regressions across all slices **[Agent: python-backend]**
