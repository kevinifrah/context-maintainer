"""Check what the context documents *claim* against what the repository shows.

`doctor` validates form: files present, sections present, no placeholders. That
is orthogonal to truth — a completely fabricated ARCHITECTURE.md passes every
structural check. This module attacks that gap.

It only checks claims that are mechanically decidable, and it is deliberately
conservative, because a false positive costs more than a missed claim: people
switch off tools that cry wolf. Hence three verdicts rather than two, and an
explicit exemption for historical statements.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

CONFIRMED = "CONFIRMED"
UNVERIFIED = "UNVERIFIED"
CONTRADICTED = "CONTRADICTED"

#: A line describing the past is not a present-tense claim. Without this,
#: "we migrated away from MongoDB" reads as a broken MongoDB claim — and
#: recording migrations is something this tool actively asks for.
_HISTORICAL_MARKERS = (
    "previously",
    "formerly",
    "used to",
    "migrated away",
    "migrated from",
    "no longer",
    "superseded",
    "deprecated",
    "historical",
    "was replaced",
    "replaced by",
    "before the migration",
    "legacy",
    "removed in",
    "dropped in",
)

#: Sections whose prose is a claim about *current* reality worth checking.
_COMMAND_SECTIONS = ("Development", "Testing", "Build", "Deploy")
_TECH_SECTIONS = ("Persistence", "Integrations", "Overview", "Components")


@dataclass
class Claim:
    kind: str  # "command" | "technology"
    value: str
    source: str  # repo-relative file
    section: str
    status: str
    detail: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "value": self.value,
            "source": self.source,
            "section": self.section,
            "status": self.status,
            "detail": self.detail,
        }


# --- runner fingerprints --------------------------------------------------
# Each entry: command token -> (marker predicate description, marker paths,
# dependency substrings). A claim is CONTRADICTED only when no marker exists
# *and* some other recognised ecosystem does — otherwise it is UNVERIFIED.

_RUNNER_MARKERS: Dict[str, Tuple[Sequence[str], Sequence[str]]] = {
    "cargo": (("Cargo.toml",), ()),
    "go": (("go.mod",), ()),
    "npm": (("package.json",), ()),
    "yarn": (("package.json", "yarn.lock"), ()),
    "pnpm": (("package.json", "pnpm-lock.yaml"), ()),
    "npx": (("package.json",), ()),
    "make": (("Makefile", "makefile", "GNUmakefile"), ()),
    "mvn": (("pom.xml",), ()),
    "gradle": (("build.gradle", "build.gradle.kts"), ()),
    "pytest": ((), ("pytest",)),
    "tox": (("tox.ini",), ("tox",)),
    "poetry": (("pyproject.toml", "poetry.lock"), ()),
    "pipenv": (("Pipfile",), ()),
    "uv": (("pyproject.toml", "uv.lock"), ()),
    "bundle": (("Gemfile",), ()),
    "rake": (("Rakefile", "Gemfile"), ()),
    "composer": (("composer.json",), ()),
    "dotnet": ((), ()),
    "swift": (("Package.swift",), ()),
    "mix": (("mix.exs",), ()),
    "helm": (("Chart.yaml",), ()),
    "kubectl": ((), ()),
    "terraform": ((), ()),
    "docker": (("Dockerfile", "docker-compose.yml", "docker-compose.yaml"), ()),
    "docker-compose": (("docker-compose.yml", "docker-compose.yaml"), ()),
    # Python tooling: a manifest, or the tool itself declared as a dependency.
    "pip": (("pyproject.toml", "setup.py", "setup.cfg", "requirements.txt"), ()),
    "ruff": ((), ("ruff",)),
    "black": ((), ("black",)),
    "mypy": ((), ("mypy",)),
    "flake8": ((), ("flake8",)),
    "unittest": (("pyproject.toml", "setup.py", "requirements.txt"), ()),
    # JS/TS tooling.
    "eslint": (("package.json",), ("eslint",)),
    "prettier": (("package.json",), ("prettier",)),
    "tsc": (("tsconfig.json",), ("typescript",)),
    "jest": (("package.json",), ("jest",)),
    "vitest": (("package.json",), ("vitest",)),
}

#: Any of these existing means the repo has a recognisable ecosystem, which is
#: what lets an absent marker count as a contradiction rather than ignorance.
_ECOSYSTEM_MARKERS = (
    "package.json",
    "pyproject.toml",
    "setup.py",
    "requirements.txt",
    "Cargo.toml",
    "go.mod",
    "pom.xml",
    "build.gradle",
    "Gemfile",
    "composer.json",
    "mix.exs",
    "Package.swift",
)

# --- technology fingerprints ---------------------------------------------

_TECH_MARKERS: Dict[str, Sequence[str]] = {
    "postgres": ("psycopg", "pg8000", "asyncpg", "postgres", "pq", "sequelize", "typeorm"),
    "postgresql": ("psycopg", "asyncpg", "postgres"),
    "mysql": ("mysql", "pymysql", "mariadb"),
    "sqlite": ("sqlite",),
    "mongodb": ("pymongo", "mongoose", "mongo"),
    "redis": ("redis", "ioredis"),
    "cassandra": ("cassandra",),
    "elasticsearch": ("elasticsearch", "opensearch"),
    "rabbitmq": ("pika", "amqp", "kombu"),
    "kafka": ("kafka", "confluent"),
    "celery": ("celery",),
    "flask": ("flask",),
    "django": ("django",),
    "fastapi": ("fastapi",),
    "express": ("express",),
    "react": ("react",),
    "vue": ("vue",),
    "kubernetes": ("kubernetes", "k8s"),
    "stripe": ("stripe",),
    "s3": ("boto3", "aws-sdk", "s3"),
}

#: Files whose text is searched for dependency substrings.
_DEPENDENCY_FILES = (
    "pyproject.toml",
    "requirements.txt",
    "requirements-dev.txt",
    "Pipfile",
    "package.json",
    "Cargo.toml",
    "go.mod",
    "pom.xml",
    "build.gradle",
    "Gemfile",
    "composer.json",
    "docker-compose.yml",
    "docker-compose.yaml",
)

_COMMAND_LINE = re.compile(r"^(?:\s{4,}|\s*[`$]\s*|\s*```\s*)?([a-z][a-z0-9_.-]*)\s")


def _is_historical(line: str) -> bool:
    lowered = line.lower()
    return any(marker in lowered for marker in _HISTORICAL_MARKERS)


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _repo_has(root: Path, names: Sequence[str]) -> Optional[str]:
    for name in names:
        if (root / name).is_file():
            return name
    return None


def _has_recognisable_ecosystem(root: Path) -> bool:
    return _repo_has(root, _ECOSYSTEM_MARKERS) is not None


def _dependency_text(root: Path) -> str:
    parts = []
    for name in _DEPENDENCY_FILES:
        path = root / name
        if path.is_file():
            parts.append(_read(path).lower())
    return "\n".join(parts)


#: Bounds on the source scan, so verification stays fast on large repositories.
_MAX_SOURCE_FILES = 400
_MAX_SOURCE_BYTES = 2_000_000

_SOURCE_EXTENSIONS = frozenset(
    {
        ".py", ".js", ".mjs", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java",
        ".rb", ".php", ".cs", ".kt", ".swift", ".ex", ".scala", ".sql",
        ".yml", ".yaml", ".tf", ".sh",
    }
)


def _source_text(root: Path) -> str:
    """Bounded scan of source files.

    Needed because a technology can be real without appearing in any manifest:
    `import sqlite3` is the standard library, so a correct "uses sqlite" claim
    has no dependency to point at. Without this, honest documents get accused.
    """
    from . import repository

    parts: List[str] = []
    budget = _MAX_SOURCE_BYTES
    count = 0
    for relative in repository.iter_candidate_files(root):
        if count >= _MAX_SOURCE_FILES or budget <= 0:
            break
        if Path(relative).suffix.lower() not in _SOURCE_EXTENSIONS:
            continue
        path = root / relative
        try:
            if path.stat().st_size > budget:
                continue
        except OSError:
            continue
        text = _read(path)
        if not text:
            continue
        parts.append(text.lower())
        budget -= len(text)
        count += 1
    return "\n".join(parts)


def extract_commands(text: str, sections: Sequence[str]) -> List[Tuple[str, str]]:
    """(section, runner token) pairs from command-looking lines."""
    from . import mdsections

    found: List[Tuple[str, str]] = []
    parsed = mdsections.parse_sections(text)
    for section in sections:
        body = parsed.get(section)
        if not body:
            continue
        for line in body.splitlines():
            stripped = line.strip().strip("`$ ")
            if not stripped or stripped.startswith(("#", "|", "-", "*", ">", "<")):
                continue
            if _is_historical(line):
                continue
            match = _COMMAND_LINE.match(line) or re.match(
                r"^([a-z][a-z0-9_.-]*)\s", stripped
            )
            if not match:
                continue
            token = match.group(1).lower()
            if token in _RUNNER_MARKERS:
                found.append((section, token))
    return found


def extract_technologies(text: str, sections: Sequence[str]) -> List[Tuple[str, str]]:
    """(section, technology) pairs named in present-tense prose."""
    from . import mdsections

    found: List[Tuple[str, str]] = []
    parsed = mdsections.parse_sections(text)
    for section in sections:
        body = parsed.get(section)
        if not body:
            continue
        for line in body.splitlines():
            if _is_historical(line):
                continue
            lowered = line.lower()
            for tech in _TECH_MARKERS:
                if re.search(rf"\b{re.escape(tech)}\b", lowered):
                    found.append((section, tech))
    return found


def verify_commands(root: Path) -> List[Claim]:
    path = root / "docs/context/WORKFLOWS.md"
    if not path.is_file():
        return []
    text = _read(path)
    deps = _dependency_text(root)
    ecosystem = _has_recognisable_ecosystem(root)

    claims: List[Claim] = []
    for section, token in dict.fromkeys(extract_commands(text, _COMMAND_SECTIONS)):
        marker_files, dep_substrings = _RUNNER_MARKERS[token]
        found = _repo_has(root, marker_files) if marker_files else None
        dep_hit = next((d for d in dep_substrings if d in deps), None)

        if found or dep_hit:
            claims.append(
                Claim(
                    "command", token, "docs/context/WORKFLOWS.md", section, CONFIRMED,
                    f"{found or dep_hit} present",
                )
            )
        elif not marker_files and not dep_substrings:
            claims.append(
                Claim("command", token, "docs/context/WORKFLOWS.md", section, UNVERIFIED,
                      "no marker file defines this runner")
            )
        elif ecosystem:
            expected = ", ".join(marker_files) or ", ".join(dep_substrings)
            claims.append(
                Claim(
                    "command", token, "docs/context/WORKFLOWS.md", section, CONTRADICTED,
                    f"`{token}` is documented but {expected} is absent, while this "
                    "repository has a different recognisable ecosystem",
                )
            )
        else:
            claims.append(
                Claim("command", token, "docs/context/WORKFLOWS.md", section, UNVERIFIED,
                      "no recognisable ecosystem to compare against")
            )
    return claims


def verify_technologies(root: Path) -> List[Claim]:
    path = root / "docs/context/ARCHITECTURE.md"
    if not path.is_file():
        return []
    text = _read(path)
    deps = _dependency_text(root)
    ecosystem = _has_recognisable_ecosystem(root)
    named = list(dict.fromkeys(extract_technologies(text, _TECH_SECTIONS)))

    # Only pay for the source scan if a manifest failed to confirm something.
    unconfirmed = [
        tech for _, tech in named
        if not any(m in deps for m in _TECH_MARKERS[tech])
    ]
    sources = _source_text(root) if unconfirmed else ""

    claims: List[Claim] = []
    for section, tech in named:
        markers = _TECH_MARKERS[tech]
        hit = next((m for m in markers if m in deps), None)
        source_hit = None if hit else next((m for m in markers if m in sources), None)
        if hit or source_hit:
            where = f"dependency matching '{hit}'" if hit else f"source usage of '{source_hit}'"
            claims.append(
                Claim("technology", tech, "docs/context/ARCHITECTURE.md", section,
                      CONFIRMED, f"{where} present")
            )
        elif ecosystem:
            claims.append(
                Claim(
                    "technology", tech, "docs/context/ARCHITECTURE.md", section,
                    CONTRADICTED,
                    f"{tech} is described as current, but no matching dependency "
                    "or source usage was found anywhere in the repository",
                )
            )
        else:
            claims.append(
                Claim("technology", tech, "docs/context/ARCHITECTURE.md", section,
                      UNVERIFIED, "no dependency manifest to compare against")
            )
    return claims


def verify_all(root: Path) -> List[Claim]:
    root = Path(root)
    return verify_commands(root) + verify_technologies(root)


def summarise(claims: Sequence[Claim]) -> Dict[str, int]:
    counts = {CONFIRMED: 0, UNVERIFIED: 0, CONTRADICTED: 0}
    for claim in claims:
        counts[claim.status] = counts.get(claim.status, 0) + 1
    return counts
