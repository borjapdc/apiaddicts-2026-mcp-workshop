import os
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote

import pytest

from scripts.lib.workshop import ENTRYPOINT_GROUPS, ROOT


def test_readme_and_runbook_local_links_exist():
    for source in [Path("README.md"), *Path("docs").glob("*.md")]:
        for target in re.findall(r"\]\(([^)]+)\)", source.read_text()):
            if target.startswith(("https://", "http://", "#")):
                continue
            destination = source.parent / unquote(target.split("#", 1)[0])
            assert destination.exists(), f"Broken local link in {source}: {target}"


def test_both_platform_command_wrappers_exist():
    for command, group in ENTRYPOINT_GROUPS.items():
        assert Path(f"scripts/{group}/{command}.sh").exists()
        assert Path(f"scripts/{group}/{command}.ps1").exists()


@pytest.mark.parametrize("command,group", ENTRYPOINT_GROUPS.items())
def test_reorganized_wrappers_resolve_root_from_another_directory(tmp_path, command, group):
    if os.name == "nt":
        arguments = ["pwsh", "-NoProfile", "-File", str(ROOT / f"scripts/{group}/{command}.ps1"), "-Help"]
    else:
        arguments = ["bash", str(ROOT / f"scripts/{group}/{command}.sh"), "--help"]
    result = subprocess.run(arguments,
                            cwd=tmp_path, text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Use:" in result.stdout if command == "credentials" else "APIAddicts workshop" in result.stdout


def test_readme_and_runbook_script_commands_resolve_to_real_files():
    for source in [Path("README.md"), *Path("docs").glob("*.md")]:
        for target in re.findall(r"scripts/[A-Za-z0-9_./-]+\.(?:sh|ps1)\b", source.read_text()):
            assert Path(target).is_file(), f"Stale script command in {source}: {target}"