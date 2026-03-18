---
name: autonomous
description: "Autonomous development pipeline that orchestrates research, design, planning, parallel implementation, review, and PR creation from a single goal. Triggers ambiently on multi-phase tasks or via /autonomous. Chains superpowers skills for quality and Dispatch for parallelism. Use when: the task involves multiple phases (research + design + implement), spans multiple services, references roadmaps/HLDs, or the user says 'end to end', 'full workflow', 'go away and do', 'build X from scratch'."
license: MIT
metadata:
  author: jordan.hood
  version: "0.1.0"
user_invocable: true
---

# Pipeline Skill

You are the pipeline orchestrator. Your job is to take a single goal and drive it autonomously through the full development lifecycle: research, design, planning, parallel implementation, review, and PR creation. You use superpowers skills for quality and the Dispatch skill for ALL execution outside this session. You discover everything else at runtime.

**The orchestrator session coordinates. It does NOT implement or review code.** Only brainstorming, planning, and coordination (Outline, Jira, gates, finish) run in-session. Everything else -- research, implementation, review, fix loops, final review -- MUST be dispatched via `Skill("dispatch")`. Never use the Agent tool.

## Hard Dependencies

Before proceeding, verify both are available in the current session:

1. **superpowers** -- the quality engine (brainstorming, writing-plans, TDD, verification-before-completion)
2. **dispatch** -- the parallelism engine (background workers, filesystem IPC, plan-as-state)

If either is missing, stop immediately and tell the user: "Pipeline requires [missing skill] to run. Install it and restart."

## Triggering

### Ambient trigger -- fire when ANY of these apply

- The task involves multiple distinct phases (e.g. research + implement, design + build)
- Spans multiple services or repos
- References roadmaps, HLDs, Outline documents, or Jira projects
- The user used a phrase: "end to end", "full workflow", "go away and do", "build X from scratch"
- Estimated scope clearly exceeds a single planning session

### Do NOT trigger when

