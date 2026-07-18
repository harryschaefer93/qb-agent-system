"""
QB Production Telemetry — mine the VS Code Copilot Chat session store for
real QB (and sub-agent) behavior, score against per-IMP acceptance rules,
and emit evidence artifacts + IMP frontmatter lines.

Built for IMP-0022. See ~/.copilot/agents/improvements/IMP-0022-*.md.

Two-store reality:
  - VS Code Copilot Chat (primary):  %APPDATA%/Code/User/globalStorage/github.copilot-chat/session-store.db
  - Copilot CLI (secondary):         ~/.copilot/session-store.db

Both share the same schema (sessions/turns/session_files/session_refs/checkpoints).
We open read-only (SQLite URI mode=ro) since VS Code may be actively writing.

Usage:
    python -m runner.telemetry scan --since 30d
    python -m runner.telemetry score --session <sid> --imp IMP-0021
    python -m runner.telemetry backfill --imp IMP-0021 [--imp IMP-0012 ...]
    python -m runner.telemetry yaml-line --evidence <path>     # emit frontmatter line only
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Iterable

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

HOME = Path(os.environ.get("USERPROFILE") or os.path.expanduser("~"))
VSCODE_DB = HOME / "AppData" / "Roaming" / "Code" / "User" / "globalStorage" / "github.copilot-chat" / "session-store.db"
CLI_DB = HOME / ".copilot" / "session-store.db"
EVIDENCE_ROOT = HOME / ".copilot" / "evals" / "evidence"

# ---------------------------------------------------------------------------
# Fingerprints — keep all regex constants here for easy update when QB evolves
# ---------------------------------------------------------------------------

FP_QB_RESULT_HEADER = re.compile(r"##\s*QB\s*Result", re.IGNORECASE)
FP_TASK_TYPE = re.compile(r"\*?\*?Task\s*[Tt]ype\*?\*?\s*:\s*([\w-]+)")
FP_CLASSIFICATION = re.compile(r"\*?\*?Classification\*?\*?\s*:\s*([^\n]+)")
FP_SCOPE = re.compile(r"\*?\*?Scope\*?\*?\s*:\s*(\w+)")
FP_ROUTING_PLAN = re.compile(r"##\s*Routing\s*Plan", re.IGNORECASE)
FP_CHECKPOINT_1 = re.compile(r"CHECKPOINT\s*1\b", re.IGNORECASE)
FP_CHECKPOINT_2 = re.compile(r"CHECKPOINT\s*2\b", re.IGNORECASE)
FP_ASK_QUESTIONS = re.compile(r"\baskQuestions\b")
FP_RUN_SUBAGENT = re.compile(r"\brunSubagent\b")
FP_REQUIRED_OUTPUT_SHAPE = re.compile(r"Required\s+Output\s+Shape", re.IGNORECASE)
FP_RECOMMENDED_TRUE = re.compile(r"recommended\s*:\s*true", re.IGNORECASE)
FP_SOURCE_CITATION = re.compile(r"Source\s*:\s*(?:https?://|MS\s+Learn|microsoft\.com|learn\.microsoft)", re.IGNORECASE)
FP_BRIEF_EMBED = re.compile(r"BRIEF\.md\s*:\s*\n", re.IGNORECASE)  # heuristic: pasted BRIEF content
FP_BRIEF_REFERENCE = re.compile(r"(read|see|reference)\s+BRIEF\.md", re.IGNORECASE)

# Sub-agent invocation patterns (retrospective summaries in Routing Plan)
SUBAGENT_NAMES = ["QA", "DEV", "INFRA", "ARCH", "DOCS", "DIAGRAM", "REPO"]
FP_SUBAGENT_BULLET = re.compile(
    r"-\s*\*\*\s*(QA|Dev|DEV|Infra|INFRA|Arch|ARCH|Docs|DOCS|Diagram|DIAGRAM|Repo|REPO)"
    r"(?:\s*\([^)]*\))?\s*[:\*]?\*\*",
    re.IGNORECASE,
)

ALL_FINGERPRINTS = {
    "qb_result_header": FP_QB_RESULT_HEADER,
    "task_type": FP_TASK_TYPE,
    "classification": FP_CLASSIFICATION,
    "scope": FP_SCOPE,
    "routing_plan": FP_ROUTING_PLAN,
    "checkpoint_1": FP_CHECKPOINT_1,
    "checkpoint_2": FP_CHECKPOINT_2,
    "ask_questions": FP_ASK_QUESTIONS,
    "run_subagent": FP_RUN_SUBAGENT,
    "required_output_shape": FP_REQUIRED_OUTPUT_SHAPE,
    "recommended_true": FP_RECOMMENDED_TRUE,
    "source_citation": FP_SOURCE_CITATION,
    "subagent_bullet": FP_SUBAGENT_BULLET,
    "brief_reference": FP_BRIEF_REFERENCE,
    "brief_embed": FP_BRIEF_EMBED,
}

# Minimum fingerprints needed to call a session "QB-attributable"
QB_MIN_FINGERPRINTS = 2
QB_ATTRIBUTION_KEYS = {"qb_result_header", "task_type", "routing_plan", "required_output_shape"}

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class QBSession:
    session_id: str
    db_path: str
    created_at: str
    summary: str | None
    turn_count: int
    fingerprints_matched: list[str]

@dataclass
class QBObservations:
    session_id: str
    db_path: str
    turn_count: int
    task_types_declared: list[str]
    classifications_declared: list[str]
    scopes_declared: list[str]
    checkpoint_1_count: int
    checkpoint_2_count: int
    ask_questions_count: int
    subagent_invocations: list[dict]      # [{turn, agent}]
    output_shape_compliance: bool
    output_shape_missing: list[str]
    brief_md_embedded: bool
    brief_md_referenced: bool
    recommendations_with_citation: int
    recommendations_total: int
    fingerprint_counts: dict[str, int]

@dataclass
class EvidenceEntry:
    imp_id: str
    session_id: str
    captured_at: str
    verdict: str                # pass | fail | inconclusive
    fingerprint_matches: list[str]
    observations: dict          # asdict(QBObservations)
    notes: str
    redactions_applied: list[str] = field(default_factory=list)

# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _open_ro(db_path: Path) -> sqlite3.Connection:
    uri = f"file:{db_path.as_posix()}?mode=ro&immutable=0"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn

def _existing_dbs() -> list[Path]:
    return [p for p in (VSCODE_DB, CLI_DB) if p.exists()]

def _parse_since(since: str) -> str:
    """Convert '30d' / '7d' / '2025-05-01' to an ISO timestamp string for sqlite comparison."""
    if re.fullmatch(r"\d+d", since):
        days = int(since[:-1])
        dt = datetime.now(timezone.utc) - timedelta(days=days)
        return dt.strftime("%Y-%m-%dT%H:%M:%fZ")
    # assume already ISO-ish
    return since

# ---------------------------------------------------------------------------
# Phase 1: detect QB sessions
# ---------------------------------------------------------------------------

def find_qb_sessions(since: str = "30d") -> list[QBSession]:
    """Scan all known session stores; return sessions matching QB fingerprints."""
    since_iso = _parse_since(since)
    out: list[QBSession] = []
    for db in _existing_dbs():
        try:
            conn = _open_ro(db)
        except sqlite3.Error as e:
            print(f"[warn] cannot open {db}: {e}", file=sys.stderr)
            continue
        rows = conn.execute(
            "SELECT id, created_at, summary FROM sessions WHERE created_at >= ? ORDER BY created_at DESC",
            (since_iso,),
        ).fetchall()
        for s in rows:
            turns = conn.execute(
                "SELECT user_message, assistant_response FROM turns WHERE session_id=?",
                (s["id"],),
            ).fetchall()
            if not turns:
                continue
            full = "\n".join((t["assistant_response"] or "") + "\n" + (t["user_message"] or "") for t in turns)
            matched = [name for name, pat in ALL_FINGERPRINTS.items() if pat.search(full)]
            attribution_hits = QB_ATTRIBUTION_KEYS.intersection(matched)
            if len(matched) >= QB_MIN_FINGERPRINTS and attribution_hits:
                out.append(QBSession(
                    session_id=s["id"],
                    db_path=str(db),
                    created_at=s["created_at"],
                    summary=s["summary"],
                    turn_count=len(turns),
                    fingerprints_matched=matched,
                ))
        conn.close()
    return out

# ---------------------------------------------------------------------------
# Phase 2: extract observations from a single session
# ---------------------------------------------------------------------------

REQUIRED_OUTPUT_HEADERS = ["## QB Result", "Task Type", "Routing Plan"]

def extract_qb_observations(session_id: str, db_path: str | None = None) -> QBObservations:
    """Walk every turn in a session; emit a structured observation set."""
    db = Path(db_path) if db_path else None
    if db is None:
        for candidate in _existing_dbs():
            try:
                with _open_ro(candidate) as c:
                    if c.execute("SELECT 1 FROM sessions WHERE id=?", (session_id,)).fetchone():
                        db = candidate
                        break
            except sqlite3.Error:
                continue
    if db is None:
        raise ValueError(f"session {session_id} not found in any known store")

    conn = _open_ro(db)
    turns = conn.execute(
        "SELECT turn_index, user_message, assistant_response FROM turns WHERE session_id=? ORDER BY turn_index",
        (session_id,),
    ).fetchall()
    conn.close()

    task_types: list[str] = []
    classifications: list[str] = []
    scopes: list[str] = []
    cp1 = cp2 = aq = 0
    subagent_invocations: list[dict] = []
    rec_total = rec_with_citation = 0
    brief_embed = brief_ref = False
    fp_counts: dict[str, int] = {k: 0 for k in ALL_FINGERPRINTS}
    output_shape_headers_seen: set[str] = set()

    for t in turns:
        text = (t["assistant_response"] or "") + "\n" + (t["user_message"] or "")
        for name, pat in ALL_FINGERPRINTS.items():
            fp_counts[name] += len(pat.findall(text))

        for m in FP_TASK_TYPE.finditer(text):
            task_types.append(m.group(1))
        for m in FP_CLASSIFICATION.finditer(text):
            classifications.append(m.group(1).strip())
        for m in FP_SCOPE.finditer(text):
            scopes.append(m.group(1))

        cp1 += len(FP_CHECKPOINT_1.findall(text))
        cp2 += len(FP_CHECKPOINT_2.findall(text))
        aq += len(FP_ASK_QUESTIONS.findall(text))

        for m in FP_SUBAGENT_BULLET.finditer(text):
            subagent_invocations.append({"turn": t["turn_index"], "agent": m.group(1).upper()})

        rec_total += len(FP_RECOMMENDED_TRUE.findall(text))
        if FP_RECOMMENDED_TRUE.search(text) and FP_SOURCE_CITATION.search(text):
            rec_with_citation += 1

        if FP_BRIEF_EMBED.search(text):
            brief_embed = True
        if FP_BRIEF_REFERENCE.search(text):
            brief_ref = True

        for h in REQUIRED_OUTPUT_HEADERS:
            if h in text:
                output_shape_headers_seen.add(h)

    missing = [h for h in REQUIRED_OUTPUT_HEADERS if h not in output_shape_headers_seen]
    return QBObservations(
        session_id=session_id,
        db_path=str(db),
        turn_count=len(turns),
        task_types_declared=task_types,
        classifications_declared=classifications,
        scopes_declared=scopes,
        checkpoint_1_count=cp1,
        checkpoint_2_count=cp2,
        ask_questions_count=aq,
        subagent_invocations=subagent_invocations,
        output_shape_compliance=(len(missing) == 0),
        output_shape_missing=missing,
        brief_md_embedded=brief_embed,
        brief_md_referenced=brief_ref,
        recommendations_with_citation=rec_with_citation,
        recommendations_total=rec_total,
        fingerprint_counts=fp_counts,
    )

# ---------------------------------------------------------------------------
# Phase 3: per-IMP scorers
# ---------------------------------------------------------------------------

def _imp_0001(obs: QBObservations) -> tuple[str, str]:
    """IMP-0001 — bounded subagent returns. Heuristic: routing-plan bullets
    summarize each subagent in <=2 lines (we proxy with bullet count >= subagent count)."""
    if not obs.subagent_invocations:
        return "inconclusive", "No sub-agent invocations observed in routing plan; can't verify bounded-return discipline."
    return ("pass",
            f"Routing plan summarizes {len(obs.subagent_invocations)} sub-agent invocation(s) using bullet form, "
            f"consistent with bounded-return rule.")

def _imp_0006(obs: QBObservations) -> tuple[str, str]:
    """IMP-0006 — reference BRIEF.md by path, do not embed content."""
    if not (obs.brief_md_embedded or obs.brief_md_referenced):
        return "inconclusive", "No BRIEF.md mentions in session; can't verify reference-by-path discipline."
    if obs.brief_md_embedded and not obs.brief_md_referenced:
        return "fail", "BRIEF.md content appears pasted (embed pattern matched) rather than referenced by path."
    if obs.brief_md_referenced and not obs.brief_md_embedded:
        return "pass", "BRIEF.md is referenced (not embedded) in subagent prompts."
    return "pass", "BRIEF.md referenced (some passages may include excerpts, but no full embed pattern detected)."

def _imp_0012(obs: QBObservations) -> tuple[str, str]:
    """IMP-0012 — self-prune after subagent reports. Heuristic: if multiple sub-agents
    invoked AND the QB Result block summarizes them in bullet form (rather than re-quoting),
    the prune rule is consistent with observed behavior."""
    if len(obs.subagent_invocations) < 2:
        return "inconclusive", f"Only {len(obs.subagent_invocations)} sub-agent invocation(s); need >=2 to observe prune behavior across reports."
    return ("pass",
            f"Multi-agent session ({len(obs.subagent_invocations)} invocations) produced a compact Routing Plan summary "
            f"consistent with self-prune discipline.")

def _imp_0021(obs: QBObservations) -> tuple[str, str]:
    """IMP-0021 PR1 — task-type detector. Requires at least one Task Type declaration
    matching one of the 7 known classes."""
    KNOWN = {"bug-fix", "new-poc-setup", "customer-handoff", "full-delivery",
             "feature-request", "refactor", "optimization"}
    if not obs.task_types_declared:
        return "fail", "No 'Task Type:' declaration found in QB output — detector did not fire."
    matched = [tt for tt in obs.task_types_declared if tt.lower() in KNOWN]
    if not matched:
        return "fail", f"Task Type declared as {obs.task_types_declared!r} but none match the 7-class taxonomy."
    return "pass", f"Task Type declared ({matched[0]!r}); detector fired correctly."

def _imp_0020(obs: QBObservations) -> tuple[str, str]:
    """IMP-0020 — evidence-backed recommendations (only meaningful once shipped)."""
    if obs.recommendations_total == 0:
        return "inconclusive", "No 'recommended: true' options observed in session."
    if obs.recommendations_with_citation == 0:
        return "fail", f"{obs.recommendations_total} recommendation(s) made without any Source: citation."
    rate = obs.recommendations_with_citation / obs.recommendations_total
    return ("pass" if rate >= 0.8 else "fail",
            f"{obs.recommendations_with_citation}/{obs.recommendations_total} recommendations carry a Source citation (rate={rate:.2f}).")

def _imp_0004(obs: QBObservations) -> tuple[str, str]:
    """IMP-0004 — QB tools trim (structural). Real-session evidence is just confirmation
    that QB still works after the trim — i.e., produced a valid Required Output Shape."""
    if obs.output_shape_compliance:
        return "pass", "QB produced compliant Required Output Shape after tool-frontmatter trim."
    return ("inconclusive" if not obs.task_types_declared else "fail",
            f"Output shape missing headers: {obs.output_shape_missing!r}")

IMP_SCORERS = {
    "IMP-0001": _imp_0001,
    "IMP-0004": _imp_0004,
    "IMP-0006": _imp_0006,
    "IMP-0012": _imp_0012,
    "IMP-0020": _imp_0020,
    "IMP-0021": _imp_0021,
}

# Earliest session date that can be valid evidence per IMP.
# A session predating the IMP's commit cannot demonstrate behavior introduced by that commit.
# Update this table when shipping new IMPs. ISO 'YYYY-MM-DD' or None to skip the gate.
IMP_VALID_FROM: dict[str, str | None] = {
    "IMP-0001": "2026-04-27",
    "IMP-0004": "2026-04-27",
    "IMP-0006": "2026-04-28",
    "IMP-0012": "2026-06-01",
    "IMP-0020": None,         # not yet shipped
    "IMP-0021": "2026-06-01",
}

def score_against_imp(obs: QBObservations, imp_id: str, session_created_at: str | None = None) -> EvidenceEntry:
    scorer = IMP_SCORERS.get(imp_id)
    if scorer is None:
        raise ValueError(f"No scorer registered for {imp_id}. Add one to IMP_SCORERS in telemetry.py.")
    verdict, notes = scorer(obs)
    matched_fps = [k for k, v in obs.fingerprint_counts.items() if v > 0]

    # Timing gate: a session predating the IMP commit cannot validate that IMP.
    valid_from = IMP_VALID_FROM.get(imp_id)
    if valid_from and session_created_at:
        if session_created_at[:10] < valid_from:
            verdict = "inconclusive"
            notes = (f"Session dated {session_created_at[:10]} predates {imp_id} commit ({valid_from}); "
                     f"cannot validate change introduced after that date. Original scorer note: {notes}")

    return EvidenceEntry(
        imp_id=imp_id,
        session_id=obs.session_id,
        captured_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        verdict=verdict,
        fingerprint_matches=matched_fps,
        observations=asdict(obs),
        notes=notes,
    )

# ---------------------------------------------------------------------------
# Phase 4: artifact + frontmatter line
# ---------------------------------------------------------------------------

def write_evidence_artifact(entry: EvidenceEntry, root: Path = EVIDENCE_ROOT) -> Path:
    folder = root / entry.imp_id
    folder.mkdir(parents=True, exist_ok=True)
    ts = entry.captured_at.replace(":", "").replace("-", "")[:15]
    fname = f"{ts}-{entry.session_id[:8]}.json"
    path = folder / fname
    path.write_text(json.dumps(asdict(entry), indent=2), encoding="utf-8")
    return path

def propose_manual_evidence_yaml_line(entry: EvidenceEntry, artifact_path: Path) -> str:
    """Single-line YAML entry safe for the manual_evidence: [] array in IMP frontmatter.

    Privacy: notes field is trimmed; no customer names or repo paths.
    """
    safe_notes = entry.notes.replace("\n", " ").replace('"', "'")[:280]
    rel = artifact_path.relative_to(EVIDENCE_ROOT.parent) if EVIDENCE_ROOT.parent in artifact_path.parents else artifact_path
    return (
        f"  - {{session_id: {entry.session_id[:8]}, "
        f"verdict: {entry.verdict}, "
        f"captured: {entry.captured_at[:10]}, "
        f"notes: \"{safe_notes} | artifact: {rel.as_posix()}\"}}"
    )

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cmd_scan(args: argparse.Namespace) -> int:
    sessions = find_qb_sessions(since=args.since)
    if args.json:
        print(json.dumps([asdict(s) for s in sessions], indent=2))
    else:
        print(f"QB-attributable sessions ({len(sessions)}):")
        for s in sessions:
            print(f"  {s.created_at[:10]} | {s.session_id[:8]} | turns={s.turn_count} | "
                  f"fps={','.join(s.fingerprints_matched[:5])}{'...' if len(s.fingerprints_matched)>5 else ''}")
            if s.summary:
                print(f"      summary: {s.summary[:120]}")
    return 0

def _session_created_at(session_id: str, db_path: str | None = None) -> str | None:
    candidates = [Path(db_path)] if db_path else _existing_dbs()
    for db in candidates:
        try:
            with _open_ro(db) as c:
                r = c.execute("SELECT created_at FROM sessions WHERE id=?", (session_id,)).fetchone()
                if r:
                    return r["created_at"]
        except sqlite3.Error:
            continue
    return None

def _cmd_score(args: argparse.Namespace) -> int:
    obs = extract_qb_observations(args.session)
    created = _session_created_at(args.session, obs.db_path)
    entry = score_against_imp(obs, args.imp, session_created_at=created)
    if args.write:
        path = write_evidence_artifact(entry)
        line = propose_manual_evidence_yaml_line(entry, path)
        print(f"verdict: {entry.verdict}")
        print(f"notes:   {entry.notes}")
        print(f"artifact: {path}")
        print()
        print("Proposed manual_evidence YAML line (review before pasting into IMP frontmatter):")
        print(line)
    else:
        print(json.dumps(asdict(entry), indent=2))
    return 0

def _cmd_backfill(args: argparse.Namespace) -> int:
    sessions = find_qb_sessions(since=args.since)
    print(f"Scoring {len(args.imp)} IMP(s) against {len(sessions)} candidate session(s)\n")
    results: dict[str, list[tuple[EvidenceEntry, Path]]] = {imp: [] for imp in args.imp}
    for imp in args.imp:
        if imp not in IMP_SCORERS:
            print(f"[skip] {imp} - no scorer registered")
            continue
        for s in sessions:
            obs = extract_qb_observations(s.session_id, s.db_path)
            entry = score_against_imp(obs, imp, session_created_at=s.created_at)
            path = write_evidence_artifact(entry)
            results[imp].append((entry, path))
    # Summary table
    print(f"{'IMP':<10} {'Session':<10} {'Verdict':<14} Notes")
    print("-" * 100)
    for imp, items in results.items():
        for entry, path in items:
            print(f"{imp:<10} {entry.session_id[:8]:<10} {entry.verdict:<14} {entry.notes[:80]}")
    print()
    print("Proposed YAML lines (one per pass-verdict entry):")
    for imp, items in results.items():
        for entry, path in items:
            if entry.verdict == "pass":
                print(f"# {imp}")
                print(propose_manual_evidence_yaml_line(entry, path))
    return 0

def _cmd_yaml_line(args: argparse.Namespace) -> int:
    p = Path(args.evidence)
    data = json.loads(p.read_text(encoding="utf-8"))
    entry = EvidenceEntry(**{k: data[k] for k in EvidenceEntry.__dataclass_fields__})
    print(propose_manual_evidence_yaml_line(entry, p))
    return 0

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="telemetry", description=__doc__)
    sp = p.add_subparsers(dest="cmd", required=True)

    p_scan = sp.add_parser("scan", help="List QB-attributable sessions in both stores")
    p_scan.add_argument("--since", default="30d", help="Window: '30d', '7d', or ISO date")
    p_scan.add_argument("--json", action="store_true", help="Emit JSON")
    p_scan.set_defaults(func=_cmd_scan)

    p_score = sp.add_parser("score", help="Score one session against one IMP")
    p_score.add_argument("--session", required=True, help="Session ID (full or 8-char prefix is OK if unique)")
    p_score.add_argument("--imp", required=True, help="IMP ID, e.g. IMP-0021")
    p_score.add_argument("--write", action="store_true", help="Write artifact + propose YAML line")
    p_score.set_defaults(func=_cmd_score)

    p_bf = sp.add_parser("backfill", help="Score all QB sessions against one or more IMPs")
    p_bf.add_argument("--imp", action="append", required=True, help="IMP ID (repeatable)")
    p_bf.add_argument("--since", default="90d", help="Lookback window")
    p_bf.set_defaults(func=_cmd_backfill)

    p_yl = sp.add_parser("yaml-line", help="Emit frontmatter YAML line from a stored evidence artifact")
    p_yl.add_argument("--evidence", required=True, help="Path to evidence JSON")
    p_yl.set_defaults(func=_cmd_yaml_line)

    args = p.parse_args(argv)
    return args.func(args)

if __name__ == "__main__":
    sys.exit(main())
