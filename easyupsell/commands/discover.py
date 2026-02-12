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
from easyupsell.core.output import write_dark_horse_results, write_catalog_gaps, write_dark_horse_excel

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
    all_failures = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Analyzing...", total=len(targets))
        
        for target in targets:
            progress.update(task, description=f"Analyzing {target}...")
            
            p_arg = "local" if model == "default" else model
            
            results = discover_dark_horses(target, all_cat_names, provider=p_arg)
            
            all_pairings.extend(results["pairings"])
            all_gaps.extend(results["gaps"])
            all_failures.extend(results.get("failures", []))
            
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
        
        if all_failures:
            console.print(f"\n[red]Failures: {len(all_failures)}[/red]")
            for f in all_failures[:5]:
                console.print(f"  [red]✗[/red] {f['category']} ({f['stage']}): {f['error'][:80]}")
    else:
        output_dir = Path("data")
        
        # Intermediate CSVs
        pairings_file = output_dir / "dark_horse_pairings.csv"
        gaps_file = output_dir / "catalog_gaps.csv"
        write_dark_horse_results(all_pairings, pairings_file)
        write_catalog_gaps(all_gaps, gaps_file)
        
        # Formatted Excel workbook
        excel_file = output_dir / "dark_horse_discovery.xlsx"
        write_dark_horse_excel(all_pairings, all_gaps, excel_file, failures=all_failures)
        
        console.print(f"\n[green]✓[/green] Saved {len(all_pairings)} pairings + {len(all_gaps)} gaps")
        if all_failures:
            console.print(f"[red]✗[/red] {len(all_failures)} failures (see Failures sheet)")
        console.print(f"  Excel: {excel_file}")
        console.print(f"  CSV:   {pairings_file} (intermediate)")
        console.print(f"  CSV:   {gaps_file} (intermediate)")

