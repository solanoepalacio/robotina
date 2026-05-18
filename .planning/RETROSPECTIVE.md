# Robotina — Living Retrospective

A milestone-by-milestone record of what worked, what didn't, and the patterns each milestone surfaced. Append new sections at the top; preserve "Cross-Milestone Trends" at the bottom.

---

## Milestone: v1.0 — MVP

**Shipped:** 2026-05-18
**Phases:** 18 (1–16 + decimal 07.1, plus backlog 999.1 deferred) | **Plans:** 70 | **Commits:** 426 | **Days:** ~55 (2026-03-24 → 2026-05-18)

### What Was Built

An end-to-end Telegram → AI agent → household-manager backend pipeline. Family members send Spanish natural-language messages; a routing agent decides between direct reply and multi-step workflow. The flagship workflow `add-recipe` runs ack → 4-step research (gather/instructions/ingredients/metadata) → load → notify, returning a stored recipe with backend slug + app-link, fully in Spanish. The runtime is a single sequential RQ worker on Postgres + Redis with full LangWatch observability via middleware.

### What Worked

- **Phase-decimal insertion for urgent fixes.** Phase 07.1 (deterministic termination) was inserted cleanly mid-stream after Phase 7 surfaced the dual-tool-call issue. Clear sequencing semantics paid off.
- **Aggressive tech-stack migrations mid-milestone.** Phases 10–12 lifted the entire agent layer onto LangChain 1.x (`create_agent`), bound `response_format` schemas, and rewrote instrumentation as middleware — without losing prior functionality. Tight scoping per phase made each migration low-risk.
- **Single-artifact accumulation pattern (Phase 15).** Replacing N disjoint step-payloads with one growing `RecipeData` flowing through the pipeline simplified both agents and the validator gate; food/unit semantic match landed inline rather than as a stage of its own.
- **4-layer validation for empty `household_id` (Phase 16).** Gateway boot fail-fast + Pydantic alias + tool-constructor guards + queue pre-DB check. Defense-in-depth was the right framing; each layer catches a different failure mode.
- **Per-phase atomic plans + summaries.** The `plan → execute → SUMMARY` cycle held tight; commits stayed phase-scoped and reviewable.
- **Real-use validation as the default.** Several phases ended with "verified in real-use via Telegram traffic" rather than synthetic UAT — this is what mattered for an agent system. The v1.0 UAT close-out (Phases 6/7/8/9) was a docs-update against behavior already proven in production.

### What Was Inefficient

- **Stale UAT docs.** Phases 6, 7, 8, 9 had `human_needed` / `pending` UAT items that lingered for weeks past the work actually being validated in production. The audit-uat reporting eventually surfaced these all at once at milestone-close. Future milestones should run `/gsd:audit-uat` more frequently — at every phase boundary, not just at milestone wrap.
- **Quick-task status field omission.** 11 of 16 quick-task SUMMARY.md files were missing `status: complete` in frontmatter, causing the close audit to flag them as open. Fixed in bulk during wrap-up. Worth automating the frontmatter write in the quick-task workflow itself.
- **REQUIREMENTS.md traceability drift after Phase 13.** Phases 14, 15, 16 delivered against ROADMAP success criteria without minting new REQ-IDs in REQUIREMENTS.md. The traceability table stayed accurate for the 82 reqs it tracked, but the milestone shipped capability outside the table — a documentation slip noted in `MILESTONES.md > Open Doc Debt`.
- **Phase 17 added without scoping.** A user-story line ("recipe via shared link") was added to ROADMAP.md as Phase 17 without goal/requirements/canonical-refs; later removed during wrap-up to be reintroduced as a properly-scoped chunk of v1.1. Don't add phases to a roadmap unless they're scoped enough to plan.
- **`recipe-scrapers` dependency added but unused.** Pulled in during Phase 8 for an alternate ingestion path that didn't materialize. It's still in `pyproject.toml`, ready for v1.1's shared-link work — but a dependency that sits idle for two months is friction.

### Patterns Established

- **Schema-constrained agent output (`response_format=PydanticModel`).** The default since Phase 11 for any agent that produces an artifact. Free-text JSON parsing is the anti-pattern; structured output via the agent factory is the way.
- **Middleware over callbacks for instrumentation.** `@before_model` / `@after_model` / `@wrap_model_call` (Phase 12) replaces `langchain_core.callbacks`. Cleaner span correlation, fewer flaky tests.
- **Agents are sequence-agnostic; the workflow registry owns orchestration.** Held through 18 phases — never deviated. Workflows are defined in `src/robotina/agent/workflows.py`; agents don't import them.
- **Per-workflow ack agents** (Phase 07.1). When a routing agent needs to terminate, a dedicated workflow-start ack agent composes the user-facing acknowledgment so the router can emit a single terminating tool call.
- **Prompt skeleton** (Role / Inputs / Tools / Process / Rules / Output) standardized across all 7 active prompts (Phase 14). New agents adopt this skeleton by default.
- **Avoid premature abstraction** (memory rule `feedback_avoid_premature_abstraction`). 3 concrete duplicates threshold before generalizing. Held throughout — agents are concrete, not generic.

### Key Lessons

- **Real-use verification > synthetic UAT for agent systems.** Once a workflow runs in production daily, the synthetic experiment-script verification is mostly redundant — they verify the same wire of the same harness. Lean into production observability (LangWatch + dashboard) and dial down ceremony.
- **Documentation lags behavior.** When a behavior is rewritten (e.g. Phase 07.1 retiring `send-notification` as an LLM agent), every doc that references the old behavior is stale until someone touches it. Wrap-up sweeps caught most; a per-phase "what docs are now stale?" prompt would catch them faster.
- **Bulk frontmatter operations are cheap.** `gsd-tools frontmatter set` over a glob of 11 files takes seconds. Don't avoid touching old artifacts during wrap-up — fix them.
- **A roadmap entry is a commitment.** Adding Phase 17 prematurely produced a dangling line item. Treat ROADMAP.md as the project's published commitments; only put items there that are scoped to plan.

### Cost Observations

- Model mix not centrally tracked at v1.0. Production agents run on `gpt-oss:20b` via Ollama by default; experiments support Anthropic / OpenAI adapter swaps.
- Notable: structured-output (`response_format`) eliminated a class of retry/parse-fallback overhead that was previously paying for itself in tokens. Phase 11 likely paid back its migration cost within weeks.

### Carried Into v1.1

- Scheduler track (planned for v1.0, deferred): scheduled-tasks queue + worker, RQ cron / `enqueue_at`, scheduler tool, HTTP API.
- Shared-link recipe ingestion + related input modalities. `recipe-scrapers >=15.11.0` already installed.
- Phase 999.1 (custom `AgentState` schemas) remains in backlog with explicit promotion criteria.

---

## Cross-Milestone Trends

*Populated as additional milestones complete.*

| Milestone | Phases | Plans | Commits | Days | LOC src | LOC tests | Notable |
|-----------|--------|-------|---------|------|---------|-----------|---------|
| v1.0      | 18     | 70    | 426     | 55   | 3,990   | 5,742     | End-to-end add-recipe gold path in production |

### Recurring "What Worked"

- Phase-atomic plan/summary cycle (validated across all 18 v1.0 phases)
- LangWatch + middleware observability (Phase 12 onward)
- Real-use validation as the default test bar

### Recurring "What Was Inefficient"

- UAT doc lag — re-evaluate at v1.1 close to see if frequency change helped
- Roadmap entries added without scope — re-evaluate at v1.1 close
