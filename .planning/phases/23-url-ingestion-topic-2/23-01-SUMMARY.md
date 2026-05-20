---
phase: 23-url-ingestion-topic-2
plan: 01
subsystem: infra
tags: [url-fetch, ssrf, http, httpx, security, safe-fetch]

# Dependency graph
requires:
  - phase: research
    provides: PITFALLS.md Pitfall 6 (SSRF defense matrix); RESEARCH.md Pattern 1 (canonical safe_fetch implementation)
provides:
  - safe_fetch sync HTTP fetcher with six SSRF defenses + gzip-bomb defense
  - SafeFetchResult Pydantic model (final_url, content_bytes, content_type, status_code)
  - SafeFetchError exception type with defense-naming messages
  - URL_INGESTION_ALLOW_HTTP env var (dev/testing only)
  - respx test infrastructure for httpx mocking
  - trafilatura dependency (consumed in 23-03)
affects: [23-03 FetchAndScrapeTool, 24-recipe-image step, any future code that fetches user-supplied URLs]

# Tech tracking
tech-stack:
  added: [trafilatura>=1.6 (project dep, used in 23-03), respx>=0.21 (dev dep, httpx mocking)]
  patterns:
    - "safe_fetch() as the single load-bearing gateway for ALL user-supplied URL fetches"
    - "respx + monkeypatch on socket.getaddrinfo as the standard test pattern for safe_fetch consumers"
    - "Defense ordering: specific-predicate (is_loopback / is_link_local) before broad-predicate (is_private) — produces precise error reason strings"

key-files:
  created:
    - src/robotina/url/__init__.py
    - src/robotina/url/safe_fetch.py
    - tests/url/__init__.py
    - tests/url/test_safe_fetch.py
  modified:
    - .env.example (added URL_INGESTION_ALLOW_HTTP)
    - pyproject.toml (added trafilatura, respx)
    - uv.lock (regenerated)

key-decisions:
  - "Reordered _is_blocked_ip predicates (Rule 1 auto-fix) — is_loopback/is_link_local checked before is_private because ipaddress.is_private is a superset; needed for precise reason strings consumed by tests and operator logs"
  - "Trafilatura declared in pyproject.toml in this plan (not in 23-03 where it's consumed) — per CLAUDE.md memory feedback_overrides_in_sync 'keep deps in one commit', dep declarations land with the first commit that touches the dep-list"
  - "gzip-bomb defense unit-tested by direct call to _decompress_with_cap rather than via full safe_fetch path — httpx auto-decompresses gzip transparently and would defeat the test setup; the unit-level test exercises the defense logic deterministically"

patterns-established:
  - "Pattern: top-level src/robotina/url/ package for URL-handling utilities (sibling to queue/, agent/, etc.) — utilities consumed by tools live OUTSIDE agent/tools/ to keep layer separation clean"
  - "Pattern: SafeFetchError messages name the violated defense — callers grep the message to drive observability tags, dashboard rendering, and test assertions"
  - "Pattern: query string stripped from INFO logs (URL_LEAK threat T-23-URL-LEAK-LOG); full URL only at DEBUG"

requirements-completed: [URL-01]

# Metrics
duration: ~12min
completed: 2026-05-20
---

# Phase 23 Plan 01: safe_fetch SSRF/Abuse Defense Utility Summary

**Sync httpx-based URL fetcher with six SSRF defenses (scheme allowlist, DNS A/AAAA blocklist, manual redirect re-validation, configurable timeouts, size caps, content-type sniff) plus a 20:1 gzip-bomb defense, backed by a 21-test respx-mocked test suite.**

## Performance

- **Duration:** ~12 min
- **Completed:** 2026-05-20T23:14:36Z
- **Tasks:** 2
- **Files created:** 4
- **Files modified:** 3

## Accomplishments

- Landed `src/robotina/url/safe_fetch.py` (239 lines) as the load-bearing security primitive for ALL subsequent URL-handling code in Phase 23 and Phase 24.
- Encoded every defense from D-16 in a single sync function: scheme allowlist (https-only unless `URL_INGESTION_ALLOW_HTTP=true`), DNS A/AAAA record blocklist (RFC1918/loopback/link-local/multicast/0.0.0.0/169.254.169.254 with IPv4-mapped-IPv6 unwrap and multi-A-record defeat), manual `follow_redirects=False` loop with max 3 hops and per-hop re-validation, configurable `httpx.Timeout`, Content-Length pre-check and post-decode body cap, Content-Type sniff (`text/html`/`application/xhtml+xml` for HTML; `image/*` prefix for images), gzip-bomb defense (ratio cap 20:1 plus decompressed-size cap).
- Wrote 21 named pytest tests in `tests/url/test_safe_fetch.py` — one per defense scenario from D-18 — with respx mocking the httpx layer and `monkeypatch.setattr(sf_mod.socket, "getaddrinfo", ...)` controlling DNS. Zero real network I/O.
- Added `URL_INGESTION_ALLOW_HTTP=false` to `.env.example` with a dev-only warning (per memory `feedback_env_example`).
- Added `trafilatura>=1.6` to project deps (consumed by Plan 23-03) and `respx>=0.21` to the dev dependency-group; `uv sync` resolves both.
- Logs successful fetches at INFO with query string stripped via `httpx.URL(url).copy_with(query=None)` — mitigates T-23-URL-LEAK-LOG.

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement safe_fetch utility module** — `b290f9a` (feat)
2. **Task 2: Wire env var, add respx dev dep, write SSRF defense test suite** — `64f9e11` (test; bundles the predicate-ordering Rule 1 auto-fix into the test commit so the suite is green at HEAD)

