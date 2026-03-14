# Pipeline + Notify Skills Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build two Claude Code skills -- a standalone notify skill for macOS/mobile notifications, and a pipeline skill that autonomously orchestrates the full development lifecycle from a single goal prompt.

**Architecture:** Notify is a standalone skill with a bash script that abstracts terminal-notifier/osascript/ntfy.sh. Pipeline is an ambient skill that dynamically selects phases (research, brainstorm, plan, implement, review, finish), chains superpowers skills with auto-approved transitions, and uses Dispatch for parallel/background execution. Pipeline optionally uses notify for alerting on background work.

**Tech Stack:** Bash (notify.sh), Markdown (SKILL.md, reference docs), YAML (state files, PSPM manifest)

---

## Chunk 0: Repository Setup

### Task 0: Initialise the monorepo

**Files:**
- Verify: `~/Sites/pipeline-skill/` exists (already created)

- [ ] **Step 1: Initialise git repo**

Run from `~/Sites/pipeline-skill`:
```bash
git init
```

- [ ] **Step 2: Commit design docs as first commit**

Per CLAUDE.md planning rules: "Commit design docs into the feature branch as the first commit before implementation."

Note: this commit is explicitly requested as part of the plan. No Co-Authored-By attribution.

```bash
git add docs/
```
Then separately:
```bash
git commit -m "docs: add pipeline skill design spec and implementation plan"
```

- [ ] **Step 3: Verify repo structure**

The directory scaffold and dispatch-config-example.yaml already exist from the brainstorming phase. Verify:

Run: `ls ~/Sites/pipeline-skill/skills/pipeline/references/dispatch-config-example.yaml`
Expected: file exists

Run: `ls -d ~/Sites/pipeline-skill/skills/notify/scripts/ ~/Sites/pipeline-skill/skills/notify/references/`
Expected: both directories exist

---

## Chunk 1: Notify Skill

Standalone notification skill. No dependencies. Ships as its own installable skill within the monorepo at `skills/notify/`.

### Task 1: Create notify.sh script

**Files:**
- Create: `~/Sites/pipeline-skill/skills/notify/scripts/notify.sh`

- [ ] **Step 1: Write notify.sh**

```bash
#!/bin/bash
# Notification helper for Claude Code skills
# Usage: notify.sh "Title" "Message" [priority] [url] [run-id]
# Priority: default, high, urgent
# URL: clickable link (terminal-notifier only)
# Run ID: notification group ID (terminal-notifier only)

TITLE="${1:-Claude Code}"
MESSAGE="${2:-Task complete}"
PRIORITY="${3:-default}"
URL="${4:-}"
RUN_ID="${5:-default}"

# terminal-notifier (primary -- clickable, groupable, rich)
if command -v terminal-notifier &>/dev/null; then
  SOUND=""
  [ "$PRIORITY" = "high" ] || [ "$PRIORITY" = "urgent" ] && SOUND="-sound Glass"
  terminal-notifier -title "$TITLE" -message "$MESSAGE" $SOUND \
    ${URL:+-open "$URL"} -group "claude-${RUN_ID}"
# osascript (fallback -- basic macOS notification)
else
  SOUND_NAME=""
  [ "$PRIORITY" = "high" ] || [ "$PRIORITY" = "urgent" ] && SOUND_NAME='sound name "Glass"'
  osascript -e "display notification \"$MESSAGE\" with title \"$TITLE\" $SOUND_NAME"
fi

# ntfy.sh (mobile push -- only on high/urgent priority, only if configured)
if [ "$PRIORITY" = "high" ] || [ "$PRIORITY" = "urgent" ]; then
  if [ -n "$NTFY_TOPIC" ]; then
    NTFY_PRIORITY="high"
    [ "$PRIORITY" = "urgent" ] && NTFY_PRIORITY="urgent"
    curl -s -H "Title: $TITLE" -H "Priority: $NTFY_PRIORITY" \
      ${URL:+-H "Click: $URL"} \
      -d "$MESSAGE" "ntfy.sh/$NTFY_TOPIC" >/dev/null 2>&1 &
  fi
fi
```

