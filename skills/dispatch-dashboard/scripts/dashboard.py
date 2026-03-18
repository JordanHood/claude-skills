#!/usr/bin/env python3
"""Dispatch dashboard server.

Serves a live HTML dashboard that monitors dispatch worker progress by
reading .dispatch/tasks/*/plan.md files and checking IPC directories.
"""

import json
import os
import re
import signal
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
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


def get_ipc_question(ipc_dir):
    if not ipc_dir.is_dir():
        return None
    questions = sorted(ipc_dir.glob("*.question"))
    for q in reversed(questions):
        seq = q.stem
        if not (ipc_dir / f"{seq}.answer").exists():
            return q.read_text().strip()
    return None


def scan_tasks(tasks_dir):
    tasks = []
    agg = {
        "total_items": 0,
        "done_items": 0,
        "running": 0,
        "blocked": 0,
        "complete": 0,
        "error": 0,
    }

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


def get_html():
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Dispatch Dashboard</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'SF Mono', 'Fira Code', monospace;
    background: #0a0a0f;
    color: #c8c8d0;
    padding: 24px;
    min-height: 100vh;
  }
  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 24px;
    padding-bottom: 16px;
    border-bottom: 1px solid #1a1a2e;
  }
  .header h1 { font-size: 16px; font-weight: 600; color: #e0e0e8; letter-spacing: 0.5px; }
  .header .meta { font-size: 12px; color: #606078; }
  .aggregate {
    display: flex;
    gap: 24px;
    margin-bottom: 24px;
    padding: 16px;
    background: #0f0f18;
    border: 1px solid #1a1a2e;
    border-radius: 8px;
  }
  .aggregate .stat { display: flex; flex-direction: column; gap: 4px; }
  .aggregate .stat-value { font-size: 24px; font-weight: 700; color: #e0e0e8; }
  .aggregate .stat-label { font-size: 11px; text-transform: uppercase; letter-spacing: 1px; color: #606078; }
  .aggregate .progress-bar-outer { flex: 1; display: flex; align-items: center; min-width: 200px; }
  .aggregate .progress-bar-bg { width: 100%; height: 6px; background: #1a1a2e; border-radius: 3px; overflow: hidden; }
  .aggregate .progress-bar-fill { height: 100%; background: linear-gradient(90deg, #3b82f6, #60a5fa); border-radius: 3px; transition: width 0.5s ease; }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(420px, 1fr));
    gap: 16px;
  }
  .card {
    background: #0f0f18;
    border: 1px solid #1a1a2e;
    border-radius: 8px;
    padding: 16px;
    transition: border-color 0.2s;
  }
  .card:hover { border-color: #2a2a4e; }
  .card.status-complete { border-left: 3px solid #22c55e; }
  .card.status-running { border-left: 3px solid #3b82f6; }
  .card.status-blocked { border-left: 3px solid #f59e0b; }
  .card.status-error { border-left: 3px solid #ef4444; }
  .card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
  .card-title { font-size: 14px; font-weight: 600; color: #e0e0e8; }
  .card-badge { font-size: 10px; padding: 2px 8px; border-radius: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }
  .badge-running { background: #1e3a5f; color: #60a5fa; }
  .badge-complete { background: #14532d; color: #4ade80; }
  .badge-blocked { background: #451a03; color: #fbbf24; }
  .badge-error { background: #450a0a; color: #f87171; }
  .card-progress { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
  .card-progress-bar { flex: 1; height: 4px; background: #1a1a2e; border-radius: 2px; overflow: hidden; }
  .card-progress-fill { height: 100%; border-radius: 2px; transition: width 0.5s ease; }
  .fill-running { background: #3b82f6; }
  .fill-complete { background: #22c55e; }
  .fill-blocked { background: #f59e0b; }
  .fill-error { background: #ef4444; }
  .card-progress-text { font-size: 12px; color: #808098; min-width: 36px; text-align: right; }
  .checklist { list-style: none; font-size: 12px; line-height: 1.8; }
  .checklist li { display: flex; align-items: center; gap: 8px; padding: 2px 0; }
  .check-icon { width: 14px; height: 14px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; font-size: 10px; }
  .check-done { color: #22c55e; }
  .check-current { color: #3b82f6; }
  .check-pending { color: #2a2a4e; }
  .check-blocked { color: #f59e0b; }
  .check-error { color: #ef4444; }
  .item-done { color: #606078; text-decoration: line-through; }
  .item-current { color: #e0e0e8; font-weight: 500; }
  .item-pending { color: #4a4a60; }
  .item-blocked { color: #fbbf24; }
  .item-error { color: #f87171; }
  .card-footer { margin-top: 12px; padding-top: 10px; border-top: 1px solid #1a1a2e; font-size: 11px; color: #606078; }
  .ipc-alert {
    margin-top: 10px;
    padding: 8px 12px;
    background: #1a1503;
    border: 1px solid #3d3200;
    border-radius: 6px;
    font-size: 12px;
    color: #fbbf24;
  }
  .ipc-alert strong { color: #fcd34d; }
  .pulse {
    display: inline-block;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #3b82f6;
    margin-right: 6px;
    animation: pulse 2s ease-in-out infinite;
  }
  @keyframes pulse {
    0%, 100% { opacity: 0.4; }
    50% { opacity: 1; }
  }
  .empty {
    text-align: center;
    padding: 80px 24px;
    color: #606078;
    font-size: 14px;
  }
  .empty-title { color: #808098; font-size: 16px; margin-bottom: 8px; }
</style>
</head>
<body>
<div class="header">
  <h1>dispatch</h1>
  <div class="meta"><span id="worker-count">0</span> workers -- polling every 2s -- <span id="clock"></span></div>
</div>
<div class="aggregate" id="aggregate">
  <div class="stat">
    <span class="stat-value"><span id="agg-done">0</span><span style="font-size:14px;color:#606078">/<span id="agg-total">0</span></span></span>
    <span class="stat-label">Items Complete</span>
  </div>
  <div class="stat">
    <span class="stat-value" id="agg-running">0</span>
    <span class="stat-label">Running</span>
  </div>
  <div class="stat">
    <span class="stat-value" id="agg-blocked">0</span>
    <span class="stat-label">Blocked</span>
  </div>
  <div class="stat">
    <span class="stat-value" id="agg-complete">0</span>
    <span class="stat-label">Complete</span>
  </div>
  <div class="stat">
    <span class="stat-value" id="agg-error">0</span>
    <span class="stat-label">Error</span>
  </div>
  <div class="progress-bar-outer">
    <div class="progress-bar-bg">
      <div class="progress-bar-fill" id="agg-bar" style="width: 0%"></div>
    </div>
  </div>
</div>
<div class="grid" id="grid"></div>
<div class="empty" id="empty">
  <div class="empty-title">Waiting for tasks...</div>
  Watching for plan files in .dispatch/tasks/
</div>
<script>
const ICONS = {
  done: '&#10003;',
  current: '&#9679;',
  pending: '&#9675;',
  blocked: '?',
  error: '!'
};

function fmt(secs) {
  const m = Math.floor(secs / 60);
  const s = secs % 60;
  return m + 'm ' + s + 's';
}

function esc(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

function renderCard(task) {
  const pct = task.total > 0 ? Math.round((task.done / task.total) * 100) : 0;
  const badgeContent = task.status === 'running'
    ? '<span class="pulse"></span>running'
    : task.status;

  let items = '';
  for (const it of task.items) {
    items += '<li><span class="check-icon check-' + it.state + '">' + ICONS[it.state] + '</span>'
      + '<span class="item-' + it.state + '">' + esc(it.text) + '</span></li>';
  }

  let ipc = '';
  if (task.ipc_question) {
    ipc = '<div class="ipc-alert"><strong>Question:</strong> ' + esc(task.ipc_question) + '</div>';
  }

  return '<div class="card status-' + task.status + '" data-id="' + task.id + '">'
    + '<div class="card-header">'
    + '<span class="card-title">' + esc(task.id) + '</span>'
    + '<span class="card-badge badge-' + task.status + '">' + badgeContent + '</span>'
    + '</div>'
    + '<div class="card-progress">'
    + '<div class="card-progress-bar"><div class="card-progress-fill fill-' + task.status + '" style="width:' + pct + '%"></div></div>'
    + '<span class="card-progress-text">' + task.done + '/' + task.total + '</span>'
    + '</div>'
    + '<ul class="checklist">' + items + '</ul>'
    + ipc
    + '<div class="card-footer">' + fmt(task.elapsed_seconds) + '</div>'
    + '</div>';
}

function update(data) {
  const agg = data.aggregate;
  document.getElementById('agg-done').textContent = agg.done_items;
  document.getElementById('agg-total').textContent = agg.total_items;
  document.getElementById('agg-running').textContent = agg.running;
  document.getElementById('agg-blocked').textContent = agg.blocked;
  document.getElementById('agg-complete').textContent = agg.complete;
  document.getElementById('agg-error').textContent = agg.error;
  document.getElementById('worker-count').textContent = data.tasks.length;

  const pct = agg.total_items > 0 ? Math.round((agg.done_items / agg.total_items) * 100) : 0;
  document.getElementById('agg-bar').style.width = pct + '%';

  const grid = document.getElementById('grid');
  const empty = document.getElementById('empty');

  if (data.tasks.length === 0) {
    grid.style.display = 'none';
    empty.style.display = 'block';
    return;
  }

  grid.style.display = 'grid';
  empty.style.display = 'none';

  const existing = {};
  for (const card of grid.querySelectorAll('.card')) {
    existing[card.dataset.id] = card;
  }

  const seen = new Set();
  for (const task of data.tasks) {
    seen.add(task.id);
    const html = renderCard(task);
    const old = existing[task.id];
    if (old) {
      if (old.outerHTML !== html) {
        old.outerHTML = html;
      }
    } else {
      grid.insertAdjacentHTML('beforeend', html);
    }
  }

  for (const [id, card] of Object.entries(existing)) {
    if (!seen.has(id)) card.remove();
  }
}

function tick() {
  document.getElementById('clock').textContent = new Date().toLocaleTimeString();
}

async function poll() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    update(data);
  } catch (e) {}
}

tick();
setInterval(tick, 1000);
poll();
setInterval(poll, 2000);
</script>
</body>
</html>"""


class DashboardHandler(BaseHTTPRequestHandler):
    tasks_dir = None

    def do_GET(self):
        if self.path == "/":
            html = get_html()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(html.encode())
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

    monitor = threading.Thread(
        target=shutdown_monitor,
        args=(tasks_dir, dispatch_dir, server),
        daemon=True,
    )
    monitor.start()

    def shutdown_handler(signum, frame):
        cleanup_files(dispatch_dir)
        server.shutdown()

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
