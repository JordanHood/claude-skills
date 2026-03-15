#!/usr/bin/env python3
"""PreToolUse hook for all Bash commands.

Blocks:
- Direct CLI tool invocation (vitest, eslint, tsc, prettier, jest)
- Commits on protected branches (main, master, staging)
- Commits when lint or tests fail
- Pushes from protected branches or branches tracking protected remotes
- Destructive commands (git reset --hard, git push --force, git clean -f)
- Writes to sensitive system/user paths
- Reading credential files (~/.ssh, ~/.aws, ~/.gnupg)
- Publishing packages (npm publish, pnpm publish)
- Dangerous system commands (launchctl, crontab, docker rm/stop)

Customise:
- BLOCKED_TOOLS: CLI tools that should use package.json scripts
- PROTECTED_BRANCHES: branches that block direct commits/pushes
- SENSITIVE_PATHS: paths that block writes
- CREDENTIAL_READ_PATHS: paths that block reads
- DESTRUCTIVE_DENY_PATTERNS: commands that are always blocked
- DESTRUCTIVE_ASK_PATTERNS: commands that prompt for confirmation
"""

import json
import os
import re
import subprocess
import sys

# --- CUSTOMISE THESE ---
BLOCKED_TOOLS = {"vitest", "eslint", "tsc", "prettier", "jest"}
TOOL_PREFIXES = {"npx", "pnpm exec", "pnpm dlx"}
PROTECTED_BRANCHES = {"staging", "main", "master"}

HOME = os.path.expanduser("~")

SENSITIVE_PATHS = [
    "/etc/", "/usr/local/etc/", "/var/",
    "/System/", "/Library/",
    os.path.join(HOME, ".ssh"),
    os.path.join(HOME, ".aws"),
    os.path.join(HOME, ".gnupg"),
]

CLAUDE_CONFIG_PATHS = [
    os.path.join(HOME, ".claude/hooks"),
    os.path.join(HOME, ".claude/settings.json"),
    os.path.join(HOME, ".claude/settings.local.json"),
    os.path.join(HOME, ".claude/CLAUDE.md"),
]

