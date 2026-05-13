# Deferred Items — Phase 11

## Pre-existing test pollution (NOT introduced by 11-01)

Running the full unit suite produces 9–13 pre-existing failures in
`tests/unit/test_agents_registry.py`. The failures are caused by another test
that sets `AGENT_OVERRIDES_FILEPATH` (pointing to `overrides/openai.json`) and
does not restore the env in teardown — subsequent registry tests then see the
openai override values instead of the registry defaults.

Reproduced with `git stash` (no Phase 11 changes applied):
- 13 failures
With Phase 11-01 changes applied:
- 9 failures (Phase 11-01 changes did NOT introduce new failures; the count drop
  is incidental — different test ordering).

Resolution: out of scope for Plan 11-01 (test-only, pre-existing). Belongs in
a separate maintenance quick-task or in Plan 11-02/03 if the same test ordering
issue blocks them.

## Database-dependent unit tests

`tests/test_db_models.py`, `tests/test_gateway.py`, `tests/test_workflow_runner.py`,
`tests/test_workflows.py`, `tests/test_jobs.py` require Postgres running locally.
The worktree environment does not have docker-compose running. These tests are
skipped during Plan 11-01 verification — they do not exercise the LLM adapter or
AgentConfig surface that this plan changes.
