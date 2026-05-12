---
status: awaiting_human_verify
trigger: "telegram-bot-not-polling"
created: 2026-03-27T00:00:00Z
updated: 2026-03-27T00:01:00Z
---

## Current Focus

hypothesis: CONFIRMED — gateway/__init__.py main() reads os.environ["TELEGRAM_BOT_TOKEN"] without calling load_dotenv() first. The .env file is never loaded for the gateway process, causing KeyError on startup. runner.py already applies the correct pattern (load_dotenv() at top of main()). Fix: add load_dotenv() to gateway/__init__.py main().
test: Read gateway/__init__.py — confirmed no load_dotenv() call. Read runner.py — confirmed load_dotenv() is called at top of main(). Read all.py — confirmed subprocess launch means each child needs its own load_dotenv().
expecting: Adding load_dotenv() to gateway main() before os.environ["TELEGRAM_BOT_TOKEN"] resolves KeyError.
next_action: Add load_dotenv() to gateway/__init__.py main()

## Symptoms

expected: `uv run agent` starts both the RQ worker AND the Telegram bot polling loop; incoming messages trigger job enqueuing and responses
actual: Only the RQ worker starts. No Telegram polling logs. Bot receives no messages.
errors: No errors in logs. Logs end at "cleaning registries for queue: agent-tasks" — nothing about Telegram or bot initialization.
reproduction: Run `uv run agent` with Docker Compose running (Postgres + Redis). Send a Telegram message. No response.
started: First time running E2E after Phase 7 implementation.

## Eliminated

- hypothesis: Bug in gateway code itself (handler.py, gateway/__init__.py)
  evidence: gateway/__init__.py correctly implements run_polling(), handler.py correctly enqueues jobs. Code is correct — it was simply never started.
  timestamp: 2026-03-27T00:01:00Z

- hypothesis: Telegram polling silently failing at startup
  evidence: No errors because gateway process is never launched by uv run agent. It is a separate script entry.
  timestamp: 2026-03-27T00:01:00Z

## Evidence

- timestamp: 2026-03-27T00:00:30Z
  checked: pyproject.toml [project.scripts] section
  found: agent = "robotina.queue.runner:main" (RQ worker only), gateway = "robotina.gateway:main" (Telegram polling only), all = "robotina.all:main" (spawns both as subprocesses)
  implication: Three separate commands exist; agent intentionally does NOT start the gateway

- timestamp: 2026-03-27T00:00:45Z
  checked: src/robotina/queue/runner.py main()
  found: Starts LoggingWorker on agent-tasks queue only. No reference to Telegram bot, no threading, no gateway startup.
  implication: By design, uv run agent = worker only

- timestamp: 2026-03-27T00:00:50Z
  checked: src/robotina/all.py
  found: Launches both ["uv", "run", "agent"] and ["uv", "run", "gateway"] as subprocess.Popen children. This is the correct command for E2E operation.
  implication: uv run all is the documented way to start full system

- timestamp: 2026-03-27T00:01:00Z
  checked: README.md Running section
  found: Documents ONLY `uv run agent` under "Task runner". No mention of `uv run gateway` or `uv run all`. This is why user ran the wrong command.
  implication: README omission caused the user confusion. Fix = update README + add startup hint in runner.py

- timestamp: 2026-03-27T00:02:00Z
  checked: gateway/__init__.py main() — confirmed no load_dotenv() call before os.environ["TELEGRAM_BOT_TOKEN"]
  found: Line 23: token = os.environ["TELEGRAM_BOT_TOKEN"] with no prior load_dotenv(). runner.py main() calls load_dotenv() as its first action (line 87-89). all.py spawns both as separate subprocess.Popen children — each child process starts fresh, inheriting OS env but NOT uv run agent's in-process load_dotenv() call.
  implication: Every invocation of `uv run gateway` (standalone or via `uv run all`) fails with KeyError unless TELEGRAM_BOT_TOKEN is already in the OS environment. The fix is to add load_dotenv() at the start of gateway main(), matching the runner.py pattern.

## Resolution

root_cause: Two compounding issues: (1) gateway/__init__.py main() calls os.environ["TELEGRAM_BOT_TOKEN"] without first calling load_dotenv(), causing KeyError when .env is present but not exported to the OS environment. runner.py correctly calls load_dotenv() but gateway does not. (2) README.md only documents `uv run agent`, so users never learn that `uv run gateway` (or `uv run all`) is needed.
fix: (1) Add load_dotenv() to gateway/__init__.py main() before reading env vars — matching the exact pattern in runner.py. (2) Update README.md to document all three run commands. (3) runner.py already has the NOTE log directing users to gateway (already applied in prior session work).
verification: Added `from dotenv import load_dotenv; load_dotenv()` to gateway/__init__.py main() before os.environ["TELEGRAM_BOT_TOKEN"] — matches the runner.py pattern exactly. Self-verified by reading both files side by side. README already documents all three commands (uv run all, uv run agent, uv run gateway) from prior session work. Awaiting human confirmation that `uv run gateway` no longer crashes.
files_changed:
  - src/robotina/gateway/__init__.py
  - README.md
