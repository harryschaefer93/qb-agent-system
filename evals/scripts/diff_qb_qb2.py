import json, glob
def load(a):
    return json.load(open(sorted(glob.glob(f'results/behavioral-{a}-*.json'))[-1], encoding='utf-8'))
qb = load('qb'); qb2 = load('qb2')
qb_fails = {r['test_id']: [c for c in r['checks'] if not c['passed']] for r in qb['results'] if not r['passed']}
qb2_fails = {r['test_id']: [c for c in r['checks'] if not c['passed']] for r in qb2['results'] if not r['passed']}
print('QB baseline fails:')
for tid, fails in qb_fails.items():
    for c in fails:
        ev = c['evidence'][:80]
        print(f'  {tid}: {c["label"]} -> {ev}')
print()
print('QB2 (template) fails:')
for tid, fails in qb2_fails.items():
    for c in fails:
        ev = c['evidence'][:80]
        print(f'  {tid}: {c["label"]} -> {ev}')
print()
print('Per-check delta (QB2 - QB):')
qb_checks = qb['summary']['by_check']
qb2_checks = qb2['summary']['by_check']
for k in sorted(set(list(qb_checks.keys()) + list(qb2_checks.keys()))):
    a = qb_checks.get(k, {}).get('passed', 0)
    b = qb2_checks.get(k, {}).get('passed', 0)
    if a != b:
        print(f'  {k}: QB={a}, QB2={b}, delta={b-a:+d}')
