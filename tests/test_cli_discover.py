import pytest
from unittest.mock import patch
from typer.testing import CliRunner
from easyupsell.cli import app

runner = CliRunner()

def test_discover_command_help():
    """Test that the discover command is registered and shows help."""
    result = runner.invoke(app, ["discover", "--help"])
    assert result.exit_code == 0
    assert "Discover hidden inventory" in result.stdout or "discover" in result.stdout

def test_discover_command_no_args_error():
    """Test that the discover command fails if no arguments are provided."""
    result = runner.invoke(app, ["discover"])
    assert result.exit_code == 1
    assert "You must specify either --category or --all" in result.stdout

def test_discover_command_both_args_error():
    """Test that the discover command fails if both --category and --all are provided."""
    result = runner.invoke(app, ["discover", "--all", "--category", "Boots"])
    assert result.exit_code == 1
    assert "You cannot specify both --category and --all" in result.stdout

def test_discover_command_all_valid():
    """Test valid execution with --all."""
    with patch("easyupsell.commands.discover.BigCommerceClient") as MockBC:
        with patch("easyupsell.commands.discover.get_all_leaf_categories") as mock_get_leaves:
            mock_get_leaves.return_value = [{"name": "Cat1"}, {"name": "Cat2"}]
            
            # Also mock discovery to avoid waiting/errors
            with patch("easyupsell.commands.discover.discover_dark_horses") as mock_discover:
                mock_discover.return_value = {"pairings": [], "gaps": []}
                
                result = runner.invoke(app, ["discover", "--all"])
                
                assert result.exit_code == 0
                assert "Starting Dark Horse Discovery..." in result.stdout
                assert "Target: ALL 2 Leaf Categories" in result.stdout

def test_discover_command_category_valid():
    """Test valid execution with --category."""
    with patch("easyupsell.commands.discover.BigCommerceClient") as MockBC:
        with patch("easyupsell.commands.discover.get_all_leaf_categories") as mock_get_leaves:
            mock_get_leaves.return_value = [{"name": "Cat1"}]
            
            with patch("easyupsell.commands.discover.discover_dark_horses") as mock_discover:
                mock_discover.return_value = {"pairings": [], "gaps": []}
                
                result = runner.invoke(app, ["discover", "--category", "Boots"])
                
                assert result.exit_code == 0
                assert "Starting Dark Horse Discovery..." in result.stdout
                assert "Target: Single Category 'Boots'" in result.stdout

def test_discover_command_integration():
    """Test that the CLI command calls the core logic."""
    with patch("easyupsell.commands.discover.BigCommerceClient") as MockBC:
        # Mock client returning categories
        mock_client = MockBC.from_env.return_value
        
        with patch("easyupsell.commands.discover.get_all_leaf_categories") as mock_get_leaves:
            mock_get_leaves.return_value = [{"id": 1, "name": "Boots"}]
            
            with patch("easyupsell.commands.discover.discover_dark_horses") as mock_discover:
                mock_discover.return_value = {
                    "pairings": [{"source": "Boots", "target": "Socks", "concept": "Socks"}],
                    "gaps": []
                }
                
                with patch("easyupsell.commands.discover.write_dark_horse_results") as mock_write:
                    result = runner.invoke(app, ["discover", "--category", "Boots"])
                    
                    assert result.exit_code == 0
                    mock_discover.assert_called_once()
                    mock_write.assert_called_once()