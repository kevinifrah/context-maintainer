"""Detect narrative drift: claims that have quietly stopped being true.

`verify.py` checks a closed vocabulary — known runner tokens, known technology
names — against fingerprints. That catches a fabricated document but is blind to
the way real documents rot: a test count that was right last month, a "there is
no release workflow" note written before someone added one, a CI job that exists
in the repository and in nobody's description of it.

Prose truth is not mechanically decidable. Evidence *movement* is. Every claim in
these documents is already required to cite where it came from
(`references/evidence-policy.md`), so this module parses those citations, records
what commit each cited artifact was last touched by, and reports the claims whose
evidence has moved since anyone last confirmed them. That converts an undecidable
question into a decidable one, and — more importantly — produces a *bounded,
localized worklist* for an agent instead of "go re-read five documents", which is
advice nobody follows.

The severity split is deliberate and follows DEC-005's logic. A citation pointing
at a file that does not exist is a defect: mechanical, unambiguous, safe to fail a
build on. A claim whose evidence moved is *unverified*, not wrong — it needs
judgment, so it warns and asks. Attestation clears the second kind and never the
first, so re-stamping the ledger can never launder a real defect.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from . import contract, gitutil, mdsections

#: Where the attestation ledger lives. Deliberately not `manifest.json`: that
#: file documents itself as machine metadata only and hard-rejects unknown keys,
#: and a per-citation baseline map would swamp it.
EVIDENCE_PATH = ".context-maintainer/evidence.json"

LEDGER_SCHEMA_VERSION = 1

#: Severities, coarsest first.
INFO = "INFO"
WARN = "WARN"
DEFECT = "DEFECT"

# Finding kinds.
UNATTESTED = "UNATTESTED"
STALE_EVIDENCE = "STALE_EVIDENCE"
DANGLING_CITATION = "DANGLING_CITATION"
VOLATILE_NUMBER = "VOLATILE_NUMBER"
NEGATIVE_CLAIM = "NEGATIVE_CLAIM"
COVERAGE_GAP = "COVERAGE_GAP"
VERSION_DRIFT = "VERSION_DRIFT"

#: Grades the evidence policy asks authors to write in prose. Kept distinct from
#: `verify.py`'s CONFIRMED/UNVERIFIED/CONTRADICTED verdicts: a grade is what the
#: author asserts, a verdict is what a machine could check.
_GRADE_PATTERN = re.compile(r"\b(CONFIRMED|INFERRED|UNKNOWN)\b")

#: A claim about the past is not a present-tense claim. Same exemption as
#: `verify.py`, for the same reason: this tool actively asks people to record
#: migrations, and flagging those as drift would punish the behaviour it wants.
_HISTORICAL = (
    "previously", "formerly", "used to", "migrated away", "migrated from",
    "no longer", "superseded", "deprecated", "historical", "was replaced",
    "replaced by", "before the migration", "legacy", "removed in", "dropped in",
)

#: Nouns that make a bare number a claim about the repository rather than a
#: date, a version, or a threshold. Kept to a deliberately short list: a number
#: is the single most drift-prone thing prose can contain, but "21 days" is a
#: documented constant, not a measurement, and flagging it would be noise.
_COUNTABLE_NOUNS = (
    "test", "tests", "check", "checks", "command", "commands", "module",
    "modules", "component", "components", "job", "jobs", "entry", "entries",
    "section", "sections", "file", "files", "dependency", "dependencies",
    "endpoint", "endpoints", "table", "tables", "service", "services",
)

#: Phrasings that assert something is *absent*. These rot in total silence:
#: nothing about adding the missing thing touches the sentence that denied it,
#: and no positive evidence can ever confirm them.
_NEGATIVE_PATTERNS = (
    re.compile(r"\bthere is no\b", re.IGNORECASE),
    re.compile(r"\bthere are no\b", re.IGNORECASE),
    re.compile(r"\bno separate\b", re.IGNORECASE),
    re.compile(r"\bnot currently\b", re.IGNORECASE),
    re.compile(r"\bnot yet wired\b", re.IGNORECASE),
    re.compile(r"\bdoes not exist\b", re.IGNORECASE),
    re.compile(r"\bnone found\b", re.IGNORECASE),
    re.compile(r"\bno .{0,30}(?:workflow|job|test|command|script)s? (?:found|exists?|present)\b", re.IGNORECASE),
)

_FENCES = ("```", "~~~")
_COMMIT_TOKEN = re.compile(r"\b(?=[0-9a-f]{7,40}\b)(?=[0-9a-f]*\d)[0-9a-f]{7,40}\b")
_VERSION_TOKEN = re.compile(r"\bv?(\d+)\.(\d+)\.(\d+)\b")
#: A number, then the words that follow it. The noun is not always adjacent —
#: "17 `doctor` checks" and "18 **deterministic** checks" both put markup and
#: an adjective in between, and an adjacency-only rule misses exactly the stale
#: counts this exists to catch (it missed that one in this repository).
_NUMBER_NOUN = re.compile(r"\b(\d[\d,]*)\s+([^.;:!?\n]{0,40})")
_WORD = re.compile(r"[a-z][a-z-]*")
_BACKTICKED = re.compile(r"`([^`\n]+)`")
_MD_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
_PATHISH = re.compile(r"^[\w./@-]+$")

#: Extensions that make a bare token a path even without a slash.
_PATH_EXTENSIONS = (
    ".py", ".md", ".json", ".toml", ".yml", ".yaml", ".sh", ".cfg", ".ini",
    ".txt", ".lock", ".tmpl", ".js", ".ts", ".go", ".rs", ".rb",
)


@dataclass
class Citation:
    kind: str  # "path" | "commit" | "version" | "date"
    value: str


@dataclass
class Block:
    """One claim-sized unit of prose: a paragraph, a bullet, or a table row."""

    source: str
    section: str
    text: str

    @property
    def grade(self) -> Optional[str]:
        match = _GRADE_PATTERN.search(self.text)
        return match.group(1) if match else None

    @property
    def is_historical(self) -> bool:
        lowered = self.text.lower()
        return any(marker in lowered for marker in _HISTORICAL)

    def excerpt(self, limit: int = 100) -> str:
        flat = " ".join(self.text.split())
        return flat if len(flat) <= limit else flat[: limit - 1].rstrip() + "…"


@dataclass
class Finding:
    kind: str
    severity: str
    source: str
    section: str
    excerpt: str
    detail: str
    remediation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "severity": self.severity,
            "source": self.source,
            "section": self.section,
            "excerpt": self.excerpt,
            "detail": self.detail,
            "remediation": self.remediation,
        }


@dataclass
class DriftReport:
    findings: List[Finding] = field(default_factory=list)
    attested: Dict[str, str] = field(default_factory=dict)
    ledger_present: bool = False

    @property
    def defects(self) -> List[Finding]:
        return [f for f in self.findings if f.severity == DEFECT]

    @property
    def warnings(self) -> List[Finding]:
        return [f for f in self.findings if f.severity == WARN]

    @property
    def adjudicable(self) -> List[Finding]:
        """Everything an agent is expected to rule on, worst first."""
        order = {DEFECT: 0, WARN: 1, INFO: 2}
        return sorted(self.findings, key=lambda f: (order.get(f.severity, 3), f.source))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ledger_present": self.ledger_present,
            "attested": self.attested,
            "counts": summarise(self.findings),
            "findings": [f.to_dict() for f in self.adjudicable],
        }


def summarise(findings: Sequence[Finding]) -> Dict[str, int]:
    counts = {DEFECT: 0, WARN: 0, INFO: 0}
    for finding in findings:
        counts[finding.severity] = counts.get(finding.severity, 0) + 1
    return counts


# --- the attestation ledger ----------------------------------------------


def ledger_path(root: Path) -> Path:
    return Path(root) / EVIDENCE_PATH


def load_ledger(root: Path) -> Dict[str, Any]:
    """The recorded baseline, or an empty ledger. Never raises.

    A corrupt ledger degrades to "nothing attested" rather than breaking every
    command that consults it: the ledger is an optimisation over re-reading
    everything, and losing it must never be fatal.
    """
    path = ledger_path(root)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"schema_version": LEDGER_SCHEMA_VERSION, "attestations": {}}
    if not isinstance(data, dict) or not isinstance(data.get("attestations"), dict):
        return {"schema_version": LEDGER_SCHEMA_VERSION, "attestations": {}}
    return data


def save_ledger(root: Path, ledger: Dict[str, Any]) -> Path:
    path = ledger_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return path


def record_attestation(root: Path, commit: Optional[str], now: str) -> Path:
    """Stamp every context document with the evidence it currently rests on.

    Called from `sync --finalize`. Re-reads each document's citations rather
    than trusting a previous run, so the baseline always describes the prose as
    it now stands.
    """
    root = Path(root)
    ledger = load_ledger(root)
    attestations = ledger.setdefault("attestations", {})
    ledger["schema_version"] = LEDGER_SCHEMA_VERSION
    index = RepoIndex(root)

    for relative in _context_documents(root):
        blocks = parse_blocks(root, relative)
        evidence: Dict[str, str] = {}
        for path in sorted(_cited_paths(root, blocks, index)):
            touched = gitutil.get_last_commit_touching(root, path)
            if touched:
                evidence[path] = touched
        attestations[relative] = {
            "commit": commit,
            "at": now,
            "evidence": evidence,
        }
    return save_ledger(root, ledger)


# --- parsing prose into claims -------------------------------------------


def _context_documents(root: Path) -> List[str]:
    return [
        cf.relative_path
        for cf in contract.CONTRACT_FILES
        if cf.relative_path.startswith(contract.CONTEXT_DIR + "/")
    ]


class RepoIndex:
    """Every path in the repository, resolvable by the suffix a document cites.

    A document that says "All CLI source lives under `.../context_maintainer/`"
    and then tabulates `doctor.py`, `cli.py`, `verify.py` is citing correctly —
    the directory was established in the sentence above. Resolving those against
    the repository root instead calls each one a broken reference. Suffix
    matching is what makes the citation style people actually write checkable.
    """

    def __init__(self, root: Path) -> None:
        from . import repository

        self.root = Path(root)
        # Tracked files *and* what is on disk. A document that describes a
        # module added in the same commit is doing the right thing, and
        # `git ls-files` cannot see that module until it is staged — reporting
        # it as a broken reference would punish documenting your work as you do
        # it. The walk also covers repositories with no git at all.
        found: Set[str] = set(repository.iter_candidate_files(self.root))
        if gitutil.is_git_repo(self.root):
            found.update(gitutil.get_tracked_files(self.root))
        paths = sorted(found)
        self.files = set(paths)
        self.dirs: Set[str] = set()
        for path in paths:
            parts = path.split("/")
            for index in range(1, len(parts)):
                self.dirs.add("/".join(parts[:index]))
        self._by_name: Dict[str, str] = {}
        for path in paths:
            self._by_name.setdefault(path.rsplit("/", 1)[-1], path)
        # Directories are cited by bare name too (`templates/`,
        # `.codex-plugin/`), so they need the same basename index as files.
        for directory in sorted(self.dirs):
            self._by_name.setdefault(directory.rsplit("/", 1)[-1], directory)

    def resolve(self, value: str) -> Optional[str]:
        """The real repo-relative path a citation names, or None."""
        # `@AGENTS.md` is Claude Code's import directive, not a filename.
        candidate = value.strip().lstrip("@").rstrip("/")
        if not candidate:
            return None
        if candidate in self.files or candidate in self.dirs:
            return candidate
        if (self.root / candidate).exists():
            return candidate
        if "/" in candidate:
            suffix = "/" + candidate
            for path in self.files:
                if path.endswith(suffix):
                    return path
            for path in self.dirs:
                if path.endswith(suffix):
                    return path
            return None
        return self._by_name.get(candidate)


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _strip_noise(body: str) -> List[str]:
    """Section body lines, minus fenced code and HTML comments.

    Fenced blocks are excluded because command claims already have a dedicated
    verifier; comments because template guidance is not a claim about anything.
    """
    lines: List[str] = []
    in_fence = False
    in_comment = False
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith(_FENCES):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if in_comment:
            if "-->" in stripped:
                in_comment = False
            continue
        if stripped.startswith("<!--"):
            if "-->" not in stripped:
                in_comment = True
            continue
        lines.append(line)
    return lines


def _segment(lines: Sequence[str]) -> List[str]:
    """Group lines into claim-sized blocks.

    A wrapped paragraph is one claim. A bullet is one claim, including its
    indented continuation lines. A table row is one claim. Getting this unit
    right is what makes a finding quotable back to the author.
    """
    blocks: List[str] = []
    current: List[str] = []

    def flush() -> None:
        if current:
            blocks.append("\n".join(current))
            current.clear()

    for line in lines:
        stripped = line.strip()
        if not stripped:
            flush()
            continue
        is_bullet = stripped.startswith(("- ", "* ", "+ ")) or re.match(r"^\d+\. ", stripped)
        is_row = stripped.startswith("|")
        if is_bullet or is_row:
            flush()
            current.append(line)
            continue
        if current and (current[-1].strip().startswith(("- ", "* ", "+ ")) or current[-1].strip().startswith("|")):
            # An indented continuation belongs to the bullet above it; a fresh
            # unindented sentence after a bullet starts a new block.
            if line.startswith((" ", "\t")):
                current.append(line)
                continue
            flush()
        current.append(line)
    flush()

    # Table separator rows carry no claim.
    return [b for b in blocks if not re.match(r"^\s*\|[\s|:-]+\|?\s*$", b)]


def parse_blocks(root: Path, relative: str) -> List[Block]:
    text = _read(Path(root) / relative)
    if not text:
        return []
    blocks: List[Block] = []
    for section, body in mdsections.parse_sections(text).items():
        for chunk in _segment(_strip_noise(body)):
            if chunk.strip():
                blocks.append(Block(source=relative, section=section, text=chunk))
    return blocks


def _looks_like_path(token: str) -> bool:
    """Is this token *asserting* a path, as opposed to being English with a slash?

    Deliberately strict, because failing to resolve a path is reported as a
    defect. `Reads/writes`, `CONFIRMED/INFERRED/UNKNOWN` and `validate/diff` are
    all prose; treating them as broken file references produced 100+ false
    positives on this repository's own documents, which is precisely how a
    checker gets switched off.
    """
    token = token.strip()
    if not token or not _PATHISH.match(token) or token.startswith("-"):
        return False
    if token.endswith("/"):
        return True
    return token.lower().endswith(_PATH_EXTENSIONS)


def extract_citations(block: Block) -> List[Citation]:
    """Everything in a block that points at a checkable artifact."""
    citations: List[Citation] = []
    seen: Set[Tuple[str, str]] = set()

    def add(kind: str, value: str) -> None:
        key = (kind, value)
        if key not in seen:
            seen.add(key)
            citations.append(Citation(kind, value))

    candidates = list(_BACKTICKED.findall(block.text))
    candidates.extend(_MD_LINK.findall(block.text))
    # Bare paths in prose ("CONFIRMED: pyproject.toml, README ..."), scanned
    # only outside backticks — otherwise `skill/context-maintainer/SKILL.md`
    # also yields the fragment `maintainer/SKILL.md`, which resolves nowhere.
    outside = _BACKTICKED.sub(" ", block.text)
    candidates.extend(
        re.findall(r"(?<![\w/-])([\w.-]+/[\w./-]+|[\w-]+\.[a-z]{2,5})\b", outside)
    )

    for candidate in candidates:
        target = candidate.split("#", 1)[0].strip().rstrip(".,;:")
        if "://" in target or target.startswith("mailto:"):
            continue
        if _looks_like_path(target):
            add("path", target)

    for token in _COMMIT_TOKEN.findall(block.text):
        add("commit", token)
    for match in _VERSION_TOKEN.finditer(block.text):
        add("version", match.group(0).lstrip("v"))
    for token in re.findall(r"\b(\d{4}-\d{2}-\d{2})\b", block.text):
        add("date", token)
    return citations


def _is_own_bookkeeping(root: Path, path: str) -> bool:
    """Is this path the context's own output rather than evidence about the project?

    A context document citing another context document is cross-referencing,
    not evidence. Treating it as evidence would make every document look stale
    the moment any one of them was edited — including by the sync that just
    updated them.
    """
    owned = set(_context_documents(root)) | {"AGENTS.md", "CLAUDE.md"}
    return path in owned or path.startswith(".context-maintainer/")


def _cited_paths(root: Path, blocks: Sequence[Block], index: "RepoIndex") -> Set[str]:
    """Real repo paths this document's claims rest on."""
    found: Set[str] = set()
    for block in blocks:
        if block.is_historical:
            continue
        for citation in extract_citations(block):
            if citation.kind != "path":
                continue
            resolved = index.resolve(citation.value)
            if resolved and not _is_own_bookkeeping(root, resolved):
                found.add(resolved)
    return found


