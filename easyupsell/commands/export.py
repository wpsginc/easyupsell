"""
Export command - Export recommendations to various formats.
"""

import typer
from pathlib import Path
from rich.console import Console
from typing import Optional
import csv

app = typer.Typer(help="Export recommendations to various formats")
console = Console()


@app.callback(invoke_without_command=True)
def export_main(ctx: typer.Context):
    """Export recommendations."""
    if ctx.invoked_subcommand is None:
        console.print("Available formats: [cyan]peasisoft, csv, json[/cyan]")
        console.print("Run: [green]pre export peasisoft[/green]")


@app.command("peasisoft")
def export_peasisoft(
    input_file: Path = typer.Option(
        Path("data/recommendations.csv"), "--input", "-i",
        help="Input recommendations CSV"
    ),
    output_file: Path = typer.Option(
        Path("data/peasisoft_import.csv"), "--output", "-o",
        help="Output Peasisoft format"
    ),
    only_valid: bool = typer.Option(
        True, "--valid-only/--all",
        help="Export only LLM-validated recommendations"
    ),
):
    """Export to Peasisoft Native Upsell format."""
    if not input_file.exists():
        console.print(f"[red]Error:[/red] {input_file} not found")
        console.print("Run [cyan]pre analyze[/cyan] first")
        raise typer.Exit(1)
    
    with open(input_file) as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    if only_valid:
        rows = [r for r in rows if r.get("llm_valid") == "True"]
    
    # Peasisoft format (adjust based on actual spec)
    output_rows = []
    for r in rows:
        output_rows.append({
            "source_category": r["source_category"],
            "product_sku": r["recommended_sku"],
            "product_name": r["recommended_name"],
            "price": r["recommended_price"],
            "weight": r.get("llm_confidence", "0.5"),
            "relationship": r.get("relationship_type", "complementary"),
        })
    
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=output_rows[0].keys())
        writer.writeheader()
        writer.writerows(output_rows)
    
    console.print(f"[green]✓[/green] Exported {len(output_rows)} recommendations")
    console.print(f"[green]✓[/green] Saved to: {output_file}")


@app.command("json")
def export_json(
    input_file: Path = typer.Option(
        Path("data/recommendations.csv"), "--input", "-i",
        help="Input recommendations CSV"
    ),
    output_file: Path = typer.Option(
        Path("data/recommendations.json"), "--output", "-o",
        help="Output JSON file"
    ),
):
    """Export to JSON format."""
    import json
    
    if not input_file.exists():
        console.print(f"[red]Error:[/red] {input_file} not found")
        raise typer.Exit(1)
    
    with open(input_file) as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(rows, indent=2))
    
    console.print(f"[green]✓[/green] Exported {len(rows)} recommendations to JSON")
