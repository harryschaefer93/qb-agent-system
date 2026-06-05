import json, glob, os
files = sorted(glob.glob('results/routing-*.json'))
latest = files[-1]
d = json.load(open(latest, encoding='utf-8'))
s = d['summary']
print(f'File: {os.path.basename(latest)}')
print(f'Total: {s["total"]}, passed: {s["passed"]}, accuracy: {s["accuracy"]:.2%}')
print()
print('Per-agent breakdown:')
for agent, m in sorted(s['per_agent'].items()):
    rate = m['passed']/m['total'] if m['total'] else 0
    print(f'  {agent:14s}  {m["passed"]}/{m["total"]}  ({rate:.0%})')
print()
arch_pass = sum(1 for r in d['results'] if r['expected']=='arch' and r['passed'])
arch_total = sum(1 for r in d['results'] if r['expected']=='arch')
repo_pass = sum(1 for r in d['results'] if r['expected']=='repo' and r['passed'])
repo_total = sum(1 for r in d['results'] if r['expected']=='repo')
print(f'NEW ARCH cases: {arch_pass}/{arch_total}')
print(f'NEW REPO cases: {repo_pass}/{repo_total}')
print()
print('Failing NEW ARCH/REPO:')
for r in d['results']:
    if r['expected'] in ('arch','repo') and not r['passed']:
        print(f'  [{r["expected"]:5s}->got:{r["matched"]:8s}] {r["prompt"][:80]}')
