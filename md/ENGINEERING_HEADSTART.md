# Jainune v2 engineering headstart

Review date: 2026-10-02. Purpose: capture reusable architecture, defensive coding, cross-layer correctness, and regression practices for future projects. This is a sampled source review, not a certification of security or production readiness.

## Review narrative and status

The user requested learning the engineering approach rather than the product or every source line. Infigraph tools were searched for but are unavailable in this chat. The review therefore uses local documentation and source. Prior Infigraph narrative was read from `.infigraph/sessions/session_2026-10-02.md`; its reported test results and fixes are historical context, not new verification. The existing modification to `backend/app/routers/auth.py` belongs to the working tree and is being preserved.

Initial inventory identifies an Expo/React Native TypeScript client, a FastAPI modular backend, asyncpg/PostgreSQL migrations, Redis coordination, Cloudflare API/media proxies, background jobs, and extensive domain-specific hardening tests. Documents emphasize contract drift, temporal ordering, distributed state, and tracing failures across components. Current source and tests take precedence over architectural aspirations and historical claims.

The first traced flows establish useful patterns: JWT validation is followed by a database account-status check; refresh tokens rotate under a database row lock with a bounded concurrency grace period and durable revocation records; payment fulfillment verifies provider status, price, currency and intent state under locks; message deduplication has a database uniqueness constraint; signed avatar uploads have owner-scoped intents and confirmation checks. These are implementation observations, not proof that all edge cases are closed.

Further review found that live WebSocket delivery and task execution are now process-local, despite older Redis pub/sub and Celery descriptions. Both Render and Docker start with one worker. Browser token storage is localStorage. These deployment assumptions and tradeoffs must accompany any reuse. Backend functions include several 250–338-line orchestration methods; module organization is useful, but security complexity has accumulated within individual functions.

Validation: all 62 backend application Python files parsed successfully with AST. TypeScript checking passed. All 13 focused mobile/Cloudflare tests passed after disabling Node test process isolation to avoid the sandbox's child-process restriction. The backend unit suite reported **516 passed, 2 skipped, 1 setup error** in 71.43 seconds. The setup error was a Windows permission denial in pytest's default temporary directory for `test_load_fcm_from_file_path`; retrying that test with a fresh workspace temp directory also hit a permission denial. There were no assertion failures in the completed unit tests. Coverage enforcement was disabled for this review run, and real database integration, native builds, penetration and load tests were not run. The interpreter was local Python 3.14, while deployment configs use 3.11/3.12.

Only this learning document and a local continuity note were authored during the review. The working tree also contains changes to `backend/app/routers/auth.py` and `docs/LOGICAL_CORRECTNESS.md` from outside this review; they were preserved. This is a working-tree sample rather than an immutable release audit.

## Architecture learned from the implementation

The current application is a modular monolith. Domain routers cover authentication, users/onboarding, discovery, interactions, chat, media, payments, moderation/admin and related concerns. Services contain reusable domain/integration logic; `core` contains infrastructure, configuration, security, task supervision, errors and observability. Pydantic schemas define request and response boundaries. Separation is present at the module level, but routers still contain considerable domain orchestration and SQL; this is not a uniformly thin-controller architecture.

```text
Expo / React Native client and web PWA
  screens, navigation, Zustand stores, hooks
    -> domain API adapters -> shared Axios client
      -> configured HTTPS API endpoint / optional Cloudflare API Worker
        -> optional edge-origin gate, body limits, CORS, security headers
          -> FastAPI dependencies and domain routers
            -> services -> asyncpg / PostgreSQL
                       -> Redis or process-local fallback
                       -> provider APIs, storage, push notifications

Chat: REST persists messages -> in-process ConnectionManager -> WebSockets
Media: backend signs owner-scoped upload -> client uploads to Storage
       -> backend confirms object -> supervised moderation -> status polling
Jobs: lifespan maintenance loop + tracked asyncio background tasks
```

The Cloudflare API Worker removes spoofable forwarding/origin headers and supplies its private origin secret. The backend only trusts forwarded IPs when the shared secret matches. The gate is configurable: having the code or secret configured does not prove direct-origin access is blocked in the deployment. The photo Worker has a deliberately narrower role: allowed avatar paths and query parameters, WebP response checks and a streamed size cap.

Clients use the backend for application-table access. Migration 0033 removes Data API privileges for selected sensitive/legacy tables and uses a security-invoker profile view. Backend PostgreSQL authorization still matters because its privileged connection is not equivalent to a client's RLS-constrained request. Presence of RLS migrations alone is not evidence of the deployed roles or grants.

Both `render.yaml` and the Docker entrypoint use one Uvicorn worker. The current socket manager and task supervisor rely on that process model. Old pub/sub protocol comments, the retained Celery compatibility file and broad scaling claims in documents must not override this implementation evidence.

## Frontend/backend contracts

| Boundary | Observed implementation | Reusable lesson |
|---|---|---|
| HTTP transport | Shared client attaches tokens, adds timeouts, serializes concurrent refresh attempts and maps friendly errors | Centralize transport policy while preserving domain-specific authorization on the server |
| Response shape | `ok`/`err` envelopes coexist with typed/raw responses; client normalizes responses and domain adapters map fields | Make producer/consumer contracts explicit; compatibility adapters need behavioral tests |
| Token lifecycle | Native SecureStore, browser localStorage, client refresh queue, backend rotation and reuse records | Treat storage, retries, rotation, logout and account state as one lifecycle |
| Message send | Client supplies idempotency identity; server uses `(chat_id, sender_id, idempotency_key)` uniqueness | A retry key must survive the entire request and map to one committed effect |
| Real-time chat | Short-lived tickets, participant checks, socket rate/heartbeat controls, REST history/delta recovery | Live events complement persistent state; reconnect must reconcile against durable history |
| Local caches | Profile/feed keys include account identity; unknown account has no shared cache key; conversation caches use chat identity | Scope private caches by their access context and test account switches and delayed responses |
| Discovery caches | Cached candidates are revalidated against current visibility, block and interaction state | A cached identifier is not a continuing authorization grant |
| Media upload | Server-created intent and signed URL, direct upload, server confirmation and asynchronous moderation | Client transformations improve UX/resource use; server confirmation enforces trust boundaries |

## Defensive patterns worth carrying forward

1. **Authenticate identity, then authorize current state and the specific resource.** JWT verification fixes algorithm, issuer, audience and required claims. `get_current_user` checks the database for missing, deleted, banned and suspended accounts. Admin access looks up roles server-side; superadmin operations have a separate dependency. Chat access checks participants and bilateral blocks. Authentication alone does not authorize a supplied object ID.
2. **Use cryptography at secret boundaries.** OTPs use secure randomness and peppered HMAC storage; refresh tokens use high-entropy randomness and hashed database identities; signatures and origin secrets use constant-time comparisons. Production configuration rejects several missing/default credentials. A named helper or comment is not enough: inspect its caller and configured inputs.
3. **Make concurrency invariants durable.** Payment fulfillment locks the intent and user state; reciprocal interactions lock user pairs in a canonical order; messages have a database uniqueness constraint; workers use Redis ownership tokens and database maintenance leases. Application prechecks improve error handling, but the shared database must settle contested effects.
4. **Reason about temporal order.** Payment cache invalidation happens after the transaction commits. Notification code distinguishes in-flight reservations from successful-delivery deduplication. Refresh rotation distinguishes benign concurrency within its grace window from later token reuse. Trace what persists if a process dies between each pair of operations.
5. **Bound adversarial work.** User/IP/subnet limits, maximum request/page/frame sizes, bounded notification concurrency, message-cache caps, deadlines and jittered retries are complementary resource controls. Limits must hold in fallback and multi-instance modes as well as the happy path.
6. **Make invalidation part of lifecycle design.** Account deletion, block/unmatch, subscription changes and media changes affect database state, Redis, cached client content, provider objects, notifications and sockets. List these effects before implementing a state transition. Record and recover incomplete external cleanup.
7. **Handle abuse as transformations and sequences.** Chat moderation normalizes Unicode and maps normalized spans back to original text; tests include invisibles, homoglyphs and adversarial formatting. Location logic checks plausibility as well as coordinates. Reports have duplicate and anti-abuse checks. Filters need false-positive and evasion cases, not just keyword examples.
8. **Preserve privacy through derived outputs.** Discovery removes internal scores, cached results are revalidated, push previews are masked according to privacy/preferences, and telemetry has redaction hooks. Verify serialized output and failure logs as well as stored records. Distance rounding/jitter is an implemented mitigation, not proof against all location inference.
9. **Design degraded mode explicitly.** The repository supplies Redis and provider fallbacks, delivery retries and offline UI behavior. Each fallback needs a stated guarantee: local rate limiting is not distributed rate limiting; cached UI availability is not server authorization; a secondary DSN is not automatically a safe writable primary.
10. **Connect fixes to a concrete regression.** Named hardening tests link the trigger, invariant and consequence. Some tests exercise real code with in-memory Redis or transpiled TypeScript; others inspect SQL strings or use mocks. Strongest evidence reproduces the old failure and checks observable behavior after the fix.

