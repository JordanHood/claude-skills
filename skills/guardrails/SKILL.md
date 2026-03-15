---
name: guardrails
description: "Safety hooks for Claude Code that protect against destructive operations, enforce write boundaries, and gate sensitive actions. Essential when running autonomous workers with --dangerously-skip-permissions. Use when: setting up a new Claude Code environment, configuring safety for dispatch/pipeline workers, or auditing existing hook coverage."
license: MIT
metadata:
  author: jordan.hood
  version: "0.1.0"
user_invocable: true
---

# Guardrails

Safety hooks for Claude Code that act as the real enforcement layer when running autonomous workers with `--dangerously-skip-permissions`.

## Why This Matters

When using Dispatch or Pipeline to spawn autonomous workers, those workers run with `--dangerously-skip-permissions` because they're headless (no terminal to prompt for approval). Without hooks, they can do anything -- force-push to main, delete files, write secrets, modify your Claude config.

Guardrails hooks are the safety net. They fire on every tool use regardless of permission mode, blocking or prompting for dangerous actions.

## What's Included

### Example Hooks

These are generalised, production-tested hooks. Copy them to `~/.claude/hooks/` and wire them into your `settings.json`.

| Hook | Type | Purpose |
|------|------|---------|
| `bash-precheck.py` | PreToolUse (Bash) | Blocks destructive commands, protects sensitive paths, gates commits, prevents credential reads |
| `write-boundary.py` | PreToolUse (Edit/Write) | Restricts file writes to project directory + /tmp, extra restrictions for workers |

### What They Block

**Hard deny (always blocked):**
- `git reset --hard`, `git push --force`, `git clean -f`
- Writes to `/etc/`, `/usr/`, `/System/`, `~/.ssh/`, `~/.aws/`, `~/.gnupg/`
- `npm publish`, `pnpm publish`, `yarn publish`
- `DROP TABLE`, `TRUNCATE TABLE`
- `launchctl` service modifications, `crontab` edits
- Workers modifying Claude config (`~/.claude/hooks/`, `settings.json`, `CLAUDE.md`)

**Prompt (ask user, allow or deny):**
- `rm -rf` and recursive `rm`
- Docker destructive commands (`docker rm`, `docker stop`, `docker system prune`)
- `kill -9`, `killall`
- Outbound data via `curl POST` / `wget --post`
- Writes outside the project directory
- Reading credential files (`~/.ssh/`, `~/.aws/`, `~/.npmrc/`, `~/.netrc/`)

**Commit gates (blocks commit until fixed):**
- Direct commits on protected branches (`main`, `master`, `staging`)
- Commits when lint fails
- Commits when tests fail
- Pushes from/to protected branches

## Installation

### 1. Copy hooks

```bash
cp examples/bash-precheck.py ~/.claude/hooks/
cp examples/write-boundary.py ~/.claude/hooks/
chmod +x ~/.claude/hooks/bash-precheck.py ~/.claude/hooks/write-boundary.py
```

### 2. Wire into settings.json

Add to your `~/.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [{ "type": "command", "command": "~/.claude/hooks/bash-precheck.py" }]
      },
      {
        "matcher": "Edit|Write|MultiEdit",
        "hooks": [{ "type": "command", "command": "~/.claude/hooks/write-boundary.py" }]
      }
    ]
  }
}
```

### 3. Customise

Edit the hooks to match your setup:

- **`BLOCKED_TOOLS`** in `bash-precheck.py` -- add/remove CLI tools that should use package.json scripts instead of direct invocation
- **`PROTECTED_BRANCHES`** -- change from `{"staging", "main", "master"}` to your branch names
- **`SENSITIVE_PATHS`** -- add paths specific to your environment
- **`ALWAYS_ALLOWED`** in `write-boundary.py` -- add directories workers should be able to write to
- **`CLAUDE_ALLOWED_WRITE_PATHS`** env var -- colon-separated additional write paths

## How Hooks Work

Claude Code hooks fire on every tool use, even with `--dangerously-skip-permissions`:

```
Agent calls Bash("git push --force")
  -> PreToolUse hooks fire
  -> bash-precheck.py reads the command
  -> Matches destructive pattern
  -> Returns deny with reason
  -> Command is blocked, agent sees the error
```

Three possible outcomes:
- **Allow** (hook returns nothing) -- tool executes normally
- **Deny** (hook returns `permissionDecision: "deny"`) -- tool blocked, agent sees reason
- **Ask** (hook returns `permissionDecision: "ask"`) -- user prompted to allow or deny

Workers running headless with `--dangerously-skip-permissions` never see "ask" prompts -- they auto-approve. This is why the hooks use "deny" for genuinely dangerous operations and "ask" only for things the user might reasonably want to allow.

## Worker Safety

The hooks detect worker sessions by checking for `/tmp/claude-workers/<session_id>.meta`. Workers get stricter rules:

- Cannot modify Claude config files (hooks, settings, CLAUDE.md)
- Cannot redirect output to Claude config
- Same destructive operation blocks as interactive sessions

This prevents a dispatched worker from modifying its own safety constraints.
