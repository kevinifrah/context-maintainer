"""Wrapper around the Repomix CLI for staged repository evidence gathering.

Two passes, deliberately: a cheap structure-only pass first, then a fuller pass
only when the structure pass is not enough. Repomix output is raw evidence for
the skill to read — it is never the canonical context, so everything lands in
the ignored cache.

Security: Repomix runs Secretlint by default and we never disable it. We also
pass an explicit ignore list for common secret-bearing paths so they are not
read in the first place.
"""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from . import contract

EXECUTABLE = "repomix"

#: Repomix requires a recent Node runtime; surfaced verbatim when it is missing.
INSTALL_HINT = (
    "Repomix is not installed. It needs Node >= 22, then either:\n"
    "  npm install -g repomix        (persistent)\n"
    "  npx repomix@latest           (one-off, downloads on first use)\n"
    "Context Maintainer never installs it for you."
)

#: Belt-and-braces on top of Repomix's own default ignores and Secretlint.
#: Inventorying that a secret mechanism exists is fine; reading values is not.
SECRET_IGNORE_PATTERNS = (
    ".env",
    ".env.*",
    "!.env.example",
    "!.env.sample",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "*.keystore",
    "id_rsa*",
    "id_ed25519*",
    "*.crt",
    "**/secrets/**",
    "**/credentials/**",
    ".aws/**",
    ".ssh/**",
)

DEFAULT_LOG_COUNT = 50
DEFAULT_STYLE = "xml"
DEFAULT_TIMEOUT_SECONDS = 600

MODE_STRUCTURE = "structure"
MODE_FULL = "full"


class RepomixNotAvailableError(Exception):
    """Repomix is not installed or not on PATH."""


@dataclass
class RepomixResult:
    """Outcome of one Repomix invocation.

    `degraded_mode` is the important field for callers: when it is True no
    structural evidence was gathered, and no audit may claim to be complete.
    """

    available: bool
    mode: str
    degraded_mode: bool = False
    output_path: Optional[str] = None
    version: Optional[str] = None
    command: List[str] = field(default_factory=list)
    returncode: Optional[int] = None
    stderr: str = ""
    note: str = ""

    @property
    def succeeded(self) -> bool:
        return self.available and self.returncode == 0 and not self.degraded_mode

    def to_dict(self) -> dict:
        return {
            "available": self.available,
            "mode": self.mode,
            "degraded_mode": self.degraded_mode,
            "output_path": self.output_path,
            "version": self.version,
            "command": self.command,
            "returncode": self.returncode,
            "stderr": self.stderr[:2000],
            "note": self.note,
            "succeeded": self.succeeded,
        }


def is_repomix_available() -> bool:
    """True only if a real `repomix` is on PATH — never triggers an npx download."""
    return shutil.which(EXECUTABLE) is not None


def get_repomix_version() -> Optional[str]:
    if not is_repomix_available():
        return None
    try:
        result = subprocess.run(
            [EXECUTABLE, "--version"], capture_output=True, text=True, timeout=60
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return (result.stdout or "").strip() or None


def cache_dir(root: Path) -> Path:
    path = Path(root) / contract.CACHE_DIR / "repomix"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _output_path(root: Path, mode: str, style: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffix = {"xml": "xml", "markdown": "md", "json": "json", "plain": "txt"}.get(
        style, "txt"
    )
    return cache_dir(root) / f"{mode}-{stamp}.{suffix}"


def build_structure_command(output: Path, style: str = DEFAULT_STYLE) -> List[str]:
    """Metadata/structure only — no file contents, so it stays cheap."""
    return [
        EXECUTABLE,
        "--no-files",
        "--style",
        style,
        "--output",
        str(output),
        "--ignore",
        ",".join(SECRET_IGNORE_PATTERNS),
    ]


def build_full_command(
    output: Path,
    style: str = DEFAULT_STYLE,
    include_logs: bool = True,
    log_count: int = DEFAULT_LOG_COUNT,
    include_diffs: bool = True,
    compress: bool = True,
) -> List[str]:
    command = [EXECUTABLE, "--style", style, "--output", str(output)]
    if compress:
        # Tree-sitter signature extraction: keeps structure, drops bodies.
        command.append("--compress")
    if include_logs:
        command += ["--include-logs", "--include-logs-count", str(log_count)]
    if include_diffs:
        command.append("--include-diffs")
    command += ["--ignore", ",".join(SECRET_IGNORE_PATTERNS)]
    # NOTE: --no-security-check is deliberately never passed; Secretlint stays on.
    return command


def _run(
    root: Path, command: List[str], mode: str, timeout: int
) -> RepomixResult:
    version = get_repomix_version()
    try:
        completed = subprocess.run(
            command,
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return RepomixResult(
            available=True,
            mode=mode,
            degraded_mode=True,
            version=version,
            command=command,
            note=f"Repomix timed out after {timeout}s; no evidence gathered.",
        )
    except OSError as exc:
        return RepomixResult(
            available=True,
            mode=mode,
            degraded_mode=True,
            version=version,
            command=command,
            note=f"Repomix could not be executed: {exc}",
        )

    output_arg = command[command.index("--output") + 1]
    produced = Path(output_arg).exists()
    failed = completed.returncode != 0 or not produced

    return RepomixResult(
        available=True,
        mode=mode,
        degraded_mode=failed,
        output_path=output_arg if produced else None,
        version=version,
        command=command,
        returncode=completed.returncode,
        stderr=(completed.stderr or "").strip(),
        note=(
            ""
            if not failed
            else "Repomix exited without producing output; treat structural "
            "evidence as incomplete."
        ),
    )


def unavailable_result(mode: str) -> RepomixResult:
    return RepomixResult(
        available=False,
        mode=mode,
        degraded_mode=True,
        note=INSTALL_HINT,
    )


def run_structure_pass(
    root: Path,
    style: str = DEFAULT_STYLE,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> RepomixResult:
    if not is_repomix_available():
        return unavailable_result(MODE_STRUCTURE)
    output = _output_path(root, MODE_STRUCTURE, style)
    return _run(root, build_structure_command(output, style), MODE_STRUCTURE, timeout)


def run_full_pass(
    root: Path,
    style: str = DEFAULT_STYLE,
    include_logs: bool = True,
    log_count: int = DEFAULT_LOG_COUNT,
    include_diffs: bool = True,
    compress: bool = True,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> RepomixResult:
    if not is_repomix_available():
        return unavailable_result(MODE_FULL)
    output = _output_path(root, MODE_FULL, style)
    command = build_full_command(
        output,
        style=style,
        include_logs=include_logs,
        log_count=log_count,
        include_diffs=include_diffs,
        compress=compress,
    )
    return _run(root, command, MODE_FULL, timeout)
