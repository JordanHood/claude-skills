# Pipeline Skill - Design Specification

## Overview

An ambient Claude Code skill that autonomously orchestrates the full development lifecycle from a single goal prompt. It dynamically selects phases based on task complexity, chains superpowers skills for quality and Dispatch for parallelism, and discovers other available skills at runtime.

## Problem

Jordan currently chains superpowers skills manually (brainstorm -> plan -> execute -> review -> finish), answering terminal action prompts at each transition. For complex work involving research, parallel implementation, and multi-service coordination, this requires constant presence and manual orchestration. The pipeline skill eliminates this by pre-answering those transitions and orchestrating the full flow autonomously.

## Core Pillars

**Superpowers** -- the quality engine. Brainstorming produces reviewed specs, writing-plans produces reviewed implementation plans, TDD ensures test-first implementation, verification-before-completion prevents false completion claims. Spec and plan reviewer subagents always run.

**Dispatch** -- the parallelism engine. Fan-out to background workers with fresh context windows, filesystem IPC for questions, plan-as-state for progress tracking. Handles parallel implementation across chunks and cold code review from separate workers.

**Everything else** -- discovered at runtime and used where relevant. Skills, MCP tools, plugins come and go. Pipeline adapts.

## Triggering

Pipeline is ambient -- it does NOT require a slash command. It triggers when the task involves multi-phase work.

### Triggers on

- Multiple phases mentioned (research + implement, design + build)
- Multiple services or repos
- References to roadmaps, HLDs, Outline documents, Jira projects
- Explicit phrases: "end to end", "full workflow", "go away and do", "build X from scratch"
- Estimated scope exceeds a single planning session

### Does NOT trigger for

- Simple fixes, single-file changes, typos
- Research-only or question-only tasks
- When the user has already invoked a specific superpowers skill manually
- When the user is guiding work step-by-step interactively

### Manual fallback

`/pipeline` is available as a slash command for cases where ambient detection misses. The ambient trigger is intentionally conservative -- it prefers false negatives (missed triggers) over false positives (unwanted triggers), since the manual command covers the gap.

## Interaction Pattern

**Announce and wait (Option B):**

```
User: "Add JSON Schema conditional support to TypeSpec emitters"

Pipeline: "Here's what I'm going to do:
  1. Research JSON Schema conditionals via Gemini (Dispatch)
  2. Brainstorm decorator design against your codebase
  3. Write implementation plan
  4. Dispatch parallel workers per plan chunk
  5. Per-chunk: code review, silent failure hunt, test coverage check
  6. Open draft PRs (one per chunk)

  Want me to adjust anything before I start?"

User: "Also break the plan into Jira stories under TSPEC-123"

Pipeline: "Updated:
  1. Research JSON Schema conditionals via Gemini
  2. Brainstorm decorator design
  3. Write implementation plan
  4. Break plan into Jira stories under TSPEC-123
  5. Dispatch parallel workers per plan chunk
  6. Per-chunk reviews
  7. Open draft PRs

  Going?"

User: "Go"

Pipeline: *runs autonomously*
```

User can tweak phases, add Jira breakdown, remove research, add Outline export, change PR strategy -- anything before saying "go".

## Phase Building Blocks

Pipeline dynamically selects from these based on task context. It does not follow a fixed sequence.

### research
- **Tool:** Dispatch with `research` alias (Sonnet worker)
- **Worker discovers and uses:** deep-research (Gemini), Context7 (library docs), episodic-memory (past decisions), mysql/postgres (data inspection)
- **Output:** `docs/research/<topic>.md`
- **When selected:** Task involves unfamiliar tech, standards, external APIs, or user explicitly asks for research

### outline_pull
- **Tool:** mcp__outline__search_documents + mcp__outline__get_document
- **Output:** HLD/spec content loaded into context for brainstorming
- **When selected:** Task references an architect HLD or Outline document

### brainstorm
- **Tool:** superpowers:brainstorming
- **Inputs:** Research output (if available) + Outline HLD (if available) + task goal
- **Output:** Spec document at `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`
- **Behaviour:** Spec reviewer subagent always runs. No human gate -- Pipeline auto-approves transitions. If brainstorming needs clarification it cannot resolve from context, it asks the user via the session.
- **Terminal action override:** Pipeline proceeds to plan phase instead of letting brainstorming invoke writing-plans itself.

