"""
Reporter — generates formatted eval reports.
"""

from __future__ import annotations

from rich.console import Console
from rich.table import Table


def print_routing_report(results: list, summary: dict, console: Console):
    """Print a formatted routing evaluation report."""

    # Summary table
    accuracy = summary.get("accuracy", 0)
    color = "green" if accuracy >= 0.9 else "yellow" if accuracy >= 0.7 else "red"

    console.print(f"\n  [bold]Overall Routing Accuracy: [{color}]{accuracy:.1%}[/{color}][/bold]")
    console.print(f"  Passed: {summary.get('passed', 0)} / {summary.get('total', 0)}")
    console.print(f"  False positive cases: {summary.get('false_positive_cases', 0)}")

    # Per-agent breakdown
    per_agent = summary.get("per_agent", {})
    if per_agent:
        table = Table(title="\nPer-Agent Routing Accuracy", show_lines=True)
        table.add_column("Agent", style="cyan")
        table.add_column("Passed", justify="right")
        table.add_column("Total", justify="right")
        table.add_column("Accuracy", justify="right")

        for agent, data in sorted(per_agent.items()):
            acc = data.get("accuracy", 0)
            acc_color = "green" if acc >= 0.9 else "yellow" if acc >= 0.7 else "red"
            table.add_row(
                agent,
                str(data.get("passed", 0)),
                str(data.get("total", 0)),
                f"[{acc_color}]{acc:.0%}[/{acc_color}]",
            )

        console.print(table)

    # Failed cases
    failures = [r for r in results if not r.passed]
    if failures:
        console.print("\n  [bold red]Failed Routing Cases:[/bold red]")
        for r in failures:
            console.print(f"    [red]✗[/red] [{r.test_id}] \"{r.prompt[:50]}...\"")
            console.print(f"      Expected: [green]{r.expected_agent}[/green] → Got: [red]{r.matched_agent}[/red]")
            if r.false_positives:
                console.print(f"      False positives: {', '.join(r.false_positives)}")

    # Confusion matrix
    confusions = summary.get("confusions", {})
    if confusions:
        console.print("\n  [bold yellow]Confusion Matrix (misroutes):[/bold yellow]")
        for expected, wrongs in confusions.items():
            for wrong_agent, count in wrongs.items():
                console.print(f"    {expected} → {wrong_agent}: {count}x")


def print_comparison_report(run_a: dict, run_b: dict, console: Console):
    """Print a comparison between two eval runs."""
    console.print("\n[bold blue]📊 Eval Comparison Report[/bold blue]\n")

    summary_a = run_a.get("summary", {})
    summary_b = run_b.get("summary", {})

    acc_a = summary_a.get("accuracy", 0)
    acc_b = summary_b.get("accuracy", 0)
    delta = acc_b - acc_a

    table = Table(title="Routing Comparison", show_lines=True)
    table.add_column("Metric", style="cyan")
    table.add_column(f"Run A ({run_a.get('run_id', '?')})", justify="right")
    table.add_column(f"Run B ({run_b.get('run_id', '?')})", justify="right")
    table.add_column("Delta", justify="right")

    delta_color = "green" if delta > 0 else "red" if delta < 0 else "white"
    delta_str = f"[{delta_color}]{delta:+.1%}[/{delta_color}]"

    table.add_row("Accuracy", f"{acc_a:.1%}", f"{acc_b:.1%}", delta_str)
    table.add_row(
        "Passed",
        str(summary_a.get("passed", 0)),
        str(summary_b.get("passed", 0)),
        str(summary_b.get("passed", 0) - summary_a.get("passed", 0)),
    )
    table.add_row(
        "False Positives",
        str(summary_a.get("false_positive_cases", 0)),
        str(summary_b.get("false_positive_cases", 0)),
        str(summary_b.get("false_positive_cases", 0) - summary_a.get("false_positive_cases", 0)),
    )

    console.print(table)

    # Per-agent comparison
    agents_a = summary_a.get("per_agent", {})
    agents_b = summary_b.get("per_agent", {})
    all_agents = sorted(set(list(agents_a.keys()) + list(agents_b.keys())))

    if all_agents:
        agent_table = Table(title="\nPer-Agent Comparison", show_lines=True)
        agent_table.add_column("Agent", style="cyan")
        agent_table.add_column("Run A", justify="right")
        agent_table.add_column("Run B", justify="right")
        agent_table.add_column("Delta", justify="right")

        for agent in all_agents:
            a_acc = agents_a.get(agent, {}).get("accuracy", 0)
            b_acc = agents_b.get(agent, {}).get("accuracy", 0)
            d = b_acc - a_acc
            d_color = "green" if d > 0 else "red" if d < 0 else "white"
            agent_table.add_row(
                agent,
                f"{a_acc:.0%}",
                f"{b_acc:.0%}",
                f"[{d_color}]{d:+.0%}[/{d_color}]",
            )

        console.print(agent_table)

    # Regressions (passed in A, failed in B)
    results_a = {r["test_id"]: r for r in run_a.get("results", [])}
    results_b = {r["test_id"]: r for r in run_b.get("results", [])}

    regressions = []
    improvements = []
    for test_id in results_a:
        if test_id in results_b:
            if results_a[test_id]["passed"] and not results_b[test_id]["passed"]:
                regressions.append(test_id)
            elif not results_a[test_id]["passed"] and results_b[test_id]["passed"]:
                improvements.append(test_id)

    if regressions:
        console.print("\n  [bold red]⚠️  Regressions (passed → failed):[/bold red]")
        for tid in regressions:
            r = results_b[tid]
            console.print(f"    [red]✗[/red] [{tid}] expected {r['expected']} → got {r['matched']}")

    if improvements:
        console.print("\n  [bold green]✅ Improvements (failed → passed):[/bold green]")
        for tid in improvements:
            console.print(f"    [green]✓[/green] [{tid}]")

    if not regressions and not improvements:
        console.print("\n  [white]No routing changes between runs.[/white]")


