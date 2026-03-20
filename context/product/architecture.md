# System Architecture Overview: Python Auth Microservice

---

## 1. Application & Technology Stack

- **Language:** Python 3.11+
- **Backend Framework:** FastAPI (async, high-performance REST API)
- **Data Validation & Settings:** Pydantic v2 (schemas, request/response models, environment config via Pydantic Settings)
- **ORM:** SQLAlchemy 2.0 (async mode)
- **Database Migrations:** Alembic
- **Async DB Driver:** asyncpg

---

## 2. Data & Persistence

- **Primary Database:** PostgreSQL (relational storage for users and roles)
- **Tables:**
  - `roles` — UUID pk, name (unique), description (nullable), created_at
  - `users` — UUID pk, email (unique), cognito_sub (unique), role_id (FK → roles), created_at, updated_at
- **Relationships:** One role → many users
- **Connection Management:** SQLAlchemy async engine with asyncpg driver, connection pooling

---

## 3. Infrastructure & Deployment

- **Cloud Provider:** AWS
- **Containerization:** Docker
- **Hosting Environment:** AWS ECS Fargate (serverless containers)
- **IaC:** Deferred — to be decided in a later phase
- **CI/CD:** To be defined (GitHub Actions, AWS CodePipeline, or similar)

---

## 4. External Services & APIs

- **Authentication Provider:** AWS Cognito (user registration, login, token issuance)
- **Cognito SDK:** boto3 (official AWS SDK for Python)
- **JWT Verification:** python-jose + Cognito JWKS (local token verification using Cognito's public keys — no network call per request)
- **Token Flow:** Cognito issues JWT tokens (access, id, refresh) → service verifies locally via JWKS endpoint

---

## 5. Observability & Monitoring

- **Logging:** ELK Stack (Elasticsearch + Logstash + Kibana) — centralized log aggregation, search, and analysis
- **Metrics & Dashboards:** Grafana + Prometheus — metrics collection and visualization
- **Application Logging:** Python structlog (structured JSON logs for ELK ingestion)
