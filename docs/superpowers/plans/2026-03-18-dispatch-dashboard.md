# Dispatch Dashboard Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a live browser dashboard that monitors dispatch worker progress by reading plan files and serving a local HTML page.

**Architecture:** Single Python script using stdlib `http.server`. Parses `.dispatch/tasks/*/plan.md` checkboxes, serves JSON API + inline HTML dashboard. Background thread handles auto-shutdown when all workers finish.

**Tech Stack:** Python 3 stdlib only (`http.server`, `pathlib`, `json`, `socket`, `os`, `re`, `signal`, `time`, `threading`, `webbrowser`, `urllib`)

**Spec:** `docs/superpowers/specs/2026-03-18-dispatch-dashboard-design.md`

---

## File Structure

```
skills/dispatch-dashboard/
  SKILL.md                -- skill frontmatter + usage docs (user-invocable)
  pspm.json               -- package metadata
  README.md               -- public docs
  scripts/
    dashboard.py          -- HTTP server, plan parser, HTML renderer, shutdown timer
```

`dashboard.py` is the only code file. It contains:
- Plan file parser (regex on markdown checkboxes)
- IPC question detector (glob for unanswered .question files)
- JSON API handler (`/api/status`)
- HTML template (inline string, the full dashboard UI)
- HTTP server (stdlib `http.server.HTTPServer`)
- Port negotiation + PID file management
- Auto-shutdown timer thread

---

### Task 1: Skill Scaffolding

**Files:**
- Create: `skills/dispatch-dashboard/SKILL.md`
- Create: `skills/dispatch-dashboard/pspm.json`
- Create: `skills/dispatch-dashboard/README.md`
- Create: `skills/dispatch-dashboard/scripts/` (directory)

- [ ] **Step 1: Create SKILL.md**

```markdown
---
name: dispatch-dashboard
description: "Live browser dashboard for monitoring dispatch workers. Shows real-time progress, blocked workers, IPC questions, and auto-shuts down when all tasks complete. Launch via script or include in dispatch scaffolding."
license: MIT
metadata:
  author: jordan.hood
  version: "0.1.0"
user_invocable: true
---

# Dispatch Dashboard

Live browser dashboard for monitoring dispatch worker progress.

## Usage

Start the dashboard server pointing at a dispatch tasks directory:

\`\`\`bash
python3 <skill-dir>/scripts/dashboard.py <tasks-dir> [--no-open]
\`\`\`

- `<tasks-dir>`: path to `.dispatch/tasks/` directory
- `--no-open`: skip auto-opening browser

The server binds to a free port on localhost, writes the port to `.dispatch/dashboard.port`, and opens the dashboard in your browser.

## Integration with Dispatch

Add to the dispatch scaffolding Bash call:

\`\`\`bash
if [ ! -f .dispatch/dashboard.port ] || ! curl -s -o /dev/null -w '' "http://localhost:$(cat .dispatch/dashboard.port)/api/status" 2>/dev/null; then
  rm -f .dispatch/dashboard.port .dispatch/dashboard.pid
  python3 <skill-dir>/scripts/dashboard.py .dispatch/tasks &
fi
\`\`\`

## Auto-Shutdown

The server monitors for `.done` markers in each task's IPC directory. Once all tasks have completed, it waits 60 seconds (grace period for reviewing final state) then exits and cleans up port/pid files.
```

- [ ] **Step 2: Create pspm.json**

```json
{
  "name": "dispatch-dashboard",
  "version": "0.1.0",
  "description": "Live browser dashboard for monitoring dispatch worker progress",
  "author": "jordan.hood",
  "license": "MIT",
  "agents": ["claude-code"],
  "optionalDependencies": {
    "dispatch": ">=2.0.0"
  },
  "keywords": ["dispatch", "dashboard", "monitoring", "workers", "progress"]
}
```

- [ ] **Step 3: Create README.md**

Brief public-facing README covering what the skill does, how to install, how to use. Keep it under 40 lines.

- [ ] **Step 4: Create scripts directory**

```bash
mkdir -p skills/dispatch-dashboard/scripts
```

- [ ] **Step 5: Commit scaffolding**

