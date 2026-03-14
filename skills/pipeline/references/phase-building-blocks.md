# Phase Building Blocks

Detailed reference for each phase available to the pipeline orchestrator. Phases are selected dynamically based on task context -- the pipeline does not follow a fixed sequence.

---

## Terminal Action Override

When invoking superpowers skills (brainstorm, plan), the pipeline prepends this instruction to suppress the skill's built-in terminal action and return control to the orchestrator:

> "You are running within an autonomous pipeline. When you reach your terminal action (the point where you would normally invoke the next skill such as writing-plans or executing-plans), do NOT invoke it. Instead, report the output file path and return control. The pipeline orchestrator will handle the next phase. Continue to run all internal quality checks (spec reviewers, plan reviewers) as normal."

This works because CLAUDE.md user instructions take priority over skill instructions. The skills run in full fidelity (including spec reviewers and plan reviewers) but the pipeline controls what happens after each one completes.

---

## research

**Purpose:** Gather background knowledge before design begins. Covers unfamiliar tech, standards, external APIs, or historical decisions.

**Execution model:** Dispatch with the `research` alias (Sonnet -- coordination, not deep reasoning).

**Worker instructions template:**
```
Goal: Research <topic> to inform the design of <feature>.

Discover and use available tools:
- deep-research (Gemini) for broad technical investigation
- Context7 for library and framework documentation
- episodic-memory for past decisions and patterns in this codebase
- mysql/postgres MCP tools for data schema inspection if relevant

Output a structured research document covering:
- Key findings relevant to the implementation goal
- Constraints, gotchas, and edge cases
- Prior art and recommended patterns
- Open questions to resolve during design

Output file: docs/research/<topic>.md

Use available skills where relevant. Report the output file path when done.
```

**Output:** `docs/research/<topic>.md`

**When selected:** Task involves unfamiliar technology, external API contracts, published standards, or the user explicitly asks for research.

**On empty results:** Skip research, proceed to brainstorm with available context. Notify user that research returned nothing useful.

---

## outline_pull

**Purpose:** Load an existing HLD or architectural spec from Outline into the pipeline's context before brainstorming begins.

**Execution model:** In-session MCP calls. No Dispatch.

**Tools used:**
- `mcp__outline__search_documents` -- locate the document by title or keywords from the task goal
- `mcp__outline__get_document` -- retrieve full content

**Behaviour:** The pipeline reads the document content into context. It is then passed as input to the brainstorm phase alongside the research output and task goal.

**Output:** HLD/spec content held in context. No file written.

**When selected:** Task references an architect HLD, an Outline document by name, or language like "implement the design in Outline" or "follow the HLD".

---

## brainstorm

**Purpose:** Produce a reviewed design spec for the feature.

**Execution model:** In-session invocation of `superpowers:brainstorming` with terminal action override prepended.

**Inputs:**
- Research output from `docs/research/<topic>.md` (if research phase ran)
- Outline HLD content (if outline_pull phase ran)
- Original task goal

**Terminal action override applies.** The spec reviewer subagent runs as normal. The brainstorming skill does not invoke writing-plans -- it reports the spec file path and returns control to the pipeline.

**Behaviour on ambiguity:** If brainstorming cannot resolve a design question from available context, it asks the user directly in the current session. The pipeline waits for the answer before proceeding.

**Output:** `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`

**When selected:** Any task that benefits from a design phase before planning. Automatically selected for multi-phase work. Can be skipped if the user provides an explicit, complete spec upfront.

---

## plan

**Purpose:** Produce a reviewed implementation plan with chunks, dependencies, and per-task breakdown.

**Execution model:** In-session invocation of `superpowers:writing-plans` with terminal action override prepended.

**Inputs:** Spec document produced by the brainstorm phase.

**Terminal action override applies.** The plan reviewer subagent runs as normal. writing-plans does not invoke executing-plans -- it reports the plan file path and returns control to the pipeline.

**Plan structure the pipeline expects:**
- Named chunks with explicit dependency declarations
- Per-chunk task list
- For each task: enough context for a Dispatch worker to operate independently

**Output:** `docs/superpowers/plans/YYYY-MM-DD-<feature>.md`

**When selected:** Always follows brainstorm when brainstorm is in the phase list. Can also be invoked directly when the user provides a spec and wants planning only.

---

## jira_breakdown

**Purpose:** Convert the implementation plan into a Jira Epic with Stories per chunk and sub-tasks per task item.

**Execution model:** In-session MCP calls via `mcp__plugin_atlassian_atlassian`.

