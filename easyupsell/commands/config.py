"""
Config command - Configure API connections.
"""

import typer
from pathlib import Path
from rich.console import Console
from rich.table import Table
import os

app = typer.Typer(help="Configure API connections")
console = Console()

ENV_FILE = Path(".env")


@app.callback(invoke_without_command=True)
def config_main(ctx: typer.Context):
    """Configure API keys and connections."""
    if ctx.invoked_subcommand is None:
        show_config()


@app.command("show")
def show_config():
    """Show current configuration (keys masked)."""
    from dotenv import dotenv_values
    
    env = dotenv_values(ENV_FILE) if ENV_FILE.exists() else {}
    
    table = Table(title="Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Status", style="green")
    
    # BigCommerce
    bc_hash = env.get("BIGCOMMERCE_STORE_HASH", "")
    bc_token = env.get("BIGCOMMERCE_ACCESS_TOKEN", "")
    bc_status = "✓ Configured" if bc_hash and bc_token else "✗ Missing"
    table.add_row("BigCommerce", bc_status)
    
    # Azure OpenAI
    azure_key = env.get("AZURE_OPENAI_API_KEY", "")
    azure_endpoint = env.get("AZURE_OPENAI_ENDPOINT", "")
    azure_status = "✓ Configured" if azure_key and azure_endpoint else "✗ Missing"
    table.add_row("Azure OpenAI", azure_status)
    
    # NetSuite (optional)
    ns_account = env.get("NETSUITE_ACCOUNT_ID", "")
    ns_status = "✓ Configured" if ns_account else "○ Not configured (optional)"
    table.add_row("NetSuite", ns_status)
    
    console.print(table)
    console.print(f"\n[dim]Config file: {ENV_FILE.absolute()}[/dim]")


@app.command("test")
def test_connections():
    """Test all API connections."""
    from dotenv import load_dotenv
    load_dotenv()
    
    console.print("\n[bold]Testing connections...[/bold]\n")
    
    # Test BigCommerce
    try:
        import sys
        sys.path.insert(0, "src")
        from bigcommerce import BigCommerceClient
        
        client = BigCommerceClient.from_env()
        result = client.test_connection()
        
        if result["success"]:
            console.print(f"[green]✓[/green] BigCommerce: {result.get('store_name')}")
        else:
            console.print(f"[red]✗[/red] BigCommerce: {result.get('error')}")
    except Exception as e:
        console.print(f"[red]✗[/red] BigCommerce: {e}")
    
    # Test Azure OpenAI
    try:
        from openai import AzureOpenAI
        
        client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version="2024-02-15-preview",
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        )
        
        # Quick test
        response = client.chat.completions.create(
            model=os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o"),
            messages=[{"role": "user", "content": "Say 'OK'"}],
            max_tokens=5,
        )
        console.print(f"[green]✓[/green] Azure OpenAI: Connected")
    except Exception as e:
        console.print(f"[red]✗[/red] Azure OpenAI: {e}")


@app.command("set")
def set_config(
    key: str = typer.Argument(..., help="Config key (e.g., BIGCOMMERCE_STORE_HASH)"),
    value: str = typer.Argument(..., help="Config value"),
):
    """Set a configuration value."""
    from dotenv import set_key
    
    set_key(ENV_FILE, key, value)
    console.print(f"[green]✓[/green] Set {key}")
