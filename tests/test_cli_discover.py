import pytest
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
    result = runner.invoke(app, ["discover", "--all"])
    assert result.exit_code == 0
    assert "Starting Dark Horse Discovery..." in result.stdout
    assert "Target: ALL Leaf Categories" in result.stdout
    assert "Discovery logic not implemented yet" in result.stdout

def test_discover_command_category_valid():
    """Test valid execution with --category."""
    result = runner.invoke(app, ["discover", "--category", "Boots"])
    assert result.exit_code == 0
    assert "Starting Dark Horse Discovery..." in result.stdout
    assert "Target: Single Category 'Boots'" in result.stdout
