# One prompt to a full app -- built a pipeline skill that makes Claude Code autonomous

Been messing with Claude Code skills for the past few days and ended up building something that I think is genuinely useful.

Basically I got frustrated with manually chaining brainstorming -> planning -> implementation -> review. Every time I'd finish brainstorming it would ask "shall I invoke writing-plans?" and I'd say yes. Then planning finishes and asks about execution. Then I'm sitting there watching workers. It felt like I was the glue.

So I built a pipeline skill that does the orchestration for me. You give it a goal, it figures out what phases are needed, proposes them, you say "go" (or tweak first), and it runs the whole thing autonomously.

Tested it on "build a real-time chat app with WebSocket rooms, JWT auth, Redis pub/sub, SQLite, Docker, CI" -- one prompt. It researched Fastify WebSocket patterns via Gemini, designed the architecture (spec reviewer caught 12 design issues before any code was written), wrote a chunked plan, dispatched parallel workers for independent chunks, reviewed everything, auto-fixed 15 issues the reviewer found, and finished with 88 tests passing at 86% coverage.

55 minutes, about $19 on API billing. I said "go" once and walked away.

The thing that surprised me most was the spec review loop. Before a single line of code existed, the reviewer found a Redis channel naming inconsistency that would have caused silent message delivery failures across instances. That alone justified the whole approach.

It's three skills in a monorepo -- pipeline (the orchestrator), notify (macOS desktop notifications for when workers finish), and guardrails (example safety hooks since workers run with --dangerously-skip-permissions). Depends on superpowers and dispatch which do the actual heavy lifting. Pipeline just wires them together and makes the whole thing hands-off.

Still a work in progress -- actively iterating on it and there are rough edges to smooth out. But the core flow works and it's already changed how I approach building things with Claude Code.

[video]
