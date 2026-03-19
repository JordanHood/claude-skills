# Claude Autonomous Skills

Four skills that turn Claude Code into an autonomous development system. Give it a goal, say "go", walk away. Come back to draft PRs.

## The skills

| Skill | What it does | Install |
|-------|-------------|---------|
| [**autonomous**](skills/autonomous/) | Orchestrates research, design, planning, parallel implementation, review, and PRs from a single prompt | `npx skills add JordanHood/claude-skills --skill autonomous` |
| [**notify**](skills/notify/) | Desktop and mobile notifications for worker completion, errors, and review gates | `npx skills add JordanHood/claude-skills --skill notify` |
| [**guardrails**](skills/guardrails/) | Safety hooks that protect against destructive operations in autonomous workers | `npx skills add JordanHood/claude-skills --skill guardrails` |
| [**dispatch-dashboard**](skills/dispatch-dashboard/) | Live browser dashboard for monitoring dispatch worker progress and status | `npx skills add JordanHood/claude-skills --skill dispatch-dashboard` |

## How it looks

[Watch the demo (79s)](demo/autonomous-demo.mp4)

```
> Build a real-time chat app with WebSocket rooms, JWT auth,
  Redis pub/sub, SQLite, Docker, and CI end to end

Pipeline: Real-Time Chat Application

  1. Research    (Dispatch, Sonnet)  -- best practices
  2. Brainstorm  (in-session, Opus)  -- architecture + spec review
  3. Plan        (in-session, Opus)  -- chunked with dependencies
  4. Implement   (Dispatch, Opus)    -- parallel workers in waves
  5. Review      (Dispatch, Sonnet)  -- code review, OWASP, test coverage
  6. Finish      (in-session)        -- draft PRs

  Want me to adjust anything before I start?

> go

  ... 55 minutes later ...

  88 tests | 86% coverage | 12 spec issues caught | 15 code issues fixed
```

## How it works

**Superpowers** provides quality -- brainstorming, TDD, spec and code review loops.
**Dispatch** provides parallelism -- fresh context windows per worker.
**Autonomous** is the glue -- chains them together so you don't have to sit there manually triggering each phase.

Workers discover and use any installed skills at runtime. Install `deep-research` and they use Gemini. Install `fastify-best-practices` and they follow Fastify patterns. No configuration needed.

## Quick start

```bash
# Install all four
npx skills add JordanHood/claude-skills --skill autonomous
npx skills add JordanHood/claude-skills --skill notify
npx skills add JordanHood/claude-skills --skill guardrails
npx skills add JordanHood/claude-skills --skill dispatch-dashboard

# Set up hooks (copy from guardrails/examples to ~/.claude/hooks/)
# Configure Dispatch aliases (see skills/autonomous/references/)
# Add CLAUDE.md routing rule (see skills/autonomous/README.md)
```

Each skill's README has detailed setup instructions.

## Dependencies

- [superpowers](https://github.com/obra/superpowers) (required)
- [dispatch](https://github.com/bassimeledath/dispatch) (required)
- [deep-research](https://github.com/sanjay3290/ai-skills/tree/main/skills/deep-research) (optional)
- [pr-review-toolkit](https://github.com/anthropics/plugins) (optional)

## Status

Work in progress. The core flow works and has been tested on multi-chunk projects with parallel dispatch, spec review loops, and code review with auto-fix. Rough edges are being smoothed out.

## License

MIT
