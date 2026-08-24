# Context update log

Newest first. Capped at 20 entries — older history lives in Git.
Written by `context-maintainer sync --finalize` / `rebuild --finalize`.

## 2026-08-24T11:54:49+00:00 — 1a4fe0e4

Fix hook notice delivery: PreCompact emits systemMessage, SessionStart carries the report on source=compact (DEC-009); suppress dates and identifier prefixes in volatile-number detection

## 2026-08-24T09:50:29+00:00 — 3c43465f

Updated: docs/context/ARCHITECTURE.md, docs/context/DECISIONS.md, docs/context/STATE.md, docs/context/WORKFLOWS.md

v0.5.0: context size budgets and the generated DECISIONS index (DEC-008); re-stamped ARCHITECTURE, STATE, WORKFLOWS, DECISIONS.


## 2026-08-24T08:44:01+00:00 — 755588ee

Updated: AGENTS.md, docs/context/ARCHITECTURE.md, docs/context/DECISIONS.md, docs/context/STATE.md, docs/context/WORKFLOWS.md

v0.5.0 work: PreCompact hook (DEC-007) and the abandoned-approach convention; re-stamped ARCHITECTURE, STATE, WORKFLOWS and DECISIONS against it.



## 2026-08-24T08:32:38+00:00 — 4dc2d291

Updated: docs/context/ARCHITECTURE.md, docs/context/PROJECT.md, docs/context/WORKFLOWS.md

Adjudicated the v0.4.0 worklist: generalized volatile-number detection past its closed noun list, reworded ARCHITECTURE's test count to defer to WORKFLOWS, corrected a stale README quote in PROJECT (v0.1.0 -> v0.4.0), re-confirmed the four absence claims and the 18-check count.




## 2026-08-24T05:47:32+00:00 — 7cfaad71

Updated: docs/context/ARCHITECTURE.md, docs/context/DECISIONS.md, docs/context/STATE.md, docs/context/WORKFLOWS.md

Re-confirmed the drift.py-citing claims after the case-sensitivity fix and the advisory-gate correction; all still accurate





## 2026-08-24T05:33:46+00:00 — 458c3474

Updated: AGENTS.md, docs/context/ARCHITECTURE.md, docs/context/DECISIONS.md, docs/context/PROJECT.md, docs/context/STATE.md, docs/context/WORKFLOWS.md

v0.4.0: drift detection by evidence movement; agent now adjudicates a claims worklist






## 2026-08-24T00:26:47+00:00 — 3010ebec

v0.3.0 shipped (verify.py, doctor --verify, CI context-check gate, time-based STATE staleness); a shallow-checkout test/CI fix followed. Backfilled PROJECT/ARCHITECTURE/WORKFLOWS/STATE/DECISIONS for v0.3.0 which had only updated AGENTS.md, and refreshed test counts (338->415).







## 2026-08-24T00:10:40+00:00 — 1e3c1aa5

Updated: AGENTS.md

v0.3.0: added claim verification, time-based STATE staleness, and CI enforcement.








## 2026-08-23T23:47:33+00:00 — bef3c38c

Added a capped context update log; recorded it in ARCHITECTURE and the README.
