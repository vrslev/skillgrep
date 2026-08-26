from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import stat
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence, TextIO

from . import __version__

CONFIG_ENV = "SKILLGREP_CONFIG"
CONFIG_VERSION = 1
SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".tox",
    ".venv",
    "__pycache__",
    "node_modules",
    "venv",
}
MAX_FRONTMATTER_BYTES = 64 * 1024
KEY = re.compile(r"^([A-Za-z0-9_-]+):(?:\s*(.*))?$")
REGISTRY_NAME = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
SKILL_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
WORDS = re.compile(r"[0-9A-Za-zА-Яа-яЁё_+#]+")


class SkillgrepError(Exception):
    """A user-facing error."""


@dataclass(frozen=True)
class Skill:
    identifier: str
    name: str
    description: str
    registry: str
    path: Path
    relative_path: Path


def default_config_path() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base.expanduser() / "skillgrep" / "config.json"


def resolve_config_path(value: str | None) -> Path:
    raw = value or os.environ.get(CONFIG_ENV)
    return Path(raw).expanduser().resolve() if raw else default_config_path().resolve()


def _compact_home(path: Path) -> str:
    home = Path.home().resolve()
    try:
        return str(Path("~") / path.resolve().relative_to(home))
    except ValueError:
        return str(path.resolve())


def _resolved_root(value: str) -> Path:
    return Path(os.path.expandvars(value)).expanduser().resolve()


def _validate_registry_name(name: str) -> str:
    if not REGISTRY_NAME.fullmatch(name):
        raise SkillgrepError(
            f"invalid registry name {name!r}; use lowercase letters, numbers, '.', '_', or '-'"
        )
    return name


def _derived_registry_name(path: Path) -> str:
    name = re.sub(r"[^a-z0-9._-]+", "-", path.name.lower()).strip("-._")
    if not name:
        raise SkillgrepError("could not derive a registry name; pass --name")
    return _validate_registry_name(name)


def _warn_config_permissions(path: Path, stderr: TextIO) -> None:
    if os.name == "nt" or not path.exists():
        return
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        print(
            f"warning: {path} is readable by group or others; run chmod 600 {path}",
            file=stderr,
        )


def read_config(path: Path, stderr: TextIO | None = None) -> dict[str, str]:
    stderr = stderr or sys.stderr
    if not path.exists():
        return {}
    _warn_config_permissions(path, stderr)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SkillgrepError(f"cannot read config: {exc}") from exc
    if not isinstance(data, dict) or data.get("version") != CONFIG_VERSION:
        raise SkillgrepError(f"config must be an object with version {CONFIG_VERSION}")
    registries = data.get("registries")
    if not isinstance(registries, dict):
        raise SkillgrepError("config 'registries' must be an object mapping names to paths")
    result: dict[str, str] = {}
    for name, root in registries.items():
        if not isinstance(name, str) or not isinstance(root, str):
            raise SkillgrepError("registry names and paths must be strings")
        result[_validate_registry_name(name)] = root
    return result


def write_config(path: Path, registries: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": CONFIG_VERSION,
        "registries": dict(sorted(registries.items())),
    }
    fd, temporary = tempfile.mkstemp(prefix=".config-", suffix=".json", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        if os.name != "nt":
            os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temporary_path, path)
        if os.name != "nt":
            path.chmod(0o600)
    finally:
        temporary_path.unlink(missing_ok=True)


def _skill_files(root: Path) -> list[Path]:
    root = root.resolve()
    if not root.is_dir():
        raise SkillgrepError(f"registry does not exist or is not a directory: {root}")
    root_skill = root / "SKILL.md"
    if root_skill.is_file():
        resolved = root_skill.resolve()
        try:
            resolved.relative_to(root)
        except ValueError:
            return []
        return [resolved]

    found: list[Path] = []
    for current, directories, files in os.walk(root, followlinks=False):
        directories[:] = [
            name for name in directories if name not in SKIP_DIRS and not name.startswith(".")
        ]
        if "SKILL.md" not in files:
            continue
        skill_file = Path(current) / "SKILL.md"
        resolved = skill_file.resolve()
        try:
            resolved.relative_to(root)
        except ValueError:
            continue
        found.append(resolved)
        directories[:] = []
    return sorted(set(found))


