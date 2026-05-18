# Pitfalls Research — Milestone v1.1 Workflows Abstraction Refinement

**Domain:** Python/LangChain agent + RQ workflow runner refactor + 3 new features (multi-recipe, URL ingestion, images)
**Researched:** 2026-05-18
**Confidence:** HIGH on architecture/refactor pitfalls (read the codebase directly); MEDIUM on LangChain 1.x `create_agent` post–`return_direct=False` behavior (verified via LangChain forum/docs but exact ToolNode parallelism semantics need a smoke test in Phase 02 before locking the prompt); MEDIUM-LOW on third-party library specifics (`recipe-scrapers` wild-mode failure surface, image-search provider quirks).

## Orientation

This milestone is a **substantive refactor of a working system**, not a greenfield build. The existing system has carefully-earned guarantees that the new design must preserve:

- **Transactional advancement** (D-07): job_id pre-assigned BEFORE commit, so a worker crash between commit and enqueue is recoverable. Any new "enqueue next Robotina invocation" path must follow the same rule.
- **AOF `appendfsync always` + `result_ttl=-1` / `failure_ttl=-1`**: no tasks lost on crash. The wake-rule enqueue must inherit these.
- **Concurrency=1 sequential worker**: removes most contention but does NOT remove the failed-registry / manual-retry path that this research must protect.
- **D-16 SPEC-locked `failure_reason` format**: `f"{type(exc).__name__}: {exc}"`. Any new fields on WorkflowRun must avoid silently leaking sensitive content (see WR-02 cap at 500 chars in `workflow_runner.py`).
- **Phase 11 structured output guarantee**: every artifact-producing agent has `response_format=PydanticModel`. The new `gather-from-url` and `recipe-image` steps must inherit this.
- **Phase 16 four-layer `household_id` validation**: gateway, Pydantic, tool constructor, `queue_workflow`. New entry points (RobotinaInvocation, `respond()` tool) need the same defense in depth.

Every pitfall below ties to one or more of these.

---

## Critical Pitfalls

### Pitfall 1: Wake-rule double-fire on the failed-registry / manual-retry path

**What goes wrong:**
The rule is "when all workflows linked to a `RobotinaInvocation` reach terminal status, enqueue the next Robotina invocation." Under concurrency=1, two workflows cannot finish at the same instant — but a workflow can transition to `FAILED` *and later* be manually requeued from RQ's `FailedJobRegistry` (the project's intentional retry path). The wake-check fires on the original failure transition (all-terminal = true, invocation N+1 enqueued). The manual retry then runs the step, eventually moves the workflow back to terminal, and re-fires the wake check → **invocation N+1 is enqueued a second time**. Robotina runs twice on stale outcome context, may double-respond to the user, may double-dispatch chained workflows.

A subtler variant: the same step can be retried directly (a developer requeues `run_task` without changing the WorkflowRun status). The completion hook fires `on_step_complete` again on a workflow that's already DONE, and if the all-terminal check is naive (`SELECT … WHERE NOT terminal`), it'll re-fire the wake.

**Why it happens:**
The mental model "concurrency=1 means no races" hides the fact that "terminal status" is not the same as "first time we observed all-terminal." Idempotency is not the worker's job — it's the wake-rule's.

**How to avoid:**
- Add a column on `RobotinaInvocation`: `wake_dispatched_at TIMESTAMPTZ NULL`. Wake logic is `UPDATE RobotinaInvocation SET wake_dispatched_at = NOW() WHERE id = :id AND wake_dispatched_at IS NULL RETURNING id` — wrapped in the same SQLAlchemy session/transaction that observes all-terminal. If the UPDATE affects 0 rows, the wake already fired; skip the enqueue. This is a Postgres-row-level guard, not an in-memory check — it survives worker crashes and double completions.
- Pre-assign the next invocation's `job_id` BEFORE commit (mirror D-07): write `RobotinaInvocation` row with `job_id` set, commit, then enqueue. If enqueue fails after commit, a startup reconciler can find rows with `wake_dispatched_at IS NOT NULL` but no matching RQ job and either re-enqueue or alert.
- Make `on_step_complete` and `on_step_failed` both call the same `_check_and_dispatch_wake(invocation_id, session)` helper. Currently `on_step_complete` only marks RUN done; `on_step_failed` only marks RUN failed. Both terminal transitions need the wake check, and the helper has to be ONE function so the guard is one place.

**Warning signs:**
- Dashboard shows two RobotinaInvocations with the same `triggered_by_completion_of` and back-to-back timestamps.
- User receives two replies for one batch.
- Manual retry of a failed workflow produces a "ghost" Robotina turn that responds to outcomes it has already seen.

**Phase to address:** RobotinaInvocation + wake-rule phase (early). The guard must land in the same PR as the wake-rule itself, not as a follow-up.

---

### Pitfall 2: Wake check runs against stale read inside a serializable race

**What goes wrong:**
Even within one process under concurrency=1, the SQL "are all sibling workflows terminal?" check can return the wrong answer if executed against a session view that hasn't observed the current step's own status write. The sequence:

1. `on_step_complete` writes `WorkflowRun.status = DONE` and `session.flush()`.
2. Wake check `SELECT COUNT(*) FROM workflow_run WHERE triggered_by_invocation_id = :id AND status NOT IN ('done', 'failed')` — must see the row we just flushed as DONE.

With SQLAlchemy 2.x default session behavior and the same session, this works. But if the wake check is factored into a separate function that opens its own `SessionLocal()` (a tempting symmetry with `StartWorkflowTool._run`), the new session can run before the outer transaction commits, miss the DONE row, count it as non-terminal, and skip the wake. Now the chain is stuck — no further Robotina invocation will ever fire because the next terminal transition isn't going to happen.

**Why it happens:**
The current codebase has a strong pattern of "open your own session" (StartWorkflowTool does it). Reusing that pattern for the wake check looks like consistency but is wrong here — the wake-check MUST be inside the same transaction that performed the terminal transition.

**How to avoid:**
- Wake check is a function that takes the **existing session** as an argument (mirror `queue_workflow(..., session)` in `workflow_runner.py`). Caller is the completion hook, which already has a session.
- Commit ONCE at the end of `on_step_complete` / `on_step_failed`, AFTER both the status write and the wake check + invocation enqueue.
- Write a regression test that uses `freezegun` or in-test mocks to verify the wake check observes the just-written status.