## Files Created/Modified

- `src/robotina/url/__init__.py` — package marker for new `robotina.url` namespace
- `src/robotina/url/safe_fetch.py` — `safe_fetch()`, `SafeFetchResult`, `SafeFetchError`, helpers `_is_blocked_ip`, `_resolve_and_check`, `_check_scheme`, `_decompress_with_cap`
- `tests/url/__init__.py` — package marker
- `tests/url/test_safe_fetch.py` — 21 named tests covering every defense scenario from D-18
- `.env.example` — appended `URL_INGESTION_ALLOW_HTTP=false` with dev/testing warning
- `pyproject.toml` — `trafilatura>=1.6` in `[project.dependencies]`, `respx>=0.21` in `[dependency-groups].dev`
- `uv.lock` — regenerated after `uv sync`

## Decisions Made

- **Predicate ordering in `_is_blocked_ip`**: specific predicates (`is_loopback`, `is_link_local`) checked before `is_private`. Rationale: Python's `ipaddress.is_private` returns True for 127.0.0.0/8 and 169.254.0.0/16, masking the more specific reason. The reason string is part of the contract (tests + operator log triage assert on it).
- **gzip-bomb test exercises `_decompress_with_cap` directly**: httpx transparently auto-decompresses gzip on the wire, defeating a respx-based end-to-end gzip-bomb test. The defense logic itself is fully covered at the unit level — both the ratio cap (20:1) and the decompressed-size cap (`> max_bytes`) — and the safe_fetch happy path tests confirm the integration call site.
- **No br/zstd manual decompression**: per plan instruction, let httpx negotiate `Accept-Encoding` and decode br/zstd transparently. Our `_decompress_with_cap` only handles gzip/deflate explicitly (the encodings most likely to surface as raw bytes after a redirect or unusual server).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Reordered `_is_blocked_ip` predicate checks**
- **Found during:** Task 2 (running the SSRF test suite)
- **Issue:** The canonical RESEARCH.md Pattern 1 ordering checked `ip.is_private` before `ip.is_loopback` / `ip.is_link_local`. Python's `ipaddress` module classifies loopback (127.0.0.0/8) and link-local (169.254.0.0/16) as ALSO `is_private`, so the broader predicate matched first and the reason string read "private (RFC1918)" instead of the specific defense ("loopback", "link-local"). Tests asserting on the precise reason failed (4 of 21).
- **Fix:** Moved `is_unspecified` / `is_loopback` / `is_link_local` / `is_multicast` ahead of `is_private` in the check ladder. The blocking semantics are unchanged (all of these still reject); only the human-readable reason string is now correct.
- **Files modified:** `src/robotina/url/safe_fetch.py` (`_is_blocked_ip`)
- **Verification:** `uv run pytest tests/url/test_safe_fetch.py -q` → 21/21 pass.
- **Committed in:** `64f9e11` (bundled with Task 2's test commit so HEAD is green)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** No scope creep. The fix preserves all defense semantics; only the error message specificity improved, which the test suite (D-18) explicitly contracts on.

## Issues Encountered

None beyond the deviation above.

## Threat Flags

None. All security-relevant surface introduced by this plan (the safe_fetch entry point itself) is documented in the plan's `<threat_model>` (T-23-SSRF-INTERNAL, T-23-DNS-REBIND, T-23-REDIRECT-INTERNAL, T-23-REDIRECT-LOOP, T-23-OVERSIZE-FETCH, T-23-GZIP-BOMB, T-23-PROTO-SMUGGLING, T-23-CONTENT-TYPE-MISMATCH, T-23-SLOW-LORIS, T-23-URL-LEAK-LOG) and each has a corresponding mitigation in code + at least one test in `tests/url/test_safe_fetch.py`.

## Self-Check: PASSED

Verified at HEAD `64f9e11`:
- `src/robotina/url/__init__.py` exists.
- `src/robotina/url/safe_fetch.py` exists (239 lines, ≥120 required).
- `tests/url/__init__.py` exists.
- `tests/url/test_safe_fetch.py` exists with 21 `def test_` functions (≥20 required).
- `grep -c SafeFetchError src/robotina/url/safe_fetch.py` → 18 (≥8 required).
- `grep -q follow_redirects=False`, `is_private`, `is_loopback`, `is_link_local`, `URL_INGESTION_ALLOW_HTTP`, `169.254.169.254`, `_GZIP_RATIO_CAP` all match.
- `grep -q URL_INGESTION_ALLOW_HTTP .env.example` → match.
- `grep -q trafilatura pyproject.toml` → match.
- `grep -q respx pyproject.toml` → match.
- `uv run python -c "from robotina.url.safe_fetch import safe_fetch, SafeFetchResult, SafeFetchError"` → succeeds.
- `uv run pytest tests/url/test_safe_fetch.py -q` → 21 passed, 0 failed.
- Commits `b290f9a` and `64f9e11` present in `git log`.

## Next Phase Readiness

- `safe_fetch` is ready to be imported by `FetchAndScrapeTool` (Plan 23-03) and the Phase 24 `recipe-image` step.
- `trafilatura` is installed and importable, ready for 23-03's HTML-cleaning fallback path.
- `URL_INGESTION_ALLOW_HTTP` env var is documented; experiment harnesses (23-06) can opt into http:// for test fixtures without code changes.
- No blockers. Plan 23-02 (workflow registry rename + AddRecipeUrlInput) is unblocked and can proceed in parallel.

---
*Phase: 23-url-ingestion-topic-2*
*Plan: 01*
*Completed: 2026-05-20*
