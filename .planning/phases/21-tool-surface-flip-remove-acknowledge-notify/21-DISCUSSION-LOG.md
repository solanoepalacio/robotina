# Phase 21 Discussion Log

**Mode:** `--auto` (system reminder; user AFK). No interactive AskUserQuestion turns. 25 D-NN decisions captured in `21-CONTEXT.md`.

## Gray Areas Resolved (auto-mode)

1. **RespondTool delivery path** — sync Telegram vs queue-hop. **D-01:** queue-hop via send-notification at_front=True. PITFALL 13 mandates it.
2. **RespondTool terminality** — non-terminal. **D-01.** `return_direct=False` so the agent can call `start-workflow` after.
3. **TerminateTool shape** — args, return_direct, what it returns. **D-02:** no args, return_direct=True, sentinel return.
4. **StartWorkflowTool schema** — `{workflow_type, input}` per call. **D-03.** Keeps `Literal["add-recipe"]` for now (Phase 23 extends).
5. **Removal scope** — single PR (acknowledge + notify + overrides + workflow step). **D-06.** PITFALL 10 mandates lockstep.
6. **send-notification task_type** — KEEP (RespondTool uses it). **D-07.** Subtle; planner mustn't conflate with workflow step.
7. **Dead-letter block disposition** — DELETE (Phase 20 kept as fallback; Phase 21 supersedes). **D-08.**
8. **Prompt versioning** — V005 (V004 retained for rollback). **D-09 / D-10.**
9. **V005 multi-recipe scope** — minimal in V005, full in V006 (Phase 22). **D-09.** Keeps smoke focused on tool-surface correctness.
10. **Dashboard label map placement** — Jinja-side (preserves module-isolation). **D-11.** Initial Spanish labels listed; no entries for acknowledge/notify.
11. **AGENT_REGISTRY ↔ overrides CI guard** — pytest parametrized test. **D-12.** Future-drift gate.
12. **Smoke set sizing + structure** — 5-8 utterances covering 1 single + 2 multi + 1 compound + 1 ambiguous + 1 over-cap. **D-13 / D-14.**
13. **Pivot path** — single-call list-form `start-workflow(actions=[...])` if OpenAI staging fails. **D-15.**
14. **No automated multi-call harness** — manual operator smoke per EVAL-01. **D-16.**
15. **Test coverage** — unit (RespondTool, TerminateTool, StartWorkflowTool refactor), integration (run_task tool injection), registry tests, label tests, repo grep gate. **D-17..D-25.**

## Flagged for User Review (Claude's-discretion calls)

- **D-08 (delete dead-letter block):** Phase 20 D-05 kept it as fallback. Phase 21 deletes it now that wake-respond works. If the user wants more conservative behavior (keep dead-letter for one more milestone as belt-and-suspenders), redirect.
- **D-09 V005 keeps single-recipe focus in examples:** could include multi-recipe examples now (BATCH lands in Phase 22 anyway). Decision keeps the smoke checkpoint scoped to tool-surface, not LLM behavior.
- **D-11 dashboard label map location:** Jinja-side macro vs Python-side dict in dashboard/queries.py. Decision keeps it Jinja-side for module-isolation purity. If the user prefers Python-side (more testable, more refactorable), redirect.
- **D-15 pivot path:** EVAL-03 says to pivot to list-form BEFORE merge if OpenAI staging fails. Decision keeps this as an automatic pivot path the executor follows; if the user wants to stop the autonomous run and pivot manually, redirect.
- **D-23 repo grep gate:** included as a verify step in the deletion plan, NOT as a permanent test. If the user wants it as a permanent CI test, the test would need to be added to D-12's parametrized suite. Decision keeps it as a one-shot pre-merge gate to avoid permanent test brittleness around future legitimate references (changelogs, etc.).

---

*All decisions in `21-CONTEXT.md`. This log is the rationale + open-loops record.*
