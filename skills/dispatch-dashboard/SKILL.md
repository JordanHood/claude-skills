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

```bash
python3 <skill-dir>/scripts/dashboard.py <tasks-dir> [--no-open]
```

- `<tasks-dir>`: path to `.dispatch/tasks/` directory
- `--no-open`: skip auto-opening browser

The server binds to a free port on localhost, writes the port to `.dispatch/dashboard.port`, and opens the dashboard in your browser.

## Integration with Dispatch

Add to the dispatch scaffolding Bash call:

```bash
if [ ! -f .dispatch/dashboard.port ] || ! curl -s -o /dev/null -w '' "http://localhost:$(cat .dispatch/dashboard.port)/api/status" 2>/dev/null; then
  rm -f .dispatch/dashboard.port .dispatch/dashboard.pid
  python3 <skill-dir>/scripts/dashboard.py .dispatch/tasks &
fi
```

## Auto-Shutdown

The server monitors for `.done` markers in each task's IPC directory. Once all tasks have completed, it waits 60 seconds (grace period for reviewing final state) then exits and cleans up port/pid files.
