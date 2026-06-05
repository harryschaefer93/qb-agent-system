import json, glob
d = json.load(open(sorted(glob.glob('results/behavioral-qb-*.json'))[-1], encoding='utf-8'))
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
print()
print('NEW checks specifically:')
for c, m in sorted(s['by_check'].items()):
    if c in ('invokes_arch','invokes_repo','fans_out_dev','delegates_arch'):
        print(f'  {c:32s} {m["passed"]}/{m["total"]}  ({m["pass_rate"]:.0%})')
