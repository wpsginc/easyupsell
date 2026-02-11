import typer
import sys
from pathlib import Path
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

# Hack to import from src
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
from bigcommerce import BigCommerceClient

from easyupsell.core.analyzer import get_all_leaf_categories
from easyupsell.core.discovery import discover_dark_horses
from easyupsell.core.output import write_dark_horse_results, write_catalog_gaps

app = typer.Typer(help="Discover hidden inventory")
console = Console()

@app.callback(invoke_without_command=True)
def discover(
    ctx: typer.Context,
    category: str = typer.Option(None, "--category", help="Run analysis on a specific category name."),
    all_cats: bool = typer.Option(False, "--all", help="Run analysis on ALL leaf categories."),
    model: str = typer.Option("default", "--model", help="Override the LLM model ID."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print results to stdout instead of saving."),
):
    """
    Discover hidden inventory and catalog gaps using "Dark Horse" analysis.
    """
    if ctx.invoked_subcommand is not None:
        return

    if not category and not all_cats:
        console.print("[red]Error: You must specify either --category or --all[/red]")
        raise typer.Exit(code=1)

    if category and all_cats:
        console.print("[red]Error: You cannot specify both --category and --all[/red]")
        raise typer.Exit(code=1)

    console.print(f"[bold green]Starting Dark Horse Discovery...[/bold green]")
    console.print(f"Model: {model}")
    if dry_run:
        console.print("[yellow]Dry Run Mode Enabled[/yellow]")

    # 1. Connect to BigCommerce (to get categories)
    try:
        client = BigCommerceClient.from_env()
    except Exception as e:
        console.print(f"[red]Error connecting to BigCommerce:[/red] {e}")
        raise typer.Exit(code=1)

    # 2. Get All Categories (for Matching)
    console.print("Fetching categories...")
    try:
        all_leaves = get_all_leaf_categories(client)
        all_cat_names = [c["name"] for c in all_leaves]
    except Exception as e:
        console.print(f"[red]Error fetching categories:[/red] {e}")
        raise typer.Exit(code=1)

    # 3. Determine Targets
    targets = []
    if category:
        targets = [category]
        console.print(f"Target: Single Category '{category}'")
    else:
        targets = all_cat_names
        console.print(f"Target: ALL {len(targets)} Leaf Categories")

    # 4. Run Analysis
    all_pairings = []
    all_gaps = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Analyzing...", total=len(targets))
        
        for target in targets:
            progress.update(task, description=f"Analyzing {target}...")
            
            # Use local provider if not specified otherwise in config, 
            # but CLI argument can override config? 
            # Currently logic uses 'local' as default in discover_dark_horses signature.
            # If user passes --model, we might want to pass that as provider or model?
            # The signature is `provider`.
            # If user says --model "gpt-4", maybe they mean provider="openai"?
            # For now, let's assume `model` arg maps to `provider` arg in discovery.
            # Or use 'local' and let config handle model.
            
            provider_arg = "local" # Default for this command per spec Phase 2 Task 2?
            # Spec says "Implement Local LLM Client Support".
            # CLI says --model.
            # Let's pass the cli arg `model` as `provider` to `discover_dark_horses` 
            # if it matches one of our providers, else assume it's a model name for local?
            # Actually, `discover_dark_horses` takes `provider`.
            # Let's use `model` arg as `provider` for now to be simple, or "local" if default.
            
            p_arg = "local" if model == "default" else model
            
            results = discover_dark_horses(target, all_cat_names, provider=p_arg)
            
            all_pairings.extend(results["pairings"])
            all_gaps.extend(results["gaps"])
            
            progress.advance(task)

    # 5. Output Results
    if dry_run:
        console.print("\n[bold]Results (Dry Run):[/bold]")
        console.print(f"Pairings found: {len(all_pairings)}")
        for p in all_pairings[:5]:
            console.print(f"  {p['source']} -> {p['target']} ({p['concept']})")
            
        console.print(f"Gaps found: {len(all_gaps)}")
        for g in all_gaps[:5]:
            console.print(f"  {g['source']} missing {g['missing_concept']}")
    else:
        output_dir = Path("data")
        pairings_file = output_dir / "dark_horse_pairings.csv"
        gaps_file = output_dir / "catalog_gaps.csv"
        
        write_dark_horse_results(all_pairings, pairings_file)
        write_catalog_gaps(all_gaps, gaps_file)
        
        console.print(f"\n[green]✓[/green] Saved {len(all_pairings)} pairings to {pairings_file}")
        console.print(f"[green]✓[/green] Saved {len(all_gaps)} gaps to {gaps_file}")
