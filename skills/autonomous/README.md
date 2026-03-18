# autonomous

Autonomous development pipeline for Claude Code. Give it a goal, say "go", walk away. Come back to draft PRs.

## What it does

Detects multi-phase tasks and orchestrates the full dev lifecycle autonomously:

1. **Research** -- dispatches a Sonnet worker to investigate best practices, patterns, APIs
2. **Brainstorm** -- designs the architecture with automated spec review (catches issues before code)
3. **Plan** -- writes a chunked implementation plan with dependency graph
4. **Implement** -- dispatches parallel Opus workers per chunk in waves
5. **Review** -- dispatches Sonnet reviewers for code quality, silent failures, test coverage, OWASP
6. **Fix loop** -- auto-fixes review issues (max 3 retries, then asks you)
7. **Finish** -- opens draft PRs

Phases are assembled dynamically -- no fixed pipelines. The skill reads the task and decides what's needed.

## Install

```bash
npx skills add JordanHood/claude-skills --skill autonomous
```

## Usage

Triggers ambiently on multi-phase tasks, or invoke with `/autonomous`.

```
Build a real-time chat app with WebSocket rooms, JWT auth,
Redis pub/sub, SQLite, Docker, and CI end to end
```

The skill proposes phases, you tweak if needed, say "go". It runs autonomously with notifications on worker completion.

### Tweaking before "go"

- Add `[review]` to any phase to pause for your review before continuing
- Override models: "use haiku for research"
- Add phases: "also break the plan into Jira stories under PROJ-100"
- Remove phases: "skip research, I know the domain"

## Dependencies

**Required:**
- [superpowers](https://github.com/obra/superpowers) >= 5.0.0
- [dispatch](https://github.com/bassimeledath/dispatch) >= 2.0.0

**Optional (auto-discovered):**
- notify (this repo)
- [deep-research](https://github.com/sanjay3290/ai-skills/tree/main/skills/deep-research)
- [pr-review-toolkit](https://github.com/anthropics/plugins)
- Any other installed skills -- the pipeline discovers and uses what's available

## Configuration

### Dispatch aliases

Merge into `~/.dispatch/config.yaml`:

```yaml
aliases:
  code:     { model: opus,   prompt: "Implementation. TDD. Follow CLAUDE.md." }
  review:   { model: sonnet, prompt: "Code review. Use pr-review-toolkit." }
  research: { model: sonnet, prompt: "Research. Use deep-research if needed." }
  sweep:    { model: opus,   prompt: "Parallel workers, one per service." }
```

### CLAUDE.md routing

Add to `~/.claude/CLAUDE.md` so it triggers before superpowers:brainstorming:

```markdown
- When a task involves multiple phases, spans multiple services, or uses
  phrases like "end to end", "full workflow", "go away and do" -- use the
  autonomous skill INSTEAD of brainstorming directly.
- For single-phase tasks, let superpowers flow as normal.
```

## How it works

**Superpowers** handles quality (spec review, TDD, code review loops). **Dispatch** handles parallelism (fresh context per worker). **Autonomous** orchestrates them -- intercepting superpowers' phase transitions, managing state, routing models, and dispatching workers in dependency-aware waves.

Workers discover and use any installed skills at runtime. No hardcoded skill list.

## State management

Runtime state persists at `.pipeline/state/<run-id>.yaml`. Enables resume after context compaction ("resume pipeline"), status checks, and concurrent pipeline runs.

Completed dispatch artifacts are archived to `.dispatch/archive/<run-id>/` during the finish phase. Clean up archives at your discretion.

### Git exclusions

`.pipeline/` and `.dispatch/` directories are created per-repo at runtime. To keep them out of `git status` globally without per-repo `.gitignore` entries, add them to your global excludes file:

```bash
echo -e ".pipeline/\n.dispatch/" >> ~/.gitignore_global
git config --global core.excludesFile ~/.gitignore_global
```