```bash
git add skills/dispatch-dashboard/SKILL.md skills/dispatch-dashboard/pspm.json skills/dispatch-dashboard/README.md skills/dispatch-dashboard/scripts/
git commit -m "feat: add dispatch-dashboard skill scaffolding"
```

---

### Task 2: Plan File Parser + JSON API

**Files:**
- Create: `skills/dispatch-dashboard/scripts/dashboard.py`

This task builds the data layer: reading plan files, parsing checkbox state, detecting IPC questions, and producing the JSON response object. No HTTP server yet -- just the functions.

- [ ] **Step 1: Write the plan parser function**

Function `parse_plan(plan_path: Path) -> dict` that:
- Reads a `plan.md` file
- Matches lines against regex: `r'^- \[([ x?!])\]\s+(.+)$'`
- First unchecked `[ ]` item gets state `current`, rest get `pending`
- `[x]` -> `done`, `[?]` -> `blocked`, `[!]` -> `error`
- For `[?]` and `[!]` items, captures the next line (if indented or non-checkbox) as `note`
- Returns `{"items": [...], "done": int, "total": int}`

```python
import re
from pathlib import Path

CHECKBOX_RE = re.compile(r"^- \[([ x?!])\]\s+(.+)$")

def parse_plan(plan_path):
    lines = plan_path.read_text().splitlines()
    items = []
    found_current = False

    for i, line in enumerate(lines):
        m = CHECKBOX_RE.match(line)
        if not m:
            continue
        marker, text = m.group(1), m.group(2)
        note = None

        if marker in ("?", "!"):
            if i + 1 < len(lines) and not CHECKBOX_RE.match(lines[i + 1]):
                note = lines[i + 1].strip()

        if marker == "x":
            state = "done"
        elif marker == "?":
            state = "blocked"
        elif marker == "!":
            state = "error"
        elif not found_current:
            state = "current"
            found_current = True
        else:
            state = "pending"

        item = {"text": text, "state": state}
        if note:
            item["note"] = note
        items.append(item)

    done_count = sum(1 for it in items if it["state"] == "done")
    return {"items": items, "done": done_count, "total": len(items)}
```

- [ ] **Step 2: Write the IPC question detector function**

Function `get_ipc_question(ipc_dir: Path) -> str | None` that:
- Globs `*.question` files in the IPC directory
- Filters out those with a matching `.answer` file
- Returns the content of the highest-numbered unanswered question, or `None`

```python
def get_ipc_question(ipc_dir):
    if not ipc_dir.is_dir():
        return None
    questions = sorted(ipc_dir.glob("*.question"))
    for q in reversed(questions):
        seq = q.stem
        if not (ipc_dir / f"{seq}.answer").exists():
            return q.read_text().strip()
    return None
```

- [ ] **Step 3: Write the task scanner function**

Function `scan_tasks(tasks_dir: Path) -> dict` that:
- Globs all subdirectories of `tasks_dir`
- For each, reads `plan.md` (skips if missing), calls `parse_plan`
- Calls `get_ipc_question` on the `ipc/` subdirectory
- Checks for `ipc/.done` marker
- Gets elapsed time from `plan.md` birthtime (`os.stat(path).st_birthtime`)
- Derives task-level status: complete (all done + .done marker), blocked (any [?]), error (any [!]), running (otherwise)
- Builds the full JSON response with per-task data and aggregate counts

