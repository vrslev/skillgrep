[![Test](https://github.com/vrslev/skillgrep/actions/workflows/test.yml/badge.svg)](https://github.com/vrslev/skillgrep/actions/workflows/test.yml)

# skillgrep

Search local [Agent Skill](https://agentskills.io/) collections without loading them all into every agent session.

Agents normally advertise every enabled skill's name and description, then load the selected `SKILL.md` on demand. `skillgrep` keeps infrequent private or team collections outside that catalog. One routing skill searches their metadata and resolves only the chosen file.

It does not clone, update, install, or execute registered skills.

## Install

```console
$ npx skills add vrslev/skillgrep
```

The skill invokes the dependency-free CLI with `uvx skillgrep`.

## Configure

```console
$ uvx skillgrep add ~/code/team-skills --name team
added  team  2
```

The name becomes the stable namespace in results such as `team:release-workflow`. It defaults to the directory name.

Configuration follows the XDG application convention:

```text
${XDG_CONFIG_HOME:-~/.config}/skillgrep/config.json
```

There is no standard Agent Skills configuration directory. Normal setup uses `add`, `rm`, and `ls`; manual configuration is optional:

```json
{
  "version": 1,
  "registries": {
    "personal": "~/code/personal-skills",
    "team": "~/code/team-skills"
  }
}
```

The file is created with mode `600` on POSIX systems. Set `SKILLGREP_CONFIG` or pass `--config` to use another location.

## Example

```console
$ uvx skillgrep q "release incident"
team:incident-release-check  Verify release state and collect incident evidence before taking action.
personal:release-notes  Draft concise release notes from a local Git history.

$ uvx skillgrep path team:incident-release-check personal:release-notes
/Users/example/code/team-skills/delivery/incident-release-check/SKILL.md
/Users/example/code/personal-skills/writing/release-notes/SKILL.md
```

`q` returns at most eight one-line matches by default; `--top N` changes the limit. It omits paths, remotes, and configuration locations. `path` reveals only the selected files. Ranking is deterministic and uses the query, skill name, and description—no embeddings or model calls.

## Commands

```text
skillgrep add PATH [--name NAME]  Register a local collection
skillgrep rm NAME                 Remove a registry
skillgrep ls [--paths]            List registries and skill counts
skillgrep q QUERY [--top N]       Query names and descriptions
skillgrep path SKILL [SKILL ...]  Print selected SKILL.md paths
```

Registry-qualified identifiers prevent collisions between collections. Duplicate names inside one registry are errors.

## Privacy and trust

- Runtime commands read only explicitly registered local directories and make no network requests. Installation and `uvx` package retrieval require network access.
- Registry paths stay in the local XDG config rather than agent settings or a public dotfiles repository.
- Descriptions are search metadata; do not put secrets in skill frontmatter.
- Registered collections must be trusted because selected files become agent instructions.
- Symlinked skill files resolving outside their registered root are ignored.

## How this differs from native discovery

The comparison reflects documented behavior available on **2026-08-26**.

| System | Initial discovery | Detailed instructions |
| --- | --- | --- |
| [Codex](https://developers.openai.com/codex/skills) | Enabled skill metadata is placed in the model-visible catalog. | The selected `SKILL.md` is read on demand. |
| [Claude Code](https://code.claude.com/docs/en/skills) | Metadata for model-invokable skills is available for routing; skills may also be manual-only. | Skill content loads when invoked. |
| [OpenCode](https://opencode.ai/docs/skills/) | Permitted names and descriptions appear in the native `skill` tool. | The `skill` tool loads selected content. |
| [Gemini CLI](https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/skills.md) | Names and descriptions of enabled skills enter the system prompt. | `activate_skill` loads selected content after consent. |
| `skillgrep` | Only its routing skill is installed. Registered collections remain outside native discovery. | The agent queries locally and resolves one chosen file. |

Native discovery remains preferable for a small, frequently used set. `skillgrep` covers the larger searchable tail. It is agent-mediated discovery, not a patch to an agent's native prompt assembler.
