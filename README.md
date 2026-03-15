# Claude Skills

A collection of Claude Code skills for autonomous development workflows.

## Skills

### pipeline

Autonomous development pipeline that orchestrates research, design, planning, parallel implementation, review, and PR creation from a single goal prompt.

**Install:**
```bash
pspm install <user>/claude-skills/pipeline
```

**Usage:** Triggers ambiently on multi-phase tasks, or invoke manually with `/pipeline`.

```
"Build custom TypeSpec decorators for JSON Schema conditionals end to end"

Pipeline proposes:
  1. Research via Gemini
  2. Brainstorm decorator design
  3. Write implementation plan
  4. Dispatch parallel workers
  5. Per-chunk code review
  6. Draft PRs

You tweak the phases, say "go", and walk away.
```

**Dependencies (required):**
- [superpowers](https://github.com/obra/superpowers) >= 5.0.0 -- brainstorming, planning, TDD, code review
- [dispatch](https://github.com/bassimeledath/dispatch) >= 2.0.0 -- parallel worker orchestration

**Dependencies (optional, auto-discovered):**
- notify (this repo) -- desktop/mobile notifications
- [deep-research](https://github.com/sanjay3290/ai-skills/tree/main/skills/deep-research) -- Gemini-powered research
- [pr-review-toolkit](https://github.com/anthropics/plugins) -- code review, silent failure detection, test coverage

### notify

Standalone macOS desktop and mobile push notifications for Claude Code. Works with any skill, worker, or session.

**Install:**
```bash
pspm install <user>/claude-skills/notify
```

**Usage:**
```bash
# From any skill or worker
bash <skill-dir>/scripts/notify.sh "Title" "Message" [priority] [url] [run-id]

# Examples
bash scripts/notify.sh "Pipeline" "Research complete"
bash scripts/notify.sh "Pipeline" "PR #45 ready" "high" "https://github.com/org/repo/pull/45"
```

**Dependencies:** None. Works out of the box on macOS via osascript.

**Optional enhancements:**
- `brew install terminal-notifier` -- clickable notifications, grouping, custom sounds
- ntfy.sh app on phone + `NTFY_TOPIC` env var -- mobile push notifications

### guardrails

Safety hooks for Claude Code that protect against destructive operations when running autonomous workers with `--dangerously-skip-permissions`.

**Install:**
```bash
pspm install <user>/claude-skills/guardrails
```

**Includes example hooks:**
- `bash-precheck.py` -- blocks destructive git ops, protects sensitive paths, gates commits on protected branches, prevents credential reads
- `write-boundary.py` -- restricts file writes to project directory, extra restrictions for worker sessions

Copy to `~/.claude/hooks/` and wire into `settings.json`. See the SKILL.md for full setup instructions.

**Dependencies:** None. Python 3 (included with macOS).

---

## Installation via PSPM

All skills can be installed via [PSPM](https://pspm.dev):

```bash
npm install -g @anytio/pspm

pspm add github:<user>/claude-skills/skills/pipeline
pspm add github:<user>/claude-skills/skills/notify
pspm add github:<user>/claude-skills/skills/guardrails
```

See `references/pspm-guide.md` for full PSPM documentation including publishing, versioning, and monorepo patterns.

## Dispatch Configuration

Pipeline requires specific Dispatch aliases. See `skills/pipeline/references/dispatch-config-example.yaml` for the required config. Merge into your `~/.dispatch/config.yaml`:

| Alias | Model | Purpose |
|---|---|---|
| `code` | Opus | Implementation workers |
| `review` | Sonnet | Per-chunk code review |
| `deep-review` | Opus | Final architecture review |
| `research` | Sonnet | Research via Gemini |
| `sweep` | Opus | Multi-repo parallel workers |

## CLAUDE.md Setup

Pipeline and Task Observer need CLAUDE.md rules for proper activation. Add to your `~/.claude/CLAUDE.md`:

```markdown
## Pipeline

- When a task involves multiple phases (research + design + implement), spans multiple
  services, references roadmaps/HLDs, or uses phrases like "end to end", "full workflow",
  "go away and do" -- use the pipeline skill INSTEAD of brainstorming directly. Pipeline
  orchestrates the full flow including brainstorming.
- For single-phase tasks (just a feature, just a fix), let superpowers brainstorming/planning
  flow as normal.

## Task Observer

- At the start of any task-oriented session -- any interaction where you will use tools and
  produce deliverables -- invoke the task-observer skill before beginning work.
```

### Why CLAUDE.md?

Claude Code skills have no priority mechanism. Without the CLAUDE.md rule, superpowers:brainstorming (which triggers on "any creative work") catches multi-phase tasks before pipeline gets a chance. The CLAUDE.md instruction takes priority over skill triggers, routing correctly.

## Known Quirks

### Ambient trigger vs slash command

Pipeline triggers ambiently via the CLAUDE.md routing rule, but this depends on the phrasing. If it doesn't trigger on a task you think it should, use `/pipeline` as a fallback. The ambient trigger is intentionally conservative -- false negatives are preferable to false positives.

**Phrases that reliably trigger:** "end to end", "full workflow", "go away and do", "build X from scratch", mentioning multiple services.

**Phrases that may NOT trigger:** Short requests, tasks that sound like single features, research-only requests.

### Superpowers terminal action override

Pipeline intercepts superpowers' terminal actions (brainstorming would normally invoke writing-plans, writing-plans would invoke executing-plans). It does this via prompt injection, not code modification. Occasionally the override may not stick if the context window is very full. If brainstorming chains directly to writing-plans instead of returning control to pipeline, restart the pipeline.

### Worker permissions

Dispatched workers are separate Claude Code sessions. They may prompt for Bash permissions that your main session has already approved. Add these to your settings.json allow list to reduce friction:

```json
"Bash(bash /tmp/worker--*)",
"Bash(bash /tmp/monitor--*)"
```

### Worker git commits

Workers commit locally in isolated worktrees during TDD cycles. This requires a CLAUDE.md exception:

```
Exception: autonomous pipeline/dispatch workers in isolated worktrees may commit
locally as part of TDD cycles when the pipeline has been approved to run.
```

Workers never push until the finish phase. Worktrees are disposable.

### State files

Pipeline writes runtime state to `.pipeline/state/<run-id>.yaml` in the project directory. This should be gitignored -- pipeline adds it automatically on first run, but if it doesn't:

```bash
echo ".pipeline/" >> .gitignore
```

### Notifications require terminal-notifier for full functionality

Without `terminal-notifier`, notifications fall back to `osascript` which lacks clickable URLs and grouping. Install for the best experience:

```bash
brew install terminal-notifier
```

### Context window on long pipelines

A full pipeline (research + brainstorm + plan + implement + review + finish) consumes significant context in the orchestrating session. The brainstorm and plan phases run in-session and produce large outputs. If the context fills up, pipeline can resume from the state file -- say "resume pipeline" or "continue" after restarting.

## Project Structure

```
skills/
  pipeline/
    SKILL.md                          # Autonomous pipeline orchestrator
    pspm.json                         # Package manifest
    references/
      phase-building-blocks.md        # Detailed per-phase docs
      state-management.md             # State file schema and lifecycle
      notification-setup.md           # Notification configuration
      dispatch-config-example.yaml    # Required Dispatch aliases
  notify/
    SKILL.md                          # Standalone notification skill
    pspm.json                         # Package manifest
    scripts/
      notify.sh                       # Notification helper script
    references/
      setup-guide.md                  # Installation guide
  guardrails/
    SKILL.md                          # Safety hooks documentation
    pspm.json                         # Package manifest
    examples/
      bash-precheck.py                # Pre-tool-use hook for Bash commands
      write-boundary.py               # Pre-tool-use hook for Edit/Write
    references/
references/
  pspm-guide.md                       # PSPM installation and publishing guide
docs/
  superpowers/
    specs/                            # Design specifications
    plans/                            # Implementation plans
```

## License

MIT