def _frontmatter(path: Path) -> dict[str, str]:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as stream:
            text = stream.read(MAX_FRONTMATTER_BYTES + 1)
    except OSError as exc:
        raise SkillgrepError(f"cannot read {path.name}: {exc}") from exc

    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    try:
        end = next(index for index, line in enumerate(lines[1:], 1) if line.strip() == "---")
    except StopIteration:
        return {}

    header = lines[1:end]
    parsed: dict[str, str] = {}
    index = 0
    while index < len(header):
        match = KEY.match(header[index])
        if not match:
            index += 1
            continue
        key = match.group(1)
        value = (match.group(2) or "").strip()
        if value in {">", "|-", "|", ">-", ">+", "|+"}:
            block: list[str] = []
            index += 1
            while index < len(header) and (not header[index] or header[index][0].isspace()):
                block.append(header[index].strip())
                index += 1
            separator = "\n" if value.startswith("|") else " "
            parsed[key] = separator.join(line for line in block if line).strip()
            continue
        parsed[key] = value.strip("'\"")
        index += 1
    return parsed


def scan_registry(name: str, raw_root: str) -> tuple[list[Skill], list[str]]:
    root = _resolved_root(raw_root)
    skills: list[Skill] = []
    warnings: list[str] = []
    seen: dict[str, Path] = {}
    for path in _skill_files(root):
        relative = path.relative_to(root)
        metadata = _frontmatter(path)
        skill_name = metadata.get("name", "").strip()
        description = metadata.get("description", "").strip()
        if not skill_name or not description:
            warnings.append(f"{name}:{relative}: missing name or description; skipped")
            continue
        if not SKILL_NAME.fullmatch(skill_name):
            warnings.append(f"{name}:{relative}: invalid Agent Skill name {skill_name!r}; skipped")
            continue
        identifier = f"{name}:{skill_name}"
        if identifier in seen:
            raise SkillgrepError(
                f"duplicate skill id {identifier!r}: {seen[identifier]} and {relative}"
            )
        seen[identifier] = relative
        skills.append(
            Skill(
                identifier=identifier,
                name=skill_name,
                description=description,
                registry=name,
                path=path,
                relative_path=relative,
            )
        )
    return sorted(skills, key=lambda skill: skill.identifier), warnings


def load_skills(
    registries: dict[str, str], stderr: TextIO | None = None
) -> tuple[list[Skill], dict[str, int]]:
    stderr = stderr or sys.stderr
    skills: list[Skill] = []
    counts: dict[str, int] = {}
    for name, root in sorted(registries.items()):
        if not _resolved_root(root).is_dir():
            print(
                f"warning: registry {name!r} is unavailable; use 'skillgrep ls --paths' to inspect it",
                file=stderr,
            )
            counts[name] = 0
            continue
        registry_skills, warnings = scan_registry(name, root)
        for warning in warnings:
            print(f"warning: {warning}", file=stderr)
        skills.extend(registry_skills)
        counts[name] = len(registry_skills)
    return skills, counts


def _tokens(value: str) -> list[str]:
    return [token.lower() for token in WORDS.findall(value)]


def relevance(skill: Skill, query: str) -> int:
    query_tokens = list(dict.fromkeys(_tokens(query)))
    if not query_tokens:
        return 0
    query_phrase = " ".join(query_tokens)
    name_tokens = _tokens(skill.name)
    description_tokens = _tokens(skill.description)
    registry_tokens = _tokens(skill.registry)
    name_phrase = " ".join(name_tokens)
    description_phrase = " ".join(description_tokens)

    score = 0
    if query_phrase == name_phrase:
        score += 1000
    elif query_phrase in name_phrase:
        score += 300
    if query_phrase in description_phrase:
        score += 120

    for token in query_tokens:
        if token in name_tokens:
            score += 80
        elif len(token) >= 3 and any(token in part for part in name_tokens):
            score += 30
        if token in description_tokens:
            score += 20
        elif len(token) >= 4 and token in description_phrase:
            score += 5
        if token in registry_tokens:
            score += 5
    return score


def search(skills: list[Skill], query: str) -> list[tuple[int, Skill]]:
    matches = [(relevance(skill, query), skill) for skill in skills]
    return sorted(
        ((score, skill) for score, skill in matches if score > 0),
        key=lambda item: (-item[0], item[1].identifier),
    )


def _color(stream: TextIO) -> bool:
    return bool(getattr(stream, "isatty", lambda: False)()) and "NO_COLOR" not in os.environ


def _styled(value: str, code: str, stream: TextIO) -> str:
    return f"\033[{code}m{value}\033[0m" if _color(stream) else value


def _result_line(skill: Skill, stream: TextIO) -> str:
    width = max(60, min(120, shutil.get_terminal_size((120, 20)).columns))
    description = " ".join(skill.description.split())
    available = max(1, width - len(skill.identifier) - 2)
    if len(description) > available:
        description = description[: max(1, available - 1)].rstrip() + "…"
    identifier = _styled(skill.identifier, "36", stream)
    return f"{identifier}  {description}"