# --- detectors -------------------------------------------------------------


def _detect_dangling(
    root: Path, blocks: Sequence[Block], is_repo: bool, index: "RepoIndex"
) -> List[Finding]:
    findings: List[Finding] = []
    for block in blocks:
        for citation in extract_citations(block):
            if citation.kind == "path":
                if index.resolve(citation.value):
                    continue
                findings.append(
                    Finding(
                        DANGLING_CITATION, DEFECT, block.source, block.section,
                        block.excerpt(),
                        f"cites `{citation.value}`, which does not exist",
                        "Correct the path, or remove the citation if the claim "
                        "no longer rests on it.",
                    )
                )
            elif citation.kind == "commit" and is_repo:
                if gitutil.commit_exists(root, citation.value):
                    continue
                findings.append(
                    Finding(
                        DANGLING_CITATION, DEFECT, block.source, block.section,
                        block.excerpt(),
                        f"cites commit {citation.value}, which is not in this "
                        "repository's history",
                        "Re-cite a commit that exists, or drop the reference "
                        "if history was rewritten.",
                    )
                )
    return findings


def _detect_stale_evidence(
    root: Path,
    blocks: Sequence[Block],
    baseline: Dict[str, str],
    index: "RepoIndex",
    moved: Optional[Set[str]],
) -> List[Finding]:
    """Claims whose cited files have changed since the document was attested.

    `moved` is the set of paths git reports as changed since the attestation
    commit — one subprocess for the whole document. Asking git per citation
    instead turned a sync into dozens of process spawns on a repository with a
    normal number of citations.
    """
    findings: List[Finding] = []
    reported: Set[Tuple[str, str, str]] = set()
    for block in blocks:
        if block.is_historical:
            continue
        for citation in extract_citations(block):
            if citation.kind != "path":
                continue
            resolved = index.resolve(citation.value)
            if not resolved or resolved not in baseline:
                continue
            if moved is not None and resolved not in moved:
                continue
            current = gitutil.get_last_commit_touching(root, resolved)
            if not current or current == baseline[resolved]:
                continue
            # One finding per *claim*, not per document: the same file cited
            # from three sections means three sentences to re-read, and
            # reporting it once would leave two of them silently unfixed.
            key = (block.source, block.section, resolved)
            if key in reported:
                continue
            reported.add(key)
            findings.append(
                Finding(
                    STALE_EVIDENCE, WARN, block.source, block.section,
                    block.excerpt(),
                    f"rests on `{resolved}`, which has changed since this "
                    f"was last confirmed ({baseline[resolved]} → {current})",
                    "Re-read the claim against the current file. Correct it, or "
                    "re-confirm it with `context-maintainer sync --finalize`.",
                )
            )
    return findings


