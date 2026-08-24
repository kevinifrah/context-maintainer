"""Claim verification: the only check that looks at whether content is *true*.

The design constraint that shapes every test here: a false positive costs more
trust than a missed claim. So the bar is not "catches everything" — it is
"never wrong about an honest document". Hence three verdicts, and an explicit
exemption for historical statements, which this tool actively asks people to
record.
"""
from pathlib import Path

import pytest

from context_maintainer import verify

from fixtures import cli_json, make_blank_repo, run_cli
from fixtures.helpers import commit, write


def _python_project(tmp_path: Path, name: str = "proj") -> Path:
    """A repo whose real stack is Python + pytest + sqlite."""
    root = make_blank_repo(tmp_path, name=name)
    write(root, "pyproject.toml", '[project]\nname = "proj"\ndependencies = ["flask"]\n'
          '[project.optional-dependencies]\ndev = ["pytest>=7"]\n')
    write(root, "app.py", "import sqlite3\n")
    commit(root, "Add python project")
    return root


def _set_section(root: Path, relative: str, heading: str, body: str) -> None:
    path = root / relative
    lines = path.read_text(encoding="utf-8").splitlines()
    out, index = [], 0
    while index < len(lines):
        line = lines[index]
        out.append(line)
        if line.strip() == f"## {heading}":
            index += 1
            while index < len(lines) and not lines[index].startswith("## "):
                index += 1
            out.extend(["", body, ""])
            continue
        index += 1
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


# --- the core promise: fabrication is caught ------------------------------


def test_a_fabricated_stack_is_contradicted(tmp_path: Path):
    """The failure that motivated this module: docs claiming a different stack."""
    root = _python_project(tmp_path)
    run_cli(root, ["init"])
    _set_section(root, "docs/context/WORKFLOWS.md", "Build", "```bash\ncargo build --release\n```")
    _set_section(root, "docs/context/ARCHITECTURE.md", "Persistence", "Backed by Cassandra.")

    claims = verify.verify_all(root)
    contradicted = {c.value for c in claims if c.status == verify.CONTRADICTED}
    assert "cargo" in contradicted
    assert "cassandra" in contradicted


def test_an_honest_document_produces_no_contradictions(tmp_path: Path):
    """The property that matters most — no false positives on true docs."""
    root = _python_project(tmp_path)
    run_cli(root, ["init"])
    _set_section(root, "docs/context/WORKFLOWS.md", "Testing", "```bash\npytest -q\n```")
    _set_section(root, "docs/context/ARCHITECTURE.md", "Components", "A Flask application.")
    _set_section(root, "docs/context/ARCHITECTURE.md", "Persistence", "Uses sqlite.")

    claims = verify.verify_all(root)
    assert [c for c in claims if c.status == verify.CONFIRMED]
    assert not [c for c in claims if c.status == verify.CONTRADICTED]


# --- the historical exemption --------------------------------------------


def test_a_migration_note_is_not_treated_as_a_current_claim(tmp_path: Path):
    """Recording migrations is something this tool asks for; it must not
    then flag the thing that was migrated away from."""
    root = _python_project(tmp_path)
    run_cli(root, ["init"])
    _set_section(
        root,
        "docs/context/ARCHITECTURE.md",
        "Persistence",
        "Uses sqlite. Previously used MongoDB; migrated away in 2025.",
    )
    claims = verify.verify_all(root)
    assert "mongodb" not in {c.value for c in claims}


@pytest.mark.parametrize(
    "phrase",
    ["previously", "formerly", "no longer", "superseded", "deprecated", "legacy",
     "used to", "migrated from", "replaced by"],
)
def test_each_historical_marker_exempts_a_line(tmp_path: Path, phrase: str):
    root = _python_project(tmp_path, name=f"p-{phrase.replace(' ', '-')}")
    run_cli(root, ["init"])
    _set_section(
        root, "docs/context/ARCHITECTURE.md", "Persistence",
        f"Storage {phrase} Cassandra.",
    )
    claims = verify.verify_all(root)
    assert "cassandra" not in {c.value for c in claims}


# --- conservatism: unknown territory is UNVERIFIED, never CONTRADICTED ---


def test_no_ecosystem_means_unverified_not_contradicted(tmp_path: Path):
    """With no manifest at all we cannot know, so we must not accuse."""
    root = make_blank_repo(tmp_path, name="bare")
    run_cli(root, ["init"])
    _set_section(root, "docs/context/WORKFLOWS.md", "Build", "```bash\ncargo build\n```")
    claims = verify.verify_all(root)
    statuses = {c.value: c.status for c in claims}
    assert statuses.get("cargo") == verify.UNVERIFIED


