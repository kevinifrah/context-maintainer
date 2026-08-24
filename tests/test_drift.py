"""Narrative drift detection.

The design constraint that shapes every test here: this checker reports on
prose that is probably fine. A finding it cannot justify costs more than a
claim it misses, because a worklist full of noise is a worklist nobody works.

Two properties matter most and are tested first:

1. It stays silent when an unrelated file changes. Per-citation baselines are
   the whole reason this is usable — "something changed since the checkpoint"
   would flag every claim on every commit.
2. It speaks up, per claim, when the specific file a claim cites moves.
"""
import json
from pathlib import Path

import pytest

from context_maintainer import drift, gitutil
from conftest import commit_all, write
from fixtures import cli_json, run_cli

ARCHITECTURE = "docs/context/ARCHITECTURE.md"


def _attest(root: Path) -> None:
    drift.record_attestation(root, gitutil.get_head_commit(root), "2026-08-24T00:00:00+00:00")


def _project(root: Path) -> Path:
    """A repository whose ARCHITECTURE.md cites a real source file."""
    write(root, "pyproject.toml", "[project]\nname = 'demo'\n")
    write(root, "src/auth.py", "def login():\n    return True\n")
    run_cli(root, ["init"])
    _set_section(root, "Overview", "Authenticates users. CONFIRMED: `src/auth.py` handles login.")
    commit_all(root, "Initial project")
    return root


def _set_section(root: Path, heading: str, body: str) -> None:
    path = root / ARCHITECTURE
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    out, skipping = [], False
    for line in lines:
        if line.startswith("## "):
            skipping = line[3:].strip() == heading
            out.append(line)
            if skipping:
                out.extend(["", body, ""])
            continue
        if skipping:
            continue
        out.append(line)
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


# --- the noise-control property -------------------------------------------


def test_unrelated_file_changing_produces_no_finding(git_repo: Path):
    """Per-citation baselines, not checkpoint lag.

    If this ever fails, the checker has become "anything changed" and will be
    ignored within a week.
    """
    root = _project(git_repo)
    _attest(root)
    write(root, "CHANGELOG.md", "# Changelog\n")
    commit_all(root, "Unrelated change")

    stale = [f for f in drift.analyse(root).findings if f.kind == drift.STALE_EVIDENCE]
    assert not stale, [f.to_dict() for f in stale]


def test_cited_file_changing_reports_the_claim_that_rests_on_it(git_repo: Path):
    root = _project(git_repo)
    _attest(root)
    write(root, "src/auth.py", "def login():\n    return False\n")
    commit_all(root, "Change auth behaviour")

    stale = [f for f in drift.analyse(root).findings if f.kind == drift.STALE_EVIDENCE]
    assert len(stale) == 1
    assert stale[0].section == "Overview"
    assert "src/auth.py" in stale[0].detail
    assert stale[0].severity == drift.WARN


def test_each_section_citing_the_same_file_is_reported_separately(git_repo: Path):
    """Three sentences resting on one file are three sentences to re-read."""
    root = _project(git_repo)
    _set_section(root, "Components", "Login lives in `src/auth.py`.")
    _set_section(root, "Data Flow", "Requests reach `src/auth.py`.")
    commit_all(root, "Describe auth in more sections")
    _attest(root)
    write(root, "src/auth.py", "def login():\n    return False\n")
    commit_all(root, "Change auth")

    sections = {
        f.section
        for f in drift.analyse(root).findings
        if f.kind == drift.STALE_EVIDENCE
    }
    assert sections == {"Overview", "Components", "Data Flow"}


def test_editing_context_documents_does_not_make_them_look_stale(git_repo: Path):
    """A sync must not report itself as drift the moment it finishes."""
    root = _project(git_repo)
    _attest(root)
    _set_section(root, "Persistence", "Flat files. CONFIRMED by direct reading.")
    commit_all(root, "Update context")

    stale = [f for f in drift.analyse(root).findings if f.kind == drift.STALE_EVIDENCE]
    assert not stale, [f.to_dict() for f in stale]


# --- citations that point nowhere -----------------------------------------


