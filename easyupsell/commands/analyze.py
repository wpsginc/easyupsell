"""
Analyze command - Generate upsell recommendations.
"""

import typer
from pathlib import Path
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from typing import Optional
import os
import sys
from datetime import datetime

app = typer.Typer(help="Generate upsell recommendations")
console = Console()

LOGS_DIR = Path("logs")
PIDS_DIR = Path(".pids")


def _run_in_background(args: list[str], log_file: Path) -> int:
    """Fork and run the analysis in background, returning the PID."""
    import subprocess
    
    # Ensure directories exist
    LOGS_DIR.mkdir(exist_ok=True)
    PIDS_DIR.mkdir(exist_ok=True)
    
    # Get the current Python and script
    python = sys.executable
    script = Path(__file__).parent.parent.parent / "easyupsell" / "cli.py"
    
    # Build command - re-invoke without --background
    cmd = [python, "-m", "easyupsell"] + args
    
    # Open log file
    with open(log_file, "w") as log:
        log.write(f"# EasyUpsell Background Job\n")
        log.write(f"# Started: {datetime.now().isoformat()}\n")
        log.write(f"# Command: {' '.join(cmd)}\n")
        log.write(f"# Log: {log_file}\n\n")
        log.flush()
        
        # Start process
        proc = subprocess.Popen(
            cmd,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,  # Detach from terminal
        )
    
    # Save PID
    pid_file = PIDS_DIR / f"analyze_{proc.pid}.pid"
    pid_file.write_text(str(proc.pid))
    
    return proc.pid


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
        help="LLM provider (azure, openai, athena, ollama)"
    ),
    background: bool = typer.Option(
        False, "--background", "-b",
        help="Run in background with logging"
    ),
):
    """
    Generate category→item recommendations.
    
    Examples:
        easyupsell analyze                    # Top 50 categories
        easyupsell analyze --all              # Full catalog  
        easyupsell analyze -c "Tactical Pants"  # Single category
        easyupsell analyze -l 100 -i 10       # 100 cats, 10 items each
        easyupsell analyze --all --background # Run in background
    """
    if ctx.invoked_subcommand is not None:
        return
    
    # Handle background mode
    if background:
        # Build args without --background
        args = ["analyze"]
        if all_categories:
            args.append("--all")
        if category:
            args.extend(["--category", category])
        args.extend(["--limit", str(limit)])
        args.extend(["--items", str(items_per_category)])
        args.extend(["--output", str(output)])
        if skip_orders:
            args.append("--skip-orders")
        if resume:
            args.append("--resume")
        args.extend(["--provider", provider])
        
        # Create log file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = LOGS_DIR / f"analyze_{timestamp}.log"
        
        pid = _run_in_background(args, log_file)
        
        console.print(f"\n[bold green]✓ Background job started![/bold green]")
        console.print(f"  PID: {pid}")
        console.print(f"  Log: {log_file}")
        console.print(f"\n[dim]Monitor with: tail -f {log_file}[/dim]")
        console.print(f"[dim]Kill with: kill {pid}[/dim]")
        return
        
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
    
    console.print(f"Provider: [cyan]{provider}[/cyan]")
    
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
        background=False,
    )


@app.command("jobs")
def list_jobs():
    """List running background jobs."""
    import signal
    
    if not PIDS_DIR.exists():
        console.print("[dim]No background jobs found[/dim]")
        return
    
    console.print("\n[bold]Background Jobs[/bold]")
    console.print("-" * 40)
    
    found = False
    for pid_file in PIDS_DIR.glob("*.pid"):
        pid = int(pid_file.read_text().strip())
        
        # Check if process is running
        try:
            os.kill(pid, 0)  # Signal 0 = check if exists
            status = "[green]running[/green]"
            found = True
        except OSError:
            status = "[dim]finished[/dim]"
            pid_file.unlink()  # Clean up
            continue
        
        console.print(f"  PID {pid}: {status}")
    
    if not found:
        console.print("[dim]No active jobs[/dim]")
    
    # Show recent logs
    if LOGS_DIR.exists():
        logs = sorted(LOGS_DIR.glob("*.log"), reverse=True)[:3]
        if logs:
            console.print("\n[bold]Recent Logs[/bold]")
            for log in logs:
                console.print(f"  {log}")

