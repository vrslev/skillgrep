[![Test](https://github.com/vrslev/skillgrep/actions/workflows/test.yml/badge.svg)](https://github.com/vrslev/skillgrep/actions/workflows/test.yml)

# skillgrep

Search local [Agent Skill](https://agentskills.io/) collections without loading
them all into every agent session.

Agents normally discover skills by advertising each enabled skill's name and
description up front, then loading its full `SKILL.md` when selected. That works
well for a small active set. It becomes noisy when a person or team keeps a much
larger private collection.

`skillgrep` exposes one routing skill. It searches metadata in trusted local
repositories, returns compact results without paths, and resolves only the
selected `SKILL.md`. It does not clone, update, install, or execute registered
skills.

## Install

Install the routing skill with any Agent Skills-compatible client:

```console
$ npx skills add vrslev/skillgrep
```

The skill runs its bundled Python package with
[`uvx`](https://docs.astral.sh/uv/guides/tools/). The Python package has no
runtime dependencies.

## Configure

Register a repository or directory containing one or more `SKILL.md` files:

```console
$ uvx --from git+https://github.com/vrslev/skillgrep skillgrep add ~/code/team-skills --name team
Added team (2 skills).
```

The name becomes the stable namespace for results, such as
`team:release-workflow`. `skillgrep` derives it from the directory name when
`--name` is omitted.

Configuration follows the XDG application convention:

```text
${XDG_CONFIG_HOME:-~/.config}/skillgrep/config.json
```

There is no standard Agent Skills configuration directory. The generated file
is deliberately application-specific and is created with mode `600` on POSIX
systems. Its complete shape is:

```json
{
  "version": 1,
  "registries": {
    "personal": "~/code/personal-skills",
    "team": "~/code/team-skills"
  }
}
```

Normal setup does not require editing this file. Use `skillgrep add`,
`skillgrep remove`, and `skillgrep list` instead. Set `SKILLGREP_CONFIG` or pass
`--config` to use another location.

## Example

```console
$ uvx --from git+https://github.com/vrslev/skillgrep skillgrep search "release incident"
Showing 2 of 5 matches

1. team:incident-release-check
   Verify release state and collect incident evidence before taking action.

2. personal:release-notes
   Draft concise release notes from a local Git history.

$ uvx --from git+https://github.com/vrslev/skillgrep skillgrep show team:incident-release-check --path
/Users/example/code/team-skills/delivery/incident-release-check/SKILL.md
```

Search results omit paths, repository remotes, and configuration locations.
`show` reveals the path of one selected skill so the agent can read it on
demand. Results are ranked deterministically from the query, skill name, and
description; no embeddings or model calls are involved.

## Commands

```text
skillgrep add PATH [--name NAME]       Register a local collection
skillgrep remove NAME                  Remove a registry from the config
skillgrep list [--paths] [--json]      List registries and skill counts
skillgrep search QUERY [--top N]       Search names and descriptions
skillgrep show REGISTRY:SKILL --path   Resolve one selected SKILL.md
```

`search --json` remains path-free. `show --json` includes the selected path.
Registry-qualified identifiers prevent skills with the same name in different
collections from overwriting or silently shadowing one another. Duplicate names
inside one registry are reported as errors.

## Privacy and trust

- Runtime search reads only explicitly registered local directories and makes
  no network requests.
- Installation through GitHub or `npx skills` naturally requires network
  access; runtime discovery does not.
- Registry paths stay in the local XDG config rather than agent settings or a
  public dotfiles repository.
- Search results disclose descriptions because the agent needs them for
  routing. Do not put secrets in skill frontmatter.
- Registered collections must be trusted. A selected `SKILL.md` becomes agent
  instructions when it is read.
- Symlinked skill files resolving outside their registered root are ignored.

## How this differs from native discovery

The comparison below reflects documented behavior available on **2026-08-26**.

| System | Initial discovery | Detailed instructions |
| --- | --- | --- |
| [Codex](https://developers.openai.com/codex/skills) | Enabled skill metadata is placed in the model-visible catalog. | The selected `SKILL.md` is read on demand. |
| [Claude Code](https://code.claude.com/docs/en/skills) | Metadata for model-invokable skills is available for routing; skills may also be manual-only. | Skill content loads when invoked. |
| [OpenCode](https://opencode.ai/docs/skills/) | Permitted names and descriptions appear in the native `skill` tool. | The `skill` tool loads selected content. |
| [Gemini CLI](https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/skills.md) | Names and descriptions of enabled skills enter the system prompt. | `activate_skill` loads selected content after consent. |
| `skillgrep` | Only the `skillgrep` routing skill must be installed. Registered collections remain outside native discovery. | The agent searches locally and resolves one chosen file. |

Native controls continue to be preferable for a small, frequently used skill
set. `skillgrep` is for the larger tail that should remain searchable without
being advertised in every session. It is agent-mediated discovery, not a patch
to an agent's native prompt assembler, so explicit native invocation of a hidden
skill is unavailable until the agent resolves it.

## Development

```console
$ uv sync --group dev
$ uv run pytest -q
$ uv build
```

The runtime deliberately uses only the Python standard library.