def test_citation_to_a_missing_file_is_a_defect(git_repo: Path):
    root = _project(git_repo)
    _set_section(root, "Components", "Sessions live in `src/sessions.py`.")
    commit_all(root, "Cite a file that does not exist")

    defects = drift.analyse(root).defects
    assert any("src/sessions.py" in f.detail for f in defects), [
        f.to_dict() for f in defects
    ]


def test_citation_to_a_nested_file_by_bare_name_resolves(git_repo: Path):
    """Documents cite `auth.py` once the directory is established in prose.

    Resolving citations against the repository root instead would call every
    such reference broken — which is what a first draft of this did, on more
    than a hundred correct lines.
    """
    root = _project(git_repo)
    _set_section(root, "Components", "Login is implemented in `auth.py`.")
    commit_all(root, "Cite by bare filename")

    assert not drift.analyse(root).defects


def test_prose_containing_a_slash_is_not_read_as_a_path(git_repo: Path):
    root = _project(git_repo)
    _set_section(root, "Components", "The parser handles validate/diff and read/write modes.")
    commit_all(root, "Prose with slashes")

    assert not drift.analyse(root).defects


@pytest.mark.parametrize("phrase", ["`templates/`", "`@AGENTS.md`"])
def test_directory_and_import_citations_resolve(git_repo: Path, phrase: str):
    root = _project(git_repo)
    write(root, "templates/base.html", "<html></html>\n")
    _set_section(root, "Components", f"See {phrase} for details.")
    commit_all(root, "Cite a directory and an import")

    assert not drift.analyse(root).defects


def test_a_miscased_citation_is_a_defect_on_every_filesystem(git_repo: Path):
    """Findings must not depend on whether the developer's disk folds case.

    `Path.exists()` says yes to `Src/Auth.py` on macOS and no on Linux. A real
    miscased citation in this repository passed locally and failed in CI before
    this was fixed.
    """
    root = _project(git_repo)
    _set_section(root, "Components", "Login lives in `Src/Auth.py`.")
    commit_all(root, "Cite with the wrong case")

    defects = drift.analyse(root).defects
    assert any("Src/Auth.py" in f.detail for f in defects), [
        f.to_dict() for f in defects
    ]


def test_citation_to_a_commit_outside_history_is_a_defect(git_repo: Path):
    root = _project(git_repo)
    _set_section(root, "Overview", "Rewritten in commit deadbe1 — CONFIRMED.")
    commit_all(root, "Cite an unknown commit")

    defects = drift.analyse(root).defects
    assert any("deadbe1" in f.detail for f in defects), [f.to_dict() for f in defects]


# --- claims that rot silently ---------------------------------------------


def test_a_counted_quantity_is_flagged_for_recounting(git_repo: Path):
    root = _project(git_repo)
    _set_section(root, "Overview", "The suite has 415 tests. CONFIRMED by running it.")
    commit_all(root, "State a test count")

    volatile = [
        f for f in drift.analyse(root).findings if f.kind == drift.VOLATILE_NUMBER
    ]
    assert volatile and "415 tests" in volatile[0].detail


def test_a_version_number_is_not_treated_as_a_count(git_repo: Path):
    root = _project(git_repo)
    _set_section(root, "Overview", "Released as v1.2.3 with 0 known issues.")
    commit_all(root, "State a version")

    volatile = [
        f for f in drift.analyse(root).findings if f.kind == drift.VOLATILE_NUMBER
    ]
    assert not volatile, [f.to_dict() for f in volatile]


@pytest.mark.parametrize(
    "sentence, expected",
    [
        # The regression: an allowlist of nouns missed this one in this
        # repository's own ARCHITECTURE.md while catching "443 tests" two
        # documents away.
        ("The test suite (415 passing, run directly) corroborates it.", "415 passing"),
        # Vocabulary the tool was never written against. Every unfamiliar
        # repository counts something in a word this list has not seen.
        ("The suite has 443 specs covering the parser.", "443 specs"),
        ("It registers 12 handlers on startup.", "12 handlers"),
        ("The router exposes 27 routes.", "27 routes"),
        # A noun it does recognise still names the finding the way it did
        # before, even with markup and an adjective in the way.
        ("There are 18 **deterministic** health checks.", "18 checks"),
    ],
)
def test_a_count_is_flagged_whatever_noun_it_uses(
    git_repo: Path, sentence: str, expected: str
):
    root = _project(git_repo)
    _set_section(root, "Overview", sentence + " CONFIRMED by running it.")
    commit_all(root, "State a count")

    volatile = [
        f for f in drift.analyse(root).findings if f.kind == drift.VOLATILE_NUMBER
    ]
    assert volatile, f"nothing flagged in: {sentence}"
    assert expected in volatile[0].detail, volatile[0].detail


