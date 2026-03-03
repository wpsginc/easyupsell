"""
CLI command: opportunities — Identify new product sourcing opportunities.

Reads catalog gaps from Phase 2 Dark Horse analysis, deduplicates by product type,
optionally enriches with LLM-generated descriptions/prices, and produces
a polished Excel report for the merchandising team.

Usage:
    pre opportunities                         # Full LLM-enriched run
    pre opportunities --skip-llm              # Instant output, no LLM cost
    pre opportunities --provider athena       # Use local model
    pre opportunities --input data/custom.csv # Custom gaps file
"""

import typer
from pathlib import Path
from rich.console import Console
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    MofNCompleteColumn,
)

from easyupsell.core.opportunities import (
    load_and_deduplicate_gaps,
    enrich_opportunities_batch,
    write_opportunities_excel,
)

app = typer.Typer(help="Identify new product sourcing opportunities")
console = Console()


@app.callback(invoke_without_command=True)
def opportunities(
    ctx: typer.Context,
    input_file: str = typer.Option(
        "data/catalog_gaps.csv",
        "--input",
        help="Path to catalog gaps CSV (from Phase 2 discovery)",
    ),
    provider: str = typer.Option("azure", help="LLM provider for enrichment"),
    batch_size: int = typer.Option(20, help="Items per LLM enrichment batch"),
    skip_llm: bool = typer.Option(
        False, "--skip-llm", help="Skip LLM enrichment (instant output)"
    ),
    output: str = typer.Option(
        None, help="Output Excel path (default: data/new_product_opportunities.xlsx)"
    ),
):
    """Identify new product sourcing opportunities from catalog gaps."""
    if ctx.invoked_subcommand is not None:
        return

    if batch_size <= 0:
        console.print("[red]Error: batch_size must be a positive integer[/red]")
        raise typer.Exit(1)

    input_path = Path(input_file)

    # Try backup location if primary doesn't exist
    if not input_path.exists():
        backup_path = Path("data/data.backup/catalog_gaps.csv")
        if backup_path.exists():
            input_path = backup_path
            console.print(f"  [dim]Using backup:[/dim] {input_path}")
        else:
            console.print(
                f"[red]Error: Catalog gaps file not found:[/red] {input_file}"
            )
            console.print(
                "[dim]Run 'pre discover --all' first to generate catalog gaps.[/dim]"
            )
            raise typer.Exit(1)

    output_path = (
        Path(output) if output else Path("data/new_product_opportunities.xlsx")
    )

    # 1. Load and deduplicate
    console.print(f"\n[bold]Phase 3: New Product Opportunities[/bold]")
    console.print(f"[bold]Loading catalog gaps from:[/bold] {input_path}")

    try:
        opportunities_list, detail_rows = load_and_deduplicate_gaps(input_path)
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    console.print(
        f"  [cyan]{len(detail_rows)}[/cyan] total gaps → [cyan]{len(opportunities_list)}[/cyan] unique product types"
    )

    if not opportunities_list:
        console.print("[yellow]No gaps found. Nothing to report.[/yellow]")
        raise typer.Exit(0)

    # Show top 5 most-needed products
    console.print(f"\n[bold]Top 5 Most-Needed Products:[/bold]")
    for opp in opportunities_list[:5]:
        console.print(
            f"  [cyan]{opp['product_type']}[/cyan] — needed by {opp['category_count']} categories"
        )

    # 2. Optional LLM enrichment
    if not skip_llm:
        console.print(
            f"\n[bold]Enriching with LLM:[/bold] {provider} (batch_size={batch_size})"
        )

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Enriching...", total=len(opportunities_list))

            def on_progress(done, total):
                progress.update(
                    task, completed=done, description=f"Enriched {done}/{total}..."
                )

            opportunities_list = enrich_opportunities_batch(
                opportunities_list,
                provider=provider,
                batch_size=batch_size,
                progress_callback=on_progress,
            )

        # Stats
        high = sum(1 for o in opportunities_list if o.get("priority") == "High")
        med = sum(1 for o in opportunities_list if o.get("priority") == "Medium")
        low = sum(1 for o in opportunities_list if o.get("priority") == "Low")
        console.print(f"\n  [green]High priority:[/green] {high}")
        console.print(f"  [yellow]Medium priority:[/yellow] {med}")
        console.print(f"  [dim]Low priority:[/dim] {low}")
    else:
        console.print(f"\n[dim]Skipping LLM enrichment (--skip-llm)[/dim]")

    # 3. Write Excel
    console.print(f"\n[bold]Writing report...[/bold]")
    stats = write_opportunities_excel(opportunities_list, detail_rows, output_path)

    console.print(f"\n[green]✓[/green] Saved to [bold]{output_path}[/bold]")
    console.print(f"  {stats['total_opportunities']} unique product opportunities")
    if stats["high_priority"]:
        console.print(f"  [green]★ {stats['high_priority']} high priority[/green]")
    console.print(f"  {stats['detail_rows']} detail rows for drill-down")
