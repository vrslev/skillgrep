from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

from skillgrep.cli import default_config_path, main


def make_skill(root: Path, relative: str, name: str, description: str) -> Path:
    directory = root / relative
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "SKILL.md"
    path.write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\n# {name}\n",
        encoding="utf-8",
    )
    return path


def invoke(config: Path, *arguments: str) -> int:
    return main(["--config", str(config), *arguments])


def test_add_creates_small_private_config(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    registry = tmp_path / "team-skills"
    make_skill(registry, "delivery/release", "release-check", "Check a release safely.")
    config = tmp_path / "config" / "config.json"

    assert invoke(config, "add", str(registry), "--name", "team") == 0

    assert json.loads(config.read_text()) == {
        "version": 1,
        "registries": {"team": str(registry)},
    }
    if os.name != "nt":
        assert stat.S_IMODE(config.stat().st_mode) == 0o600
    assert capsys.readouterr().out == "Added team (1 skill).\n"


def test_add_is_idempotent_by_path(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    registry = tmp_path / "skills"
    make_skill(registry, "one", "one", "First skill.")
    config = tmp_path / "config.json"

    assert invoke(config, "add", str(registry), "--name", "first") == 0
    assert invoke(config, "add", str(registry), "--name", "second") == 0

    assert "Already registered as first." in capsys.readouterr().out
    assert json.loads(config.read_text())["registries"] == {"first": str(registry)}


def test_add_rejects_bad_inputs(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    config = tmp_path / "config.json"

    assert invoke(config, "add", str(empty), "--name", "Bad Name") == 2
    assert "invalid registry name" in capsys.readouterr().err
    assert invoke(config, "add", str(empty), "--name", "empty") == 2
    assert "no valid SKILL.md files" in capsys.readouterr().err


def test_add_rejects_missing_root_and_duplicate_name(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    make_skill(first, "one", "one", "First skill.")
    make_skill(second, "two", "two", "Second skill.")
    config = tmp_path / "config.json"

    assert invoke(config, "add", str(tmp_path / "missing"), "--name", "missing") == 2
    assert "does not exist" in capsys.readouterr().err
    assert invoke(config, "add", str(first), "--name", "same") == 0
    capsys.readouterr()
    assert invoke(config, "add", str(second), "--name", "same") == 2
    assert "already exists" in capsys.readouterr().err


def test_search_ranks_exact_name_and_hides_paths(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registry = tmp_path / "private-location"
    make_skill(registry, "jira", "jira-release", "Work with Jira releases.")
    make_skill(registry, "notes", "release-notes", "Draft notes for releases.")
    make_skill(registry, "ru", "incident-ru", "Разбирает инциденты и ошибки сервисов.")
    config = tmp_path / "config.json"
    assert invoke(config, "add", str(registry), "--name", "team") == 0
    capsys.readouterr()

    assert invoke(config, "search", "jira-release") == 0
    output = capsys.readouterr().out
    assert output.index("team:jira-release") < output.index("team:release-notes")
    assert str(registry) not in output

    assert invoke(config, "search", "инциденты ошибки") == 0
    assert "team:incident-ru" in capsys.readouterr().out


def test_search_json_is_compact_and_path_free(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registry = tmp_path / "secret-root"
    make_skill(registry, "one", "jira", "Search Jira issues.")
    config = tmp_path / "config.json"
    assert invoke(config, "add", str(registry), "--name", "team") == 0
    capsys.readouterr()

    assert invoke(config, "search", "jira", "--json") == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["results"][0]["id"] == "team:jira"
    assert "path" not in payload["results"][0]
    assert str(registry) not in json.dumps(payload)


def test_search_handles_no_matches_and_limits_results(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registry = tmp_path / "skills"
    make_skill(registry, "one", "one", "Release one.")
    make_skill(registry, "two", "two", "Release two.")
    config = tmp_path / "config.json"
    assert invoke(config, "add", str(registry)) == 0
    capsys.readouterr()

    assert invoke(config, "search", "missing") == 0
    assert capsys.readouterr().out == "No matching skills.\n"
    assert invoke(config, "search", "release", "--top", "1") == 0
    assert "Showing 1 of 2 matches" in capsys.readouterr().out


def test_show_resolves_selected_path_and_rejects_ambiguous_name(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first_path = make_skill(first, "shared", "shared", "First shared skill.")
    make_skill(second, "shared", "shared", "Second shared skill.")
    config = tmp_path / "config.json"
    assert invoke(config, "add", str(first), "--name", "one") == 0
    assert invoke(config, "add", str(second), "--name", "two") == 0
    capsys.readouterr()

    assert invoke(config, "show", "one:shared", "--path") == 0
    assert capsys.readouterr().out.strip() == str(first_path)
    assert invoke(config, "show", "shared") == 2
    assert "ambiguous skill name" in capsys.readouterr().err
    assert invoke(config, "show", "missing") == 2
    assert "skill not found" in capsys.readouterr().err


def test_show_json_contains_only_selected_path(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registry = tmp_path / "skills"
    path = make_skill(registry, "one", "one", "The one skill.")
    config = tmp_path / "config.json"
    assert invoke(config, "add", str(registry), "--name", "r") == 0
    capsys.readouterr()

    assert invoke(config, "show", "one", "--json") == 0
    assert json.loads(capsys.readouterr().out)["path"] == str(path)

    assert invoke(config, "show", "r:one") == 0
    output = capsys.readouterr().out
    assert "r:one" in output
    assert "The one skill." in output
    assert str(path) in output


def test_list_omits_paths_unless_requested_and_remove_is_reversible(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registry = tmp_path / "private-root"
    make_skill(registry, "one", "one", "One skill.")
    config = tmp_path / "config.json"
    assert invoke(config, "add", str(registry), "--name", "team") == 0
    capsys.readouterr()

    assert invoke(config, "list") == 0
    assert str(registry) not in capsys.readouterr().out
    assert invoke(config, "list", "--paths", "--json") == 0
    assert json.loads(capsys.readouterr().out)["registries"][0]["path"] == str(registry)
    assert invoke(config, "list", "--json") == 0
    assert "path" not in json.loads(capsys.readouterr().out)["registries"][0]
    assert invoke(config, "remove", "team") == 0
    assert "Removed team." in capsys.readouterr().out
    assert invoke(config, "list") == 0
    assert "No registries configured" in capsys.readouterr().out
    assert invoke(config, "remove", "team") == 2
    assert "registry not found" in capsys.readouterr().err


def test_folded_description_and_invalid_skill_warning(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registry = tmp_path / "skills"
    valid = registry / "valid"
    valid.mkdir(parents=True)
    (valid / "SKILL.md").write_text(
        "---\nname: folded\ndescription: >\n  Search internal systems\n  without loading everything.\n---\n",
        encoding="utf-8",
    )
    invalid = registry / "invalid"
    invalid.mkdir()
    (invalid / "SKILL.md").write_text("# Missing frontmatter\n", encoding="utf-8")
    config = tmp_path / "config.json"

    assert invoke(config, "add", str(registry), "--name", "team") == 0
    captured = capsys.readouterr()
    assert "missing name or description" in captured.err
    assert invoke(config, "search", "loading everything") == 0
    assert "team:folded" in capsys.readouterr().out


def test_nonstandard_skill_name_is_skipped(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registry = tmp_path / "skills"
    make_skill(registry, "bad", "Bad_Name", "Not an Agent Skills name.")
    config = tmp_path / "config.json"

    assert invoke(config, "add", str(registry), "--name", "team") == 2
    captured = capsys.readouterr()
    assert "invalid Agent Skill name" in captured.err
    assert "no valid SKILL.md files" in captured.err


def test_duplicate_ids_fail_closed(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    registry = tmp_path / "skills"
    make_skill(registry, "one", "duplicate", "One.")
    make_skill(registry, "two", "duplicate", "Two.")
    config = tmp_path / "config.json"

    assert invoke(config, "add", str(registry), "--name", "team") == 2
    assert "duplicate skill id" in capsys.readouterr().err
    assert not config.exists()


def test_config_validation_and_permission_warning(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = tmp_path / "config.json"
    config.write_text('{"version": 2, "registries": {}}\n', encoding="utf-8")
    assert invoke(config, "list") == 2
    assert "version 1" in capsys.readouterr().err

    config.write_text('{"version": 1, "registries": {}}\n', encoding="utf-8")
    if os.name != "nt":
        config.chmod(0o644)
        assert invoke(config, "list") == 0
        assert "chmod 600" in capsys.readouterr().err


@pytest.mark.parametrize(
    "payload,error",
    [
        ('{"version": 1, "registries": []}', "must be an object"),
        ('{"version": 1, "registries": {"team": 3}}', "must be strings"),
        ('{"version": 1, "registries": {"Bad Name": "/tmp"}}', "invalid registry name"),
    ],
)
def test_config_rejects_invalid_registry_shapes(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    payload: str,
    error: str,
) -> None:
    config = tmp_path / "config.json"
    config.write_text(payload, encoding="utf-8")
    assert invoke(config, "list") == 2
    assert error in capsys.readouterr().err


def test_default_config_obeys_xdg(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert default_config_path() == tmp_path / "skillgrep" / "config.json"


def test_symlink_escaping_registry_is_ignored(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registry = tmp_path / "skills"
    registry.mkdir()
    outside = tmp_path / "outside"
    make_skill(outside, ".", "outside", "Must stay outside.")
    link = registry / "linked"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlinks are unavailable")
    config = tmp_path / "config.json"

    assert invoke(config, "add", str(registry), "--name", "team") == 2
    assert "no valid SKILL.md files" in capsys.readouterr().err


def test_root_skill_symlink_escaping_registry_is_ignored(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registry = tmp_path / "skills"
    registry.mkdir()
    outside = make_skill(tmp_path, "outside", "outside", "Must stay outside.")
    try:
        (registry / "SKILL.md").symlink_to(outside)
    except OSError:
        pytest.skip("file symlinks are unavailable")
    config = tmp_path / "config.json"

    assert invoke(config, "add", str(registry), "--name", "team") == 2
    assert "no valid SKILL.md files" in capsys.readouterr().err


def test_missing_registry_and_malformed_config(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = tmp_path / "config.json"
    assert invoke(config, "search", "anything") == 2
    assert "no registries configured" in capsys.readouterr().err

    config.write_text("not json", encoding="utf-8")
    assert invoke(config, "list") == 2
    assert "cannot read config" in capsys.readouterr().err


def test_unavailable_registry_does_not_hide_healthy_registries(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    healthy = tmp_path / "healthy"
    make_skill(healthy, "one", "healthy-skill", "A healthy searchable skill.")
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            {
                "version": 1,
                "registries": {
                    "missing": str(tmp_path / "missing"),
                    "healthy": str(healthy),
                },
            }
        ),
        encoding="utf-8",
    )
    config.chmod(0o600)

    assert invoke(config, "search", "healthy") == 0
    captured = capsys.readouterr()
    assert "healthy:healthy-skill" in captured.out
    assert "registry 'missing' is unavailable" in captured.err
    assert str(tmp_path / "missing") not in captured.err


def test_root_can_be_a_single_skill(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    registry = tmp_path / "single"
    path = make_skill(tmp_path, "single", "single", "One standalone skill.")
    config = tmp_path / "config.json"

    assert invoke(config, "add", str(registry)) == 0
    capsys.readouterr()
    assert invoke(config, "show", "single", "--path") == 0
    assert capsys.readouterr().out.strip() == str(path)
