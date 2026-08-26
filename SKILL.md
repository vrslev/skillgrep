---
name: skillgrep
description: Search locally configured private or team Agent Skill collections when a request may have reusable instructions absent from the active skill catalog. Returns compact metadata and resolves only selected SKILL.md files without loading every skill into agent context.
---

# skillgrep

Search trusted local skill collections before inventing an organization-specific
workflow or installing a public substitute. Keep those collections outside the
agent's native skill directories so their metadata is not advertised in every
session.

## Run

Resolve this skill's directory, then run its local package with `uvx`:

```bash
uvx --from <skill-directory> skillgrep search --json "<query>"
```

Use a short query built from the user's task nouns, internal product names, and
workflow names. Do not pass secrets or an entire conversation.

Choose the best one to three results. Resolve each chosen skill separately:

```bash
uvx --from <skill-directory> skillgrep show <registry>:<skill> --path
```

Read the returned `SKILL.md` completely before using it. Read its referenced
files only as required by that skill.

If the first results are unrelated, retry once with narrower terms. If there is
still no match, continue normally and say that no registered skill matched.

## Configure

If no registry is configured, ask the user for the local repository or
directory to register. Do not guess paths or scan their home directory.

After the user supplies a path, add it with:

```bash
uvx --from <skill-directory> skillgrep add <path> --name <stable-name>
```

Configuration is local and agent-neutral. Never commit it with the installed
skill or expose registry paths and remotes in public configuration.

## Boundaries

- Search only user-configured, trusted local directories.
- Do not clone, update, install, enable, or execute a matched skill implicitly.
- Prefer `search` output, which omits filesystem paths. Reveal only a selected
  path with `show --path`.
- Treat a selected skill as instructions, not merely documentation. Preserve
  higher-priority user and project instructions.