- [ ] **Step 2: Make executable**

Run: `chmod +x ~/Sites/pipeline-skill/skills/notify/scripts/notify.sh`

- [ ] **Step 3: Test with osascript (available on all macOS)**

Run: `~/Sites/pipeline-skill/skills/notify/scripts/notify.sh "Test" "Hello from notify skill" "high"`
Expected: macOS notification appears with "Test" title and Glass sound

- [ ] **Step 4: Test with default priority (no sound)**

Run: `~/Sites/pipeline-skill/skills/notify/scripts/notify.sh "Test" "Silent notification" "default"`
Expected: macOS notification appears, no sound

### Task 2: Create notify SKILL.md

**Files:**
- Create: `~/Sites/pipeline-skill/skills/notify/SKILL.md`

- [ ] **Step 1: Write SKILL.md**

```markdown
---
name: notify
description: "Send macOS desktop and mobile push notifications from Claude Code. Use when: completing background tasks, alerting on errors, notifying at pipeline gates, or any time the user should be alerted about something happening outside the active session. Supports terminal-notifier (rich, clickable), osascript (fallback), and ntfy.sh (mobile push)."
license: MIT
metadata:
  author: jordan.hood
  version: "0.1.0"
user_invocable: true
---

# Notify

Send notifications to the user's desktop or phone.

## Usage

Run the notify script from any skill, worker, or session:

\`\`\`bash
bash <skill-dir>/scripts/notify.sh "Title" "Message" [priority] [url] [run-id]
\`\`\`

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| Title | Yes | "Claude Code" | Notification title |
| Message | Yes | "Task complete" | Notification body |
| Priority | No | "default" | `default`, `high`, or `urgent`. High/urgent play sound and send mobile push. |
| URL | No | none | Clickable URL (terminal-notifier only). Opens on notification click. |
| Run ID | No | "default" | Group ID for notification replacement. Same run-id updates in place. |

### Priority behaviour

| Priority | Desktop sound | Mobile push (ntfy) | Use case |
|----------|--------------|-------------------|----------|
| `default` | No | No | Phase completion, progress updates |
| `high` | Yes (Glass) | Yes | Errors, gates, pipeline complete, PRs ready |
| `urgent` | Yes (Glass) | Yes (bypasses DnD) | Critical failures |

### Examples

\`\`\`bash
# Simple notification
bash scripts/notify.sh "Pipeline" "Research complete"

# High priority with PR link
bash scripts/notify.sh "Pipeline" "PR #45 ready for review" "high" "https://github.com/org/repo/pull/45"

# Grouped notification (updates in place)
bash scripts/notify.sh "Pipeline" "Worker 2/4 complete" "default" "" "pipeline-run-123"
bash scripts/notify.sh "Pipeline" "Worker 3/4 complete" "default" "" "pipeline-run-123"
\`\`\`

## Setup

### Desktop notifications (works out of the box)

Uses `osascript` which is available on all macOS systems. For richer notifications:

\`\`\`bash
brew install terminal-notifier
\`\`\`

This adds: clickable URLs, notification grouping/replacement, and custom sounds.

### Mobile push notifications (optional)

1. Install the ntfy app on your phone (iOS/Android)
2. Subscribe to a topic (e.g., `jordan-claude-pipeline`)
3. Set the environment variable:

\`\`\`bash
export NTFY_TOPIC="jordan-claude-pipeline"
\`\`\`

Or add to `~/.claude/settings.json` env block. Notifications with `high` or `urgent` priority will be pushed to your phone.
```

- [ ] **Step 2: Verify skill loads**

Test by checking the skill is readable:
Run: `head -10 ~/Sites/pipeline-skill/skills/notify/SKILL.md`
Expected: frontmatter with `name: notify`

### Task 3: Create notify setup guide reference

**Files:**
- Create: `~/Sites/pipeline-skill/skills/notify/references/setup-guide.md`

- [ ] **Step 1: Write setup-guide.md**

