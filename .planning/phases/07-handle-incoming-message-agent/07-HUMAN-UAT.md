---
status: partial
phase: 07-handle-incoming-message-agent
source: [07-VERIFICATION.md]
started: 2026-03-27T00:00:00Z
updated: 2026-03-27T00:00:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. Direct reply path
expected: Send "What recipes do we have?" to the bot; bot queries household-manager API and returns a readable answer in Telegram
result: [pending]

### 2. Workflow initiation path
expected: Send "Add a recipe for chocolate cake"; a WorkflowRun job appears in RQ Dashboard, no immediate Telegram reply sent
result: [pending]

### 3. Auth hard-error path
expected: Set invalid HOUSEHOLD_MANAGER_API_KEY; job lands in FailedJobRegistry with RuntimeError trace visible in LangWatch
result: [pending]

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps
