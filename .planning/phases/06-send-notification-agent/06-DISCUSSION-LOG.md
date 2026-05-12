# Phase 6: send-notification Agent - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in CONTEXT.md — this log preserves the discussion.

**Date:** 2026-03-27
**Phase:** 06-send-notification-agent
**Mode:** discuss
**Areas discussed:** SendNotificationTool interface, Experiment inputs

## Gray Areas Presented

| Area | Selected for discussion |
|------|------------------------|
| format-telegram-message skill structure | No |
| SendNotificationTool interface | Yes |
| Experiment inputs | Yes |

## Discussions

### SendNotificationTool Interface

**Options presented:**
- **A (Recommended):** Constructor injection — `run_task()` builds `SendNotificationTool(chat_id, user_id, platform)` from `task_input`. Agent tool schema only accepts `formatted_text: str`.
- **B:** Agent provides all args — tool schema exposes `chat_id`, `platform`, `formatted_text`. Agent reads recipient info from user message.

**User decision:** Option A — constructor injection. Agent's sole job is formatting, not routing. Consistent with spec intent and `StartWorkflowTool` pattern.

### Experiment Inputs

**Options presented:** Short plain text, recipe added notification, bullet list, special chars stress test.

**User decision:** All four inputs. Each targets a distinct failure mode:
1. Short plain text → baseline happy path
2. Recipe notification → structured data formatting
3. Bullet list → list formatting
4. Special chars → MarkdownV2 escaping (highest risk failure mode)

## Skipped Areas (Claude's Discretion)

- **format-telegram-message skill structure** — sub-files, content depth, and structure left to Claude's discretion during planning/implementation.
