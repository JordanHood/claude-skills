# notify

Desktop and mobile push notifications for Claude Code. Works with any skill, worker, or session.

## Install

```bash
npx skills add JordanHood/claude-skills --skill notify
```

## Usage

```bash
bash <skill-dir>/scripts/notify.sh "Title" "Message" [priority] [url] [run-id]
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| Title | "Claude Code" | Notification title |
| Message | "Task complete" | Notification body |
| Priority | "default" | `default`, `high`, or `urgent` |
| URL | -- | Clickable link (terminal-notifier only) |
| Run ID | "default" | Group ID for notification replacement |

## Three tiers

| Tier | Install | Features |
|------|---------|----------|
| **osascript** | Nothing (built into macOS) | Basic notifications with sound |
| **terminal-notifier** | `brew install terminal-notifier` | Clickable URLs, grouping, custom sounds |
| **ntfy.sh** | Phone app + `NTFY_TOPIC` env var | Push to your phone when away from desk |

The script auto-detects what's available and uses the best option. High/urgent priority fires both desktop and mobile (if configured).

## Automatic worker notifications

For notifications on every Dispatch worker completion, use the `claude-with-notify.sh` wrapper from the guardrails skill as your Dispatch backend:

```yaml
# ~/.dispatch/config.yaml
backends:
  claude:
    command: ~/.claude/hooks/claude-with-notify.sh
```

This fires a notification after every `claude -p` session exits, regardless of what the worker did.