**Inputs:** Plan document from `docs/superpowers/plans/YYYY-MM-DD-<feature>.md`.

**Behaviour:**
- Creates one Epic representing the overall feature, linked to any project key the user referenced
- Creates one Story per plan chunk using the standard user story template: "As a [role], I want [capability] so that [value]"
- Creates sub-tasks under each Story for individual tasks within the chunk
- Adds chunk dependency information to Story descriptions
- Reports created Epic and Story keys on completion

**When selected:** User requests Jira breakdown explicitly, or the task references a Jira project key (e.g. TSPEC-123, BOOK-456).

---

## outline_push

**Purpose:** Export the implementation plan to Outline for team or architect visibility.

**Execution model:** In-session MCP calls.

**Tools used:**
- `mcp__outline__create_document` -- if no matching document exists
- `mcp__outline__update_document` -- if a matching document already exists in the target collection

**Inputs:** Plan document from `docs/superpowers/plans/YYYY-MM-DD-<feature>.md`.

**Behaviour:** The plan content is published to the appropriate Outline collection. If a gate phase follows, this is typically why -- the architect needs to review before implementation begins.

**When selected:** User requests architect involvement, team visibility, or says something like "push the plan to Outline" or "share with the team".

---

## gate

**Purpose:** Pause the pipeline at a defined point and wait for explicit human sign-off before continuing.

**Execution model:** In-session. No Dispatch.

**Behaviour:**
1. Pipeline reaches the gate phase and stops execution of subsequent phases
2. Sends a high-priority notification (title: "Pipeline Paused", message describes what is waiting and what to review)
3. Writes current state to `.pipeline/state/<run-id>.yaml` with `current_phase: gate` and `status: waiting`
4. Waits for the user to say "continue" or "resume" in the session

**On resume:** Pipeline reads state, identifies the next phase after the gate, and continues from there.

**When selected:** User explicitly requests a pause point ("pause after the plan", "wait for my approval before building"). Also automatically inserted after outline_push when architect review was the reason for the push.

---

## implement

**Purpose:** Execute the implementation plan, producing working, tested code.

**Execution model:** Fan-out / fan-in based on plan chunk structure.

```
Pipeline reads plan -> identifies chunks and dependencies

Independent tasks within a chunk -> Dispatch parallel Opus workers, each in own worktree
Sequential/dependent tasks -> subagent-driven-development in current session
Single simple task -> subagent in current session

Fan-in: pipeline waits for all workers in a chunk before starting the next chunk
```

**Dispatch alias:** `code` (Opus -- complex code generation requires deeper reasoning).

**Worker instructions template:**
```
You are implementing chunk <N> of a pipeline execution.

Plan file: <path to plan document>
Your tasks: <list of task names from this chunk>
Repository: <repo path>
Worktree: create one if .bare/ is detected, otherwise work in place

Steps:
1. Create worktree if .bare/ exists: gw worktree add <path> <branch>
2. Install node_modules in the worktree
3. Use superpowers:test-driven-development for each task
4. Use superpowers:systematic-debugging if tests fail
5. Use superpowers:verification-before-completion before marking any task done
6. Discover and use other available skills (fastify, node, security-guidance, etc.)

Commit each task locally as you complete it. Do not push.

When all tasks in your chunk are complete, report:
- Tasks completed
- Worktree path / branch name
- Any issues encountered

Use available skills where relevant. NEVER delete files you did not create.
```

**Per-worker behaviour:**
- Creates worktree if `.bare/` is detected in the repo
- Installs node_modules
- Uses TDD for each task
- Uses systematic-debugging if tests fail and cannot self-resolve
- Uses verification-before-completion before reporting a task done
- Discovers and uses other installed skills relevant to the work
- Commits locally per task, never pushes

**When selected:** Always. Implement is the core phase of every pipeline run.

---

## review

**Purpose:** Cold, unbiased code review of each completed chunk's output.

**Execution model:** Dispatch with the `review` alias (Sonnet -- fast, pattern-based checklist work, no implementation bias from a fresh context window).

**Dispatch alias:** `review` (Sonnet).

**Worker instructions template:**
```
You are performing a cold code review of chunk <N> from a pipeline implementation.

Branch / worktree to review: <branch or path>
Plan chunk for context: <chunk section from plan document>

Run each of the following review skills against the changes in this branch:
- pr-review-toolkit:code-reviewer
- pr-review-toolkit:silent-failure-hunter
- pr-review-toolkit:pr-test-analyzer
- security-guidance (especially on any API, auth, or data-handling changes)

Also discover and run any other installed review skills that are relevant to the
type of code changed (e.g. type-design-analyzer for new types, comment-analyzer
for documentation changes).

Produce a single structured review report at:
  .pipeline/review/<run-id>/chunk-<N>-review.md

Format:
- Summary: pass / needs-fixes
- Issues: list of issues with severity (blocking / non-blocking), file, line, description
- Suggestions: optional non-blocking improvements

Report the output file path when done.
```

