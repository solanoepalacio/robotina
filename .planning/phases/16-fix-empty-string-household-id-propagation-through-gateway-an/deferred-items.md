# Phase 16 Deferred Items

Pre-existing or out-of-scope discoveries that are NOT addressed by Phase 16 plans.
Each entry is logged per executor SCOPE BOUNDARY rule.

## test_send_message_persists assertion mismatch (discovered during 16-05)

- **File:** tests/test_gateway.py:127
- **Failure:** `assert result == "7777"` but `result` is `SendResult(message_id='7777')`
- **Discovered:** during plan 16-05 verification of handler.py changes
- **Caused by 16-05?** No — unrelated to HOUSEHOLD_ID. send_message return type evolved (probably Phase 6) but the test wasn't updated.
- **Action:** Out of scope for plan 16-05. Suggested follow-up: either update the test to compare `.message_id` or change send.py to return raw str.
