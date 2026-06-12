# Server Layout

```
server/
├── main.py                  # FastAPI app entrypoint + middleware
├── db.py                    # backwards-compat re-export of core.database
├── security_utils.py        # JWT + Fernet primitives (no FastAPI dep)
├── analyzer.py              # LLM analyzer + SSRF guard + URL builders
├── mailer.py                # SMTP helpers (OTP, reset, alert emails)
├── models_db.py             # SQLAlchemy ORM models (User, UserConfig,
│                            #   Log, AuthChallenge, AuditLog, RefreshToken)
├── models/                  # Pydantic schemas (request/response)
│   └── schemas.py
├── core/                    # framework-agnostic infrastructure
│   ├── config.py            # env-driven constants
│   ├── database.py          # engine, SessionLocal, Base, TimestampMixin,
│   │                        #   init_db, log writer, schema migrations
│   ├── exceptions.py        # DomainException hierarchy
│   ├── security.py          # JWT cookie helpers + require_auth_user
│   ├── refresh_tokens.py    # refresh-token issue/consume/revoke
│   ├── rbac.py              # Role enum + require_role factory
│   ├── rate_limiter.py      # in-memory rate-limit tracker
│   ├── state.py             # global app state (alert queue, etc.)
│   ├── websocket.py         # ConnectionManager
│   ├── llm_utils.py         # provider selection + system prompts
│   └── utils.py             # misc helpers
├── routers/                 # FastAPI routers (one per resource)
│   ├── auth_router.py
│   ├── alerts_router.py
│   ├── copilot_router.py
│   ├── llm_router.py
│   ├── user_router.py
│   ├── admin_router.py
│   ├── waf_router.py
│   ├── ...
├── services/                # business logic (called by routers)
│   ├── auth_service.py
│   ├── alert_service.py
│   ├── copilot_service.py
│   ├── user_service.py
│   ├── llm_service.py
│   ├── llm_providers.py     # LLM provider strategy pattern
│   ├── site_monitor_service.py
│   ├── audit_service.py
│   ├── challenge_service.py
│   └── ...
└── tests/                   # pytest suite + manual legacy scripts
```

## Why some files remain at the `server/` root

`db.py`, `analyzer.py`, `mailer.py`, `models_db.py`, `security_utils.py` are
intentionally kept at the package root rather than nested. They are widely
imported by both `core/` and `services/` modules, and moving them would
require updating 10+ import statements with no benefit to the call graph
(no module above or below depends on their location, only on the symbols
they expose).

If a future refactor wants to relocate them, the recommended targets are:

| Current | Target | Rationale |
|---------|--------|-----------|
| `analyzer.py` | `core/llm_analyzer.py` | LLM plumbing fits in `core/` |
| `mailer.py` | `services/mailer.py` | I/O adapter, like other services |
| `models_db.py` | `models/db.py` (next to `schemas.py`) | All ORM + pydantic together |
| `security_utils.py` | `core/jwt_fernet.py` | Pure crypto, fits in `core/` |
| `db.py` | _(delete)_ | Already a thin re-export |