def _detect_volatile_numbers(
    blocks: Sequence[Block], code_moved: bool, attested: bool
) -> List[Finding]:
    """Counted quantities asserted about the repository.

    A number is the most perishable thing prose can contain: nothing about
    adding the 416th test edits the sentence that says there are 415. It stays
    informational while the code sits still, and becomes worth re-checking the
    moment it moves.
    """
    findings: List[Finding] = []
    severity = WARN if (code_moved or not attested) else INFO
    for block in blocks:
        if block.is_historical:
            continue
        versions = {m.group(0) for m in _VERSION_TOKEN.finditer(block.text)}
        for match in _NUMBER_NOUN.finditer(block.text.lower()):
            number = match.group(1)
            if any(number in version for version in versions):
                continue
            # The noun may sit a word or two past the number, behind markup.
            following = _WORD.findall(match.group(2))[:3]
            noun = next((w for w in following if w in _COUNTABLE_NOUNS), None)
            if not noun:
                continue
            findings.append(
                Finding(
                    VOLATILE_NUMBER, severity, block.source, block.section,
                    block.excerpt(),
                    f'states "{number} {noun}" — a count that nothing will '
                    "correct when it stops being right",
                    "Re-count it, or reword so the exact figure is not the claim.",
                )
            )
            break
    return findings