@pytest.mark.parametrize(
    "sentence",
    [
        # Documented constants and thresholds, not measurements.
        "STATE is re-confirmed after 21 days.",
        "Notes are truncated at 300 characters.",
        # Versions and dates carry their own units.
        "Requires Python 3.9 or newer.",
        "Released as v0.4.0 on 2026-08-24.",
        "Coverage sits at 80% overall.",
        # Identifiers, not quantities.
        "The daemon listens on port 8080 in production.",
        "Tracked upstream as issue 16430 for now.",
        # Too small to be a measurement anyone re-derives.
        "Both of the 2 hosts read the same files.",
        # A date whose trailing field lands next to a word this file does not
        # know. `2026-08-24 (v1.18.0` read as the count "24 v" until dates were
        # suppressed the way versions already were.
        "Available here as of 2026-08-24 (v1.18.0, via nvm Node 22).",
        "Attested at 2026-08-24 (commit fd27551) by the agent.",
        # A decision identifier. `_WORD` kept the trailing hyphen, so "DEC-004"
        # yielded "dec-" and never matched the `dec` suppression written for it.
        "It never writes, for the reason DEC-004 gave and DEC-007 restates.",
        "Superseded by ADR-017 after the review.",
    ],
)
def test_a_number_that_is_not_a_count_is_left_alone(git_repo: Path, sentence: str):
    """The precision side. Flagging these would make the worklist unworkable."""
    root = _project(git_repo)
    _set_section(root, "Overview", sentence + " CONFIRMED by reading the config.")
    commit_all(root, "State a non-count number")

    volatile = [
        f for f in drift.analyse(root).findings if f.kind == drift.VOLATILE_NUMBER
    ]
    assert not volatile, [f.to_dict() for f in volatile]


def test_a_claim_of_absence_is_flagged_for_rechecking(git_repo: Path):
    root = _project(git_repo)
    _set_section(root, "Integrations", "There is no message queue in this system.")
    commit_all(root, "Assert an absence")

    negatives = [
        f for f in drift.analyse(root).findings if f.kind == drift.NEGATIVE_CLAIM
    ]
    assert negatives


def test_a_migration_note_is_not_treated_as_a_current_claim(git_repo: Path):
    """The same historical exemption `verify.py` needs, for the same reason."""
    root = _project(git_repo)
    _attest(root)
    _set_section(
        root, "Persistence", "We migrated away from `src/auth.py` storage. No longer used."
    )
    write(root, "src/auth.py", "def login():\n    return False\n")
    commit_all(root, "Record a migration")

    stale = [
        f
        for f in drift.analyse(root).findings
        if f.kind == drift.STALE_EVIDENCE and f.section == "Persistence"
    ]
    assert not stale, [f.to_dict() for f in stale]


def test_decisions_are_exempt_from_current_state_checks(git_repo: Path):
    """DECISIONS.md records what was true when a decision was taken."""
    root = _project(git_repo)
    path = root / "docs/context/DECISIONS.md"
    path.write_text(
        path.read_text(encoding="utf-8")
        + "\n## DEC-009: Kept the runner\n\nWhy: there is no faster option, and "
        "the suite had 42 tests at the time.\n",
        encoding="utf-8",
    )
    commit_all(root, "Record a decision")

    kinds = {
        f.kind
        for f in drift.analyse(root).findings
        if f.source.endswith("DECISIONS.md")
    }
    assert drift.VOLATILE_NUMBER not in kinds
    assert drift.NEGATIVE_CLAIM not in kinds


# --- omissions verification cannot see ------------------------------------