### plan
- **Tool:** superpowers:writing-plans
- **Inputs:** Spec document from brainstorm phase
- **Output:** Plan document at `docs/superpowers/plans/YYYY-MM-DD-<feature>.md` with chunks, dependencies, and per-chunk task breakdown
- **Behaviour:** Plan reviewer subagent always runs. No human gate.
- **Terminal action override:** Pipeline proceeds to implement phase (via Dispatch or subagent-driven) instead of letting writing-plans invoke executing-plans.

### jira_breakdown
- **Tool:** mcp__plugin_atlassian_atlassian (Jira APIs)
- **Behaviour:** Reads the plan document, creates an Epic with Stories per chunk, tasks per task item. Uses standard user story templates.
- **When selected:** User requests it or task references a Jira project key

### outline_push
- **Tool:** mcp__outline__create_document or mcp__outline__update_document
- **Behaviour:** Exports plan document to Outline for team/architect visibility
- **When selected:** User requests architect involvement or team visibility

### gate
- **Behaviour:** Pauses pipeline, sends notification, waits for user to say "continue"
- **When selected:** User explicitly requests a pause point, or architect review is needed after outline_push

### implement
- **Execution model:** Fan-out / fan-in based on plan chunk structure

```
Pipeline reads plan -> identifies chunks and dependencies

Independent tasks within a chunk -> Dispatch parallel Opus workers, each in own worktree
Sequential/dependent tasks -> subagent-driven-development in current session
Single simple task -> subagent in current session

Per chunk (whether dispatched or in-session):
  Worker creates worktree (if .bare/ detected)
  Worker installs node_modules
  Worker uses TDD (superpowers:test-driven-development)
  Worker uses systematic-debugging if tests fail
  Worker uses verification-before-completion before marking done
  Worker discovers and uses other relevant skills (fastify, node, security, etc.)

Chunk 1 (independent tasks A, B, C):
  -> 3 parallel Dispatch workers
  -> Fan in: wait for all

Chunk 2 (depends on chunk 1, tasks D, E):
  -> 2 parallel Dispatch workers
  -> Fan in: wait for all

Chunk 3 (single task F):
  -> Subagent in-session
```

### review (per-chunk)
After each chunk completes implementation, a review cycle runs:

- **pr-review-toolkit:code-reviewer** -- code quality, correctness, maintainability
- **pr-review-toolkit:silent-failure-hunter** -- catch suppressed errors, bad fallbacks
- **pr-review-toolkit:pr-test-analyzer** -- test coverage gaps
- **security-guidance / OWASP patterns** -- security review (especially on API/auth code)

Additional review skills discovered at runtime are used where relevant (type-design-analyzer for new types, comment-analyzer for new docs).

Review runs as a **fresh Dispatch worker** using the `review` alias (**Sonnet** -- fast, cheap, pattern-matching). No implementation bias from a fresh context window.

### fix_loop
- **Trigger:** Review finds issues
- **Behaviour:** Dispatch a fix worker with the review report, then re-review
- **Max retries:** 3
- **On max retries exceeded:** Notify user, pause for human decision

```
implement -> review -> issues found?
  no  -> continue to next chunk or finish
  yes -> dispatch fix worker -> re-review -> loop (max 3)
        -> still failing -> notify human, pause
```

### finish
- **Tool:** superpowers:finishing-a-development-branch
- **PR strategy:** Dynamic, proposed in the announcement:
  - One PR per chunk (default for multi-chunk work)
  - Single PR (for small features)
  - User tweaks at announcement step
- **Behaviour:** Creates draft PRs, notifies with PR links
- **If receiving-code-review skill is available:** Pipeline notes that subsequent PR feedback should use this skill

### final_review
- **Tool:** Dispatch `deep-review` alias (**Opus** -- cross-chunk reasoning needs deeper model)
- **Behaviour:** Cold architecture review across ALL PRs/chunks together. Checks cross-chunk consistency, integration concerns, overall design coherence.
- **When selected:** Automatically included for multi-chunk work. Skipped for single-chunk work. User can add or remove at announcement step.