**Warning signs:**
- A chain hangs: Robotina dispatches 1 workflow, workflow completes successfully, but no further invocation fires.
- Logs show "Workflow complete" but no "Wake dispatched" line for that invocation.

**Phase to address:** Same phase as Pitfall 1 (RobotinaInvocation + wake-rule).

---

### Pitfall 3: Migration backfill of `WorkflowRun.conversation_id` is non-trivial — `shared_context.reply_context.chat_id` is per-platform

**What goes wrong:**
The migration plan says: "Backfill `conversation_id` for existing rows from `shared_context.reply_context.chat_id` + platform." That sounds clean, but:

1. `shared_context` is a JSON column — Alembic generates SQL, and JSON path extraction differs between dev/staging/prod Postgres versions and is verbose in raw SQL (`shared_context->'reply_context'->>'chat_id'`).
2. `Conversation` is keyed on `(platform, chat_id)`. If two `chat_id` values collide across platforms (unlikely but possible — Telegram chat_ids are large ints; the next platform might recycle smaller IDs), naive backfill creates orphan FKs.
3. The current codebase still has live `acknowledge-add-recipe` workflows that may be **in-flight** during deploy. Backfilling them mid-run will silently move them to a Conversation row that may not be the one the workflow originally targeted (because `Conversation.id` may have been recreated since).
4. Some pre-Phase-16 historical rows may have `household_id = ""` or `reply_context = {}` — backfill must handle these (skip with logging, not crash the migration).

**Why it happens:**
JSON-glue migrations look superficially like "just an UPDATE" but the data shape is heterogeneous over time. Phases 1–16 evolved `shared_context` schema implicitly; older rows may not match what the migration assumes.

