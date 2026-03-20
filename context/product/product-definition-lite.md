# Python Auth Microservice — Summary

## Vision

A production-ready, standalone authentication microservice for user identity management and Cognito-based authentication, decoupled from authorization and business logic.

## Target Audience

- End users interacting with registration and login flows.
- Internal development teams integrating centralized authentication.

## Tech Stack

Python | FastAPI | PostgreSQL | AWS Cognito | SQLAlchemy 2.0 | Alembic | Pydantic

## Core Features

- **User Registration** — Cognito signup + PostgreSQL user storage.
- **User Login** — Cognito authentication with JWT token issuance.
- **Token Verification** — Endpoint and middleware for Cognito JWT validation.
- **User Lookup** — Retrieve users by UUID or email.
- **Role Management** — Create, list, and assign roles.
- **Cognito Mapping** — Map Cognito `sub` to internal user records.

## Deployment

AWS ECS / Fargate (containerized).
