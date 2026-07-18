---
id: IMP-0012
title: QB self-prunes after reading subagent reports
status: validated
source: review-context-window-2026-04
affects: [QB]
risk: low
created: 2026-04-27
updated: 2026-06-10
commit: f267392
superseded_by: IMP-0026
eval_type: tool_loop
eval_id: imp_0012
eval_seed: 42
baseline_run: baselines/IMP-0012/20260601-172720-cf9eaa5-baseline.json
post_run: baselines/IMP-0012/20260610-142431-56910cd-post.json
manual_evidence:
  - {source: synthetic, verdict: pass, captured: 2026-06-10, notes: "tool_loop post-eval PASS overall_pass_rate 1.00 across 2 scenarios x 8 samples = 16 conclusive observations of the self-prune rule (>= 15 threshold, Wilson 95% CI lower bound >= 0.80). Bumped N_SAMPLES 3->8 to clear the confidence bar. README bar option (b), synthetic eval evidence: after each runSubagent return, QB summarizes into bullets/scratchpad and does not re-quote the original report."}
---

## Problem

After a subagent returns, QB keeps the verbose report resident in context for the rest of the session — even though it only needs the conclusions.

## Proposal

Add an explicit self-prune rule to QB:

> After reading a subagent report, immediately summarize it into 3–5 bullets in your next turn (or in the scratchpad — see IMP-0002). Treat the original report as discardable; do not re-quote it in subsequent turns.

## Acceptance criteria

- [x] Self-prune rule documented in QB (likely the same subsection as IMP-0001's bounded-return rule) *(commit `f267392`, Rule 7 sub-section)*
- [x] Real session shows QB referencing its own summary, not re-quoting the subagent's full report *(satisfied via README option (b) synthetic eval: tool_loop post-eval, 16/16 observations PASS — QB summarizes each subagent return into bullets/scratchpad and never re-quotes >100 contiguous chars of the original report)*

## Validation plan

Inspect a multi-iteration bug-fix session. Confirm QB doesn't re-paste prior QA reports when invoking later agents.

## Notes

**2026-06-10 — validated (README bar option b, synthetic eval evidence).** Bumped `N_SAMPLES` 3→8 (`imp_0012.py`) to clear the ≥15-observation confidence bar, then re-captured (`20260610-142431-56910cd-post.json`): **overall_pass_rate 1.00 across 2 scenarios × 8 samples = 16 conclusive observations** of the self-prune rule — QB summarizes each runSubagent return into bullets/scratchpad and does not re-quote the original report. Earlier samples landed in the inconclusive path; with 8 samples the runtime rule fires reliably. Compare verdict `pass`, no regressions: quality 0.00→1.00; the +95% wall_time / +175% cost are **not** regressions — they are the expected effect of running 8 samples vs the baseline's 3 (harness now demotes total-based exec deltas to advisory when `n_samples` differs, since totals aren't comparable across sample counts; per-observation time is unchanged).

**Implemented 2026-06-01** in commit `f267392`. Eval results:

- **Baseline (vs current QB):** 0/2 scenarios PASS, overall_pass_rate=0.00 — rule was not yet documented in QB.
- **Post (vs QB with Self-Prune subsection):** 2/2 scenarios PASS, overall_pass_rate=1.00.

**Caveat (matches IMP-0001 initial-pass pattern):** Both post-eval samples landed in the INCONCLUSIVE path — QB did not actually invoke a subagent within the 8-turn budget under the surrogate harness, so the "summarize after report" rule was not exercised at runtime. The evaluator treats inconclusive as PASS (no runtime violation) but provides only weak evidence of behavior change. Pre-validation TODO: bump `N_SAMPLES` (currently 3) and `MAX_TURNS` (currently 8) — or add more direct scenarios — to drive runSubagent calls reliably and demonstrate real summarization, same path IMP-0001 took (final N=5, MAX_TURNS=8, 80/80 runtime compliance).

**Manual-evidence status (2026-06-02 telemetry backfill, IMP-0022):**

- All 4 currently-captured QB sessions are either pre-commit (cfeb7744 / 6dca5610 / 057d35cf) or zero-subagent (50ecd17b).
- **Next real bug-fix or new-poc-setup session with multiple sub-agent invocations** should be scored against IMP-0012 — run `python -m runner.telemetry score --session <sid> --imp IMP-0012 --write` from `~/.copilot/evals/`. The scorer needs ≥2 sub-agent invocations to make a verdict.
- Until then, this IMP stays at `implemented` per the validated bar.

Per IMP-0015 `validated` bar, this IMP is `implemented` not `validated` because: (a) post-eval is inconclusive (no runtime observations), (b) no real-session manual_evidence captured yet. Promote to `validated` after a real VS Code session shows QB self-pruning OR after a tighter eval scenario demonstrates summarization at runtime (N≥15 conclusive observations, Wilson lower ≥0.80).

Pairs tightly with IMP-0001 and IMP-0002 — implement together as one "context discipline" patch.


**2026-06-08 — pipeline-eval note.** Palette/tool-availability coverage for QB is now enforced globally by the Tier-1 synthetic-pipeline CI gate (`run-all-imps` via `imp_0024`/`tool_palette`), so this behavioral IMP needs no per-IMP palette check.

**2026-06-08 — evidence backfill (telemetry).** Ran `telemetry backfill` over 5 QB sessions (120d). All inconclusive: 3 predate the IMP commit (timing gate); the 2 post-commit sessions had 0 sub-agent invocations, so prune-across-reports behavior couldn't be observed. Stays `implemented` — needs a real multi-subagent QB session (>=2 dispatches).

**2026-06-08 — synthetic scorer-validation.** `evals/scripts/synthesize_qb_sessions.py` builds realistic synthetic QB transcripts and confirms this IMP's telemetry scorer returns `pass` (the pass-path had never fired on a real session). Synthetic = scorer/regression fixture only; per the `validated` bar (IMP-0015) a real session is still required to graduate.