CREDENTIAL_READ_PATHS = [
    os.path.join(HOME, ".ssh"),
    os.path.join(HOME, ".aws"),
    os.path.join(HOME, ".gnupg"),
    os.path.join(HOME, ".npmrc"),
    os.path.join(HOME, ".netrc"),
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


def run(cmd, cwd=None):
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return result.returncode, result.stdout.strip()


def strip_env_vars(s):
    """Remove leading KEY=value assignments from a command string."""
    while re.match(r'^[A-Za-z_]\w*=\S+\s+', s):
        s = re.sub(r'^[A-Za-z_]\w*=\S+\s+', '', s)
    return s


def resolve_path(p, work_dir=None):
    """Resolve a path to absolute, expanding ~ and relative refs."""
    p = p.strip().strip("'\"")
    p = os.path.expanduser(p)
    if not os.path.isabs(p):
        base = work_dir or os.getcwd()
        p = os.path.join(base, p)
    return os.path.realpath(p)


def path_touches_sensitive(path_str, work_dir=None):
    """Check if a path resolves to or falls under a sensitive location."""
    try:
        resolved = resolve_path(path_str, work_dir)
    except (ValueError, OSError):
        return None
    for sp in SENSITIVE_PATHS:
        sp_resolved = os.path.realpath(os.path.expanduser(sp))
        if resolved == sp_resolved or resolved.startswith(sp_resolved + "/") or sp_resolved.startswith(resolved + "/"):
            return sp
    return None


def path_reads_credentials(path_str, work_dir=None):
    """Check if a path resolves to a credential location."""
    try:
        resolved = resolve_path(path_str, work_dir)
    except (ValueError, OSError):
        return None
    for cp in CREDENTIAL_READ_PATHS:
        cp_resolved = os.path.realpath(os.path.expanduser(cp))
        if resolved == cp_resolved or resolved.startswith(cp_resolved + "/"):
            return cp
    return None


WRITE_COMMANDS = {"cp", "mv", "install", "tee", "touch", "mkdir", "ln", "rsync", "scp"}
READ_COMMANDS = {"cat", "less", "more", "head", "tail", "bat", "open"}
REDIRECT_PATTERN = re.compile(r'[12]?\s*>>?\s*(\S+)')


def is_worker_session(session_id):
    """Detect if this is a Dispatch/Session Driver worker."""
    if not session_id:
        return False
    return os.path.exists(f"/tmp/claude-workers/{session_id}.meta")


def path_touches_claude_config(path_str, work_dir=None):
    try:
        resolved = resolve_path(path_str, work_dir)
    except (ValueError, OSError):
        return None
    for cp in CLAUDE_CONFIG_PATHS:
        cp_resolved = os.path.realpath(os.path.expanduser(cp))
        if resolved == cp_resolved or resolved.startswith(cp_resolved + "/") or cp_resolved.startswith(resolved + "/"):
            return cp
    return None


def check_sensitive_paths(cmd, session_id=""):
    """Block writes to sensitive paths and reads of credential files."""
    worker = is_worker_session(session_id)
    parts = re.split(r'\s*(?:&&|\|\||;|\|)\s*', cmd)
    for part in parts:
        stripped = strip_env_vars(part.strip())
        words = stripped.split()
        if not words:
            continue

        base_cmd = os.path.basename(words[0])

        if base_cmd in WRITE_COMMANDS and len(words) > 1:
            for arg in words[1:]:
                if arg.startswith("-"):
                    continue
                hit = path_touches_sensitive(arg)
                if hit:
                    ask(f"Write to sensitive path: {hit}. Allow?")
                config_hit = path_touches_claude_config(arg)
                if config_hit:
                    if worker:
                        deny(f"Worker cannot modify Claude config: {config_hit}")
                    else:
                        ask(f"Write to Claude config: {config_hit}. Allow?")

        if base_cmd in READ_COMMANDS and len(words) > 1:
            for arg in words[1:]:
                if arg.startswith("-"):
                    continue
                hit = path_reads_credentials(arg)
                if hit:
                    ask(f"Reading credential file: {hit}. Allow?")

        redirects = REDIRECT_PATTERN.findall(stripped)
        for target in redirects:
            hit = path_touches_sensitive(target)
            if hit:
                ask(f"Redirect to sensitive path: {hit}. Allow?")
            config_hit = path_touches_claude_config(target)
            if config_hit:
                if worker:
                    deny(f"Worker cannot redirect to Claude config: {config_hit}")
                else:
                    ask(f"Redirect to Claude config: {config_hit}. Allow?")


DENIED_COMMANDS = [
    (r'\bnpm\s+publish\b', "npm publish blocked. Publish manually."),
    (r'\bpnpm\s+publish\b', "pnpm publish blocked. Publish manually."),
    (r'\byarn\s+publish\b', "yarn publish blocked. Publish manually."),
    (r'\blaunchctl\s+(load|unload|submit|bootstrap)\b', "launchctl service modification blocked."),
    (r'\bcrontab\s+-[er]', "crontab modification blocked."),
    (r'\bchmod\b.*\b(\/etc|\/usr|\/System)', "chmod on system paths blocked."),
    (r'(?i)\bDROP\s+(TABLE|DATABASE)\b', "DROP TABLE/DATABASE blocked. Run destructive SQL manually."),
    (r'(?i)\bTRUNCATE\s+TABLE\b', "TRUNCATE TABLE blocked. Run destructive SQL manually."),
]

ASK_COMMANDS = [
    (r'\bdocker\s+(rm|stop|kill|system\s+prune)\b', "Destructive docker command. Allow?"),
    (r'\bkill\s+-9\b', "kill -9 signal. Allow?"),
    (r'\bkillall\b', "killall command. Allow?"),
    (r'\bchown\b', "chown command. Allow?"),
    (r'\bcurl\b.*(-X\s*P(UT|OST|ATCH)|--data|--upload-file|-d\b)', "Outbound data submission via curl. Allow?"),
    (r'\bwget\s+--post', "Outbound POST via wget. Allow?"),
]


def check_blocked_commands(cmd):
    """Block or prompt for dangerous system commands and data exfiltration."""
    for pattern, reason in DENIED_COMMANDS:
        if re.search(pattern, cmd, re.IGNORECASE):
            deny(reason)
    for pattern, reason in ASK_COMMANDS:
        if re.search(pattern, cmd, re.IGNORECASE):
            ask(reason)


def check_cli_tools(cmd):
    """Block direct invocation of CLI tools that should use npm/pnpm scripts."""
    parts = re.split(r'\s*(?:&&|\|\||;)\s*', cmd)
    for part in parts:
        stripped = strip_env_vars(part.strip())
        words = stripped.split()
        if not words:
            continue
        first = os.path.basename(words[0])
        if first in BLOCKED_TOOLS:
            deny("Do not run CLI tools directly. Use package manager scripts (e.g. npm test, pnpm run lint).")
        for prefix in TOOL_PREFIXES:
            pw = prefix.split()
            if words[:len(pw)] == pw and len(words) > len(pw) and words[len(pw)] in BLOCKED_TOOLS:
                deny("Do not run CLI tools directly. Use package manager scripts (e.g. npm test, pnpm run lint).")


DESTRUCTIVE_DENY_PATTERNS = [
    (r'\bgit\s+reset\s+--hard\b', "git reset --hard is blocked. Use git stash or git checkout instead."),
    (r'\bgit\s+push\s+.*--force(?!-with-lease)\b', "git push --force is blocked. Use --force-with-lease or push manually."),
    (r'\bgit\s+push\s+.*(?<!\w)-f\b', "git push -f is blocked. Use --force-with-lease or push manually."),
    (r'\bgit\s+clean\s+-[a-zA-Z]*f', "git clean -f is blocked. Clean files manually if needed."),
    (r'\bgit\s+checkout\s+--\s+\.', "git checkout -- . is blocked. Discard changes on specific files instead."),
    (r'\bgit\s+restore\s+--staged\s+--worktree\s+\.', "Bulk git restore is blocked. Restore specific files instead."),
]

DESTRUCTIVE_ASK_PATTERNS = [
    (r'\brm\s+(-[a-zA-Z]*r[a-zA-Z]*f|(-[a-zA-Z]*f[a-zA-Z]*r))\b', "rm -rf detected. Allow?"),
    (r'\brm\s+-[a-zA-Z]*r\b.*/', "Recursive rm on directories. Allow?"),
]


def check_destructive(cmd):
    """Block or prompt for destructive commands."""
    for pattern, reason in DESTRUCTIVE_DENY_PATTERNS:
        if re.search(pattern, cmd):
            deny(reason)
    for pattern, reason in DESTRUCTIVE_ASK_PATTERNS:
        if re.search(pattern, cmd):
            ask(reason)


def get_work_dir(cmd):
    """Extract cd target from compound command and return it, or None."""
    if cmd.startswith("cd "):
        match = re.match(r'^cd\s+([^\s&;|]+)', cmd)
        if match:
            d = match.group(1)
            if os.path.isdir(d):
                return d
    return None


def get_branch(cwd=None):
    rc, out = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd)
    return out if rc == 0 else None


