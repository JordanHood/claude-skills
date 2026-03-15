#!/bin/bash
# Wrapper around claude -p that fires a notification on exit.
# Used as the Dispatch backend command instead of calling claude directly.
env -u CLAUDE_CODE_ENTRYPOINT -u CLAUDECODE claude -p --dangerously-skip-permissions "$@"
EXIT_CODE=$?

# Fire notification on worker completion
NOTIFY_SCRIPT=""
for p in ~/.claude/skills/notify/scripts/notify.sh ~/.agents/skills/notify/scripts/notify.sh; do
    [ -f "$p" ] && NOTIFY_SCRIPT="$p" && break
done

if [ -n "$NOTIFY_SCRIPT" ]; then
    bash "$NOTIFY_SCRIPT" "Worker Done" "Task complete (exit $EXIT_CODE)" "high"
else
    osascript -e "display notification \"Worker complete (exit $EXIT_CODE)\" with title \"Pipeline\" sound name \"Glass\""
fi

exit $EXIT_CODE
