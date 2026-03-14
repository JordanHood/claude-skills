---
name: notify
description: "Send macOS desktop and mobile push notifications from Claude Code. Use when: completing background tasks, alerting on errors, notifying at pipeline gates, or any time the user should be alerted about something happening outside the active session. Supports terminal-notifier (rich, clickable), osascript (fallback), and ntfy.sh (mobile push)."
license: MIT
metadata:
  author: jordan.hood
  version: "0.1.0"
user_invocable: true
---

# Notify

Send notifications to the user's desktop or phone.

## Usage

Run the notify script from any skill, worker, or session:

```bash
bash <skill-dir>/scripts/notify.sh "Title" "Message" [priority] [url] [run-id]
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| Title | Yes | "Claude Code" | Notification title |
| Message | Yes | "Task complete" | Notification body |
| Priority | No | "default" | `default`, `high`, or `urgent`. High/urgent play sound and send mobile push. |
| URL | No | none | Clickable URL (terminal-notifier only). Opens on notification click. |
| Run ID | No | "default" | Group ID for notification replacement. Same run-id updates in place. |

### Priority behaviour

| Priority | Desktop sound | Mobile push (ntfy) | Use case |
|----------|--------------|-------------------|----------|
| `default` | No | No | Phase completion, progress updates |
| `high` | Yes (Glass) | Yes | Errors, gates, pipeline complete, PRs ready |
| `urgent` | Yes (Glass) | Yes (bypasses DnD) | Critical failures |

### Examples

```bash
# Simple notification
bash <skill-dir>/scripts/notify.sh "Pipeline" "Research complete"

# High priority with PR link
bash <skill-dir>/scripts/notify.sh "Pipeline" "PR #45 ready for review" "high" "https://github.com/org/repo/pull/45"

# Grouped notification (updates in place)
bash <skill-dir>/scripts/notify.sh "Pipeline" "Worker 2/4 complete" "default" "" "pipeline-run-123"
bash <skill-dir>/scripts/notify.sh "Pipeline" "Worker 3/4 complete" "default" "" "pipeline-run-123"
```

## Setup

### Desktop notifications (works out of the box)

Uses `osascript` which is available on all macOS systems. For richer notifications:

```bash
brew install terminal-notifier
```

This adds: clickable URLs, notification grouping/replacement, and custom sounds.

### Mobile push notifications (optional)

1. Install the ntfy app on your phone (iOS/Android)
2. Subscribe to a topic (e.g., `jordan-claude-pipeline`)
3. Set the environment variable:

```bash
export NTFY_TOPIC="jordan-claude-pipeline"
```

Or add to `~/.claude/settings.json` env block. Notifications with `high` or `urgent` priority will be pushed to your phone.
