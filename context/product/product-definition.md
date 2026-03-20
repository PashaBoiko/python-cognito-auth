# Product Definition: Python Auth Microservice

- **Version:** 1.0
- **Status:** Proposed

---

## 1. The Big Picture (The "Why")

### 1.1. Project Vision & Purpose

To provide a production-ready, standalone authentication microservice that handles user identity management and Cognito-based authentication — decoupled from authorization and business logic — so that consuming services can rely on a single, trusted source for user storage, registration, login, and token verification.

### 1.2. Target Audience

- **End users** who interact with registration, login, and account management flows through client applications that consume this service.
- **Internal development teams** who integrate this microservice into a larger system architecture for centralized authentication.

### 1.3. User Personas

- **Persona 1: "Alex the App User"**
  - **Role:** End user of a client application backed by this auth service.
  - **Goal:** Wants to quickly sign up, log in, and have a secure session without friction.
  - **Frustration:** Slow or unreliable authentication flows, confusing error messages during registration or login.

- **Persona 2: "Jordan the Backend Developer"**
  - **Role:** Developer on a consuming service team.
  - **Goal:** Needs to verify tokens, look up users by email or ID, and assign roles via a clean, well-documented API.
  - **Frustration:** Unclear API contracts, lack of proper error codes, or tightly coupled auth logic that's hard to integrate.

### 1.4. Success Metrics

- **Reliability:** 99.9%+ uptime on all auth endpoints with low error rates.
- **Security:** Zero authentication bypasses; all tokens properly validated through Cognito; passing security audits.
- **Performance:** Sub-200ms response times on auth endpoints; efficient async database queries; minimal Cognito latency overhead.
- **Operational:** Successful containerized deployment on AWS ECS/Fargate with health checks and graceful error handling.

---

## 2. The Product Experience (The "What")

### 2.1. Core Features

- **User Registration** — Sign up via AWS Cognito, then store the user record (email, cognito_sub, role) in PostgreSQL.
- **User Login** — Authenticate through Cognito and return JWT tokens.
- **Token Verification** — Validate Cognito-issued JWT tokens via a dedicated endpoint and middleware.
- **User Lookup** — Retrieve users by internal UUID or by email address.
- **Role Management** — Create and list roles; assign roles to users via a foreign key relationship.
- **Cognito-to-Internal User Mapping** — Map Cognito `sub` identifiers to internal user records.

### 2.2. User Journey

1. A new user submits their email and password to `POST /auth/signup`.
2. The service registers the user in AWS Cognito and stores the resulting `cognito_sub`, email, and default role in PostgreSQL.
3. The user logs in via `POST /auth/login`, receiving JWT tokens (access, id, refresh) from Cognito.
4. Subsequent requests from client apps include the JWT in the Authorization header; the Cognito token verification middleware validates it on every request.
5. Consuming services call `GET /users/{id}` or `GET /users/by-email/{email}` to retrieve user details.
6. Admins create roles via `POST /roles` and assign them to users as needed.

---

## 3. Project Boundaries

### 3.1. What's In-Scope for this Version

- User registration and storage (Cognito + PostgreSQL).
- User login via Cognito with JWT token issuance.
- Token verification endpoint and middleware.
- User retrieval by UUID and by email.
- Role CRUD (create and list) with user-role assignment.
- Clean architecture with layer separation (routers, services, repositories, models).
- Tech stack: Python, FastAPI, PostgreSQL, AWS Cognito, SQLAlchemy 2.0, Alembic, Pydantic.
- Async database support with UUID primary keys.
- Environment configuration via Pydantic Settings.
- Containerized deployment targeting AWS ECS / Fargate.

### 3.2. What's Out-of-Scope (Non-Goals)

- Authorization logic (RBAC enforcement, permission checks) — consuming services handle this.
- Business logic beyond user storage and authentication.
- Password reset / forgot password flows.
- Multi-factor authentication (MFA).
- OAuth2 social login providers (Google, GitHub, etc.).
- Admin UI or frontend.
- Rate limiting and API gateway concerns (handled at infrastructure level).
- Multi-tenancy support.
- Mobile SDK or client libraries.