def get_upstream(cwd=None):
    rc, out = run(["git", "rev-parse", "--abbrev-ref", "@{upstream}"], cwd=cwd)
    return out if rc == 0 else None


def detect_package_manager(cwd=None):
    d = cwd or "."
    if os.path.exists(os.path.join(d, "pnpm-lock.yaml")):
        return "pnpm"
    if os.path.exists(os.path.join(d, "yarn.lock")):
        return "yarn"
    return "npm"


def check_commit(cmd, work_dir):
    """Block commits on protected branches and when lint/tests fail."""
    if re.search(r'git (checkout|switch)', cmd):
        match = re.search(r'git (?:checkout|switch)\s+(?:-[bBq]\s+)*(\S+)', cmd)
        if match:
            target = match.group(1)
            if target in PROTECTED_BRANCHES:
                deny(f"Command checks out and commits on protected branch '{target}'. Use a feature branch.")
    else:
        branch = get_branch(work_dir)
        if branch in PROTECTED_BRANCHES:
            deny(f"Direct commit on protected branch '{branch}'. Use a feature branch.")

    pkg = os.path.join(work_dir, "package.json") if work_dir else "package.json"
    if os.path.exists(pkg):
        pm = detect_package_manager(work_dir)

        rc, out = run([pm, "run", "lint"], cwd=work_dir)
        if rc != 0:
            lines = out.splitlines()[-30:]
            print("\n".join(lines), file=sys.stderr)
            deny("Lint failed. Fix errors before committing.")

        rc, out = run([pm, "test"], cwd=work_dir)
        if rc != 0:
            lines = out.splitlines()[-30:]
            print("\n".join(lines), file=sys.stderr)
            deny("Tests failed. Fix failures before committing.")


def check_push(cmd, work_dir):
    """Block pushes from/to protected branches."""
    branch = get_branch(work_dir)
    if branch in PROTECTED_BRANCHES:
        deny(f"Direct push from protected branch '{branch}'. Use a feature branch and PR.")

    upstream = get_upstream(work_dir)
    if upstream:
        remote_branch = upstream.split("/", 1)[-1] if "/" in upstream else upstream
        if remote_branch in PROTECTED_BRANCHES:
            deny(f"Branch '{branch}' tracks '{upstream}'. Push to a feature remote branch instead.")


def main():
    data = json.load(sys.stdin)
    cmd = data.get("tool_input", {}).get("command", "")
    session_id = data.get("session_id", "")

    if not cmd:
        return

    check_cli_tools(cmd)
    check_destructive(cmd)
    check_sensitive_paths(cmd, session_id)
    check_blocked_commands(cmd)

    if not re.search(r'git (commit|push)|gw (commit|push)', cmd):
        return

    work_dir = get_work_dir(cmd)

    if re.search(r'git commit|gw commit', cmd):
        check_commit(cmd, work_dir)

    if re.search(r'git push|gw push', cmd):
        check_push(cmd, work_dir)


if __name__ == "__main__":
    main()