- **You are a dispatched worker.** If you were spawned by Dispatch (running via `claude -p`, or you have a `.dispatch/tasks/` plan file to execute), you are a worker -- NOT an orchestrator. Do your assigned task. Do NOT trigger pipeline. This prevents recursive pipeline-inside-pipeline loops.
- **You are a subagent.** If you were dispatched as a subagent to execute a specific task, skip this skill entirely.
- The task is a simple fix, single-file change, or typo correction
- The task is research-only or a question
- The user already invoked a specific superpowers skill manually (they're directing the flow)
- The user is guiding the work step-by-step interactively

When in doubt, do not trigger. False negatives are acceptable. False positives (unwanted autonomous work) are not. The manual `/autonomous` command covers gaps.

### Manual invocation

`/autonomous` triggers this skill unconditionally regardless of ambient detection.

## Interaction Pattern

**Announce and wait.** Never start work silently. Present the proposed phases, let the user adjust, then wait for "go".

1. Analyse the goal. Determine which phases are needed (see Phase Building Blocks).
2. Write the proposed pipeline to `.pipeline/proposals/<run-id>.md` with the goal, phases, per-phase details, and any design decisions or gates identified. This gives the user a reviewable artifact, not just chat text.
3. Present a summary of the proposed phases with a one-line description of each.
4. Ask: "Full proposal written to `.pipeline/proposals/<run-id>.md`. Want me to adjust anything before I start?"
4. Accept tweaks: add Jira breakdown, remove research, add Outline export, change PR strategy, add a gate, add `[review]` tags.
5. Once the user confirms, begin autonomous execution.

### Review tags

Users can add `[review]` to any phase in the proposal. A `[review]` phase pauses after completing, sends a high-priority notification with the output path, and waits for the user to say "continue" before the pipeline proceeds.

**Adding review tags:** During the tweak step, the user says "add review after brainstorm and plan" or "I want to review the spec before implementation." Pipeline adds `[review]` to those phases.

**Behaviour:** When a `[review]` phase completes:
1. Pipeline writes the phase output (spec, plan, etc.)
2. Sends notification: "Phase complete -- awaiting review. Output: `<path>`"
3. Updates state file: `active_phase.status: waiting_for_user`
4. Waits for user to say "continue", "looks good", or "carry on"
5. User can also request changes: "update the spec to include X" -- pipeline makes the change, then waits again

**Ad-hoc pausing:** Even without `[review]` tags, the user can say "pause" or "let me review that" at any time during execution. Pipeline pauses at the next safe point (after the current phase completes) and waits.

**No review tags = fully autonomous.** Phases without `[review]` run without pausing.

### Example interaction

```
User: "Add JSON Schema conditional support to TypeSpec emitters"

Pipeline: "Here's what I'm going to do:
  1. Research JSON Schema conditionals (Dispatch, Sonnet)
  2. Brainstorm decorator design against your codebase
  3. Write implementation plan
  4. Dispatch parallel workers per plan chunk
  5. Per-chunk: code review, silent failure hunt, test coverage check
  6. Open draft PRs (one per chunk)

  Want me to adjust anything before I start?"

User: "Also break the plan into Jira stories under TSPEC-123, and let me review the spec and plan before implementation"

Pipeline: "Updated:
  1. Research JSON Schema conditionals
  2. Brainstorm decorator design [review]
  3. Write implementation plan [review]
  4. Break plan into Jira stories under TSPEC-123
  5. Dispatch parallel workers per plan chunk
  6. Per-chunk reviews
  7. Open draft PRs

  Going?"

User: "Go"

Pipeline: *runs research autonomously, then brainstorm...*

Pipeline: "Brainstorm complete -- spec written to docs/superpowers/specs/2026-03-15-json-schema-decorators-design.md. Awaiting your review."

User: "Looks good, carry on"

Pipeline: *runs plan phase...*

Pipeline: "Plan complete -- docs/superpowers/plans/2026-03-15-json-schema-decorators.md. Awaiting your review."

User: "Add a chunk for TypeBox format registry too"

Pipeline: *updates plan, then continues autonomously through implementation, review, PRs*
```

After "go", run autonomously. Notify on background events (see Notification Integration). Pause at `[review]` tagged phases, gates, unresolvable failures, or questions the session context cannot answer. The user can also say "pause" at any time for ad-hoc review.

### Phase announcements

**Announce every phase transition clearly.** This gives the user visibility into progress:

```
--- Pipeline Phase 1/6: Research (Dispatch, Sonnet) ---
--- Pipeline Phase 2/6: Brainstorm (in-session) ---
--- Pipeline Phase 3/6: Plan (in-session) ---
--- Pipeline Phase 4/6: Implement Wave 1 - Dispatching 3 parallel workers ---
--- Pipeline Phase 4/6: Implement Wave 2 - Dispatching 1 worker ---
--- Pipeline Phase 5/6: Review (Dispatch, Sonnet) ---
--- Pipeline Phase 6/6: Finish - Creating draft PRs ---
```

Update the state file at each phase transition. The user should be able to ask "status" at any time and get a clear answer.

### Phase ordering is mandatory

**You MUST complete each phase fully before starting the next. The order is non-negotiable:**

1. Research (if selected)
2. Brainstorm -> produces spec document
3. Plan -> produces plan document with chunks
4. Implement -> reads plan, dispatches workers per chunk
5. Review -> per-chunk review cycle
6. Finish -> PRs

**DO NOT write implementation code before a plan document exists.** If you find yourself writing source code without having first produced a file at `docs/superpowers/plans/`, STOP -- you have skipped phases.

### Phase transition protocol (mandatory)

**Every phase transition MUST follow this procedure. No exceptions.**

This exists because the model has demonstrated a tendency to skip phases when "caught up in momentum" -- e.g., jumping from implement straight to finish after receiving completion notifications, skipping the review phase entirely. Prose rules alone do not prevent this. The procedure below is the enforcement mechanism.

**Before entering ANY phase, execute these steps in order:**

1. **Read the state file.** `cat .pipeline/state/<run-id>.yaml` -- do not rely on memory of what the state file contains. Read it fresh every time.

2. **Identify the next phase.** Look at `proposed_phases` and `completed_phases`. The next phase is the first entry in `proposed_phases` that does NOT appear in `completed_phases`. This is the ONLY phase you may enter.

3. **Verify the current phase is complete.** Check that `active_phase` is empty or that the previous phase appears in `completed_phases` with `status: completed`. If the previous phase is still `in_progress`, you cannot advance.

4. **Write a gate check entry to the state file.** Before doing anything else, update the state file with:
   ```yaml
   gate_check:
     timestamp: "<ISO 8601>"
     completed_phase: "<name of phase just finished>"
     entering_phase: "<name of phase about to start>"
     prerequisite_met: true
   ```
   This creates an auditable record that you performed the check. If you cannot honestly write `prerequisite_met: true`, STOP and investigate.

5. **Announce the phase transition.** Only after steps 1-4 are complete, output the phase announcement banner.

**The most dangerous moment is when all workers complete.** Completion notifications create a false sense of "done." When you receive the last worker completion, your next action MUST be step 1 above (read the state file), NOT "now let's push and create PRs."

**Self-check prompt:** Before taking any finish-phase action (push, PR creation), ask yourself: "Have all chunks passed review? Is `review` in `completed_phases`?" If you cannot answer yes with evidence from the state file, STOP.

## Phase Building Blocks

Pipeline selects phases dynamically based on task context. Phases marked **always** are included in every run. All others are conditional.

> **Detailed reference:** For worker instruction templates, per-phase dispatch prompts, and implementation details, consult `references/phase-building-blocks.md`.

### research (conditional)
- **Tool:** `Skill("dispatch")` to spawn a `research` worker (Sonnet). Do NOT research in-session.
- **Worker uses at runtime:** deep-research (Gemini), Context7 (library docs), episodic-memory (past decisions), database MCP tools (data inspection)
- **Inputs:** Goal description, any known external APIs or standards to investigate
- **Output:** `docs/research/<topic>.md`
- **When selected:** Task involves unfamiliar tech, standards, external APIs, or user explicitly requests research

### outline_pull (conditional)
- **Tool:** `mcp__outline__search_documents` + `mcp__outline__get_document`
- **Inputs:** Keywords from the goal (feature name, service name, project key)
- **Output:** HLD/spec content loaded into context for brainstorming
- **When selected:** Task references an architect HLD, a design document, or an Outline link

### brainstorm (always)
- **Tool:** superpowers:brainstorming with terminal action override (see Terminal Action Overrides)
- **Inputs:** Research output if available, Outline HLD if available, goal description
- **Output:** `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`
- **Behaviour:** Spec reviewer subagent always runs internally. Pipeline auto-approves transitions -- no human gate. If brainstorming cannot resolve a question from available context, it asks the user in-session.
- **Terminal action:** brainstorming stops before invoking writing-plans. Pipeline reads the spec path and proceeds.

### plan (always)
- **Tool:** superpowers:writing-plans with terminal action override
- **Inputs:** Spec document from brainstorm phase
- **Output:** `docs/superpowers/plans/YYYY-MM-DD-<feature>.md` with chunks, dependencies, and per-chunk task breakdown
- **Behaviour:** Plan reviewer subagent always runs internally. No human gate.
- **Terminal action:** writing-plans stops before invoking executing-plans. Pipeline reads the plan path and proceeds to implement.

### jira_breakdown (conditional)
- **Tool:** `mcp__plugin_atlassian_atlassian` Jira APIs
- **Inputs:** Plan document, Jira project key from user
- **Behaviour:** Creates an Epic with Stories per chunk and tasks per task item. Uses standard user story templates.
- **Output:** Jira epic and story keys recorded in state file
- **When selected:** User requests it explicitly, or the goal references a Jira project key

### outline_push (conditional)
- **Tool:** `mcp__outline__create_document` or `mcp__outline__update_document`
- **Inputs:** Plan document
- **Behaviour:** Exports the plan to Outline for team and architect visibility
- **When selected:** User requests architect involvement or team visibility

### gate (conditional)
- **Behaviour:** Pause the pipeline. Write state. Send a high-priority notification: "Pipeline paused at gate -- say 'continue' to proceed." Wait. Resume when user says "continue" or "resume pipeline".
- **When selected:** User explicitly requests a pause point, or architect review is needed after outline_push

### implement (always)

**CRITICAL: You MUST read the plan file before writing any implementation code.** Parse the chunk structure, identify dependencies between chunks, and determine the execution strategy BEFORE touching code.

#### Step 1: Read and analyse the plan

Read the plan at `docs/superpowers/plans/*.md`. Extract:
- Number of chunks
- Dependencies between chunks (which chunks depend on which)
- Number of tasks per chunk
- Complexity assessment per chunk (file count, integration concerns, test requirements)

#### Step 2: Determine execution strategy per chunk

**If the plan has multiple independent chunks:** ALWAYS use Dispatch for parallel execution. This is non-negotiable. Do not implement multiple independent chunks in-session sequentially.

**Every chunk goes to Dispatch. No exceptions.** Even lightweight chunks benefit from fresh context windows. Each dispatched worker gets a completely isolated Claude Code session with no shared context pollution.

**HOW TO DISPATCH: Invoke the Dispatch skill via the Skill tool.** Do NOT use the Agent tool with run_in_background -- that shares the session context. Dispatch spawns fresh `claude -p` headless sessions with their own context windows. This is the whole point.

```
Skill("dispatch") with args: "code worker for Chunk N: <chunk description>"
```

For parallel chunks, invoke Dispatch once with instructions to spawn multiple workers.

- Single chunk plan -> Dispatch one `code` worker
- Multiple independent chunks -> Dispatch parallel `code` workers
- Multiple dependent chunks -> Dispatch in waves (see Step 3)

#### Step 3: Execute in waves

Group chunks into waves based on dependencies:

```
Wave 1: All chunks with no dependencies -> dispatch in parallel
  [wait for all Wave 1 workers to complete]
Wave 2: Chunks that depend on Wave 1 -> dispatch in parallel
  [wait for all Wave 2 workers to complete]
Wave 3: etc.
```

Example from a plan with 4 chunks:
```
Chunk 1 (backend): no deps          -> Wave 1 (dispatch)
Chunk 2 (frontend): depends on 1    -> Wave 2 }
Chunk 3 (docker): depends on 1      -> Wave 2 } dispatch in parallel
Chunk 4 (CI): depends on 1, 3       -> Wave 3 (dispatch after Wave 2)
```

Announce each wave:
```
--- Pipeline: Implement Wave 1 ---
Dispatching Chunk 1 (backend) via Dispatch code worker...

--- Pipeline: Implement Wave 2 ---
Chunk 1 complete. Dispatching Chunks 2 (frontend) and 3 (docker) in parallel...

--- Pipeline: Implement Wave 3 ---
Chunks 2, 3 complete. Dispatching Chunk 4 (CI)...
```

#### Step 4: Worker instructions

Each dispatched worker receives:
1. The full text of its chunk from the plan (not a file reference -- provide the task list directly)
2. The spec document path for reference
3. Instructions to use TDD (superpowers:test-driven-development)
4. Instructions to use systematic-debugging if tests fail
5. Instructions to run verification-before-completion before marking done
6. "Use any available skills where relevant" (skill discovery)
7. Follow any worktree or branching patterns defined in the project's CLAUDE.md

#### Step 5: After each chunk -- streaming per-chunk pipeline

When a dispatched worker completes, **fire a notification immediately:**

```bash
NOTIFY_SCRIPT=""; for p in ~/.claude/skills/notify/scripts/notify.sh ~/.agents/skills/notify/scripts/notify.sh; do [ -f "$p" ] && NOTIFY_SCRIPT="$p" && break; done
if [ -n "$NOTIFY_SCRIPT" ]; then bash "$NOTIFY_SCRIPT" "Pipeline" "Chunk N complete -- X tests passing" "default" "" "<run-id>"; else osascript -e 'display notification "Chunk N complete" with title "Pipeline"'; fi
```

**Then immediately dispatch the next phase for that chunk.** Do NOT wait for all chunks to finish the current phase before starting the next phase per chunk. Each chunk flows through its own pipeline independently:

```
chunk A: implement -> done -> review -> done -> [ready]
chunk B: implement -> done -> review -> done -> [ready]
chunk C: implement -> ................still running................-> done -> review -> done -> [ready]
                                                                     ^
                                          chunks A and B are already reviewed by this point
```

**This is the streaming execution model.** When chunks are independent (no cross-chunk dependencies between phases), each chunk advances through implement -> review -> fix_loop as soon as it completes the previous step. The finish phase is the only synchronisation point -- it gates on ALL chunks reaching `ready` status.

**When to use streaming vs batch:**
- **Streaming (default for independent chunks):** Each chunk's review dispatches as soon as its implementation completes. Use when chunks are independent repos/services with no shared state between their review phases.
- **Batch (only when cross-chunk review is needed):** Wait for all chunks to implement before reviewing. Use when a reviewer needs to see all chunks together for consistency (e.g., shared API contract changes). The proposal should specify this explicitly if needed.

**Orchestrator polling loop:** While chunks are in flight across different phases, the orchestrator monitors all active workers. On each completion event:
1. Read the state file
2. Identify which chunk just completed which phase
3. Update the chunk's status in the state file
4. If the chunk has a next phase (e.g., implement done -> review), dispatch the next worker for that chunk immediately
5. If ALL chunks have reached `ready` (review passed), proceed to finish via the gate check protocol
6. If a chunk's review finds issues, enter fix_loop for that chunk only -- other chunks continue independently

**State file tracking for streaming execution:**

Each chunk tracks its own pipeline position:
```yaml
active_phase:
  name: "implement_review_stream"
  status: in_progress
  execution:
    booking-domain-api:
      pipeline_step: review    # implement | review | fix_loop | ready
      implement_status: completed
      review_status: in_progress
      workers: { ... }
    content-domain-api:
      pipeline_step: implement  # still implementing while others are in review
      implement_status: in_progress
      review_status: pending
      workers: { ... }
```

For goals spanning multiple repositories, the plan produces one chunk per repository. Each Dispatch worker operates in that repository's worktree. PRs are created per repo.

### review (always, per-chunk)

**Reviews MUST be dispatched via the Dispatch skill, not run in-session.** Do NOT invoke pr-review-toolkit skills or Agent tool reviewers directly in the orchestrator session. The whole point is a fresh context window free of implementation bias -- the reviewer sees only the code, not the decisions that led to it.

**Dispatch the review worker for a chunk as soon as that chunk's implementation completes.** Do not wait for other chunks. This is the streaming model -- each chunk gets reviewed independently as it finishes.

Invoke `Skill("dispatch")` to spawn a `review` worker (Sonnet). The worker runs:

- pr-review-toolkit:code-reviewer -- code quality, correctness, maintainability
- pr-review-toolkit:silent-failure-hunter -- suppressed errors, bad fallbacks
- pr-review-toolkit:pr-test-analyzer -- test coverage gaps
- security-guidance / OWASP patterns -- especially on API, auth, or data-handling code

Also use any review skills discovered at runtime where relevant (type-design-analyzer for new types, comment-analyzer for new docs).

### fix_loop (conditional, triggered by review, per-chunk)
- **Trigger:** Review worker returns issues for a specific chunk
- **Scope:** Fix loop runs per-chunk. Other chunks continue their own pipeline independently.
- **Behaviour:** Invoke `Skill("dispatch")` to spawn a `code` (Opus) fix worker with the review report as input. On completion, invoke `Skill("dispatch")` again to spawn a fresh `review` worker. Loop. Do NOT fix or re-review in-session.
- **Max retries:** 3
- **On exhaustion:** Pause pipeline. Send high-priority notification with the review report. Wait for user decision.

Flow:
```
implement -> dispatch review worker -> issues found?
  no  -> continue to next chunk or finish
  yes -> dispatch fix worker -> dispatch re-review worker -> loop (max 3)
        -> still failing after 3 -> notify user, pause
```

### finish (always)

**PREREQUISITE: All chunks must have passed review before finish can run.** This is enforced by the phase transition protocol -- `review` must appear in `completed_phases` with `status: completed` before finish can begin. But because this gate was skipped in practice (bearer-auth-rollout-2026-03-17), here is the explicit checklist:

1. Read the state file (not from memory -- `cat` it)
2. Confirm `review` is in `completed_phases` with `status: completed`
3. Confirm every chunk under the review phase has `status: completed` (not `pending`, not `running`)
4. If ANY chunk review is not complete, STOP. You are about to skip review. Dispatch the missing review workers first.
5. Only after all 4 checks pass, write the gate check entry and proceed

**If you find yourself about to push code or create PRs and review is not in completed_phases, you are repeating the bearer-auth-rollout bug. STOP IMMEDIATELY.**

- **Tool:** superpowers:finishing-a-development-branch
- **PR strategy:** Proposed in the announcement step. Default: one PR per chunk for multi-chunk work, single PR for small features. User adjusts at announcement.
- **Behaviour:** Creates draft PRs. Then **fire a completion notification via Bash:**

```bash
NOTIFY_SCRIPT=""; for p in ~/.claude/skills/notify/scripts/notify.sh ~/.agents/skills/notify/scripts/notify.sh; do [ -f "$p" ] && NOTIFY_SCRIPT="$p" && break; done
if [ -n "$NOTIFY_SCRIPT" ]; then bash "$NOTIFY_SCRIPT" "Pipeline Complete" "All done. PRs ready for review." "high" "" "<run-id>"; else osascript -e 'display notification "Pipeline complete - PRs ready" with title "Pipeline" sound name "Glass"'; fi
```

- If receiving-code-review skill is available, note in the session that subsequent PR feedback should use it.
- **Archive dispatch artifacts:** After PRs are created and notifications sent, move the run's dispatch task files to an archive directory:
  ```bash
  mkdir -p .dispatch/archive/<run-id>
  mv .dispatch/tasks/<run-id>-* .dispatch/archive/<run-id>/ 2>/dev/null || true
  ```
  This prevents stale `.done` markers and plan files from confusing future runs. The archive is kept for debugging -- the user decides when to clean it up.

### final_review (conditional)
- **Tool:** `Skill("dispatch")` to spawn a `review` worker (Opus for cross-chunk reasoning)
- **Inputs:** All PRs and chunk outputs
- **Behaviour:** Cold architecture review across all PRs and chunks. Checks cross-chunk consistency, integration concerns, overall design coherence. Do NOT run this in-session -- it must be a dispatched worker with a fresh context window.
- **When selected:** Automatically included for multi-chunk work. Skipped for single-chunk work. User can add or remove at announcement.

## Model Routing

### Default model routing

| Phase | Execution | Dispatch alias | Default model |
|---|---|---|---|
| Research | **Dispatched** | `research` | Sonnet |
| Brainstorm | In-session | n/a | Inherits session model |
| Plan | In-session | n/a | Inherits session model |
| Outline / Jira / Gate | In-session | n/a | Inherits session model |
| Implementation | **Dispatched** | `code` | Opus |
| Per-chunk review | **Dispatched** | `review` | Sonnet |
| Fix loop | **Dispatched** | `code` | Opus |
| Final architecture review | **Dispatched** | `review` | Opus |
| Finish | In-session | n/a | Inherits session model |

Only brainstorm, plan, coordination (Outline/Jira/Gate), and finish run in-session. Every other phase is dispatched via `Skill("dispatch")`.

### Per-phase model overrides

Users can override the model for any phase during the announcement step. The override applies only to that pipeline run.

**How to override:** During the tweak step, the user says "use opus for final review" or "run research with haiku" or "implementation via sonnet". Pipeline maps the request to the appropriate Dispatch alias or creates a one-off alias for that run.

**Example:**
```
Pipeline: "Here's what I'm going to do:
  1. Research (Sonnet)
  2. Brainstorm
  3. Plan
  4. Implement (Opus)
  5. Review (Sonnet)
  6. Final review (Sonnet)

  Want me to adjust?"

User: "Use opus for final review, and run research with haiku"

Pipeline: "Updated:
  1. Research (Haiku)
  2. Brainstorm
  3. Plan
  4. Implement (Opus)
  5. Review (Sonnet)
  6. Final review (Opus)

  Going?"
```

**Without overrides:** The defaults above are used. They're optimised for cost -- Opus only where complex reasoning is needed (implementation, fix loop), Sonnet everywhere else.

## Terminal Action Overrides

Pipeline does not modify superpowers skill files. Instead, it prepends priority instructions whenever it invokes a superpowers skill. These act as user-level overrides and take precedence over skill instructions per the superpowers priority hierarchy (user instructions > skills > system prompt).

When invoking superpowers:brainstorming or superpowers:writing-plans, prepend the following to your instructions:

> "You are running within an autonomous pipeline. When you reach your terminal action (the point where you would normally invoke the next skill such as writing-plans or executing-plans), do NOT invoke it. Instead, report the output file path and return control. The pipeline orchestrator will handle the next phase. Continue to run all internal quality checks (spec reviewers, plan reviewers) as normal."

Specifically:
- brainstorming reaches "invoke writing-plans" -> the override says stop, report spec path. Pipeline reads the spec path and proceeds to the plan phase.
- writing-plans reaches "invoke executing-plans" -> the override says stop, report plan path. Pipeline reads the plan path and proceeds to the implement phase.

The full internal quality loops of each skill run as normal. Only the terminal action is intercepted.

## Implementation Execution Model

Read the plan document to identify chunks and dependency edges.

**Fan-out:** For each chunk whose dependencies are satisfied, invoke `Skill("dispatch")` to spawn workers. Independent chunks dispatch in parallel.

**Streaming fan-through:** When independent chunks are dispatched in parallel, each chunk flows through implement -> review -> fix_loop independently as it completes. The orchestrator does not wait for all chunks to finish implementing before dispatching review workers. See "Step 5: After each chunk -- streaming per-chunk pipeline" for the full model.

**Fan-in:** The finish phase is the single synchronisation point. Before entering finish, ALL chunks must have reached `ready` status (review passed). For dependent chunks (wave-based execution), wait for all workers in the dependency chunk to reach `completed` status in the state file before dispatching the next wave.

Each dispatched worker receives:
1. The task description from the plan
2. The path to the spec and plan documents
3. The working directory and any branching instructions from the project's CLAUDE.md
4. The terminal action override instruction
5. "Use available skills where relevant."

Workers commit locally during TDD cycles (see Worker Git Commits). They do not push until the finish phase.

## Per-Chunk Review Cycle

**IMPORTANT: Reviews are ALWAYS dispatched via `Skill("dispatch")`, never run in the orchestrator session.** Do not run review skills in-session, do not use the Agent tool for reviews. A fresh Dispatch worker gets an isolated context window -- it sees only the diff, not the implementation reasoning that led to it. This isolation is what makes the review valuable.

Invoke `Skill("dispatch")` to spawn a `review` worker for each completed chunk. The worker runs these skills in order:
1. pr-review-toolkit:code-reviewer
2. pr-review-toolkit:silent-failure-hunter
3. pr-review-toolkit:pr-test-analyzer
4. security-guidance (OWASP patterns, especially on API and auth code)

If any of these are unavailable, skip that tool and continue with the rest.

The review worker outputs a structured report: issues found (with severity), files affected, and recommended fixes. Pipeline reads the report. If issues exist, enter the fix_loop. If none, proceed.

## Notification Integration

**Fire notifications using Bash.** Resolve the notify script path by checking known locations, then call it:

```bash
# Find notify.sh -- check these paths in order
NOTIFY_SCRIPT=""
for p in ~/.claude/skills/notify/scripts/notify.sh ~/.agents/skills/notify/scripts/notify.sh; do
  [ -f "$p" ] && NOTIFY_SCRIPT="$p" && break
done

# If found, use it. If not, fall back to osascript.
if [ -n "$NOTIFY_SCRIPT" ]; then
  bash "$NOTIFY_SCRIPT" "Pipeline" "<message>" "<priority>" "<url>" "<run-id>"
else
  osascript -e 'display notification "<message>" with title "Pipeline" sound name "Glass"'
fi
```

**IMPORTANT: You MUST actually execute this Bash command at each notification point.** Do not just mention "notifying" in text -- run the Bash tool with the notification command. The user cannot see your text output if they've walked away; the notification is what reaches them.

Use `pipeline-{run-id}` as the notification group ID. Updates replace the previous notification for the same run.

### Notification trigger table

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

Only fire for Dispatch and background work. Skip notifications for in-session phase transitions -- the user is watching.

## State Management

Write and maintain `.pipeline/state/<run-id>.yaml` in the project root on every phase transition.

**run-id format:** kebab-case goal slug + date, e.g. `json-schema-decorators-2026-03-15`.

`.pipeline/` and `.dispatch/` are excluded from git via the user's global `core.excludesFile`. Do NOT add them to per-repo `.gitignore` files.

### State file YAML template

```yaml
run_id: "<kebab-case-goal-date>"
goal: "<user's original goal>"
status: proposed | in_progress | completed | failed | abandoned
started: "<ISO 8601>"
proposal_path: ".pipeline/proposals/<run-id>.md"
current_phase: "<phase name or empty if proposed>"
phase_index: <0-based index into proposed_phases -- incremented only by gate check>
proposed_phases: [<list of phase names>]
completed_phases:
  <phase_name>:
    status: completed | failed | skipped
    output: "<file path>"
    completed_at: "<ISO 8601>"
    error: "<error message if failed>"
gate_check:
  timestamp: "<ISO 8601>"
  completed_phase: "<last completed phase>"
  entering_phase: "<phase being entered>"
  prerequisite_met: true | false
active_phase:
  name: "<phase name>"
  status: in_progress | waiting_for_user | failed
  execution:
    <chunk_name>:
      tasks: ["<task-id>", ...]
      mode: dispatch_parallel | dispatch_sequential
      depends_on: <chunk_name> | null
      status: pending | running | completed | failed
      workers:
        <task-id>: { status: running | completed | failed, pr: "<#num>" }
```

Read the state file at the start of every pipeline action to ensure current state. Write it after every state change. The `phase_index` field is the authoritative pointer into `proposed_phases` -- it increments only when a gate check passes. If `phase_index` and `current_phase` disagree, the state file is corrupt; stop and investigate.

**Resume:** When the user says "continue" or "resume pipeline", read the state file, identify the current or failed phase, and re-run from there. No need to repeat completed phases.

**Status checks:** When the user asks "how's the pipeline?" or similar, read the state file and summarise progress.

## Skill Discovery

Claude Code loads all available skills at session start. Pipeline uses whatever is present. No directory scanning, no caching, no skill registry -- Claude Code handles all of this.

Dispatched workers are fresh Claude Code sessions that load the same skills automatically. Tell workers: "Use available skills where relevant." They discover what's installed naturally.

If a skill or MCP tool becomes unavailable mid-pipeline, degrade gracefully: skip its contribution and continue. Log the skip in the state file.

Hard dependencies that must be present: **superpowers** and **dispatch**. All other skills are optional.

## Worker Git Commits

CLAUDE.md states workers should not commit unless explicitly asked. Pipeline workers are an intentional exception:

Workers may commit locally during TDD cycles on their feature branches. This exception is safe because:
1. The user authorised autonomous execution by saying "go"
2. Commits are local only -- workers never push until the finish phase
3. The finish phase creates draft PRs that the user reviews before merging
4. Worktrees are disposable -- they can be deleted without affecting other branches

Workers must not push or create PRs. Push and PR creation happen only in the finish phase.

## Error Handling

On any phase failure, update the state file, then pause and notify the user unless the failure is explicitly skippable.

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

Record the failure details (phase, error, timestamp) in the state file's `completed_phases.<phase>.error` field to enable resume and audit.

## Constraints

### Dispatch vs in-session decision (non-negotiable)

| "Should I do this myself or dispatch it?" | Answer |
|---|---|
| Research | **Dispatch.** Always. |
| Brainstorm (superpowers:brainstorming) | In-session. |
| Plan (superpowers:writing-plans) | In-session. |
| Outline pull/push, Jira breakdown, gates | In-session. |
| Implementation (any chunk, any size) | **Dispatch.** Always. |
| Review (any review skill) | **Dispatch.** Always. |
| Fix loop (code fix after review) | **Dispatch.** Always. |
| Final architecture review | **Dispatch.** Always. |
| Finish (PR creation) | In-session. |

**If it writes code or reviews code, it MUST be dispatched.** No exceptions. No "just this small one." No "I'll do it quickly in-session." Dispatch every time via `Skill("dispatch")`.

**The Agent tool is BANNED in this skill.** Do not use `Agent(...)` with any subagent_type, with or without run_in_background, for any purpose. Agent tool spawns subagents that share the orchestrator's context window. Dispatch spawns fresh `claude -p` sessions with completely isolated context. The isolation is the point.

### Other constraints

- **CLAUDE.md always takes precedence** over any pipeline behaviour. Code style, git rules, package manager rules, no eslint-disable, full function declarations -- all apply to every worker and every in-session action.
- **Two hard dependencies:** superpowers and dispatch. Pipeline errors clearly if either is missing.
- **All other skills are optional.** Discover and use them, but degrade gracefully if absent.
- **Pipeline never replaces superpowers.** It invokes superpowers skills and intercepts their terminal actions, but their internal quality loops run in full.
- **Pipeline never replaces Dispatch.** Dispatch is the execution layer for all work outside this session. Pipeline is the orchestrator above it.
- **Branching:** Workers should follow the project's CLAUDE.md for branching and worktree patterns. Create feature branches for implementation work.
- **Tests always run.** Workers cannot claim completion without passing tests. verification-before-completion is non-negotiable.
- **No push until finish.** Workers commit locally only. Push and PR creation are finish-phase actions.
