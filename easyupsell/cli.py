"""
EasyUpsell CLI - Main entry point.

Usage:
    pre analyze              # Analyze top categories
    pre analyze --all        # Full catalog
    pre review               # Review recommendations
    pre export               # Export to formats
    pre brands               # Manage priority brands
    pre config               # Configure API keys
"""

import typer
from pathlib import Path
from rich.console import Console
from rich.table import Table

from easyupsell.commands import analyze, brands, config, discover, export, opportunities, review

# Main app with rich help
app = typer.Typer(
    name="pre",
    help="AI-powered upsell recommendation engine for BigCommerce.",
    add_completion=True,
    rich_markup_mode="rich",
)

console = Console()

# Register subcommands
app.add_typer(analyze.app, name="analyze", help="Generate upsell recommendations")
app.add_typer(brands.app, name="brands", help="Manage priority brand list")
app.add_typer(config.app, name="config", help="Configure API connections")
app.add_typer(discover.app, name="discover", help="Discover hidden inventory")
app.add_typer(export.app, name="export", help="Export recommendations")
app.add_typer(opportunities.app, name="opportunities", help="New product sourcing opportunities")
app.add_typer(review.app, name="review", help="Review and approve recommendations")
sync_app = typer.Typer(name="sync", help="Sync recommendations to external systems")
app.add_typer(sync_app)


@app.command()
def version():
    """Show version information."""
    from easyupsell import __version__
    console.print(f"[bold]pre[/bold] v{__version__}")


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", "--host", help="API host"),
    port: int = typer.Option(8090, "--port", help="API port"),
):
    """Start the PRE recommendation API server."""
    import uvicorn

    uvicorn.run("src.api:app", host=host, port=port, reload=False)


@app.command()
def status():
    """Show analysis status and statistics."""
    from pathlib import Path
    import csv
    
    data_dir = Path("data")
    
    table = Table(title="EasyUpsell Status")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    
    # Check for recommendation files
    rec_file = data_dir / "full_recommendations_v2.csv"
    if rec_file.exists():
        with open(rec_file) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            valid = sum(1 for r in rows if r.get("llm_valid") == "True")
            
        table.add_row("Recommendations file", str(rec_file))
        table.add_row("Total analyzed", str(len(rows)))
        table.add_row("Valid recommendations", str(valid))
        table.add_row("Validation rate", f"{100 * valid // len(rows) if rows else 0}%")
    else:
        table.add_row("Recommendations", "[red]No analysis found[/red]")
        table.add_row("Run", "[dim]pre analyze[/dim]")
    
    console.print(table)


@sync_app.command("netsuite")
def sync_netsuite(
    dry_run: bool = typer.Option(False, "--dry-run", help="Build payloads but make zero API calls"),
    max_rpm: int = typer.Option(40, "--max-rpm", help="Max NetSuite requests per minute"),
    batch_size: int = typer.Option(50, "--batch-size", help="Batch size for DB read loop"),
    force: bool = typer.Option(False, "--force", help="Include already-synced records"),
):
    """Push approved recommendations to NetSuite."""
    import os
    from src.db import RecommendationDB
    from src.netsuite.client import NetSuiteClient
    from src.sync.netsuite import NetSuiteSyncJob

    db_path = Path(os.getenv("PRE_DB_PATH", "data/recommendations.db"))
    db = RecommendationDB(db_path)
    db.init_db()

    ns_client = NetSuiteClient.from_env()
    job = NetSuiteSyncJob(db=db, ns_client=ns_client, max_rpm=max_rpm, batch_size=batch_size)
    result = job.run(dry_run=dry_run, force=force)

    console.print("\n[bold]PRE NetSuite Sync Complete[/bold]")
    console.print(f"  Job ID:    {result.job_id}")
    console.print(f"  Duration:  {result.duration}")
    console.print(f"  Synced:    {result.synced}")
    console.print(f"  Failed:    {result.failed}")
    console.print(f"  Orphaned:  {result.orphaned}")
    console.print(f"  Skipped:   {result.skipped}")

    if result.failed > 0 and not dry_run:
        raise typer.Exit(1)


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """
    EasyUpsell - AI-powered upsell recommendations.
    
    Generate category→item recommendations using LLM validation
    and business metrics for BigCommerce checkout upsells.
    """
    if ctx.invoked_subcommand is None:
        # Show help if no command given
        console.print("[bold]pre[/bold] - AI-powered upsell recommendations\n")
        console.print("Run [cyan]pre --help[/cyan] for available commands.")
        console.print("Quick start: [green]pre analyze[/green]")


if __name__ == "__main__":
    app()
