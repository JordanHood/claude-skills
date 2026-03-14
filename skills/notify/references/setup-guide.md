# Notify Skill Setup Guide

## Quick start (no install needed)

The notify skill works immediately on macOS using `osascript`. No setup required.

## Recommended: install terminal-notifier

For clickable notifications, grouping, and better UX:

```bash
brew install terminal-notifier
```

After install, you may need to grant notification permissions:
1. Open System Settings > Notifications
2. Find "terminal-notifier" in the list
3. Enable "Allow Notifications"

## Optional: mobile push via ntfy.sh

For notifications on your phone when away from your desk:

1. Install the ntfy app:
   - iOS: App Store, search "ntfy"
   - Android: Google Play or F-Droid, search "ntfy"

2. Open the app and subscribe to a topic (use something unique):
   - e.g., `jordan-claude-pipeline-abc123`

3. Set the environment variable in your shell or Claude settings:
   ```bash
   # In ~/.zshrc
   export NTFY_TOPIC="jordan-claude-pipeline-abc123"

   # Or in ~/.claude/settings.json
   "env": { "NTFY_TOPIC": "jordan-claude-pipeline-abc123" }
   ```

4. Test it:
   ```bash
   curl -d "Test notification" ntfy.sh/jordan-claude-pipeline-abc123
   ```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| No notification appears | Check System Settings > Notifications. Ensure terminal app has permission. |
| terminal-notifier not found after install | Run `brew link terminal-notifier` or check PATH |
| ntfy notifications not arriving on phone | Check you subscribed to the exact same topic name |
| Sound not playing | Check system volume and Do Not Disturb settings |