def _detect_negative_claims(
    blocks: Sequence[Block], code_moved: bool, attested: bool
) -> List[Finding]:
    findings: List[Finding] = []
    for block in blocks:
        if block.is_historical:
            continue
        if not any(pattern.search(block.text) for pattern in _NEGATIVE_PATTERNS):
            continue
        severity = WARN if (code_moved or not attested) else INFO
        findings.append(
            Finding(
                NEGATIVE_CLAIM, severity, block.source, block.section,
                block.excerpt(),
                "asserts something is absent — a claim no positive evidence can "
                "ever re-confirm, and which nothing will contradict out loud "
                "when it stops being true",
                "Check whether it is still absent. If it is, re-confirm it; if "
                "it is not, this is the drift you were looking for.",
            )
        )
    return findings


def _ci_job_names(root: Path) -> Dict[str, List[str]]:
    """Job names per workflow file, parsed without a YAML dependency.

    Line-based on purpose: this package has no third-party dependencies, and a
    `jobs:` block is regular enough that indentation alone identifies it.
    """
    jobs: Dict[str, List[str]] = {}
    workflows = Path(root) / ".github" / "workflows"
    if not workflows.is_dir():
        return jobs
    for path in sorted(workflows.glob("*.y*ml")):
        names: List[str] = []
        in_jobs = False
        indent = None
        for line in _read(path).splitlines():
            if re.match(r"^jobs:\s*$", line):
                in_jobs = True
                continue
            if not in_jobs or not line.strip() or line.lstrip().startswith("#"):
                continue
            leading = len(line) - len(line.lstrip())
            if leading == 0:
                break
            if indent is None:
                indent = leading
            if leading == indent:
                match = re.match(r"^\s*([A-Za-z0-9_-]+):\s*$", line)
                if match:
                    names.append(match.group(1))
        if names:
            jobs[str(path.relative_to(root))] = names
    return jobs


