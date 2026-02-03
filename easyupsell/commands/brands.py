"""
Brands command - Manage priority brand list.
"""

import typer
from pathlib import Path
from rich.console import Console
from rich.table import Table
import json

app = typer.Typer(help="Manage priority brand list")
console = Console()

BRANDS_FILE = Path("data/priority_brands.json")

DEFAULT_BRANDS = [
    "streamlight",
    "benchmade", 
    "channellock",
    "pelican",
    "gerber",
    "leatherman",
    "5.11",
    "blackinton",
    "safariland",
]


def load_brands() -> list[str]:
    """Load brands from config file."""
    if BRANDS_FILE.exists():
        return json.loads(BRANDS_FILE.read_text())
    return DEFAULT_BRANDS.copy()


def save_brands(brands: list[str]):
    """Save brands to config file."""
    BRANDS_FILE.parent.mkdir(parents=True, exist_ok=True)
    BRANDS_FILE.write_text(json.dumps(sorted(set(brands)), indent=2))


@app.callback(invoke_without_command=True)
def brands_main(ctx: typer.Context):
    """Manage priority brands that get boosted in recommendations."""
    if ctx.invoked_subcommand is None:
        # Default: show list
        list_brands()


@app.command("list")
def list_brands():
    """List all priority brands."""
    brands = load_brands()
    
    table = Table(title="Priority Brands")
    table.add_column("#", style="dim")
    table.add_column("Brand", style="cyan")
    
    for i, brand in enumerate(sorted(brands), 1):
        table.add_row(str(i), brand)
    
    console.print(table)
    console.print(f"\n[dim]These brands get 50% of recommendation slots.[/dim]")


@app.command("add")
def add_brand(
    name: str = typer.Argument(..., help="Brand name to add (case-insensitive)")
):
    """Add a brand to the priority list."""
    brands = load_brands()
    name_lower = name.lower()
    
    if name_lower in brands:
        console.print(f"[yellow]'{name}' is already in the list[/yellow]")
        return
    
    brands.append(name_lower)
    save_brands(brands)
    console.print(f"[green]✓[/green] Added '{name_lower}' to priority brands")


@app.command("remove")
def remove_brand(
    name: str = typer.Argument(..., help="Brand name to remove")
):
    """Remove a brand from the priority list."""
    brands = load_brands()
    name_lower = name.lower()
    
    if name_lower not in brands:
        console.print(f"[yellow]'{name}' is not in the list[/yellow]")
        return
    
    brands.remove(name_lower)
    save_brands(brands)
    console.print(f"[green]✓[/green] Removed '{name_lower}' from priority brands")


@app.command("reset")
def reset_brands():
    """Reset to default brand list."""
    save_brands(DEFAULT_BRANDS)
    console.print("[green]✓[/green] Reset to default brands")
    list_brands()
