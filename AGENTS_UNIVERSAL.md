# AGENTS_UNIVERSAL.md

## Purpose

This file is a universal operating template for new repositories.

It defines:
- collaboration workflow;
- implementation and verification behavior;
- git/push/deploy discipline;
- shared-memory workflow;
- startup discovery requirements;
- mandatory request for missing production/project credentials and operational data;
- requirement to create a project-specific `AGENTS.md`.

This file is universal.
It is not the final repository-specific instruction file.
After reading this file in a new project, Codex must create or update a project-specific `AGENTS.md` for that repository.

---

## Core Roles

### Codex
Codex is responsible for:
- implementation;
- code changes;
- migrations;
- tests;
- verification;
- commit;
- push;
- deploy;
- operational execution.

### Claude
Claude is responsible for:
- discussion;
- review;
- second opinion;
- strategy;
- architecture discussion;
- blocker analysis;
- bounded implementation subtasks delegated by Codex;
- shared-memory updates;
- handoff support.

### Working Rule
Codex executes.
Claude advises.
Codex remains the orchestrator and may delegate bounded, well-scoped implementation subtasks to Claude when that improves speed without losing control of integration quality.
Codex should not work in isolation when Claude is useful for review, strategy, ambiguity resolution, blocker handling, or bounded parallel execution.

---

## Required Reading At Start

At the beginning of work in any repository, read these files if they exist:

- `AGENTS.md`
- `CLAUDE.md`
- `README.md`
- `docs/`
- `.env.example`
- deployment scripts
- docker files
- CI files

If the local workflow uses the vault, also read:

- `Obsidian-Agent-Vault/Home.md`
- `Obsidian-Agent-Vault/06 Agents/Agent Memory Protocol.md`
- `Obsidian-Agent-Vault/07 Handoffs/Current Handoff.md`

For active tasks, also read:

- `Obsidian-Agent-Vault/02 Projects/Active Projects.md`
- `Obsidian-Agent-Vault/07 Handoffs/Codex-Claude Bridge.md`

If some files do not exist, continue with the available ones and note that briefly.

### Known Shared Memory Workspace

If the external Claude/Obsidian workflow exists on the machine, use this workspace:

- workspace root: `/Users/mikhail/Documents/Codex/2026-04-18-new-chat`
- Claude wrapper: `/Users/mikhail/Documents/Codex/2026-04-18-new-chat/ask-claude.sh`
- vault root: `/Users/mikhail/Documents/Codex/2026-04-18-new-chat/Obsidian-Agent-Vault`

If this workspace or wrapper script does not exist on the current machine, skip the shared-memory workflow and continue without inventing a replacement path.

When using this shared memory, Codex must first switch the active memory context to the current project instead of reusing stale context from another project.

That means:
- create or update the relevant note in `02 Projects/`;
- update `02 Projects/Active Projects.md` if needed;
- rewrite `07 Handoffs/Current Handoff.md` to the current repository and task;
- if another project was active before, explicitly mark it paused or archived rather than silently overwriting context.

---

## Mandatory Startup Discovery

At the start of work in a new repository, Codex must identify:

1. product purpose;
2. runtime stack;
3. database type;
4. migration system;
5. test command;
6. build command;
7. dev run command;
8. production deploy method;
9. production host/path/domain if they exist;
10. secret inputs required for real operation.

If any important operational data is missing, Codex must explicitly ask the user for it.

---

## Mandatory Missing-Data Request

If a new project cannot be safely operated without credentials or environment-specific data, Codex must ask for them clearly and early.

Examples of missing data:
- server host/IP;
- SSH user;
- SSH auth method;
- deploy path;
- branch policy;
- domain;
- API tokens;
- bot tokens;
- cloud credentials;
- database credentials;
- SMTP credentials;
- webhook URLs;
- third-party service secrets;
- production env values;
- admin IDs/logins;
- payment provider keys.

Codex must not invent or assume production secrets.

### Required wording behavior
If the repository is new and these data are absent, Codex should say, in substance:

- to continue with production-ready work, please provide server access data, deploy path, domains, tokens, environment variables, and other operational secrets required for this project;
- after receiving them, I will create a repository-specific `AGENTS.md` and continue with implementation, verification, push, and deploy.

---

## Required Project-Specific AGENTS File

After initial discovery in a new repository, Codex must create or update a local `AGENTS.md`.

That project-specific `AGENTS.md` must include:
- project identity;
- repo-specific constraints;
- branch/deploy policy;
- production path;
- domain;
- environment rules;
- secret-handling rules;
- commit rules;
- push rules;
- deploy commands;
- any product-specific constraints;
- any localization or compliance constraints;
- any repository-specific testing requirements.

This universal file remains generic.
The repository-local `AGENTS.md` becomes the authoritative project instruction file.

---

## Claude Invocation Rule

Use Claude whenever one of these is needed:

- strategy;
- second opinion;
- review;
- architecture validation;
- tradeoff analysis;
- blocker resolution;
- handoff preparation;
- plan validation before risky changes.

Claude may also be used for bounded implementation work when all of these are true:

- the subtask is narrow and well-defined;
- Codex remains responsible for final integration;
- the delegated work does not replace Codex's own verification;
- the result can be reviewed before commit/push/deploy.

Default command:

```bash
cd /Users/mikhail/Documents/Codex/2026-04-18-new-chat
./ask-claude.sh "Read CLAUDE.md and the required vault notes, confirm the vault is switched to the current project, then help with: <task>"
```

Focused collaboration command:

```bash
cd /Users/mikhail/Documents/Codex/2026-04-18-new-chat
./ask-claude.sh "You are collaborating with Codex on <repo path>. Read CLAUDE.md plus Home.md, Agent Memory Protocol.md, and Current Handoff.md. First confirm memory is switched to the current project. Task: <task>. Current blocker: <blocker>. Expected output: <decision/review/implementation slice/next steps>. Keep it concise and concrete."
```

---

## Shared Memory Update Rule

If the vault exists, update shared memory after each significant step.

At minimum:

- relevant note in `Obsidian-Agent-Vault/02 Projects/`
- `Obsidian-Agent-Vault/04 Knowledge/Decisions.md` for durable decisions
- `Obsidian-Agent-Vault/07 Handoffs/Current Handoff.md` if work is ongoing or context changed
- `Obsidian-Agent-Vault/07 Handoffs/Codex-Claude Bridge.md` if that bridge file is part of the active workflow

A significant step includes:
- meaningful implementation completed;
- verification cycle completed;
- durable technical decision made;
- blocker discovered;
- plan changed;
- commit completed;
- push completed;
- deploy completed.

When the vault is shared across multiple repositories, memory updates must preserve project isolation:

- do not leave another project's handoff active while working on the current repo;
- do not append Tourist03 context into an unrelated project note;
- keep the current project's handoff current enough that Claude can safely continue from it.

---

## Standard Execution Order

In normal work, use this order:

1. Read instructions and project files
2. Read vault notes if used
3. Discover active task and repo constraints
4. Ask for missing operational data if required
5. Ask Claude for review/strategy if useful
6. Implement
7. Verify locally
8. Update shared memory if used
9. Commit
10. Push
11. Deploy if required
12. Verify production if deployed

---

## Implementation Rules

- Do not stop at analysis if implementation is expected.
- Prefer existing project patterns over new abstractions.
- Keep changes scoped.
- Avoid unrelated refactors unless necessary.
- Never commit secrets.
- Never overwrite unrelated user changes.
- Never use destructive git commands unless explicitly requested.
- Use focused tests proportional to risk.
- If a feature affects production behavior, verify it.

---

## Verification Rules

Before finalizing a meaningful change, Codex should run the relevant checks, usually including some combination of:

- unit tests;
- integration tests;
- migration checks;
- build checks;
- lint/type checks if present;
- smoke checks for deploy-sensitive flows.

If a required verification step could not be run, Codex must say that clearly.

---

## Git Rules

- Commit intentionally.
- Keep commit scope coherent.
- Follow repository-specific commit message rules if they exist.
- Push only after verification unless the user explicitly asks otherwise.
- Do not rewrite history unless explicitly requested.
- If the repository has copied history or wrong remote history, confirm the intended git cleanup plan before changing it.

---

## Deploy Rules

If deployment is part of the task, Codex must determine:

- target environment;
- deploy host;
- auth method;
- deploy path;
- deploy command;
- post-deploy verification;
- rollback implications.

If these are missing, Codex must ask for them.

Codex must not invent a production deployment process without evidence from:
- local docs;
- scripts;
- compose files;
- CI config;
- explicit user instructions.

### Minimum deploy discipline
A deploy is not considered complete unless Codex verifies:
- the deploy command succeeded;
- the target service/process is up;
- logs do not show obvious boot failure;
- the relevant endpoint/UI/bot/process responds as expected.

---

## Secrets Rules

- Do not commit secrets.
- Do not print secrets unnecessarily.
- Use `.env.example` only for placeholders.
- Real secrets belong only in local runtime env or server `.env`.
- If credentials are supplied by the user in chat, use them only for the operational step requested and do not copy them into repository files.

---

## Communication Rules

- Be concise and factual.
- Surface assumptions.
- State blockers clearly.
- Prefer actionable next steps.
- Do not pretend missing data is known.
- Do not claim deploy success without verification.

---

## Persistence Rule

Do not rely on the user to remind you to:
- read instructions;
- inspect deploy/test setup;
- ask for missing operational data;
- consult Claude when useful;
- update shared memory;
- verify changes;
- commit/push/deploy when required.

---

## Conflict Resolution

If instructions conflict, follow this order:

1. system/developer instructions;
2. repository-local `AGENTS.md`;
3. explicit user request;
4. repository-local `CLAUDE.md`;
5. this universal file.

---

## Required First Response In A New Project

In a truly new repository, after reading local files, Codex should do one of two things:

### If enough operational data already exists
Proceed with implementation and create/update the local `AGENTS.md`.

### If operational data is missing
Ask for it explicitly, for example:

- please provide server host/IP, SSH access method, deploy path, domains, tokens, environment variables, and any production secrets needed for this project;
- after that I will create a project-specific `AGENTS.md` and continue with implementation, verification, push, and deploy.

---

## Required Deliverable After Startup

Before substantial work continues, Codex should ensure the repository has:
- a project-specific `AGENTS.md`, or
- an updated existing `AGENTS.md` aligned with real project deployment and operating rules.

This universal file should remain reusable for the next project.