**How to avoid:**
- Make the new FK columns NULLABLE on first migration. Backfill in a **separate data migration** (Alembic op or a one-off script), not in the schema migration. Schema-only migration runs in seconds; data migration can be replayed.
- Block deploy if `WORKFLOWS_IN_FLIGHT > 0`: a pre-deploy check that counts WorkflowRuns where `status IN ('pending', 'running')`. Wait for drain or fail loud.
- For unresolvable rows (no `reply_context` in `shared_context`, or platform+chat_id doesn't match any Conversation), insert a synthetic Conversation row OR leave `conversation_id NULL` and add a code path that tolerates NULL for historical-only reads.
- Test the migration against a snapshot of the staging DB before running on production. The `docker-compose.yml` Postgres makes this cheap.

**Warning signs:**
- Migration takes more than a few seconds (likely a JSON scan or missing index).
- Post-migration query for `SELECT COUNT(*) FROM workflow_run WHERE conversation_id IS NULL AND status = 'done'` returns > 0 (orphans).
- New code path that reads `WorkflowRun.conversation_id` crashes on a NULL it didn't expect.

**Phase to address:** Schema migration phase (first phase of the refactor — must precede new code that depends on FKs).

---

### Pitfall 4: `return_direct=True` removal lets LLM text leak into the assistant message

**What goes wrong:**
Currently `StartWorkflowTool.return_direct=True` makes the graph terminate the instant the tool runs — no further model call, no AI text rendered. With `return_direct` removed and N parallel `start-workflow` tool calls allowed, the LangChain 1.x `create_agent` ReAct loop continues until the model emits an AI message with NO tool calls — that final AI message's `content` becomes the "user-facing" output by default ([LangChain agents docs](https://docs.langchain.com/oss/python/langchain/agents)).

Robotina is now responsible for messaging via the **explicit `respond()` tool**. But:
- The LLM may emit a final text turn AFTER the `respond()` calls ("OK, I started 3 workflows") that the user never sees because we're not piping the final AI content anywhere — and we **shouldn't**, because we have explicit `respond()`. But if we ARE consuming `result["messages"][-1].content`, that text now leaks.
- Conversely, if Robotina mis-uses `terminate()` and never calls `respond()`, the user gets silence after a multi-recipe request because no agent message reached the gateway.

**Why it happens:**
The Phase 11 `_extract_task_output` path in `workflow_runner.py` already strictly rejects free-text final messages — but Robotina is the one agent without `response_format` bound (it's conversational, not artifact-producing). The current `handle-incoming-message` task type is the legacy free-text path that Phase 11 grandfathered (`expects_structured=False`). Once Robotina emits text post-tool-calls, that path silently consumes it.

**How to avoid:**
- Robotina's agent loop must NOT have its final AI message content forwarded to the user. Make `respond()` the **only** user-visible channel. The agent's final AI message (if any) is treated as internal scratchpad — log it for debugging, do not deliver it.
- Add an explicit `terminate()` tool (in the milestone description). Make it `return_direct=True` — that's the engine-enforced termination point. After `terminate()`, the loop ends; any text the model wrote in the same AI message as the `terminate()` call is ignored.
- Update the Robotina prompt's Output rule to: "All user-facing messages MUST go through `respond()`. After your last tool call, call `terminate()`. Do not write user-facing text in your final assistant message."
- Smoke test: invoke the agent with a prompt that tends to produce trailing text ("explain what you're doing"). Verify trailing text never reaches the user.

**Warning signs:**
- User receives a message they didn't expect, content matches Robotina's "thinking" tone.
- Telegram message appears AFTER the "all workflows done" reply.
- `respond()` tool call count != number of messages delivered to Telegram.

**Phase to address:** `respond()` + `terminate()` tools + Robotina prompt rewrite phase.

---

### Pitfall 5: `create_agent` does not let us disable parallel tool calls — multi `start-workflow` ordering is provider-dependent

**What goes wrong:**
Multi-recipe means Robotina is expected to emit N `start-workflow` tool calls per turn. LangChain's `create_agent` runs tools through `ToolNode`, which executes all tool calls in a single AI message either in parallel (where the model emitted parallel) or sequentially. **`create_agent` does NOT expose `parallel_tool_calls=False`** — there's an open issue ([langchain-ai/langchain#34010](https://github.com/langchain-ai/langchain/issues/34010)) and the workaround is to hand-build the agent with LangGraph, which would cost us the middleware (Phase 12) and `response_format` (Phase 11) wins.

Implications for us:
- If the provider emits parallel tool calls (OpenAI does by default; Anthropic does; Ollama varies), all N `start-workflow` invocations run concurrently from `ToolNode`'s perspective. Each opens its own `SessionLocal()` (see `StartWorkflowTool._run`) — so we get N concurrent Postgres transactions, N concurrent `queue.enqueue` calls.
- The new RobotinaInvocation row needs all N WorkflowRuns to point to it. If `respond()` creates the invocation lazily or if the linkage is "current invocation in a context var," concurrency inside the same Python process across tool calls can race.
- Ordering is not guaranteed. The workflows may not enqueue in user-uttered order. For Topic 1 (multi-recipe), this is acceptable; for any future "ordered batch" use case it's not.

**Why it happens:**
The shift from `return_direct=True` (one call, terminate) to "N calls, no termination" exposes `ToolNode`'s parallel execution semantics that the previous architecture hid.

**How to avoid:**
- **Make `StartWorkflowTool._run` idempotent and self-contained**: each call opens its own session, creates exactly one WorkflowRun, commits. Concurrent calls within the same turn are independent transactions on independent rows. This is already roughly what the code does — keep it that way and DO NOT add a "current invocation" mutable in the tool.
- The `RobotinaInvocation.id` MUST be passed into the tool at construction time (via the same path that injects `chat_id` / `household_id` today). Then it's a constructor field, not mutable shared state. The tool writes `workflow_run.triggered_by_invocation_id = self.invocation_id` — concurrent calls all use the same constant.
- If strict ordering of WorkflowRun rows ever matters (it doesn't for V1), wrap the N enqueues in a sequential loop by binding the provider parameter at the provider-adapter level (e.g. ChatOpenAI accepts `parallel_tool_calls=False` in `bind_tools`). This is a per-adapter customization, not a `create_agent` change.
- Smoke test specifically the Ollama backend (used in development per CLAUDE.md): small local models are notably worse at emitting multiple coherent tool calls. Acceptance criterion: the dev backend can reliably do 3 recipes.

**Warning signs:**
- N user-uttered recipes → fewer than N WorkflowRuns created.
- WorkflowRuns created with `triggered_by_invocation_id` pointing to wrong invocation (off-by-one if there's mutable shared state).
- Intermittent test failures when running multi-recipe scenarios — classic race smell.

**Phase to address:** `StartWorkflowTool` schema + injection refactor phase.

---

### Pitfall 6: SSRF and resource-exhaustion via user-supplied URL — `recipe-scrapers` doesn't fetch, *we* do

**What goes wrong:**
`recipe-scrapers` is **HTML-parser only** ([recipe-scrapers docs](https://docs.recipe-scrapers.com/)). The fetch is our code. A user pastes:
- `http://169.254.169.254/latest/meta-data/...` — AWS instance metadata (if Robotina ever runs on EC2/ECS). Returns IAM creds.
- `http://localhost:6379/...` — direct Redis access. Could exfiltrate other users' tasks or run commands.
- `http://postgres:5432/...` — Compose-internal DB. Less exploitable but still wrong.
- `http://[::1]/admin` — IPv6 loopback bypass.
- `https://example.com/recipe` that 302s to `http://169.254.169.254/...` — redirect-chain SSRF.
- A 5 GB HTML file — content-length bomb if we don't cap.
- `application/octet-stream` declaring itself HTML in the body — content-type spoofing.
- `gzip` bomb (Content-Encoding: gzip with 100:1 ratio expanding past memory).
- Slow-read attack: server trickles bytes, holding our worker for minutes (concurrency=1 = total queue freeze).

The dev environment runs `agent/gateway` on the host with Postgres/Redis in Docker (per memory `project_local_dev_setup.md`), so `localhost` exposure is real. Staging is containerized but on a shared network with backend services.

**Why it happens:**
"Just fetch the URL the user gave us" looks one-line. The defenses are dozens of lines.

**How to avoid:**
A `safe_fetch(url)` helper in a single module, used by `gather-from-url` and `recipe-image` (the only two places we follow user-controlled URLs):
- **Scheme allowlist:** `https` only (or `http` only on explicit override flag for testing). Reject everything else.
- **DNS resolve and IP check BEFORE the HTTP call:** resolve hostname, reject if any A/AAAA record is in RFC1918 (`10.0.0.0/8`, `172.16/12`, `192.168/16`), loopback (`127/8`, `::1`), link-local (`169.254/16`, `fe80::/10`), IPv4-mapped IPv6, `0.0.0.0`, multicast. Python: `ipaddress.ip_address(socket.gethostbyname(host)).is_private` etc.
- **Disable redirects OR re-validate after each redirect:** `httpx.get(url, follow_redirects=False)`. If 3xx, re-run the IP check on the Location, then manually re-issue, cap at 3 hops.
- **Caps:** `timeout=httpx.Timeout(connect=5, read=15, write=5, pool=5)`, `httpx.AsyncClient(limits=httpx.Limits(max_connections=2))`. Cap response: stream with `iter_bytes(chunk_size)` and abort if accumulated bytes > 5 MB. Reject `Content-Length` headers > 10 MB up front.
- **Decompression cap:** if response is gzip/br, decompress incrementally with size cap; reject if ratio > 20:1.
- **Content-Type sniff:** require `text/html` or `application/xhtml+xml` for `gather-from-url`. For images, require `image/*` AND verify magic bytes (PIL can open the first KB or use `imghdr`).
- **No DNS rebinding window:** `httpx` re-resolves per call by default. If we ever pin the address, do `socket.getaddrinfo` → connect by IP → set `Host:` header — kills rebinding.

**Warning signs:**
- A URL submission produces a response that resembles cloud-metadata JSON.
- Worker hangs >60s on a single workflow.
- Memory spike during a single `gather-from-url`.

**Phase to address:** `gather-from-url` step phase (this is the FIRST line of code that should land in that phase — the safe-fetch helper must precede the parser integration). Same helper is reused in `recipe-image`.

---

### Pitfall 7: `recipe-scrapers` failure modes — silent partial extraction

**What goes wrong:**
The library covers ~300 supported sites well; `wild_mode=True` falls back to schema.org/Recipe JSON-LD for unsupported sites. Failure modes:

- **Site supported but page is a category/listing**, not a recipe: scraper returns mostly empty / raises `ElementNotFoundInHtml` for some fields, succeeds for others. We get a `RecipeData` with title="Cooking Tips" and `ingredients=[]`. Looks valid; isn't.
- **Site supported but unit and quantity formats are locale-specific** (Spanish-language sites, fractional Unicode like "½ taza"). The scraper may return raw strings that the downstream `validate-units` tool can't match.
- **Site supported but old scraper hasn't been updated** since the site redesigned. Scraper silently extracts wrong field (e.g. comments labelled as ingredients). Hard to detect.
- **`wild_mode=True` for an unsupported site:** schema.org/Recipe absent → raises `WebsiteNotImplementedError`. Caught by us, but no fallback yet.
- **Per-method exceptions:** `scrape_me(url).title()` raises if no title element. `.ingredients()` raises if it can't find the block. We must individually try/except each field — partial scrape is preferable to all-or-nothing rejection.

**Why it happens:**
A scraping library inherits the entropy of the open web. The library does its job — we still own validating the extraction.

**How to avoid:**
- Wrap each field call in try/except, accumulate into a partial dict, then run **the same `RecipeData` Pydantic schema validation** the LLM-based path runs. If validation fails (e.g. `len(ingredients) < 2`), fall back to the LLM-extraction path: pass the raw HTML (or a content-extracted plain-text version via `trafilatura` or `readability-lxml`) to an LLM step. The LLM path is the long-tail safety net.
- For the LLM fallback, REUSE the existing recipe-research pipeline contract (`RecipeData` output) — don't invent a new schema. The downstream steps (instructions/ingredients/metadata) should not need to know whether the source was scraper or LLM.
- Eval the parser against a held-out set of 10-20 known-good URLs (Spanish + English; popular recipe sites + long-tail). Track field-level success rate, not page-level.
- Always preserve the source URL in `RecipeData` (or on `WorkflowRun.outcome`) — debugging the wrong-field case requires re-fetching.

**Warning signs:**
- Workflow succeeds, recipe is saved, but the user sees obviously wrong title or ingredients.
- High proportion of `gather-from-url` workflows that pass the scraper but produce `RecipeData` with empty ingredients (silent partial).
- A specific domain accounts for repeated quality complaints.

**Phase to address:** `gather-from-url` step phase. Eval-set creation belongs in the same phase (the experiment script for `gather-from-url` should be the eval harness from day one).

---

### Pitfall 8: Recipe-image source returns the wrong dish

**What goes wrong:**
Web image search for "carbonara" returns ~50% pasta-with-cream-and-mushrooms (the Americanized variant), 20% the actual carbonara, 15% pasta-of-some-other-kind, and 15% random kitchen photos. Saved alongside the recipe, the wrong image becomes the recipe's identity in the household UI. Worse cases:

- Generic search returns stock-photo with watermark.
- Image is NSFW (rare for food searches but possible — image search APIs do leak).
- Image is a thumbnail (250px wide); usable on a list but ugly on a detail screen.
- Image URL becomes a 404 in 6 months (link rot is endemic on aggregator sites).
- Image is hot-linked from a site that enforces `Referer:` checks and returns a different image when fetched from our domain.
- Image is copyrighted; saving the source URL is a passive "we link to your hosted file" — saving a downloaded copy may be infringement depending on jurisdiction.

The milestone description leans web-image-search for V1, with storage URL-vs-rehost as an open question.

**Why it happens:**
"Get an image for X" is one of those tasks where the LLM/search returns a plausible-looking result that humans only validate by gut. There's no built-in semantic check.

**How to avoid:**
- **Pick a search API with a content filter knob and Spanish-language coverage** (Bing Image Search → being deprecated; Google Custom Search; SerpAPI; Tavily already in stack but image search is limited). Verify with safe-search ON. For V1, leaning Tavily for stack consistency unless its image coverage is poor; verify empirically.
- **Validation step inside the `recipe-image` task itself:** after picking a candidate URL, fetch the image, send it to a vision-capable LLM with the recipe name + ingredients list and a yes/no prompt: "Does this image plausibly depict {recipe_name}? Reply YES or NO with one-sentence rationale." If NO, try the next candidate. Cap at 3 candidates; if all fail, the workflow completes WITHOUT an image — that's the non-fatal failure mode the milestone description allows.
- **Rehost to the household-manager backend** if it has image-storage support; if not, store the source URL but add a periodic broken-link sweep (deferred to scheduler milestone). Document this as a known v1.1 gap.
- **Strip EXIF before storing.** EXIF often contains GPS coords for amateur photos.
- **Fetch with the same `safe_fetch` helper** from Pitfall 6 — image URLs are also user-influenced (via search result). The SSRF rules apply.
- **Magic-byte validation:** open with PIL `Image.open(BytesIO(content)).verify()` and assert format in `{JPEG, PNG, WEBP}`. Reject SVG (XSS via embedded scripts).

**Warning signs:**
- User complaint: "this isn't the right dish."
- High proportion of saved recipes share the same generic stock image.
- Image URLs all point to the same domain (search bias toward one source).

**Phase to address:** `recipe-image` step phase.

---

### Pitfall 9: Robotina context bloat as invocation chain grows

**What goes wrong:**
The whole point of `WorkflowRun.outcome` (compact) is to let the next Robotina invocation see "what happened" without re-ingesting the full pipeline artifacts. But:

- A developer writes the outcome field in the recipe-load step as `outcome = {"recipe": recipe_data.model_dump()}` for "completeness." `recipe_data` is the full RecipeData (instructions, all ingredients, image URL, metadata). Across a 3-recipe batch, the next Robotina turn sees 3 × full RecipeData = potentially 5-20 KB of structured text. Fine for one batch; a chained set of 5 batches over a long conversation, ingesting prior history, blows past the context window.
- The conversation history (`StoredMessage`) is loaded in full per Robotina invocation today. As a household uses Robotina for months, this grows unbounded. Phase 4 / current code likely doesn't truncate.
- `WorkflowRun.outcome` schema is JSON, no Pydantic class enforces compactness.

**Why it happens:**
Compactness is a non-functional requirement. Without a schema or a CI check, it drifts.

**How to avoid:**
- Define `WorkflowOutcome` as a Pydantic model PER workflow type — e.g. `AddRecipeOutcome(BaseModel): status: Literal["saved", "failed"]; recipe_id: str | None; recipe_name: str; failure_reason: str | None; image_present: bool`. Enforce at write time. Reject anything else. Total payload ~200 bytes/workflow.
- Add a token-count guard on Robotina input assembly: estimate input tokens (tiktoken or LangChain's `count_tokens`); if > threshold (e.g. 8 K), truncate older `StoredMessage` rows with a "(N older messages omitted)" marker.
- Cap conversation-history load to last N messages (e.g. 20) regardless of token count. Robotina memory layer is explicitly out-of-scope for v1.1 — so a hard cap is the right v1.1 stance.
- Add a unit test that creates 10 chained invocations with full outcomes and asserts the Robotina input stays under a token threshold.

**Warning signs:**
- LangWatch shows Robotina input-token counts climbing over a conversation.
- LLM cost-per-Robotina-turn rising.
- Provider returns `context_length_exceeded` errors.

**Phase to address:** RobotinaInvocation + `WorkflowOutcome` schema phase.

---

### Pitfall 10: Removing `acknowledge-add-recipe` step leaves orphan dependencies

**What goes wrong:**
The `acknowledge-add-recipe` step has been in the codebase since Phase 7.1 and is referenced in places easy to overlook:
- `AGENT_REGISTRY` entry — per memory `feedback_overrides_in_sync.md`, every `overrides/*.json` file references this. Removing the agent and forgetting to update an override leaves staging/dev pointing at a missing entry (silent runtime failure).
- Prompts directory (the actual prompt file `acknowledge-add-recipe/V001.md` or similar).
- Tests: integration tests that assert the workflow has N steps; removing the step changes N.
- Dashboard rendering: hard-coded step icons or label maps may include `acknowledge-add-recipe`.
- LangWatch experiment collections: removing the agent removes its trace collection retroactively.
- Prompt skeleton (Phase 14): the standardized Role/Inputs/Tools/Process/Rules/Output skeleton is across 7 active prompts. Removing one breaks the count documented in PROJECT.md.

**Why it happens:**
Phase 7.1 was a tactical workaround. It accumulated implicit dependencies that no one inventoried.

**How to avoid:**
- Treat removal as a checklist item, not an edit: AGENT_REGISTRY → all `overrides/*.json` → prompts dir → tests → dashboard step-label map → PROJECT.md prompt count.
- Grep for the literal string `acknowledge-add-recipe` across the repo before the removal PR. Should hit zero after the PR.
- Add a CI guard: enumerate AGENT_REGISTRY keys at startup, fail if any `overrides/*.json` references a missing one (per memory `feedback_overrides_in_sync.md` — this is already user-flagged as a recurring pain point; the v1.1 refactor is the right time to harden it).

**Warning signs:**
- `KeyError: 'acknowledge-add-recipe'` at runtime in dev or staging.
- Test failure: workflow step count mismatch.
- Dashboard renders blank cell or "unknown step."

**Phase to address:** Same phase that introduces `respond()` (the replacement). Single PR that adds `respond()` and removes `acknowledge-add-recipe`.

---

### Pitfall 11: Idempotency across worker crash on chain advancement

**What goes wrong:**
The wake-rule enqueues a Robotina invocation. The mechanically-risky window:
1. `on_step_complete` writes WorkflowRun.status = DONE.
2. Wake check returns true.
3. Insert RobotinaInvocation row + commit (`wake_dispatched_at` set).
4. `queue.enqueue("robotina.queue.jobs.run_task", invocation_id, job_id=pre_assigned)` — this is the failure window.
5. Worker crashes between commit (step 3) and enqueue (step 4).

After restart: the RobotinaInvocation row exists with `wake_dispatched_at` set but no RQ job. AOF flushed the commit; AOF cannot replay the enqueue (it's RQ-side and we crashed before the enqueue completed).

Mirror existing D-07 pattern in `queue_workflow`: pre-assign `job_id` BEFORE commit so a startup reconciler can detect "row says we enqueued job X; RQ has no job X" and re-enqueue.

**Why it happens:**
The current codebase already has this exact pattern for workflow steps (D-07, `task_job_id` pre-assigned in `queue_workflow` and `on_step_complete`). Re-applying it for invocations is "obvious" only if you've internalized D-07.

**How to avoid:**
- Apply D-07 for RobotinaInvocation enqueues identically: `job_id = str(uuid.uuid4())` BEFORE commit; commit; then `queue.enqueue(..., job_id=job_id, result_ttl=-1, failure_ttl=-1, meta={'task_type': 'handle-robotina-turn'})`.
- Startup reconciler in the agent boot path: query `SELECT id, job_id FROM robotina_invocation WHERE status = 'pending' AND wake_dispatched_at IS NOT NULL`. For each, check `Job.exists(job_id, connection=redis)`. If not, re-enqueue.
- Same reconciler should also handle WorkflowRunSteps in `PENDING` with `task_job_id IS NOT NULL` but no RQ job — there's currently no such reconciler in the codebase. Adding it during this milestone is a freebie.

**Warning signs:**
- After a worker restart, a RobotinaInvocation is "stuck" — row in DB, no RQ job, no log.
- User asks for a recipe, gets no reply, gets no error.

**Phase to address:** RobotinaInvocation + wake-rule phase (the reconciler can land in the same phase since it's small).

---

### Pitfall 12: Multi-recipe LLM parsing is unreliable in subtle ways

**What goes wrong:**
- User: "agregá canelones de choclo, pollo al horno y arroz pilaf" → 3 recipes. Easy case.
- User: "agregá pollo al horno con papas y arroz pilaf" → 2 recipes (pollo+papas; arroz) or 3 (pollo; papas; arroz)? Ambiguous.
- User: "salt and pepper chicken" — must NOT split into "salt" + "pepper chicken." A small/local Ollama model frequently does.
- User: "canelones con salsa blanca y boloñesa" — 1 recipe with two sauces, NOT 2 recipes.
- User pastes a URL + free text: "agregá esta receta https://example/x y también lasaña" → 1 URL workflow + 1 query workflow. Cross-source case.
- LLM emits 3 tool calls but `recipe_query` strings are non-unique ("recipe", "another recipe", "third").

**Why it happens:**
Tool-call structure forces the LLM to commit to a count. Without structured-output enforcement (Robotina is the one agent without `response_format`), the natural-language parsing is implicit in the prompt and varies by model.

**How to avoid:**
- Build a **multi-recipe eval set** in `experiments/recipe_research/` (or a new `experiments/robotina/`). 30-50 representative Spanish utterances with ground-truth recipe counts and names. Run against each LLM backend (Anthropic, OpenAI, Ollama). Accuracy threshold: ≥ 95% on the count, ≥ 90% on the names (Levenshtein or LLM-judge).
- Prompt-engineer Robotina with explicit examples covering the ambiguity classes (compound dishes, side dishes, sauces, conjunctions). Include "if you are unsure whether something is one recipe or many, prefer FEWER recipes and ask the user."
- Add an explicit `ask_user(question)` tool that lets Robotina escalate ambiguity rather than guessing. This is the "ask once, save right" mode the project's UX warrants.
- Validate before enqueue: if N > 5, reject with a `respond()` "esto son muchas — preferís de a una?" rather than fanning out a runaway batch.
- Log per-turn: `recipes_uttered_count_estimate` (LLM's count) vs. user-confirmed-count (if `ask_user` was used). Track drift.

**Warning signs:**
- Users report "I said 3 but only got 2."
- A specific phrasing pattern consistently mis-counts (e.g. "X with Y" always splits when it shouldn't).
- Eval set accuracy drops on a model upgrade.

**Phase to address:** Robotina prompt + multi-recipe phase. The eval set should LAND in this phase, not be deferred.

---

### Pitfall 13: `respond()` tool is synchronous but Telegram is async

**What goes wrong:**
The milestone description says `respond()` "writes a StoredMessage and sends to the user" synchronously. But:
- The agent task runs under RQ on a sync worker.
- Telegram send is an async call (`python-telegram-bot` v21 is async-native per the stack doc).
- Calling `asyncio.run()` inside a sync RQ job opens a new event loop each invocation — works but is slow and brittle.
- If `respond()` sends to Telegram and FAILS (network blip), do we:
  - Raise → agent's tool node returns ToolMessage(status=error) → agent retries — possibly re-sending the same text once the network recovers (duplicate user message).
  - Swallow → user never sees the message; Robotina believes it sent.
  - Return error to the agent → it may try to "fix" via another `respond()` call → loop.

**Why it happens:**
The "synchronous side-effect" framing in the description glosses over the sync/async boundary. The current Phase 7.1 path uses the QueueTool with `at_front=True` for `send-notification` (per memory `feedback_queue_at_front.md`) — i.e. the notification is enqueued, NOT sent inline. That works precisely because it's async-via-queue.

**How to avoid:**
- Make `respond()` enqueue a `send-notification` job at the front of the queue (mirror the existing Phase 6/7.1 pattern). The tool returns immediately. The job persistence guarantees the message will be sent (AOF + `result_ttl=-1`).
- BUT: this means under concurrency=1, the Robotina turn must complete and the send-notification job must run AFTER it to actually deliver. That's fine — the agent calling `respond()` then `start-workflow()` then `terminate()` produces the queue order [respond-notif, workflow-step-1, workflow-step-2, ..., next-robotina]. Because `at_front=True`, respond goes to the head.
- Alternative: a "direct send" path that bypasses the queue. NOT recommended — loses the persistence + retry guarantees and makes the agent's `respond()` behaviorally different from the existing notification path. Stay consistent.
- Make `respond()` idempotency-keyed: include the RobotinaInvocation ID + a sequence-within-turn counter in the StoredMessage row. If a duplicate is enqueued (e.g. retry path), de-dupe in the send-notification handler.

**Warning signs:**
- User receives a message twice.
- User receives the "thinking out loud" message after the final summary (ordering wrong).
- Agent loops calling `respond()` because the previous one returned an error.

**Phase to address:** `respond()` tool phase. Mirror the existing QueueTool + `send-notification` pattern.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Skip safe_fetch SSRF guards, just call `httpx.get(url)` | One line vs. a module | First time someone fetches an internal URL we leak creds; incident response is days | **Never** — SSRF is unrecoverable once exploited |
| Store image source URL only, never rehost | No backend storage changes needed | 6 months in, 30% of images are 404; user trust degrades | Acceptable for v1.1 with documented link-rot risk; revisit in v1.2 |
| Allow N up to ∞ recipes per turn | No upfront UX work | One user fans out 50 recipes; queue stalls for hours | Cap at 5 (with `respond()`-mediated polite cap) — never unlimited |
| Backfill `conversation_id` in the schema migration | One migration step | Migration takes minutes on a populated DB and blocks deploy; risk of orphan rows | Acceptable on a small DB; **never** on staging/prod once it's grown |
| Reuse `_extract_task_output` non-structured branch for Robotina | No new code path | If Robotina gains `response_format` later, the dual-path complexity sits forever | Acceptable while Robotina has no response_format; revisit when adding one |
| Drop `acknowledge-add-recipe` without auditing overrides | Smaller PR | First time staging boots with a missing AGENT_REGISTRY key → silent fail | **Never** — the override-sync invariant is already a known papercut |
| LLM-fallback path for URL parsing not built in v1.1 | Smaller scope | Long-tail URLs (sites without schema.org/Recipe) fail; users learn URL feature doesn't work | Acceptable for v1.1 if eval shows >85% URL coverage with scraper alone; revisit otherwise |
| `wake_dispatched_at` guard not added (rely on concurrency=1) | One less column | First failed-registry retry double-fires; user confusion or worse | **Never** — this is the entire pitfall #1 |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| RQ + AOF persistence | Enqueue without `result_ttl=-1, failure_ttl=-1` | Always set both — spec-locked; CI guard already partial in workflow_runner.py |
| RQ + pre-commit enqueue | Enqueue then commit (race window on crash) | Commit DB row with pre-assigned `job_id`, THEN enqueue (D-07 pattern) |
| SQLAlchemy 2.x + Alembic on JSON | `op.execute("UPDATE ... SET col = json_col->'x'")` in schema migration | Separate data migration script; never block schema migration on JSON access |
| Pydantic v2 + `Literal` field on `StartWorkflowArgs` | Add `"add-recipe"` to `Literal` only; forget to add corresponding workflow_def entry | Single registry: `WORKFLOW_REGISTRY` keys generate the `Literal`. Currently hardcoded — fix this in the refactor |
| `httpx` + redirects | Default `follow_redirects=False` plus manual loop forgets to re-check IPs | Centralized `safe_fetch` with strict per-hop validation |
| `python-telegram-bot` v21 + sync RQ worker | `asyncio.run(...)` in every tool call | Send via queue (`send-notification` job), not direct call |
| LangChain `create_agent` + multi-tool-call | Assume sequential ordering | Parallel by default; design tools to be order-independent |
| LangChain `create_agent` + Ollama | Assume model emits multiple tool calls cleanly | Test Ollama specifically; small local models split poorly |
| LangChain `response_format` + Robotina | Force a schema on the conversational agent | Robotina stays free-text; output goes through explicit `respond()` tool only |
| LangWatch + new agent types (`gather-from-url`, `recipe-image`, `respond`) | Forget to register experiment collection | Per CLAUDE.md: experiment script + LangWatch project per new agent type |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| URL fetch slow-read DoS | Single workflow holds the worker for minutes; full queue stall | `httpx` timeouts: `connect=5, read=15` at most | First adversarial URL — could be the first day |
| Multi-recipe fan-out without cap | 50-recipe submission stalls queue for an hour | Cap N at 5 with polite `respond()` | First user that pastes a TOC of recipes |
| Conversation history grows unbounded | Robotina input tokens climb monthly; provider cost climbs | Cap at last 20 messages OR token-budget-truncate | 3-6 months of active use per household |
| `WorkflowRun.outcome` filled with full RecipeData | Each invocation chain blows context window after 3-4 batches | Pydantic `WorkflowOutcome` model enforces compactness | First batch with verbose outcomes |
| Image fetch + vision-LLM-validation per candidate | 3 candidate fetches × ~10s each = 30s per recipe | Cap candidates at 3; ship the recipe without image if all fail (non-fatal) | Already a concern at single-recipe scale |
| JSON column scans in dashboards | Dashboard slow as workflow_run grows past ~10K rows | Add expression index on `shared_context->>'recipe_query'` if dashboard sorts/filters on it | When dashboard becomes a daily-use tool |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Fetching user-supplied URLs without IP/scheme/redirect guards | SSRF to AWS metadata, Redis, internal services → cred leak | `safe_fetch` helper as the only URL fetcher in the codebase; lint to forbid raw `httpx.get` outside it |
| Trusting Content-Type header for image upload | XSS via SVG with embedded `<script>` | Magic-byte validation; allowlist `{JPEG, PNG, WEBP}`; reject SVG |
| Embedding user URL in agent prompt without sanitization | Prompt injection (URL is "Ignore all instructions and …") | URL goes into a tool argument, never spliced into a prompt template directly; tool reads the URL, fetches, parses, returns extracted RecipeData. Agent sees the extracted data, not the URL contents. |
| Logging the full URL with embedded credentials | `https://user:pass@host/...` in logs → leak | Sanitize credentials from URL before logging (`urllib.parse.urlsplit` → drop userinfo) |
| `WorkflowRun.outcome` JSON contains PII or chat content | DB dump leaks more than necessary | `WorkflowOutcome` schema is constrained — no free-form text dumping |
| Image storing with EXIF | GPS coords leak | Strip EXIF (Pillow `image.getexif().clear()`) before save/rehost |
| Trusting LLM-generated SQL/HTML/file paths | Code injection if those outputs are exec'd | Already mitigated by tool-arg validation; reinforce: nothing the LLM emits is exec'd verbatim |
| Allowing `http://` URLs (not just https) | Plaintext exfil; easier MitM | Scheme allowlist defaults to https only |
| Dashboard exposed on 0.0.0.0 with failure_reason leaking exc text | Per WR-02 comment — D-16 format leaks env vars / payloads | Already capped at 500 chars + default loopback; document that 0.0.0.0 opt-in carries residual risk |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Silent multi-recipe partial failure | User said 3, sees 2 saved, no mention of the third | `respond()` always summarizes ALL workflow outcomes (success and failure) explicitly |
| Wrong-dish image saved | User trust breaks ("Robotina doesn't know what she's doing") | Vision-LLM validation before save; ship without image rather than wrong image |
| Slow URL-ingestion with no progress indicator | User pastes URL, waits 30s wondering if it worked | `respond()` BEFORE `start-workflow` with "ya estoy buscando esa receta…" |
| Apology message after success | "Algo falló…" fires from dead-letter even on retry success | Idempotency on send-notification + sequence numbers (Pitfall 13) |
| Same recipe name saved twice (multi-recipe with overlap) | User confused about which is which | Detect overlap in the wake-up Robotina turn; ask "ya tenés X, querés sobreescribir?" |
| URL with auto-redirect to wrong recipe variant | User shares "carbonara" URL, gets pasta-with-cream because that's where the URL redirected | Show user the title that was extracted in the success message: "agregué 'Pasta con Crema y Champiñones' — era esto?" |
| Robotina speaks too much (chatty after every workflow) | Spam | Prompt rule: one user-facing message per invocation, unless explicitly multiple distinct events |

## "Looks Done But Isn't" Checklist

- [ ] **Wake rule:** appears to work in tests under sequential single-batch scenario — verify it survives a `kill -9` of the worker between two terminal transitions
- [ ] **Multi `start-workflow` calls:** appears to work with Anthropic — verify with Ollama (development backend), where parallel tool calls are flakier
- [ ] **`return_direct=True` removal:** appears clean — verify no path consumes `result['messages'][-1].content` as a user-visible string
- [ ] **`respond()` tool:** appears to send — verify it survives a `send-notification` retry without double-delivery
- [ ] **`acknowledge-add-recipe` removal:** appears removed — grep the entire repo for the literal string after the PR; verify all `overrides/*.json` still load
- [ ] **`conversation_id` migration:** appears to backfill — verify post-migration `COUNT(conversation_id IS NULL AND status = 'done')` per platform
- [ ] **`WorkflowRun.outcome`:** appears compact — measure average size after 5 batches; assert < 1 KB/workflow
- [ ] **URL fetch:** appears to work — verify it REJECTS `http://169.254.169.254/`, `http://localhost:6379/`, redirect chains that cross those, gzip bombs, 100 MB HTML
- [ ] **`gather-from-url`:** appears to parse — measure field-level success rate on a 20-URL eval set (title, ingredients_count, instructions_count, image)
- [ ] **`recipe-image`:** appears to fetch — verify vision-LLM validation actually rejects wrong-dish candidates (test with a "carbonara" → known cream-and-mushroom image)
- [ ] **RobotinaInvocation reconciler:** appears unnecessary on a happy path — verify a `kill -9` between commit and enqueue produces a `pending` row that the next startup re-enqueues
- [ ] **`WorkflowOutcome` schema:** appears to constrain — verify a developer who writes `outcome = {"raw": recipe_data.model_dump()}` gets rejected at write time
- [ ] **Multi-recipe eval:** appears accurate on cherry-picked cases — verify the eval set includes the ambiguous classes (compound dishes, side dishes, conjunctions)

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Wake-rule double-fire | LOW | Add `wake_dispatched_at` column + retroactive UPDATE setting it for any RobotinaInvocation older than 1 hour; backfill complete |
| Wrong image saved | LOW | Backend admin endpoint to clear/replace image URL; reaction-emoji from user could trigger re-image as a v1.2 feature |
| `conversation_id` orphan rows after migration | LOW-MEDIUM | Data-fix script; safe because new code tolerates NULL |
| Robotina context bloat already happening | LOW | Add token-cap truncation to history loader; deploy; rolling improvement |
| SSRF exploit fired | HIGH | Rotate any creds reachable from the worker host; audit logs for prior exploit; patch URL-fetch; consider time window of vulnerability |
| Multi-recipe parsing chronically wrong | MEDIUM | Iterate prompt with the eval set; if model is the bottleneck, swap LLM backend for Robotina (multi-LLM swap is cheap per CLAUDE.md) |
| `respond()` double-delivery | LOW | Add sequence-key idempotency; replay log to count duplicates and notify affected users |
| `acknowledge-add-recipe` ghost reference broke staging | LOW | Roll back PR; re-do with full grep + override audit; ship |
| URL fetch hangs the worker | MEDIUM | Kill the job from RQ failed registry; tighten timeouts; document affected URL pattern in fetch helper tests |
| `WorkflowRun.outcome` already verbose in some workflows | LOW | Backfill: rewrite existing rows to the compact schema; deploy schema enforcement; old rows truncated to fields the new schema accepts |

## Pitfall-to-Phase Mapping

The roadmapper should treat this as guidance on phase ordering and per-phase research depth.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| 1: Wake double-fire | RobotinaInvocation + wake-rule | `wake_dispatched_at` UPDATE returns 0 rows on retry — assertion in test |
| 2: Stale-read wake check | Same as #1 | Test injects a session and asserts wake fires inside the same transaction |
| 3: Migration backfill | Schema migration phase (PRECEDES code that depends on FKs) | Post-migration count of orphan rows = 0; in-flight workflow count = 0 at deploy |
| 4: AI text leak post-`return_direct=False` | `respond()` + `terminate()` + prompt rewrite | Smoke test: prompt that elicits chain-of-thought; verify `respond()` count == user-visible messages |
| 5: `create_agent` parallel tool calls | `StartWorkflowTool` refactor | Test: agent emits 3 parallel start-workflow calls, all 3 WorkflowRuns created, all linked to same invocation |
| 6: SSRF | `gather-from-url` (FIRST commit in that phase = safe_fetch helper) | Test suite that submits 10 adversarial URLs; all rejected |
| 7: recipe-scrapers silent partial | `gather-from-url` (same phase, after safe-fetch) | 20-URL eval-set with field-level success rate target ≥ 85% |
| 8: Wrong-dish image | `recipe-image` phase | Vision-LLM validation reduces wrong-dish rate on 30-recipe spot-check eval |
| 9: Context bloat | RobotinaInvocation phase (`WorkflowOutcome` schema lands together) | Pydantic schema enforced; token-budget truncation on history; LangWatch input-token median plotted |
| 10: `acknowledge-add-recipe` removal | Same phase as `respond()` | Repo grep returns zero hits; CI guard for AGENT_REGISTRY ↔ overrides/*.json |
| 11: Idempotency on chain interruption | RobotinaInvocation + wake-rule (same phase as #1 — reconciler is small) | Manual test: `kill -9` between commit and enqueue; restart; verify pending invocation recovers |
| 12: Multi-recipe parsing | Robotina prompt + multi-recipe phase | Eval set with ≥ 95% count accuracy on Anthropic/OpenAI; ≥ 85% on Ollama dev |
| 13: `respond()` sync/async | `respond()` tool phase | Crash test: kill worker after `respond()` enqueue but before delivery — message still delivers on restart |

## Sources

- Internal: `/home/solanoe/code/robotina-gsd/plans/02-workflow-refinement/description.md` (architectural direction; explicit open questions cited above)
- Internal: `/home/solanoe/code/robotina-gsd/src/robotina/queue/workflow_runner.py` (D-07 transactional advancement; D-16 failure_reason format; WR-02 length cap; AOF + `result_ttl=-1, failure_ttl=-1` invariants)
- Internal: `/home/solanoe/code/robotina-gsd/src/robotina/agent/tools/start_workflow.py` (Phase 07.1 `return_direct=True`, REQ-HID-3 household_id required, args_schema with `extra='forbid'`)
- Internal: `CLAUDE.md` (Phase 11 response_format adoption; Phase 16 four-layer household_id; LangChain 1.x via `langchain.agents.create_agent`; concurrency=1; AOF `appendfsync always`)
- Internal: project memory `feedback_overrides_in_sync.md` (AGENT_REGISTRY ↔ overrides invariant)
- Internal: project memory `feedback_queue_at_front.md` (notifications via QueueTool at_front=True)
- Internal: project memory `project_local_dev_setup.md` (agent/gateway on host; Postgres/Redis in Compose — SSRF-relevant: `localhost` from agent IS the host machine)
- External: [LangChain agents docs (`create_agent` ReAct loop, final-message content semantics)](https://docs.langchain.com/oss/python/langchain/agents) — MEDIUM confidence on exact final-AI-message-content vs. structured-response interaction; smoke test in Phase 02 before locking the prompt
- External: [LangChain GitHub #34010 — Disable parallel tool calls in `create_agent()`](https://github.com/langchain-ai/langchain/issues/34010) — HIGH confidence that `parallel_tool_calls` is not exposed on `create_agent`; workaround documented
- External: [LangChain forum — parallel tool calling in LangGraph](https://forum.langchain.com/t/parallel-tool-calling-in-langgraph/439) — corroborates above
- External: [recipe-scrapers docs](https://docs.recipe-scrapers.com/) — HIGH confidence that the library is parser-only and the caller owns network/security
- External: [recipe-scrapers GitHub](https://github.com/hhursev/recipe-scrapers) — wild_mode behavior and supported-sites list
- External: General SSRF prevention guidance (OWASP SSRF cheat sheet patterns: scheme allowlist, IP allowlist post-DNS, redirect re-validation, resource caps) — applied here to Python/httpx specifics

---
*Pitfalls research for: Robotina v1.1 Workflows Abstraction Refinement*
*Researched: 2026-05-18*