def test_a_runner_with_no_defining_marker_is_unverified(tmp_path: Path):
    root = _python_project(tmp_path)
    run_cli(root, ["init"])
    _set_section(root, "docs/context/WORKFLOWS.md", "Deploy", "```bash\nkubectl apply -f k8s/\n```")
    claims = verify.verify_all(root)
    statuses = {c.value: c.status for c in claims}
    assert statuses.get("kubectl") == verify.UNVERIFIED


def test_prose_that_is_not_a_command_is_ignored(tmp_path: Path):
    root = _python_project(tmp_path)
    run_cli(root, ["init"])
    _set_section(
        root, "docs/context/WORKFLOWS.md", "Deploy",
        "Deployment is handled by the platform team; ask before releasing.",
    )
    assert not [c for c in verify.verify_all(root) if c.kind == "command"]


def test_unknown_words_are_not_invented_as_claims(tmp_path: Path):
    root = _python_project(tmp_path)
    run_cli(root, ["init"])
    _set_section(root, "docs/context/WORKFLOWS.md", "Build", "```bash\nfrobnicate --all\n```")
    assert "frobnicate" not in {c.value for c in verify.verify_all(root)}


# --- confirmation paths --------------------------------------------------


def test_a_marker_file_confirms_a_runner(tmp_path: Path):
    root = _python_project(tmp_path)
    write(root, "Makefile", "check:\n\tpytest -q\n")
    commit(root, "Add Makefile")
    run_cli(root, ["init"])
    _set_section(root, "docs/context/WORKFLOWS.md", "Testing", "```bash\nmake check\n```")
    statuses = {c.value: c.status for c in verify.verify_all(root)}
    assert statuses.get("make") == verify.CONFIRMED


def test_a_dependency_confirms_a_technology(tmp_path: Path):
    root = _python_project(tmp_path)
    run_cli(root, ["init"])
    _set_section(root, "docs/context/ARCHITECTURE.md", "Components", "Built on Flask.")
    statuses = {c.value: c.status for c in verify.verify_all(root)}
    assert statuses.get("flask") == verify.CONFIRMED


def test_docker_compose_dependency_confirms_a_service(tmp_path: Path):
    root = _python_project(tmp_path)
    write(root, "docker-compose.yml", "services:\n  cache:\n    image: redis:7\n")
    commit(root, "Add compose file")
    run_cli(root, ["init"])
    _set_section(root, "docs/context/ARCHITECTURE.md", "Integrations", "Redis for caching.")
    statuses = {c.value: c.status for c in verify.verify_all(root)}
    assert statuses.get("redis") == verify.CONFIRMED


def test_summarise_counts_each_status(tmp_path: Path):
    root = _python_project(tmp_path)
    run_cli(root, ["init"])
    _set_section(root, "docs/context/WORKFLOWS.md", "Testing", "```bash\npytest -q\n```")
    _set_section(root, "docs/context/ARCHITECTURE.md", "Persistence", "Backed by Cassandra.")
    counts = verify.summarise(verify.verify_all(root))
    assert counts[verify.CONFIRMED] >= 1
    assert counts[verify.CONTRADICTED] >= 1


def test_missing_documents_yield_no_claims(tmp_path: Path):
    root = make_blank_repo(tmp_path, name="nodocs")
    assert verify.verify_all(root) == []


# --- integration with doctor ---------------------------------------------


def test_doctor_without_verify_ignores_content_entirely(tmp_path: Path):
    """Structural checks are orthogonal to truth — that is why --verify exists."""
    root = _python_project(tmp_path)
    run_cli(root, ["init"])
    _set_section(root, "docs/context/ARCHITECTURE.md", "Persistence", "Backed by Cassandra.")
    _, payload = cli_json(root, ["doctor"])
    assert not any(r["name"] == "claims_verified" for r in payload["results"])


def test_doctor_verify_reports_contradictions_as_warn(tmp_path: Path):
    root = _python_project(tmp_path)
    run_cli(root, ["init"])
    _set_section(root, "docs/context/ARCHITECTURE.md", "Persistence", "Backed by Cassandra.")
    code, payload = cli_json(root, ["doctor", "--verify"])
    check = next(r for r in payload["results"] if r["name"] == "claims_verified")
    assert check["status"] == "WARN"
    assert "contradicted" in check["message"]
    assert code == 0, "advisory by default — a false positive must not block work"