def _detect_coverage_gaps(root: Path, corpus: str) -> List[Finding]:
    """Salient repository facts that no context document mentions.

    Verification can only judge claims that exist; an omission is invisible to
    it. This is the other half — and it is why a CI job can be added, described
    nowhere, and still leave every check green.
    """
    findings: List[Finding] = []
    lowered = corpus.lower()

    for workflow, names in _ci_job_names(root).items():
        missing = [n for n in names if n.lower() not in lowered]
        if not missing or len(missing) == len(names):
            # All named, or none named at all: a project that documents no jobs
            # has chosen not to enumerate them, and nagging would be wrong.
            continue
        findings.append(
            Finding(
                COVERAGE_GAP, WARN, "docs/context/WORKFLOWS.md", "Deploy",
                f"{workflow}: {', '.join(missing)}",
                f"CI job(s) {', '.join(missing)} exist in {workflow} but appear "
                "in no context document, while their sibling jobs do",
                "Describe them in WORKFLOWS.md, or say why they are not worth "
                "documenting.",
            )
        )
    return findings


def _detect_version_drift(root: Path, corpus: str, is_repo: bool) -> List[Finding]:
    if not is_repo:
        return []
    tags = [t for t in gitutil.get_tags(root) if _VERSION_TOKEN.search(t)]
    if not tags:
        return []

    def parse(text: str) -> Optional[Tuple[int, int, int]]:
        match = _VERSION_TOKEN.search(text)
        if not match:
            return None
        return (int(match.group(1)), int(match.group(2)), int(match.group(3)))

    latest_tag = max((parse(t) for t in tags if parse(t)), default=None)
    documented = [parse(m.group(0)) for m in _VERSION_TOKEN.finditer(corpus)]
    highest_documented = max((v for v in documented if v), default=None)
    if latest_tag is None or highest_documented is None:
        return []
    if highest_documented >= latest_tag:
        return []
    return [
        Finding(
            VERSION_DRIFT, DEFECT, "docs/context/STATE.md", "Phase",
            "v{}.{}.{} is the newest version any context document mentions".format(
                *highest_documented
            ),
            "the repository is tagged v{}.{}.{}, newer than anything the context "
            "documents describe".format(*latest_tag),
            "Update STATE.md's Phase (and PROJECT/ARCHITECTURE if the release "
            "changed them) to describe the released version.",
        )
    ]