```python
import os
import time

def scan_tasks(tasks_dir):
    tasks = []
    agg = {"total_items": 0, "done_items": 0, "running": 0, "blocked": 0, "complete": 0, "error": 0}

    if not tasks_dir.is_dir():
        return {"tasks": tasks, "aggregate": agg}

    for task_dir in sorted(tasks_dir.iterdir()):
        if not task_dir.is_dir():
            continue
        plan_path = task_dir / "plan.md"
        if not plan_path.exists():
            continue

        task_id = task_dir.name
        parsed = parse_plan(plan_path)
        ipc_dir = task_dir / "ipc"
        ipc_question = get_ipc_question(ipc_dir)
        has_done = (ipc_dir / ".done").exists()

        try:
            birth = os.stat(plan_path).st_birthtime
            elapsed = int(time.time() - birth)
        except AttributeError:
            elapsed = int(time.time() - os.stat(plan_path).st_mtime)

        states = [it["state"] for it in parsed["items"]]
        if parsed["done"] == parsed["total"] and parsed["total"] > 0 and has_done:
            status = "complete"
        elif "blocked" in states:
            status = "blocked"
        elif "error" in states:
            status = "error"
        else:
            status = "running"

        tasks.append({
            "id": task_id,
            "status": status,
            "items": parsed["items"],
            "done": parsed["done"],
            "total": parsed["total"],
            "ipc_question": ipc_question,
            "elapsed_seconds": elapsed,
            "has_done_marker": has_done,
        })

        agg["total_items"] += parsed["total"]
        agg["done_items"] += parsed["done"]
        agg[status] += 1

    return {"tasks": tasks, "aggregate": agg}
```

- [ ] **Step 4: Verify parser with a test plan file**

Create test data and run the parser via direct import to confirm output.

```bash
mkdir -p /tmp/test-dispatch/tasks/test-task/ipc
cat > /tmp/test-dispatch/tasks/test-task/plan.md << 'EOF'
# Test Task

- [x] First step done
- [x] Second step done
- [ ] Third step in progress
- [ ] Fourth step pending
EOF
cd skills/dispatch-dashboard
python3 -c "
import sys, json
sys.path.insert(0, 'scripts')
import dashboard
from pathlib import Path
result = dashboard.scan_tasks(Path('/tmp/test-dispatch/tasks'))
print(json.dumps(result, indent=2))
task = result['tasks'][0]
assert task['id'] == 'test-task', f'wrong id: {task[\"id\"]}'
assert task['done'] == 2, f'expected 2 done, got {task[\"done\"]}'
assert task['total'] == 4, f'expected 4 total, got {task[\"total\"]}'
assert task['status'] == 'running', f'expected running, got {task[\"status\"]}'
assert task['items'][2]['state'] == 'current', f'third item should be current'
assert task['items'][3]['state'] == 'pending', f'fourth item should be pending'
print('All assertions passed')
"
```

Expected: JSON output printed, followed by "All assertions passed".

- [ ] **Step 5: Commit parser and API functions**

```bash
git add skills/dispatch-dashboard/scripts/dashboard.py
git commit -m "feat: add plan parser, IPC detector, and task scanner"
```

---

### Task 3: HTTP Server + Port Negotiation

**Files:**
- Modify: `skills/dispatch-dashboard/scripts/dashboard.py`

Add the HTTP server, port negotiation, PID file management, and CLI argument parsing. This task makes the script runnable but serves only the JSON API (HTML comes in Task 4).

- [ ] **Step 1: Add the HTTP request handler**

Subclass `http.server.BaseHTTPRequestHandler`. Route `GET /` to a placeholder (just return "dashboard" text for now), `GET /api/status` to `scan_tasks` JSON output, everything else to 404.

```python
import json
from http.server import HTTPServer, BaseHTTPRequestHandler

class DashboardHandler(BaseHTTPRequestHandler):
    tasks_dir = None

    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h1>dashboard</h1>")
        elif self.path == "/api/status":
            data = scan_tasks(self.tasks_dir)
            body = json.dumps(data).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Not Found")

    def log_message(self, format, *args):
        pass
```

- [ ] **Step 2: Add port negotiation and PID management**

```python
import socket
import urllib.request

def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]

def is_dashboard_running(dispatch_dir):
    port_file = dispatch_dir / "dashboard.port"
    if not port_file.exists():
        return False
    try:
        port = int(port_file.read_text().strip())
        urllib.request.urlopen(f"http://127.0.0.1:{port}/api/status", timeout=2)
        return True
    except Exception:
        return False

def write_pid_and_port(dispatch_dir, port):
    (dispatch_dir / "dashboard.port").write_text(str(port))
    (dispatch_dir / "dashboard.pid").write_text(str(os.getpid()))

def cleanup_files(dispatch_dir):
    for f in ("dashboard.port", "dashboard.pid"):
        p = dispatch_dir / f
        if p.exists():
            p.unlink()
```

