# Milestones

## v1.0 — MVP (Shipped: 2026-05-18)

**Delivered:** Robotina v1.0 ships an end-to-end Telegram → AI agent → household-manager pipeline. A family member sends a natural-language message in Spanish; Robotina routes it, runs a multi-step workflow if needed, and replies in Spanish — with the gold path being "add a recipe by name" working through research → load → notify, in production, on a single sequential RQ worker with full LangWatch observability.

**Scope:** 18 phases (1–16 + decimal 07.1, backlog 999.1 deferred), 70 plans, 426 commits over ~55 days (2026-03-24 → 2026-05-18). 3,990 LOC `src/` Python across 32 files, 5,742 LOC tests across 38 files.

### Key Accomplishments

1. **Telegram → workflow gold path in production** — Phase 7 routing agent decides direct-reply vs. workflow start; `add-recipe` runs ack → 4-step research → load → notify entirely in Spanish, returning a recipe slug + link to the household-manager backend (Phases 6–9).
2. **Modern LangChain 1.x agent stack** — `langchain.agents.create_agent` everywhere across 3 LLMBackend adapters (Ollama / Anthropic / OpenAI), with `response_format=PydanticModel` structurally eliminating the canelones-class prose-wrapped-JSON parse failures, and middleware-based instrumentation (`@before_model`/`@after_model`/`@wrap_model_call`) replacing legacy callbacks (Phases 10–12).
3. **Sequential single-worker queue with no lost tasks** — Postgres + Redis (AOF `appendfsync always`) + RQ 2.5 native scheduler, with `WorkflowRun`/`WorkflowRunStep` lifecycle management and pre-assigned job IDs for transactional advancement (Phases 2, 5).
4. **Self-hosted queue visibility dashboard** — Independent FastAPI + Jinja2 + HTMX read-only debugger over `WorkflowRunStep` rows including persisted `step_input` and `failure_reason`; module-level grep gate prevents cross-imports (Phase 13).
5. **4-layer `household_id` validation** — Gateway boot `sys.exit(1)`, `NonEmptyHouseholdId` on 7 task-input Pydantic models, tool-constructor validation, and `queue_workflow` pre-DB guard — eliminating the empty-string silent-failure mode that was producing confusing 4xx responses from the backend (Phase 16).
6. **Pipeline-grade recipe ingestion** — Single growing `RecipeData` artifact accumulated through 4 sub-agents (gather/instructions/ingredients/metadata), with food/unit name resolution done inline via batched-LLM semantic match against the household catalog and a `recipe-load` agent that resolves to backend IDs and POSTs the final recipe (Phases 8, 9, 15).

### Production-Verified Behavior

Real-use Telegram traffic continuously through Phases 7–16 has exercised: routing, multi-step workflows, the full add-recipe pipeline, Spanish notifications with app-link, gateway boot-time validation, and the dashboard for post-hoc inspection. UAT items in Phases 6 / 7 / 8 / 9 that required live-service confirmation were verified through this real-use stream (see each phase's `*-UAT.md` / `*-VERIFICATION.md` for closure notes recorded during the v1.0 wrap-up).

### Decimal Phases

- **Phase 07.1** — Deterministic agent termination (`return_direct=True` on terminal tools), inserted after Phase 7 to fix a routing-agent issue where the LLM sometimes called both `queue` and `start-workflow` in the same turn.

### Known Deferred (Backlog)

- **Phase 999.1** — Custom `AgentState` schemas for `reply_context` + `household_id`. Promote when 3+ tools need ambient context or when a future phase wants middleware that reads typed state.
- **Shared-link recipe ingestion** — User shares a URL ("agregá esta receta: <link>"). Will land in milestone v1.1 alongside related recipe-input modalities. `recipe-scrapers>=15.11.0` is already declared in `pyproject.toml` (added Phase 8, unused) ready for adoption.

### Architecture Decisions Validated

- Centralized task-runner orchestrates workflows; agents know nothing about sequence.
- `reply_context` lives in `WorkflowRun.shared_context`, never in intermediate task inputs.
- `RecipeData` uses human-readable food/unit names; resolution is the loader's job.
- Skills use lazy loading (index pre-loaded; sub-files on demand).
- `langchain.agents.create_agent` is the agent factory (Phase 10 migration completed; `create_react_agent` retired).

### Open Doc Debt

- `REQUIREMENTS.md` traceability table at v1.0 close tracked 82 v1 requirements through Phase 13 (DASH-09). Phases 14–16 delivered against ROADMAP success criteria without minting new REQ-IDs — a documentation slip carried into the archive. Future milestones should mint new REQ-IDs per phase OR formalize ROADMAP-success-criteria-as-requirements.

### Archived Artifacts

- `.planning/milestones/v1.0-ROADMAP.md` — full phase detail at close
- `.planning/milestones/v1.0-REQUIREMENTS.md` — 82 v1 requirements + traceability
