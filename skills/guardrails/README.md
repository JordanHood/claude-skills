# guardrails

Safety hooks for Claude Code. Essential when running autonomous workers with `--dangerously-skip-permissions`.

Hooks fire on every tool use regardless of permission mode -- they're the real enforcement layer.

## Install

```bash
npx skills add JordanHood/claude-skills --skill guardrails
```

Then copy the examples to your hooks directory:

```bash
cp examples/bash-precheck.py ~/.claude/hooks/
cp examples/write-boundary.py ~/.claude/hooks/
cp examples/claude-with-notify.sh ~/.claude/hooks/
chmod +x ~/.claude/hooks/bash-precheck.py ~/.claude/hooks/write-boundary.py ~/.claude/hooks/claude-with-notify.sh
```

Wire into `~/.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      { "matcher": "Bash", "hooks": [{ "type": "command", "command": "~/.claude/hooks/bash-precheck.py" }] },
      { "matcher": "Edit|Write|MultiEdit", "hooks": [{ "type": "command", "command": "~/.claude/hooks/write-boundary.py" }] }
    ]
  }
}
```

## What's included

### bash-precheck.py

Pre-tool-use hook for Bash commands.

**Hard deny:** force-push, reset --hard, clean -f, writes to /etc /usr ~/.ssh ~/.aws, npm publish, DROP TABLE, workers modifying Claude config

**Prompt:** rm -rf, docker rm/stop, kill -9, outbound curl POST, credential file reads

**Commit gates:** blocks commits on protected branches, blocks commits when lint or tests fail

### write-boundary.py

Pre-tool-use hook for Edit/Write/MultiEdit.

Restricts writes to the project directory + /tmp. Workers get stricter boundaries -- they can't modify ~/.claude/hooks, settings.json, or CLAUDE.md.

Extend via `CLAUDE_ALLOWED_WRITE_PATHS` env var (colon-separated paths).

### claude-with-notify.sh

Dispatch backend wrapper. Runs `claude -p` then fires a notification on exit. Use as your Dispatch backend for automatic worker completion alerts:

```yaml
# ~/.dispatch/config.yaml
backends:
  claude:
    command: ~/.claude/hooks/claude-with-notify.sh
```

## Customisation

All hooks have clearly marked `CUSTOMISE THESE` sections at the top:

- **BLOCKED_TOOLS** -- CLI tools that should use package.json scripts
- **PROTECTED_BRANCHES** -- branches that block direct commits
- **SENSITIVE_PATHS** -- paths that block writes
- **ALWAYS_ALLOWED** -- paths workers can always write to