def test_an_undocumented_ci_job_is_reported_when_its_siblings_are_documented(
    git_repo: Path,
):
    root = _project(git_repo)
    write(
        root,
        ".github/workflows/ci.yml",
        "name: CI\non: [push]\njobs:\n  test:\n    runs-on: ubuntu-latest\n"
        "  publish:\n    runs-on: ubuntu-latest\n",
    )
    _set_section(root, "Overview", "CI runs the test job on every push.")
    commit_all(root, "Add a second CI job")

    gaps = [f for f in drift.analyse(root).findings if f.kind == drift.COVERAGE_GAP]
    assert gaps and "publish" in gaps[0].detail


def test_a_project_documenting_no_ci_jobs_is_left_alone(git_repo: Path):
    """Choosing not to enumerate is a choice, not an omission."""
    root = _project(git_repo)
    write(
        root,
        ".github/workflows/ci.yml",
        "name: CI\non: [push]\njobs:\n  test:\n    runs-on: ubuntu-latest\n",
    )
    commit_all(root, "Add CI")

    gaps = [f for f in drift.analyse(root).findings if f.kind == drift.COVERAGE_GAP]
    assert not gaps


def test_a_release_newer_than_any_document_is_a_defect(git_repo: Path):
    root = _project(git_repo)
    _set_section(root, "Overview", "Shipping v0.1.0 now.")
    commit_all(root, "Describe the release")
    gitutil._run(root, "tag", "v0.2.0")

    defects = drift.analyse(root).defects
    assert any(f.kind == drift.VERSION_DRIFT for f in defects), [
        f.to_dict() for f in defects
    ]


# --- the ledger -----------------------------------------------------------


def test_attestation_records_the_commit_each_cited_file_was_last_touched_by(
    git_repo: Path,
):
    root = _project(git_repo)
    _attest(root)
    ledger = drift.load_ledger(root)
    evidence = ledger["attestations"][ARCHITECTURE]["evidence"]
    assert evidence["src/auth.py"] == gitutil.get_last_commit_touching(root, "src/auth.py")


def test_a_corrupt_ledger_degrades_instead_of_raising(git_repo: Path):
    root = _project(git_repo)
    (root / drift.EVIDENCE_PATH).write_text("{not json", encoding="utf-8")
    report = drift.analyse(root)
    assert not report.ledger_present
    assert any(f.kind == drift.UNATTESTED for f in report.findings)


def test_attesting_does_not_clear_a_real_defect(git_repo: Path):
    """Re-stamping must never launder a broken citation into a clean report."""
    root = _project(git_repo)
    _set_section(root, "Components", "Sessions live in `src/sessions.py`.")
    commit_all(root, "Cite a missing file")
    _attest(root)

    assert drift.analyse(root).defects


# --- integration with the CLI and doctor ----------------------------------


def test_review_reports_findings_as_json(git_repo: Path):
    root = _project(git_repo)
    _set_section(root, "Components", "Sessions live in `src/sessions.py`.")
    commit_all(root, "Cite a missing file")

    code, payload = cli_json(root, ["review"])
    assert code == 0
    assert payload["counts"][drift.DEFECT] >= 1
    assert any(f["kind"] == drift.DANGLING_CITATION for f in payload["findings"])


def test_sync_finalize_writes_the_evidence_baseline(git_repo: Path):
    root = _project(git_repo)
    code, payload = cli_json(root, ["sync", "--finalize", "--note", "initial baseline"])
    assert code == 0
    ledger = json.loads((root / drift.EVIDENCE_PATH).read_text(encoding="utf-8"))
    assert ledger["attestations"][ARCHITECTURE]["evidence"]["src/auth.py"]


def test_sync_reports_how_many_claims_need_adjudication(git_repo: Path):
    root = _project(git_repo)
    _set_section(root, "Components", "Sessions live in `src/sessions.py`.")
    commit_all(root, "Cite a missing file")

    code, payload = cli_json(root, ["sync"])
    assert code == 0
    assert payload["claims_to_adjudicate"][drift.DEFECT] >= 1


