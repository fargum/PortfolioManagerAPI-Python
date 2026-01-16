# Architecture Notes & Design Rationale

This repository is part of a broader capstone project exploring the design of production-grade, AI-enabled backend services. The goal is not to demonstrate isolated techniques, but to show how modern AI components integrate cleanly into a real system with security, observability, and operational constraints.

What follows explains the why behind the main architectural decisions.

## High-Level Architecture

The system is structured as a layered FastAPI service:

**API layer**  
FastAPI endpoints, request/response schemas, authentication dependencies, streaming support.

**Service layer**  
Domain logic (portfolio, holdings, pricing, AI orchestration). This keeps business logic independent of HTTP and AI frameworks.

**Persistence layer**  
Async SQLAlchemy with PostgreSQL, Alembic migrations, and explicit session handling.

**AI / Agent layer**  
A LangGraph-based agent that uses tool calling to interact with the service layer rather than embedding business logic in prompts.

This separation allows the AI layer to be treated as optional and replaceable, rather than the centre of the application.

## Why FastAPI + Async SQLAlchemy

Async end-to-end allows the service to handle:

- streaming LLM responses
- concurrent tool calls
- non-blocking database access

SQLAlchemy is used explicitly (rather than ORMs hidden behind abstractions) to make data access and transaction boundaries clear.

The API can run fully without the AI layer configured, which keeps development, testing, and operations simple.

## Agent Design: LangGraph, Not "Prompt Soup"

The AI component is implemented as a tool-using agent using LangGraph rather than:

- ad-hoc prompt chaining, or
- embedding SQL / business logic directly into prompts.

**Key principles:**

**The agent does not own business logic**  
All portfolio and holdings logic lives in services that are also used by non-AI endpoints.

**Tools are constructed per request**  
Tools are created via factories with request-scoped dependencies (account ID, services), avoiding global mutable state and ensuring correct multi-tenant behaviour.

**Stateful but explicit memory**  
LangGraph state and a Postgres checkpointer are used to demonstrate how conversational memory can be persisted outside the model, rather than relying on hidden session state.

This mirrors how agents are deployed in production systems where correctness and isolation matter more than clever prompting.

## Security Model

- Authentication is handled via **Azure Entra ID** (OAuth2 / OIDC).
- Account identity is always derived server-side from the authenticated principal.
- The AI endpoints **do not accept account identifiers from the client**, preventing cross-account access via prompt or request manipulation.
- AI functionality is disabled cleanly when credentials are not configured, returning explicit HTTP errors rather than failing at startup.
- The design assumes a multi-tenant system, even though this project is primarily for demonstration.

## Observability & Telemetry

The service is instrumented with **OpenTelemetry** for:

- structured logging
- request traces
- custom spans around AI orchestration and tool execution

This was a deliberate choice to reflect real operational requirements:

- AI systems are probabilistic and harder to debug
- latency, cost, and failure modes matter
- visibility must be designed in from the start

Observability is treated as a first-class concern, not an afterthought.

## Why AI Is "Optional" in the Architecture

A key design goal was to avoid building an AI-shaped application.

Instead:

- the core API can run and serve data without any AI configuration
- AI endpoints are layered on top and can be enabled or disabled independently
- this mirrors how many organisations introduce AI incrementally into existing systems

This keeps the system testable, debuggable, and evolvable.

## Testing, Guardrails, and Evals

This repository focuses on architecture and correctness.

More advanced evaluation and guardrail strategies (prompt regression testing, output validation, cost controls) are implemented in a parallel C#/.NET version of the system and will be unified later.

The intent here is to demonstrate clean integration patterns, not to duplicate the same evaluation stack across languages.