## Quality assessment and limits on reuse

The useful quality signal is substantial attention to failure paths and non-local contracts. There are explicit schemas, parameterized SQL, domain modules, targeted regressions, production configuration checks, privacy controls, and CI security/test stages. Tests cover negative states, cache failure, duplicate delivery and stale history, not only successful requests.

Maintainability is mixed. Several orchestration functions span roughly 250–338 lines; SQL, provider calls, cache handling and policy checks often live together. Frontend adapters use `any` and accept multiple representations. Production paths sometimes inspect connection capabilities in ways that also accommodate mocks. Broad exception handling provides availability but can obscure whether required security or cleanup actually succeeded. These are reasons to carry the invariants forward while simplifying their implementation in a new project.

Specific constraints recorded from source, without making unverified exploit claims:

- Browser tokens are in JavaScript-accessible localStorage; native SecureStore guarantees do not transfer to the PWA.
- Short-lived WebSocket tickets have atomic GETDEL/Lua paths, followed by a non-atomic get/delete fallback. Single-use semantics must be evaluated in that fallback as well.
- WebSockets validate origin host names rather than the full scheme/host/port origin, with localhost included. Carry the exact trust policy into a future design review.
- Live fan-out, presence, disconnect controls and many background tasks are process-local. Adding workers/replicas requires redesign of coordination and delivery guarantees.
- Tracked asyncio tasks are retained and drained at shutdown; they are not a durable job queue that survives a crash. Durable leases do not automatically make every task durable.
- Redis fallback state is local and temporary. Revocation, distributed quotas and locks require explicit restart/outage guarantees; PostgreSQL refresh-revocation records only cover the paths that consult them.
- The native `setCertificatePins` bridge explicitly does not configure runtime pins. Android XML covers named domains; a successful bridge call is not evidence of pinning for every configured API/Worker host. Client checks remain supplementary to server controls.
- Catching a database statement error inside a transaction is not sufficient evidence the transaction remains usable. Mock-based tests cannot establish real PostgreSQL abort/rollback behavior.
- There is startup schema DDL as well as migration history. Future projects need one understood schema ownership/versioning path and deployment checks against real database behavior.
- CI defines backend scans and tests and mobile type checking. Its mobile dependency audit is advisory (`continue-on-error`); the sampled CI file does not invoke the focused mobile/edge Node tests or the available mobile lint script. The SSH deployment workflow checks CI for its commit, while Render separately has automatic deployment configured. Do not describe every deployment path as sharing one enforced gate.
- Production document claims about capacity, cost, compliance, unbeatable anti-tampering and historical test totals are not independently verified by this review.

## Bug-fix and non-regression workflow for a future project