def print_behavioral_report(results: list, summary, console: Console):
    """Print a formatted behavioral evaluation report."""

    # Overall pass rate
    rate = summary.pass_rate
    color = "green" if rate >= 0.9 else "yellow" if rate >= 0.7 else "red"
    console.print(f"\n  [bold]Overall Checkpoint Compliance: [{color}]{rate:.0%}[/{color}][/bold]")
    console.print(f"  Passed: {summary.passed_cases} / {summary.total_cases}\n")

    # By category table
    if summary.by_category:
        cat_table = Table(title="Compliance by Category", show_lines=True)
        cat_table.add_column("Category", style="cyan")
        cat_table.add_column("Passed", justify="right")
        cat_table.add_column("Total", justify="right")
        cat_table.add_column("Rate", justify="right")

        for cat, data in sorted(summary.by_category.items()):
            cat_rate = data.get("pass_rate", 0)
            cat_color = "green" if cat_rate >= 0.9 else "yellow" if cat_rate >= 0.7 else "red"
            cat_table.add_row(
                cat,
                str(data["passed"]),
                str(data["total"]),
                f"[{cat_color}]{cat_rate:.0%}[/{cat_color}]",
            )
        console.print(cat_table)

    # By check type table
    if summary.by_check:
        check_table = Table(title="\nCompliance by Check Type", show_lines=True)
        check_table.add_column("Check", style="cyan")
        check_table.add_column("Passed", justify="right")
        check_table.add_column("Total", justify="right")
        check_table.add_column("Rate", justify="right")

        for check_id, data in sorted(summary.by_check.items()):
            check_rate = data.get("pass_rate", 0)
            check_color = "green" if check_rate >= 0.9 else "yellow" if check_rate >= 0.7 else "red"
            check_table.add_row(
                check_id,
                str(data["passed"]),
                str(data["total"]),
                f"[{check_color}]{check_rate:.0%}[/{check_color}]",
            )
        console.print(check_table)

    # Per-case details
    console.print("\n  [bold]Per-Case Results:[/bold]")
    for r in results:
        status = "[green]✓[/green]" if r.passed else "[red]✗[/red]"
        console.print(f"\n  {status} [cyan]{r.test_id}[/cyan] ({r.category}) — {r.passed_checks}/{r.total_checks} checks")
        console.print(f"    Prompt: \"{r.prompt[:70]}{'...' if len(r.prompt) > 70 else ''}\"")
        for check in r.checks:
            check_status = "[green]✓[/green]" if check.passed else "[red]✗[/red]"
            console.print(f"      {check_status} {check.label}: {check.evidence[:100]}")

    # Failures summary
    if summary.failures:
        console.print(f"\n  [bold red]⚠ {len(summary.failures)} Failed Cases:[/bold red]")
        for f in summary.failures:
            console.print(f"    [red]✗[/red] [{f['test_id']}] ({f['category']})")
            for fc in f["failed_checks"]:
                console.print(f"      → {fc['label']}: {fc['evidence'][:80]}")