# --- the whole pass --------------------------------------------------------


def analyse(root: Path) -> DriftReport:
    """Every drift finding for this repository, worst first."""
    root = Path(root)
    is_repo = gitutil.is_git_repo(root)
    ledger = load_ledger(root)
    attestations = ledger.get("attestations", {})
    report = DriftReport(ledger_present=bool(attestations))
    index = RepoIndex(root)

    documents = _context_documents(root)
    corpus_parts: List[str] = []
    all_blocks: Dict[str, List[Block]] = {}
    for relative in documents:
        blocks = parse_blocks(root, relative)
        all_blocks[relative] = blocks
        corpus_parts.append(_read(root / relative))
    corpus = "\n".join(corpus_parts)

    for relative in documents:
        blocks = all_blocks[relative]
        if not blocks:
            continue
        record = attestations.get(relative) or {}
        baseline = record.get("evidence") or {}
        attested = bool(record.get("commit"))
        if attested:
            report.attested[relative] = str(record.get("at") or "")

        report.findings.extend(_detect_dangling(root, blocks, is_repo, index))

        if not attested:
            report.findings.append(
                Finding(
                    UNATTESTED, INFO, relative, "(document)", "",
                    "no evidence baseline recorded, so nothing here can be "
                    "reported as newly stale",
                    "Run `context-maintainer sync --finalize` to record what "
                    "this document currently rests on.",
                )
            )
        # One `git diff` per document answers both "which cited files moved"
        # and "did any code move at all", instead of a subprocess per citation.
        changed: Optional[List[Tuple[str, str]]] = None
        stamp = str(record.get("commit") or "")
        if attested and is_repo and stamp and gitutil.commit_exists(root, stamp):
            changed = gitutil.get_changed_files_since(root, stamp)

        if attested:
            moved = {path for _, path in changed} if changed is not None else None
            report.findings.extend(
                _detect_stale_evidence(root, blocks, baseline, index, moved)
            )

        code_moved = bool(changed is not None and _has_non_context_change(changed))
        # DECISIONS.md is an append-only record of what was decided and when.
        # Its numbers and negatives describe the moment a decision was taken,
        # not the present, so re-checking them against today's repository would
        # ask authors to rewrite history — which the contract forbids.
        if relative.endswith("DECISIONS.md"):
            continue
        report.findings.extend(
            _detect_volatile_numbers(blocks, code_moved, attested)
        )
        report.findings.extend(_detect_negative_claims(blocks, code_moved, attested))

    report.findings.extend(_detect_coverage_gaps(root, corpus))
    report.findings.extend(_detect_version_drift(root, corpus, is_repo))
    return report