```markdown
# Notify Skill Setup Guide

## Quick start (no install needed)

The notify skill works immediately on macOS using `osascript`. No setup required.

## Recommended: install terminal-notifier

For clickable notifications, grouping, and better UX:

\`\`\`bash
brew install terminal-notifier
\`\`\`

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
   \`\`\`bash
   # In ~/.zshrc
   export NTFY_TOPIC="jordan-claude-pipeline-abc123"

   # Or in ~/.claude/settings.json
   "env": { "NTFY_TOPIC": "jordan-claude-pipeline-abc123" }
   \`\`\`

4. Test it:
   \`\`\`bash
   curl -d "Test notification" ntfy.sh/jordan-claude-pipeline-abc123
   \`\`\`

## Troubleshooting

| Issue | Solution |
|-------|----------|
| No notification appears | Check System Settings > Notifications. Ensure terminal app has permission. |
| terminal-notifier not found after install | Run `brew link terminal-notifier` or check PATH |
| ntfy notifications not arriving on phone | Check you subscribed to the exact same topic name |
| Sound not playing | Check system volume and Do Not Disturb settings |
```

- [ ] **Step 2: Verify reference file**

Run: `head -5 ~/Sites/pipeline-skill/skills/notify/references/setup-guide.md`

### Task 4: Create notify pspm.json

**Files:**
- Create: `~/Sites/pipeline-skill/skills/notify/pspm.json`

- [ ] **Step 1: Write pspm.json**

```json
{
  "name": "notify",
  "version": "0.1.0",
  "description": "macOS desktop and mobile push notifications for Claude Code skills and workers",
  "author": "jordan.hood",
  "license": "MIT",
  "agents": ["claude-code"],
  "keywords": ["notifications", "macos", "ntfy", "terminal-notifier", "alerts"]
}
```

### Task 5: Install and test notify skill end-to-end

- [ ] **Step 1: Symlink into skills directory**

Run: `ln -sfn ~/Sites/pipeline-skill/skills/notify ~/.agents/skills/notify`

- [ ] **Step 2: Verify symlink**

Run: `ls -la ~/.agents/skills/notify`
Expected: symlink pointing to `~/Sites/pipeline-skill/skills/notify`

- [ ] **Step 3: Verify Claude Code sees the skill**

Run: `ls ~/.claude/skills/notify 2>/dev/null || echo "May need Claude restart to pick up"`

- [ ] **Step 4: End-to-end test -- default priority**

Run: `~/.agents/skills/notify/scripts/notify.sh "Notify Skill" "Installation successful" "default"`
Expected: silent macOS notification

- [ ] **Step 5: End-to-end test -- high priority**

Run: `~/.agents/skills/notify/scripts/notify.sh "Notify Skill" "High priority test" "high"`
Expected: macOS notification with Glass sound

- [ ] **Step 6: Commit notify skill**

Note: this commit is explicitly requested as part of the plan. No Co-Authored-By attribution.

Run from `~/Sites/pipeline-skill`:
```bash
git add skills/notify/
```
Then separately:
```bash
git commit -m "feat: add notify skill with terminal-notifier, osascript, ntfy support"
```

---

## Chunk 2: Pipeline Skill -- Core SKILL.md

The main pipeline skill. The SKILL.md is the core deliverable -- it translates the design spec into Claude-executable instructions. The spec at `docs/superpowers/specs/2026-03-15-pipeline-skill-design.md` is the source of truth for all behaviour. The SKILL.md must be written referencing that spec.

Note: TDD does not apply to this chunk. The deliverables are markdown and YAML -- there is nothing to unit test. Verification is done via manual testing in Task 11.

### Task 6: Create pipeline SKILL.md

**Files:**
- Create: `~/Sites/pipeline-skill/skills/pipeline/SKILL.md`

- [ ] **Step 1: Write the SKILL.md**

Write the full SKILL.md referencing the design spec. The file must include the following sections. Load-bearing content that must appear verbatim is provided below.

**Frontmatter (verbatim):**