- [ ] **Step 3: Add CLI entry point with argument parsing**

```python
import sys
import webbrowser
import signal

def main():
    args = sys.argv[1:]
    no_open = "--no-open" in args
    args = [a for a in args if a != "--no-open"]

    if not args:
        print("Usage: dashboard.py <tasks-dir> [--no-open]", file=sys.stderr)
        sys.exit(1)

    tasks_dir = Path(args[0]).resolve()
    dispatch_dir = tasks_dir.parent
    tasks_dir.mkdir(parents=True, exist_ok=True)

    if is_dashboard_running(dispatch_dir):
        port = int((dispatch_dir / "dashboard.port").read_text().strip())
        print(f"Dashboard already running at http://127.0.0.1:{port}")
        sys.exit(0)

    port = find_free_port()
    DashboardHandler.tasks_dir = tasks_dir

    server = HTTPServer(("127.0.0.1", port), DashboardHandler)
    write_pid_and_port(dispatch_dir, port)

    def shutdown_handler(signum, frame):
        cleanup_files(dispatch_dir)
        server.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)

    url = f"http://127.0.0.1:{port}"
    print(f"Dispatch dashboard: {url}")
    if not no_open:
        webbrowser.open(url)

    try:
        server.serve_forever()
    finally:
        cleanup_files(dispatch_dir)

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Test the server manually**

```bash
python3 skills/dispatch-dashboard/scripts/dashboard.py /tmp/test-dispatch/tasks --no-open &
SERVER_PID=$!
sleep 1
curl -s http://127.0.0.1:$(cat /tmp/test-dispatch/dashboard.port)/api/status | python3 -m json.tool
kill $SERVER_PID
```

Expected: JSON output with one task (`test-task`), 2 done, 4 total, status `running`.

- [ ] **Step 5: Commit HTTP server**

```bash
git add skills/dispatch-dashboard/scripts/dashboard.py
git commit -m "feat: add HTTP server with port negotiation and JSON API"
```

---

### Task 4: Auto-Shutdown Timer

**Files:**
- Modify: `skills/dispatch-dashboard/scripts/dashboard.py`

Add the background thread that monitors for completion and shuts down the server after a grace period.

- [ ] **Step 1: Add the shutdown monitor thread**

```python
import threading

def shutdown_monitor(tasks_dir, dispatch_dir, server, grace_seconds=60):
    grace_start = None

    while True:
        time.sleep(5)
        task_dirs = [d for d in tasks_dir.iterdir() if d.is_dir()] if tasks_dir.is_dir() else []

        if not task_dirs:
            grace_start = None
            continue

        all_done = all((d / "ipc" / ".done").exists() for d in task_dirs)

        if all_done:
            if grace_start is None:
                grace_start = time.time()
            elif time.time() - grace_start >= grace_seconds:
                cleanup_files(dispatch_dir)
                server.shutdown()
                return
        else:
            grace_start = None
```

- [ ] **Step 2: Wire the thread into main()**

Add after server creation, before `serve_forever()`:

```python
    monitor = threading.Thread(
        target=shutdown_monitor,
        args=(tasks_dir, dispatch_dir, server),
        daemon=True,
    )
    monitor.start()