### Model routing summary

| Phase | Dispatch alias | Model | Rationale |
|---|---|---|---|
| Research | `research` | Sonnet | Coordination, not deep reasoning |
| Implementation | `code` | Opus | Complex code generation |
| Per-chunk review | `review` | Sonnet | Pattern matching, checklist-based |
| Fix loop (fixing issues) | `code` | Opus | Needs to understand and fix code |
| Final architecture review | `deep-review` | Opus | Cross-chunk reasoning |
| In-session brainstorm/plan | n/a (current session) | Inherits session model | Creative design decisions |

### Multi-repo sweep

For goals spanning multiple repositories (e.g., "update the auth contract across booking-api, gateway, and frontend"), the plan phase produces one chunk per repository. Each chunk's Dispatch worker operates in that repository's worktree. PRs are created per-repo.

## Notification Design

**Engine:** `terminal-notifier` (primary, install via `brew install terminal-notifier`), `osascript` (fallback), `ntfy.sh` (optional mobile push via `NTFY_TOPIC` env var).

**When notifications fire:**

| Event | Fires? | Priority |
|---|---|---|
| Dispatched worker starts | No (noise) | -- |
| Dispatched worker completes | Yes | Default |
| Dispatched worker fails | Yes | High |
| Worker asks a question (IPC) | Yes | High |
| In-session phase completes | No (you're watching) | -- |
| Review finds issues | Yes | Default |
| Fix loop exhausted (max retries) | Yes | High |
| Gate reached | Yes | High |
| Pipeline complete | Yes | High |
| PRs created | Yes (with PR URLs) | High |

**Notification grouping:** Use `pipeline-{run-id}` as group ID. Phase updates replace previous notification so the user sees one evolving notification per pipeline run.

**Implementation:** `scripts/notify.sh` in the skill directory:

```bash
#!/bin/bash
TITLE="${1:-Pipeline}"
MESSAGE="${2:-Task complete}"
PRIORITY="${3:-default}"
URL="${4:-}"

# terminal-notifier (primary -- clickable, groupable)
if command -v terminal-notifier &>/dev/null; then
  SOUND=""
  [ "$PRIORITY" = "high" ] && SOUND="-sound Glass"
  terminal-notifier -title "$TITLE" -message "$MESSAGE" $SOUND \
    ${URL:+-open "$URL"} -group "pipeline-${RUN_ID:-default}"
# osascript (fallback -- basic notification)
else
  SOUND_NAME=""
  [ "$PRIORITY" = "high" ] && SOUND_NAME='sound name "Glass"'
  osascript -e "display notification \"$MESSAGE\" with title \"$TITLE\" $SOUND_NAME"
fi

# ntfy.sh (mobile push -- only on high priority, only if configured)
if [ "$PRIORITY" = "high" ] && [ -n "$NTFY_TOPIC" ]; then
  curl -s -H "Title: $TITLE" -H "Priority: high" \
    ${URL:+-H "Click: $URL"} \
    -d "$MESSAGE" "ntfy.sh/$NTFY_TOPIC" >/dev/null 2>&1 &
fi
```

## Skill Discovery

Pipeline does NOT hardcode which skills to use at each phase. Claude Code already loads all available skills (from `~/.claude/skills/`, plugins, MCP tools) at session start. Pipeline reads this list from its session context and evaluates which skills are relevant to each phase.

Dispatched workers inherit the same skill ecosystem -- they're fresh Claude Code sessions that load the same skills automatically. Pipeline tells workers "use available skills where relevant" and they discover what's installed naturally.

**No directory scanning. No caching. No skill registry.** Claude Code handles all of this. Pipeline just uses what's there.

If a new skill is installed between pipeline runs, it's automatically available next time. If a skill or MCP tool becomes unavailable mid-pipeline, Pipeline degrades gracefully -- it skips that skill's contribution and continues.

The only hardcoded dependencies are the two pillars: **superpowers** and **dispatch**. Everything else is optional and discovered at runtime.

## State Management

Pipeline state persists in `.pipeline/state/<run-id>.yaml` in the project directory:

```yaml
run_id: "json-schema-decorators-2026-03-15"
goal: "Add JSON Schema conditional support to TypeSpec emitters"
started: "2026-03-15T22:15:00Z"
current_phase: "implement"
proposed_phases:
  - research
  - brainstorm
  - plan
  - implement
  - review
  - finish
completed_phases:
  research:
    status: completed
    output: "docs/research/json-schema-advanced.md"
    completed_at: "2026-03-15T22:25:00Z"
  brainstorm:
    status: completed
    output: "docs/superpowers/specs/2026-03-15-json-schema-decorators-design.md"
    completed_at: "2026-03-15T22:35:00Z"
  plan:
    status: completed
    output: "docs/superpowers/plans/2026-03-15-json-schema-decorators.md"
    completed_at: "2026-03-15T22:42:00Z"
active_phase:
  name: implement
  status: in_progress
  execution:
    chunk_1:
      tasks: ["conditional-required", "dependent-schemas"]
      mode: dispatch_parallel
      workers:
        conditional-required: { status: completed, pr: "#45" }
        dependent-schemas: { status: running }
    chunk_2:
      tasks: ["additional-properties"]
      mode: subagent
      depends_on: chunk_1
      status: pending
```

**Enables:**
- Resume after context window compaction (read state, continue from current phase)
- Status checks ("how's the pipeline?")
- Multiple concurrent pipelines
- Error recovery (re-run from failed phase)
- Post-completion audit trail

**Housekeeping:** `.pipeline/` contains runtime state, not documentation. It should be added to `.gitignore` in projects using the pipeline skill. The pipeline skill can do this automatically on first run.

## Terminal Action Override Mechanism

Superpowers skills have hardcoded terminal actions (brainstorming always invokes writing-plans, writing-plans always invokes executing-plans/subagent-driven). Pipeline needs to control these transitions.

**How it works:** Pipeline does NOT modify skill files. Instead, it provides priority instructions in the session context that override the terminal action behaviour. When Pipeline invokes a superpowers skill, it prepends instructions such as:

> "You are running within an autonomous pipeline. When you reach your terminal action (the point where you would normally invoke the next skill), do NOT invoke it. Instead, report the output file path and return control. The pipeline orchestrator will handle the next phase."

This works because CLAUDE.md instructions take priority over skill instructions (per superpowers' own priority rules: user instructions > skills > system prompt). The Pipeline's instructions act as user-level overrides.

**Specifically:**
- brainstorming reaches "invoke writing-plans" -> Pipeline instruction says "stop here, report spec path"
- writing-plans reaches "invoke executing-plans" -> Pipeline instruction says "stop here, report plan path"
- Pipeline then reads the output and proceeds to its next phase

This preserves the full internal quality of each skill (spec reviewers, plan reviewers) while Pipeline controls the transitions between them.

## Error Handling

**Phase failure policy:** Any phase failure pauses the pipeline and notifies the user.

| Failure type | Behaviour |
|---|---|
| Research returns nothing useful | Skip research, proceed to brainstorm with available context. Notify user. |
| Brainstorming cannot produce a spec | Pause pipeline. Notify: "Brainstorming needs help -- insufficient context for {goal}." |
| Plan reviewer fails after 5 iterations | Pause pipeline. Notify: "Plan review loop exhausted." Surface issues to user. |
| Dispatch worker crashes or times out | Mark task failed in state. If other workers in chunk are still running, let them finish. Notify: "Worker {task} failed." Offer re-dispatch or skip. |
| Worktree creation fails | Pause pipeline. Notify with error. Likely a git issue the user needs to resolve. |
| node_modules install fails | Pause pipeline. Notify. Likely a dependency issue. |
| Review fix loop exhausted (3 retries) | Pause pipeline. Notify with review report. User decides. |
| MCP tool unavailable (Outline, Jira down) | Skip that phase if optional. If required (user explicitly requested), pause and notify. |

**State on failure:** The state file records the failure, the phase it occurred in, and any error context. This enables resume from the failed phase after the user resolves the issue.

**Resume command:** User says "continue" or "resume pipeline" after fixing the issue. Pipeline reads state file, identifies the failed phase, and re-runs from there.

## CLAUDE.md Compliance

Pipeline operates entirely within the existing harness:

- **Worktrees:** Detects `.bare/` and creates worktrees per worker. Uses `git` inside worktrees, `gw` at repo root.
- **Hooks:** All workers inherit bash-precheck, write-boundary, commit-check, mcp-gate, file-check, read-guard.
- **Code style:** Full function declarations, no arrow functions except callbacks. No eslint-disable. No unnecessary comments.
- **Package manager:** Detected from lockfile per CLAUDE.md rules.
- **Tests:** Always run after implementation. Workers cannot claim completion without passing tests (verification-before-completion).

### Intentional deviation: worker git commits

CLAUDE.md states: "NEVER commit, stage, or push unless I explicitly ask you to." Pipeline workers commit during the TDD cycle as part of autonomous execution. This is safe because:

1. **User authorized it** by saying "Go" at the announcement step
2. **Commits are local only** -- workers commit to isolated worktrees, never push until the finish phase
3. **Push/PR only happens at finish** -- the user reviews PRs before merging
4. **Worktrees are disposable** -- if anything goes wrong, the worktree can be deleted without affecting other branches

This deviation is the cost of autonomous execution. Without worker commits, TDD cycles cannot persist progress between iterations.

## File Structure

Monorepo layout -- both skills in one repo, individually installable:

```
~/Sites/pipeline-skill/                 # Monorepo root
  skills/
    pipeline/
      SKILL.md                          # Main skill: ambient trigger, routing, phase orchestration
      pspm.json                         # PSPM package manifest
      references/
        phase-building-blocks.md        # Detailed docs per phase type
        state-management.md             # State file format and resume logic
        notification-setup.md           # How to configure notifications
        dispatch-config-example.yaml    # Required Dispatch aliases
    notify/
      SKILL.md                          # Standalone notification skill
      pspm.json                         # PSPM package manifest
      scripts/
        notify.sh                       # terminal-notifier / osascript / ntfy.sh
      references/
        setup-guide.md                  # Installation and configuration guide
  docs/
    superpowers/
      specs/                            # Design specs (this document)
      plans/                            # Implementation plans
```

## Constraints

- **Two hard dependencies:** superpowers and dispatch. Pipeline errors clearly if either is missing.
- **All other skills are optional.** Pipeline discovers and uses what's available.
- **Pipeline never replaces superpowers.** It invokes them and auto-approves their transitions.
- **Pipeline never replaces Dispatch.** It uses Dispatch as its execution layer for parallel/background work.
- **CLAUDE.md rules always take precedence** over pipeline behaviour.

## Packaging (PSPM + npx skills)

Pipeline is distributed as two separate skills for maximum reuse:

### 1. `notify` skill (standalone)
A general-purpose notification skill for Claude Code. Not Pipeline-specific -- any skill, worker, or session can use it.

```
~/Sites/notify-skill/
  SKILL.md                    # Skill definition: "use when you need to notify the user"
  scripts/
    notify.sh                 # terminal-notifier / osascript / ntfy.sh
  references/
    setup-guide.md            # How to install terminal-notifier, configure ntfy
```

**Install:** `npx skills add <repo>/notify` or `pspm install notify`
**Usage:** Workers call `bash <skill-dir>/scripts/notify.sh "Title" "Message" "high" "https://url"`
**No dependencies.** Works standalone on macOS.

### 2. `pipeline` skill (orchestrator)
The main pipeline skill. Depends on superpowers, dispatch, and optionally notify.

```
~/Sites/pipeline-skill/
  SKILL.md
  pspm.json                             # PSPM package manifest
  references/
    phase-building-blocks.md
    state-management.md
    notification-setup.md
    dispatch-config-example.yaml
```

**Install:** `npx skills add <repo>/pipeline` or `pspm install pipeline`

### PSPM manifest (`pspm.json`)

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

### Repo structure for open source

Single monorepo with multiple skills (same pattern as `sanjay3290/ai-skills`):

```
github.com/<user>/claude-skills
  skills/
    pipeline/
      SKILL.md
      references/
      pspm.json
    notify/
      SKILL.md
      scripts/notify.sh
      references/
      pspm.json
  README.md
```

**Install individually:**
```
npx skills add <user>/claude-skills/pipeline
npx skills add <user>/claude-skills/notify
```

Both follow the Agent Skills standard. Both installable via PSPM or npx skills add.
