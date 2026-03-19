# Dispatch Dashboard

Live browser-based dashboard for monitoring dispatch workers across a project.

## Problem

Running 6-12 dispatch workers in parallel produces no visual feedback beyond reading plan files manually. There's no way to see aggregate progress, spot blocked workers, or know when everything is done without checking each task individually.

## Solution

A Python script (`scripts/dashboard.py`) that serves a local HTML dashboard showing real-time progress for all dispatch tasks in a project.

## Architecture

```
.dispatch/tasks/*/plan.md  --->  dashboard.py reads + parses
.dispatch/tasks/*/ipc/     --->  checks for unanswered .question files
                           --->  GET /api/status (JSON)
                           --->  browser polls every 2s, renders cards
```

Single file, zero dependencies beyond Python stdlib (`http.server`, `pathlib`, `json`, `socket`, `os`, `re`, `signal`, `time`).

## Script Interface

```bash
python3 <skill-dir>/scripts/dashboard.py <tasks-dir> [--no-open]
```

- `<tasks-dir>`: path to `.dispatch/tasks/` directory to watch
- `--no-open`: skip auto-opening browser (for headless/CI use)

## Port Negotiation

- Bind to `localhost:0` (127.0.0.1 only, not reachable from other machines) -- OS assigns a free port
- Write the port number to `<tasks-dir>/../dashboard.port` (i.e. `.dispatch/dashboard.port`)
- Write PID to `<tasks-dir>/../dashboard.pid`
- On startup, check if `.dispatch/dashboard.port` exists and that port is responsive. If so, skip launch (another dashboard is already running for this project)

## HTTP Routes

### `GET /`

Serves the HTML dashboard (`text/html`). All CSS and JS are inline -- single self-contained response. No external dependencies.

### `GET /api/status`

Returns JSON (`application/json`):

### All other routes

Returns `404 Not Found` with plain text body.


```json
{
  "tasks": [
    {
      "id": "auth-middleware",
      "status": "running|complete|blocked|error",
      "items": [
        { "text": "Extract JWT validation", "state": "done|current|pending|blocked|error", "note": "optional note" }
      ],
      "done": 3,
      "total": 5,
      "ipc_question": null,
      "elapsed_seconds": 247,
      "has_done_marker": false
    }
  ],
  "aggregate": {
    "total_items": 32,
    "done_items": 19,
    "running": 4,
    "blocked": 1,
    "complete": 1,
    "error": 0
  }
}
```

## Plan File Parsing

Reads each `plan.md` and parses checkbox lines:

| Pattern | State |
|---------|-------|
| `- [x]` | done |
| `- [ ]` (first unchecked) | current |
| `- [ ]` (subsequent) | pending |
| `- [?]` | blocked |
| `- [!]` | error |

Task-level status derived from items:
- All items done + `.done` marker exists -> `complete`
- Any item `[?]` -> `blocked`
- Any item `[!]` -> `error`
- Otherwise -> `running`

Text after the checkbox marker is the item description. Text on the line after `[?]` or `[!]` items (indented or as a note) is captured as the `note` field.

## IPC Question Detection

For blocked tasks, reads `.dispatch/tasks/<id>/ipc/*.question` files that don't have a matching `.answer` file. If multiple unanswered questions exist, returns the highest-numbered one (latest). The question content is returned in `ipc_question` as a string (nullable).

## Task ID

The task ID is the directory name under `tasks/` (e.g. `.dispatch/tasks/auth-middleware/` -> `"auth-middleware"`).

## Elapsed Time

Uses the `plan.md` file's birth time (`st_birthtime` on macOS via `os.stat`). This survives checkbox updates that change mtime. Elapsed = now - birthtime.

## Auto-Shutdown

The done marker path is `.dispatch/tasks/<id>/ipc/.done` (written by dispatch workers per the dispatch skill protocol).

- A server-side timer thread checks every 5 seconds whether all task directories have an `ipc/.done` marker
- This runs independently of browser polling -- shutdown works even if the tab is closed
- Once all tasks are done, start a 60-second grace timer
- If a new task directory appears during grace, cancel the timer
- After grace expires, clean up `.dispatch/dashboard.port` and `.dispatch/dashboard.pid`, then exit

## HTML Dashboard

Design matches the approved mockup:

- Dark theme (`#0a0a0f` background, monospace font)
- Aggregate bar at top: items complete, running/blocked/complete/error counts, progress bar
- Card grid (responsive, `min-width: 420px` per card)
- Cards colour-coded by status: green (complete), blue (running), amber (blocked), red (error)
- Pulsing dot on running tasks
- Checklist with state-coloured icons
- Blocked tasks show IPC question in an amber alert box
- Footer per card: elapsed time
- Polls `/api/status` every 2 seconds via `fetch()`
- Updates DOM in-place (no full re-render flicker)

## Integration with Dispatch Skill

The dispatch skill's scaffolding Bash call adds:

```bash
if [ ! -f .dispatch/dashboard.port ] || ! curl -s -o /dev/null -w '' "http://localhost:$(cat .dispatch/dashboard.port)/api/status" 2>/dev/null; then
  rm -f .dispatch/dashboard.port .dispatch/dashboard.pid
  python3 <skill-dir>/scripts/dashboard.py .dispatch/tasks &
fi
```

Detection uses an HTTP health check against the port (not just PID liveness) to avoid false positives from recycled PIDs. Starts the dashboard on first dispatch, skips on subsequent dispatches in the same project.

## Skill Structure

```
skills/dispatch-dashboard/
  SKILL.md              -- frontmatter + usage docs
  pspm.json             -- package metadata
  scripts/
    dashboard.py        -- the server
  README.md             -- public docs
```

## Failure Modes

- **tasks-dir doesn't exist yet**: create it, serve empty dashboard, wait for tasks to appear
- **plan.md malformed**: skip unparseable lines, show what we can
- **Port file stale** (process died without cleanup): detect via HTTP health check to `/api/status`, clean up `.port`/`.pid` and start fresh
- **Browser doesn't open**: print URL to stdout, user can open manually