def _has_non_context_change(changed: Sequence[Tuple[str, str]]) -> bool:
    """Did anything outside the context's own bookkeeping change?

    Mirrors `briefing._is_context_owned`: counting our own output as change
    would make every document look stale immediately after every sync.
    """
    for _, path in changed:
        if path in ("AGENTS.md", "CLAUDE.md"):
            continue
        if path.startswith((contract.CONTEXT_DIR + "/", ".context-maintainer/")):
            continue
        return True
    return False


def render_text(report: DriftReport) -> str:
    findings = report.adjudicable
    if not findings:
        return (
            "No context drift detected — every cited claim rests on evidence "
            "that has not moved since it was confirmed."
        )
    counts = summarise(findings)
    lines = [
        "Claims needing adjudication: "
        f"{counts[DEFECT]} defect(s), {counts[WARN]} to re-check, "
        f"{counts[INFO]} informational.",
        "",
    ]
    current_source = None
    for finding in findings:
        if finding.source != current_source:
            current_source = finding.source
            lines.append(f"{finding.source}")
        lines.append(f"  [{finding.severity}] {finding.kind} — {finding.section}")
        if finding.excerpt:
            lines.append(f"      “{finding.excerpt}”")
        lines.append(f"      {finding.detail}")
        if finding.remediation:
            lines.append(f"      → {finding.remediation}")
    lines.append("")
    lines.append(
        "Adjudicate every item: correct the claim, or re-confirm it and record "
        "that with `context-maintainer sync --finalize --note \"...\"`."
    )
    return "\n".join(lines)