```yaml
---
name: pipeline
description: "Autonomous development pipeline that orchestrates research, design, planning, parallel implementation, review, and PR creation from a single goal. Triggers ambently on multi-phase tasks or via /pipeline. Chains superpowers skills for quality and Dispatch for parallelism. Use when: the task involves multiple phases (research + design + implement), spans multiple services, references roadmaps/HLDs, or the user says 'end to end', 'full workflow', 'go away and do', 'build X from scratch'."
license: MIT
metadata:
  author: jordan.hood
  version: "0.1.0"
user_invocable: true
---
```

**Terminal action override instruction (verbatim -- this is the prompt text injected when invoking superpowers skills):**

> "You are running within an autonomous pipeline. When you reach your terminal action (the point where you would normally invoke the next skill such as writing-plans or executing-plans), do NOT invoke it. Instead, report the output file path and return control. The pipeline orchestrator will handle the next phase. Continue to run all internal quality checks (spec reviewers, plan reviewers) as normal."

**Model routing table (include in SKILL.md):**

| Phase | Dispatch alias | Model | When to use |
|---|---|---|---|
| Research | `research` | Sonnet | Unfamiliar tech, standards, external APIs |
| Implementation | `code` | Opus | Code generation, TDD |
| Per-chunk review | `review` | Sonnet | Code review, silent failures, OWASP, test coverage |
| Fix loop | `code` | Opus | Fixing issues found in review |
| Final architecture review | `deep-review` | Opus | Multi-chunk cross-cutting review |

**Notification trigger table (include in SKILL.md):**

| Event | Fires? | Priority |
|---|---|---|
| Dispatched worker completes | Yes | default |
| Dispatched worker fails | Yes | high |
| Worker asks IPC question | Yes | high |
| In-session phase completes | No | -- |
| Review finds issues | Yes | default |
| Fix loop exhausted (3 retries) | Yes | high |
| Gate reached | Yes | high |
| Pipeline complete | Yes | high |
| PRs created | Yes (with URLs) | high |

**State file YAML template (include in SKILL.md for read/write reference):**

```yaml
run_id: "<kebab-case-goal-date>"
goal: "<user's original goal>"
started: "<ISO 8601>"
current_phase: "<phase name>"
proposed_phases: [<list of phase names>]
completed_phases:
  <phase_name>:
    status: completed | failed | skipped
    output: "<file path>"
    completed_at: "<ISO 8601>"
    error: "<error message if failed>"
active_phase:
  name: "<phase name>"
  status: in_progress | waiting_for_user | failed
  execution:
    <chunk_name>:
      tasks: ["<task-id>", ...]
      mode: dispatch_parallel | subagent
      depends_on: <chunk_name> | null
      status: pending | running | completed | failed
      workers:
        <task-id>: { status: running | completed | failed, pr: "<#num>" }
```

**Error handling table (include in SKILL.md):**

| Failure | Behaviour |
|---|---|
| Research returns nothing useful | Skip, proceed to brainstorm with available context. Notify. |
| Brainstorming cannot produce spec | Pause. Notify: "Brainstorming needs help." |
| Plan review loop exhausted (5 iterations) | Pause. Notify. Surface issues. |
| Dispatch worker crashes/times out | Mark failed. Let other workers finish. Notify. Offer re-dispatch or skip. |
| Worktree creation fails | Pause. Notify. |
| node_modules install fails | Pause. Notify. |
| Review fix loop exhausted (3 retries) | Pause. Notify with report. |
| MCP tool unavailable | Skip if optional, pause if user-requested. |

