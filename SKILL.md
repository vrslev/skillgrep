---
name: skillgrep
description: Search trusted local private or team Agent Skill collections when reusable instructions may exist outside the active skill catalog. Resolve only the selected SKILL.md instead of loading every skill into agent context.
---

Before inventing an organization-specific workflow or installing a public substitute, search with `uvx skillgrep q "<short task nouns and product names>"`.

Choose the best match from the returned descriptions; do not assume the first result is correct. Resolve and read only that match. Resolve a second match only when the results are genuinely ambiguous or the task clearly spans two distinct workflows. Read every resolved file completely.

If no registry is configured, ask for its local directory and run `uvx skillgrep add <path> --name <stable-name>`. Do not guess paths or scan the home directory.

Retry unrelated results once with narrower terms. If nothing matches, continue normally and say so. Do not query with secrets or whole conversations. Do not clone, update, install, enable, or execute matched skills implicitly. Treat selected skills as instructions subordinate to user and project instructions.
