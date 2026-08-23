import subprocess
import sys
from pathlib import Path

import context_maintainer
from context_maintainer.cli import build_parser


def test_version_flag_prints_version_and_exits_zero():
    result = subprocess.run(
        [sys.executable, "-m", "context_maintainer", "--version"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert context_maintainer.__version__ in result.stdout


def test_help_flag_lists_all_five_subcommands():
    parser = build_parser()
    help_text = parser.format_help()
    for command in ("init", "status", "sync", "doctor", "rebuild"):
        assert command in help_text


def test_package_is_importable():
    assert hasattr(context_maintainer, "__version__")


def test_templates_directory_contains_all_required_template_files():
    templates_dir = Path(context_maintainer.__file__).parent / "templates"
    required = {
        "AGENTS.md.tmpl",
        "CLAUDE.md.tmpl",
        "PROJECT.md.tmpl",
        "ARCHITECTURE.md.tmpl",
        "WORKFLOWS.md.tmpl",
        "STATE.md.tmpl",
        "DECISIONS.md.tmpl",
        "manifest.schema.json",
    }
    present = {p.name for p in templates_dir.iterdir()}
    assert required.issubset(present)