def test_doctor_verify_fails_on_a_dangling_citation(git_repo: Path):
    from context_maintainer import doctor

    root = _project(git_repo)
    _set_section(root, "Components", "Sessions live in `src/sessions.py`.")
    commit_all(root, "Cite a missing file")

    report = doctor.run_all_checks(root, verify=True)
    result = next(r for r in report.results if r.name == "context_drift")
    assert result.status == doctor.FAIL
    assert report.failed(strict=False), "a broken citation is unambiguous enough to fail"


def test_moved_evidence_does_not_fail_the_build_even_under_strict(git_repo: Path):
    """Moved evidence means unverified, not wrong — it asks rather than blocks.

    This is not merely about noise. If `--strict` failed here, the cheapest way
    back to a green build would be `sync --finalize` with no re-reading at all,
    so the gate would reward exactly the blind re-stamping DEC-006 warns about.
    """
    from context_maintainer import doctor

    root = _project(git_repo)
    _attest(root)
    write(root, "src/auth.py", "def login():\n    return False\n")
    commit_all(root, "Change auth")

    report = doctor.run_all_checks(root, verify=True)
    result = next(r for r in report.results if r.name == "context_drift")
    assert result.status == doctor.WARN
    assert not report.failed(strict=False)

    # Isolate this check: a freshly scaffolded fixture carries other warnings
    # (placeholders) that legitimately do fail under --strict.
    alone = doctor.DoctorReport(results=[result])
    assert not alone.failed(strict=True), "staleness must never break a build"


def test_a_defect_still_fails_even_though_the_check_is_advisory(git_repo: Path):
    """Advisory suppresses WARN promotion only. A FAIL is always a FAIL."""
    from context_maintainer import doctor

    assert "context_drift" in doctor.ADVISORY_CHECKS

    root = _project(git_repo)
    _set_section(root, "Components", "Sessions live in `src/sessions.py`.")
    commit_all(root, "Cite a missing file")

    report = doctor.run_all_checks(root, verify=True)
    assert report.failed(strict=False)


# --- COMPLETED_INTENT: plans the repository shows are already carried out ---
#
# The blind spot this closes is structural, not a missed pattern. Every other
# detector here watches a claim's cited evidence and reports when it moves. A
# `Next` section cites nothing, because it describes the future — so nothing can
# move underneath it, and a finished plan sits there looking current forever.
# This repository's own STATE.md carried "release the accumulated work (tag,
# marketplace update)" across three tagged releases and no detector saw it.


STATE = "docs/context/STATE.md"


def _set_state(root: Path, heading: str, body: str) -> None:
    path = root / STATE
    out, skipping = [], False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            skipping = line[3:].strip() == heading
            out.append(line)
            if skipping:
                out.extend(["", body, ""])
            continue
        if skipping:
            continue
        out.append(line)
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def _intents(root: Path):
    return [
        f for f in drift.analyse(root).findings if f.kind == drift.COMPLETED_INTENT
    ]


def test_a_plan_to_release_an_already_tagged_version_is_flagged(git_repo: Path):
    """The regression. Nothing cites a tag, so nothing else can see this."""
    root = _project(git_repo)
    _set_state(root, "Next", "Release v0.2.0, then validate on other repositories.")
    commit_all(root, "Plan the release")
    gitutil._run(root, "tag", "v0.2.0")

    findings = _intents(root)
    assert findings, "a plan to release an already-tagged version went unreported"
    assert "v0.2.0" in findings[0].detail


def test_a_plan_to_release_an_unreleased_version_is_left_alone(git_repo: Path):
    """The precision side: an unshipped plan is the normal, correct state."""
    root = _project(git_repo)
    _set_state(root, "Next", "Release v0.9.0 once the audit lands.")
    commit_all(root, "Plan the release")
    gitutil._run(root, "tag", "v0.2.0")

    assert not _intents(root)


def test_an_imperative_release_plan_is_flagged_once_nothing_is_pending(
    git_repo: Path,
):
    """"Release the accumulated work" names no version, and is still finished."""
    root = _project(git_repo)
    _set_state(root, "Phase", "Shipping v0.2.0.")
    _set_state(root, "Next", "Release the accumulated work (tag, marketplace update).")
    commit_all(root, "Plan the release")
    gitutil._run(root, "tag", "v0.2.0")

    assert _intents(root)