def _resolve_skill(skills: list[Skill], requested: str) -> Skill:
    exact = [skill for skill in skills if skill.identifier == requested]
    if exact:
        return exact[0]
    by_name = [skill for skill in skills if skill.name == requested]
    if len(by_name) == 1:
        return by_name[0]
    if len(by_name) > 1:
        choices = ", ".join(skill.identifier for skill in by_name)
        raise SkillgrepError(f"ambiguous skill name {requested!r}; use one of: {choices}")
    raise SkillgrepError(f"skill not found: {requested}")


def command_add(args: argparse.Namespace) -> int:
    config = resolve_config_path(args.config)
    registries = read_config(config)
    root = Path(args.path).expanduser().resolve()
    name = _validate_registry_name(args.name) if args.name else _derived_registry_name(root)
    for existing_name, existing_root in registries.items():
        if _resolved_root(existing_root) == root:
            print(f"Already registered as {existing_name}.")
            return 0
    if name in registries:
        raise SkillgrepError(f"registry {name!r} already exists; choose another --name")
    skills, warnings = scan_registry(name, str(root))
    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)
    if not skills:
        raise SkillgrepError(f"no valid SKILL.md files found under {root}")
    registries[name] = _compact_home(root)
    write_config(config, registries)
    print(f"added  {name}  {len(skills)}")
    return 0


def command_remove(args: argparse.Namespace) -> int:
    config = resolve_config_path(args.config)
    registries = read_config(config)
    if args.name not in registries:
        raise SkillgrepError(f"registry not found: {args.name}")
    del registries[args.name]
    write_config(config, registries)
    print(f"Removed {args.name}.")
    return 0


def command_list(args: argparse.Namespace) -> int:
    config = resolve_config_path(args.config)
    registries = read_config(config)
    if not registries:
        print("No registries configured. Use 'skillgrep add PATH'.")
        return 0
    _, counts = load_skills(registries)
    for name, root in sorted(registries.items()):
        suffix = f"  {_resolved_root(root)}" if args.paths else ""
        print(f"{name}  {counts[name]}{suffix}")
    return 0


def command_search(args: argparse.Namespace) -> int:
    config = resolve_config_path(args.config)
    registries = read_config(config)
    if not registries:
        raise SkillgrepError("no registries configured; use 'skillgrep add PATH'")
    skills, _ = load_skills(registries)
    query = " ".join(args.query).strip()
    matches = search(skills, query)
    shown = matches[: args.top]
    if not matches:
        print("No matches.")
        return 0
    for _, skill in shown:
        print(_result_line(skill, sys.stdout))
    return 0


def command_path(args: argparse.Namespace) -> int:
    config = resolve_config_path(args.config)
    registries = read_config(config)
    if not registries:
        raise SkillgrepError("no registries configured; use 'skillgrep add PATH'")
    skills, _ = load_skills(registries)
    selected = [_resolve_skill(skills, requested) for requested in args.skills]
    for skill in selected:
        print(skill.path)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="skillgrep",
        description="Search local Agent Skill collections without loading them all.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--config",
        metavar="PATH",
        help=f"config file (default: $XDG_CONFIG_HOME/skillgrep/config.json; env: {CONFIG_ENV})",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    add = commands.add_parser("add", help="register a local skill collection")
    add.add_argument("path", help="repository or directory containing SKILL.md files")
    add.add_argument("--name", help="stable registry name (default: directory name)")
    add.set_defaults(handler=command_add)

    remove = commands.add_parser("rm", help="remove a registry from the config")
    remove.add_argument("name", help="registry name")
    remove.set_defaults(handler=command_remove)

    listing = commands.add_parser("ls", help="list registries and skill counts")
    listing.add_argument("--paths", action="store_true", help="also reveal registry paths")
    listing.set_defaults(handler=command_list)

    searching = commands.add_parser("q", help="query names and descriptions")
    searching.add_argument("query", nargs="+", help="search terms")
    searching.add_argument("--top", type=int, default=8, help="maximum results (default: 8)")
    searching.set_defaults(handler=command_search)

    path = commands.add_parser("path", help="print selected SKILL.md paths")
    path.add_argument(
        "skills",
        nargs="+",
        metavar="SKILL",
        help="registry:name, or an unambiguous skill name",
    )
    path.set_defaults(handler=command_path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "top", 1) < 1:
        parser.error("--top must be at least 1")
    try:
        return int(args.handler(args))
    except SkillgrepError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
