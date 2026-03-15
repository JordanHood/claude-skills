# State Management

Pipeline state is persisted to disk so runs can survive interruptions and be resumed without losing progress.

## Location

State files live at `.pipeline/state/<run-id>.yaml` relative to the project directory where the pipeline was started.

## Run ID Format

Run IDs are kebab-case slugs derived from the goal and the current date:

```
json-schema-decorators-2026-03-15
```

When multiple runs share the same goal on the same day, append a counter suffix: `-2`, `-3`, etc.

## YAML Schema

```yaml
run_id: "<kebab-case-goal-date>"
goal: "<user's original goal>"
status: proposed | in_progress | completed | failed | abandoned
started: "<ISO 8601>"
proposal_path: ".pipeline/proposals/<run-id>.md"
current_phase: "<phase name or empty if proposed>"
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

## Lifecycle

### Creating state

Pipeline creates the state file when it writes the proposal (BEFORE the user says "go"). At creation time, record:

- `run_id`
- `goal`
- `proposed_phases`
- `started`
- `status` set to `proposed`
- `current_phase` left empty (no phase is executing yet)
- `proposal_path` set to `.pipeline/proposals/<run-id>.md`

When the user says "go", update the state:
- `status` transitions from `proposed` to `in_progress`
- `current_phase` set to the first phase name

If the user tweaks phases before saying "go", update `proposed_phases` in the state file to match.

If the user abandons the proposal (walks away, starts a different task), the state file remains with `status: proposed` and can be cleaned up or resumed later.

### Updating state

After each phase completes, update the state file:

- Move the completed phase entry into `completed_phases` with `status`, `output`, and `completed_at`
- Advance `current_phase` to the next phase name
- Update `active_phase` to reflect the newly running phase

Write the file after every meaningful state transition, not just at phase boundaries.

### Reading state for resume

When the user says "continue" or "resume pipeline":

1. List files in `.pipeline/state/` sorted by modification time
2. Read the most recent file
3. Inspect `current_phase` to determine where execution left off
4. Re-execute from that phase forward, skipping phases already in `completed_phases` with `status: completed`

If the user provides a run ID explicitly, load that specific file instead of the most recent.

### Failure recording

On any phase failure:

1. Set the phase's `status` to `failed`
2. Populate `error` with the failure message or stack trace excerpt
3. Write the state file
4. Pause pipeline execution and notify the user with the run ID and error

Do not advance `current_phase` on failure. The failed phase remains current so a resume will retry it.

## Concurrent Pipelines

Each run gets its own state file keyed by run ID. Multiple pipelines can run simultaneously in the same project without conflict. To list active runs:

```
ls .pipeline/state/
```

## Gitignore

`.pipeline/` is runtime state and should not be committed. On the first pipeline run in a project, check whether `.pipeline` appears in `.gitignore`. If it does not, append it:

```
.pipeline/
```

Do this before writing the first state file so the file is never tracked.

## Cleanup

State files are retained after a run completes. They serve as an audit trail and debugging aid. To remove all pipeline state:

```
rm -rf .pipeline/
```

Individual run files can also be deleted selectively from `.pipeline/state/`.
