# Notification Setup

## How Pipeline Uses the Notify Skill

Pipeline looks for the notify skill in the available skills list at startup. When found, it calls:

```
bash <notify-skill-dir>/scripts/notify.sh "Title" "Message" "priority" "url" "run-id"
```

If the notify skill is not installed, Pipeline falls back to inline osascript:

```bash
osascript -e 'display notification "Message" with title "Title"'
```

## When Notifications Fire

| Event | Fires? | Priority |
|---|---|---|
| Dispatched worker completes | Yes | default |
| Dispatched worker fails | Yes | high |
| Worker asks IPC question | Yes | high |
| In-session phase completes | No | -- |
| Review finds issues | Yes | default |
| Fix loop exhausted (3 retries) | Yes | high |
| Gate reached | Yes | high |
| Pipeline complete | Yes | high |
| PRs created | Yes (with URLs) | high |

## Notification Grouping

Use `pipeline-<run-id>` as the group ID for all notifications in a run. This keeps related alerts together in notification center and allows clearing them as a unit.

## In-Session vs Background Work

Notifications are skipped for in-session phases because the user is actively watching the output. Notifications fire for Dispatch/background work where the user has moved away from the terminal.

## Installing terminal-notifier

```bash
brew install terminal-notifier
```

## Configuring ntfy.sh for Mobile Push

Set the `NTFY_TOPIC` environment variable to your ntfy.sh topic name:

```bash
export NTFY_TOPIC=your-topic-name
```

The notify skill will use this to forward high-priority notifications to your phone via ntfy.sh.