```

- [ ] **Step 3: Test auto-shutdown**

```bash
python3 skills/dispatch-dashboard/scripts/dashboard.py /tmp/test-dispatch/tasks --no-open &
sleep 2
# Mark the test task as done
touch /tmp/test-dispatch/tasks/test-task/ipc/.done
# Server should exit after ~65 seconds (5s check + 60s grace)
# For faster testing, temporarily set grace_seconds=5
```

- [ ] **Step 4: Commit shutdown timer**

```bash
git add skills/dispatch-dashboard/scripts/dashboard.py
git commit -m "feat: add auto-shutdown timer thread"
```

---

### Task 5: HTML Dashboard

**Files:**
- Modify: `skills/dispatch-dashboard/scripts/dashboard.py`

Replace the placeholder HTML with the full dashboard UI. This is the largest task -- the HTML/CSS/JS template string based on the approved mockup.

- [ ] **Step 1: Write the HTML template as a Python string**

Create a function `get_html() -> str` that returns the complete HTML document. Key elements:

- Dark theme CSS matching the mockup (`#0a0a0f` background, monospace font, card grid)
- Aggregate stats bar (total items, running/blocked/complete/error counts, progress bar)
- Card grid with responsive layout (`grid-template-columns: repeat(auto-fill, minmax(420px, 1fr))`)
- Card template with: title, status badge (pulsing dot for running), progress bar, checklist, elapsed time footer
- IPC question alert box (amber) for blocked tasks
- Colour coding: green=complete, blue=running, amber=blocked, red=error
- CSS classes for checklist item states: done (strikethrough, grey), current (white, bold), pending (dim), blocked (amber), error (red)
- JavaScript that:
  - Fetches `/api/status` every 2 seconds
  - Renders cards by diffing against current DOM (no full re-render flicker)
  - Updates clock in header
  - Formats elapsed seconds as `Xm Ys`

Use the mockup at `/tmp/dispatch-dashboard-mockup.html` as the CSS/layout reference. The JS needs to be dynamic (the mockup was static).

- [ ] **Step 2: Wire HTML into the request handler**

Replace the placeholder `GET /` response:

```python
    def do_GET(self):
        if self.path == "/":
            html = get_html()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(html.encode())
```

- [ ] **Step 3: Test the full dashboard end-to-end**

Set up a realistic test scenario:

```bash
# Create multiple test tasks with different states
mkdir -p /tmp/test-dispatch/tasks/auth-middleware/ipc
mkdir -p /tmp/test-dispatch/tasks/grpc-client/ipc
mkdir -p /tmp/test-dispatch/tasks/rate-limiter/ipc

cat > /tmp/test-dispatch/tasks/auth-middleware/plan.md << 'EOF'
# Auth Middleware
- [x] Extract JWT validation
- [x] Add token refresh logic
- [x] Wire into routes
EOF
touch /tmp/test-dispatch/tasks/auth-middleware/ipc/.done

cat > /tmp/test-dispatch/tasks/grpc-client/plan.md << 'EOF'
# gRPC Client
- [x] Generate TypeScript types
- [x] Implement channel pool
- [ ] Add retry logic
- [ ] Write unit tests
EOF

cat > /tmp/test-dispatch/tasks/rate-limiter/plan.md << 'EOF'
# Rate Limiter
- [x] Implement sliding window
- [?] Configure per-route limits
  Should /api/bookings and /api/availability have different limits?
- [ ] Add rate limit headers
EOF
echo "Should /api/bookings and /api/availability have different limits?" > /tmp/test-dispatch/tasks/rate-limiter/ipc/001.question

# Launch and verify in browser
python3 skills/dispatch-dashboard/scripts/dashboard.py /tmp/test-dispatch/tasks
```

Expected: browser opens showing 3 cards -- auth-middleware (complete/green), grpc-client (running/blue), rate-limiter (blocked/amber with question).

- [ ] **Step 4: Commit HTML dashboard**

```bash
git add skills/dispatch-dashboard/scripts/dashboard.py
git commit -m "feat: add full HTML dashboard with live polling"
```

---

### Task 6: Final Cleanup and Verification

**Files:**
- Modify: `skills/dispatch-dashboard/scripts/dashboard.py` (if needed)

- [ ] **Step 1: Clean up the /tmp test data**

```bash
rm -rf /tmp/test-dispatch /tmp/dispatch-dashboard-mockup.html
```

- [ ] **Step 2: Full end-to-end test with fresh data**

Create a clean test scenario, launch the dashboard, verify all states render correctly, verify auto-shutdown fires after marking all tasks done.

- [ ] **Step 3: Verify skill structure matches spec**

```
skills/dispatch-dashboard/
  SKILL.md
  pspm.json
  README.md
  scripts/
    dashboard.py
```

- [ ] **Step 4: Final commit if any cleanup was needed**

```bash
git add -A skills/dispatch-dashboard/
git commit -m "chore: final cleanup for dispatch-dashboard skill"
```
