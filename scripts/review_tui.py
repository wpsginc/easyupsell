import sys
from pathlib import Path
import csv

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, DataTable, Static, Label
from textual.containers import Container, Horizontal, Vertical
from textual.binding import Binding

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from config import settings

class ReviewApp(App):
    """A TUI for reviewing upsell recommendations."""
    
    TITLE = "EasyUpsell Review Tool"
    CSS = """
    DataTable {
        height: 60%;
        border: solid green;
    }
    
    #detail-panel {
        height: 40%;
        border: double blue;
        padding: 1;
        background: $boost;
    }
    
    .approved {
        background: green 0.2;
        color: green;
    }
    
    .rejected {
        background: red 0.2;
        color: red;
    }
    """
    
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("a", "approve", "Approve", show=True),
        Binding("r", "reject", "Reject", show=True),
        Binding("s", "save", "Save CSV", show=True),
    ]

    def __init__(self, csv_path: Path):
        super().__init__()
        self.csv_path = csv_path
        self.data = []
        self.load_data()

    def load_data(self):
        """Load recommendations from CSV."""
        if not self.csv_path.exists():
            return
            
        with open(self.csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            self.data = list(reader)
            # Ensure human_status exists
            for row in self.data:
                if "human_status" not in row:
                    row["human_status"] = "Pending"

    def compose(self) -> ComposeResult:
        yield Header()
        yield DataTable()
        yield Static(id="detail-panel")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.cursor_type = "row"
        
        # Add columns
        columns = [
            "Status", "Source Category", "Recommended Item", 
            "Price", "LLM Valid", "Confidence"
        ]
        table.add_columns(*columns)
        
        # Add rows
        for i, row in enumerate(self.data):
            table.add_row(
                row.get("human_status", "Pending"),
                row.get("source_category", ""),
                row.get("recommended_name", ""),
                f"${row.get('recommended_price', '0')}",
                "✅" if str(row.get("llm_valid")) == "True" else "❌",
                row.get("llm_confidence", "0"),
                key=str(i)
            )
            
    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Show details when a row is selected."""
        row_idx = int(event.row_key.value)
        row_data = self.data[row_idx]
        
        detail = self.query_one("#detail-panel", Static)
        
        # Basic Info
        text = f"[bold blue]Source:[/bold blue] {row_data.get('source_category')}\n"
        text += f"[bold blue]Item:[/bold blue] {row_data.get('recommended_name')} ({row_data.get('recommended_sku')})\n"
        
        # Enrichment Data
        if row_data.get('margin_pct'):
            margin = float(row_data['margin_pct']) * 100
            color = "green" if margin > 40 else "yellow" if margin > 20 else "red"
            text += f"[bold]Margin:[/bold] [{color}]{margin:.1f}%[/{color}]  "
            
        if row_data.get('velocity_90d'):
            vel = int(float(row_data['velocity_90d']))
            text += f"[bold]Velocity (90d):[/bold] {vel} units  "
            
        if row_data.get('copurchase_count'):
            text += f"[bold]Co-purchases:[/bold] {row_data['copurchase_count']}\n"
        else:
            text += "\n"
            
        # LLM Info
        text += f"\n[bold blue]LLM Reason:[/bold blue] {row_data.get('llm_reason')}\n"
        text += f"[bold blue]Relationship:[/bold blue] {row_data.get('relationship_type')}\n"
        
        detail.update(text)

    def action_approve(self) -> None:
        """Mark selected row as approved."""
        table = self.query_one(DataTable)
        if table.cursor_row is not None:
            row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
            row_idx = int(row_key.value)
            self.data[row_idx]["human_status"] = "Approved"
            
            # Update table visually (in a real app we'd update the specific cell)
            # For simplicity, we just update the data list and could refresh
            table.update_cell(row_key, table.columns.keys()[0], "Approved")

    def action_reject(self) -> None:
        """Mark selected row as rejected."""
        table = self.query_one(DataTable)
        if table.cursor_row is not None:
            row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
            row_idx = int(row_key.value)
            self.data[row_idx]["human_status"] = "Rejected"
            table.update_cell(row_key, table.columns.keys()[0], "Rejected")

    def action_save(self) -> None:
        """Save the data back to CSV."""
        if not self.data:
            return
            
        fieldnames = list(self.data[0].keys())
        with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.data)
        
        self.notify(f"Saved {len(self.data)} rows to {self.csv_path.name}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("file", nargs="?", default="full_recommendations_v2.csv")
    args = parser.parse_args()
    
    csv_path = Path(args.file)
    if not csv_path.exists():
        csv_path = settings.DATA_DIR / args.file
        
    app = ReviewApp(csv_path)
    app.run()
