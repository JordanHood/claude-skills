# dispatch-dashboard

Live browser dashboard for monitoring [dispatch](../dispatch/) worker progress in real time.

## What it does

- Shows a card per dispatch task with progress bar, checklist, and status
- Colour-coded: green (complete), blue (running), amber (blocked), red (error)
- Displays IPC questions from blocked workers
- Aggregate progress bar across all tasks
- Auto-shuts down 60s after all workers finish
- Port negotiation for multiple concurrent sessions

## Install

```bash
npx skills add dispatch-dashboard
```

## Usage

```bash
python3 <skill-dir>/scripts/dashboard.py .dispatch/tasks
```

Or integrate into dispatch scaffolding (see SKILL.md for the snippet).

## Requirements

- Python 3.8+ (stdlib only, no pip dependencies)
- macOS or Linux
