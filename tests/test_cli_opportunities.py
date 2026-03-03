from pathlib import Path
from unittest.mock import ANY, patch

from typer.testing import CliRunner

from easyupsell.cli import app


runner = CliRunner()


def _sample_opportunities():
    opportunities = [
        {
            "product_type": "Tactical Helmet",
            "source_categories": ["Protective Gear", "Rescue Gear"],
            "category_count": 2,
            "description": "",
            "price_range_low": "",
            "price_range_high": "",
            "priority": "",
            "sourcing_notes": "",
        }
    ]
    detail_rows = [
        {
            "source_category": "Protective Gear",
            "missing_product_type": "Tactical Helmet",
        }
    ]
    return opportunities, detail_rows


def _sample_stats():
    return {
        "total_opportunities": 1,
        "high_priority": 0,
        "detail_rows": 1,
    }


def test_opportunities_command_help():
    result = runner.invoke(app, ["opportunities", "--help"])

    assert result.exit_code == 0
    assert "New product sourcing opportunities" in result.stdout
    assert "--skip-llm" in result.stdout
    assert "--provider" in result.stdout
    assert "--batch-size" in result.stdout


def test_opportunities_command_is_registered():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "opportunities" in result.stdout


def test_opportunities_command_no_input_failure(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        app, ["opportunities", "--input", "missing_catalog_gaps.csv"]
    )

    assert result.exit_code == 1
    assert "Error: Catalog gaps file not found" in result.stdout
    assert "Run 'pre discover --all' first" in result.stdout


def test_opportunities_command_invalid_batch_size(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(
        app,
        [
            "opportunities",
            "--skip-llm",
            "--batch-size",
            "0",
        ],
    )

    assert result.exit_code == 1
    assert "batch_size must be a positive integer" in result.stdout


def test_opportunities_command_backup_fallback_and_provider_batch_options(
    monkeypatch, tmp_path
):
    monkeypatch.chdir(tmp_path)
    backup_file = tmp_path / "data" / "data.backup" / "catalog_gaps.csv"
    backup_file.parent.mkdir(parents=True, exist_ok=True)
    backup_file.write_text("source_category,missing_product_type\n")

    opportunities, detail_rows = _sample_opportunities()

    with patch(
        "easyupsell.commands.opportunities.load_and_deduplicate_gaps"
    ) as mock_load:
        mock_load.return_value = (opportunities, detail_rows)

        with patch(
            "easyupsell.commands.opportunities.enrich_opportunities_batch"
        ) as mock_enrich:
            mock_enrich.return_value = opportunities

            with patch(
                "easyupsell.commands.opportunities.write_opportunities_excel"
            ) as mock_write:
                mock_write.return_value = _sample_stats()

                result = runner.invoke(
                    app,
                    [
                        "opportunities",
                        "--input",
                        "missing_catalog_gaps.csv",
                        "--provider",
                        "athena",
                        "--batch-size",
                        "7",
                    ],
                )

    assert result.exit_code == 0
    assert "Using backup" in result.stdout
    mock_load.assert_called_once_with(Path("data/data.backup/catalog_gaps.csv"))
    mock_enrich.assert_called_once_with(
        opportunities,
        provider="athena",
        batch_size=7,
        progress_callback=ANY,
    )


def test_opportunities_skip_llm_path_calls_writer_without_enricher(
    monkeypatch, tmp_path
):
    monkeypatch.chdir(tmp_path)
    input_file = tmp_path / "data" / "catalog_gaps.csv"
    input_file.parent.mkdir(parents=True, exist_ok=True)
    input_file.write_text("source_category,missing_product_type\n")

    opportunities, detail_rows = _sample_opportunities()

    with patch(
        "easyupsell.commands.opportunities.load_and_deduplicate_gaps"
    ) as mock_load:
        mock_load.return_value = (opportunities, detail_rows)

        with patch(
            "easyupsell.commands.opportunities.enrich_opportunities_batch"
        ) as mock_enrich:
            with patch(
                "easyupsell.commands.opportunities.write_opportunities_excel"
            ) as mock_write:
                mock_write.return_value = _sample_stats()

                result = runner.invoke(
                    app,
                    [
                        "opportunities",
                        "--input",
                        str(input_file),
                        "--skip-llm",
                    ],
                )

    assert result.exit_code == 0
    assert "Skipping LLM enrichment (--skip-llm)" in result.stdout
    mock_load.assert_called_once_with(input_file)
    mock_enrich.assert_not_called()
    mock_write.assert_called_once_with(
        opportunities, detail_rows, Path("data/new_product_opportunities.xlsx")
    )
