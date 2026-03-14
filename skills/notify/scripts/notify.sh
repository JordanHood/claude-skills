#!/bin/bash
# Notification helper for Claude Code skills
# Fire-and-forget: errors in notification delivery are silently ignored.
# Usage: notify.sh "Title" "Message" [priority] [url] [run-id]
# Priority: default, high, urgent
# URL: clickable link (terminal-notifier only)
# Run ID: notification group ID (terminal-notifier only)

TITLE="${1:-Claude Code}"
MESSAGE="${2:-Task complete}"
PRIORITY="${3:-default}"
URL="${4:-}"
RUN_ID="${5:-default}"

# terminal-notifier (primary -- clickable, groupable, rich)
if command -v terminal-notifier &>/dev/null; then
  SOUND=""
  [ "$PRIORITY" = "high" ] || [ "$PRIORITY" = "urgent" ] && SOUND="-sound Glass"
  terminal-notifier -title "$TITLE" -message "$MESSAGE" $SOUND \
    ${URL:+-open "$URL"} -group "claude-${RUN_ID}" || true
# osascript (fallback -- basic macOS notification)
else
  SOUND_NAME=""
  [ "$PRIORITY" = "high" ] || [ "$PRIORITY" = "urgent" ] && SOUND_NAME='sound name "Glass"'
  osascript -e "display notification \"$MESSAGE\" with title \"$TITLE\" $SOUND_NAME" || true
fi

# ntfy.sh (mobile push -- only on high/urgent priority, only if configured)
if [ "$PRIORITY" = "high" ] || [ "$PRIORITY" = "urgent" ]; then
  if [ -n "$NTFY_TOPIC" ]; then
    NTFY_PRIORITY="high"
    [ "$PRIORITY" = "urgent" ] && NTFY_PRIORITY="urgent"
    curl -s -H "Title: $TITLE" -H "Priority: $NTFY_PRIORITY" \
      ${URL:+-H "Click: $URL"} \
      -d "$MESSAGE" "ntfy.sh/$NTFY_TOPIC" >/dev/null 2>&1 &
  fi
fi