1. State the violated invariant in plain language: who can do what, which effect may happen once, what state must survive, or which output must remain private.
2. Trace **symptom -> trigger -> state transition -> root cause -> downstream consequence** across the producer and consumer. Include schema, client adapters, caches, jobs and deployment mode when relevant.
3. Reproduce the failure with a test that would fail on the original implementation. Add an adjacent valid case so the fix does not simply deny all requests.
4. Enumerate concurrency, timeout/retry, stale/absent/corrupt cache, provider outage, partial completion, restart and account-switch variants that apply to that invariant.
5. Fix the layer that owns the guarantee. Add database uniqueness/locking for contested durable effects; enforce resource ownership server-side; keep UX validation on the client as an additional layer.
6. Preserve response fields, cursor ordering, units, enum meanings and existing valid workflows. Explicitly handle compatibility rather than relying on silent defaults.
7. Check side effects and invalidation after commit. For external effects that need recovery, persist recovery state instead of relying solely on an in-memory callback.
8. Run the targeted regression, relevant domain tests, type/static checks, and broader suites appropriate to the blast radius. Use real PostgreSQL/Redis tests for database races, rollback and distributed semantics. Report what ran and what was simulated.
9. Record the invariant, evidence, deployment assumptions and remaining uncertainty. Count green tests as regression evidence, not as proof of exhaustive security.

The logical-correctness document contains valuable principles but some absolute wording needs interpretation. Avoid nested pool acquisitions and keep transactions short; multiple sequential acquisitions do not by themselves prove pool starvation. Canonical ordering reduces deadlocks only when all competing code follows compatible ordering. A database lease requires ownership/expiry reasoning; two locks alone do not prove split-brain is impossible. An invalidation attempt is not proof that all clients or external systems are synchronized.

## Headstart brief to use with another project

> Use Jainune's engineering approach as a starting point: map trust boundaries and state transitions before implementation; keep the server authoritative for identity, ownership, money and entitlements; define explicit producer/consumer contracts; protect contested effects with database invariants; make retries idempotent; revalidate cached private data; design outage, restart and concurrency behavior; bound resource use; connect bug fixes to meaningful regressions; and verify deployed controls rather than trusting comments. Keep the next project's implementation simpler where possible, and adapt to its threat model and deployment topology. Read this document before transferring a specific pattern.

This file is portable context. It does not automatically supply memory to unrelated future chats: explicitly point those chats at it, or copy it into the next project's engineering documentation.

## Source map

- Architecture/runtime: `backend/app/main.py`, `dependencies.py`, `core/database.py`, `core/redis.py`, `core/background_tasks.py`, `services/connection_manager.py`, `render.yaml`, `backend/Dockerfile`.
- Identity/abuse: `backend/app/core/security.py`, `core/bot_defense.py`, `core/config.py`, `routers/auth.py`, `models/schemas/auth.py`, `models/schemas/user.py`.
- Financial/concurrency: `backend/app/services/payment_service.py`, `routers/subscriptions.py`, `routers/interactions.py`, `workers/daily_compatible.py`.
- Privacy/content/lifecycle: `backend/app/routers/chats.py`, `routers/websockets.py`, `routers/media.py`, `services/core_people_finder.py`, `services/moderation.py`, `services/chat_safety_filter.py`, `services/location_verifier.py`, `services/dignity_engine.py`, `services/account_service.py`, `workers/notification_worker.py`, `core/sentry.py`.
- Client contracts: `mobile/src/api/client.ts`, `api/chatApi.ts`, `api/profileApi.ts`, `store/authStore.ts`, `hooks/useWebSocket.ts`, `utils/cache.ts`, `utils/secureStorage.web.ts`, `config/endpoints.ts`.
- Native/edge/data access: `mobile/src/security/`, Android security bridge and network XML, `cloudflare/*proxy.mjs`, migrations 0025/0029/0030/0032/0033.
- Regression/operations: `backend/tests/unit/`, sampled `backend/tests/integration/test_auth_pipeline.py`, `mobile/tests/`, `cloudflare/*test.mjs`, `backend/pytest.ini`, `.github/workflows/ci.yml`, `.github/workflows/deploy-prod.yml`, `docs/LOGICAL_CORRECTNESS.md` and prior Infigraph narrative.
