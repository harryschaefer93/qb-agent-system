# Eval-Driven IMP System — Build Plan

> **Why this file exists:** We are wiring the agent improvement (IMP) lifecycle in `~/.copilot/` together with the co-located eval harness in `~/.copilot/evals/` so that every IMP ships with a measurable before/after. This file is the canonical plan. **Future sessions: start here when working on IMPs, evals, or `/Implement-Improvement`.**

**Status:** Implemented. Function-calling support landed in evals commit `3589050`; the multi-turn **tool execution loop** (`evaluators/tool_loop.py`) and **IMP-eval integration** (`runner/imp_runner.py` + `run-imp` CLI) are built and in use. As of 2026-06-08 this also includes the **synthetic pipeline eval** (Tier 1, deterministic) + **Tier-2 surrogate pipeline** (recursive `runSubagent`), a **generic `tool_palette` evaluator**, and a **CI gate** (`run-all-imps` + `.github/workflows/imp-ci-gate.yml`) that blocks structural regressions on every push. See §3d.

**Owner:** Solo (Harry). 10-day pragmatic timeline — keep overhead low.

---

## 0. Two-runtime reality (read this first)

This system has **two distinct runtimes** and most design decisions follow from the gap between them.

| | Production runtime | Eval runtime |
|---|---|---|
| **Where agents actually run** | VS Code + GitHub Copilot Chat | Azure AI Foundry (chat completions API) |
| **Models available** | `claude-opus-4.6-1m`, `gpt-5.x`, `gemini-2.5-pro`, etc. (Copilot routes; we don't pick directly) | Whatever Foundry exposes — currently `gpt-5.4` is the practical surrogate (see §0a) |
| **Tool surface** | Real VS Code tools (file system, terminal, browser, MCP servers, deferred-tool loader) | Mocked tools via `datasets/{agent}/mocks.yaml` (Pattern C) |
| **Context loading** | Real workspace, real `.copilot/` skill/instruction injection | Synthetic prompt assembly that mimics injection |
| **Determinism** | None — Copilot internals + tool latency + user steering | Pinnable: temperature=0, fixed seed, fixed mocks |

**What evals can tell us (high confidence):**
- Prompt/frontmatter shape changes (`structural`).
- Tool-selection logic and sequencing on a given model (`tool_loop`).
- Subagent routing decisions (`subagent_routing` — see §3).
- Output structure on captured prompts (`behavioral`).

**What evals cannot tell us (must validate manually):**
- How `claude-opus-4.6-1m` specifically will behave — the Foundry surrogate is a *directional* signal, not a faithful one. A green eval ≠ green in Copilot.
- Real tool-call success/failure (mocks always succeed unless we encode failure rules).
- User-experience qualities (response cadence, conversational tone, follow-up handling).

**Implication for every IMP:** non-`structural` evals are *necessary but not sufficient*. Validation always ends with at least one real Copilot session captured under `session-state/` and linked from the IMP's Results table.

### 0a. Surrogate model selection (not arbitrary, but not deeply benchmarked)

`gpt-5.4` is the **current default** because it has reliable function-calling, low cost, and is the model the harness landed on in evals commit `3589050`. It was not picked through a head-to-head bake-off.

**Other Foundry options worth considering, by use case:**

| Surrogate | When to pick it | Trade-off |
|---|---|---|
| `gpt-5.4` (default) | Most `tool_loop`, `behavioral`, `subagent_routing` evals | Cheap, deterministic with seed; no Anthropic/Google fidelity |
| `gpt-5-pro` / `gpt-5.x-high` | High-stakes `quality` evals or rubric calibration | Slower + more expensive; closer to opus on reasoning depth |
| `gemini-2.5-pro` (if Foundry exposes it) | Cross-model sanity check — run alongside gpt-5.4 to detect prompt overfitting | Doubles cost; only worth it for IMPs touching prompt structure |
| `o4-mini` / fast small model | Structural smoke tests, regression sweeps over many IMPs | Lower fidelity for tool-loop reasoning; fine for shape checks |

**Selection rules:**
1. `structural` evals: model-agnostic — don't call a model at all.
2. Default to `gpt-5.4` for anything else unless the IMP explicitly targets behavior the default model masks.
3. For any IMP affecting prompt structure visible to multiple model families (e.g. core agent frontmatter), run the eval on **both** `gpt-5.4` *and* one cross-family model (gemini if available) and require both to pass. Record both in the snapshot.
4. Record `model` + `model_provider` in every snapshot — enables comparing across surrogates later.
5. Revisit the default when Foundry adds an Anthropic model or we get a direct Anthropic key.

---

## 1. The problem we're solving

1. IMPs ship without proof they helped (or hurt) — `validated` status is hand-wavy.
2. The behavioral eval scored post-IMP-0004 QB at **26%** which looked like a regression but was actually a harness limitation (single-turn, no tool execution).
3. Production and surrogate models differ. We use Foundry surrogates plus exact runtime confidence
   and explicit provenance; real-session evidence is mandatory only for irreducibly manual
   criteria and otherwise remains opportunistic corroboration.
4. There is no glue between `agents/improvements/IMP-XXXX.md` files and `~/.copilot/evals/` runs.

## 2. Target lifecycle (6 phases)

```
Discovery -> Triage+EvalScoping -> Baseline -> Implement -> Post-EvalRun -> Validate+Decide
```

| Phase | Trigger | Output |
|---|---|---|
| Discovery | retro / ad-hoc / customer | `IMP-XXXX.md` `status: proposed` |
| Triage + Eval Scoping | manual review | `status: accepted`, `eval_type` + `eval_id` populated in frontmatter |
| Baseline | `/Implement-Improvement IMP-XXXX` step 1 | `baselines/IMP-XXXX-pre.json` committed in evals repo |
| Implement | the actual code/prompt change | commit SHA in IMP frontmatter |
| Post-Eval Run | auto, after implement | `baselines/IMP-XXXX-post.json` |
| Validate + Decide | `/Validate-IMP IMP-XXXX` | `status: validated` or `reverted`, metrics table appended to IMP file |

## 3. Eval types (pick one per IMP)

| `eval_type` | When to use | Model required | Cost |
|---|---|---|---|
| `structural` | Prompt-edit IMPs (frontmatter shape, file size, presence/absence of strings) | none | free |
| `tool_loop` | IMPs that change tool selection, sequencing, or subagent fan-out | gpt-5.4 (Foundry) via mocked tools | cheap |
| `subagent_routing` | IMPs that change which subagent QB picks per scenario (sub-type of tool_loop, confusion-matrix metric) | gpt-5.4 via mocked `runSubagent` | cheap |
| `behavioral` | IMPs that change response shape on captured prompts | gpt-5.4 single-turn | cheap |
| `quality` | IMPs that change output quality for a customer-style task | gpt-5.4 + LLM judge (with rubric + judge-the-judge sanity, see §3a) | medium |
| `rubric` | IMPs scored on weighted, multi-criterion output quality (e.g. tone, structure, correctness). Requires hand-graded calibration set. | gpt-5.4 (Foundry) as judge | medium |
| `execution_metrics` | IMPs that are pure cost/speed optimisations with no behavioural change (e.g. prompt trim, model swap). | optional — runs scenario only if `eval_id` set | low |
| `composite` | IMPs that need multiple eval types together (e.g. tool_loop + rubric + cost gating). | inherited from sub-evals | inherited |
| `manual` | Criteria that require genuine user judgment, elapsed operation, physical interaction, picker availability, or production-only observation | n/a | n/a |

Default is `structural` because most IMPs are prompt edits. **IMP-0004 is the reference example**, already passing 4/4.

### 3d. Synthetic pipeline evals — Tier 1 vs Tier 2 (added 2026-06-08)

Tool-palette / pipeline IMPs (e.g. IMP-0024 QB trim, IMP-0025 INFRA/QA least-privilege) are validated by a **synthetic pipeline harness** so we don't depend on slow live Copilot sessions. Two tiers, distinguished by **whether a model runs**:

| | **Tier 1 — deterministic** | **Tier 2 — surrogate** |
|---|---|---|
| Model? | No | Yes (gpt-5.4 Foundry) |
| Driven by | scripted tool-call sequences | the model's real decisions |
| Speed / cost | seconds / free | minutes / real tokens |
| Where | **CI gate, every push** | manual, per-IMP |
| Answers | "Are the tool palettes correct & sufficient for the intended pipeline?" | "How does QB actually route/sequence end-to-end?" |
| Code | `evaluators/pipeline.py` | `evaluators/pipeline_surrogate.py` |

**Tier 1 building blocks** (`evaluators/pipeline.py`):
- `load_palette()` — each agent's granted tools parsed from its frontmatter `tools:` line (single source of truth).
- `CONTRACTS` — canonical per-agent role spec: required tools + forbidden families/tools. Add an entry to cover a new agent.
- `build_pipeline_trace()` — recursive `runSubagent` dispatch producing a QB→ARCH/DEV/INFRA/QA/… trace.
- `generate_scenarios()` — composes 7 task-type pipelines from `TASK_DISPATCH` (the IMP-0021 taxonomy: bug-fix, new-poc-setup, customer-handoff, full-delivery, feature-request, refactor, optimization).
- `check_all_scenarios_tool_availability()` — asserts no agent reaches for a tool outside its palette in any scenario.
- `check_scenario_taxonomy_sync()` — guards that the generator stays in sync with QB's documented task-types.

**Generic evaluator:** any tool-palette IMP sets `eval_type: structural`, `eval_id: tool_palette`, `affects: [<AGENTS>]` → `evaluators/custom/tool_palette.py` runs the per-agent contract + all-scenario pipeline checks with **no bespoke Python**. `imp_0024.py`/`imp_0025.py` are reference implementations.

**Tier 2** (`evaluators/pipeline_surrogate.py`): opt-in via `run_tool_loop(subagent_dispatch=...)` (default `None` = unchanged single-agent behavior). When QB calls `runSubagent`, a child loop actually runs for the named subagent (its dataset tools.json if present, else tools synthesized from its palette). Driven via `python -m runner.cli run-pipeline "<prompt>"`. Tier-2 may be a qualifying targeted evidence gate when it observes the same rule with explicit surrogate provenance and the runtime confidence threshold. A later real session remains valuable corroboration.

**Structural fleet gate:** `python -m runner.cli run-all-imps` runs every active
(implemented/validated, non-superseded) `structural` IMP and exits non-zero on any red; skips
rejected/superseded/manual/non-structural. It guards prompt/file structure only and never proves a
non-structural behavior. Graduation uses the separate **targeted evidence gate** for that IMP.

### 3a. Determinism + measurement contract (applies to every non-structural eval)

Every snapshot JSON MUST include the following fields so before/after diffs are meaningful:

```yaml
model: gpt-5.4              # or whatever Foundry surrogate was used
temperature: 0
top_p: 1
seed: 42                    # fixed per IMP, recorded in frontmatter
n_samples: 3                # run each scenario 3x; report mean + stddev
cost:
  input_tokens: <int>
  output_tokens: <int>
  wall_time_ms: <int>
trajectory:                 # required for tool_loop / subagent_routing
  tool_call_count: <int>
  tool_call_sequence: [tool_a, tool_b, ...]
  redundant_call_rate: <float>
  max_turns_hit: <bool>
```

Runtime assertions normalize to `{passed, conclusive, detail}`. Explicit `conclusive` wins;
legacy details beginning `INCONCLUSIVE:` are non-conclusive; reported violations are conclusive.
`tool_loop`, `subagent_routing`, and `behavioral` require at least 15 conclusive observations,
zero conclusive failures, Wilson 95% lower bound >= 0.80, and per-scenario coverage: every
declared scenario has at least one conclusive observation and zero conclusive failures. Exact
math matters: 15/15 is below 0.80; 16/16 passes. Inconclusive observations are neither failures
nor passes, and an entirely inconclusive scenario blocks pooled confidence. Runtime snapshots
persist `metrics.declared_scenario_ids`; graduation imports the declared evaluator's
`get_scenarios()` and rejects missing, unknown, or duplicate IDs before confidence aggregation.
Standalone `execution_metrics` graduation requires a committed declared baseline and an exact
passing comparison against the committed post snapshot.

Canonical evidence lives in `validation_evidence` with source
`deterministic | synthetic | surrogate | real_session | inspection`. `implementation_commit` is
always the current IMP frontmatter `commit`; `evaluated_commit` is only the selected snapshot
`meta.commit_sha`; `artifact_commit` for snapshot-backed proof is the later commit containing
that snapshot. Evaluator/dataset/
subject hashes are included when applicable.
`artifact_commit` is the later commit that first contains the exact committed artifact bytes;
graduation requires evaluated → artifact → current HEAD ancestry and unchanged artifact bytes at
HEAD. Evaluator/dataset/subject hashes remain bound to `evaluated_commit`. Raw typed
`real_session` artifacts stay gitignored/untracked and do not use `artifact_commit`. Legacy real-session
`manual_evidence` remains readable and valid; do not rewrite historical IMPs only to migrate.
Use `python -m runner.cli graduation-check IMP-NNNN` for the mechanical four-bar, ancestry,
staleness, and supersession decision.

After the implementation commit, capture the snapshot. Commit declared baseline/post snapshots,
`post_run`, CHANGELOG SHA bookkeeping, and any typed synthetic/surrogate/deterministic/inspection
artifact while the IMP remains `implemented`; that commit becomes `artifact_commit`. Then add the
typed evidence record in a separate bookkeeping commit referencing that already-known SHA. Never
claim evidence can know the SHA of the same commit that creates it. Run `graduation-check` on the
clean resulting HEAD; all committed inputs must match HEAD. Flip to `validated` only in a later validation
commit after PASS, then rerun the gate on the committed status. If that post-status check fails,
immediately commit a corrective return to `implemented` or `needs-review`; never claim validated
on dirty state. The IMP and CHANGELOG files themselves must be Git-tracked and byte-identical to
HEAD for both checks. Raw legacy/real-session artifacts remain allowed in gitignored evidence storage.

Behavioral IMP adapters use the custom evaluator convention
`get_scenarios() -> list[{id, prompt}]`, optional `N_SAMPLES`, and
`check_<scenario_id>(response, scenario)` or `check_scenario(response, scenario)`. `run-imp`
generates single-turn Foundry responses and writes the authoritative post snapshot with the same
confidence/per-sample contract as other runtime types. `run-personal` remains a broader
personal-suite regression gate and does not replace the IMP post snapshot for graduation.

**Regression rule:** a metric counts as regressed only if `delta_mean > 2 * stddev(baseline_samples)`. Single-sample diffs are advisory, not gating.

**Negative cases required:** every `tool_loop` / `subagent_routing` dataset must include ≥1 scenario where the correct behavior is *refusing* to call a tool / *not* spawning a subagent. Otherwise an IMP that overfits toward "always fan out" passes everything.

**Quality rubric requirements:** any `quality` eval ships with `evaluators/rubrics/imp_XXXX.md` containing a 1–5 scale, explicit pass criteria per score, and 5 hand-graded calibration examples the LLM judge must agree with at ≥80% before its scores are trusted.

### 3b. Rubric eval contract

`rubric` evals score outputs against a markdown rubric using an LLM judge. Builds on the §3a contract; adds these requirements:

**Required IMP frontmatter:**
- `rubric_path: evaluators/rubrics/imp_XXXX.md` — the rubric file
- `calibration_path: evaluators/rubrics/imp_XXXX.calibration.jsonl` — 5+ hand-graded examples
- `calibration_min_agreement: 0.80` — snapshot rejected if judge agrees with humans on fewer than this fraction of examples (full-criterion agreement only — judge off-by-1 on any criterion = disagreement)

**Rubric markdown format** (parsed by `evaluators.rubric.load_rubric()`, template at `evals/evaluators/rubrics/_template.md`):
- Per criterion: `## Criterion: <name> (weight: <0.0-1.0>)`, one-line description, `### Score Definitions` block with all 5 levels, optional `### Examples` block
- All weights MUST sum to 1.0 (±0.001)
- Every criterion MUST have score definitions for {1,2,3,4,5}

**Snapshot metrics shape:**

```yaml
metrics:
  weighted_score: 4.20            # 1-5 scale; mean across scenarios
  pass_rate: 0.83                 # fraction of scenarios where rubric.passed
  all_passed: false               # all scenarios + calibration passed
  calibration_agreement: 0.84     # fraction of calibration examples where judge fully agreed
  calibration_passed: true        # agreement >= calibration_min_agreement
  per_criterion_means:
    correctness: 4.5
    tone: 4.0
    structure: 4.0
```

**Calibration gate:** if `calibration_passed: false`, the snapshot's `raw_results` lists per-example expected vs actual scores so the rubric author can iterate. Do NOT promote a rubric to `validated` while the gate fails.

**Determinism:** judge calls use `temperature=0` and `seed=42` per §3a. Calibration is rerun on every snapshot capture so judge drift across model updates is caught.

### 3c. Composite eval contract

`composite` evals combine multiple sub-evaluators with weights and per-sub `must_pass` flags. Used when an IMP touches behaviour, output quality, AND cost in the same change.

**Required IMP frontmatter:**

```yaml
eval_type: composite
sub_evals:
  - eval_type: tool_loop
    eval_id: imp_0014_loop
    weight: 0.6
    must_pass: true            # failure forces composite verdict to fail
  - eval_type: rubric
    eval_id: imp_0014
    rubric_path: evaluators/rubrics/imp_0014.md
    weight: 0.3
    must_pass: true
  - eval_type: execution_metrics
    weight: 0.1
    must_pass: false           # advisory contribution only
composite_pass_threshold: 0.7  # weighted score must be >= this for verdict=pass
```

**Constraints:**
- All sub_eval weights MUST sum to 1.0 (±0.001) — `parse_composite_spec()` raises ValueError otherwise
- Sub-eval `eval_type` must be one of the registered types in `evals/evaluators/__init__.py`
- `must_pass: true` sub-eval failures zero out their contribution AND force composite verdict to `fail`

**Snapshot shape:**
- `metrics`: `{weighted_score, verdict, sub_verdicts}` from `runner.composite.to_snapshot_dict()`
- `raw_results`: empty (sub-detail lives in `sub_snapshots`)
- `sub_snapshots`: `{eval_type:eval_id: {meta, metrics, raw_results}}` — each sub-eval's full snapshot embedded inline for full provenance

**Verdict roll-up rules:**
- Any `must_pass: true` sub-eval that failed → `fail`
- Else if `weighted_score >= composite_pass_threshold` → `pass`
- Else → `partial`

**Compare semantics:** `compare_composites()` flags regression if post weighted_score < pre weighted_score OR if pre verdict was `pass` and post verdict is `fail`. Per-sub-eval drill-down is rendered in `evals run-imp ... --compare` as a tree.

### 3d. Execution metrics eval contract

`execution_metrics` is BOTH a standalone `eval_type` AND a piece of metadata captured for every non-`manual` snapshot. Tokens, wall_time_ms, and cost_usd are first-class everywhere.

**Always-on capture** (applies to every eval_type):
- `meta.cost = {input_tokens, output_tokens, wall_time_ms, cost_usd, pricing_source}`
- `cost_usd` is computed from `config.yaml::pricing.deployments[<deployment>]` × token counts
- `pricing_source` records the config version (e.g. `"config.yaml@v1"`) so old snapshots remain interpretable across price updates
- Structural evals capture eval-harness wall_time (no model call); cost_usd is 0.0

**Standalone `eval_type: execution_metrics`** — for IMPs that are pure cost/speed optimisations:
- If `eval_id` is set, runs ONE scenario from the evaluator at `max_turns=2` purely to measure cost. Behavioural pass is not asserted at capture time.
- If `eval_id` is null, captures harness-only wall_time (no model call).
- Verdict gating happens entirely in `--compare` via `compare_exec_metrics()`.

**Default thresholds** (from `config.yaml::execution_metrics`, IMP-overridable via `thresholds: {...}` in frontmatter):

```yaml
speed_regression_pct: 25      # wall_time delta > 25% => severity=fail
cost_regression_pct: null     # null => warn-only (advisory; user prioritises quality + speed over cost)
wall_time_max_ms: 60000       # absolute cap; severity=fail if exceeded
token_regression_pct: 30      # input+output growth > 30% => severity=warn
```

**Severity → verdict mapping in `compare_snapshots()`:**
- Any `severity: fail` in execution_metrics regressions → composite verdict becomes `REGRESSION`
- `severity: warn` adds a yellow ⚠ line under the three-pillar summary but does NOT change verdict
- `severity: info` is silent

**Three-pillar render in `--compare`:**

```
Quality:  ✓ pass_rate 0.95 -> 0.98 (+0.03)
Speed:    ✗ wall_time 4200ms -> 5800ms (+38%)  REGRESSION (>25% threshold)
Cost:     ⚠ cost_usd $0.0042 -> $0.0061 (+45%)  ADVISORY
```

**Known noise issue:** for sub-second wall_time values (e.g. structural evals at 5-20ms), the percentage threshold trips on absolute noise. Consider raising `speed_regression_pct` for `eval_type: structural` IMPs or adding an absolute-floor gate in a future IMP.

---

## 4. Build plan — ordered phases

### Phase A — Tool execution loop (`tool_loop.py`) — ~1.5 hr

**Path:** `evals/` (in this repo)

Build a Pattern C (mock tool runtime) loop so gpt-5.4 can complete multi-turn tool sequences.

**New files:**
- `evaluators/tool_loop.py`
- `datasets/qb/mocks.yaml` (per-agent mock config)

**Dataclass shape (tool_loop.py):**

```python
@dataclass
class LoopConfig:
    max_turns: int = 6
    stop_on: list[str] = field(default_factory=lambda: ["final_answer"])  # tool names that end the loop
    on_unmocked: Literal["error", "echo", "skip"] = "echo"

@dataclass
class ToolMock:
    name: str
    strategy: Literal["static", "conditional", "echo"]
    response: Any = None                       # for static
    rules: list["MockRule"] = field(default_factory=list)  # for conditional

@dataclass
class MockRule:
    when: dict[str, Any]   # arg-match: {"path": "BRIEF.md"}
    then: Any              # tool result to return

@dataclass
class LoopTrace:
    turns: list[dict]      # {role, content, tool_calls, tool_results}
    stopped_reason: str    # "final_answer" | "max_turns" | "error"
    tool_call_sequence: list[str]
```

**`mocks.yaml` schema (datasets/qb/mocks.yaml):**

```yaml
defaults:
  on_unmocked: echo
mocks:
  - name: fileSearch
    strategy: conditional
    rules:
      - when: { query: "BRIEF.md" }
        then: { files: ["BRIEF.md"] }
      - when: { query: "*" }
        then: { files: [] }
  - name: readFile
    strategy: static
    response: "stubbed file contents"
  - name: askQuestions
    strategy: static
    response: { answers: ["yes", "proceed"] }
  - name: runSubagent
    strategy: echo   # returns {"agent": <name>, "result": "<mock subagent output>"}
```

**Loop algorithm:**
1. Send messages + tools to Foundry chat completions.
2. If response has `tool_calls`: resolve each via `mocks.yaml`, append tool results, recurse.
3. Stop when: model emits final assistant message with no tool calls, OR `max_turns` hit, OR a `stop_on` tool fires.
4. Return `LoopTrace`.

### Phase B — `run-imp` CLI command — ~1 hr

**Path:** `evals/` (in this repo)  
**File:** `runner/cli.py`

Add commands:

```bash
evals run-imp IMP-0004 --baseline       # snapshot pre-state -> baselines/IMP-0004-pre.json
evals run-imp IMP-0004 --post           # snapshot post-state -> baselines/IMP-0004-post.json
evals run-imp IMP-0004 --compare        # diff pre vs post, exit non-zero on regression
evals run-imp IMP-0004 --full           # baseline + (caller implements) + post + compare
```

**New directory:** `evals/baselines/IMP-XXXX/{timestamp}-{commit_sha}.json` (rolling history, not single overwrite).

Each snapshot contains the full §3a contract: `eval_type`, `eval_id`, `commit_sha`, `model`, `temperature`, `seed`, `n_samples`, `metrics: {mean, stddev, per_sample}`, `cost: {...}`, `trajectory: {...}`, `raw_results: {...}`, `timestamp`.

`--compare` diffs against the most recent **pre-IMP** snapshot, not a pinned file — this catches drift unrelated to the IMP (model updates, mock changes).

### Phase C — Update IMP `_template.md` — ~15 min

**File:** `~/.copilot/agents/improvements/_template.md`

Add to frontmatter:

```yaml
eval_type: structural | tool_loop | behavioral | quality | manual
eval_id: <slug matching evaluators/custom/imp_XXXX.py or null>
baseline_run: <path to baselines/IMP-XXXX-pre.json or null>
post_run: <path to baselines/IMP-XXXX-post.json or null>
```

Add body section:

```markdown
## Eval Plan

- **Type:** <eval_type>
- **What we measure:** <metric list>
- **Pass criteria:** <thresholds>
- **Known limits:** <e.g. surrogate model is gpt-5.4 not opus>

## Results

| Metric | Baseline | Post | Delta | Pass? |
|---|---|---|---|---|
| ... | ... | ... | ... | ... |
```

### Phase D — Update `/Implement-Improvement` prompt — ~15 min — **DONE 2026-04-28**

**File:** `~/.copilot/prompts/implement-improvement.prompt.md` (and `agent-status.prompt.md`)

Add steps:
1. **Pre-flight gate:** if `eval_type != manual` and `baseline_run` is null → run `evals run-imp <ID> --baseline` first, commit, update frontmatter, then proceed.
2. After implementation commit → run `evals run-imp <ID> --post`.
3. Append the results table, select `post_run`, and commit the snapshot plus CHANGELOG SHA while
   status remains `implemented`; capture that commit as `artifact_commit`.
4. Add typed evidence in a later bookkeeping commit referencing the known `artifact_commit`.
   If regression → mark `status: needs-review` instead of `implemented`.

**Shipped:** evaluator-gate guard for `eval_id: null` (redirects to `/Create-IMP-Eval`); reordered so commit (Step 6) happens before post-eval (Step 6.5) so snapshots tag the actual IMP commit; results-append now includes Cost delta line + real-session evidence placeholder for non-structural evals; `agent-status` reads `post_run` JSON to render Last Δ + Verdict columns; Eval Coverage now treats `manual` as covered; new "Regressions Outstanding" subsection.

### Phase E — New `/Create-IMP-Eval` prompt — ~30 min

**New file:** `~/.copilot/prompts/create-imp-eval.prompt.md`

Workflow: given an accepted IMP, generate the matching evaluator stub (`evals/evaluators/custom/imp_XXXX.py`) and `mocks.yaml` additions if needed. Use IMP-0004's structural eval as the canonical pattern.

### Phase F — New `/Validate-IMP` prompt — ~30 min

**New file:** `~/.copilot/prompts/validate-imp.prompt.md`

Workflow: re-run the post eval against current main, compare to committed baseline, optionally pull a real session log to confirm behavior in the wild, flip status to `validated` (or `reverted`).

### Phase G — Recommender → IMP adapter — ~1 hr

**New file:** `evals/runner/imp_adapter.py`

When the eval recommender suggests a change, emit a draft `IMP-XXXX.md` file with `status: proposed` and pre-filled `eval_type` / `eval_id` so the loop closes.

---

## 5. Files to touch (cheat sheet)

### `~/.copilot/` (this repo)

| File | Change | Phase |
|---|---|---|
| `agents/improvements/_template.md` | Add eval frontmatter fields + Results section | C |
| `agents/improvements/README.md` | Document eval workflow + link to this plan | (now) |
| `prompts/implement-improvement.prompt.md` | Add baseline gate + auto post-eval + results-append | D |
| `prompts/agent-status.prompt.md` | Surface `eval_type` / last metric / regression flag in dashboard | D |
| `prompts/create-imp-eval.prompt.md` | NEW — scaffold evaluator from IMP | E |
| `prompts/validate-imp.prompt.md` | NEW — re-run + flip status | F |
| `copilot-instructions.md` | Add a "see EVAL-SYSTEM-PLAN.md" pointer for IMP/eval work | (now) |
| `EVAL-SYSTEM-PLAN.md` | This file | (now) |

### `evals/` (co-located in this repo)

| File | Change | Phase |
|---|---|---|
| `evaluators/tool_loop.py` | NEW — Pattern C loop | A |
| `datasets/qb/mocks.yaml` | NEW — per-agent mock config | A |
| `datasets/{agent}/mocks.yaml` | NEW per agent as added | A+ |
| `runner/cli.py` | Add `run-imp` subcommand | B |
| `baselines/` | NEW directory, committed JSON snapshots | B |
| `evaluators/custom/imp_XXXX.py` | One per eval'd IMP (IMP-0004 already exists as reference) | E (per IMP) |
| `runner/imp_adapter.py` | NEW — recommender → draft IMP | G |
| `README.md` | Add a section pointing back to `~/.copilot/EVAL-SYSTEM-PLAN.md` | (now) |

### Memory

- `/memories/repo/agent-improvements.md` — add pointer to this file. (Done as part of this task.)

---

## 6. Acceptance criteria (when is this whole thing "done"?)

- [ ] Phase A: `evals run-behavioral --with-tools --use-loop` completes a multi-turn QB scenario end to end on gpt-5.4.
- [ ] Phase B: `evals run-imp IMP-0004 --full` produces pre + post snapshots and a comparison report.
- [ ] Phase C: `_template.md` has eval fields; lint check passes on existing IMPs (treat missing fields as `eval_type: manual` for back-compat).
- [ ] Phase D: Running `/Implement-Improvement` on a fresh IMP captures baseline before any code change and writes the results table after.
- [ ] Phase E+F: At least one IMP after IMP-0004 ships using `/Create-IMP-Eval` then `/Validate-IMP`.
- [ ] Backfill: IMP-0004 frontmatter updated with `commit: 2531ab6`, `eval_type: structural`, `eval_id: imp_0004`, baseline + post paths.

## 7. Open questions / known limits

- **Surrogate model gap (the big one):** production and surrogate behavior can differ. Use
  source-tagged provenance, representative negatives, and the hard confidence gate. Backfill real
  sessions opportunistically; require them only when the criterion cannot be observed through a
  deterministic, synthetic, surrogate, or inspection path.
- **Mock fidelity:** `mocks.yaml` is hand-curated; bad mocks silently produce bad evals. Phase A.5 mitigates by capturing one real session per agent and asserting mocks are JSON-schema-compatible with what the real tool returned.
- **Cost drift:** Foundry calls are cheap but not free. `max_turns` caps per-run cost; `cost.{tokens,wall_time}` in every snapshot lets us spot creep across IMPs.
- **VS Code tool surface drift:** the Copilot tool list (especially deferred tools) evolves. Re-run mock-shape validation quarterly or whenever a new tool category appears in `copilot-instructions.md`.
- **Run-cost units (IMP-0058):** `cost_estimates` / `cost_estimate_total` on run records are
  **weighted model-request counts** (per-session turns × tier weight from `config.yaml
  cost_model:`; tiers per the IMP-0049 fleet table), NOT dollars — Copilot billing exposes no
  per-request dollars. Valid for relative comparisons only (fleet A vs B, local vs delegated,
  task-type mix). Attribution rides the IMP-0052 `-subN` session split; its accuracy bounds the
  proxy. Bump `cost_model.version` when weights change. Per-phase wall time (`phase_durations`,
  `dev_segment_minutes`) requires the driver's `pipeline dispatch` stamp — legacy records with
  `started == finished` yield null, never fabricated zeros.

## 8. Implementation order recommendation

1. **Phase C (template) + §3a measurement contract** — 30 min, shapes everything downstream. Do first so Phase A emits the right fields from day one.
2. Phase A (tool loop) — unblocks `tool_loop` / `subagent_routing` / `behavioral` evals.
3. Phase A.5 (mock-shape validation against one captured real session per agent).
4. Phase B (`run-imp`) — needed before Phase D can auto-call it.
5. Phase D (`/Implement-Improvement` update) — closes the loop for the next IMP.
6. Backfill IMP-0004 to prove the pipeline end-to-end.
7. Phase E + F prompts.
8. Phase G — reframe as **failure-case routing** (failed eval cases auto-attach to relevant IMP as evidence) rather than IMP generation.

---

## 9. Pointers for future sessions

If a future session asks about:
- "How do we eval an IMP?" → **this file**, sections 3 + 4.
- "Where do baselines live?" → `evals/baselines/`.
- "How do mocks work?" → Phase A + `evals/datasets/{agent}/mocks.yaml`.
- "What's the IMP lifecycle?" → `agents/improvements/README.md` (lifecycle) + this file (eval phases).
- "Is IMP-XXXX validated?" → check `status:` in the IMP file and the Results table.
