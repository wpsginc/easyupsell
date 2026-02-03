"""
Review command - Interactive review and approval workflow.
"""

import typer
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm
import csv

app = typer.Typer(help="Review and approve recommendations")
console = Console()


@app.callback(invoke_without_command=True)
def review_main(
    ctx: typer.Context,
    input_file: Path = typer.Option(
        Path("data/recommendations.csv"), "--input", "-i",
        help="Recommendations CSV to review"
    ),
):
    """Interactive review of recommendations."""
    if ctx.invoked_subcommand is not None:
        return
    
    if not input_file.exists():
        console.print(f"[red]Error:[/red] {input_file} not found")
        console.print("Run [cyan]easyupsell analyze[/cyan] first")
        raise typer.Exit(1)
    
    with open(input_file) as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    valid = [r for r in rows if r.get("llm_valid") == "True"]
    
    console.print(f"\n[bold]Recommendations Review[/bold]")
    console.print(f"Total: {len(rows)} | Valid: {len(valid)}\n")
    
    # Group by source category
    by_category = {}
    for r in valid:
        cat = r["source_category"]
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(r)
    
    console.print(f"Categories with recommendations: {len(by_category)}\n")
    
    # Show summary table
    table = Table(title="Valid Recommendations by Category")
    table.add_column("Category", style="cyan")
    table.add_column("Items", style="green")
    table.add_column("Top Item")
    
    for cat, items in sorted(by_category.items(), key=lambda x: -len(x[1]))[:20]:
        top = items[0]["recommended_name"][:40]
        table.add_row(cat, str(len(items)), top)
    
    console.print(table)
    
    if len(by_category) > 20:
        console.print(f"\n[dim]...and {len(by_category) - 20} more categories[/dim]")
    
    console.print("\n[dim]For detailed review: easyupsell review category 'Category Name'[/dim]")


@app.command("category")
def review_category(
    name: str = typer.Argument(..., help="Category name to review"),
    input_file: Path = typer.Option(
        Path("data/recommendations.csv"), "--input", "-i",
        help="Recommendations CSV"
    ),
):
    """Review recommendations for a specific category."""
    if not input_file.exists():
        console.print(f"[red]Error:[/red] {input_file} not found")
        raise typer.Exit(1)
    
    with open(input_file) as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    # Find matching category (case-insensitive)
    name_lower = name.lower()
    matches = [r for r in rows if r["source_category"].lower() == name_lower and r.get("llm_valid") == "True"]
    
    if not matches:
        console.print(f"[yellow]No valid recommendations for '{name}'[/yellow]")
        return
    
    console.print(f"\n[bold cyan]{name}[/bold cyan] - {len(matches)} recommendations\n")
    
    for i, r in enumerate(matches, 1):
        console.print(f"[bold]{i}. {r['recommended_name']}[/bold]")
        console.print(f"   SKU: {r['recommended_sku']} | Price: ${r['recommended_price']}")
        console.print(f"   Type: {r.get('relationship_type', 'N/A')} | Confidence: {r.get('llm_confidence', 'N/A')}")
        console.print(f"   [dim]{r.get('llm_reason', '')[:100]}...[/dim]")
        console.print()


@app.command("approve")
def approve_recommendations(
    input_file: Path = typer.Option(
        Path("data/recommendations.csv"), "--input", "-i",
        help="Recommendations CSV"
    ),
    output_file: Path = typer.Option(
        Path("data/approved_recommendations.csv"), "--output", "-o",
        help="Output approved recommendations"
    ),
):
    """Mark all valid recommendations as approved."""
    if not input_file.exists():
        console.print(f"[red]Error:[/red] {input_file} not found")
        raise typer.Exit(1)
    
    with open(input_file) as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    approved = [r for r in rows if r.get("llm_valid") == "True"]
    
    if not approved:
        console.print("[yellow]No valid recommendations to approve[/yellow]")
        return
    
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=approved[0].keys())
        writer.writeheader()
        writer.writerows(approved)
    
    console.print(f"[green]✓[/green] Approved {len(approved)} recommendations")
    console.print(f"[green]✓[/green] Saved to: {output_file}")
