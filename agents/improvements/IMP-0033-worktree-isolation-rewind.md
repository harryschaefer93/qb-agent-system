---
id: IMP-0033
title: Git worktree isolation + phase checkpoint commits for fan-out and rewind
status: implemented
source: review-2026-06-10
affects: [QB, REPO, DEV]
risk: medium
created: 2026-06-10
updated: 2026-07-13
commit: e768326
eval_type: manual
skip_validation: false
eval_id: null
eval_seed: 42
baseline_run: null
post_run: null
manual_evidence: []
---

## Problem

DEV fan-out runs parallel tracks **in one shared working tree**. Collision prevention is prompt-only ("Do NOT touch files outside your owned paths"), and the merge gate is `git status` + a build — it detects damage but can't attribute it to a track or revert it cleanly. When an iteration hits the 2-cycle limit, the escalation hands the user a working tree mid-surgery to untangle by hand.

Gold-standard harnesses make undo mechanical: worktree/branch isolation per parallel actor, snapshots/checkpoints per phase, rollback as a primitive (Claude Code worktrees + /rewind, Devin snapshots, Codex sandboxes). The key strategic point: **agents that can be cheaply undone can be trusted with more autonomy** — this IMP is what makes IMP-0028's relaxed gating safe.

## Proposal

REPO-owned git mechanics (REPO already owns all git operations per QB's operating rules):

1. **Fan-out isolation:** a `fanout-setup` script creates one worktree + branch per declared track (`track/<name>` off the integration branch). Each DEV invocation gets its worktree path as its working root — "owned paths" becomes physically enforced, not promised.
2. **Merge gate becomes a real merge:** tracks merge sequentially into an integration branch. Conflicts surface as actual conflict hunks, bounced to the *responsible track* with the hunks in the prompt (replacing today's "git status + hope"). Build runs on the merged result as before.
3. **Phase checkpoint commits:** at every pipeline seam (the IMP-0003 trigger list), commit on the working branch with a `checkpoint:` prefix. Rewind = `git reset` to the last good checkpoint; a failed 2-cycle iteration = discard the branch — the escalation message offers "roll back to checkpoint N" as a one-step option instead of manual surgery.
4. **History hygiene:** REPO squashes `checkpoint:` commits before the final push — customer-visible history is unchanged. Worktrees are local and cleaned up at pipeline end.
5. **Serial tasks** get the checkpoint commits only (no worktrees) — rewind capability without the ceremony.

## Acceptance criteria

- [ ] `fanout-setup` / `fanout-merge` / `checkpoint` / `rewind` scripts exist under REPO's ownership with usage docs
- [ ] One fan-out run (real or rehearsed on a sample repo) with 2 tracks in separate worktrees; a deliberately seeded conflict surfaces as merge-conflict hunks bounced to the right track
- [ ] Failed-iteration rollback demonstrated: discard branch, working tree clean, run-state records the rewind
- [ ] No `checkpoint:` commits appear in pushed history (squash verified)
- [ ] QB.agent.md Merge Gate + DEV Fan-Out sections updated to reference the scripts; Iteration Protocol escalation offers rollback

## Validation plan

Deterministic rehearsal on a scratch repo first (scripts are plain git — testable without any model). Then one real multi-track `new-poc-setup`. Watch for Windows-specific worktree friction (path length, file locks from running dev servers) — note mitigations in the scripts.

## Eval Plan

- **Type:** manual (git mechanics verifiable by deterministic script tests + inspection; the QB-prompt deltas are minor)
- **What we measure:** scripted rehearsal covers setup/conflict/rollback/squash paths; prompt sections reference the scripts
- **Pass criteria:** all acceptance checkboxes
- **Known limits:** whether QB *invokes* the scripts at the right seams is production behavior — one real fan-out session required before `validated`.

## Results

**Implemented 2026-07-13** (Wave 3). `scripts/git/` (REPO-owned): `fanout-setup.ps1`
(integration branch + `<repo>.tracks\<name>` worktrees on `track/<name>`, refuses dirty tree,
sets `core.longpaths`), `fanout-merge.ps1` (sequential `--no-ff`; conflict aborts + returns
hunks attributed to the responsible track), `checkpoint.ps1` (seam commits; hooks NOT skipped),
`rewind.ps1` (checkpoint hard-reset / `-DiscardTrack`; destructive → askQuestions-gated),
`squash-checkpoints.ps1` (verifies zero `checkpoint:` commits remain) + README. Deterministic
rehearsal: `evals/pipeline/tests/test_worktree_scripts.py` — 6 tests green (clean 2-track merge,
seeded conflict attributed to the right track with clean abort, checkpoint+rewind, discard,
squash-verify, dirty-tree refusal). QB DEV Fan-Out/Merge Gate/Iteration Protocol updated in
place; DEV worktree hard rule; REPO "Fan-out & Rewind Mechanics" section; run-state gains
`checkpoint_shas[]`.

Validation pending: one real 2-track `new-poc-setup` (QB invokes the scripts at the right
seams; no `checkpoint:` commits in pushed history).

## Notes

- Source: 2026-06-10 gap analysis, gap #3.
- Enabler for IMP-0028 (cheap undo justifies relaxed gates). Complements IMP-0026 (run-state records checkpoint SHAs → rewind targets).
- Scope note: this is *not* the rejected IMP-0010 — no agent outputs move into the repo; this is purely git topology for code changes the agents were already making.
