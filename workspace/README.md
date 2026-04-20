# Agent Workspace

This folder is the shared writable workspace for human and AI coding sessions.

Start the coding agent with this project folder mounted as writable:

```bash
cd trading-bot
codex
```

Use this folder for collaboration artifacts that should live beside the code without mixing into application modules.

## Layout

- `agent_memory/`: Private working notes the agent may update during a session.
- `scratch/`: Temporary experiments, snippets, and one-off outputs.
- `tasks/`: Handoff notes, task briefs, and review checklists.

## Rules

1. Keep source code changes in the real project files, not inside `workspace/`.
2. Do not put secrets, tokens, private keys, or account credentials here.
3. Treat `agent_memory/` and `scratch/` as local-only unless a specific file is intentionally promoted into docs or code.
4. Before release, run the packaging script and check the archive does not include private scratch data.

## Ready-For-Codex Checklist

1. Open the project root as the current working directory.
2. Make sure the sandbox mode allows writes to the project root.
3. Use a git branch when the project is inside a git repository.
4. Tell the agent the exact folder it can use for work memory: `workspace/agent_memory/`.
5. Review the diff before publishing.
