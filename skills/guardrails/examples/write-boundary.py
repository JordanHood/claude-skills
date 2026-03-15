#!/usr/bin/env python3
"""PreToolUse hook for Edit and Write tools.

Blocks file modifications outside the current project directory and /tmp.
Prevents writes to sensitive system and user configuration paths.
Allows additional paths via CLAUDE_ALLOWED_WRITE_PATHS env var (colon-separated).

Behaviour:
- System paths (/etc, /usr, /System, ~/.ssh, ~/.aws): hard deny always
- ~/.claude config in worker sessions: hard deny (workers must not self-modify)
- Other out-of-boundary paths: ask for permission (user can approve)

Worker detection: if /tmp/claude-workers/<session_id>.meta exists, the session
is a Dispatch/Session Driver worker and gets stricter boundaries.

Customise:
- ALWAYS_DENIED: paths that are never writable
- WORKER_DENIED: additional paths blocked for worker sessions
- ALWAYS_ALLOWED: paths that are always writable (in addition to CWD)
- CLAUDE_ALLOWED_WRITE_PATHS env var: colon-separated additional writable paths
"""

import json
import os
import sys

HOME = os.path.expanduser("~")

# --- CUSTOMISE THESE ---
ALWAYS_DENIED = [
    "/etc/", "/usr/", "/var/",
    "/System/", "/Library/",
    os.path.join(HOME, ".ssh"),
    os.path.join(HOME, ".aws"),
    os.path.join(HOME, ".gnupg"),
]

WORKER_DENIED = [
    os.path.join(HOME, ".claude/hooks"),
    os.path.join(HOME, ".claude/settings.json"),
    os.path.join(HOME, ".claude/settings.local.json"),
    os.path.join(HOME, ".claude/CLAUDE.md"),
]

ALWAYS_ALLOWED = [
    "/tmp/",
    "/private/tmp/",
    os.path.join(HOME, ".claude"),
]
# --- END CUSTOMISE ---


def deny(reason):
    json.dump({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }, sys.stdout)
    sys.exit(0)


def ask(reason):
    json.dump({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": reason,
        }
    }, sys.stdout)
    sys.exit(0)


def is_worker_session(session_id):
    """Detect if this is a Dispatch/Session Driver worker."""
    if not session_id:
        return False
    return os.path.exists(f"/tmp/claude-workers/{session_id}.meta")


def get_allowed_roots():
    roots = [os.path.realpath(os.getcwd())]
    for p in ALWAYS_ALLOWED:
        roots.append(os.path.realpath(p))
    extra = os.environ.get("CLAUDE_ALLOWED_WRITE_PATHS", "")
    if extra:
        for p in extra.split(":"):
            p = p.strip()
            if p:
                roots.append(os.path.realpath(os.path.expanduser(p)))
    return roots


def main():
    data = json.load(sys.stdin)
    tool_name = data.get("tool_name", "")

    if tool_name not in ("Edit", "Write", "MultiEdit"):
        return

    file_path = data.get("tool_input", {}).get("file_path", "")
    if not file_path:
        return

    resolved = os.path.realpath(os.path.expanduser(file_path))
    session_id = data.get("session_id", "")

    for blocked in ALWAYS_DENIED:
        blocked_resolved = os.path.realpath(blocked)
        if resolved == blocked_resolved or resolved.startswith(blocked_resolved + "/") or resolved.startswith(blocked_resolved):
            deny(f"Write to system path denied: {blocked}")

    if is_worker_session(session_id):
        for blocked in WORKER_DENIED:
            blocked_resolved = os.path.realpath(blocked)
            if resolved == blocked_resolved or resolved.startswith(blocked_resolved + "/") or resolved.startswith(blocked_resolved):
                deny(f"Worker cannot modify Claude config: {blocked}")

    allowed_roots = get_allowed_roots()
    for root in allowed_roots:
        if resolved == root or resolved.startswith(root + "/"):
            return

    ask(
        f"Write outside project boundary: {file_path}. "
        f"Allowed roots: {', '.join(allowed_roots)}. "
        f"Approve this write?"
    )


if __name__ == "__main__":
    main()
