import typer
from rich.console import Console

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
    if category:
        console.print(f"Target: Single Category '{category}'")
    else:
        console.print(f"Target: ALL Leaf Categories")
    
    console.print(f"Model: {model}")
    if dry_run:
        console.print("[yellow]Dry Run Mode Enabled[/yellow]")

    # Logic placeholder
    console.print("Discovery logic not implemented yet.")