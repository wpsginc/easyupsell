"""
Analyze command - Generate upsell recommendations.
"""

import typer
from pathlib import Path
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from typing import Optional

app = typer.Typer(help="Generate upsell recommendations")
console = Console()


@app.callback(invoke_without_command=True)
def analyze(
    ctx: typer.Context,
    all_categories: bool = typer.Option(
        False, "--all", "-a",
        help="Analyze all 1,252 leaf categories (takes hours)"
    ),
    category: Optional[str] = typer.Option(
        None, "--category", "-c",
        help="Analyze specific category by name"
    ),
    limit: int = typer.Option(
        50, "--limit", "-l",
        help="Number of top categories to analyze"
    ),
    items_per_category: int = typer.Option(
        8, "--items", "-i",
        help="Candidate items per category"
    ),
    output: Path = typer.Option(
        Path("data/recommendations.csv"), "--output", "-o",
        help="Output CSV file"
    ),
    skip_orders: bool = typer.Option(
        False, "--skip-orders",
        help="Skip order history analysis (faster)"
    ),
    resume: bool = typer.Option(
        False, "--resume", "-r",
        help="Resume from last checkpoint"
    ),
    provider: str = typer.Option(
        "azure", "--provider", "-p",
        help="LLM provider (azure, openai, ollama)"
    ),
):
    """
    Generate category→item recommendations.
    
    Examples:
        easyupsell analyze                    # Top 50 categories
        easyupsell analyze --all              # Full catalog  
        easyupsell analyze -c "Tactical Pants"  # Single category
        easyupsell analyze -l 100 -i 10       # 100 cats, 10 items each
    """
    if ctx.invoked_subcommand is not None:
        return
        
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
    
    from easyupsell.core.analyzer import run_analysis
    
    console.print("\n[bold cyan]EasyUpsell Analyzer[/bold cyan]")
    console.print("=" * 50)
    
    # Determine mode
    if category:
        console.print(f"Mode: [green]Single category[/green] - {category}")
        categories_limit = 1
    elif all_categories:
        console.print("Mode: [yellow]Full catalog[/yellow] - 1,252 categories")
        console.print("[dim]This will take several hours...[/dim]")
        categories_limit = 9999
    else:
        console.print(f"Mode: [green]Top {limit} categories[/green] by sales")
        categories_limit = limit
    
    # Run analysis
    try:
        results = run_analysis(
            category_name=category,
            limit=categories_limit,
            items_per_category=items_per_category,
            output_path=output,
            skip_orders=skip_orders,
            resume=resume,
            provider=provider,
        )
        
        valid = results.get("valid_count", 0)
        total = results.get("total_count", 0)
        
        console.print(f"\n[green]✓[/green] Valid recommendations: {valid}/{total}")
        console.print(f"[green]✓[/green] Saved to: {output}")
        
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command("quick")
def quick_analyze():
    """Quick analysis - top 20 categories, 5 items each."""
    analyze(
        ctx=typer.Context(analyze),
        all_categories=False,
        category=None,
        limit=20,
        items_per_category=5,
        output=Path("data/quick_recommendations.csv"),
        skip_orders=False,
        resume=False,
        provider="azure",
    )
