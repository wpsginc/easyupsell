#!/usr/bin/env python3
"""
Analyze Batch Validation Results

Parses the CSV output from recommend_items_full.py and generates a validation report.
"""

import argparse
import sys
from pathlib import Path

import pandas as pd
from rich.console import Console
from rich.table import Table

# Add src to path for config
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from config import settings

console = Console()

def analyze_results(csv_path: Path):
    if not csv_path.exists():
        console.print(f"[bold red]File not found: {csv_path}[/bold red]")
        return

    console.print(f"Analyzing [bold]{csv_path}[/bold]...")
    
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        console.print(f"[bold red]Error reading CSV: {e}[/bold red]")
        return

    # Basic stats
    total_rows = len(df)
    
    # Handle boolean strings if necessary
    if df['llm_valid'].dtype == object:
        df['llm_valid'] = df['llm_valid'].map({'True': True, 'False': False, 'None': None, 'TRUE': True, 'FALSE': False})
    
    valid_count = df['llm_valid'].sum()
    invalid_count = (~df['llm_valid'].astype(bool)).sum()
    uncertain_count = df['llm_valid'].isna().sum()
    
    # Acceptance Rate
    acceptance_rate = (valid_count / total_rows * 100) if total_rows > 0 else 0
    
    console.print(f"\n[bold]Summary Metrics[/bold]")
    console.print(f"Total Rows: {total_rows}")
    console.print(f"Valid Recommendations: [green]{valid_count}[/green]")
    console.print(f"Invalid Recommendations: [red]{invalid_count}[/red]")
    console.print(f"Uncertain/Error: [yellow]{uncertain_count}[/yellow]")
    console.print(f"Acceptance Rate: [bold blue]{acceptance_rate:.1f}%[/bold blue]")
    
    # Confidence Distribution
    if 'llm_confidence' in df.columns:
        console.print(f"\n[bold]Confidence Scores (Valid Items)[/bold]")
        valid_df = df[df['llm_valid'] == True]
        console.print(valid_df['llm_confidence'].describe().to_string())

    # Top Rejected Categories
    console.print(f"\n[bold]Top Rejected Categories[/bold]")
    rejected_df = df[df['llm_valid'] == False]
    if not rejected_df.empty:
        top_rejected = rejected_df['source_category'].value_counts().head(5)
        console.print(top_rejected.to_string())
        
    # Sample "Hallucinations" (High Confidence but Rejected? Or Low Confidence but Accepted?)
    # Actually, we rely on 'llm_valid' as the truth from the LLM. 
    # Let's look for Low Confidence Valid items.
    
    if 'llm_confidence' in df.columns:
        console.print(f"\n[bold]Low Confidence Approvals (< 0.7)[/bold]")
        shaky_approvals = df[(df['llm_valid'] == True) & (df['llm_confidence'] < 0.7)]
        if not shaky_approvals.empty:
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Source", style="dim")
            table.add_column("Item")
            table.add_column("Conf")
            table.add_column("Reason")
            
            for _, row in shaky_approvals.head(5).iterrows():
                table.add_row(
                    str(row['source_category'])[:20],
                    str(row['recommended_name'])[:30],
                    f"{row['llm_confidence']:.2f}",
                    str(row['llm_reason'])[:50]
                )
            console.print(table)
        else:
            console.print("None found.")

def main():
    parser = argparse.ArgumentParser(description="Analyze batch results CSV")
    parser.add_argument("file", nargs="?", default="full_recommendations.csv", help="CSV file to analyze")
    args = parser.parse_args()
    
    # Try arguments, then config default, then fallback
    csv_path = Path(args.file)
    if not csv_path.exists():
        csv_path = settings.DATA_DIR / args.file
        
    analyze_results(csv_path)

if __name__ == "__main__":
    main()