**Additional sections the SKILL.md must contain** (write based on the spec, these don't need verbatim content):

- Ambient trigger logic: when to activate, when NOT to, false-negative recovery via `/pipeline`
- Announce-and-wait interaction: propose phases, user tweaks, "go" to execute
- Phase building blocks: all 12 phases with tools, inputs, outputs, when-selected criteria
- Fan-out/fan-in execution model: independent chunks -> Dispatch parallel, sequential -> subagent-driven, dependency boundaries as fan-in points
- Per-chunk review cycle: code-reviewer, silent-failure-hunter, pr-test-analyzer, security-guidance, plus runtime-discovered review skills
- Skill discovery: Claude Code loads skills at session start, no scanning needed, workers inherit same ecosystem
- `.pipeline/` gitignore: on first run, add `.pipeline/` to the project's `.gitignore` if not already present
- Resume: read state file on "continue" or "resume pipeline", pick up from failed/paused phase
- Constraints: two hard deps (superpowers, dispatch), CLAUDE.md always takes precedence
- Worker git commits: workers may commit locally in isolated worktrees during TDD (per CLAUDE.md exception)

- [ ] **Step 2: Verify SKILL.md structure**

Run: `head -10 ~/Sites/pipeline-skill/skills/pipeline/SKILL.md`
Expected: frontmatter with `name: pipeline`

Run: `wc -l ~/Sites/pipeline-skill/skills/pipeline/SKILL.md`
Expected: 300-500 lines

Run: `grep -c "terminal action" ~/Sites/pipeline-skill/skills/pipeline/SKILL.md`
Expected: at least 1 (terminal action override instruction present)

### Task 7: Create phase-building-blocks.md reference

**Files:**
- Create: `~/Sites/pipeline-skill/skills/pipeline/references/phase-building-blocks.md`

- [ ] **Step 1: Write phase-building-blocks.md**

Detailed documentation per phase type. Includes:
- Exact Dispatch alias and model for each phase
- Input/output file paths and formats
- Terminal action override instructions per skill
- Worker prompt templates for Dispatch phases
- Review skill invocation order
- Fix loop mechanics

This is the reference the SKILL.md points to for detailed phase behaviour. Keep it factual and precise -- workers will read this.

- [ ] **Step 2: Verify**

Run: `head -5 ~/Sites/pipeline-skill/skills/pipeline/references/phase-building-blocks.md`

### Task 8: Create state-management.md reference

**Files:**
- Create: `~/Sites/pipeline-skill/skills/pipeline/references/state-management.md`

- [ ] **Step 1: Write state-management.md**

Include the following content:

- **Location:** `.pipeline/state/<run-id>.yaml` in the project directory
- **Run ID format:** kebab-case from goal + date, e.g. `json-schema-decorators-2026-03-15`
- **YAML schema:** use the template from Task 6 Step 1 (the state file YAML template)
- **Creating state:** Pipeline writes the initial state file when the user says "go", recording run_id, goal, proposed_phases, and started timestamp
- **Updating state:** After each phase completes, update the phase status, output path, and completed_at. Move current_phase forward.
- **Reading state for resume:** When user says "continue" or "resume pipeline", read the most recent state file, find the current_phase, and re-execute from there
- **Failure recording:** On failure, set phase status to "failed" with error message. Pipeline pauses and notifies.
- **Concurrent pipelines:** Each pipeline run gets its own state file. Multiple can exist simultaneously. List with `ls .pipeline/state/`
- **Gitignore:** `.pipeline/` is runtime state, not documentation. On first pipeline run, check if `.pipeline` is in `.gitignore`. If not, add it.
- **Cleanup:** State files persist for audit/debugging. User can delete `.pipeline/` to clean up.

- [ ] **Step 2: Verify**

Run: `head -5 ~/Sites/pipeline-skill/skills/pipeline/references/state-management.md`

### Task 9: Create notification-setup.md reference

**Files:**
- Create: `~/Sites/pipeline-skill/skills/pipeline/references/notification-setup.md`

- [ ] **Step 1: Write notification-setup.md**

Covers:
- How Pipeline uses the notify skill (or falls back to inline osascript)
- When notifications fire (table from spec)
- How to configure notification priority per phase
- How to set up ntfy.sh for mobile push
- How to install terminal-notifier

- [ ] **Step 2: Verify**

Run: `head -5 ~/Sites/pipeline-skill/skills/pipeline/references/notification-setup.md`

### Task 10: Create pipeline pspm.json

**Files:**
- Create: `~/Sites/pipeline-skill/skills/pipeline/pspm.json`

- [ ] **Step 1: Write pspm.json**

```json
{
  "name": "pipeline",
  "version": "0.1.0",
  "description": "Autonomous development pipeline that chains research, design, planning, parallel implementation, review, and PR creation",
  "author": "jordan.hood",
  "license": "MIT",
  "agents": ["claude-code"],
  "dependencies": {
    "superpowers": ">=5.0.0",
    "dispatch": ">=2.0.0"
  },
  "optionalDependencies": {
    "notify": ">=0.1.0",
    "deep-research": ">=1.0",
    "pr-review-toolkit": ">=1.0.0"
  },
  "keywords": ["pipeline", "orchestration", "autonomous", "dispatch", "superpowers"]
}
```

### Task 10b: Verify dispatch-config-example.yaml

**Files:**
- Verify: `~/Sites/pipeline-skill/skills/pipeline/references/dispatch-config-example.yaml` (already exists)

- [ ] **Step 1: Verify file exists and contains required aliases**

Run: `grep -c "code:\|review:\|deep-review:\|research:\|sweep:" ~/Sites/pipeline-skill/skills/pipeline/references/dispatch-config-example.yaml`
Expected: 5 (all required aliases present)

### Task 11: Install and test pipeline skill

- [ ] **Step 1: Symlink into skills directory**

Run: `ln -sfn ~/Sites/pipeline-skill/skills/pipeline ~/.agents/skills/pipeline`

- [ ] **Step 2: Verify symlink**

Run: `ls -la ~/.agents/skills/pipeline`

- [ ] **Step 3: Test ambient trigger detection**

Start a new Claude session and say: "Build a new authentication service for the booking platform end to end"
Expected: Pipeline skill triggers, proposes phases, waits for user approval

- [ ] **Step 4: Test negative -- should NOT trigger**

In a session, say: "Fix the typo in README.md"
Expected: Pipeline does NOT trigger, normal flow handles it

- [ ] **Step 5: Test manual fallback**

In a session, say: `/pipeline`
Expected: Pipeline activates and asks what to work on

- [ ] **Step 6: Test announce-and-wait interaction**

When Pipeline proposes phases, say: "Also add Jira breakdown under BOOK-100"
Expected: Pipeline updates its proposed phases to include jira_breakdown

- [ ] **Step 7: Commit pipeline skill**

Note: this commit is explicitly requested as part of the plan. No Co-Authored-By attribution.

Run from `~/Sites/pipeline-skill`:
```bash
git add skills/pipeline/ docs/
```
Then separately:
```bash
git commit -m "feat: add pipeline skill with ambient trigger, dynamic phases, and state management"
```

---

## Chunk 3: Integration Testing

### Task 12: End-to-end pipeline test on a real project

- [ ] **Step 1: Pick a small, well-defined task on typespec-emitters**

Suggested: "Confirm @patch method support in the fastify emitter" (from the P1 roadmap -- small, bounded)

- [ ] **Step 2: Run pipeline**

From `~/Sites/typespec-emitters`, say: "Confirm and test @patch method support in the fastify emitter, end to end"
Expected: Pipeline triggers, proposes phases (brainstorm, plan, implement, review, finish), waits for approval

- [ ] **Step 3: Say "go" and observe**

Let Pipeline run. Verify:
- Brainstorming produces a spec
- Writing-plans produces a plan
- Implementation uses TDD
- Review runs on the result
- State file created at `.pipeline/state/`
- Notifications fire on Dispatch phases (if terminal-notifier installed)

- [ ] **Step 4: Verify state file**

Run: `cat ~/Sites/typespec-emitters/.pipeline/state/*.yaml`
Expected: YAML with run_id, goal, phase statuses

- [ ] **Step 5: Verify .gitignore was updated**

Run: `grep ".pipeline" ~/Sites/typespec-emitters/.gitignore`
Expected: `.pipeline/` present in .gitignore

- [ ] **Step 6: Document any issues found**

Write issues to `~/Sites/pipeline-skill/docs/testing-notes.md` for iteration.