**Output:** `.pipeline/review/<run-id>/chunk-<N>-review.md`

**When selected:** Always runs after each implement chunk completes. Cannot be skipped.

---

## fix_loop

**Purpose:** Dispatch a targeted fix worker when review finds blocking issues, then re-review. Loops until clean or retry limit reached.

**Execution model:** Dispatch with the `code` alias (Opus -- needs to understand and fix code).

**Dispatch alias:** `code` (Opus).

**Max retries:** 3. On exhaustion: notify user, pause pipeline, surface full review report for human decision.

**Flow:**
```
implement -> review -> issues found?
  no  -> continue to next chunk or finish
  yes -> dispatch fix worker -> re-review -> loop (max 3)
        -> still failing after 3 retries -> notify human, pause
```

**Fix worker instructions template:**
```
You are fixing code review issues in chunk <N> of a pipeline execution.

Branch / worktree: <path>
Review report: <path to review report>

Address all blocking issues listed in the review report.
Non-blocking suggestions are at your discretion.

After fixing, run all tests. Use superpowers:verification-before-completion
before reporting done.

Report:
- Issues addressed
- Issues deferred (with rationale)
- Test results

Use available skills where relevant. NEVER delete files you did not create.
```

**When selected:** Automatically triggered whenever a review phase returns `needs-fixes`. Not user-configurable.

---

## finish

**Purpose:** Create draft PRs from the completed worktrees.

**Execution model:** In-session invocation of `superpowers:finishing-a-development-branch`.

**PR strategy:** Proposed at the pipeline announcement step and confirmed before "Go". Options:
- One PR per chunk (default for multi-chunk work)
- Single PR (default for small, single-chunk work)

**Behaviour:**
- Creates draft PRs for each branch/chunk
- Notifies with PR URLs (high-priority notification)
- If `superpowers:receiving-code-review` is available, the completion notification includes a note that subsequent PR feedback should be handled with that skill

**When selected:** Always the final phase before final_review (if applicable). Creates the reviewable artifacts from the pipeline run.

---

## final_review

**Purpose:** Cross-chunk architecture review across all PRs and chunks together. Catches integration concerns, cross-chunk inconsistencies, and overall design coherence issues that per-chunk review cannot see.

**Execution model:** Dispatch with the `deep-review` alias (Opus -- cross-chunk reasoning requires deeper model).

**Dispatch alias:** `deep-review` (Opus).

**Worker instructions template:**
```
You are performing a final architecture review across all chunks of a completed
pipeline implementation.

Goal: <original pipeline goal>
Plan document: <path>
PR list: <list of PR URLs or branch names, one per chunk>

Review all changes together as a unified system. Check for:
- Cross-chunk consistency (naming, interfaces, data contracts)
- Integration concerns (do the pieces fit together correctly?)
- Overall design coherence against the original spec and plan
- Anything that per-chunk review could not see in isolation

Produce a final architecture review report at:
  .pipeline/review/<run-id>/final-architecture-review.md

Format:
- Summary: pass / needs-attention
- Cross-chunk issues: list with severity and affected chunks
- Integration concerns: any pieces that need rework before merge
- Positive notes: things done particularly well

Report the output file path when done.
```

**Output:** `.pipeline/review/<run-id>/final-architecture-review.md`

**When selected:** Automatically included for multi-chunk work. Automatically skipped for single-chunk work. User can add or remove at the announcement step.

---

## Model Routing Summary

| Phase | Dispatch alias | Model | Rationale |
|---|---|---|---|
| research | `research` | Sonnet | Coordination and synthesis, not deep reasoning |
| implement | `code` | Opus | Complex code generation and problem solving |
| review (per-chunk) | `review` | Sonnet | Pattern matching and checklist-based review |
| fix_loop | `code` | Opus | Must understand and fix non-trivial code issues |
| final_review | `deep-review` | Opus | Cross-chunk reasoning across multiple PRs |
| brainstorm, plan | n/a (in-session) | Inherits session model | Creative design decisions benefit from continuity |
| outline_pull, outline_push, jira_breakdown, gate, finish | n/a (in-session) | Inherits session model | Coordination tasks, no heavy reasoning needed |
