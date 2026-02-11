"""
EasyUpsell CLI - Main entry point.

Usage:
    easyupsell analyze              # Analyze top categories
    easyupsell analyze --all        # Full catalog
    easyupsell review               # Review recommendations
    easyupsell export               # Export to formats
    easyupsell brands               # Manage priority brands
    easyupsell config               # Configure API keys
"""

import typer
from rich.console import Console
from rich.table import Table

from easyupsell.commands import analyze, brands, config, discover, export, review

# Main app with rich help
app = typer.Typer(
    name="easyupsell",
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
app.add_typer(review.app, name="review", help="Review and approve recommendations")


@app.command()
def version():
    """Show version information."""
    from easyupsell import __version__
    console.print(f"[bold]easyupsell[/bold] v{__version__}")


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
        table.add_row("Run", "[dim]easyupsell analyze[/dim]")
    
    console.print(table)


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """
    EasyUpsell - AI-powered upsell recommendations.
    
    Generate category→item recommendations using LLM validation
    and business metrics for BigCommerce checkout upsells.
    """
    if ctx.invoked_subcommand is None:
        # Show help if no command given
        console.print("[bold]easyupsell[/bold] - AI-powered upsell recommendations\n")
        console.print("Run [cyan]easyupsell --help[/cyan] for available commands.")
        console.print("Quick start: [green]easyupsell analyze[/green]")


if __name__ == "__main__":
    app()