def test_doctor_verify_strict_fails(tmp_path: Path):
    """Enforcement is opt-in, and this is what CI uses."""
    root = _python_project(tmp_path)
    run_cli(root, ["init"])
    _set_section(root, "docs/context/ARCHITECTURE.md", "Persistence", "Backed by Cassandra.")
    code, _ = cli_json(root, ["doctor", "--verify", "--strict"])
    assert code == 1


def test_doctor_verify_passes_on_honest_documents(tmp_path: Path):
    root = _python_project(tmp_path)
    run_cli(root, ["init"])
    _set_section(root, "docs/context/WORKFLOWS.md", "Testing", "```bash\npytest -q\n```")
    _, payload = cli_json(root, ["doctor", "--verify"])
    check = next(r for r in payload["results"] if r["name"] == "claims_verified")
    assert check["status"] == "PASS"


def test_this_repository_has_no_contradicted_claims():
    """Dogfooding: our own context must survive our own verifier."""
    repo_root = Path(__file__).resolve().parent.parent
    contradicted = [
        c for c in verify.verify_all(repo_root) if c.status == verify.CONTRADICTED
    ]
    assert not contradicted, [c.to_dict() for c in contradicted]


# --- advisory vs blocking: what --strict may and may not fail on ----------


def test_strict_ignores_environmental_warnings(tmp_path: Path, monkeypatch):
    """CI must not fail because a machine lacks an optional tool.

    Repomix availability and skill installation are always WARN in CI and say
    nothing about whether the documents are correct. Promoting them would make
    --strict useless for the one job it exists to do.
    """
    from context_maintainer import doctor

    report = doctor.DoctorReport(
        results=[
            doctor.CheckResult("repomix_available", doctor.WARN, "absent"),
            doctor.CheckResult("skill_installation", doctor.WARN, "not installed"),
            doctor.CheckResult("checkpoint_freshness", doctor.WARN, "behind"),
            doctor.CheckResult("state_freshness", doctor.WARN, "old"),
        ]
    )
    assert report.overall == doctor.WARN
    assert not report.failed(strict=True)


def test_strict_fails_on_context_warnings(tmp_path: Path):
    from context_maintainer import doctor

    report = doctor.DoctorReport(
        results=[
            doctor.CheckResult("repomix_available", doctor.WARN, "absent"),
            doctor.CheckResult("claims_verified", doctor.WARN, "contradicted"),
        ]
    )
    assert report.failed(strict=True)


def test_structural_failures_block_without_strict():
    from context_maintainer import doctor

    report = doctor.DoctorReport(
        results=[doctor.CheckResult("claude_agents_bridge", doctor.FAIL, "broken")]
    )
    assert report.failed(strict=False)


def test_every_advisory_check_name_is_a_real_check():
    """A typo in ADVISORY_CHECKS would silently stop enforcing a real check."""
    from context_maintainer import doctor

    known = {c.__name__.replace("check_", "") for c in doctor.CHECKS}
    # Check names are not always their function names, so compare against the
    # names the checks actually emit on a bare directory.
    from pathlib import Path as _P
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        emitted = {c(_P(tmp)).name for c in doctor.CHECKS}
    # Verify-only checks are not in CHECKS, so name them explicitly.
    emitted.add("claims_verified")
    emitted.add("context_drift")
    unknown = doctor.ADVISORY_CHECKS - emitted
    assert not unknown, f"ADVISORY_CHECKS names no real check: {unknown}"


def _is_shallow(root: Path) -> bool:
    import subprocess

    result = subprocess.run(
        ["git", "rev-parse", "--is-shallow-repository"],
        cwd=str(root), capture_output=True, text=True,
    )
    return result.stdout.strip() == "true"


def test_this_repository_passes_its_own_ci_gate():
    """The exact command the CI job runs must pass on this repository.

    Skipped on a shallow clone: the checkpoint commit legitimately does not
    exist there, so the failure would be about checkout depth rather than about
    this repository's context.
    """
    from context_maintainer import doctor

    repo_root = Path(__file__).resolve().parent.parent
    if _is_shallow(repo_root):
        pytest.skip("shallow clone: checkpoint history unavailable")
    report = doctor.run_all_checks(repo_root, verify=True)
    assert not report.failed(strict=True), [
        r.to_dict() for r in report.results
        if r.status != doctor.PASS and r.name not in doctor.ADVISORY_CHECKS
    ]
