import json, glob, sys
agent = sys.argv[1] if len(sys.argv) > 1 else 'qb2'
d = json.load(open(sorted(glob.glob(f'results/behavioral-{agent}-*.json'))[-1], encoding='utf-8'))
s = d['summary']
print(f'Pass rate: {s["pass_rate"]:.0%} ({s["passed_cases"]}/{s["total_cases"]})')
print()
print('By category:')
for c, m in sorted(s['by_category'].items()):
    print(f'  {c:22s} {m["passed"]}/{m["total"]}  ({m["pass_rate"]:.0%})')
print()
print('By check:')
for c, m in sorted(s['by_check'].items()):
    print(f'  {c:32s} {m["passed"]}/{m["total"]}  ({m["pass_rate"]:.0%})')
