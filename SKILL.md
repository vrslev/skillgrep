---
name: skillgrep
description: Search trusted local private or team Agent Skill collections when reusable instructions may exist outside the active skill catalog. Resolve only the selected SKILL.md instead of loading every skill into agent context.
---

Before inventing an organization-specific workflow or installing a public substitute, search with `uvx skillgrep q "<short task nouns and product names>"`.

Resolve the best one to three matches with `uvx skillgrep path <registry>:<skill> [...]`, then read each returned file completely.

If no registry is configured, ask for its local directory and run `uvx skillgrep add <path> --name <stable-name>`. Do not guess paths or scan the home directory.

Retry unrelated results once with narrower terms. If nothing matches, continue normally and say so. Do not query with secrets or whole conversations. Do not clone, update, install, enable, or execute matched skills implicitly. Treat selected skills as instructions subordinate to user and project instructions.
