# Mesiri.AI — Agent Guidelines

> **You are an AI coding agent working in this monorepo.**  
> Follow these rules on every task unless a folder-specific `AGENTS.md` overrides them.

---

## The 3 R's of Coding

Apply these in order before writing new code:

### 1. Reduce

- Keep every change as small as possible. Fix the problem — don't expand scope.
- Remove dead code, unused imports, and redundant abstractions when you touch a file.
- Prefer one clear solution over multiple fallbacks for unlikely edge cases.
- Do not add features, refactors, or docs the user did not ask for.

### 2. Reuse

- Read surrounding code before writing. Match naming, types, patterns, and import style.
- Extend existing functions, components, and modules instead of duplicating logic.
- Search the codebase for prior art before introducing a new helper, utility, or pattern.
- When no project convention exists, follow language and framework best practices.

### 3. Refactor

- Improve structure only when it directly supports the current task.
- Refactor incrementally inside the files you are already changing — not as a separate sweep.
- Extract a module or component when a file grows too large or responsibilities diverge.
- Preserve behavior. Refactoring is restructuring, not rewriting from scratch.

---

## File Size Limit

**Do not create or grow source files beyond ~1,000 lines** unless there is a clear, documented reason.

### When a file approaches 1,000 lines

1. Stop adding to it.
2. Split by single responsibility — one module, component, or concern per file.
3. Keep public APIs stable; move internals into focused submodules.

### Acceptable exceptions (must be intentional)

- Generated code (lockfiles, migrations, OpenAPI specs)
- Large static data or fixture files
- Folder-specific constitution docs (e.g. `apps/whatsapp-assistant/AGENTS.md`)
- A monolithic config or registry that is genuinely one cohesive unit and splitting would hurt clarity

When an exception applies, add a brief comment at the top of the file explaining why it stays large.

---

## Explain Before Executing

**Never silently implement a non-trivial change.** Before writing code for anything beyond a one-line fix:

1. Explain what you're about to change and why, in two registers:
   - **Plain language first** — a short analogy or non-jargon description of what the change does, for a non-coder reading along.
   - **Technical detail after** — the actual files, functions, and contracts involved.
2. Use a diagram (flowchart, sequence trace) whenever the change touches more than one module or is easier to see than to describe — don't default to a wall of text for architecture-level changes.
3. Wait for at least implicit go-ahead before writing code. "Sounds good", "yes", or silence-after-a-clear-plan counts; moving straight from explanation to implementation without pausing does not.

This applies to real feature work and bug fixes — not to routine verification (running tests, checking git status) or to work the user has already explicitly and specifically authorized in the same message.

---

## Git Workflow — This Is a Shared, Actively-Developed Repo

Other contributors push to `main` frequently and mid-session. Follow this sequence every time, no exceptions:

1. **Before starting work**: `git fetch origin main` and check divergence (`git rev-list --left-right --count origin/main...HEAD`). Pull if behind.
2. **Before committing**: run the full test suite (see below) and lint — not a subset.
3. **Before pushing**: `git fetch`/pull again. New commits routinely land between when you started and when you're ready to push. If your pull touches a file you've also edited, read the merge result before pushing — don't assume it merged correctly.
4. **Never lose either side's changes.** A conflict or overlap gets resolved by hand, preserving both contributions — never resolved by blindly picking one side.
5. If a partner's push has lint/CI errors unrelated to your own changes, that's on them to fix — don't silently fix someone else's broken commit unless asked to.

### Test suite — run the whole thing, not just `tests/unit`

`apps/whatsapp-assistant` and `backend` each have multiple test directories (`unit/`, `contract/`, `scenario/`, `integration/`) that CI runs together. Running only `tests/unit` has previously let a real regression through that `tests/contract` caught. Before declaring "tests pass" or pushing:

```bash
# from apps/whatsapp-assistant
pytest tests/ --ignore=tests/integration -q

# from backend
pytest tests/ --ignore=tests/integration -q
```

`tests/integration` needs a live database that isn't reachable from every dev environment — excluded here, not skipped silently elsewhere. Also run the `shared/contracts` and `platform/ai` suites when you've touched either package. Lint with `ruff check` across whichever `src/` trees you touched before committing.

---

## Folder-Specific Rules

Some apps and packages have their own `AGENTS.md` with deeper architectural constraints. **Read and obey the nearest `AGENTS.md` in the folder tree you are editing.**

| Path | Document |
|---|---|
| `apps/whatsapp-assistant/` | [apps/whatsapp-assistant/AGENTS.md](apps/whatsapp-assistant/AGENTS.md) |

---

*Last updated: 2026-07-12*