def test_merely_mentioning_a_release_is_not_a_plan_to_make_one(git_repo: Path):
    """Sentence-scoped and imperative-only, or two in three findings are noise.

    Both sentences below were real false positives while the rule was
    block-scoped: each mentions a released version *and* the word release, and
    neither is a plan to release anything.
    """
    root = _project(git_repo)
    _set_state(root, "Phase", "Shipping v0.2.0.")
    _set_state(
        root,
        "Next",
        "The v0.2.0 delivery fix is verified by tests. That check needs a "
        "release first.\n\nUntested consequence of the v0.2.0 envelope: it "
        "should be looked at on release, not assumed.",
    )
    commit_all(root, "Note the open questions")
    gitutil._run(root, "tag", "v0.2.0")

    assert not _intents(root), [f.to_dict() for f in _intents(root)]


def test_a_past_tense_note_about_a_release_is_not_a_plan(git_repo: Path):
    root = _project(git_repo)
    _set_state(root, "Next", "Superseded: we used to release v0.2.0 monthly.")
    commit_all(root, "Record the history")
    gitutil._run(root, "tag", "v0.2.0")

    assert not _intents(root)


def test_plans_outside_a_forward_looking_section_are_not_checked(git_repo: Path):
    """`Blockers` is not a plan list; flagging it would nag without cause."""
    root = _project(git_repo)
    _set_state(root, "Blockers", "Release v0.2.0 is stuck behind CI.")
    commit_all(root, "Record the blocker")
    gitutil._run(root, "tag", "v0.2.0")

    assert not _intents(root)


def test_another_projects_version_does_not_disable_version_checking(
    git_repo: Path,
):
    """The latent bug found while building this.

    Documenting Repomix `v1.18.0` made it "the newest version any context
    document mentions", so nothing could ever be *behind* it and `VERSION_DRIFT`
    — a DEFECT-severity check — silently stopped firing in this repository.
    """
    root = _project(git_repo)
    _set_section(root, "Overview", "Shipping v0.1.0, built against Repomix v1.18.0.")
    commit_all(root, "Describe the release")
    gitutil._run(root, "tag", "v0.2.0")

    assert any(f.kind == drift.VERSION_DRIFT for f in drift.analyse(root).defects)


def test_a_claim_that_a_tagged_version_is_unreleased_is_flagged(git_repo: Path):
    """The real-world catch: STATE.md said v0.5.1 was untagged after tagging it.

    Not a plan — an assertion about the present that a tag contradicts outright,
    which is why it is checked in every section rather than only forward-looking
    ones.
    """
    root = _project(git_repo)
    _set_state(
        root,
        "In Progress",
        "v0.2.0 is written and green but unreleased: no tag, and the "
        "marketplace has not been updated.",
    )
    commit_all(root, "Record progress")
    gitutil._run(root, "tag", "v0.2.0")

    findings = _intents(root)
    assert findings, "a tag did not contradict a claim that nothing was tagged"
    assert "unreleased" in findings[0].detail


def test_an_unreleased_claim_about_a_newer_version_is_not_about_the_tagged_one(
    git_repo: Path,
):
    """A false positive this repository's own Phase section produced.

    "v0.6.0 is not tagged; the newest tag is v0.5.1" is true, and both versions
    are in one sentence. Taking the tagged one as the subject of the negation
    reads the sentence backwards. When any named version is untagged the
    negation plausibly belongs to it, and ambiguity must not produce a finding.
    """
    root = _project(git_repo)
    _set_state(
        root,
        "Phase",
        "v0.9.0 is committed but deliberately not tagged: the newest tag is "
        "v0.2.0.",
    )
    commit_all(root, "Describe the phase")
    gitutil._run(root, "tag", "v0.2.0")

    assert not _intents(root), [f.to_dict() for f in _intents(root)]


def test_an_unreleased_claim_still_fires_when_every_version_named_is_tagged(
    git_repo: Path,
):
    """The guard above must not smother the true positive it sits next to."""
    root = _project(git_repo)
    _set_state(root, "Phase", "v0.2.0 is written but unreleased: no tag yet.")
    commit_all(root, "Describe the phase")
    gitutil._run(root, "tag", "v0.2.0")

    assert _intents(root)
