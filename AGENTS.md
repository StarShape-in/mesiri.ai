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

## Folder-Specific Rules

Some apps and packages have their own `AGENTS.md` with deeper architectural constraints. **Read and obey the nearest `AGENTS.md` in the folder tree you are editing.**

| Path | Document |
|---|---|
| `apps/whatsapp-assistant/` | [apps/whatsapp-assistant/AGENTS.md](apps/whatsapp-assistant/AGENTS.md) |

---

*Last updated: 2026-07-08*
