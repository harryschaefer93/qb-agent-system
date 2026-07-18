"""Run IMP-0004 evaluations: structural checks + pre/post comparison."""
from pathlib import Path
from evaluators.custom.imp_0004 import evaluate_imp_0004, evaluate_imp_0004_baseline

EVALS_ROOT = Path(__file__).resolve().parent.parent  # scripts/ -> evals/
COPILOT_ROOT = EVALS_ROOT.parent                     # evals/   -> .copilot/

post_file = COPILOT_ROOT / "agents" / "QB.agent.md"
pre_file = EVALS_ROOT / "results" / "qb-pre-imp0004.md"

# 1. Structural eval on current (post-IMP-0004) file
report = evaluate_imp_0004(post_file)
status = "PASS" if report.passed else "FAIL"

print("=" * 60)
print(f"IMP-0004 STRUCTURAL EVAL — {status} ({report.passed_checks}/{report.total_checks})")
print("=" * 60)
for r in report.results:
    icon = "PASS" if r.passed else "FAIL"
    print(f"  [{icon}] {r.label}")
    print(f"         {r.detail}")
print()

# 2. Pre/post comparison
comp = evaluate_imp_0004_baseline(pre_file, post_file)
status2 = "PASS" if comp.passed else "FAIL"

print("=" * 60)
print(f"IMP-0004 PRE/POST COMPARISON — {status2} ({comp.passed_checks}/{comp.total_checks})")
print("=" * 60)
for r in comp.results:
    icon = "PASS" if r.passed else "FAIL"
    print(f"  [{icon}] {r.label}")
    print(f"         {r.detail}")
